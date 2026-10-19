"""R36.A headless gate: canonical authoring, state resolution, save/replay isolation."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring
from drawtemp.studio.r28d_workflow import AnimationHitboxStudio
from sporebound.animation_graph import (
    NAMESPACE, AnimationGraphError, AnimationStateController,
    controllers_from_project, validate_controller,
)
from sporebound.assets import AssetRegistry
from sporebound.game_project import GameProject


def registry():
    return AssetRegistry({
        "version": 1,
        "entries": [
            {"id": "s_idle", "kind": "sprite", "path": "art/idle.png"},
            {"id": "s_attack", "kind": "sprite", "path": "art/attack.png"},
            {"id": "s_hit", "kind": "sprite", "path": "art/hit.png"},
            {"id": "idle_anim", "kind": "animation", "loop": True,
             "frames": [{"sprite": "s_idle", "duration_ms": 120}]},
            {"id": "attack_anim", "kind": "animation", "loop": False,
             "frames": [{"sprite": "s_attack", "duration_ms": 90},
                        {"sprite": "s_hit", "duration_ms": 90}]},
        ],
        "bindings": {},
    })


def graph():
    return {"schema_version": 1, "id": "hero_animation", "initial": "idle",
            "states": [{"id": "idle", "animation": "idle_anim"},
                       {"id": "attack", "animation": "attack_anim"}],
            "transitions": [
                {"source": "idle", "target": "attack", "on": "attack",
                 "priority": 20},
                {"source": "attack", "target": "idle", "on": "finished",
                 "priority": 10},
            ]}


def authored():
    session = AuthoringSession.new(*reference_project())
    editor = AnimationHitboxStudio(session)
    for sid in ("s_idle", "s_attack", "s_hit"):
        editor.apply(editor.preview_sprite(sid, "art/" + sid + ".png"))
    editor.apply(editor.preview_animation(
        "idle_anim", [{"sprite": "s_idle", "duration_ms": 120}],
        loop=True))
    editor.apply(editor.preview_animation(
        "attack_anim", [{"sprite": "s_attack", "duration_ms": 90},
                        {"sprite": "s_hit", "duration_ms": 90}],
        loop=False))
    return session


class AnimationGraphTests(unittest.TestCase):
    def test_validated_state_graph_is_detached(self):
        data = graph()
        output = validate_controller(data, registry())
        output["states"][0]["id"] = "edited"
        self.assertEqual(data["states"][0]["id"], "idle")

    def test_missing_frames_states_schema_and_ambiguity_fail_closed(self):
        spec = graph()
        for key, value in (
            ("schema_version", 2), ("initial", "missing"),
            ("states", []), ("initial", []),
        ):
            bad = deepcopy(spec)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(AnimationGraphError):
                validate_controller(bad, registry())
        bad = deepcopy(spec)
        bad["states"][1]["animation"] = "unknown"
        with self.assertRaises(AnimationGraphError):
            validate_controller(bad, registry())
        bad = deepcopy(spec)
        bad["transitions"].append(dict(bad["transitions"][0]))
        with self.assertRaises(AnimationGraphError):
            validate_controller(bad, registry())
        bad = deepcopy(spec)
        bad["transitions"][0]["source"] = []
        with self.assertRaises(AnimationGraphError):
            validate_controller(bad, registry())

    def test_frame_resolution_and_finished_transition_are_tick_deterministic(self):
        a = AnimationStateController(graph(), registry())
        self.assertEqual(a.advance(0)["sprite"], "s_idle")
        self.assertEqual(a.advance(1, ["attack"])["state"], "attack")
        self.assertEqual(a.sample(1)["sprite"], "s_attack")
        self.assertEqual(a.advance(8)["sprite"], "s_hit")
        checkpoint = a.checkpoint()
        b = AnimationStateController(graph(), registry(), checkpoint=checkpoint)
        self.assertEqual(b.checkpoint(), checkpoint)
        self.assertEqual(a.advance(12), b.advance(12))
        self.assertEqual(a.sample(12)["sprite"], "s_idle")
        self.assertEqual(a.checkpoint(), b.checkpoint())
        with self.assertRaises(AnimationGraphError):
            a.advance(12)
        self.assertEqual(a.checkpoint(), b.checkpoint())

    def test_checkpoint_rejects_graph_change_and_corrupt_clock(self):
        a = AnimationStateController(graph(), registry())
        a.advance(0)
        snap = a.checkpoint()
        invalid = deepcopy(snap)
        invalid["entered_tick"] = 300
        with self.assertRaises(AnimationGraphError):
            AnimationStateController(graph(), registry(), checkpoint=invalid)
        edited = graph()
        edited["transitions"][0]["priority"] = 30
        with self.assertRaises(AnimationGraphError):
            AnimationStateController(edited, registry(), checkpoint=snap)

    def test_canonical_undo_redo_roundtrip_and_stale_revision(self):
        session = authored()
        editor = AnimationControllerAuthoring(session)
        baseline = session.snapshot().to_dict()
        self.assertEqual(editor.controllers(), [])
        pending = editor.preview(graph(), expected_revision=session.revision)
        self.assertEqual(session.snapshot().to_dict(), baseline)
        editor.apply(pending)
        self.assertEqual(editor.controllers(), [graph()])
        self.assertEqual(controllers_from_project(
            session.snapshot().to_dict()["project"]), [graph()])
        with self.assertRaises(AuthoringError):
            editor.apply(pending)
        session.undo()
        self.assertEqual(editor.controllers(), [])
        session.redo()
        self.assertEqual(editor.controllers(), [graph()])
        with self.assertRaises(AnimationGraphError):
            editor.preview(graph(), expected_revision=0)
        with TemporaryDirectory() as temp:
            path = Path(temp) / "r36_project.json"
            session.save_as(path)
            reloaded = AuthoringSession.open(path)
            self.assertEqual(AnimationControllerAuthoring(reloaded).controllers(), [graph()])
        editor.apply(editor.preview_remove("hero_animation",
                                          expected_revision=session.revision))
        self.assertEqual(editor.controllers(), [])
        session.undo()
        self.assertEqual(editor.controllers(), [graph()])

    def test_gameproject_load_checks_malformed_or_dangling_controller(self):
        session = authored()
        editor = AnimationControllerAuthoring(session)
        editor.apply(editor.preview(graph()))
        pair = session.snapshot().to_dict()
        content, _ = reference_project()
        valid = GameProject.from_dict(pair["project"], content)
        self.assertIn(NAMESPACE, valid.extensions)
        bad = deepcopy(pair["project"])
        bad["extensions"][NAMESPACE]["data"]["controllers"][0]["initial"] = "unknown"
        with self.assertRaises(AnimationGraphError):
            GameProject.from_dict(bad, content)
        dangling = deepcopy(pair["project"])
        dangling["assets"]["entries"] = [
            row for row in dangling["assets"]["entries"] if row["id"] != "attack_anim"]
        with self.assertRaises(ValueError):
            GameProject.from_dict(dangling, content)


if __name__ == "__main__":
    unittest.main()
