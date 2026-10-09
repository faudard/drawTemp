"""Optional, declarative campaign choices for simultaneous siege fronts.

An army may capture a corridor, negotiate passage, retreat or secure only a
tactical objective. None of these choices impersonates a Battle victory.
Only normal Battle results and authored verified objective events can satisfy
a campaign condition.
"""
from copy import deepcopy

from .model import require
from . import front_links


OUTCOMES = {"victory", "defeat", "withdrawn", "negotiated", "partial"}


class SiegeCampaign:
    def __init__(self, spec, content, missions):
        require(isinstance(spec, dict) and
                {"final_front", "required_fronts", "partial", "negotiation", "retreat"}
                <= set(spec) <=
                {"final_front", "required_fronts", "partial", "negotiation", "retreat",
                 "routes", "recovery", "treaties"}
                and (("routes" in spec) == ("recovery" in spec)
                     == ("treaties" in spec)),
            "Invalid campaign structure")
        final = spec["final_front"]
        require(isinstance(final, str) and final in missions,
                "Campaign final front is unknown")
        required = spec["required_fronts"]
        require(isinstance(required, dict) and bool(required)
                and final not in required, "Invalid final-front prerequisites")
        for front, accepted in required.items():
            require(front in missions and isinstance(accepted, list)
                    and bool(accepted)
                    and all(isinstance(value, str) for value in accepted)
                    and len(set(accepted)) == len(accepted)
                    and set(accepted) <= {"victory", "partial", "negotiated"},
                    "Invalid campaign allowed outcomes")
        for key in ("partial", "negotiation", "retreat"):
            require(isinstance(spec[key], dict)
                    and set(spec[key]) <= set(missions) - {final},
                    "Invalid campaign outcome options")
        for front, rule in spec["partial"].items():
            require(isinstance(rule, dict) and set(rule) == {
                "event", "object", "cost", "target", "target_loss"},
                "Invalid partial-front rule")
            require(rule["event"] in {"interact", "defense_sabotaged"},
                    "Partial result needs an actual tactical objective event")
            require(isinstance(rule["object"], str) and bool(rule["object"])
                    and isinstance(rule["target"], str)
                    and rule["target"] in missions and rule["target"] != front,
                    "Invalid partial objective/target")
            obj = next((item for item in content.missions[missions[front]].objects
                        if item["id"] == rule["object"]), None)
            require(obj is not None and
                    (obj["kind"] == "defense" if rule["event"] == "defense_sabotaged"
                     else obj["kind"] not in {"defense", "passage"}),
                    "Unknown or incompatible partial objective")
            self._loss(rule, "cost", "target_loss")
        for front, rule in spec["negotiation"].items():
            require(isinstance(rule, dict) and set(rule) == {
                "supplies", "target", "target_loss"},
                "Invalid negotiation rule")
            require(isinstance(rule["target"], str)
                    and rule["target"] in missions and rule["target"] != front,
                    "Invalid negotiation target")
            self._loss(rule, "supplies", "target_loss")
            require(rule["supplies"] > 0, "Negotiation needs a nonzero ransom")
        for front, rule in spec["retreat"].items():
            require(isinstance(rule, dict) and set(rule) == {
                "target", "target_loss"}, "Invalid retreat rule")
            require(isinstance(rule["target"], str)
                    and rule["target"] in missions and rule["target"] != front,
                    "Invalid retreat target")
            self._loss(rule, "target_loss")
        self.spec = deepcopy(spec)
        self.final = final

    @staticmethod
    def _loss(rule, *keys):
        require(all(type(rule.get(key)) is int and 0 <= rule[key] <= 10000
                    for key in keys), "Invalid campaign losses/costs")

    def allowed(self, session):
        if session.route_policy is not None:
            return session.route_policy.checked(session)
        return {front: {"status": session.timeline.fronts[front]["status"],
                        "accepted": session.timeline.fronts[front]["status"] in statuses}
                for front, statuses in self.spec["required_fronts"].items()}

    def gate(self, session, destination):
        if destination != self.final:
            return
        failed = [front for front, info in self.allowed(session).items()
                  if not info["accepted"]]
        require(not failed,
                "Final front locked by: " + ", ".join(sorted(failed)))

    def state(self, session):
        checked = self.allowed(session)
        accepted = all(row["accepted"] for row in checked.values())
        irrevocable = any(row["status"] not in {"active", "victory",
                                                "partial", "negotiated"}
                          and not row["accepted"] for row in checked.values())
        final_status = session.timeline.fronts[self.final]["status"]
        if final_status == "victory":
            battle = session.battles.get(self.final)
            if session.route_policy is not None and (
                    not accepted or battle is None or battle.result != "victory"):
                status = "blocked"
            else:
                status = "victory"
        elif final_status in {"defeat", "withdrawn"}:
            status = "defeat"
        elif irrevocable:
            status = "blocked"
        elif accepted:
            status = "throne_unlocked"
        else:
            status = "in_progress"
        state = {"final_front": self.final, "status": status,
                 "unlocked": accepted, "required": checked,
                 "policy": deepcopy(self.spec)}
        if session.route_policy is not None:
            state["route"] = session.route_selected
            state["route_committed"] = session.route_locked
            state["available_routes"] = sorted(session.route_policy.routes)
            state["recovery_outcomes"] = deepcopy(session.recovery_outcomes)
            state["recovery_battles"] = {
                front: battle.state()
                for front, battle in sorted(session.recovery_battles.items())}
        return state


class CampaignChoicesMixin:
    def _campaign_choice(self, front, category):
        require(self.campaign is not None, "Siege campaign is not configured")
        require(front == self.timeline.focused and front in self.campaign.spec[category],
                "This campaign choice is not enabled for the focused front")
        require(self.timeline.fronts[front]["status"] == "active",
                "Front has already been resolved")
        require(not self.rescue_battles and not self.pursuit_battles,
                "Finish the side encounter before deciding")
        battle = self.active
        require(battle.result is None and not battle.deploying
                and (battle.active is None
                     or not battle.active.moved and not battle.active.acted),
                "Choose at a safe tactical turn boundary")
        return battle, self.campaign.spec[category][front]

    def _lose_campaign_strength(self, target, amount):
        if amount:
            front_links._reduce_force(self, target, amount, field="strength",
                                      losing_team="player", result="defeat")

    def _record_campaign_choice(self, front, outcome, rule):
        self.timeline.fronts[front]["status"] = outcome
        self._lose_campaign_strength(rule["target"], rule["target_loss"])
        self.timeline.events.append({
            "turn": self.timeline.turn, "kind": "campaign_front_" + outcome,
            "front": front, "target": rule["target"],
            "strength_loss": rule["target_loss"]})

    def partial_front(self, front):
        battle, rule = self._campaign_choice(front, "partial")
        event = rule["event"]
        require(any(e["kind"] == event and e.get("object") == rule["object"]
                    for e in battle.events),
                "Partial victory requires completed tactical objective")
        cost = rule["cost"]
        require(self.timeline.fronts[front]["strength"] > cost,
                "Not enough front strength to consolidate a partial victory")
        snapshot = deepcopy((self.timeline, self.battles))
        try:
            self._lose_campaign_strength(front, cost)
            self._record_campaign_choice(front, "partial", rule)
        except Exception:
            self.timeline, self.battles = snapshot
            raise
        self.history.append({"kind": "partial_front", "front": front})

    def negotiate_front(self, front):
        _battle, rule = self._campaign_choice(front, "negotiation")
        require(self.logistics is not None and self.logistics.supplies is not None,
                "Campaign negotiations need strategic supplies")
        if self.route_policy is not None:
            self.route_policy.verify_treaty(self, front)
        snapshot = deepcopy((self.timeline, self.battles, self.logistics))
        try:
            self.logistics.spend_supplies("player", rule["supplies"])
            self._record_campaign_choice(front, "negotiated", rule)
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "campaign_ransom_paid",
                "front": front, "supplies": rule["supplies"]})
        except Exception:
            self.timeline, self.battles, self.logistics = snapshot
            raise
        self.history.append({"kind": "negotiate_front", "front": front})

    def withdraw_front(self, front):
        _battle, rule = self._campaign_choice(front, "retreat")
        snapshot = deepcopy((self.timeline, self.battles))
        try:
            self._record_campaign_choice(front, "withdrawn", rule)
        except Exception:
            self.timeline, self.battles = snapshot
            raise
        self.history.append({"kind": "withdraw_front", "front": front})
