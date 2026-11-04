"""Regression tests for Title Screen WYSIWYG content and localization."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from sporebound.model import RuleError
from sporebound.title_screen_settings import (
    DEFAULTS, NAMESPACE, display_text, extra_box, extension_for,
    settings_for, validate_title_screen,
)


def text_element(name="text1"):
    return {
        "id": name, "kind": "text", "text": "Hello",
        "image": "", "color": "#f4ead7", "size": 28,
        "x": 0.2, "y": 0.1, "width": 0.3, "height": 0.15,
    }


class WysiwygContractTests(unittest.TestCase):
    def test_legacy_no_override(self):
        project = SimpleNamespace(extensions={})
        self.assertEqual(settings_for(project), DEFAULTS)
        self.assertEqual(project.extensions, {})

    def test_overlay_roundtrip_does_not_mutate_project(self):
        data = {
            "source_language": "fr",
            "extras": [text_element()],
            "hidden": ["logo", "campaign_action"],
            "captions": {"new": "Une autre aventure"},
            "strings": {"campaign_heading": "Épisode actuel"},
            "translations": {
                "en": {
                    "title": "Ashes of the Kingdom",
                    "labels": {"new": "Start"},
                    "extras": {"text1": "Welcome"},
                },
            },
        }
        project = SimpleNamespace(extensions={NAMESPACE: extension_for(data)})
        loaded = settings_for(project)
        self.assertEqual(loaded["extras"][0]["text"], "Hello")
        self.assertEqual(
            display_text(loaded, "en", "extras", "text1", "Hello"), "Welcome")
        self.assertEqual(
            display_text(loaded, "en", "labels", "new", "Nouvelle partie"),
            "Start")
        self.assertEqual(
            display_text(loaded, "fr", "labels", "new", "Nouvelle partie"),
            "Nouvelle partie")
        loaded["extras"][0]["text"] = "Modified"
        self.assertEqual(settings_for(project)["extras"][0]["text"], "Hello")

    def test_english_fallback_for_non_source_locale(self):
        data = validate_title_screen({
            "source_language": "fr", "labels": {"new": "Partie"},
        })
        self.assertEqual(display_text(data, "fr", "labels", "new", "Original"), "Partie")
        self.assertEqual(display_text(data, "en", "labels", "new", "Original"), "New game")
        self.assertEqual(display_text(data, "en", "strings", "help", "Aide"), "Help")

    def test_extra_box_is_responsive_and_clamped(self):
        extra = text_element()
        extra["x"], extra["y"] = 0.99, 0.98
        for width, height in ((800, 580), (1160, 820), (1920, 1080)):
            left, top, right, bottom = extra_box(extra, width, height)
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(top, 0)
            self.assertEqual(right, width)
            self.assertEqual(bottom, height)

    def test_reject_malformed_extra_elements_and_locales(self):
        baseline = text_element()
        invalid = (
            {"extras": [baseline, deepcopy(baseline)]},
            {"extras": [dict(baseline, id="../secret")]},
            {"extras": [dict(baseline, color="red")]},
            {"extras": [dict(baseline, size=121)]},
            {"extras": [dict(baseline, width=0)]},
            {"extras": [dict(baseline, x=True)]},
            {"extras": [dict(baseline, image="../../private.png")]},
            {"extras": [dict(baseline, kind="image")]},
            {"hidden": ["logo", "logo"]},
            {"hidden": ["nonexistent"]},
            {"hidden": [{"bad": True}]},
            {"translations": {"es": {"title": "Hola"}}},
            {"translations": {"en": {"labels": {"unknown": "Hi"}}}},
            {"translations": {"fr": {"extras": {"missing": "Bad"}}}},
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate), self.assertRaises(RuleError):
                validate_title_screen(candidate)


if __name__ == "__main__":
    unittest.main()
