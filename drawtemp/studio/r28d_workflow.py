"""R28.D — canonical animation authoring, event graph and isolated playtest.

Only GameProject.assets, Content.missions and GameSession own the respective
data. No new gameplay collision format, event interpreter or save protocol.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.simulation import thaw
from drawtemp.studio.events import EventStudio
from drawtemp.studio.profile_authoring import inspect_profile
from sporebound.assets import AssetRegistry
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError, require
from sporebound.tactical_rpg3 import authored_rules_for_document
from sporebound.visual_motion import animation_sprite_id


class R28DError(ValueError):
    """Scope and version validation for editor-facing diagnostics."""


@dataclass(frozen=True)
class AnimationPreview:
    plan: object
    before: dict
    after: dict
    animation_id: str


def _snapshot(session):
    return session.snapshot().to_dict()


def _assets(data):
    return deepcopy(data or {"version": 1, "entries": [], "bindings": {}})


class AnimationHitboxStudio:
    """Edit portable animation frames while hitboxes stay owned by the engine."""

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected AuthoringSession")
        self.session = session

    def manifest(self):
        return AssetRegistry(_snapshot(self.session)["project"].get("assets") or None).to_dict()

    def sprites(self):
        return tuple(row["id"] for row in self.manifest()["entries"]
                     if row["kind"] == "sprite")

    def animations(self):
        return tuple(row["id"] for row in self.manifest()["entries"]
                     if row["kind"] == "animation")

    def preview_sprite(self, sprite_id, path, *, expected_revision=None):
        """Register an existing *reference*, not a file upload or decoder."""
        if expected_revision is not None and expected_revision != self.session.revision:
            raise R28DError("Vue obsolète : actualiser les ressources.")
        def transform(project):
            data = _assets(project.get("assets"))
            require(not any(entry["id"] == sprite_id for entry in data["entries"]),
                    "Asset identifier already in use")
            data["entries"].append({"id": sprite_id, "kind": "sprite", "path": path})
            project["assets"] = AssetRegistry(data).to_dict()
            return project
        return self.session.preview_project(transform, kind="r28.sprite.register")

    def preview_animation(self, animation_id, frames, *, loop=True, slot=None,
                          expected_revision=None):
        """One R1 transaction for validated frames AND their presentation binding."""
        if expected_revision is not None and expected_revision != self.session.revision:
            raise R28DError("Vue obsolète : actualiser les animations.")
        if type(frames) not in (tuple, list):
            raise R28DError("Liste de frames requise.")
        if slot is not None and (not isinstance(slot, str) or not slot):
            raise R28DError("Nom d'emplacement d'animation invalide.")
        before = self.manifest()
        def transform(project):
            data = _assets(project.get("assets"))
            entry = {
                "id": animation_id, "kind": "animation",
                "frames": deepcopy(list(frames)), "loop": loop,
            }
            existing = next(
                (i for i, row in enumerate(data["entries"])
                 if row["id"] == animation_id), None)
            if existing is None:
                data["entries"].append(entry)
            else:
                require(data["entries"][existing]["kind"] == "animation",
                        "Cannot replace a sprite or sound with an animation")
                data["entries"][existing] = entry
            if slot is not None:
                data["bindings"].setdefault("animation", {})[slot] = animation_id
            project["assets"] = AssetRegistry(data).to_dict()
            return project
        plan = self.session.preview_project(transform, kind="r28.animation.frames")
        return AnimationPreview(plan, before, _assets(thaw(plan.project).get("assets")),
                                animation_id)

    def apply(self, preview):
        if isinstance(preview, AnimationPreview):
            return self.session.apply(preview.plan)
        return self.session.apply(preview)

    def sample(self, slot, elapsed_ms, *, actor_id="hero", team="player",
               action="idle", direction="south"):
        """Read the *actual* MotionDirector portable animation slot lookup."""
        if type(elapsed_ms) is not int or elapsed_ms < 0:
            raise R28DError("Le temps de prévisualisation doit être positif.")
        registry = AssetRegistry(self.manifest())
        spec = registry.binding("animation", slot)
        if spec is None:
            raise R28DError("Aucune animation liée à ce slot.")
        # The slot can be an actor/team pose key, e.g. hero_move_east.
        result = animation_sprite_id(
            registry, actor_id, team, action, direction, elapsed_ms)
        return {
            "slot": slot, "animation": spec["id"],
            "elapsed_ms": elapsed_ms,
            "sprite": result,
            "note": "Sélection d'image par registre, sans lecture PNG, VFX ou état de combat.",
        }

    def hitboxes(self, mission_id):
        """Project real Battle Unit.occupied_cells(), never a parallel collider."""
        pair = _snapshot(self.session)
        raw = pair["content"]
        content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
        if mission_id not in content.missions:
            raise R28DError("Mission inconnue.")
        mission = content.missions[mission_id]
        rows = [
            {
                "id": unit.id, "team": unit.team,
                "origin": list(unit.pos), "footprint": list(unit.footprint),
                "occupied_cells": [list(cell) for cell in sorted(unit.occupied_cells())],
            }
            for unit in mission.units
        ]
        return {
            "mission": mission_id,
            "board": [mission.board.width, mission.board.height],
            "units": rows,
            "editable": False,
            "note": "Empreintes Unit.occupied_cells() du moteur CT ; aucune "
                    "hitbox temps réel ni collider de sprite n'est inventé.",
        }


class EventQuestGraph:
    """Mission.triggers R9 plus diagnostics de modes et de narration R25."""

    def __init__(self, session: AuthoringSession):
        self.session = session
        self.events = EventStudio(session)

    def missions(self):
        return tuple(self.events.missions())

    def inspect(self, mission_id):
        graph = self.events.graph(mission_id)
        pair = _snapshot(self.session)
        scene_rows = []
        for row in pair["project"].get("story", {}).get("scenes", []):
            spec = inspect_profile(self.session.snapshot(), row["id"])
            scene_rows.append({
                "id": row["id"], "title": row.get("title", row["id"]),
                "combat": spec["effective"]["combat"],
                "source": spec["source"],
            })
        return {
            "mission": mission_id, "graph": deepcopy(graph),
            "events": self.events.events(mission_id),
            "diagnostics": self.events.diagnostics(mission_id),
            "story_scenes": scene_rows,
            "mode": inspect_profile(self.session.snapshot(), mission_id)["effective"],
            "runtime_note": "Le graphe exécutable est celui des triggers CT R9. "
                            "Les scènes narratives sont des liens canoniques, "
                            "pas des transitions Action/CT Player certifiées.",
        }

    def link(self, mission_id, target_event, source_event, *, any_of=False,
             expected_revision=None):
        if expected_revision is not None and expected_revision != self.session.revision:
            raise R28DError("Graphe modifié entre sélection et liaison.")
        return self.events.link(mission_id, target_event, source_event, any_of=any_of)


class IsolatedPlaytest:
    """In-memory author→canonical GameSession→verified restore, no disk writes."""

    def __init__(self, session: AuthoringSession):
        self.session = session

    def campaigns(self):
        return tuple((row["id"], row["name"]) for row in
                     _snapshot(self.session)["project"]["campaigns"])

    def run(self, campaign_id, *, choice_id=None, mission_id=None, seed=1,
            expected_revision=None):
        if expected_revision is not None and expected_revision != self.session.revision:
            raise R28DError("Projet modifié depuis le choix du playtest.")
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise R28DError("Seed invalide.")
        pair = _snapshot(self.session)
        before_revision = pair["revision"]
        content = Content.from_dict(
            pair["content"], rules=authored_rules_for_document(pair["content"]))
        project = GameProject.from_dict(pair["project"], content)
        game = GameSession.new(content, project, campaign_id, seed=seed)
        initial_story = game.active_scene()
        if choice_id is not None:
            game.choose_story_option(choice_id)
        available = list(game.available_missions())
        if mission_id is not None:
            game.start_mission(mission_id)  # canonical gates; no forced unlocks
        recording = game.recording()
        restored = GameSession.from_recording(recording, content, project)
        verified = restored.recording() == recording
        if not verified:
            raise R28DError("Le checkpoint GameSession ne se restaure pas à l'identique.")
        if self.session.revision != before_revision:
            raise R28DError("Session d'édition modifiée pendant le playtest.")
        return {
            "campaign": campaign_id, "mode": game.mode,
            "initial_scene": initial_story["id"] if initial_story else None,
            "choice": choice_id, "available_missions": available,
            "mission": mission_id, "seed": seed,
            "checkpoint_digest": recording["digest"],
            "checkpoint_verified": verified,
            "author_revision": before_revision,
            "author_dirty_unchanged": (
                self.session.snapshot().dirty == pair["dirty"]),
            "runtime": "GameSession v1 / Battle CT (isolated headless)",
            "limitations": "Pas de fenêtre Player, d'input temps réel R26, "
                           "de victoire simulée ou d'export certifié.",
        }
