"""R7.18 portable audiovisual structural golden/reference regression gate."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from sporebound.cinematic_visual_goldens import (
    assert_golden_matches, golden_at, golden_sha256)
from sporebound.cinematics import cinematic_template, event_template
from sporebound.model import RuleError


GOLDEN = Path(__file__).parent / "goldens" / "r7_18_castle_scene.json"


def castle_golden_clip():
    clip = cinematic_template("castle_golden", "Reference gate",
                              "campaign_start", "main")
    clip["duration_ms"] = 2000
    bg = event_template("background", "sky", 0, 2000)
    bg["color"] = "#243c56"
    actor = event_template("actor", "walk", 0, 2000)
    actor.update(actor="jeanne", easing="ease_in_out",
                 **{"from": [.25, .6], "to": [.75, .6]})
    camera = event_template("camera", "camera", 0, 2000)
    camera.update(shot="arrival", transition="wipe",
                  **{"from": [0., 0.], "to": [.2, 0.]},
                  zoom_from=1., zoom_to=1.5)
    dialogue = event_template("dialogue", "speech", 500, 1200)
    dialogue.update(speaker="Jeanne", text="Une porte",
                    portrait="jeanne", expression="determined",
                    chars_per_second=8)
    fade = event_template("fade", "blackout", 1500, 500)
    score = event_template("sound", "score", 0, 2000)
    score.update(cue="theme", bus="music", volume=80, volume_to=40,
                 loop=True)
    clip["events"] = [bg, actor, camera, dialogue, fade, score]
    return clip


class R718GoldenTests(unittest.TestCase):
    def setUp(self):
        self.clip = castle_golden_clip()
        self.fixture = json.loads(GOLDEN.read_text(encoding="utf-8"))

    def test_reviewed_reference_at_1x_2x_and_all_visual_beats(self):
        clips = {"castle_golden": self.clip}
        result = assert_golden_matches(clips, self.fixture)
        self.assertEqual(len(result), 64)
        self.assertEqual(result, assert_golden_matches(clips, self.fixture))
        self.assertEqual(len(self.fixture["samples"]), 6)

    def test_seek_replay_and_studio_player_snapshot_are_order_independent(self):
        samples = [(s["expected"]["ms"], s["expected"]["viewport"])
                   for s in self.fixture["samples"]]
        forward = [golden_at(self.clip, ms, viewport=size, portrait=True)
                   for ms, size in samples]
        backward = [golden_at(self.clip, ms, viewport=size, portrait=True)
                    for ms, size in reversed(samples)]
        self.assertEqual(forward, list(reversed(backward)))
        self.assertEqual(golden_sha256(forward),
                         golden_sha256(list(reversed(backward))))

    def test_resize_dpi_projection_and_presentation_safe_area(self):
        at1 = golden_at(self.clip, 1000, viewport=(800, 500), portrait=True)
        at2 = golden_at(self.clip, 1000, viewport=(1600, 1000), portrait=True)
        self.assertEqual(at1["actors"], at2["actors"])
        self.assertEqual(at1["camera"], at2["camera"])
        self.assertEqual(at1["zoom"], at2["zoom"])
        self.assertEqual(at1["dialogue"], at2["dialogue"])
        for (x1, y1), (x2, y2) in zip(at1["actor_centers"],
                                     at2["actor_centers"]):
            self.assertAlmostEqual(x2, x1 * 2, places=3)
            self.assertAlmostEqual(y2, y1 * 2, places=3)
        for snapshot in (at1, at2):
            x0, y0, x1, y1 = snapshot["dialogue_boxes"][0]
            w, h = snapshot["viewport"]
            self.assertTrue(0 <= x0 < x1 <= w)
            self.assertTrue(0 <= y0 < y1 <= h)
        self.assertEqual(at2["portrait_images"],
                         ["portrait:jeanne_determined"])

    def test_canonical_layer_sequence_and_audio_fades(self):
        start = golden_at(self.clip, 0, portrait=True)
        wipe = golden_at(self.clip, 250, portrait=True)
        speech = golden_at(self.clip, 1000, portrait=True)
        end = golden_at(self.clip, 1750, portrait=True)
        self.assertEqual(start["transition"], ["wipe", 0.0])
        self.assertEqual(wipe["transition"], ["wipe", 0.5])
        self.assertIsNone(speech["transition"])
        self.assertEqual(speech["labels"][-1], "Une ")
        self.assertEqual(speech["mix"], [["score", "music", 0.6, True]])
        self.assertEqual(end["fade"], ["#000000", 0.5])
        self.assertFalse(end["dialogue_boxes"])

    def test_accidental_rebaseline_is_rejected_by_default(self):
        for change in ("volume", "camera", "text", "portrait", "fixture"):
            clip = deepcopy(self.clip)
            expected = deepcopy(self.fixture)
            if change == "volume":
                clip["events"][-1]["volume_to"] = 20
            elif change == "camera":
                clip["events"][2]["to"] = [.4, 0.]
            elif change == "text":
                clip["events"][3]["text"] = "Une grille"
            elif change == "portrait":
                clip["events"][3]["expression"] = "sad"
            else:
                expected["samples"][0]["expected"]["background"] = "#eeeeee"
            with self.subTest(change=change), self.assertRaises(RuleError):
                assert_golden_matches({"castle_golden": clip}, expected)


if __name__ == "__main__":
    unittest.main()
