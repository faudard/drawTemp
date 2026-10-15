"""R8.C: cross-document names/variables, rollback and multi-edit gates."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.rpg_database import DatabaseEditor, lancer_example
from drawtemp.studio.r8_integrity import IntegrityEditor, flags, renamed_documents
from sporebound.model import Content, RuleError


class R8IntegrityTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.editor = DatabaseEditor(self.session)
        self.integrity = IntegrityEditor(self.session)

    def _add_project_usages(self):
        def add(project):
            project["story"]["scenes"][0]["choices"][0]["effects"] = [
                {"kind": "set_flag", "flag": "trust", "value": True},
                {"kind": "grant_item", "item": "r8_spear", "quantity": 1},
            ]
            project["campaign_flow"] = {
                "gates": {MISSION: {"flag": "trust", "eq": True}},
                "outcomes": {MISSION: {"victory": [
                    {"kind": "add_flag", "flag": "morale", "amount": 1},
                    {"kind": "equip_hero", "hero": "jeanne", "item": "r8_spear"},
                ]}},
            }
            project["battle_support"] = [
                {"mission": MISSION, "flag": "trust", "gte": 1,
                 "potion_bonus": 1},
            ]
            return project
        self.session.apply(self.session.preview_project(add))

    def test_variables_index_includes_read_write_and_type(self):
        lancer_example(self.session)
        self._add_project_usages()
        catalog = self.integrity.flags()
        self.assertEqual(set(catalog), {"trust", "morale"})
        uses = catalog["trust"]
        self.assertGreaterEqual(len(uses), 3)
        self.assertTrue(any(u.context == "write" for u in uses))
        self.assertTrue(any(u.context == "condition" for u in uses))
        self.assertTrue(any(u.document == "GameProject.battle_support" for u in uses))
        self.assertTrue(any("campaign_flow" in u.document for u in uses))
        self.assertIn("trust", {x.id for x in self.editor.entries("flags")})
        self.assertTrue(self.editor.references("flags", "trust"))

    def test_flag_rename_one_transaction_undo_save_restore(self):
        lancer_example(self.session)
        self._add_project_usages()
        old = self.session.snapshot()
        with self.assertRaises(RuleError):
            self.integrity.rename("flags", "trust", "alliance")
        self.assertEqual(self.session.snapshot(), old)
        result = self.integrity.rename("flags", "trust", "alliance",
                                       acknowledge_external_saves=True)
        self.assertEqual(result.snapshot.revision, old.revision + 1)
        self.assertNotIn("trust", self.integrity.flags())
        self.assertEqual(len(self.integrity.flags()["alliance"]), 3)
        with TemporaryDirectory() as tmp:
            self.session.save_as(Path(tmp) / "r8_integrity.json")
            reopened = IntegrityEditor(AuthoringSession.open(
                Path(tmp) / "r8_integrity.json"))
            self.assertEqual(reopened.flags(), self.integrity.flags())
        self.session.undo()
        self.assertIn("trust", self.integrity.flags())
        self.session.redo()
        self.assertIn("alliance", self.integrity.flags())

    def test_equipment_rename_updates_story_campaign_and_rejects_collision(self):
        lancer_example(self.session)
        self._add_project_usages()
        before = self.session.snapshot()
        with self.assertRaises(RuleError):
            self.integrity.rename("equipment", "r8_spear", "r8_spear",
                                  acknowledge_external_saves=True)
        self.assertEqual(self.session.snapshot(), before)
        self.integrity.rename("equipment", "r8_spear", "long_spear",
                              acknowledge_external_saves=True)
        pair = self.session.snapshot().to_dict()
        self.assertIn("long_spear", pair["content"]["equipment"])
        self.assertEqual(pair["project"]["story"]["scenes"][0]
                         ["choices"][0]["effects"][1]["item"], "long_spear")
        self.assertEqual(pair["project"]["campaign_flow"]["outcomes"][MISSION]
                         ["victory"][1]["item"], "long_spear")
        Content.from_dict(pair["content"])

    def test_campaign_equipment_references_block_delete(self):
        lancer_example(self.session)
        self._add_project_usages()
        references = self.editor.references("equipment", "r8_spear")
        self.assertTrue(any("GameProject/campaign_flow" in ref
                            for ref in references))
        self.assertTrue(any("GameProject/story" in ref for ref in references))
        original = self.session.snapshot()
        with self.assertRaises(AuthoringError):
            self.editor.remove("equipment", "r8_spear")
        self.assertEqual(self.session.snapshot(), original)

    def test_skill_rename_preserves_job_archetype_and_instances(self):
        lancer_example(self.session)
        before = self.session.snapshot()
        self.integrity.rename("skills", "r8_guard_ally", "shield_guard",
                              acknowledge_external_saves=True)
        pair = self.session.snapshot().to_dict()
        self.assertIn("shield_guard", [row["id"] for row in pair["content"]["skills"]])
        self.assertEqual(pair["content"]["jobs"]["r8_lancier"]["skills"],
                         {"shield_guard": 1})
        self.assertEqual(pair["content"]["archetypes"]["r8_lancier"]["skills"],
                         ["shield_guard"])
        with self.assertRaises(RuleError):
            self.integrity.rename("skills", "shield_guard", "estoc",
                                  acknowledge_external_saves=True)
        self.assertNotEqual(self.session.snapshot(), before)
        Content.from_dict(self.session.snapshot().to_dict()["content"])

    def test_archetype_rename_updates_placed_actor(self):
        lancer_example(self.session)
        mission = self.editor.snapshot().to_dict()["content"]["missions"][0]
        busy = {tuple(u["pos"]) for u in mission["units"]}
        busy.update(tuple(o["pos"]) for o in mission["objects"])
        blocked = {tuple(t["pos"]) for t in mission["board"]["tiles"]
                   if t.get("blocked")}
        cell = next([x,y] for y in range(mission["board"]["height"])
                    for x in range(mission["board"]["width"])
                    if (x,y) not in busy | blocked)
        self.editor.create("actors", "guard_new", mission_id=MISSION,
                           archetype="r8_lancier", name="Guard",
                           team="player", pos=cell)
        self.integrity.rename("archetypes", "r8_lancier", "r8_spear_guard",
                              acknowledge_external_saves=True)
        pair = self.editor.snapshot().to_dict()["content"]
        self.assertIn("r8_spear_guard", pair["archetypes"])
        self.assertEqual(next(u["archetype"] for u in pair["missions"][0]["units"]
                              if u["id"] == "guard_new"), "r8_spear_guard")

    def test_bulk_actor_update_is_one_undo_and_failure_is_atomic(self):
        before = self.session.snapshot()
        actors = self.editor.entries("actors")
        self.assertGreaterEqual(len(actors), 2)
        group = [(a.family, a.id, a.mission_id) for a in actors[:2]]
        prior = [self.editor.detail("actors", a.id, a.mission_id)["speed"]
                 for a in actors[:2]]
        result = self.integrity.apply_bulk(group, {"speed": 13})
        self.assertEqual(result.snapshot.revision, before.revision + 1)
        self.assertEqual([self.editor.detail("actors", a.id, a.mission_id)["speed"]
                          for a in actors[:2]], [13, 13])
        stale = self.integrity.plan_bulk(group, {"speed": 12})
        self.session.undo()
        self.assertEqual([self.editor.detail("actors", a.id, a.mission_id)["speed"]
                          for a in actors[:2]], prior)
        with self.assertRaises(AuthoringError):
            self.session.apply(stale)
        self.session.redo()
        after = self.session.snapshot()
        bad = [*group, ("actors", "not_existing", MISSION)]
        with self.assertRaises(AuthoringError):
            self.integrity.apply_bulk(bad, {"attack": 7})
        self.assertEqual(self.session.snapshot(), after)
        with self.assertRaises(RuleError):
            self.integrity.plan_bulk([group[0], group[0]], {"speed": 3})
        with self.assertRaises(RuleError):
            self.integrity.plan_bulk([group[0], ("jobs", "brave", "")],
                                     {"speed": 3})

    def test_document_rename_is_pure_and_declines_unknown_family(self):
        content, project = reference_project()
        orig_c, orig_p = content.to_dict(), project.to_dict()
        changed, unchanged = renamed_documents(orig_c, orig_p, "jobs",
                                               "brave", "brave_renamed")
        self.assertIn("brave_renamed", changed["jobs"])
        self.assertNotIn("brave_renamed", orig_c["jobs"])
        self.assertEqual(unchanged, orig_p)
        with self.assertRaises(RuleError):
            renamed_documents(orig_c, orig_p, "actors", "jeanne", "jeanne_new")
        with self.assertRaises(RuleError):
            renamed_documents(orig_c, orig_p, "jobs", "brave", "not valid")

if __name__ == "__main__":
    unittest.main()
