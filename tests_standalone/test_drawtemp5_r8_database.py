"""R8 5.0 acceptance: canonical database actions + live Battle protection."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.rpg_database import DatabaseEditor, lancer_example, used_flags
from sporebound.character_authoring import make_effect
from sporebound.engine import Battle
from sporebound.model import Board, Mission, RuleError, Unit


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.editor = DatabaseEditor(self.session)

    def test_lancier_single_transaction_and_reversible(self):
        baseline = self.session.snapshot()
        lancer_example(self.session)
        snap = self.session.snapshot()
        self.assertEqual(snap.revision, baseline.revision + 1)
        data = snap.to_dict()["content"]
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["jobs"]["r8_lancier"]["skills"], {"r8_guard_ally": 1})
        self.assertEqual(data["equipment"]["r8_spear"]["slot"], "weapon")
        self.assertEqual(data["archetypes"]["r8_lancier"]["weapon"], "spear")
        self.assertEqual(data["archetypes"]["r8_lancier"]["skills"], ["r8_guard_ally"])
        self.assertEqual(next(s for s in data["skills"]
                              if s["id"] == "r8_guard_ally")["effects"][0]["status"],
                         "protect")
        Content.from_dict(data)
        self.editor.undo()
        self.assertEqual(self.session.snapshot().content, baseline.content)
        self.editor.redo()
        self.assertEqual(self.session.snapshot().content, snap.content)

    def test_lancier_protect_skill_executes_in_real_battle(self):
        lancer_example(self.session)
        data = self.session.snapshot().to_dict()["content"]
        skill = Content.from_dict(data).skills["r8_guard_ally"]
        battle_content = Content(
            {"r8_guard_ally": skill},
            {"demo": Mission("demo", "R8 — protection", Board(8, 5), [
                Unit("lancier", "Lancier", "player", (0, 1),
                     speed=20, weapon="spear", skills=["r8_guard_ally"]),
                Unit("ally", "Compagnon", "player", (1, 1), speed=10),
                Unit("wolf", "Loup", "enemy", (4, 1), speed=10),
            ])},
        )
        battle = Battle(battle_content, "demo", seed=11)
        self.assertEqual(battle.active_id, "lancier")
        battle.execute({"kind": "act", "skill": "r8_guard_ally", "cell": [1, 1]})
        self.assertIn("protect", battle.unit("ally").statuses)
        self.assertEqual(battle.unit("lancier").mp, 9)

    def test_dangling_references_rejected_before_delete(self):
        lancer_example(self.session)
        before = self.session.snapshot()
        with self.assertRaises(AuthoringError):
            self.editor.remove("skills", "r8_guard_ally")
        with self.assertRaises(AuthoringError):
            self.editor.remove("archetypes", "missing")
        self.assertEqual(self.session.snapshot(), before)
        self.assertIn("archetype/r8_lancier/skills",
                      self.editor.references("skills", "r8_guard_ally"))

    def test_skill_multieffect_duplicate_all_fields(self):
        lancer_example(self.session)
        extra = make_effect("heal", power=4)
        self.editor.set_effect("r8_guard_ally", 1, extra, insert=True)
        self.editor.update("skills", "r8_guard_ally", accuracy=85, radius=1)
        before = self.editor.detail("skills", "r8_guard_ally")
        self.editor.duplicate("skills", "r8_guard_ally", "r8_guard_copy")
        after = self.editor.detail("skills", "r8_guard_copy")
        self.assertEqual(after["effects"], before["effects"])
        self.assertEqual(after["accuracy"], 85)
        self.assertEqual(after["radius"], 1)
        self.editor.move_effect("r8_guard_copy", 1, -1)
        self.assertEqual(self.editor.detail("skills", "r8_guard_copy")
                         ["effects"][0]["kind"], "heal")
        self.editor.remove_effect("r8_guard_copy", 1)
        self.assertEqual(len(self.editor.detail("skills", "r8_guard_copy")
                             ["effects"]), 1)

    def test_transaction_rolls_back_if_any_step_fails(self):
        before = self.session.snapshot()
        with self.assertRaises(AuthoringError):
            self.editor.apply_many((
                ("jobs", "create", "first", "", {"name": "First"}),
                ("jobs", "create", "second", "",
                 {"name": "Bad", "requires": "missing"}),
            ))
        self.assertEqual(self.session.snapshot(), before)

    def test_stale_preview_rejected_even_after_undo(self):
        plan = self.editor.preview_many((
            ("jobs", "create", "preview_job", "", {"name": "Test"}),))
        self.editor.create("jobs", "other", name="Other")
        self.editor.undo()
        with self.assertRaises(AuthoringError) as caught:
            self.editor.commit(plan)
        self.assertEqual(caught.exception.code, "stale_revision")

    def test_job_cycle_rejected(self):
        lancer_example(self.session)
        self.editor.create("jobs", "r8_guardian", name="Gardien",
                           requires="r8_lancier")
        before = self.session.snapshot()
        with self.assertRaises(AuthoringError):
            self.editor.link_job("r8_lancier", "r8_guardian")
        with self.assertRaises(AuthoringError):
            self.editor.update("jobs", "r8_lancier", requires="r8_guardian")
        self.assertEqual(self.session.snapshot(), before)

    def test_reusable_template_cannot_rewrite_placed_unit(self):
        lancer_example(self.session)
        pair = self.session.snapshot().to_dict()
        mission = Content.from_dict(pair["content"]).missions[next(
            iter(Content.from_dict(pair["content"]).missions))]
        occupied = set()
        for actor in mission.units:
            occupied.update(actor.occupied_cells())
        occupied.update(tuple(obj["pos"]) for obj in mission.objects)
        cell = next((x, y) for y in range(mission.board.height)
                    for x in range(mission.board.width)
                    if (x, y) not in occupied and not mission.board.tile((x, y)).blocked)
        self.editor.create("actors", "guard_01", mission_id=mission.id,
                           archetype="r8_lancier", name="Lancier de garde",
                           team="player", pos=list(cell))
        placed = self.editor.detail("actors", "guard_01", mission.id)
        self.editor.update("archetypes", "r8_lancier", attack=11)
        after = self.editor.detail("actors", "guard_01", mission.id)
        self.assertEqual(placed["attack"], after["attack"])
        self.assertEqual(self.editor.detail("archetypes", "r8_lancier")["attack"], 11)

    def test_flags_are_inferred_from_project_not_extra_database(self):
        project = {"story": {"scenes": [{"choices": [
            {"when": {"flag": "rescued_jeanne", "eq": True},
             "effects": [{"kind": "set_flag", "flag": "quest_active", "value": True}]}
        ]}]}}
        self.assertEqual(used_flags(project), {"rescued_jeanne", "quest_active"})
        self.assertFalse(self.editor.entries("flags"))

    def test_save_reopen_preserves_both_documents_and_ids(self):
        lancer_example(self.session)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r8.json"
            self.editor.save_as(path)
            self.assertEqual(self.session.snapshot().dirty, False)
            opened = AuthoringSession.open(path)
            restored = DatabaseEditor(opened)
            self.assertEqual(restored.detail("jobs", "r8_lancier")["name"],
                             "Lancier")
            original = self.session.snapshot().to_dict()
            saved = opened.snapshot().to_dict()
            self.assertEqual(saved["content"], original["content"])
            self.assertEqual(saved["project"], original["project"])
            Content.from_dict(saved["content"])
            GameProject.from_dict(saved["project"], Content.from_dict(saved["content"]))


if __name__ == "__main__":
    unittest.main()
