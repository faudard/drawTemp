"""Headless tests for the existing Tk Studio's textured 2D map.

No display, Pillow or Qt dependency. The renderer uses a recorded fake Canvas.
"""
from types import SimpleNamespace
import unittest

from drawtemp.assets.topdown_tileset import tile_rgba
from drawtemp.render.autotile2d import encode_key, tile_key
from sporebound.model import Board, Tile
from sporebound.topdown_tk_art import (
    BoardTileIndex, autotile_png, compose_tile_rgba, overlay_png, png_rgba,
)
from sporebound.topdown_tk_renderer import draw_topdown


def pixel(data, x, y):
    p = (y * 64 + x) * 4
    return tuple(data[p:p + 4])


class TopdownCompositionTests(unittest.TestCase):
    def test_base_tile_uses_original_2d_atlas(self):
        key = encode_key("grass", ["grass"] * 8, 0)
        self.assertEqual(compose_tile_rgba(key), tile_rgba("grass", 0))
        self.assertEqual(compose_tile_rgba(key), compose_tile_rgba(key))
        self.assertTrue(autotile_png(key).startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(png_rgba(tile_rgba("rock", 0)).startswith(
            b"\x89PNG\r\n\x1a\n"))

    def test_four_quadrants_and_priority_are_composed_independently(self):
        # N=dirt; NE/E=stone; SE=rock; remaining cells grass.
        key = encode_key("grass", (
            "dirt", "stone", "stone", "rock",
            "grass", "grass", "grass", "grass"), 0)
        rgba = compose_tile_rgba(key)
        self.assertEqual(pixel(rgba, 0, 0), pixel(tile_rgba("dirt", 0), 0, 0))
        self.assertEqual(pixel(rgba, 63, 0), pixel(tile_rgba("stone", 0), 63, 0))
        self.assertEqual(pixel(rgba, 63, 63), pixel(tile_rgba("rock", 0), 63, 63))
        self.assertEqual(pixel(rgba, 0, 63), pixel(tile_rgba("grass", 0), 0, 63))

    def test_different_elevation_does_not_bleed_transitions(self):
        board = Board(2, 1, {
            (0, 0): Tile(surface="grass", height=0),
            (1, 0): Tile(surface="stone", height=3),
        })
        key = tile_key(BoardTileIndex(board), 0, 0)
        self.assertEqual(compose_tile_rgba(key), tile_rgba("grass", 0))

    def test_layer_masks_preserve_each_quadrant_alpha(self):
        image = overlay_png("dirt", (255, 90, 0, 200), 0, 50)
        self.assertTrue(image.startswith(b"\x89PNG"))
        # Cross-check raw alpha through PNG decompression, no PIL dependency.
        from struct import unpack
        from zlib import decompress
        offset = 8
        image_data = b""
        while offset < len(image):
            length = unpack(">I", image[offset:offset + 4])[0]
            tag = image[offset + 4:offset + 8]
            data = image[offset + 8:offset + 8 + length]
            if tag == b"IDAT":
                image_data += data
            offset += length + 12
        rows = decompress(image_data)
        def alpha(x, y):
            return rows[y * (64 * 4 + 1) + 1 + x * 4 + 3]
        self.assertEqual([alpha(0, 0), alpha(63, 0),
                          alpha(0, 63), alpha(63, 63)],
                         [127, 45, 0, 100])
        with self.assertRaises(ValueError):
            overlay_png("grass", (255, -1, 0, 0), 0, 100)

    def test_png_rejects_partial_image(self):
        with self.assertRaises(ValueError):
            png_rgba(b"bad")


class FakeCanvas:
    def __init__(self):
        self.events = []
    def delete(self, *args):
        self.events.append(("delete", (), {"tags": args}))
    def configure(self, **kwargs):
        self.events.append(("configure", (), kwargs))
    def _create(self, typ, args, kwargs):
        self.events.append((typ, args, kwargs))
        return len(self.events)
    def create_image(self, *a, **k):
        return self._create("image", a, k)
    def create_rectangle(self, *a, **k):
        return self._create("rectangle", a, k)
    def create_line(self, *a, **k):
        return self._create("line", a, k)
    def create_oval(self, *a, **k):
        return self._create("oval", a, k)
    def create_text(self, *a, **k):
        return self._create("text", a, k)


class FakeTerrain:
    def __init__(self):
        self.keys = []
        self.layers = []
        self.frames = 0
    def begin_frame(self):
        self.frames += 1
    def terrain(self, key, size):
        self.keys.append((key, size))
        return "terrain-photo"
    def layer(self, material, mask, variant, opacity, size):
        self.layers.append((material, tuple(mask), variant, opacity, size))
        return "layer-photo"


class FakeSprite:
    def __init__(self):
        self.calls = []
    def sprite(self, *args):
        self.calls.append(args)
        return "real-asset-photo"


class TopdownCanvasTests(unittest.TestCase):
    def make_scene(self):
        board = Board(2, 2, {(0, 0): Tile(surface="grass", feature="tree"),
                              (1, 0): Tile(surface="dirt")})
        mission = SimpleNamespace(
            goal=[], deployment=[], relic=None, structures=[],
            objects=[{"kind": "chest", "pos": (0, 1)}])
        unit = SimpleNamespace(
            id="jeanne", name="Jeanne", team="player", pos=(1, 1),
            alive=True, facing=(0, 1), hp=40)
        return board, mission, [unit]

    def test_true_sprites_are_drawn_between_lower_and_upper_layers(self):
        board, mission, units = self.make_scene()
        canvas = FakeCanvas()
        terrain = FakeTerrain()
        props, actors, objects = FakeSprite(), FakeSprite(), FakeSprite()
        visual = [
            {"id": "ground", "plane": "below", "visible": True,
             "opacity": 80,
             "cells": [{"pos": [0, 0], "material": "sand",
                        "mask": [255, 0, 0, 0]}]},
            {"id": "canopy", "plane": "above", "visible": True,
             "opacity": 60,
             "cells": [{"pos": [1, 1], "material": "grass",
                        "mask": [0, 255, 0, 255]}]},
        ]
        draw_topdown(
            canvas, board, mission, units, cell_size=54,
            layers={"Terrain": True, "Décors": True, "Unités": True,
                    "Objets": True, "Objectifs": True, "Bâtiments": True},
            selected_cell=(0, 1), selected_tiles={(1, 0)}, atlas=terrain,
            props=props, actors=actors, objects_atlas=objects,
            visual_layers=visual)
        tags = [event[2].get("tags", ()) for event in canvas.events]
        def index(tag):
            return next(i for i, row in enumerate(tags) if tag in row)
        self.assertLess(index("topdown_autotile"),
                        index("topdown_plane_below"))
        self.assertLess(index("topdown_plane_below"), index("topdown_decor"))
        self.assertLess(index("topdown_decor"), index("topdown_actor"))
        self.assertLess(index("topdown_actor"), index("topdown_plane_above"))
        self.assertLess(index("topdown_plane_above"), index("selection"))
        self.assertEqual(len(terrain.keys), 4)
        self.assertEqual(terrain.frames, 1)
        self.assertEqual(len(terrain.layers), 2)
        self.assertTrue(props.calls)
        self.assertTrue(actors.calls)
        self.assertTrue(objects.calls)

    def test_layer_visibility_and_painting_do_not_modify_map(self):
        board, mission, units = self.make_scene()
        original = dict(board.tiles)
        canvas = FakeCanvas()
        draw_topdown(canvas, board, mission, units, cell_size=54,
                     layers={"Terrain": False, "Décors": False,
                             "Unités": False, "Objets": False},
                     selected_cell=(1, 0), grid=True)
        self.assertEqual(original, board.tiles)
        self.assertTrue(any("topdown_grid" in e[2].get("tags", ())
                            for e in canvas.events))
        self.assertFalse(any("topdown_actor" in e[2].get("tags", ())
                             for e in canvas.events))


if __name__ == "__main__":
    unittest.main()
