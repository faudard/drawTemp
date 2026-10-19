"""R19.B2: committed action frames never advance or invent combat events."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import unittest

from drawtemp.player.animation_controller import AnimationDirector
from drawtemp.render.visual_clip_frames import (
    POSES, clip_art_frame, facing_for_clip,
)


class RecordingPack:
    character_id = "jeanne"
    variants = ("peasant", "armor")

    def __init__(self):
        self.calls = []
        self.missing = set()

    def duration(self, variant, action, direction):
        if (variant, action, direction) in self.missing:
            return 0
        return {"walk": 420, "attack": 510, "hit": 320,
                "magic": 930, "block": 840}.get(action, 0)

    def sample(self, *, variant, action, direction, elapsed_ms):
        self.calls.append((variant, action, direction, elapsed_ms))
        return {
            "spriteReady": True, "spriteUrl": "file:///pack/atlas.png",
            "spriteRegion": [64 * (elapsed_ms // 100), 0, 64, 64],
            "spritePivot": [32, 63],
        }


class RecordingAssets:
    def __init__(self):
        self.calls = []

    def actor_frame(self, actor_id, *, direction, pose, elapsed_ms):
        self.calls.append((actor_id, direction, pose, elapsed_ms))
        return {
            "imageUrl": "file:///project/atlas.png",
            "atlasX": 0, "atlasY": 0,
            "frameWidth": 64, "frameHeight": 64, "pivotX": 32, "pivotY": 63,
        }


def clip(kind="attack", *, actor="jeanne", start=(2, 2), end=(4, 2)):
    return {"kind": kind, "actor": actor, "start": list(start), "end": list(end),
            "duration_ms": 270}


@dataclass(frozen=True)
class Snapshot:
    revision: int
    battle: dict | None


def snapshot(revision, events):
    return Snapshot(revision, {"mission_id": "village", "events": deepcopy(events),
                               "units": [{"id": "jeanne", "team": "player",
                                          "pos": [2, 2]},
                                         {"id": "wolf", "team": "enemy",
                                          "pos": [4, 2]}]})


class VisualClipFrameTests(unittest.TestCase):
    def setUp(self):
        self.jeanne = {"id": "jeanne", "direction": "north", "alive": True}
        self.pack = RecordingPack()
        self.assets = RecordingAssets()

    def resolve(self, entry, phase=0, **kwargs):
        return clip_art_frame(entry, phase, actor=self.jeanne,
                              character=self.pack, variant="peasant",
                              assets=self.assets, **kwargs)

    def test_r7_clip_is_used_before_r4_and_timing_covers_complete_pose(self):
        entry = clip("attack")
        initial = self.resolve(entry, 0)
        final = self.resolve(entry, 1)
        self.assertEqual(initial["source"], "character_pack")
        self.assertEqual(initial["pose"], "attack")
        self.assertEqual(initial["direction"], "east")
        self.assertEqual(initial["pivotY"], 63)
        self.assertEqual(initial["atlasX"], 0)
        self.assertEqual(final["atlasX"], 64 * 5)
        self.assertEqual(self.pack.calls[-1], ("peasant", "attack", "east", 509))
        self.assertEqual(self.assets.calls, [])

    def test_cast_magic_and_impact_hit_keep_canonical_actor_facing(self):
        for kind, pose, total in (("cast", "magic", 930), ("impact", "hit", 320)):
            with self.subTest(kind=kind):
                result = self.resolve(clip(kind, start=(2, 2), end=(2, 2)), 1)
                self.assertEqual(result["direction"], "north")
                self.assertEqual(result["pose"], pose)
                self.assertEqual(self.pack.calls[-1][-1], total - 1)
        self.assertEqual(self.assets.calls, [])

    def test_moving_actor_walks_in_direction_but_does_not_invent_run(self):
        result = self.resolve(clip("move", start=(3, 3), end=(1, 3)), 0.5)
        self.assertEqual(result["pose"], "walk")
        self.assertEqual(result["direction"], "west")
        self.assertEqual(self.pack.calls[-1][:3], ("peasant", "walk", "west"))

    def test_missing_r7_magic_never_falls_back_to_legacy_idle(self):
        self.pack.missing.add(("peasant", "magic", "north"))
        result = self.resolve(clip("cast", start=(2, 2), end=(2, 2)))
        self.assertEqual(result, {})
        self.assertEqual(self.assets.calls, [])

    def test_legacy_project_atlas_remains_supported(self):
        entry = clip("attack")
        result = clip_art_frame(entry, .5, actor=self.jeanne, assets=self.assets)
        self.assertEqual(result["source"], "project_assets")
        self.assertEqual(self.assets.calls, [("jeanne", "east", "attack", 135)])

    def test_no_fake_miss_heal_interrupt_or_unknown_actor_frames(self):
        for kind in ("heal", "miss", "interrupt", "defeat", "unknown"):
            self.assertEqual(self.resolve(clip(kind)), {}, kind)
        self.assertEqual(clip_art_frame(clip("impact", actor="wolf"), 0,
                                        actor=self.jeanne, character=self.pack), {})
        self.assertEqual(self.pack.calls, [])
        self.assertEqual(self.assets.calls, [])

    def test_blocks_are_presentation_only_when_explicitly_requested(self):
        result = self.resolve(clip("block", start=(2, 2), end=(2, 2)), .6)
        self.assertEqual(result["pose"], "block")
        self.assertEqual(result["direction"], "north")

    def test_invalid_visual_phase_and_duration_fail_closed(self):
        entry = clip()
        for phase in (-.01, 1.01, float("nan"), float("inf"), None, True):
            self.assertEqual(self.resolve(entry, phase), {})
        for value in (0, -1, 60001, 3.5, True):
            trial = {**entry, "duration_ms": value}
            self.assertEqual(self.resolve(trial), {})
        self.assertEqual(self.assets.calls, [])

    def test_facing_does_not_guess_south_when_stationary(self):
        entry = clip("impact", start=(2, 2), end=(2, 2))
        self.assertEqual(facing_for_clip(entry, self.jeanne), "north")
        self.assertEqual(facing_for_clip(entry, {"direction": "invalid"}), "south")
        self.assertEqual(facing_for_clip(clip(start=(0, 0), end=(0, -1))), "north")

    def test_serial_cancellation_and_journal_purity(self):
        before = snapshot(7, [{"kind": "activation", "unit": "jeanne"}])
        after = snapshot(8, [
            {"kind": "activation", "unit": "jeanne"},
            {"kind": "skill", "unit": "jeanne", "skill": "attack", "cell": [4, 2]},
            {"kind": "damage", "unit": "wolf", "amount": 5},
            {"kind": "cast_failed", "unit": "jeanne"},
        ])
        original = deepcopy(after.battle)
        director = AnimationDirector()
        first = director.update(before, after)
        self.assertEqual([x["kind"] for x in first["clips"]],
                         ["attack", "impact", "interrupt"])
        attack = self.resolve(first["clips"][0], .5)
        self.assertEqual(attack["pose"], "attack")
        # Wolf has no R7 pack: it must use its own existing R4 binding or FX.
        enemy = {"id": "wolf", "direction": "west"}
        impact = clip_art_frame(first["clips"][1], .5, actor=enemy,
                                character=self.pack, assets=self.assets)
        self.assertEqual(impact.get("source"), "project_assets")
        self.assertEqual(clip_art_frame(first["clips"][2], .5,
                                        actor=self.jeanne, character=self.pack), {})
        self.assertEqual(after.battle, original)
        cancelled = director.cancel()
        self.assertGreater(cancelled["serial"], first["serial"])
        self.assertEqual(cancelled["clips"], [])
        self.assertEqual(POSES["impact"], ("hit", "hit"))


if __name__ == "__main__":
    unittest.main()
