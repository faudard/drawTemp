"""Global strategic clock for several simultaneous tactical fronts.

Inactive fronts resolve one deterministic strategic step at each synchronization.
The focused front is never auto-resolved. All fronts share one clock.
"""
from copy import deepcopy
from .model import require
from . import front_links
from .logistics import LogisticsDirector, destination_actors
from .convoy_choices import ConvoyChoicesMixin
from .campaign_strategy import SiegeCampaign, CampaignChoicesMixin
from .campaign_routes import CampaignRoutesPolicy, CampaignRoutesMixin

DOCTRINES = {"hold", "assault", "delay", "retreat"}


class FrontDirector:
    def __init__(self, fronts, focused, *, seed=1):
        require(isinstance(fronts, dict) and bool(fronts), "Fronts must be a nonempty mapping")
        require(focused in fronts, "Unknown focused front")
        self.fronts = {}
        for name, spec in fronts.items():
            require(isinstance(name, str) and name and isinstance(spec, dict), "Invalid front")
            doctrine = spec.get("doctrine", "hold")
            require(doctrine in DOCTRINES, "Unknown front doctrine")
            strength = spec.get("strength", 10)
            opposition = spec.get("opposition", 10)
            require(all(type(n) is int and 0 <= n <= 10000 for n in (strength, opposition)),
                    "Invalid front strength")
            self.fronts[name] = {"strength": strength, "opposition": opposition,
                                 "doctrine": doctrine, "status": "active"}
        require(type(seed) is int, "Seed must be an integer")
        self.seed = seed
        self.focused = focused
        self.turn = 0
        self.events = []

    def switch(self, front):
        require(front in self.fronts, "Unknown front")
        require(self.fronts[front]["status"] == "active", "Front already resolved")
        previous = self.focused
        self.focused = front
        self.events.append({"turn": self.turn, "kind": "focus_changed",
                            "from": previous, "to": front})

    def set_doctrine(self, front, doctrine):
        require(front in self.fronts and doctrine in DOCTRINES, "Invalid doctrine")
        require(self.fronts[front]["status"] == "active", "Front already resolved")
        self.fronts[front]["doctrine"] = doctrine

    def advance(self):
        """One strategic turn; automatic results do not depend on iteration order."""
        self.turn += 1
        for name in sorted(self.fronts):
            if name == self.focused or name in getattr(self, "tactical_only", ()):
                continue
            front = self.fronts[name]
            if front["status"] != "active":
                continue
            doctrine = front["doctrine"]
            attack = {"hold": 1, "assault": 3, "delay": 0, "retreat": 0}[doctrine]
            defense = {"hold": 2, "assault": 0, "delay": 1, "retreat": 3}[doctrine]
            front["opposition"] = max(0, front["opposition"] - min(front["strength"], attack))
            front["strength"] = max(0, front["strength"] - max(0, 2 - defense))
            if doctrine == "retreat":
                front["status"] = "withdrawn"
            elif front["opposition"] == 0:
                front["status"] = "victory"
            elif front["strength"] == 0:
                front["status"] = "defeat"
            self.events.append({"turn": self.turn, "kind": "front_resolved",
                                "front": name, **deepcopy(front)})
        return self.state()

    def state(self):
        return {"turn": self.turn, "focused": self.focused,
                "fronts": deepcopy(self.fronts), "events": deepcopy(self.events)}

    def restore(self, state):
        require(isinstance(state, dict) and type(state.get("turn")) is int
                and state["turn"] >= 0 and state.get("focused") in self.fronts,
                "Invalid front state")
        require(isinstance(state.get("fronts"), dict)
                and set(state["fronts"]) == set(self.fronts)
                and isinstance(state.get("events"), list), "Invalid front state")
        self.turn = state["turn"]
        self.focused = state["focused"]
        self.fronts = deepcopy(state["fronts"])
        self.events = deepcopy(state["events"])


class MultiFrontSession(CampaignRoutesMixin, CampaignChoicesMixin, ConvoyChoicesMixin):
    """Deterministic tactical/strategic session with an explicit command journal.

    Use execute() rather than calling active.execute() directly when a session
    must be saved or replayed. Strategic changes are not Battle commands: only
    the multi-front journal can reconstruct offscreen attrition.
    """

    def __init__(self, content, missions, focused, *, seed=1, rules=None, specs=None, links=None, logistics=None, campaign=None):
        from .engine import Battle
        from .rules import default_rules
        require(isinstance(missions, dict) and bool(missions) and focused in missions,
                "Invalid multi-front missions")
        require(all(isinstance(name, str) and name and isinstance(mid, str)
                    and mid in content.missions for name, mid in missions.items()),
                "Unknown front mission")
        definitions = deepcopy(specs) if specs is not None else {name: {} for name in missions}
        require(isinstance(definitions, dict) and set(definitions) == set(missions),
                "Front specifications must match mission names")
        self.content = deepcopy(content)
        self.missions = dict(missions)
        self.rules = rules if rules is not None else default_rules()
        self.seed = seed
        self.initial_focus = focused
        self.initial_specs = deepcopy(definitions)
        self.timeline = FrontDirector(definitions, focused, seed=seed)
        self.initial_fronts = deepcopy(self.timeline.fronts)
        self.battles = {}
        self.front_snapshots = {}
        self.pending_reinforcements = {}
        self.history = []
        self.initial_campaign = deepcopy(campaign) if campaign is not None else None
        self.campaign = (SiegeCampaign(self.initial_campaign, self.content, self.missions)
                         if self.initial_campaign is not None else None)
        self.route_policy = None
        if self.campaign is not None and "routes" in self.initial_campaign:
            self.route_policy = CampaignRoutesPolicy(
                {"routes": self.initial_campaign["routes"],
                 "recovery": self.initial_campaign["recovery"],
                 "treaties": self.initial_campaign["treaties"]},
                self.content, self.missions, self.campaign.final)
        self.route_selected = "breach"
        self.route_locked = False
        if self.route_policy is not None:
            # These fronts require *played* tactical wins; an aggregate
            # off-screen battle may never unlock a route or the final boss.
            extra = {front for route in self.route_policy.routes.values()
                     for front in route["required"]
                     if front not in self.campaign.spec["required_fronts"]}
            self.timeline.tactical_only = extra | {self.campaign.final}
        self.recovery_battles = {}
        self.recovery_outcomes = {}
        if self.campaign is not None:
            require(focused != self.campaign.final
                    or all(self.timeline.fronts[f]["status"] in outcomes
                           for f, outcomes in
                           (self.route_policy.routes["breach"]["required"]
                            if self.route_policy is not None else
                            self.campaign.spec["required_fronts"]).items()),
                    "Cannot begin on a locked final front")
        self.initial_logistics = deepcopy(logistics) if logistics is not None else None
        self.logistics = (LogisticsDirector(self.initial_logistics, self.missions)
                          if self.initial_logistics is not None else None)
        self.rescue_battles = {}
        self.rescue_outcomes = {}
        self.pursuit_targets = {}
        self.pursuit_battles = {}
        self.pursuit_outcomes = {}
        self._validate_pursuit_mission()
        if self.logistics is not None and self.logistics.rescue_mission is not None:
            mid = self.logistics.rescue_mission
            require(mid in self.content.missions, "Unknown rescue mission")
            mission = self.content.missions[mid]
            require(mission.objective == "eliminate" and mission.protected_id
                    and any(u.id == mission.protected_id and u.team == "player"
                            for u in mission.units)
                    and any(u.id != mission.protected_id and u.team == "player"
                            for u in mission.units)
                    and any(u.team == "enemy" for u in mission.units),
                    "Rescue mission needs a wagon, escort fighters, enemy and elimination goal")
        self.links = deepcopy(links if links is not None else [])
        front_links.validate(self.content, self.missions, self.links)
        self.applied_links = set()
        self.front_overrides = {}
        self.blocked_reinforcements = set()
        self.battles[focused] = self._new_battle(focused)

    def _new_battle(self, front):
        from .engine import Battle
        prepared = deepcopy(self.content)
        front_links.configure_mission(
            prepared, self.missions[front], self.front_overrides.get(front, {}),
            front in self.blocked_reinforcements)
        return Battle(prepared, self.missions[front],
                      seed=self.seed + sorted(self.missions).index(front)
                      if front != self.initial_focus else self.seed,
                      rules=self.rules)

    @property
    def active(self):
        return self.battles[self.timeline.focused]

    def execute(self, command):
        """Execute exactly one player/AI command on the focused front."""
        require(not self.rescue_battles and not self.pursuit_battles
                and not self.recovery_battles,
                "Resolve the tactical side mission first")
        if self.campaign is not None:
            require(self.timeline.fronts[self.timeline.focused]["status"]
                    not in {"partial", "negotiated", "withdrawn", "reclaimed"},
                    "Resolved campaign front cannot accept more tactical orders")
        require(isinstance(command, dict), "Expected tactical command")
        # Battle.execute is transactional. Linking other fronts must be just as
        # atomic, including their events, aggregate scores and future overrides.
        snapshot = deepcopy((self.timeline, self.battles, self.front_overrides,
                             self.blocked_reinforcements, self.pending_reinforcements,
                             self.applied_links))
        source = self.timeline.focused
        try:
            start = len(self.active.events)
            self.active.execute(deepcopy(command))
            for event in self.battles[source].events[start:]:
                for link in self.links:
                    if (link["source"] == source and link["id"] not in self.applied_links
                            and front_links.match(link, event)):
                        front_links.apply(self, link)
            if self.campaign is not None and self.active.result in {"victory", "defeat"}:
                row = self.timeline.fronts[source]
                if row["status"] == "active":
                    row["status"] = self.active.result
                    self.timeline.events.append({
                        "turn": self.timeline.turn, "kind": "campaign_battle_resolved",
                        "front": source, "outcome": row["status"]})
        except Exception:
            (self.timeline, self.battles, self.front_overrides,
             self.blocked_reinforcements, self.pending_reinforcements,
             self.applied_links) = snapshot
            raise
        self.history.append({"kind": "execute", "command": deepcopy(command)})

    def set_doctrine(self, front, doctrine):
        self.timeline.set_doctrine(front, doctrine)
        self.history.append({"kind": "doctrine", "front": front, "doctrine": doctrine})

    def switch(self, front):
        require(not self.rescue_battles and not self.pursuit_battles
                and not self.recovery_battles,
                "Resolve the tactical side mission first")
        require(front in self.missions, "Unknown front")
        if self.campaign is not None:
            self.campaign.gate(self, front)
        require(self.active.active is None or (not self.active.active.moved
                and not self.active.active.acted),
                "Finish the active unit turn before switching fronts")
        snapshot = deepcopy((self.timeline, self.battles, self.front_snapshots,
                             self.pending_reinforcements))
        try:
            self.timeline.switch(front)
            if front not in self.battles:
                self.battles[front] = self._new_battle(front)
                # An unopened front has already fought its offscreen turns.
                # Materialize those losses once when it first gains focus.
                initial = self.initial_fronts[front]
                current = self.timeline.fronts[front]
                self._apply_attrition(self.battles[front], "player",
                                      initial["strength"] - current["strength"])
                self._apply_attrition(self.battles[front], "enemy",
                                      initial["opposition"] - current["opposition"])
            self.front_snapshots.pop(front, None)
            self._deliver_reinforcements(front)
        except Exception:
            (self.timeline, self.battles, self.front_snapshots,
             self.pending_reinforcements) = snapshot
            raise
        self.history.append({"kind": "switch", "front": front})
        return self.active

    def reinforce(self, front, actors, *, lifetime=None):
        """Queue a concrete wave for either a loaded or an unopened front."""
        from .encounters import EncounterDirector
        require(front in self.missions and self.timeline.fronts[front]["status"] == "active",
                "Unknown or inactive reinforcement front")
        require(front not in self.blocked_reinforcements,
                "Reinforcements interdicted on this front")
        # Validate capacity and lifetime now, not after the player switches.
        EncounterDirector().queue(actors, lifetime=lifetime)
        self.pending_reinforcements.setdefault(front, []).append(
            {"actors": deepcopy(actors), "lifetime": lifetime})
        self.timeline.events.append({"turn": self.timeline.turn, "kind": "reinforcement_queued",
                                     "front": front, "count": len(actors)})
        self.history.append({"kind": "reinforce", "front": front,
                             "actors": deepcopy(actors), "lifetime": lifetime})

    def _deliver_reinforcements(self, front):
        battle = self.battles[front]
        waves = self.pending_reinforcements.pop(front, [])
        for wave in waves:
            battle.queue_wave(wave["actors"], lifetime=wave["lifetime"])

    def _check_convoy_destination(self, front, actors):
        require(self.timeline.fronts[front]["status"] == "active",
                "Destination front is no longer active")
        require(front not in self.blocked_reinforcements,
                "The destination is under reinforcement interdiction")
        return destination_actors(self, front, actors)

    def send_reserves(self, destination, actors):
        """Spend a finite strategic pool and send one bounded convoy.

        The destination must have an authored reserve route. This never
        creates tactical units until a later strategic synchronization.
        """
        require(self.logistics is not None, "Strategic logistics not configured")
        require(destination in self.missions, "Unknown reserve destination")
        snapshot = deepcopy((self.logistics, self.timeline))
        try:
            validated = self._check_convoy_destination(destination, actors)
            teams = {actor["team"] for actor in validated}
            require(len(teams) == 1, "Reserve convoy must use one team")
            team = next(iter(teams))
            require(self.logistics.reserves[team] >= len(validated),
                    "Insufficient strategic reserves")
            convoy_id = self.logistics.order(
                "reserve", destination, validated, team, self.timeline.turn)
            self.logistics.spend_supplies(team, len(validated))
            self.logistics.reserves[team] -= len(validated)
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "reserves_dispatched",
                "convoy": convoy_id, "front": destination, "team": team,
                "count": len(validated)})
        except Exception:
            self.logistics, self.timeline = snapshot
            raise
        self.history.append({"kind": "send_reserves", "front": destination,
                             "actors": deepcopy(actors)})
        return convoy_id

    def transfer_units(self, destination, placements):
        """Move idle living players from the focused battle to another front.

        placements: {unit_id: [x, y]}. Members leave their original Battle
        immediately; current CT, casting and reaction reservations do not
        travel. HP, MP, equipment stats and statuses survive the journey.
        """
        from dataclasses import asdict
        require(self.logistics is not None, "Strategic logistics not configured")
        source = self.timeline.focused
        require(destination in self.missions and destination != source,
                "Invalid transfer destination")
        require(isinstance(placements, dict) and bool(placements),
                "Transfer needs unit placements")
        battle = self.active
        require(not battle.deploying and battle.result is None,
                "Finish deployment before transfers")
        selected = []
        for uid, pos in sorted(placements.items()):
            require(isinstance(uid, str) and bool(uid), "Invalid transfer id")
            actor = next((u for u in battle.units if u.id == uid), None)
            require(actor is not None and actor.alive and actor.team == "player",
                    "Only living friendly actors can transfer")
            require(actor.id != battle.active_id and actor.id != battle.carrier
                    and actor.id != battle.mission.protected_id,
                    "Active, carrying or protected actors cannot depart")
            require(actor.kind != "summon" and actor.cast is None
                    and not actor.moved and not actor.acted
                    and actor.id not in battle.summon_owners,
                    "Actor must be an idle permanent unit")
            definition = asdict(actor)
            definition.update(pos=pos, ct=0, moved=False, acted=False,
                              cast=None, disengaging=False)
            selected.append(definition)
        remaining = sum(u.alive and u.team == "player"
                        and u.id not in placements for u in battle.units)
        require(remaining > 0, "A front must retain a friendly defender")
        require(self.timeline.fronts[source]["strength"] > len(selected),
                "Cannot empty the source strategic front")
        snapshot = deepcopy((self.timeline, self.battles, self.logistics))
        try:
            validated = self._check_convoy_destination(destination, selected)
            convoy_id = self.logistics.order(source, destination, validated,
                                             "player", self.timeline.turn)
            self.logistics.spend_supplies("player", len(validated))
            for definition in selected:
                battle.despawn_actor(definition["id"])
            own_front = self.timeline.fronts[source]
            own_front["strength"] = max(0, own_front["strength"] - len(selected))
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "units_departed",
                "convoy": convoy_id, "from": source, "to": destination,
                "units": [actor["id"] for actor in selected]})
        except Exception:
            self.timeline, self.battles, self.logistics = snapshot
            raise
        self.history.append({"kind": "transfer_units", "destination": destination,
                             "placements": deepcopy(placements)})
        return convoy_id

    def escort_convoy(self, convoy_id):
        """Commit one limited escort token before an ambush is evaluated."""
        require(self.logistics is not None, "Strategic logistics not configured")
        convoy = self.logistics.convoy(convoy_id)
        require(not convoy.get("stranded") and not convoy.get("ambushed")
                and not convoy.get("escorted"), "Convoy cannot be escorted now")
        require(self.logistics.escorts > 0, "No escort orders remaining")
        self.logistics.escorts -= 1
        convoy["escorted"] = True
        self.timeline.events.append({
            "turn": self.timeline.turn, "kind": "escort_assigned",
            "convoy": convoy_id})
        self.history.append({"kind": "escort_convoy", "convoy": convoy_id})

    def rescue_convoy(self, convoy_id):
        """Recover an ambushed stranded convoy using one provision."""
        require(self.logistics is not None, "Strategic logistics not configured")
        convoy = self.logistics.convoy(convoy_id)
        require(convoy_id not in self.rescue_battles,
                "Cannot bypass an active tactical rescue")
        require(convoy.get("stranded") is True and convoy["actors"],
                "Only a stranded surviving convoy can be rescued")
        self.logistics.spend_supplies(convoy["team"], 1)
        convoy.pop("stranded")
        convoy["arrival"] = max(convoy["arrival"], self.timeline.turn + 1)
        self.timeline.events.append({
            "turn": self.timeline.turn, "kind": "convoy_rescued",
            "convoy": convoy_id, "arrival": convoy["arrival"]})
        self.history.append({"kind": "rescue_convoy", "convoy": convoy_id})

    def start_rescue(self, convoy_id):
        """Enter a genuine small tactical Battle for one stranded convoy."""
        from .engine import Battle
        require(self.logistics is not None and self.logistics.rescue_mission is not None,
                "Tactical convoy rescue is not enabled")
        require(not self.rescue_battles and not self.pursuit_battles,
                "Finish the current tactical side mission first")
        require(convoy_id not in self.rescue_outcomes, "Rescue already resolved")
        convoy = self.logistics.convoy(convoy_id)
        require(convoy.get("stranded") is True and convoy["actors"],
                "Only a stranded surviving convoy can enter a rescue mission")
        require(self.timeline.fronts[convoy["to"]]["status"] == "active",
                "Cannot rescue a convoy heading to a resolved front")
        # The rescue mission's fighters are a separate escort squad; travelling
        # roster actors remain in the convoy manifest until the outcome is known.
        battle = Battle(self.content, self.logistics.rescue_mission,
                        seed=self.seed + 10000 + self.logistics.serial,
                        rules=self.rules)
        self.rescue_battles[convoy_id] = battle
        self.timeline.events.append({"turn": self.timeline.turn,
                                     "kind": "convoy_rescue_started",
                                     "convoy": convoy_id,
                                     "mission": battle.mission.id})
        self.history.append({"kind": "start_rescue", "convoy": convoy_id})
        return battle

    def _finish_rescue(self, convoy_id):
        """Apply an actual Battle outcome, not a fabricated strategic victory."""
        battle = self.rescue_battles[convoy_id]
        require(battle.result in {"victory", "defeat"},
                "Rescue battle must have a final result")
        convoy = self.logistics.convoy(convoy_id)
        if battle.result == "victory":
            require(convoy.get("stranded") is True,
                    "Cannot finish a convoy which is no longer stranded")
            convoy.pop("stranded")
            convoy["arrival"] = max(convoy["arrival"], self.timeline.turn + 1)
            # Recover a small amount of supplies from the raider camp.
            if self.logistics.supplies is not None:
                team = convoy["team"]
                self.logistics.supplies[team] = min(
                    10000, self.logistics.supplies[team] + 1)
            event_kind = "convoy_rescue_victory"
        else:
            self.logistics.in_transit.remove(convoy)
            event_kind = "convoy_rescue_defeat"
        self.rescue_outcomes[convoy_id] = battle.result
        del self.rescue_battles[convoy_id]
        self.timeline.events.append({"turn": self.timeline.turn,
                                     "kind": event_kind, "convoy": convoy_id,
                                     "units": [u["id"] for u in convoy["actors"]]})

    def execute_rescue(self, convoy_id, command):
        """Execute one normal Battle command and settle victory/defeat atomically."""
        require(isinstance(command, dict) and convoy_id in self.rescue_battles,
                "Unknown active rescue battle or invalid command")
        snapshot = deepcopy((self.rescue_battles, self.rescue_outcomes,
                             self.logistics, self.timeline))
        try:
            battle = self.rescue_battles[convoy_id]
            battle.execute(deepcopy(command))
            # A defenseless cart cannot win once every non-wagon escort has
            # fallen. The ordinary eliminate objective alone would otherwise
            # leave an unarmed cart trapped against surviving bandits forever.
            if (battle.result is None
                    and not any(u.team == "player"
                                and u.id != battle.mission.protected_id and u.alive
                                for u in battle.units)):
                battle.result = "defeat"
                battle.active_id = None
                battle.emit("battle_end", result="defeat")
            if battle.result is not None:
                self._finish_rescue(convoy_id)
        except Exception:
            (self.rescue_battles, self.rescue_outcomes,
             self.logistics, self.timeline) = snapshot
            raise
        self.history.append({"kind": "execute_rescue", "convoy": convoy_id,
                             "command": deepcopy(command)})

    def abandon_convoy(self, convoy_id):
        """Explicit no-resource-cost withdrawal: lose the cargo and its actors."""
        require(self.logistics is not None, "Strategic logistics not configured")
        convoy = self.logistics.convoy(convoy_id)
        require(convoy.get("stranded") is True, "Only stranded convoys can be abandoned")
        if self.rescue_battles:
            require(convoy_id in self.rescue_battles,
                    "A different tactical rescue is in progress")
            del self.rescue_battles[convoy_id]
        self.logistics.in_transit.remove(convoy)
        self.rescue_outcomes[convoy_id] = "abandoned"
        self.timeline.events.append({
            "turn": self.timeline.turn, "kind": "convoy_abandoned",
            "convoy": convoy_id, "lost": [u["id"] for u in convoy["actors"]]})
        self.history.append({"kind": "abandon_convoy", "convoy": convoy_id})

    def _resolve_ambushes(self):
        """One deterministic ambush opportunity per convoy; no tactical AI."""
        if self.logistics is None:
            return
        for convoy in list(self.logistics.in_transit):
            key = (convoy["from"], convoy["to"])
            hazard = self.logistics.ambushes.get(key)
            if (hazard is None or hazard["charges"] == 0
                    or convoy.get("ambushed")):
                continue
            if self.timeline.fronts[convoy["to"]]["status"] != "active":
                continue
            convoy["ambushed"] = True
            if convoy.get("escorted"):
                self.timeline.events.append({
                    "turn": self.timeline.turn, "kind": "ambush_prevented",
                    "convoy": convoy["id"]})
                continue
            hazard["charges"] -= 1
            removed = convoy["actors"][-hazard["casualties"]:] if hazard["casualties"] else []
            if removed:
                del convoy["actors"][-len(removed):]
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "convoy_ambushed",
                "convoy": convoy["id"], "lost": [u["id"] for u in removed],
                "survivors": len(convoy["actors"]), "route": list(key)})
            if not convoy["actors"]:
                self.logistics.in_transit.remove(convoy)
                self.timeline.events.append({
                    "turn": self.timeline.turn, "kind": "convoy_lost",
                    "convoy": convoy["id"], "front": convoy["to"],
                    "reason": "ambush"})
                continue
            convoy["stranded"] = True
            convoy["arrival"] = max(convoy["arrival"], self.timeline.turn) + hazard["delay"]
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "convoy_stranded",
                "convoy": convoy["id"], "arrival": convoy["arrival"]})

    def _arrive_convoys(self):
        if self.logistics is None:
            return
        for convoy in self.logistics.due(self.timeline.turn):
            front = convoy["to"]
            if (self.timeline.fronts[front]["status"] != "active"
                    or front in self.blocked_reinforcements):
                self.timeline.events.append({
                    "turn": self.timeline.turn, "kind": "convoy_lost",
                    "convoy": convoy["id"], "front": front,
                    "reason": "front_inactive" if self.timeline.fronts[front]["status"]
                    != "active" else "interdicted"})
                continue
            self.pending_reinforcements.setdefault(front, []).append({
                "actors": deepcopy(convoy["actors"]), "lifetime": None})
            row = self.timeline.fronts[front]
            field = "strength" if convoy["team"] == "player" else "opposition"
            row[field] = min(10000, row[field] + len(convoy["actors"]))
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "convoy_arrived",
                "convoy": convoy["id"], "front": front,
                "count": len(convoy["actors"]), "team": convoy["team"]})

    def advance(self):
        """One strategic turn; automatic fights never execute tactical AI."""
        require(not self.rescue_battles and not self.pursuit_battles
                and not self.recovery_battles,
                "Resolve the tactical side mission before advancing the timeline")
        snapshot = deepcopy((self.timeline, self.battles, self.front_snapshots,
                             self.pending_reinforcements, self.logistics))
        try:
            for name, battle in self.battles.items():
                if (battle.result in {"victory", "defeat"}
                        and self.timeline.fronts[name]["status"] == "active"):
                    self.timeline.fronts[name]["status"] = battle.result
            before = deepcopy(self.timeline.fronts)
            self.timeline.advance()
            if self.campaign is not None:
                for name in sorted(self.campaign.spec["retreat"]):
                    if (before[name]["status"] == "active"
                            and self.timeline.fronts[name]["status"] == "withdrawn"):
                        rule = self.campaign.spec["retreat"][name]
                        self._lose_campaign_strength(rule["target"], rule["target_loss"])
                        self.timeline.events.append({
                            "turn": self.timeline.turn, "kind": "campaign_retreat_cost",
                            "front": name, "target": rule["target"],
                            "strength_loss": rule["target_loss"]})
            self._resolve_ambushes()
            self._arrive_convoys()
            self._deliver_reinforcements(self.timeline.focused)
            for name, battle in self.battles.items():
                if name == self.timeline.focused or battle.result is not None:
                    continue
                old, new = before[name], self.timeline.fronts[name]
                if old["status"] != "active":
                    continue
                self._apply_attrition(battle, "player",
                                      old["strength"] - new["strength"])
                self._apply_attrition(battle, "enemy",
                                      old["opposition"] - new["opposition"])
                if new["status"] in {"victory", "defeat"}:
                    loser = "enemy" if new["status"] == "victory" else "player"
                    self._apply_attrition(battle, loser, 1000000)
                    battle.result = new["status"]
                    battle.active_id = None
                    battle.emit("battle_end", result=battle.result)
            for name, front in self.timeline.fronts.items():
                if name != self.timeline.focused and name in self.battles:
                    self.front_snapshots[name] = deepcopy(front)
        except Exception:
            (self.timeline, self.battles, self.front_snapshots,
             self.pending_reinforcements, self.logistics) = snapshot
            raise
        self.history.append({"kind": "advance"})
        return self.timeline.state()

    @staticmethod
    def _apply_attrition(battle, team, amount):
        """Apply strategic losses in stable unit order without running CT ticks."""
        remaining = max(0, amount)
        total = 0
        for unit in sorted((u for u in battle.units if u.team == team and u.alive),
                           key=lambda u: u.id):
            if remaining == 0:
                break
            damage = min(unit.hp, remaining)
            unit.hp -= damage
            total += damage
            remaining -= damage
        if total:
            battle.emit("strategic_attrition", team=team, amount=total)

    def state(self):
        state = {"timeline": self.timeline.state(), "missions": dict(self.missions),
                 "battles": {name: battle.state() for name, battle in sorted(self.battles.items())},
                 "front_snapshots": deepcopy(self.front_snapshots),
                 "pending_reinforcements": deepcopy(self.pending_reinforcements)}
        # Preserve version-1 checksum semantics for sessions without links.
        if self.campaign is not None:
            state["campaign"] = self.campaign.state(self)
        if self.logistics is not None:
            state["logistics"] = self.logistics.state()
            if self.logistics.rescue_mission is not None:
                state["rescue_battles"] = {
                    key: battle.state() for key, battle in sorted(self.rescue_battles.items())}
                state["rescue_outcomes"] = deepcopy(self.rescue_outcomes)
            if self.logistics.choices is not None:
                state["pursuit_targets"] = deepcopy(self.pursuit_targets)
                state["pursuit_battles"] = {
                    key: battle.state() for key, battle in sorted(self.pursuit_battles.items())}
                state["pursuit_outcomes"] = deepcopy(self.pursuit_outcomes)
        if self.links:
            state["links"] = deepcopy(self.links)
            state["applied_links"] = sorted(self.applied_links)
            state["front_overrides"] = deepcopy(self.front_overrides)
            state["blocked_reinforcements"] = sorted(self.blocked_reinforcements)
        return state

    def digest(self):
        import hashlib
        import json
        return hashlib.sha256(json.dumps(self.state(), sort_keys=True).encode()).hexdigest()

    def recording(self):
        """Portable journal; replay proves all tactical and strategic mutations."""
        extended = self.logistics is not None and self.logistics._extended
        return {"version": 5 if self.campaign is not None else
                4 if extended else 3 if self.logistics is not None else 2,
                "kind": "multi_front",
                "content": self.content.to_dict(), "missions": dict(self.missions),
                "focused": self.initial_focus, "specs": deepcopy(self.initial_specs),
                "links": deepcopy(self.links),
                **({"campaign": deepcopy(self.initial_campaign)}
                   if self.campaign is not None else {}),
                **({"logistics": deepcopy(self.initial_logistics)}
                   if self.logistics is not None else {}),
                "seed": self.seed, "rules": self.rules.manifest(),
                "operations": deepcopy(self.history), "digest": self.digest()}

    @classmethod
    def replay(cls, recording, *, rules=None):
        from .model import Content
        from .rules import default_rules
        require(isinstance(recording, dict) and recording.get("version") in {1, 2, 3, 4, 5}
                and recording.get("kind") == "multi_front", "Unsupported multi-front save")
        effective_rules = rules if rules is not None else default_rules()
        require(recording.get("rules") == effective_rules.manifest(),
                "Multi-front ruleset mismatch")
        session = cls(Content.from_dict(recording["content"], rules=effective_rules),
                      recording["missions"], recording["focused"],
                      seed=recording["seed"], rules=effective_rules,
                      specs=recording["specs"],
                      links=recording.get("links", []) if recording["version"] >= 2 else [],
                      logistics=recording.get("logistics")
                      if recording["version"] in {3, 4, 5} else None,
                      campaign=recording["campaign"] if recording["version"] == 5 else None)
        for operation in recording["operations"]:
            kind = operation["kind"]
            if kind == "execute":
                session.execute(operation["command"])
            elif kind == "switch":
                session.switch(operation["front"])
            elif kind == "advance":
                session.advance()
            elif kind == "doctrine":
                session.set_doctrine(operation["front"], operation["doctrine"])
            elif kind == "reinforce":
                session.reinforce(operation["front"], operation["actors"],
                                  lifetime=operation["lifetime"])
            elif kind == "send_reserves":
                session.send_reserves(operation["front"], operation["actors"])
            elif kind == "transfer_units":
                session.transfer_units(operation["destination"], operation["placements"])
            elif kind == "escort_convoy":
                session.escort_convoy(operation["convoy"])
            elif kind == "rescue_convoy":
                session.rescue_convoy(operation["convoy"])
            elif kind == "start_rescue":
                session.start_rescue(operation["convoy"])
            elif kind == "execute_rescue":
                session.execute_rescue(operation["convoy"], operation["command"])
            elif kind == "abandon_convoy":
                session.abandon_convoy(operation["convoy"])
            elif kind == "evacuate_convoy":
                session.evacuate_convoy(operation["convoy"])
            elif kind == "salvage_convoy":
                session.salvage_convoy(operation["convoy"])
            elif kind == "negotiate_convoy":
                session.negotiate_convoy(operation["convoy"])
            elif kind == "start_pursuit":
                session.start_pursuit(operation["convoy"])
            elif kind == "execute_pursuit":
                session.execute_pursuit(operation["convoy"], operation["command"])
            elif kind == "abandon_pursuit":
                session.abandon_pursuit(operation["convoy"])
            elif kind == "partial_front":
                session.partial_front(operation["front"])
            elif kind == "negotiate_front":
                session.negotiate_front(operation["front"])
            elif kind == "withdraw_front":
                session.withdraw_front(operation["front"])
            elif kind == "select_route":
                session.select_route(operation["route"])
            elif kind == "start_recovery":
                session.start_recovery(operation["front"])
            elif kind == "execute_recovery":
                session.execute_recovery(operation["front"], operation["command"])
            elif kind == "abandon_recovery":
                session.abandon_recovery(operation["front"])
            else:
                require(False, "Unknown multi-front operation")
        require(session.digest() == recording["digest"], "Multi-front checksum mismatch")
        return session

    def restore(self, recording):
        """Reconstruct combat from an authenticated journal, never from Battle.state()."""
        require(isinstance(recording, dict) and recording.get("kind") == "multi_front",
                "Pass a multi-front recording, not a public state snapshot")
        restored = self.replay(recording, rules=self.rules)
        require(restored.missions == self.missions
                and restored.content.to_dict() == self.content.to_dict()
                and restored.links == self.links
                and restored.initial_logistics == self.initial_logistics
                and restored.initial_campaign == self.initial_campaign,
                "Incompatible multi-front save")
        self.__dict__.update(restored.__dict__)
