"""3.7.32D: stable projection, minimap viewport, and authored revision tests."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor_refresh_scale import (
    EditorContentProjection, MinimapBackgroundCache)
from sporebound.model import Content, RuleError


class FakeMinimapCanvas:
    def __init__(self):
        self.items = []
        self.next_id = 0

    def find_all(self):
        return tuple(row[0] for row in self.items)

    def create_rectangle(self, *coords, **options):
        self.next_id += 1
        self.items.append((self.next_id, options.get("tags", "")))
        return self.next_id

    def delete(self, tag):
        if tag == "all":
            self.items = []
        else:
            self.items = [row for row in self.items if row[1] != tag]


class MapRefreshScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Content.load(DEFAULT_CONTENT).to_dict()

    def make_map(self, size):
        return add_blank_mission(deepcopy(self.source),
                                 "large_map", "Grande carte", size, size)

    def test_validated_content_is_reused_at_all_map_sizes(self):
        for size in (32, 64, 128):
            with self.subTest(size=size):
                raw = self.make_map(size)
                cache = EditorContentProjection()
                first = cache.get(raw)
                self.assertEqual(first.missions["large_map"].board.width, size)
                self.assertIs(first, cache.get(raw))
                self.assertIs(first, cache.get(deepcopy(raw)))
                self.assertEqual(cache.generation, 1)
                self.assertEqual(cache.rebuilds, 1)
                # A nested in-place terrain edit must invalidate a generation.
                row = next(m for m in raw["missions"] if m["id"] == "large_map")
                row["board"]["tiles"].append(
                    {"pos": [size - 2, size - 2], "surface": "water",
                     "blocked": True})
                edited = cache.get(raw)
                self.assertIsNot(edited, first)
                self.assertEqual(cache.generation, 2)
                self.assertTrue(
                    edited.missions["large_map"].board.tile(
                        (size - 2, size - 2)).blocked)
                # Undo restoring the first snapshot is another valid generation.
                cache.get(self.make_map(size))
                self.assertEqual(cache.generation, 3)

    def test_invalid_mutation_does_not_poison_projection(self):
        raw = self.make_map(32)
        cache = EditorContentProjection()
        original = cache.get(raw)
        invalid = deepcopy(raw)
        row = next(m for m in invalid["missions"] if m["id"] == "large_map")
        row["board"]["width"] = 500
        with self.assertRaises((RuleError, ValueError)):
            cache.get(invalid)
        self.assertIs(cache.get(raw), original)
        self.assertEqual(cache.generation, 1)

    def test_minimap_static_background_and_viewport_parity(self):
        cache, canvas = MinimapBackgroundCache(), FakeMinimapCanvas()
        key = (1, "large_map", 128, 128, ("terrain", True))
        self.assertTrue(cache.needs_background(key, canvas))
        canvas.create_rectangle(0, 0, 184, 184, tags="base")
        canvas.create_rectangle(2, 2, 24, 24, tags="terrain")
        canvas.create_rectangle(0, 0, 45, 45, tags="viewport")
        cache.complete(key, canvas, background_redrawn=True)
        static_ids = canvas.find_all()[:-1]
        for i in range(8):
            self.assertFalse(cache.needs_background(key, canvas))
            canvas.delete("viewport")
            canvas.create_rectangle(i, i, 30+i, 30+i, tags="viewport")
            cache.complete(key, canvas, background_redrawn=False)
            self.assertEqual(canvas.find_all()[:-1], static_ids)
        self.assertEqual(cache.full_repaints, 1)
        self.assertEqual(cache.viewport_updates, 9)
        self.assertTrue(cache.needs_background((2, *key[1:]), canvas))
        self.assertTrue(cache.needs_background((1, *key[1:-1], ("terrain", False)),
                                               canvas))
        # Out-of-band draw is detected, not left as a stale view.
        canvas.create_rectangle(1, 1, 2, 2, tags="external")
        self.assertTrue(cache.needs_background(key, canvas))
        cache.invalidate()
        self.assertTrue(cache.needs_background(key, canvas))


    def test_selection_only_studio_does_not_rebuild_expensive_panels(self):
        from types import SimpleNamespace
        from sporebound.studio_panels import StudioPanels

        class Label:
            text = None

            def config(self, **kw):
                self.text = kw.get("text")

        studio = StudioPanels.__new__(StudioPanels)
        studio.project = object()
        studio.doc = lambda: SimpleNamespace(
            data={"missions": [{"id": "large_map", "name": "Grande carte"}]})
        studio.mission = lambda: "large_map"
        studio.selection = lambda: (120, 120)
        studio.cell_label = Label()

        class NeverRefresh:
            def refresh(self):
                raise AssertionError("Full Studio refresh on selection-only!")

        studio.workspace = NeverRefresh()
        studio.advanced = NeverRefresh()
        studio.world_studio = NeverRefresh()
        studio.refresh_selection()
        self.assertIn("(120, 120)", studio.cell_label.text)


if __name__ == "__main__":
    unittest.main()
