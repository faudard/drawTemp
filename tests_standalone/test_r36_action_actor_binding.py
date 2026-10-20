"""R36.B3: live R26 authored pose/marker binding remains visual-only."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.player.action_controller import ActionPlayerController
from drawtemp.player.animation_presentation import ActionAnimationPresentation
from drawtemp.render.iso_scene import scene_from_action, render_items, Camera, TopDownProjection
from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring
from drawtemp.studio.animation_timeline_authoring import AnimationTimelineAuthoring
from tests_standalone.test_r36_animation_graph import authored, graph
from tests_standalone.test_r36_animation_timeline import timeline
from tests_standalone.test_r36_committed_fx import encounter_scene
from sporebound.action_runtime import ActionRuntime


def bound_project():
    editor = authored()
    actor = AnimationControllerAuthoring(editor)
    actor.apply(actor.preview(graph()))
    markers = AnimationTimelineAuthoring(editor)
    markers.apply(markers.preview(timeline()))
    return editor.snapshot().to_dict()["project"]


class ActorAnimationPresentationTests(unittest.TestCase):
    def test_committed_action_changes_pose_and_emits_pure_visual_marker(self):
        scene = encounter_scene()
        project = bound_project()
        player = ActionPlayerController(
            scene, animation_project=project,
            animation_bindings={"hero": "hero_animation"})
        baseline = ActionRuntime(scene)
        self.assertEqual(player.state()["animation_frames"]["hero"]["state"], "idle")
        self.assertEqual(player.state()["animation_frames"]["hero"]["sprite"], "s_idle")
        emitted = player.step(dx=1, attack=True)
        baseline.step({"tick": 1, "dx": 1, "attack": True})
        self.assertIn("hero_attack", [row["kind"] for row in emitted])
        self.assertEqual(player.state()["animation_frames"]["hero"]["state"], "attack")
        self.assertEqual(player.state()["animation_frames"]["hero"]["sprite"], "s_attack")
        for tick in range(2, 5):
            player.step()
            baseline.step({"tick": tick})
        state = player.state()
        self.assertEqual(player.runtime.recording(), baseline.recording())
        self.assertEqual(
            [(row["actor"], row["kind"]) for row in state["animation_cues"]],
            [("hero", "guard")])
        self.assertEqual(len(state["animation_frames"]), 1)
        self.assertTrue(state["vfx"]["particles"])
        self.assertEqual(player.runtime.recording(), baseline.recording())
        projected = scene_from_action(
            player.runtime, animation_frames=state["animation_frames"])
        self.assertEqual(projected["actors"][0]["animation_state"], "attack")
        rows = render_items(projected, Camera(), TopDownProjection())
        actors = [row for row in rows if row["kind"] == "actor"]
        self.assertEqual(actors[0]["animationState"], "attack")
        self.assertEqual(actors[0]["spriteId"], "s_attack")
        for tick in range(5, 13):
            player.step()
            baseline.step({"tick": tick})
        self.assertEqual(player.state()["animation_frames"]["hero"]["state"], "idle")
        self.assertEqual(player.runtime.recording(), baseline.recording())

    def test_load_resets_transient_pose_and_keeps_canonical_checkpoint(self):
        with TemporaryDirectory() as directory:
            scene = encounter_scene()
            save = Path(directory) / "action.json"
            player = ActionPlayerController(
                scene, save_path=save, animation_project=bound_project(),
                animation_bindings={"hero": "hero_animation"})
            player.step(dx=1, attack=True)
            player.save()
            checkpoint = save.read_bytes()
            self.assertNotIn(b"animation_frames", checkpoint)
            player.step()
            player.load()
            self.assertEqual(player.runtime.tick, 1)
            self.assertEqual(player.state()["animation_frames"]["hero"]["state"], "idle")
            self.assertEqual(player.state()["animation_cues"], [])
            self.assertEqual(player.runtime.recording(),
                             ActionRuntime.from_recording(
                                 player.runtime.recording()).recording())
            self.assertEqual(save.read_bytes(), checkpoint)
            player.step()
            self.assertEqual(player.runtime.tick, 2)

    def test_bad_actor_binding_is_rejected_and_visual_fault_cannot_rollback(self):
        scene = encounter_scene()
        project = bound_project()
        with self.assertRaises(ValueError):
            ActionPlayerController(
                scene, animation_project=project,
                animation_bindings={"not_an_actor": "hero_animation"})
        with self.assertRaises(ValueError):
            ActionPlayerController(
                scene, animation_project=project,
                animation_bindings={"hero": "not_a_graph"})
        player = ActionPlayerController(
            scene, animation_project=project,
            animation_bindings={"hero": "hero_animation"})
        reference = ActionRuntime(scene)
        with patch.object(player.animation, "observe", side_effect=ValueError("visual fault")):
            player.step(dx=1, attack=True)
        reference.step({"tick": 1, "dx": 1, "attack": True})
        self.assertEqual(player.runtime.recording(), reference.recording())
        self.assertIn("visual fault", player.state()["fx_warning"])
        self.assertEqual(player.state()["animation_cues"], [])
        player.step()
        self.assertEqual(player.state()["fx_warning"], "")
        self.assertEqual(player.runtime.tick, 2)

    def test_same_actions_produce_identical_actor_markers_regardless_of_redraw(self):
        scene = encounter_scene()
        project = bound_project()
        players = [ActionPlayerController(
            scene, animation_project=deepcopy(project),
            animation_bindings={"hero": "hero_animation"}) for _ in range(2)]
        for tick in range(1, 14):
            for player in players:
                player.step(dx=1 if tick == 1 else 0,
                            attack=tick == 1)
            for _ in range(tick % 4):
                players[0].state()
            self.assertEqual(players[0].state()["animation_frames"],
                             players[1].state()["animation_frames"])
            self.assertEqual(players[0].state()["animation_cues"],
                             players[1].state()["animation_cues"])
        self.assertEqual(players[0].runtime.recording(),
                         players[1].runtime.recording())


if __name__ == "__main__":
    unittest.main()
