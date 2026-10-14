"""The Jeanne palette stays consistent without importing or starting Tk."""
from unittest import TestCase

from sporebound.player_visual_theme import (
    apply_player_theme, player_palette)


class FakeStyle:
    def __init__(self):
        self.configured = {}
        self.mapped = {}
        self.theme = None

    def theme_use(self, name):
        self.theme = name

    def configure(self, key, **kw):
        self.configured[key] = kw

    def map(self, key, **kw):
        self.mapped[key] = kw


class FakeRoot:
    def __init__(self):
        self.colors = {}
    def configure(self, **kw):
        self.colors.update(kw)


class FakeTtk:
    def __init__(self):
        self.style = FakeStyle()

    def Style(self, root):
        return self.style


class PlayerVisualThemeTests(TestCase):
    def test_warm_palette_applies_to_controls_and_titles(self):
        root, ttk = FakeRoot(), FakeTtk()
        palette = apply_player_theme(root, ttk, scale=1.25)
        self.assertEqual(root.colors["background"], palette.background)
        self.assertEqual(ttk.style.theme, "clam")
        self.assertEqual(
            ttk.style.configured["Player.Accent.TButton"]["background"],
            palette.gold)
        self.assertEqual(
            ttk.style.configured["Player.Title.TLabel"]["background"],
            palette.background)
        self.assertIn("TNotebook.Tab", ttk.style.mapped)
        self.assertIn("Treeview", ttk.style.configured)

    def test_high_contrast_palette_never_uses_subtle_readability_colors(self):
        high = player_palette(True)
        normal = player_palette()
        self.assertEqual(high.background, "#000000")
        self.assertEqual(high.text, "#ffffff")
        self.assertEqual(high.gold, "#ffff00")
        self.assertNotEqual(high.gold, normal.gold)
        root, ttk = FakeRoot(), FakeTtk()
        apply_player_theme(root, ttk, high_contrast=True)
        self.assertEqual(
            ttk.style.configured["TCombobox"]["fieldbackground"], "#ffffff")
        self.assertEqual(
            ttk.style.configured["TCombobox"]["foreground"], "#000000")


if __name__ == "__main__":
    import unittest
    unittest.main()
