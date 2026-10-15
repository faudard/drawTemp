"""R8.D -- authored combat states and tactical AI profiles, no parallel runtime.

All edits apply to Content v1 through the existing R1 AuthoringSession.
The real Battle and tactical_rpg3 rules own previews and AI decisions.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound import class_ai_authoring, character_authoring
from sporebound.model import Content, SUPPORTS, require
from sporebound.rules import default_rules, statuses as status_rules
from sporebound.tactical_rpg3 import authored_rules_for_document

DOCTRINES = ("", "pack_hunt", "bandit_ambush", "spear_hold", "crossbow_reload")
BEHAVIORS = ("tactical", "coordinated", "phase_boss", "adaptive_boss")
FORMATIONS = ("none", "shield_wall", "phalanx", "escort")
ROLES = class_ai_authoring.ROLES
REACTION_KEYS = tuple(sorted(key for key, _ in default_rules().reactions.entries))
STATUS_KEYS = tuple(sorted(key for key, _ in default_rules().statuses.entries))
SUPPORT_KEYS = tuple(sorted(SUPPORTS))
MOVEMENT_KEYS = tuple(sorted(key for key, _ in default_rules().movements.entries))

# Elements here are damage-resistance keys, NOT immunity against status application.
ELEMENTS = ("physical", "fire", "ice", "lightning", "holy", "dark", "wind", "earth", "water")


def _mission(data, mission_id):
    mission = next((m for m in data["missions"] if m["id"] == mission_id), None)
    require(mission is not None, "Unknown mission")
    return mission


def _actor(data, mission_id, actor_id):
    mission = _mission(data, mission_id)
    row = next((u for u in mission["units"] if u["id"] == actor_id), None)
    require(row is not None, "Unknown actor")
    return row


def _validated(data):
    return Content.from_dict(
        data, rules=authored_rules_for_document(data)).to_dict()


def _set_initial_state(data, mission_id, actor_id, *, statuses=None,
                       resistances=None, reaction=None, support=None,
                       movement=None):
    new = deepcopy(data)
    actor = _actor(new, mission_id, actor_id)
    if statuses is not None:
        require(isinstance(statuses, dict) and all(
            key in STATUS_KEYS and type(value) is int and
            (value == -1 or 1 <= value <= 10000)
            for key, value in statuses.items()), "Invalid initial status/duration")
        registry = default_rules().statuses
        require(not any(registry.get(key).opposite in statuses
                        for key in statuses if registry.get(key).opposite),
                "Opposed initial statuses cannot coexist")
        actor["statuses"] = dict(sorted(statuses.items()))
    if resistances is not None:
        require(isinstance(resistances, dict) and all(
            key in ELEMENTS and type(value) is int and -100 <= value <= 100
            for key, value in resistances.items()), "Invalid elemental resistance")
        actor["resistances"] = dict(sorted(resistances.items()))
    for field, option, allowed in (
        ("reaction", reaction, REACTION_KEYS),
        ("support", support, SUPPORT_KEYS),
        ("movement", movement, MOVEMENT_KEYS),
    ):
        if option is not None:
            require(option in allowed, "Invalid " + field)
            actor[field] = option
    return _validated(new)


def _set_ai(data, mission_id, actor_id, *, behavior, roles, doctrine,
            route, squad, formation, escort_target):
    require(behavior in BEHAVIORS, "Unknown AI behavior")
    require(doctrine in DOCTRINES, "Unknown AI doctrine")
    require(isinstance(roles, (tuple, list)) and all(
        role in ROLES for role in roles) and len(set(roles)) == len(roles),
        "Unknown or repeated AI role")
    require(isinstance(squad, str) and len(squad) <= 64 and
            (not squad or all(c.isalnum() or c in "_-" for c in squad)),
            "Invalid squad identifier")
    require(formation in FORMATIONS and isinstance(escort_target, str),
            "Invalid formation")
    require(isinstance(route, (tuple, list)) and all(
        isinstance(p, (tuple, list)) and len(p) == 2 and
        all(type(c) is int for c in p) for p in route), "Invalid patrol waypoints")
    cells = [list(p) for p in route]
    require(not cells or len(cells) >= 2, "Patrol requires at least two waypoints")
    require(len({tuple(c) for c in cells}) == len(cells),
            "Duplicate patrol waypoint")
    require(not doctrine or behavior == "tactical",
            "Doctrines require tactical behavior")
    require(not cells or (behavior == "tactical" and not doctrine),
            "Patrol cannot be combined with a doctrine or boss policy")
    if cells:
        class_ai_authoring.validate_route(data, mission_id, cells)

    updated = deepcopy(data)
    actor = _actor(updated, mission_id, actor_id)
    require(not behavior.endswith("boss") or actor["team"] == "enemy",
            "Boss AI requires an enemy actor")
    require(not doctrine or actor["team"] == "enemy",
            "Enemy doctrine requires an enemy actor")
    require(doctrine != "spear_hold" or actor["weapon"] == "spear",
            "Spear-hold doctrine requires a spear")
    require(doctrine != "crossbow_reload" or actor["weapon"] == "ranged",
            "Crossbow doctrine requires a ranged weapon")
    require(formation != "phalanx" or actor["weapon"] == "spear",
            "Phalanx requires a spear")
    if formation == "escort":
        ally = next((u for u in _mission(updated, mission_id)["units"]
                     if u["id"] == escort_target and u["team"] == actor["team"]
                     and u["id"] != actor_id and u["hp"] > 0), None)
        require(ally is not None, "Escort requires a living allied actor")
        from sporebound.model import distance
        require(distance(tuple(actor["pos"]), tuple(ally["pos"])) <= 2,
                "Escort target is too far")
    else:
        require(not escort_target, "Only escort can specify a target")

    # Keep all unrelated authored tags (morale, boss phases, reload, etc.).
    prefixes = ("doctrine:", "squad:", "formation:")
    retained = [tag for tag in actor.get("tags", [])
                if tag not in ROLES and not tag.startswith(prefixes)]
    actor["tags"] = retained + list(roles)
    if doctrine:
        actor["tags"].append("doctrine:" + doctrine)
    if squad:
        actor["tags"].append("squad:" + squad)
    if formation != "none":
        actor["tags"].append("formation:" + formation +
                             (":" + escort_target if formation == "escort" else ""))
    actor["behavior"] = behavior
    actor["patrol_route"] = cells
    return _validated(updated)


class CombatAIEditor:
    """Transactional R8.D facade over canonical Actor/Skill/AI contracts."""

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected AuthoringSession")
        self.session = session

    def _data(self):
        return self.session.snapshot().to_dict()["content"]

    def _edit(self, transform, *, mission_id=None):
        plan = self.session.preview_pair(
            lambda content, project: (transform(content), project),
            kind="r8-combat-ai", mission_id=mission_id,
            views=("workspace", "inspector"))
        return self.session.apply(plan)

    def missions(self):
        return tuple((m["id"], m["name"]) for m in self._data()["missions"])

    def actors(self, mission_id):
        return tuple((u["id"], u["name"], u["team"])
                     for u in _mission(self._data(), mission_id)["units"])

    def detail(self, mission_id, actor_id):
        return deepcopy(_actor(self._data(), mission_id, actor_id))

    def states(self, mission_id, actor_id, **kwargs):
        """Initial battle statuses/resistance and reaction/support slots."""
        return self._edit(lambda data: _set_initial_state(
            data, mission_id, actor_id, **kwargs), mission_id=mission_id)

    def ai(self, mission_id, actor_id, *, behavior="tactical", roles=(),
           doctrine="", route=(), squad="", formation="none",
           escort_target=""):
        return self._edit(lambda data: _set_ai(
            data, mission_id, actor_id, behavior=behavior, roles=roles,
            doctrine=doctrine, route=route, squad=squad,
            formation=formation, escort_target=escort_target),
            mission_id=mission_id)

    def set_status_effect(self, skill_id, index, status, duration, *,
                          kind="status", scope="target"):
        """Real Skill.effects status/cleanse; not an invented global status table."""
        from drawtemp.studio.rpg_database import DatabaseEditor
        require(kind in ("status", "cleanse") and status in STATUS_KEYS,
                "Unknown status effect")
        require(type(duration) is int and 1 <= duration <= 10000,
                "Invalid effect duration")
        require(scope in ("target", "allies", "enemies", "all"),
                "Invalid effect scope")
        effect = character_authoring.make_effect(
            kind, power=1, status=status, duration=duration, scope=scope)
        return DatabaseEditor(self.session).set_effect(skill_id, index, effect)

    def preview(self, mission_id, actor_id, *, seed=1):
        """Use the actual Battle, status and formation policies without editing it.

        A forecast of a future activation is deliberately not synthesized.
        """
        from sporebound.engine import Battle
        from sporebound.formations3 import formation_preview
        from sporebound.tactical_r6 import active_enemy_plan
        require(type(seed) is int and 0 <= seed < 2**32, "Invalid seed")
        data = self._data()
        rules = authored_rules_for_document(data)
        content = Content.from_dict(data, rules=rules)
        battle = Battle(content, mission_id, seed=seed, rules=rules)
        unit = battle.unit(actor_id)
        report = {
            "unit": unit.id, "team": unit.team, "behavior": unit.behavior,
            "reaction": unit.reaction, "support": unit.support,
            "statuses": deepcopy(unit.statuses),
            "resistances": deepcopy(unit.resistances),
            "effective_speed": status_rules.speed(battle, unit),
            "blocked_move": battle.status_blocks(unit, "move"),
            "blocked_act": battle.status_blocks(unit, "act"),
            "formation": formation_preview(battle, unit.id),
            "battle_digest": battle.digest(),
            "certainty": "observed_initial_state",
        }
        # Only the actual active enemy's next command is meaningful here.
        report["active_enemy_plan"] = (
            active_enemy_plan(battle)
            if battle.active_id == actor_id and unit.team == "enemy" else None)
        return report

    def undo(self):
        return self.session.undo()

    def redo(self):
        return self.session.redo()
