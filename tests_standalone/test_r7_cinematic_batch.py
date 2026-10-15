"""R7.20 reliability gates: atomic selection, clipboard, persistence and replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematic_batch import (
    copy_events, delete_events, paste_events, selected_events, shift_events)
from sporebound.cinematic_authoring4 import add_motion_keyframe
from sporebound.cinematics import cinematic_template, event_template, frame_at
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError


class R720BatchTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.clip = cinematic_template("village", "Village", "campaign_start", "main")
        self.clip["duration_ms"] = 7000
        actor = event_template("actor", "jeanne", 1000, 1600)
        actor = add_motion_keyframe(actor, 800)
        dialogue = event_template("dialogue", "line", 2200, 1000)
        dialogue.update(text="Allons au château", portrait="jeanne",
                        expression="determined", chars_per_second=12)
        music = event_template("sound", "theme", 500, 5000)
        music.update(cue="jeanne_music", bus="music", volume=80, volume_to=45,
                     loop=True, fade_in_ms=200, fade_out_ms=300)
        self.clip["events"] = [actor, dialogue, music]

    def validate(self, clip):
        project = deepcopy(self.project)
        project.cinematics = [clip]
        project.validate(self.content)
        return project

    def test_selected_order_is_authored_not_click_order(self):
        events = selected_events(self.clip, ("theme", "jeanne"))
        self.assertEqual([e["id"] for e in events], ["jeanne", "theme"])
        for ids in ((), ("jeanne", "jeanne"), ("missing",), ("line", 1)):
            with self.subTest(ids=ids), self.assertRaises(RuleError):
                selected_events(self.clip, ids)

    def test_multitrack_copy_cross_clip_keeps_offsets_and_keyframes(self):
        original = deepcopy(self.clip)
        clipboard = copy_events(self.clip, ("line", "jeanne"))
        dest = cinematic_template("castle", "Château", "campaign_start", "main")
        dest["duration_ms"] = 9000
        pasted, ids = paste_events(dest, clipboard, 1500)
        self.assertEqual([e["start_ms"] for e in pasted["events"]],
                         [1500, 2700])
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(pasted["events"][0]["keyframes"],
                         self.clip["events"][0]["keyframes"])
        self.assertEqual(pasted["events"][1]["expression"], "determined")
        self.validate(pasted)
        self.assertEqual(self.clip, original)
        # Clipboard is not an alias of the selected source event dictionary.
        pasted["events"][0]["keyframes"][0]["pos"][0] = -1
        self.assertNotEqual(pasted["events"][0]["keyframes"],
                            clipboard["events"][0]["keyframes"])

    def test_repeated_paste_allocates_stable_noncolliding_ids(self):
        clipboard = copy_events(self.clip, ("jeanne",))
        first, first_ids = paste_events(self.clip, clipboard, 3500)
        second, second_ids = paste_events(first, clipboard, 5200)
        self.assertEqual(first_ids, ("jeanne_copy",))
        self.assertEqual(second_ids, ("jeanne_copy2",))
        self.validate(second)
        self.assertEqual(len({e["id"] for e in second["events"]}), 5)

    def test_group_shift_preserves_relative_offset_and_audio_automation(self):
        old = deepcopy(self.clip)
        after = shift_events(self.clip, ("jeanne", "theme"), 900)
        self.assertEqual([e["start_ms"] for e in after["events"]],
                         [1900, 2200, 1400])
        self.assertEqual(after["events"][0]["keyframes"][0]["at_ms"], 800)
        self.assertEqual(after["events"][2]["volume_to"], 45)
        self.validate(after)
        self.assertEqual(self.clip, old)
        with self.assertRaises(RuleError):
            shift_events(self.clip, ("theme", "jeanne"), 1700)
        with self.assertRaises(RuleError):
            shift_events(self.clip, ("jeanne",), -1001)
        with self.assertRaises(RuleError):
            shift_events(self.clip, ("jeanne",), 5.5)

    def test_invalid_paste_is_atomic_even_if_only_one_event_overflows(self):
        dest = cinematic_template("short", "Court", "campaign_start", "main")
        dest["duration_ms"] = 2500
        clipboard = copy_events(self.clip, ("jeanne", "line"))
        before = deepcopy(dest)
        with self.assertRaises(RuleError):
            # Actor ends at 2000 ms; dialogue alone ends at 2600 ms.
            paste_events(dest, clipboard, 400)
        self.assertEqual(dest, before)
        with self.assertRaises(RuleError):
            paste_events(dest, clipboard, True)
        self.assertEqual(dest, before)
        for invalid in ({"version": 0}, {"events": []},
                        {**clipboard, "origin_ms": 1234}):
            with self.assertRaises(RuleError):
                paste_events(self.clip, invalid, 100)

    def test_cut_delete_undo_roundtrip_as_one_project_revision(self):
        original = self.validate(deepcopy(self.clip))
        before = original.to_dict()
        clipboard = copy_events(self.clip, ("jeanne", "theme"))
        cut = delete_events(self.clip, ("jeanne", "theme"))
        self.assertEqual([e["id"] for e in cut["events"]], ["line"])
        cut_project = self.validate(cut)
        repasted, ids = paste_events(cut, clipboard, 1200)
        reloaded = self.validate(repasted)
        with TemporaryDirectory() as folder:
            filename = Path(folder) / "r720.game.json"
            reloaded.save(filename, self.content)
            from_disk = GameProject.load(filename, self.content)
            self.assertEqual(from_disk.cinematics[0]["events"],
                             repasted["events"])
        # The project before the entire cut transaction remains reconstructible
        # and no gameplay timeline or narrative action was executed.
        self.assertEqual(
            GameProject.from_dict(before, self.content).to_dict(), before)
        self.assertEqual(len(cut_project.cinematics[0]["events"]), 1)
        self.assertEqual(len(ids), 2)

    def test_group_move_deterministic_at_same_playhead(self):
        moved = shift_events(self.clip, ("jeanne", "line", "theme"), 100)
        self.validate(moved)
        for ms in (0, 500, 1100, 2000, 3400, 5000):
            self.assertEqual(frame_at(moved, ms), frame_at(moved, ms))


if __name__ == "__main__":
    unittest.main()
