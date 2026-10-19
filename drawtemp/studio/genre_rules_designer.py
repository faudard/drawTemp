"""R28.C — ability and enemy authoring on the canonical R8/R25 contracts.

Headless adapter. No new skill tables, AI rules, GameProject keys or Player
behavior are invented. Action/RPG modes remain explicit unavailable bindings.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.simulation import thaw
from drawtemp.studio.profile_authoring import inspect_profile
from drawtemp.studio.r8_combat_ai import _set_ai, BEHAVIORS, DOCTRINES, FORMATIONS, ROLES
from drawtemp.studio.rpg_database import DatabaseEditor
from sporebound.character_authoring import make_effect
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


class GenreDesignError(ValueError):
    """Configuration or preview error safe to display in the Studio."""


@dataclass(frozen=True)
class DesignPreview:
    kind: str
    plan: object
    report: dict


_SKILL_FIELDS = frozenset({
    "name", "target", "cost", "range", "min_range", "radius", "shape",
    "accuracy", "magical", "cast_ticks", "lock", "los", "optimal_range",
    "falloff_per_tile",
})
_EFFECT_FIELDS = frozenset({"kind", "power", "element", "status", "duration", "scope"})


def _tactical_scope(session, mission_id):
    pair = session.snapshot().to_dict()
    missions = {mission["id"] for mission in pair["content"]["missions"]}
    if mission_id not in missions:
        raise GenreDesignError("Une mission tactique existante est obligatoire.")
    profile = inspect_profile(session.snapshot(), mission_id)["effective"]
    if profile["combat"] != "TACTICAL_CT":
        raise GenreDesignError(
            "La capacité " + profile["combat"] +
            " n'est pas liée au designer R8. Attendre le Player R26/R28.9.")
    return profile


def _same_revision(session, revision):
    if revision is not None and (
            type(revision) is not int or revision != session.revision):
        raise GenreDesignError("Session modifiée depuis la sélection : actualiser.")


class GenreRulesDesigner:
    """Preview + commit facade over one authoritative AuthoringSession."""

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("AuthoringSession attendue")
        self.session = session
        self.database = DatabaseEditor(session)

    def missions(self):
        pair = self.session.snapshot().to_dict()
        return tuple((row["id"], row["name"])
                     for row in pair["content"]["missions"])

    def skills(self):
        return self.database.entries("skills")

    def skill(self, skill_id):
        return self.database.detail("skills", skill_id)

    def enemies(self, mission_id):
        _tactical_scope(self.session, mission_id)
        from drawtemp.studio.r8_combat_ai import CombatAIEditor
        return tuple((key, label) for key, label, team
                     in CombatAIEditor(self.session).actors(mission_id)
                     if team == "enemy")

    def enemy(self, mission_id, actor_id):
        _tactical_scope(self.session, mission_id)
        from drawtemp.studio.r8_combat_ai import CombatAIEditor
        actor = CombatAIEditor(self.session).detail(mission_id, actor_id)
        if actor["team"] != "enemy":
            raise GenreDesignError("Le designer ennemi attend une unité ennemie.")
        return actor

    def compatibility(self, scene_id):
        """Capabilities are descriptive; no false real-time gameplay forecast."""
        report = inspect_profile(self.session.snapshot(), scene_id)
        active = report["effective"]["combat"]
        return {
            "scene": scene_id,
            "combat": active,
            "editable_in_this_workbench": active == "TACTICAL_CT",
            "engine": "sporebound.engine.Battle" if active == "TACTICAL_CT" else None,
            "explanation": (
                "Compétences et IA tactiques exécutées par Battle."
                if active == "TACTICAL_CT" else
                "Profil déclaratif seulement : aucune liaison Ability/Enemy "
                "au runtime Action/RPG n'est disponible à ce stade."),
        }

    def preview_skill(self, mission_id, skill_id, properties=None,
                      *, effect_index=None, effect=None, expected_revision=None):
        """One R8 database batch; an effect and its skill properties are atomic."""
        _same_revision(self.session, expected_revision)
        _tactical_scope(self.session, mission_id)
        properties = dict(properties or {})
        if set(properties) - _SKILL_FIELDS:
            raise GenreDesignError("Champ de compétence non pris en charge.")
        if effect is not None and (type(effect) is not dict or
                                   set(effect) - _EFFECT_FIELDS):
            raise GenreDesignError("Effet non pris en charge.")
        if (effect is None) != (effect_index is None):
            raise GenreDesignError("Choisir un effet et son indice.")
        if not properties and effect is None:
            raise GenreDesignError("Aucune modification demandée.")
        before = self.skill(skill_id)
        operations = []
        if properties:
            operations.append((
                "skills", "update", skill_id, "", deepcopy(properties)))
        if effect is not None:
            if (type(effect_index) is not int or
                    not 0 <= effect_index < len(before["effects"])):
                raise GenreDesignError("Indice d'effet invalide.")
            merged = {**before["effects"][effect_index], **deepcopy(effect)}
            # The canonical maker validates supported effect kinds, then
            # the full Content validator validates scope, power and status.
            built = make_effect(**merged)
            operations.append((
                "skills", "effect", skill_id, "",
                {"index": effect_index, "effect": built}))
        plan = self.database.preview_many(operations)
        after = next(row for row in thaw(plan.content)["skills"]
                     if row["id"] == skill_id)
        return DesignPreview("skill", plan, {
            "kind": "skill", "scene": mission_id, "skill_id": skill_id,
            "revision": plan.source_revision,
            "engine": "TACTICAL_CT / Battle",
            "before": before, "after": deepcopy(after),
            "changed": before != after,
            "notes": "Aperçu du Content validé, pas une estimation de dégâts.",
        })

    def preview_enemy(self, mission_id, actor_id, *, behavior="tactical",
                      roles=(), doctrine="", route=(), squad="",
                      formation="none", escort_target="",
                      expected_revision=None, seed=1):
        """R8 AI authoring and real Battle initial-state digest, no synthetic AI."""
        _same_revision(self.session, expected_revision)
        _tactical_scope(self.session, mission_id)
        before = self.enemy(mission_id, actor_id)
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise GenreDesignError("Seed invalide.")
        def change(content, project):
            updated = _set_ai(content, mission_id, actor_id,
                              behavior=behavior, roles=roles,
                              doctrine=doctrine, route=route, squad=squad,
                              formation=formation, escort_target=escort_target)
            return updated, project
        plan = self.session.preview_pair(
            change, kind="r28.enemy.design", mission_id=mission_id,
            views=("workspace", "inspector"))
        detached = thaw(plan.content)
        actor = next(unit for mission in detached["missions"]
                     if mission["id"] == mission_id
                     for unit in mission["units"] if unit["id"] == actor_id)
        from sporebound.engine import Battle
        rules = authored_rules_for_document(detached)
        game = Battle(Content.from_dict(detached, rules=rules),
                      mission_id, seed=seed, rules=rules)
        actual = game.unit(actor_id)
        return DesignPreview("enemy", plan, {
            "kind": "enemy", "scene": mission_id, "actor_id": actor_id,
            "revision": plan.source_revision,
            "engine": "TACTICAL_CT / Battle",
            "before": before, "after": deepcopy(actor),
            "changed": before != actor,
            "observed_initial_state": {
                "battle_digest": game.digest(), "behavior": actual.behavior,
                "patrol_route": deepcopy(actor.get("patrol_route", [])),
                "tags": deepcopy(actor.get("tags", [])),
            },
            "notes": "État Battle initial observé, pas une prédiction de l'IA.",
        })

    def apply(self, preview: DesignPreview):
        if not isinstance(preview, DesignPreview) or (
                preview.kind not in ("skill", "enemy")):
            raise GenreDesignError("Prévisualisation R28.C invalide.")
        return self.session.apply(preview.plan)
