"""Opt-in multi-route siege policy and bounded tactical counterattack missions.

Routes change which *verified* fronts unlock the throne; they never invent a
combat win. One paid alternative route can be selected per campaign. A lost
front may be reclaimed only through a genuine, separate tactical Battle.
"""
from copy import deepcopy
from .model import require
from . import front_links


ACCEPTED = {"victory", "partial", "negotiated", "reclaimed"}


class CampaignRoutesPolicy:
    def __init__(self, spec, content, missions, final_front):
        require(isinstance(spec, dict)
                and {"routes", "recovery", "treaties"} <= set(spec)
                and set(spec) <= {"routes", "recovery", "treaties", "counteroffensives"},
                "Invalid alternative-route configuration")
        routes = spec["routes"]
        require(isinstance(routes, dict) and "breach" in routes and
                len(routes) >= 2, "Routes must include breach and an alternative")
        self.routes = deepcopy(routes)
        for name, row in routes.items():
            require(isinstance(name, str) and bool(name)
                    and isinstance(row, dict)
                    and set(row) == {"required", "supplies", "strength_loss"},
                    "Invalid route definition")
            required = row["required"]
            require(isinstance(required, dict)
                    and final_front not in required, "Invalid route prerequisites")
            for front, statuses in required.items():
                require(isinstance(front, str) and front in missions
                        and isinstance(statuses, list) and bool(statuses)
                        and all(isinstance(status, str) for status in statuses)
                        and set(statuses) <= ACCEPTED
                        and len(set(statuses)) == len(statuses),
                        "Invalid route-required front or status")
            require(type(row["supplies"]) is int
                    and 0 <= row["supplies"] <= 10000
                    and type(row["strength_loss"]) is int
                    and 0 <= row["strength_loss"] <= 10000,
                    "Invalid route costs")
            if not required:
                require(row["supplies"] > 0 and row["strength_loss"] > 0,
                        "An unrestricted assault must expend supplies and troops")
        require(routes["breach"]["supplies"] == 0
                and routes["breach"]["strength_loss"] == 0,
                "Default breach cannot charge at initial session creation")
        recovery = spec["recovery"]
        require(isinstance(recovery, dict), "Invalid recovery rules")
        self.recovery = deepcopy(recovery)
        treaties = spec["treaties"]
        require(isinstance(treaties, dict)
                and set(treaties) <= set(missions) - {final_front},
                "Invalid treaty conditions")
        self.treaties = deepcopy(treaties)
        for front, rule in treaties.items():
            require(isinstance(rule, dict)
                    and set(rule) == {"requires_front", "event", "object"}
                    and rule["requires_front"] in missions
                    and rule["requires_front"] != front
                    and rule["event"] in {"interact", "defense_sabotaged"}
                    and isinstance(rule["object"], str),
                    "Invalid treaty prerequisite")
            mission = content.missions[missions[rule["requires_front"]]]
            obj = next((o for o in mission.objects
                        if o["id"] == rule["object"]), None)
            require(obj is not None
                    and (obj["kind"] == "defense" if rule["event"] == "defense_sabotaged"
                         else obj["kind"] not in {"defense", "passage"}),
                    "Treaty prerequisite needs a valid tactical object")
        for front, row in recovery.items():
            require(isinstance(front, str) and front in missions
                    and front != final_front and
                    isinstance(row, dict) and set(row) == {
                        "mission", "supplies", "strength_loss", "reclaimed_strength"},
                    "Invalid recovery definition")
            require(isinstance(row["mission"], str)
                    and row["mission"] in content.missions,
                    "Unknown recovery tactical mission")
            mission = content.missions[row["mission"]]
            require(mission.objective == "eliminate" and
                    any(u.team == "player" for u in mission.units)
                    and any(u.team == "enemy" for u in mission.units),
                    "Recovery mission must contain both teams and elimination objective")
            require(type(row["supplies"]) is int and 1 <= row["supplies"] <= 10000
                    and type(row["strength_loss"]) is int
                    and 0 <= row["strength_loss"] <= 10000
                    and type(row["reclaimed_strength"]) is int
                    and 1 <= row["reclaimed_strength"] <= 10000,
                    "Invalid recovery costs")
        counteroffensives = spec.get("counteroffensives", {})
        require(isinstance(counteroffensives, dict)
                and set(counteroffensives) <= set(missions) - {final_front},
                "Invalid counteroffensive targets")
        self.counteroffensives = deepcopy(counteroffensives)
        for front, row in counteroffensives.items():
            require(front in recovery and isinstance(row, dict)
                    and set(row) == {"after_turn", "mission", "strength_loss",
                                     "opposition_gain"},
                    "Invalid counteroffensive rule")
            require(type(row["after_turn"]) is int and row["after_turn"] >= 1
                    and isinstance(row["mission"], str)
                    and row["mission"] in content.missions
                    and type(row["strength_loss"]) is int
                    and 0 <= row["strength_loss"] <= 10000
                    and type(row["opposition_gain"]) is int
                    and 1 <= row["opposition_gain"] <= 10000,
                    "Invalid counteroffensive timing, mission, or pressure")
            mission = content.missions[row["mission"]]
            require(mission.objective == "eliminate"
                    and any(unit.team == "player" for unit in mission.units)
                    and any(unit.team == "enemy" for unit in mission.units),
                    "Counteroffensive mission must be a playable elimination battle")

    def verify_treaty(self, session, front):
        if front not in self.treaties:
            return
        row = self.treaties[front]
        source = session.battles.get(row["requires_front"])
        require(source is not None and
                any(e["kind"] == row["event"] and e.get("object") == row["object"]
                    for e in source.events),
                "Treaty needs the authenticated supply/intelligence objective")

    def checked(self, session):
        required = self.routes[session.route_selected]["required"]
        result = {}
        for name, outcomes in required.items():
            status = session.timeline.fronts[name]["status"]
            accepted = status in outcomes
            if session.route_selected != "breach" and status == "victory":
                battle = session.battles.get(name)
                accepted = accepted and battle is not None and battle.result == "victory"
            result[name] = {"status": status, "accepted": accepted}
        return result


class CampaignRoutesMixin:
    def select_route(self, name):
        """Select one paid route exactly once, before the throne is entered."""
        require(self.route_policy is not None, "Alternative routes are not enabled")
        require(name in self.route_policy.routes, "Unknown authored siege route")
        require(not self.route_locked and name != "breach",
                "An alternative route has already been committed")
        require(self.timeline.focused != self.campaign.final
                and self.timeline.fronts[self.campaign.final]["status"] == "active",
                "Cannot change the route after entering the throne")
        require(not self.rescue_battles and not self.pursuit_battles
                and not self.recovery_battles,
                "Finish the tactical side encounter first")
        row = self.route_policy.routes[name]
        if row["supplies"]:
            require(self.logistics is not None
                    and self.logistics.supplies is not None,
                    "Route choice requires a finite supply pool")
            require(self.logistics.supplies["player"] >= row["supplies"],
                    "Not enough provisions for route")
        throne = self.timeline.fronts[self.campaign.final]
        require(throne["strength"] > row["strength_loss"],
                "Not enough fighters remain to storm the throne")
        snapshot = deepcopy((self.logistics, self.timeline, self.battles))
        try:
            if row["supplies"]:
                self.logistics.spend_supplies("player", row["supplies"])
            if row["strength_loss"]:
                front_links._reduce_force(
                    self, self.campaign.final, row["strength_loss"],
                    field="strength", losing_team="player", result="defeat")
            self.route_selected = name
            self.route_locked = True
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "campaign_route_selected",
                "route": name, "supplies": row["supplies"],
                "troop_losses": row["strength_loss"]})
        except Exception:
            self.logistics, self.timeline, self.battles = snapshot
            raise
        self.history.append({"kind": "select_route", "route": name})

    def start_recovery(self, front):
        """Recover a lost required front by playing a separate small encounter."""
        from .engine import Battle
        require(self.route_policy is not None, "Campaign recovery is not enabled")
        require(front in self.route_policy.recovery,
                "No authored counterattack for this front")
        require(not self.recovery_battles and not self.rescue_battles
                and not self.pursuit_battles,
                "Finish the current tactical side encounter")
        require(self.timeline.fronts[front]["status"] in {"defeat", "withdrawn"},
                "Counterattack requires a lost or withdrawn front")
        require(self.timeline.fronts[self.campaign.final]["status"] == "active"
                and self.timeline.focused != self.campaign.final,
                "The final battle has already begun or finished")
        rule = self.route_policy.recovery[front]
        require(self.logistics is not None and self.logistics.supplies is not None,
                "Counterattack requires strategic supplies")
        require(self.logistics.supplies["player"] >= rule["supplies"],
                "Insufficient supplies to stage counterattack")
        require(self.timeline.fronts[self.campaign.final]["strength"]
                > rule["strength_loss"],
                "Insufficient final-assault forces for counterattack")
        # Create Battle first so malformed mission content cannot spend money.
        battle = Battle(self.content, rule["mission"],
                        seed=self.seed + 30000 + sorted(self.missions).index(front),
                        rules=self.rules)
        snapshot = deepcopy((self.timeline, self.logistics, self.battles))
        try:
            self.logistics.spend_supplies("player", rule["supplies"])
            if rule["strength_loss"]:
                front_links._reduce_force(
                    self, self.campaign.final, rule["strength_loss"],
                    field="strength", losing_team="player", result="defeat")
            self.recovery_battles[front] = battle
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "campaign_recovery_started",
                "front": front, "mission": rule["mission"],
                "supplies": rule["supplies"]})
        except Exception:
            self.timeline, self.logistics, self.battles = snapshot
            raise
        self.history.append({"kind": "start_recovery", "front": front})
        return battle

    def execute_recovery(self, front, command):
        require(isinstance(command, dict) and front in self.recovery_battles,
                "Invalid command or unknown active counterattack")
        snapshot = deepcopy((self.recovery_battles, self.recovery_outcomes,
                             self.timeline, self.battles,
                             self.counteroffensive_active))
        try:
            battle = self.recovery_battles[front]
            battle.execute(deepcopy(command))
            if battle.result in {"victory", "defeat"}:
                was_counteroffensive = front in self.counteroffensive_active
                self.recovery_outcomes[front] = battle.result
                if battle.result == "victory":
                    row = self.timeline.fronts[front]
                    row["status"] = "reclaimed"
                    row["strength"] = max(
                        row["strength"],
                        self.route_policy.recovery[front]["reclaimed_strength"])
                del self.recovery_battles[front]
                if was_counteroffensive:
                    self.counteroffensive_active.discard(front)
                self.timeline.events.append({
                    "turn": self.timeline.turn,
                    "kind": ("campaign_counteroffensive_" if was_counteroffensive
                             else "campaign_recovery_") + battle.result,
                    "front": front})
        except Exception:
            (self.recovery_battles, self.recovery_outcomes,
             self.timeline, self.battles,
             self.counteroffensive_active) = snapshot
            raise
        self.history.append({"kind": "execute_recovery", "front": front,
                             "command": deepcopy(command)})

    def abandon_recovery(self, front):
        require(front in self.recovery_battles,
                "No active recovery mission to abandon")
        was_counteroffensive = front in self.counteroffensive_active
        del self.recovery_battles[front]
        self.recovery_outcomes[front] = "abandoned"
        if was_counteroffensive:
            self.counteroffensive_active.discard(front)
        self.timeline.events.append({
            "turn": self.timeline.turn,
            "kind": ("campaign_counteroffensive_" if was_counteroffensive
                     else "campaign_recovery_") + "abandoned",
            "front": front})
        self.history.append({"kind": "abandon_recovery", "front": front})
