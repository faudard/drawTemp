"""R74.C2: real R5 multi-room parity, R27 key gate witnesses, atomic project edits."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r74_assisted_dungeons import (
    AssistedDungeonController, DungeonAssistError,
)
from drawtemp.studio.r74_spatial_dungeons import (
    _layout_geometry, _reachable, apply_spatial_dungeons,
    prepare_spatial_dungeons,
)
from sporebound.game_session import GameSession
from sporebound.tactical_rpg3 import authored_rules_for_document


class R74SpatialDungeonTests(unittest.TestCase):
    def setUp(self):
        self.session = AuthoringSession.new(*reference_project())
        self.controller = AssistedDungeonController(self.session)
        self.suggestions = self.controller.preview_variants(
            seed=74, count=3, rooms=8, branches=2, locked_goal=True,
            biome="ruins",
        )
        self.before = self.session.snapshot().to_dict()

    def preview(self, prefix="r74s"):
        return prepare_spatial_dungeons(
            self.controller, self.suggestions, prefix=prefix)

    def test_exact_room_and_edge_topology_for_three_real_maps(self):
        prepared = self.preview()
        report = prepared.to_dict()
        self.assertTrue(report["r34_graph_parity"])
        self.assertFalse(report["combat_and_resource_parity"])
        self.assertFalse(report["player_export_certified"])
        self.assertEqual(len(report["proofs"]), 3)
        self.assertEqual([row["seed"] for row in report["proofs"]],
                         [row.seed for row in self.suggestions])
        for source, proof in zip(self.suggestions, report["proofs"]):
            self.assertEqual(proof["room_count"], source.recipe["rooms"])
            self.assertEqual(proof["physical_edges"], proof["r34_edges"])
            expected = sorted(
                [min(r["id"], n), max(r["id"], n)]
                for r in source.layout["rooms"] for n in r["neighbors"]
                if r["id"] < n
            )
            self.assertEqual(proof["physical_edges"], expected)
            self.assertTrue(proof["graph_parity"])
            self.assertTrue(proof["lock_bypass_excluded"])
            self.assertIn("collect r74_goal_key",
                          proof["goal_witness"]["witness"])
            self.assertIn("open r74_goal_door",
                          proof["exit_witness"]["witness"])
            self.assertLess(proof["exit_witness"]["states"], 50000)
            self.assertEqual(len(proof["room_centers"]), source.recipe["rooms"])
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_actual_authoritative_tiles_cannot_bypass_gate(self):
        prepared = self.preview()
        applied = apply_spatial_dungeons(self.controller, prepared).snapshot.to_dict()
        for proof, mission_id in zip(prepared.proofs, prepared.mission_ids):
            row = next(m for m in applied["content"]["missions"]
                       if m["id"] == mission_id)
            self.assertEqual(len(row["board"]["tiles"]),
                             row["board"]["width"] * row["board"]["height"])
            door = next(o for o in row["objects"] if o["kind"] == "door")
            key = next(o for o in row["objects"] if o["kind"] == "key")
            self.assertEqual(door["key"], key["id"])
            self.assertTrue(door["locked"])
            self.assertTrue(next(t for t in row["board"]["tiles"]
                                 if t["pos"] == door["pos"])["blocked"])
            self.assertEqual(row["objective"], "extract")
            self.assertEqual(row["goal"], [proof["exit"]])
            floor = {tuple(t["pos"]) for t in row["board"]["tiles"]
                     if not t["blocked"]}
            from_entry = _reachable(tuple(proof["entry"]), floor)
            self.assertNotIn(tuple(proof["exit"]), from_entry)
            self.assertIn(tuple(proof["key"]), from_entry)
            floor.add(tuple(door["pos"]))
            self.assertIn(tuple(proof["exit"]),
                          _reachable(tuple(proof["entry"]), floor))

    def test_apply_is_one_r1_edit_and_undo_redo_are_exact(self):
        preview = self.preview()
        applied = apply_spatial_dungeons(self.controller, preview).snapshot.to_dict()
        self.assertEqual(applied["revision"], self.before["revision"] + 1)
        self.assertEqual(applied["content"]["missions"][:-3],
                         self.before["content"]["missions"])
        self.assertEqual(applied["project"]["story"], self.before["project"]["story"])
        self.assertEqual(len(applied["content"]["missions"]),
                         len(self.before["content"]["missions"]) + 3)
        self.assertEqual(applied["project"]["campaigns"][-1]["id"],
                         preview.campaign_id)
        raw = applied["content"]
        content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
        project = GameProject.from_dict(applied["project"], content)
        self.assertEqual(project.campaigns[-1]["start_mission"],
                         preview.mission_ids[0])
        self.assertEqual(self.session.undo().snapshot.to_dict()["content"],
                         self.before["content"])
        self.assertEqual(self.session.redo().snapshot.to_dict()["project"],
                         applied["project"])

    def test_three_mission_campaign_is_startable_and_session_resumable(self):
        preview = self.preview()
        pair = apply_spatial_dungeons(self.controller, preview).snapshot.to_dict()
        raw = pair["content"]
        content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
        project = GameProject.from_dict(pair["project"], content)
        game = GameSession.new(content, project, preview.campaign_id, seed=74)
        self.assertIn(preview.mission_ids[0], game.available_missions())
        game.start_mission(preview.mission_ids[0])
        self.assertIsNotNone(game.battle)
        self.assertTrue(any(o["kind"] == "key" for o in game.battle.mission.objects))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "r74-multi.json"
            game.save(path)
            loaded = GameSession.load(path, content, project)
            self.assertEqual(loaded.recording(), game.recording())
            self.assertEqual(loaded.battle.mission.id, preview.mission_ids[0])

    def test_stale_invalid_prefix_and_duplicate_mission_fail_closed(self):
        for value in ("", "../", "INVALID", "a" * 13):
            with self.subTest(value=value):
                with self.assertRaises(DungeonAssistError):
                    self.preview(value)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        prepared = self.preview()
        changed = self.session.preview_project(
            lambda data: {**data, "subtitle": "Other author wrote first"})
        self.session.apply(changed)
        with self.assertRaises(AuthoringError):
            apply_spatial_dungeons(self.controller, prepared)
        self.controller.preview_variants(
            seed=74, count=3, rooms=8, branches=2, locked_goal=True)
        applied = prepare_spatial_dungeons(self.controller,
                                           self.controller._suggestions)
        apply_spatial_dungeons(self.controller, applied)
        self.controller.preview_variants(
            seed=74, count=3, rooms=8, branches=2, locked_goal=True)
        with self.assertRaises(DungeonAssistError) as duplicate:
            prepare_spatial_dungeons(self.controller,
                                     self.controller._suggestions)
        self.assertEqual(duplicate.exception.code, "duplicate_mission")

    def test_tampered_witness_and_foreign_owner_rejected(self):
        preview = self.preview()
        preview.proofs[0]["exit_witness"]["witness"].clear()
        with self.assertRaises(DungeonAssistError) as denied:
            apply_spatial_dungeons(self.controller, preview)
        self.assertEqual(denied.exception.code, "modified_preview")
        other = AssistedDungeonController(
            AuthoringSession.new(*reference_project()))
        with self.assertRaises(DungeonAssistError) as foreign:
            apply_spatial_dungeons(other, preview)
        self.assertEqual(foreign.exception.code, "foreign_preview")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_locked_and_unlocked_bounded_recipes(self):
        unlocked = self.controller.preview_variants(
            seed=90, count=3, rooms=8, branches=2, locked_goal=False)
        physical = prepare_spatial_dungeons(
            self.controller, unlocked, prefix="unlocked")
        for report in physical.proofs:
            self.assertEqual(report["lock_cells"], [])
            self.assertIsNone(report["key"])
            self.assertTrue(report["graph_parity"])
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_unsupported_large_layout_is_rejected_before_mutation(self):
        large = self.controller.preview_variants(
            seed=91, count=3, rooms=13, branches=2, locked_goal=True)
        with self.assertRaises(DungeonAssistError) as denial:
            prepare_spatial_dungeons(self.controller, large, prefix="large")
        self.assertEqual(denial.exception.code, "spatial_limit")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_three_branches_at_entry_include_left_socket_without_extra_edges(self):
        rooms = [
            {"id": i, "role": ("entry" if i == 0 else
                              "goal" if i == 2 else
                              "exit" if i == 3 else "normal"),
             "neighbors": [], "keys": []}
            for i in range(7)
        ]
        def connect(a, b):
            rooms[a]["neighbors"].append(b)
            rooms[b]["neighbors"].append(a)
        connect(0, 1)
        connect(1, 2)
        connect(2, 3)
        for child in (4, 5, 6):
            connect(0, child)
        layout = {"rooms": rooms, "locks": []}
        geometry = _layout_geometry(layout)
        self.assertEqual(len(geometry["edges"]), 6)
        self.assertEqual(geometry["positions"][6], (5, 13))
        self.assertTrue(geometry["floors"])
        self.assertLessEqual(geometry["width"], 128)


if __name__ == "__main__":
    unittest.main()
