"""R12.7 animation director: authoritative logs, interruption and replay purity."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.animation_controller import (
    AnimationDirector, MAX_CLIPS, MAX_EVENTS, compile_clips)
from drawtemp.player.controller import PlayerController
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.ai import choose_command


@dataclass(frozen=True)
class Sample:
    revision: int
    battle: dict | None


def state(revision, events, *, mission="training", units=None):
    return Sample(revision, {
        "mission_id": mission, "events": deepcopy(events),
        "units": deepcopy(units if units is not None else [
            {"id": "jeanne", "team": "player", "pos": [1, 1]},
            {"id": "wolf", "team": "enemy", "pos": [4, 1]},
        ]),
    })


class AnimationDirectorTests(unittest.TestCase):
    def test_strict_native_event_order_damage_only_when_logged(self):
        before = state(5, [{"tick": 0, "kind": "activation", "unit": "jeanne"}])
        after = state(6, [
            {"tick": 0, "kind": "activation", "unit": "jeanne"},
            {"tick": 1, "kind": "move", "unit": "jeanne", "start": [1, 1], "end": [2, 1]},
            {"tick": 1, "kind": "skill", "unit": "jeanne", "skill": "attack", "cell": [4, 1]},
            {"tick": 1, "kind": "miss", "unit": "wolf"},
            {"tick": 1, "kind": "cast_failed", "unit": "jeanne"},
        ], units=[
            {"id": "jeanne", "team": "player", "pos": [2, 1]},
            {"id": "wolf", "team": "enemy", "pos": [4, 1]},
        ])
        original = deepcopy(after.battle)
        clips = compile_clips(before, after)
        self.assertEqual([clip["kind"] for clip in clips],
                         ["move", "attack", "miss", "interrupt"])
        self.assertEqual(clips[0]["start"], [1, 1])
        self.assertEqual(clips[0]["end"], [2, 1])
        self.assertEqual(clips[1]["start"], [2, 1])
        self.assertEqual(clips[1]["end"], [4, 1])
        self.assertEqual([clip for clip in clips if clip["kind"] == "impact"], [])
        self.assertEqual(after.battle, original)

    def test_damage_heal_and_displacement_follow_recorded_events(self):
        before = state(0, [])
        after = state(1, [
            {"tick": 1, "kind": "skill", "unit": "jeanne", "skill": "attack", "cell": [4, 1]},
            {"tick": 1, "kind": "damage", "unit": "wolf", "amount": 17},
            {"tick": 1, "kind": "displace", "unit": "wolf", "pos": [5, 1]},
            {"tick": 1, "kind": "heal", "unit": "jeanne", "amount": 5},
        ], units=[
            {"id": "jeanne", "team": "player", "pos": [1, 1]},
            {"id": "wolf", "team": "enemy", "pos": [5, 1]},
        ])
        result = compile_clips(before, after)
        self.assertEqual([c["kind"] for c in result],
                         ["attack", "impact", "move", "heal"])
        self.assertEqual(result[1]["amount"], 17)
        self.assertEqual(result[2]["start"], [4, 1])
        self.assertEqual(result[2]["end"], [5, 1])
        self.assertEqual(result[3]["amount"], 5)

    def test_unchanged_stale_reordered_and_other_mission_journals_cancel(self):
        base = state(2, [{"kind": "activation", "unit": "jeanne"}])
        later = state(3, [
            {"kind": "activation", "unit": "jeanne"},
            {"kind": "damage", "unit": "wolf", "amount": 6},
        ])
        self.assertEqual(compile_clips(base, base), [])
        self.assertEqual(compile_clips(later, base), [])
        self.assertEqual(compile_clips(base, state(3, later.battle["events"],
                                                  mission="another")), [])
        self.assertEqual(compile_clips(base, state(3, [
            {"kind": "activation", "unit": "wolf"},
            {"kind": "damage", "unit": "wolf", "amount": 6},
        ])), [])
        self.assertEqual(compile_clips(base, Sample(3, None)), [])
        self.assertEqual(compile_clips(Sample(0, None), later), [])
        self.assertEqual(compile_clips(base, state(4, [
            *base.battle["events"], *([{"kind": "damage", "unit": "wolf",
                                       "amount": 1}] * (MAX_EVENTS + 1))
        ])), [])

    def test_bounded_queue_and_generation_cancel(self):
        before = state(1, [])
        after = state(2, [{"kind": "damage", "unit": "wolf", "amount": 2}
                          for _ in range(MAX_CLIPS + 4)])
        clips = compile_clips(before, after)
        self.assertEqual(len(clips), MAX_CLIPS)
        animator = AnimationDirector()
        first = animator.update(before, after)
        self.assertEqual(first["clips"], clips)
        first["clips"][0]["amount"] = 999
        self.assertEqual(animator.snapshot()["clips"][0]["amount"], 2)
        second = animator.cancel()
        self.assertEqual(second["clips"], [])
        self.assertGreater(second["serial"], first["serial"])
        third = animator.update(before, Sample(3, None))
        self.assertEqual(third["clips"], [])
        self.assertGreater(third["serial"], second["serial"])

    def test_live_battle_events_do_not_mutate_session_or_replay(self):
        content, project = reference_project()
        with TemporaryDirectory() as temp:
            player = PlayerController(content, project, "main", temp)
            player.new_game()
            player.choose("enter")
            player.start_mission(MISSION)
            director = AnimationDirector()
            observed = set()
            for _ in range(500):
                before = player.session.snapshot()
                battle = player.session._session.active_battle
                if battle is None or battle.result:
                    break
                command = choose_command(battle)
                player.session.execute(command)
                after = player.session.snapshot()
                recording = player.session.recording()
                plan = director.update(before, after)
                observed.update(clip["kind"] for clip in plan["clips"])
                self.assertEqual(recording, player.session.recording())
                self.assertEqual(plan["revision"], after.revision)
            self.assertIn("move", observed)
            self.assertIn("attack", observed)
            self.assertIn("impact", observed)
            player.save(1)
            saved = Path(temp) / "slot_1.json"
            copy = PlayerController(content, project, "main", temp)
            copy.load(1)
            self.assertEqual(copy.session.recording(), player.session.recording())
            self.assertEqual(director.cancel()["clips"], [])
            self.assertEqual(compile_clips(copy.session.snapshot(),
                                           copy.session.snapshot()), [])


if __name__ == "__main__":
    unittest.main()
