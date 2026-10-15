"""DrawTemp 5 R8.B: talent DAGs and mission encounter transactions."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project, MISSION
from drawtemp.studio.rpg_database import lancer_example
from drawtemp.studio.r8_advanced import RulesWorkbench
from sporebound.model import RuleError


class AdvancedR8Tests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.editor = RulesWorkbench(self.session)

    def test_talent_authoring_graph_undo_redo_and_jp(self):
        lancer_example(self.session)
        first = self.session.snapshot()
        self.editor.save_talent("r8_lancier", "stance", jp=2,
                                bonuses={"defense": 2}, creating=True)
        self.editor.save_talent("r8_lancier", "guardian",
                                jp=3, requires=["stance"],
                                exclusive="shield_stances",
                                skills=["r8_guard_ally"], creating=True)
        graph = self.editor.talent_graph("r8_lancier")
        self.assertEqual({row["id"] for row in graph["nodes"]},
                         {"stance", "guardian"})
        self.assertEqual(graph["edges"], [{"from": "stance", "to": "guardian"}])
        self.assertEqual(self.editor.talents("r8_lancier")["guardian"]["jp"], 3)
        self.assertEqual(self.session.snapshot().revision, first.revision + 2)
        self.editor.undo()
        self.assertNotIn("guardian", self.editor.talents("r8_lancier"))
        self.editor.redo()
        self.assertIn("guardian", self.editor.talents("r8_lancier"))
        Content.from_dict(self.session.snapshot().to_dict()["content"])

    def test_bad_talents_dangling_edges_and_cycles_are_atomic(self):
        lancer_example(self.session)
        self.editor.save_talent("r8_lancier", "root", creating=True)
        self.editor.save_talent("r8_lancier", "branch",
                                requires=["root"], creating=True)
        before = self.session.snapshot()
        for command in (
            lambda: self.editor.remove_talent("r8_lancier", "root"),
            lambda: self.editor.save_talent("r8_lancier", "root",
                     requires=["branch"], creating=False),
            lambda: self.editor.save_talent("r8_lancier", "invalid",
                     skills=["ghost"], creating=True),
            lambda: self.editor.save_talent("r8_lancier", "bad_jp",
                     jp=0, creating=True),
        ):
            with self.subTest(command=command), self.assertRaises(RuleError):
                command()
            self.assertEqual(self.session.snapshot(), before)

    def test_class_links_are_real_and_cycle_checked(self):
        lancer_example(self.session)
        self.editor.link_class("r8_lancier", "brave", 3)
        data = self.session.snapshot().to_dict()["content"]
        self.assertEqual(data["jobs"]["r8_lancier"]["requires"], "brave")
        self.assertEqual(data["jobs"]["r8_lancier"]["requires_level"], 3)
        self.assertEqual(self.editor.class_graph()["edges"][-1]["to"], "r8_lancier")
        with self.assertRaises(RuleError):
            self.editor.link_class("brave", "r8_lancier", 2)

    def _free_cells(self):
        mission = self.editor.mission(MISSION)
        occupied = set()
        for unit in mission["units"]:
            x, y = unit["pos"]
            width, height = unit.get("footprint", [1, 1])
            occupied.update((x + dx, y + dy)
                            for dy in range(height) for dx in range(width))
        occupied.update(tuple(obj["pos"]) for obj in mission["objects"])
        blocked = {tuple(tile["pos"])
                   for tile in mission["board"].get("tiles", [])
                   if tile.get("blocked", False)}
        return [(x, y) for y in range(mission["board"]["height"])
                for x in range(mission["board"]["width"])
                if (x, y) not in occupied and (x, y) not in blocked]

    def test_live_encounter_add_move_formation_objective_save(self):
        lancer_example(self.session)
        original = self.session.snapshot()
        cells = self._free_cells()
        self.assertGreaterEqual(len(cells), 2)
        c1, c2 = cells[:2]
        self.editor.add_actor(MISSION, "r8_lancier", "guard_r8",
                              name="Garde", team="player", cell=c1)
        self.editor.move_actor(MISSION, "guard_r8", c2)
        self.editor.set_formation(MISSION, "guard_r8", role="protector",
                                  formation="phalanx")
        self.editor.set_objective(MISSION, "eliminate", 445)
        report = self.editor.preview(MISSION)
        self.assertEqual(report["reward"], 445)
        self.assertEqual(report["players"],
                         sum(unit.team == "player" for unit in report["actors"]))
        unit = next(unit for unit in self.editor.units(MISSION)
                    if unit.id == "guard_r8")
        self.assertEqual((unit.x, unit.y), c2)
        row = next(r for r in self.editor.mission(MISSION)["units"]
                   if r["id"] == "guard_r8")
        self.assertIn("protector", row["tags"])
        self.assertIn("formation:phalanx", row["tags"])
        Content.from_dict(self.session.snapshot().to_dict()["content"])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "jeanne_r8b.json"
            self.session.save_as(path)
            reopened = RulesWorkbench(AuthoringSession.open(path))
            self.assertEqual(reopened.preview(MISSION), report)
            self.assertEqual(reopened.talents("r8_lancier"), {})
        self.editor.undo()
        self.assertNotEqual(self.editor.preview(MISSION)["reward"], 445)
        self.editor.redo()
        self.assertEqual(self.editor.preview(MISSION)["reward"], 445)
        self.assertNotEqual(self.session.snapshot().content, original.content)

    def test_invalid_spawn_and_last_enemy_removal_have_no_side_effects(self):
        lancer_example(self.session)
        before = self.session.snapshot()
        mission = self.editor.mission(MISSION)
        taken = mission["units"][0]["pos"]
        with self.assertRaises(RuleError):
            self.editor.add_actor(MISSION, "r8_lancier", "bad_spawn",
                                  name="Dup", cell=taken)
        with self.assertRaises(RuleError):
            self.editor.add_actor(MISSION, "r8_lancier", "bad_spawn",
                                  name="Dup", team="neutral", cell=(0, 0))
        self.assertEqual(self.session.snapshot(), before)
        enemies = [row["id"] for row in mission["units"]
                   if row["team"] == "enemy"]
        if len(enemies) == 1:
            with self.assertRaises(RuleError):
                self.editor.remove_actor(MISSION, enemies[0])
            self.assertEqual(self.session.snapshot(), before)

    def test_role_validation_does_not_corrupt_document(self):
        lancer_example(self.session)
        existing_id = next(row.id for row in self.editor.units(MISSION)
                           if row.team == "player")
        before = self.session.snapshot()
        with self.assertRaises(RuleError):
            self.editor.set_formation(MISSION, existing_id,
                                      formation="escort", escort_target="missing")
        self.assertEqual(self.session.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
