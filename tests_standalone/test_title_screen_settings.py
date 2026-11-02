"""Title-screen authoring data is validated independently of any Tk display."""
import unittest
from types import SimpleNamespace
from sporebound.title_screen_settings import (
    DEFAULTS, NAMESPACE, extension_for, settings_for, validate_title_screen,
)
from sporebound.model import RuleError


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
        )
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(RuleError):
                validate_title_screen(data)


if __name__ == "__main__":
    unittest.main()
