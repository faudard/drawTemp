"""Unified campaign, story and tactical lifecycle. No UI or new combat rules."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib
import json

from .ai import play_activation
from .campaign import Campaign
from .campaign_flow import (available_missions as flow_available_missions,
                            inspect_campaign as flow_inspect_campaign,
                            settle as settle_campaign_flow, verify_save as verify_flow_save)
from .engine import Battle
from .exploration import Exploration
from .world_travel import PENDING, WorldJourney
from .fronts import MultiFrontSession
from .model import RuleError, require
from .narrative import StoryBook
from .rules import default_rules
from .storage import write_json


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gameplay_project_digest(project):
    """Fingerprint game-affecting project data, not decorative world positions.

    Legacy projects without a world preserve their exact original digest.
    Adding/moving map pins cannot invalidate a persisted Campaign checkpoint.
    Other story, campaign, asset and gameplay fields remain strictly verified.
    """
    manifest = project.to_dict()
    world = manifest.pop("world", {})
    # Decorative positions remain save-compatible, but authored encounters
    # affect gameplay and must invalidate incompatible checkpoints.
    if world.get("events"):
        manifest["world_events"] = world["events"]
    return digest(manifest)


class IncompatibleSaveError(RuleError):
    """A verified save belongs to other content, project or gameplay rules.

    Identity changes are never coerced, reconstructed or replayed with new
    rules. A future migration must be opt-in and independently verified.
    """

    def __init__(self, dimension, saved, running):
        def fingerprint(value):
            return value[:12] if isinstance(value, str) and len(value) == 64 else digest(value)[:12]

        self.dimension = dimension
        super().__init__(
            f"Save incompatible ({dimension}): recorded={fingerprint(saved)}, "
            f"current={fingerprint(running)}. Reopen with the original "
            "content/project/rules or run a validated, explicit migration. "
            "The replay has not been modified."
        )


class GameSession:
    """Compose Campaign, StoryBook, Battle and MultiFrontSession.

    This uses a new explicit session save format. Existing PlayerSession slots
    and historical battle/multi-front replay formats are untouched.
    """
    VERSION = 1
    FRONT_BATTLE_GROUPS = ("battles", "rescue_battles", "pursuit_battles", "recovery_battles")

    def __init__(self, content, project, campaign_id, *, seed=1, rules=None):
        if rules is None:
            from .event_pages import has_pages
            from .tactical_rpg3 import authored_rules_for_document
            raw = content.to_dict()
            rules = authored_rules_for_document(raw) if has_pages(raw) else default_rules()
        self.rules = rules
        content.validate(rules=self.rules)
        project.validate(content)
        require(project.campaign(campaign_id) is not None, "Unknown campaign")
        require(type(seed) is int, "Invalid seed")
        self.content, self.project = deepcopy(content), deepcopy(project)
        self.campaign_id, self.seed = campaign_id, seed
        self.story = StoryBook(project.story, content, project.campaigns)
        self.exploration = Exploration(project.exploration, project.story)
        self.progress = project.new_game(campaign_id, content)
        from .scene_router import SceneRouter
        self.scene_router = SceneRouter(self.project.scene_routes, self.content, self.project)
        self.route_scene = self.scene_router.start
        self.route_history = []
        self._route_starting = False
        # Opt-in per-scene movement journal; absent in all legacy recordings.
        self._rt_origin = None
        self._rt_position = None
        self._rt_journal = None
        self.battle = None
        self.fronts = None
        self.finalized = False
        self.settled_fronts = set()
        self.siege_id = None  # Optional authored siege identity; old slots omit it.
        # Project-owned narrative choices; no mutation of Battle's replay log.
        self.tactical_story_pending = ""
        self.tactical_story_queue = []

    @classmethod
    def new(cls, content, project, campaign_id, **kwargs):
        return cls(content, project, campaign_id, **kwargs)

    @property
    def mode(self):
        return "fronts" if self.fronts is not None else (
            "battle" if self.battle is not None else "campaign")

    @property
    def active_battle(self):
        if self.fronts is not None:
            if self.fronts.recovery_battles:
                return self.fronts.recovery_battles[
                    sorted(self.fronts.recovery_battles)[0]]
            return self.fronts.active
        return self.battle

    def active_scene(self):
        return self.story.active_scene(self.progress)

    def scene_profile(self, scene_id=None):
        """Read the canonical project profile without changing CT state."""
        if scene_id is not None:
            known = (set(self.content.missions)
                     | set(self.project.exploration)
                     | set(self.story.scenes))
            require(type(scene_id) is str and scene_id in known,
                    "Unknown game mode scene")
        from .game_modes import resolve_scene_profile
        return resolve_scene_profile(self.project.game_modes, scene_id)

    def route_state(self):
        """Return the active exploration state from canonical Campaign flags."""
        require(self.scene_router.enabled, "Scene routing is not enabled")
        require(self.route_scene in self.project.exploration,
                "Current route is not an exploration scene")
        return self.exploration.state(self.progress, self.route_scene)

    def route_move(self, dx, dy):
        """Legacy cardinal exploration remains available before free movement starts."""
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and self._rt_journal is None,
                "Resolve encounter or free movement before cardinal movement")
        return self.exploration.move(self.progress, self.route_scene, dx, dy)

    def route_realtime_state(self):
        """Detached subcell position for Player/Studio; no Qt dependency."""
        from .fixed_realtime import FreeMovement
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and self.route_scene in self.project.exploration
                and self.scene_profile(self.route_scene)["movement"] == "FREE_REALTIME",
                "No active free movement scene")
        stage = self.exploration.state(self.progress, self.route_scene)
        movement = FreeMovement(stage)
        position = (list(self._rt_position) if self._rt_position is not None
                    else movement.center(stage["position"]))
        return {"scene": self.route_scene, "position": position,
                "cell": movement.cell(position),
                "tick": self._rt_journal.tick if self._rt_journal else 0}

    def route_realtime_step(self, dx=0, dy=0):
        """Apply exactly one fixed simulation tick; no wall-clock delta accepted.

        A failed command leaves both the journal and Campaign unchanged.
        The FixedTickJournal is local to the active exploration scene.
        """
        from .fixed_clock import FixedTickJournal
        from .fixed_realtime import FreeMovement
        current = self.route_realtime_state()
        require(type(dx) is int and type(dy) is int
                and dx in (-1, 0, 1) and dy in (-1, 0, 1),
                "Invalid free movement input")
        scene = current["scene"]
        movement = FreeMovement(self.project.exploration[scene])
        origin = (list(self._rt_origin) if self._rt_origin is not None
                  else list(current["position"]))
        # A private journal copy makes input submission and step atomic even
        # if a handler, digest, or validation unexpectedly fails.
        journal = (deepcopy(self._rt_journal) if self._rt_journal is not None
                   else FixedTickJournal(rate=60, seed=self.seed))
        pos = list(current["position"])
        journal.submit(journal.tick + 1, "hero",
                       {"kind": "move", "dx": dx, "dy": dy})
        def handler(tick, commands):
            nonlocal pos
            for event in commands:
                require(event["source"] == "hero", "Unknown free movement source")
                cmd = event["command"]
                require(set(cmd) == {"kind", "dx", "dy"}
                        and cmd["kind"] == "move",
                        "Invalid free movement command")
                pos = movement.advance(pos, cmd["dx"], cmd["dy"])
            return {"scene": scene, "position": list(pos)}
        snapshot = journal.step(handler)
        from .exploration import _key
        cell = movement.cell(snapshot["position"])
        self.progress.story_flags[_key(scene, "pos")] = ",".join(map(str, cell))
        self._rt_origin, self._rt_position, self._rt_journal = (
            origin, snapshot["position"], journal)
        return self.route_realtime_state()

    def route_transition(self, link_id):
        """One atomic navigation command; tactical startup uses the real CT core."""
        from .scene_router import MAX_HISTORY
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "Resolve encounter or dialogue before changing scenes")
        require(len(self.route_history) < MAX_HISTORY,
                "Scene transition history limit reached")
        route = self.scene_router.destination(self.route_scene, link_id, self.progress)
        before = deepcopy((self.progress, self.battle, self.fronts, self.finalized,
                           self.settled_fronts, self.siege_id, self.route_scene,
                           self.route_history, self.tactical_story_pending,
                           self.tactical_story_queue, self._rt_origin,
                           self._rt_position, self._rt_journal))
        try:
            dest = route["destination"]
            if dest in self.content.missions:
                self._route_starting = True
                try:
                    self.start_mission(dest)
                finally:
                    self._route_starting = False
            else:
                from .exploration import _key
                # Use existing Campaign.story_flags, never a second world save.
                self.progress.story_flags[_key(dest, "pos")] = ",".join(
                    map(str, route["spawn"]))
                self.exploration.state(self.progress, dest)
            self.route_scene = dest
            self.route_history.append(route["id"])
            # The next exploration segment starts a fresh tick log.
            # R25.E will certify continuous replay spanning mode boundaries.
            self._rt_origin = None
            self._rt_position = None
            self._rt_journal = None
            return {"scene": dest, "profile": self.scene_profile(dest),
                    "spawn": list(route["spawn"]), "mode": self.mode}
        except Exception:
            (self.progress, self.battle, self.fronts, self.finalized,
             self.settled_fronts, self.siege_id, self.route_scene,
             self.route_history, self.tactical_story_pending,
             self.tactical_story_queue, self._rt_origin,
             self._rt_position, self._rt_journal) = before
            raise

    def _tactical_story_progress(self):
        require(bool(self.tactical_story_pending), "No tactical dialogue pending")
        require(not self.progress.story_pending,
                "Cannot overlap campaign and tactical dialogue")
        projected = deepcopy(self.progress)
        projected.story_pending = self.tactical_story_pending
        return projected

    def tactical_scene(self):
        return self.story.active_scene(self._tactical_story_progress())

    def tactical_choices(self):
        return self.story.choices(self._tactical_story_progress())

    def _queue_tactical_story(self, battle, old_fired=(), old_event_count=None):
        """Consume each new event firing, including opt-in repeat pages.

        Mission initialisation retains the historical first-fired-ID logic.
        During an authenticated command the journal slice is authoritative:
        a repeated trigger ID produces a NEW dialogue presentation without
        duplicating the old one-shot event or a restored save.
        """
        if battle is None or self.fronts is not None:
            return
        if old_event_count is None:
            seen = set(old_fired)
            ids = [eid for eid in battle.fired if eid not in seen]
        else:
            ids = [row["id"] for row in battle.events[old_event_count:]
                   if row["kind"] == "trigger"]
        for event_id in ids:
            target = f"{battle.mission.id}/{event_id}"
            scene = self.story.during_tactical_event.get(target)
            if scene:
                self.tactical_story_queue.append(scene)
        if not self.tactical_story_pending and self.tactical_story_queue:
            self.tactical_story_pending = self.tactical_story_queue.pop(0)

    def choose_tactical_story_option(self, choice_id):
        """Atomically apply canonical StoryBook choice and resume the Battle."""
        require(self.mode == "battle", "No standalone tactical dialogue")
        require(self.battle is not None, 'Missing tactical battle')
        previous = deepcopy((self.progress, self.battle,
                             self.tactical_story_pending,
                             self.tactical_story_queue, self.finalized))
        try:
            projected = self._tactical_story_progress()
            scene_id = projected.story_pending
            selected = next((c for c in self.story.choices(projected)
                             if c['id'] == choice_id), None)
            require(selected is not None, 'Choice is unavailable')
            updated = self.story.choose(projected, choice_id)
            # Every tactical choice has a journal entry, including an empty
            # tactical-effects list. This makes replay and story history agree.
            before_fired = tuple(self.battle.fired)
            before_event_count = len(self.battle.events)
            self.battle.execute({
                'kind': 'story_effects', 'scene': scene_id,
                'choice': choice_id,
                'effects': deepcopy(selected.get('tactical_effects', [])),
            })
            self._queue_tactical_story(
                self.battle, before_fired, before_event_count)
            next_scene = updated.story_pending
            updated.story_pending = ""
            self.progress = updated
            self.tactical_story_pending = (next_scene or
                                           (self.tactical_story_queue.pop(0)
                                            if self.tactical_story_queue else ""))
            if not self.tactical_story_pending:
                self._settle()
            return self.tactical_scene() if self.tactical_story_pending else None
        except Exception:
            (self.progress, self.battle, self.tactical_story_pending,
             self.tactical_story_queue, self.finalized) = previous
            raise

    def exploration_state(self):
        scene = self.active_scene()
        return self.exploration.state(self.progress, scene["id"]) if scene else None

    def explore_move(self, dx, dy):
        require(self.mode == "campaign", "Exploration unavailable during combat")
        scene = self.active_scene()
        require(scene is not None, "No active narrative scene")
        return self.exploration.move(self.progress, scene["id"], dx, dy)

    def explore_interact(self, point_id):
        require(self.mode == "campaign", "Exploration unavailable during combat")
        scene = self.active_scene()
        require(scene is not None, "No active narrative scene")
        return self.exploration.interact(self.progress, scene["id"], point_id)

    def explore_wait(self):
        require(self.mode == "campaign", "Exploration unavailable during combat")
        scene = self.active_scene()
        require(scene is not None, "No active narrative scene")
        return self.exploration.wait(self.progress, scene["id"])

    def explore_actor(self, actor_id, action):
        require(self.mode == "campaign", "Exploration unavailable during combat")
        scene = self.active_scene()
        require(scene is not None, "No active narrative scene")
        return self.exploration.actor_action(self.progress, scene["id"],
                                             actor_id, action)

    def world_state(self):
        """Read the party cursor without mutating an old campaign slot."""
        return WorldJourney(self.project.world, self.content,
                            self.project.campaign(self.campaign_id)).state(self.progress)

    def world_destination(self, mission_id):
        require(self.mode == "campaign" and not self.progress.story_pending
                and self.active_scene() is None,
                "Resolve combat and narrative scenes before traveling")
        return WorldJourney(self.project.world, self.content,
                            self.project.campaign(self.campaign_id)).destination(
                                self.progress, mission_id)

    def world_advance(self):
        require(self.mode == "campaign" and not self.progress.story_pending
                and self.active_scene() is None,
                "Resolve combat and narrative scenes before traveling")
        journey = WorldJourney(self.project.world, self.content,
                               self.project.campaign(self.campaign_id))
        state = journey.advance(self.progress)
        event = journey.event_at(self.progress)
        if event is not None:
            require(event["scene"] in self.story.scenes,
                    "Unresolved world story scene")
            self.progress.story_flags["world_evt_" + event["id"]] = True
            self.progress.story_flags[PENDING] = event["id"]
            self.progress.story_pending = event["scene"]
        return state

    def world_can_enter(self, mission_id):
        return (self.mode == "campaign" and
                mission_id in self.available_missions() and
                WorldJourney(self.project.world, self.content,
                             self.project.campaign(self.campaign_id)).can_enter(
                                 self.progress, mission_id))

    def available_choices(self):
        stage = self.exploration_state()
        if stage is not None and not stage["completed"]:
            return []
        return self.story.choices(self.progress)

    def available_missions(self):
        if self.progress.story_pending:
            return []
        return flow_available_missions(self.progress, self.project.campaign_flow)

    def campaign_inspector(self):
        """Read-only persistent variables, companions, gates and endings."""
        return flow_inspect_campaign(self.progress, self.project.campaign_flow)

    def choose_story_option(self, choice_id):
        require(self.active_battle is None or self.active_battle.result is not None,
                "Finish combat before choosing dialogue")
        stage = self.exploration_state()
        require(stage is None or stage["completed"], "Explore the area first")
        active = self.active_scene()
        event_id = self.progress.story_flags.get(PENDING, "")
        event = None
        if event_id:
            event = next((item for item in self.project.world.get("events", [])
                          if item["id"] == event_id), None)
            require(event is not None and active is not None and
                    active["id"] == event["scene"],
                    "Pending world event does not match narrative scene")
        updated = self.story.choose(self.progress, choice_id)
        if event is not None:
            next_scene = updated.story_pending
            # Validate the pending road checkpoint while choosing a route;
            # StoryBook may already have switched to a chained next_scene.
            updated.story_pending = active["id"]
            WorldJourney(self.project.world, self.content,
                         self.project.campaign(self.campaign_id)).redirect(
                             updated, event, choice_id)
            updated.story_pending = next_scene
        self.progress = updated
        return self.active_scene()

    def available_sieges(self):
        """Describe authored plans for the current campaign without unlocking missions."""
        available = set(self.available_missions()) if self.mode == "campaign" else set()
        return [
            {"id": bp["id"], "fronts": len(bp["fronts"]),
             "locked": sorted(set(bp["fronts"].values()) - available),
             "ready": (self.mode == "campaign"
                       and len(set(bp["fronts"].values())) == len(bp["fronts"])
                       and set(bp["fronts"].values()) <= available)}
            for bp in self.project.sieges
            if bp["campaign_id"] == self.campaign_id
        ]

    def start_configured_siege(self, siege_id):
        """Start one saved Studio blueprint through normal campaign/roster gates."""
        require(self.mode == "campaign", "End the current encounter first")
        blueprint = next((bp for bp in self.project.sieges
                          if bp["id"] == siege_id and
                          bp["campaign_id"] == self.campaign_id), None)
        require(blueprint is not None, "Unknown siege in this campaign")
        mids = list(blueprint["fronts"].values())
        require(len(set(mids)) == len(mids), "Siege fronts require distinct missions")
        missing = sorted(set(mids) - set(self.available_missions()))
        require(not missing, "Siege missions are locked: " + ", ".join(missing))
        # No parallel rules or save format: use the same validated GameSession.
        self.start_fronts(blueprint["fronts"], blueprint["focused"],
                          specs=blueprint["specs"], links=blueprint["links"],
                          logistics=blueprint.get("logistics"),
                          campaign=blueprint["campaign"],
                          event_graph=blueprint.get("event_graph"))
        self.siege_id = siege_id
        return self.fronts

    def _battle_support(self, mission_id):
        total = 0
        for spec in self.project.battle_support:
            value = self.progress.story_flags.get(spec["flag"], 0)
            require(type(value) is int, "Battle support flag must be an integer")
            if spec["mission"] == mission_id and value >= spec["gte"]:
                total += spec["potion_bonus"]
        if not total:
            return None
        # Use the standard replay-verified Battle.initial_state contract;
        # no out-of-band mutations after Battle was constructed.
        require(total <= 30, "Battle support exceeds supply cap")
        return {"inventory": {"potion": 3 + total, "ether": 2, "phoenix": 1}}

    def _can_edit_hero_equipment(self, uid):
        """Only canonical playable heroes, only outside tactical encounters."""
        require(self.mode == "campaign" and not self.tactical_story_pending,
                "Finish the current encounter before changing equipment")
        require(not self.progress.story_pending and self.active_scene() is None,
                "Finish dialogue/exploration before changing equipment")
        require(isinstance(uid, str) and bool(uid),
                "Hero ID is required")
        roster = {unit.id for mission in self.content.missions.values()
                  for unit in mission.units if unit.team == "player"}
        require(uid in roster, "Unknown playable hero")

    def equip_hero(self, uid, item_id):
        """Delegate inventory/slot/ownership rules to the existing Campaign."""
        self._can_edit_hero_equipment(uid)
        self.progress.equip(self.content, uid, item_id)

    def unequip_hero(self, uid, slot):
        """Return a canonical equipped item to the persistent inventory."""
        self._can_edit_hero_equipment(uid)
        require(slot in ("weapon", "armor", "accessory"),
                "Unknown equipment slot")
        self.progress.unequip(uid, slot)

    def start_mission(self, mission_id):
        require(not self.scene_router.enabled or self._route_starting,
                "Routed projects must enter battles through a scene transition")
        require(self.mode == "campaign", "End the current encounter first")
        require(mission_id in self.available_missions(), "Mission is locked")
        # Enforce arrival at a visible world location at the headless boundary:
        # UI controls alone must not bypass an interrupted route event.
        state = self.world_state()
        if state is not None and any(
                node["mission"] == mission_id
                for node in self.project.world["nodes"]):
            require(self.world_can_enter(mission_id),
                    "Travel to the mission location before starting combat")
        # Campaign.prepare can materialize heroes: use a throwaway roster.
        battle = deepcopy(self.progress).prepare(
            self.content, mission_id, seed=self.seed, ruleset=self.rules,
            initial_state=self._battle_support(mission_id))
        self.battle, self.finalized = battle, False
        self._queue_tactical_story(battle)
        if not self.tactical_story_pending:
            self._settle()
        return battle

    def start_fronts(self, missions, focused, *, specs=None, links=None,
                     logistics=None, campaign=None, event_graph=None):
        require(not self.scene_router.enabled,
                "Routed multi-front sessions are not supported yet")
        require(self.mode == "campaign", "End the current encounter first")
        require(isinstance(missions, dict) and bool(missions) and focused in missions,
                "Invalid front mapping")
        available = set(self.available_missions())
        require(all(isinstance(name, str) and bool(name) and
                    isinstance(mid, str) and mid in available
                    for name, mid in missions.items()), "Front mission is locked")
        require(len(set(missions.values())) == len(missions),
                "Duplicate mission in fronts")
        prepared = deepcopy(self.content)
        for mid in missions.values():
            battle = deepcopy(self.progress).prepare(
                self.content, mid, seed=self.seed, ruleset=self.rules)
            # Battle.mission is live; Battle.content still holds authored units.
            prepared.missions[mid] = deepcopy(battle.content.missions[mid])
        self.fronts = MultiFrontSession(
            prepared, missions, focused, seed=self.seed, rules=self.rules,
            specs=specs, links=links, logistics=logistics, campaign=campaign,
            event_graph=event_graph)
        self.settled_fronts.clear()
        self.siege_id = None
        self.tactical_story_pending = ""
        self.tactical_story_queue.clear()
        return self.fronts

    def _commit(self, battle):
        updated = deepcopy(self.progress)
        route = battle.result == "victory" and battle.mission.id in self.story.after
        changed = updated.finish(battle, unlock_next=not route)
        if changed and route:
            self.story.after_victory(updated, battle.mission.id)
        updated = settle_campaign_flow(updated, self.project.campaign_flow,
                                      battle.mission.id, battle.result,
                                      content=self.content)
        self.progress = updated

    def _settle(self):
        # A battle may reach victory on the same tick as a dialogue trigger:
        # defer settlement/reward and any after-victory scene until selection.
        if self.tactical_story_pending:
            return
        if self.fronts is not None:
            for front, battle in self.fronts.battles.items():
                if front not in self.settled_fronts and battle.result in ("victory", "defeat"):
                    self._commit(battle)
                    self.settled_fronts.add(front)
        elif self.battle is not None and not self.finalized and self.battle.result in ("victory", "defeat"):
            self._commit(self.battle)
            self.finalized = True

    def execute(self, command):
        require(self.active_battle is not None, "No tactical combat")
        require(isinstance(command, dict)
                and command.get('kind') != 'story_effects',
                'Story effects must come from a validated narrative choice')
        require(not self.progress.story_pending and not self.tactical_story_pending,
                "Resolve pending dialogue first")
        before_fired = set(self.active_battle.fired) if self.fronts is None else set()
        before_event_count = (len(self.active_battle.events)
                              if self.fronts is None else None)
        before = deepcopy((self.progress, self.battle, self.fronts,
                           self.finalized, self.settled_fronts,
                           self.tactical_story_pending, self.tactical_story_queue))
        try:
            if self.fronts is not None:
                if self.fronts.recovery_battles:
                    front = sorted(self.fronts.recovery_battles)[0]
                    self.fronts.execute_recovery(front, command)
                else:
                    self.fronts.execute(command)
            else:
                require(not self.finalized, "Combat already completed")
                self.battle.execute(command)
                self._queue_tactical_story(
                    self.battle, before_fired, before_event_count)
            self._settle()
        except Exception:
            (self.progress, self.battle, self.fronts,
             self.finalized, self.settled_fronts,
             self.tactical_story_pending, self.tactical_story_queue) = before
            raise
        return self.active_battle

    def switch_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.switch(front)
        return self.active_battle

    def advance_fronts(self):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        before = deepcopy((self.progress, self.fronts, self.settled_fronts))
        try:
            state = self.fronts.advance()
            self._settle()
        except Exception:
            self.progress, self.fronts, self.settled_fronts = before
            raise
        return state

    def set_doctrine(self, front, doctrine):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.set_doctrine(front, doctrine)

    def select_route(self, route):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.select_route(route)

    def negotiate_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.negotiate_front(front)

    def partial_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.partial_front(front)

    def withdraw_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.withdraw_front(front)

    def start_recovery(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.start_recovery(front)

    def abandon_recovery(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.abandon_recovery(front)

    def send_reserves(self, destination, actors):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.send_reserves(destination, actors)

    def transfer_units(self, destination, placements):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.transfer_units(destination, placements)

    def escort_convoy(self, convoy_id):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.escort_convoy(convoy_id)

    def rescue_convoy(self, convoy_id):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.rescue_convoy(convoy_id)

    def ai_turn(self):
        require(self.mode == "battle" and not self.finalized and
                not self.battle.deploying and not self.tactical_story_pending,
                "No standalone AI combat or pending tactical dialogue")
        require(self.battle.active is not None and self.battle.active.team == "enemy",
                "Not an enemy activation")
        old_fired = set(self.battle.fired)
        before = deepcopy((self.progress, self.battle, self.finalized,
                           self.tactical_story_pending, self.tactical_story_queue))
        try:
            play_activation(self.battle)
            self._queue_tactical_story(self.battle, old_fired)
            self._settle()
        except Exception:
            (self.progress, self.battle, self.finalized,
             self.tactical_story_pending, self.tactical_story_queue) = before
            raise

    def return_to_campaign(self):
        if self.fronts is not None:
            require(not (self.fronts.rescue_battles or self.fronts.pursuit_battles
                         or self.fronts.recovery_battles),
                    "Finish tactical side missions first")
            require(all(row["status"] != "active"
                        or self.fronts.battles[name].result is not None
                        for name, row in self.fronts.timeline.fronts.items()),
                    "Fronts still active; abandon explicitly")
        elif self.battle is not None:
            require(self.finalized, "Combat still active; abandon explicitly")
        self.abandon_encounter()

    def abandon_encounter(self):
        """Discard uncompleted tactical progress, not already settled rewards."""
        self.battle = None
        self.fronts = None
        self.finalized = False
        self.settled_fronts = set()
        self.siege_id = None
        self.tactical_story_pending = ""
        self.tactical_story_queue.clear()

    def recording(self):
        """Portable v1 checkpoint; embedded tactical journals verify by replay."""
        tactical = None
        if self.battle is not None:
            tactical = self.battle.recording()
            Battle.replay(tactical, rules=self.rules)
        elif self.fronts is not None:
            tactical = self.fronts.recording()
            MultiFrontSession.replay(tactical, rules=self.rules)
        data = {
            "version": self.VERSION, "kind": "game_session",
            "campaign_id": self.campaign_id, "seed": self.seed,
            "content_digest": digest(self.content.to_dict()),
            "project_digest": gameplay_project_digest(self.project),
            "rules": self.rules.manifest(),
            "progress": {"version": 1, **asdict(self.progress)},
            "mode": self.mode, "tactical": tactical,
            "finalized": self.finalized,
            "settled_fronts": sorted(self.settled_fronts),
        }
        if self.scene_router.enabled:
            data["scene_route"] = {
                "version": 1, "current": self.route_scene,
                "history": list(self.route_history)}
        if self._rt_journal is not None:
            require(self.scene_router.enabled and self.mode == "campaign"
                    and self.route_scene in self.project.exploration,
                    "Realtime checkpoint requires active exploration")
            data["scene_realtime"] = {
                "version": 1, "scene": self.route_scene,
                "origin": list(self._rt_origin),
                "position": list(self._rt_position),
                "journal": self._rt_journal.recording()}
        if self.siege_id is not None:
            data["siege_id"] = self.siege_id
        if self.tactical_story_pending:
            data["tactical_story_pending"] = self.tactical_story_pending
        if self.tactical_story_queue:
            data["tactical_story_queue"] = list(self.tactical_story_queue)
        if self.fronts is not None:
            # MultiFront journals verify rules/state, but historically recreate
            # Battle UUIDs. Preserve identities used by Campaign.record_bonds.
            data["front_battle_ids"] = {
                group: {key: battle.battle_id for key, battle in
                        sorted(getattr(self.fronts, group).items())}
                for group in self.FRONT_BATTLE_GROUPS}
        return {**data, "digest": digest(data)}

    def save(self, path):
        write_json(path, self.recording())
        return Path(path)

    @classmethod
    def from_recording(cls, data, content, project, *, rules=None):
        require(isinstance(data, dict) and type(data.get("version")) is int
                and data.get("version") == cls.VERSION
                and data.get("kind") == "game_session", "Unsupported game session")
        require(set(data) - {"front_battle_ids", "siege_id", "scene_route",
                             "scene_realtime", "tactical_story_pending",
                             "tactical_story_queue"} ==
                {"version", "kind", "campaign_id", "seed",
                "content_digest", "project_digest", "rules", "progress",
                "mode", "tactical", "finalized", "settled_fronts", "digest"},
                "Malformed game session")
        require(data["digest"] == digest({k: v for k, v in data.items()
                                         if k != "digest"}), "Game session checksum mismatch")
        if rules is None:
            from .event_pages import has_pages
            from .tactical_rpg3 import authored_rules_for_document
            raw = content.to_dict()
            rules = authored_rules_for_document(raw) if has_pages(raw) else default_rules()
        current_content = digest(content.to_dict())
        current_project = gameplay_project_digest(project)
        current_rules = rules.manifest()
        if data["content_digest"] != current_content:
            raise IncompatibleSaveError("content", data["content_digest"], current_content)
        if data["project_digest"] != current_project:
            raise IncompatibleSaveError("project", data["project_digest"], current_project)
        if data["rules"] != current_rules:
            raise IncompatibleSaveError("rules", data["rules"], current_rules)
        session = cls(content, project, data["campaign_id"],
                      seed=data["seed"], rules=rules)
        session.progress = Campaign.from_dict(data["progress"], ruleset=rules)
        verify_flow_save(session.progress, project.campaign_flow)
        session.story.initialize(session.progress, session.campaign_id)
        require(set(session.progress.unlocked + session.progress.completed)
                <= set(session.content.missions), "Unknown campaign mission")
        mode = data["mode"]
        require(mode in {"campaign", "battle", "fronts"}, "Invalid session mode")
        pending = data.get("tactical_story_pending", "")
        queue = data.get("tactical_story_queue", [])
        require(isinstance(pending, str) and
                isinstance(queue, list) and len(queue) <= 128 and
                all(isinstance(sid, str) for sid in queue),
                "Invalid tactical dialogue checkpoint")
        require(not pending or pending in session.story.scenes,
                "Unknown pending tactical scene")
        require(all(scene in session.story.during_tactical_event.values()
                    for scene in queue), "Unknown queued tactical scene")
        require(not queue or bool(pending),
                "Queued tactical scenes require a pending dialogue")
        require((not pending and not queue) or
                (mode == "battle" and not session.progress.story_pending),
                "Tactical dialogue belongs to a standalone battle")
        session.tactical_story_pending = pending
        session.tactical_story_queue = list(queue)
        require("siege_id" not in data or (mode == "fronts"
                and isinstance(data["siege_id"], str) and bool(data["siege_id"])),
                "Invalid authored siege identity")
        require("front_battle_ids" not in data or mode == "fronts",
                "Battle identities require a multi-front session")
        settled = data["settled_fronts"]
        require(isinstance(settled, list) and all(isinstance(s, str) for s in settled)
                and len(set(settled)) == len(settled), "Invalid settlement log")
        require(type(data["finalized"]) is bool, "Invalid finalization flag")
        if mode == "campaign":
            require(data["tactical"] is None and not data["finalized"] and not settled,
                    "Idle session has tactical state")
        elif mode == "battle":
            require(isinstance(data["tactical"], dict) and not settled,
                    "Invalid standalone battle state")
            session.battle = Battle.replay(data["tactical"], rules=rules)
            require(session.battle.mission.id in
                    session.progress.unlocked + session.progress.completed,
                    "Unknown or locked tactical mission")
            session.finalized = data["finalized"]
            require(session.finalized ==
                    (session.battle.result in ("victory", "defeat")
                     and not pending),
                    "Battle finalization mismatch")
            if pending:
                require(any(ref.split("/", 1)[0] == session.battle.mission.id
                            and ref.split("/", 1)[1] in session.battle.fired
                            for ref in session.story.during_tactical_event),
                        "Pending tactical dialogue has no fired origin")
            # Recorded narrative actions must correspond to real authored
            # choices, not arbitrary Battle commands injected into the journal.
            # Every post-3.7.21F tactical choice writes one story_effects command.
            decisions = [cmd for cmd in session.battle.commands
                         if cmd.get('kind') == 'story_effects']
            history = session.progress.story_history
            require(len(decisions) <= len(history),
                    'Battle story decisions exceed campaign history')
            if decisions:
                require(history[-len(decisions):] == [
                    {'scene': cmd['scene'], 'choice': cmd['choice']}
                    for cmd in decisions], 'Battle story decisions mismatch campaign history')
                permitted = set()
                def visit(scene_id):
                    if scene_id in permitted:
                        return
                    permitted.add(scene_id)
                    for choice in session.story.scenes[scene_id]['choices']:
                        dest = choice.get('next_scene')
                        if dest:
                            visit(dest)
                for reference, root in session.story.during_tactical_event.items():
                    mid, trigger_id = reference.split('/', 1)
                    if mid == session.battle.mission.id and trigger_id in session.battle.fired:
                        visit(root)
                for cmd in decisions:
                    require(cmd['scene'] in permitted,
                            'Story choice was not reached by a tactical event')
                    authored = next((c for c in session.story.scenes[cmd['scene']]['choices']
                                    if c['id'] == cmd['choice']), None)
                    require(authored is not None and
                            authored.get('tactical_effects', []) == cmd['effects'],
                            'Replayed tactical effects differ from authored choice')
        else:
            require(isinstance(data["tactical"], dict) and not data["finalized"],
                    "Invalid multi-front state")
            session.fronts = MultiFrontSession.replay(data["tactical"], rules=rules)
            require(set(session.fronts.missions.values()) <=
                    set(session.progress.unlocked + session.progress.completed)
                    and set(settled) <= set(session.fronts.missions),
                    "Unknown multi-front mission or settlement")
            for front, battle in session.fronts.battles.items():
                require((front in settled) == (battle.result in ("victory", "defeat")),
                        "Front finalization mismatch")
            session.settled_fronts = set(settled)
            if "siege_id" in data:
                bp = next((row for row in session.project.sieges
                           if row["id"] == data["siege_id"] and
                           row["campaign_id"] == session.campaign_id), None)
                require(bp is not None and session.fronts.missions == bp["fronts"]
                        and session.fronts.initial_focus == bp["focused"]
                        and session.fronts.initial_specs == bp["specs"]
                        and session.fronts.links == bp["links"]
                        and session.fronts.initial_campaign == bp["campaign"]
                        and session.fronts.initial_logistics == bp.get("logistics")
                        and session.fronts.initial_event_graph == bp.get("event_graph", []),
                        "Authored siege no longer matches saved front configuration")
                session.siege_id = data["siege_id"]
            if "front_battle_ids" in data:
                identities = data["front_battle_ids"]
                require(isinstance(identities, dict) and
                        set(identities) == set(cls.FRONT_BATTLE_GROUPS),
                        "Invalid front battle identity groups")
                seen = set()
                for group in cls.FRONT_BATTLE_GROUPS:
                    battles = getattr(session.fronts, group)
                    rows = identities[group]
                    require(isinstance(rows, dict) and set(rows) == set(battles),
                            "Front battle identities do not match live battles")
                    for key, identity in rows.items():
                        require(isinstance(identity, str) and 0 < len(identity) <= 128
                                and identity not in seen, "Invalid or duplicate battle identity")
                        battles[key].battle_id = identity
                        seen.add(identity)
        # R25.B scene routing is opt-in. The legacy v1 recording is untouched.
        if session.scene_router.enabled:
            require("scene_route" in data,
                    "Routed project checkpoint is missing scene state")
            session.route_scene = session.scene_router.validate_checkpoint(
                data["scene_route"], mode=mode, battle=session.battle)
            session.route_history = list(data["scene_route"]["history"])
            if session.route_scene in session.project.exploration:
                session.exploration.state(session.progress, session.route_scene)
        else:
            require("scene_route" not in data,
                    "Unexpected scene state in legacy checkpoint")
        if "scene_realtime" in data:
            from .fixed_clock import FixedTickJournal
            from .fixed_realtime import FreeMovement
            saved = data["scene_realtime"]
            require(type(saved) is dict
                    and set(saved) == {"version", "scene", "origin",
                                       "position", "journal"}
                    and type(saved["version"]) is int
                    and saved["version"] == 1
                    and saved["scene"] == session.route_scene
                    and mode == "campaign"
                    and session.scene_router.enabled
                    and saved["scene"] in project.exploration
                    and session.scene_profile(saved["scene"])["movement"]
                    == "FREE_REALTIME",
                    "Invalid realtime checkpoint metadata")
            movement = FreeMovement(project.exploration[saved["scene"]])
            origin = movement.center(movement.cell(saved["origin"]))
            require(origin == saved["origin"],
                    "Realtime journal origin must be an unblocked tile center")
            position = list(origin)
            def verify_tick(tick, commands):
                nonlocal position
                for event in commands:
                    cmd = event["command"]
                    require(event["source"] == "hero"
                            and type(cmd) is dict
                            and set(cmd) == {"kind", "dx", "dy"}
                            and cmd["kind"] == "move",
                            "Invalid replayed movement command")
                    position = movement.advance(position, cmd["dx"], cmd["dy"])
                return {"scene": saved["scene"], "position": list(position)}
            journal = FixedTickJournal.replay(saved["journal"], verify_tick)
            require(journal.tick > 0 and saved["position"] == position,
                    "Realtime replay position diverged")
            stage = session.exploration.state(session.progress, saved["scene"])
            require(stage["position"] == movement.cell(position),
                    "Realtime and campaign exploration positions disagree")
            session._rt_origin = origin
            session._rt_position = list(position)
            session._rt_journal = journal
        # World map travel is optional, but an existing cursor must never be
        # accepted from a malformed or inaccessible persisted route.
        session.world_state()
        return session

    @classmethod
    def load(cls, path, content, project, *, rules=None):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls.from_recording(data, content, project, rules=rules)
        except IncompatibleSaveError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise RuleError(f"Invalid game session: {exc}") from exc
