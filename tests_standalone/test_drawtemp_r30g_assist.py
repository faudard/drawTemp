"""R30.G deterministic helpers; actual R1 validation and undo, no hidden writes."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.r30_assist_generation import (
    AssistController, AssistError, MODES,
)
from sporebound.studio_transaction import validate_pair


RECT = (0, 0, 4, 3)


class AssistedGenerationTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)
        self.helper = AssistController(self.session)
        self.before = self.session.snapshot().to_dict()

    def preview(self, mode="clearing", *, seed=7, rect=RECT, namespace="demo"):
        return self.helper.preview(
            MISSION, rectangle=rect, seed=seed,
            mode=mode, namespace=namespace)

    def test_clearing_only_adds_unoccupied_unauthored_tiles(self):
        old = next(m for m in self.before["content"]["missions"] if m["id"] == MISSION)
        previous_tiles = {tuple(t["pos"]): t for t in old["board"]["tiles"]}
        previous_units = deepcopy(old["units"])
        previous_objects = deepcopy(old["objects"])
        preview = self.preview()
        self.assertTrue(preview.tiles)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        changed_positions = {(cell.x, cell.y) for cell in preview.tiles}
        self.assertFalse(changed_positions & set(previous_tiles))
        self.assertFalse(changed_positions & {tuple(u["pos"]) for u in previous_units})
        self.assertFalse(preview.to_dict()["gameplay_certified"])
        after = self.helper.apply(preview).snapshot.to_dict()
        mission = next(m for m in after["content"]["missions"] if m["id"] == MISSION)
        updated_tiles = {tuple(t["pos"]): t for t in mission["board"]["tiles"]}
        for point, tile in previous_tiles.items():
            self.assertEqual(updated_tiles[point], tile)
        self.assertEqual(mission["units"], previous_units)
        self.assertEqual(mission["objects"], previous_objects)
        self.assertEqual(after["project"], self.before["project"])
        self.assertEqual(
            len(updated_tiles), len(previous_tiles) + len(preview.tiles))
        validate_pair(after["content"], after["project"])
        self.assertEqual(self.session.undo().snapshot.to_dict()["content"],
                         self.before["content"])

    def test_trail_is_four_connected_and_seed_deterministic(self):
        result = self.preview("trail", seed=12)
        positions = [(cell.x, cell.y) for cell in result.tiles]
        self.assertTrue(positions)
        for before, after in zip(positions, positions[1:]):
            self.assertEqual(abs(before[0] - after[0]) +
                             abs(before[1] - after[1]), 1)
        twin = AssistController(AuthoringSession.new(self.content, self.project))
        comparison = twin.preview(MISSION, rectangle=RECT,
                                  mode="trail", seed=12, namespace="demo")
        self.assertEqual(result.tiles, comparison.tiles)
        self.assertEqual(result.to_dict(), comparison.to_dict())
        different = twin.preview(MISSION, rectangle=RECT,
                                 mode="trail", seed=13, namespace="demo")
        self.assertNotEqual(result.tiles, different.tiles)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_lever_door_is_real_linked_canonical_objects_accessible_to_player(self):
        proposal = self.preview("lever-door", namespace="bridge")
        self.assertEqual(set(proposal.object_ids),
                         {"r30g_bridge_door", "r30g_bridge_switch"})
        self.assertTrue(proposal.switch_reachable)
        self.assertFalse(proposal.tiles)
        self.assertEqual(len(proposal.object_cells), 2)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        changed = self.helper.apply(proposal).snapshot.to_dict()
        mission = next(m for m in changed["content"]["missions"] if m["id"] == MISSION)
        door = next(item for item in mission["objects"]
                    if item["id"] == "r30g_bridge_door")
        switch = next(item for item in mission["objects"]
                      if item["id"] == "r30g_bridge_switch")
        self.assertEqual(door["kind"], "door")
        self.assertEqual(switch["kind"], "switch")
        self.assertEqual(switch["link"], door["id"])
        self.assertEqual(changed["project"], self.before["project"])
        self.assertEqual(changed["content"]["missions"][0]["units"],
                         self.before["content"]["missions"][0]["units"])
        validate_pair(changed["content"], changed["project"])
        self.assertEqual(self.session.undo().snapshot.to_dict()["content"],
                         self.before["content"])

    def test_namespace_collision_does_not_duplicate_existing_puzzle(self):
        self.helper.apply(self.preview("lever-door", namespace="single"))
        applied = self.session.snapshot().to_dict()
        with self.assertRaises(AssistError) as ctx:
            self.preview("lever-door", namespace="single")
        self.assertEqual(ctx.exception.code, "duplicate_object")
        self.assertEqual(self.session.snapshot().to_dict(), applied)
        self.helper.apply(self.preview("lever-door", namespace="other"))
        objects = self.session.snapshot().to_dict()["content"]["missions"][0]["objects"]
        self.assertEqual(len({obj["id"] for obj in objects}), len(objects))

    def test_rect_bounds_types_seed_and_modes_are_refused(self):
        for mode, rect, seed, namespace in (
            ("invalid", RECT, 1, "demo"), ("clearing", (0, 0, 100, 100), 1, "demo"),
            ("clearing", (0, 0, 1, 1), -1, "demo"),
            ("clearing", (True, 0, 2, 2), 1, "demo"),
            ("clearing", (0, 0, 3, 3), True, "demo"),
            ("clearing", RECT, 0, "../unsafe"),
            ("clearing", RECT, 0, "UPPER"),
        ):
            with self.subTest(mode=mode, rect=rect, seed=seed, namespace=namespace):
                with self.assertRaises(AssistError):
                    self.helper.preview(MISSION, rectangle=rect, mode=mode,
                                        seed=seed, namespace=namespace)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_existing_authored_tree_tile_is_not_overwritten_and_noop_refused(self):
        with self.assertRaises(AssistError) as ctx:
            self.preview(rect=(0, 0, 1, 1))
        self.assertEqual(ctx.exception.code, "no_safe_cells")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_single_safe_cell_cannot_fake_solvable_puzzle(self):
        with self.assertRaises(AssistError) as ctx:
            self.preview("lever-door", rect=(7, 5, 1, 1))
        self.assertEqual(ctx.exception.code, "unreachable_switch")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_preview_becomes_stale_after_edit_then_undo_aba(self):
        preview = self.preview()
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "subtitle": "Changed"}))
        self.session.undo()
        original = self.session.snapshot().to_dict()
        with self.assertRaises(AuthoringError) as ctx:
            self.helper.apply(preview)
        self.assertEqual(ctx.exception.code, "stale_revision")
        self.assertEqual(self.session.snapshot().to_dict(), original)
        with self.assertRaises(AssistError):
            self.helper.apply(preview)

    def test_preview_must_be_explicit_and_single_use(self):
        first = self.preview()
        second = self.preview(seed=8)
        with self.assertRaises(AssistError):
            self.helper.apply(first)
        self.helper.apply(second)
        with self.assertRaises(AssistError):
            self.helper.apply(second)

    def test_no_disk_writes_before_explicit_save_and_reopen(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "game.json"
            AuthoringSession.new(self.content, self.project).save_as(path)
            game = path.with_name("game.game.json")
            previous = path.read_bytes(), game.read_bytes()
            session = AuthoringSession.open(path)
            controller = AssistController(session)
            proposal = controller.preview(MISSION, rectangle=RECT,
                                          mode="clearing", seed=7)
            self.assertEqual((path.read_bytes(), game.read_bytes()), previous)
            controller.apply(proposal)
            self.assertEqual((path.read_bytes(), game.read_bytes()), previous)
            session.save()
            self.assertNotEqual(path.read_bytes(), previous[0])
            reopened = AuthoringSession.open(path)
            self.assertEqual(reopened.snapshot().to_dict()["content"],
                             session.snapshot().to_dict()["content"])


if __name__ == "__main__":
    unittest.main()
