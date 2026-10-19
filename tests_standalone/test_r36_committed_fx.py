"""R36.B1: event-locked visual effects with bounded CPU and unchanged action replay."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.action_controller import ActionPlayerController
from drawtemp.render.committed_fx import (
    CommittedFxDirector, MAX_ACTIVE, MAX_EMITS_PER_TICK,
)
from sporebound.action_runtime import ActionRuntime


def encounter_scene():
    return {
        "id": "r36_fx", "width": 7, "height": 7, "walls": [],
        "hero": {"pos": [1, 1], "hp": 12},
        "enemies": [{"id": "wolf", "pos": [2, 1], "hp": 1, "patrol": []}],
        "objects": [],
    }


class CommittedFxTests(unittest.TestCase):
    def test_hits_and_vfx_share_exact_authoritative_event_tick(self):
        scene = encounter_scene()
        player = ActionPlayerController(scene)
        reference = ActionRuntime(scene)
        commands = {"tick": 1, "dx": 1, "attack": True}
        expected = reference.step(commands)
        events = player.step(dx=1, attack=True)
        self.assertEqual(events, expected)
        self.assertEqual(player.runtime.recording(), reference.recording())
        self.assertEqual(player.runtime.digest(), reference.digest())
        self.assertEqual(
            [r["kind"] for r in events],
            ["hero_attack", "enemy_hit", "enemy_dead"])
        view = player.state()
        self.assertEqual(view["tick"], 1)
        self.assertEqual(
            [r["kind"] for r in view["fx"]],
            ["slash", "impact", "defeat"])
        self.assertEqual([r["id"] for r in view["fx"]],
                         ["1:0", "1:1", "1:2"])
        self.assertEqual(view["fx"][1]["actor"], "wolf")
        self.assertEqual((view["fx"][1]["x"], view["fx"][1]["y"]), (2, 1))
        # Pure redraw doesn't advance or replay a visual event.
        self.assertEqual(player.state()["fx"], view["fx"])
        view["fx"][1]["x"] = -1
        self.assertEqual(player.state()["fx"][1]["x"], 2)
        self.assertEqual(player.runtime.recording(), reference.recording())

    def test_save_load_preserves_action_save_and_resets_only_fx(self):
        with TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "action.json"
            p = ActionPlayerController(encounter_scene(), save_path=checkpoint)
            p.step(dx=1, attack=True)
            committed = p.runtime.recording()
            p.save()
            saved_bytes = checkpoint.read_bytes()
            self.assertNotIn(b'"fx"', saved_bytes)
            p.step()
            self.assertTrue(p.state()["fx"])
            p.load()
            self.assertEqual(p.runtime.recording(), committed)
            self.assertEqual(p.state()["fx"], [])
            p.step()
            self.assertEqual(p.runtime.tick, 2)
            self.assertEqual(p.state()["fx"], [])
            self.assertEqual(checkpoint.read_bytes(), saved_bytes)

    def test_corruption_rejected_without_dropping_active_fx(self):
        with TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "action.json"
            p = ActionPlayerController(encounter_scene(), save_path=checkpoint)
            p.step(dx=1, attack=True)
            p.save()
            before = p.state()["fx"]
            checkpoint.write_text("not a valid checkpoint", encoding="utf-8")
            with self.assertRaises(ValueError):
                p.load()
            self.assertEqual(p.state()["fx"], before)

    def test_budgets_ttl_and_reduced_flashes_do_not_mutate_sim(self):
        runtime = ActionRuntime(encounter_scene())
        fx = CommittedFxDirector()
        for tick in range(1, 25):
            runtime.step({"tick": tick})
            state = runtime.snapshot()
            events = [{"tick": tick, "kind": "hero_attack"} for _ in range(125)]
            fx.observe(state, events)
            self.assertLessEqual(len(fx.snapshot()), MAX_ACTIVE)
            self.assertEqual(len(fx.snapshot()), min(8, tick) * MAX_EMITS_PER_TICK
                             if tick <= 3 else len(fx.snapshot()))
        self.assertEqual(len(fx.snapshot()), MAX_ACTIVE)
        fx.reset(runtime.tick)
        self.assertEqual(fx.snapshot(), [])
        runtime.step({"tick": runtime.tick + 1})
        fx.observe(runtime.snapshot(), [{"tick": runtime.tick, "kind": "hero_hit"}])
        self.assertEqual(len(fx.snapshot()), 1)
        self.assertEqual(fx.snapshot(reduced_flashes=True), [])
        self.assertEqual(len(fx.snapshot()), 1)
        self.assertEqual(runtime.digest(), ActionRuntime.from_recording(
            runtime.recording()).digest())

    def test_bad_tick_or_forged_event_is_rejected_atomically(self):
        runtime = ActionRuntime(encounter_scene())
        fx = CommittedFxDirector()
        runtime.step({"tick": 1})
        before = fx.snapshot()
        invalid_events = (
            [{"tick": 2, "kind": "hero_hit"}],
            [{"tick": 1, "kind": 10}],
            [{"tick": 1, "kind": "enemy_hit", "enemy": "not-present"}],
        )
        for events in invalid_events:
            with self.subTest(events=events), self.assertRaises(ValueError):
                fx.observe(runtime.snapshot(), events)
            self.assertEqual(fx.snapshot(), before)
        fx.observe(runtime.snapshot(), [])
        with self.assertRaises(ValueError):
            fx.observe(runtime.snapshot(), [])

    def test_fx_stream_deterministic_across_identical_commands(self):
        first, second = (ActionRuntime(encounter_scene()) for _ in range(2))
        fx_first, fx_second = CommittedFxDirector(), CommittedFxDirector()
        for tick in range(1, 27):
            command = {"tick": tick, "dx": 1 if tick == 1 else 0,
                       "attack": tick in (1, 15)}
            e1, e2 = first.step(deepcopy(command)), second.step(deepcopy(command))
            self.assertEqual(e1, e2)
            self.assertEqual(fx_first.observe(first.snapshot(), e1),
                             fx_second.observe(second.snapshot(), e2))
        self.assertEqual(first.recording(), second.recording())


if __name__ == "__main__":
    unittest.main()
