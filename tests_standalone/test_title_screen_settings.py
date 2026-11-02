"""Title-screen authoring data is validated independently of any Tk display."""
import unittest
from types import SimpleNamespace
from sporebound.title_screen_settings import (
    DEFAULTS, NAMESPACE, extension_for, settings_for, validate_title_screen,
)
from sporebound.model import RuleError
from sporebound.title_menu_cinematic import title_geometry
from sporebound.title_screen_layout import (
    CARD_KEYS, ELEMENTS, default_boxes, placement, relocate, resolve_boxes,
)


class TitleScreenSettingsTests(unittest.TestCase):
    def test_legacy_projects_keep_defaults_without_mutation(self):
        project = SimpleNamespace(extensions={})
        self.assertEqual(settings_for(project), DEFAULTS)
        self.assertEqual(project.extensions, {})

    def test_roundtrip_override(self):
        data = dict(background="image", image="art/title/background.png",
                    accent="#CDA46A", labels={"new": "Commencer"})
        project = SimpleNamespace(extensions={NAMESPACE: extension_for(data)})
        actual = settings_for(project)
        self.assertEqual(actual["labels"]["new"], "Commencer")
        self.assertEqual(actual["background"], "image")
        self.assertTrue(actual["show_campaign"])
        actual["labels"]["new"] = "Changed"
        self.assertEqual(settings_for(project)["labels"]["new"], "Commencer")

    def test_reject_paths_and_invalid_values(self):
        invalid = (
            {"background": "image", "image": "../private.png"},
            {"background": "image", "image": "/tmp/title.png"},
            {"background": "image", "image": "art/../../secret.png"},
            {"background": "image", "image": "C:\\other.png"},
            {"background": "image", "image": "art/file.svg"},
            {"background": "image", "image": ""},
            {"accent": "red"},
            {"panel": "#gggggg"},
            {"show_campaign": 1},
            {"labels": {"unknown": "X"}},
            {"labels": {"new": ""}},
            {"unknown": True},
            {"positions": {"random": [0.1, 0.2]}},
            {"positions": {"title": [-0.1, 0.2]}},
            {"positions": {"title": [0.1, 1.01]}},
            {"positions": {"title": ["0.1", 0.2]}},
            {"positions": {"title": [True, 0.2]}},
            {"positions": {"title": [0.1]}},
        )
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(RuleError):
                validate_title_screen(data)


class TitleScreenPlacementTests(unittest.TestCase):
    def test_legacy_geometry_is_unchanged(self):
        for w, h in ((800, 580), (1160, 820), (1920, 1080)):
            with self.subTest(size=(w, h)):
                legacy = title_geometry(w, h)
                expected = default_boxes(w, h, legacy)
                self.assertEqual(resolve_boxes(w, h, legacy, {}), expected)
                self.assertEqual(
                    [expected[key] for key in CARD_KEYS], legacy["cards"])
                self.assertEqual(expected["campaign"], legacy["campaign"])
                self.assertEqual(len(expected), len(ELEMENTS))

    def test_dragged_rect_clamps_without_resizing(self):
        for w, h in ((800, 580), (1160, 820), (1920, 1080)):
            with self.subTest(size=(w, h)):
                layout = title_geometry(w, h)
                original = resolve_boxes(w, h, layout)
                positions = {"new": [0.96, 0.99], "logo": [0, 0]}
                resolved = resolve_boxes(w, h, layout, positions)
                for key, rect in resolved.items():
                    x0, y0, x1, y1 = rect
                    self.assertGreaterEqual(x0, 0)
                    self.assertGreaterEqual(y0, 0)
                    self.assertLessEqual(x1, w)
                    self.assertLessEqual(y1, h)
                    self.assertEqual(x1-x0, original[key][2]-original[key][0])
                    self.assertEqual(y1-y0, original[key][3]-original[key][1])
                self.assertEqual(resolved["logo"][0], 0)
                self.assertEqual(resolved["logo"][1], 0)

    def test_drag_round_trip_at_editor_reference_size(self):
        w, h = 1160, 820
        layout = title_geometry(w, h)
        base = resolve_boxes(w, h, layout)["title"]
        moved = relocate(base, 60, 100, w, h)
        xy = placement(moved, w, h)
        restored = resolve_boxes(w, h, layout, {"title": xy})["title"]
        self.assertLess(abs(restored[0]-moved[0]), 0.02)
        self.assertLess(abs(restored[1]-moved[1]), 0.02)


if __name__ == "__main__":
    unittest.main()
