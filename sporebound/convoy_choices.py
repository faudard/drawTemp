"""Optional branching convoy decisions and tactical pursuit.

This mixin deliberately uses existing Battle and LogisticsDirector contracts.
Its methods are only enabled for scenarios authored with logistics.choices.
No alternate tactical simulator, RNG draws or background actions are created.
"""
from copy import deepcopy

from .model import require


class ConvoyChoicesMixin:
    def _choices(self):
        logistics = self.logistics
        require(logistics is not None and logistics.choices is not None,
                "Branching convoy decisions are not enabled")
        return logistics.choices

    def _validate_pursuit_mission(self):
        if self.logistics is None or self.logistics.choices is None:
            return
        mid = self.logistics.choices["pursuit_mission"]
        require(mid in self.content.missions, "Unknown pursuit mission")
        mission = self.content.missions[mid]
        require(mission.objective == "eliminate" and not mission.deployment
                and any(u.team == "player" for u in mission.units)
                and any(u.team == "enemy" for u in mission.units),
                "Pursuit mission requires two teams and elimination objective")

    def _stranded_choice(self, convoy_id):
        self._choices()
        convoy = self.logistics.convoy(convoy_id)
        require(convoy["team"] == "player" and convoy.get("stranded") is True
                and bool(convoy["actors"]), "Choice requires stranded friendly survivors")
        require(not self.pursuit_battles, "Finish the pursuit battle first")
        require(not self.rescue_battles or convoy_id in self.rescue_battles,
                "A different rescue battle is active")
        require(convoy_id not in self.rescue_outcomes,
                "Convoy has already chosen a rescue outcome")
        return convoy

    def _release_cargo(self, convoy, *, outcome, salvaged, delay):
        """One atomic choice boundary; called after validating every precondition."""
        cid = convoy["id"]
        total = convoy["cargo"]
        require(type(salvaged) is int and 0 <= salvaged <= total,
                "Invalid recovered cargo amount")
        convoy["cargo"] = salvaged
        convoy.pop("stranded")
        convoy["arrival"] = max(convoy["arrival"], self.timeline.turn + delay)
        lost = total - salvaged
        if lost:
            self.pursuit_targets[cid] = {
                "team": convoy["team"], "front": convoy["to"], "loot": lost,
            }
        if cid in self.rescue_battles:
            del self.rescue_battles[cid]
        self.rescue_outcomes[cid] = outcome
        self.timeline.events.append({
            "turn": self.timeline.turn, "kind": "convoy_" + outcome,
            "convoy": cid, "survivors": [actor["id"] for actor in convoy["actors"]],
            "cargo_saved": salvaged, "cargo_lost": lost,
            "arrival": convoy["arrival"]})

    def evacuate_convoy(self, convoy_id):
        """Withdraw the living crew without their loot; not a free full rescue."""
        convoy = self._stranded_choice(convoy_id)
        self._release_cargo(convoy, outcome="evacuated", salvaged=0, delay=2)
        self.history.append({"kind": "evacuate_convoy", "convoy": convoy_id})

    def salvage_convoy(self, convoy_id):
        """Break contact after defeating a raider, retaining half the cargo."""
        convoy = self._stranded_choice(convoy_id)
        require(convoy_id in self.rescue_battles,
                "Partial recovery requires an active tactical skirmish")
        battle = self.rescue_battles[convoy_id]
        require(battle.result is None and battle.unit(battle.mission.protected_id).alive,
                "Protected wagon must survive partial recovery")
        require(any(u.team == "player" and u.id != battle.mission.protected_id
                    and u.alive for u in battle.units),
                "At least one escort must survive")
        require(any(u.team == "enemy" and not u.alive for u in battle.units)
                and any(u.team == "enemy" and u.alive for u in battle.units),
                "Win a skirmish against at least one raider before falling back")
        salvaged = max(1, convoy["cargo"] // 2)
        require(self.logistics.supplies["player"] + salvaged <= 10000,
                "Supply pool cannot contain recovered cargo")
        self.logistics.supplies["player"] += salvaged
        self._release_cargo(convoy, outcome="partial", salvaged=salvaged, delay=2)
        self.history.append({"kind": "salvage_convoy", "convoy": convoy_id})

    def negotiate_convoy(self, convoy_id):
        """Pay a ransom *during* a skirmish to avoid a doomed battle.

        Unlike a free crew evacuation, negotiation preserves cargo but costs
        valuable supplies; unlike the ordinary pre-battle rescue order, it
        can be used once fighting has already started.
        """
        convoy = self._stranded_choice(convoy_id)
        require(convoy_id in self.rescue_battles,
                "Negotiation is only available during a rescue skirmish")
        battle = self.rescue_battles[convoy_id]
        require(battle.result is None
                and battle.unit(battle.mission.protected_id).alive,
                "The wagon must survive negotiation")
        ransom = self._choices()["ransom"]
        self.logistics.spend_supplies("player", ransom)
        self._release_cargo(convoy, outcome="negotiated",
                            salvaged=convoy["cargo"], delay=1)
        self.timeline.events.append({
            "turn": self.timeline.turn, "kind": "convoy_ransom_paid",
            "convoy": convoy_id, "supplies": ransom})
        self.history.append({"kind": "negotiate_convoy", "convoy": convoy_id})

    def start_pursuit(self, convoy_id):
        """Optional follow-up: recover lost cargo from fleeing pillagers."""
        from .engine import Battle
        choices = self._choices()
        require(not self.rescue_battles and not self.pursuit_battles
                and not self.recovery_battles,
                "Resolve the current tactical side mission first")
        require(convoy_id in self.pursuit_targets
                and convoy_id not in self.pursuit_outcomes,
                "No unrecovered convoy loot for pursuit")
        target = self.pursuit_targets[convoy_id]
        require(self.timeline.fronts[target["front"]]["status"] == "active",
                "Target front already resolved")
        battle = Battle(self.content, choices["pursuit_mission"],
                        seed=self.seed + 20000
                        + int(convoy_id.split("_")[-1]),
                        rules=self.rules)
        self.pursuit_battles[convoy_id] = battle
        self.timeline.events.append({
            "turn": self.timeline.turn, "kind": "convoy_pursuit_started",
            "convoy": convoy_id, "mission": battle.mission.id})
        self.history.append({"kind": "start_pursuit", "convoy": convoy_id})
        return battle

    def _finish_pursuit(self, convoy_id):
        battle = self.pursuit_battles[convoy_id]
        require(battle.result in {"victory", "defeat"},
                "Pursuit requires a completed tactical battle")
        target = self.pursuit_targets.pop(convoy_id)
        reward = 0
        reduction = 0
        if battle.result == "victory":
            reward = min(self._choices()["pursuit_reward"], target["loot"],
                         10000 - self.logistics.supplies[target["team"]])
            self.logistics.supplies[target["team"]] += reward
            row = self.timeline.fronts[target["front"]]
            if row["status"] == "active":
                field = "opposition" if target["team"] == "player" else "strength"
                team = "enemy" if target["team"] == "player" else "player"
                reduction = min(1, max(0, row[field] - 1))
                row[field] -= reduction
                tactical = self.battles.get(target["front"])
                if tactical is not None and reduction:
                    self._apply_attrition(tactical, team, reduction)
        self.pursuit_outcomes[convoy_id] = battle.result
        del self.pursuit_battles[convoy_id]
        self.timeline.events.append({
            "turn": self.timeline.turn,
            "kind": "convoy_pursuit_" + battle.result,
            "convoy": convoy_id, "supplies": reward,
            "enemy_pressure_reduced": reduction})

    def execute_pursuit(self, convoy_id, command):
        require(isinstance(command, dict) and convoy_id in self.pursuit_battles,
                "Unknown active pursuit or invalid command")
        snapshot = deepcopy((self.pursuit_battles, self.pursuit_targets,
                             self.pursuit_outcomes, self.logistics,
                             self.timeline, self.battles))
        try:
            battle = self.pursuit_battles[convoy_id]
            battle.execute(deepcopy(command))
            if battle.result is not None:
                self._finish_pursuit(convoy_id)
        except Exception:
            (self.pursuit_battles, self.pursuit_targets,
             self.pursuit_outcomes, self.logistics,
             self.timeline, self.battles) = snapshot
            raise
        self.history.append({"kind": "execute_pursuit", "convoy": convoy_id,
                             "command": deepcopy(command)})

    def abandon_pursuit(self, convoy_id):
        self._choices()
        require(convoy_id in self.pursuit_targets
                and convoy_id not in self.pursuit_outcomes,
                "No pursuit available to abandon")
        require(not self.pursuit_battles
                or convoy_id in self.pursuit_battles,
                "A different pursuit battle is running")
        self.pursuit_battles.pop(convoy_id, None)
        self.pursuit_targets.pop(convoy_id)
        self.pursuit_outcomes[convoy_id] = "abandoned"
        self.timeline.events.append({
            "turn": self.timeline.turn,
            "kind": "convoy_pursuit_abandoned", "convoy": convoy_id})
        self.history.append({"kind": "abandon_pursuit", "convoy": convoy_id})
