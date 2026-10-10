"""Medieval bestiary, player progression and legacy content compatibility."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest

from sporebound.campaign import Campaign
from sporebound.game_project import GameProject
from sporebound.medieval_catalog import (BESTIARY, EQUIPMENT, JOBS, SKILLS,
    archetype_id, entries, find_free_cell, install_pack, place_entry)
from sporebound.model import Content, RuleError
from sporebound.player_session import PlayerSession


def arena():
    return {
        "version": 1,
        "skills": [],
        "missions": [
            {"id": "field", "name": "Aux abords du village",
             "board": {"width": 12, "height": 10},
             "units": [
                 {"id": "jeanne", "name": "Jeanne", "team": "player", "pos": [1, 1]},
                 {"id": "brigand", "name": "Brigand", "team": "enemy", "pos": [8, 8]},
             ]}
        ],
        "jobs": {"brave": {"name": "Brave"}},
    }


class MedievalCatalogTests(unittest.TestCase):
    def test_pack_import_is_opt_in_idempotent_and_non_mutating(self):
        base = arena()
        before = deepcopy(base)
        result = install_pack(base)
        self.assertEqual(base, before)
        self.assertEqual(result["missions"], Content.from_dict(base).to_dict()["missions"])
        self.assertEqual(len(result["archetypes"]), len(BESTIARY))
        self.assertEqual(len(result["jobs"]), len(JOBS) + 1)
        self.assertEqual(len(result["skills"]), len(SKILLS))
        self.assertEqual(len(result["equipment"]), len(EQUIPMENT))
        self.assertEqual(result, install_pack(result))
        Content.from_dict(result)

    def test_conflicts_are_rejected_without_replacing_existing_data(self):
        base = arena()
        base["archetypes"] = {"med_wolf": {"kind": "monster", "attack": 999}}
        before = deepcopy(base)
        with self.assertRaisesRegex(RuleError, "Conflicting medieval archetypes"):
            install_pack(base)
        self.assertEqual(before, base)
        packed = install_pack(arena())
        packed["skills"][0]["name"] = "Modifié par l'auteur"
        before = deepcopy(packed)
        with self.assertRaisesRegex(RuleError, "Conflicting medieval skills"):
            install_pack(packed)
        self.assertEqual(before, packed)

    def test_every_actor_and_skill_is_runtime_valid(self):
        packed = install_pack(arena())
        model = Content.from_dict(packed)
        for identifier in BESTIARY:
            key = archetype_id(identifier)
            self.assertIn(key, model.archetypes)
            self.assertTrue(all(skill in model.skills
                            for skill in model.archetypes[key]["skills"]))
        wolf = BESTIARY["wolf"]
        self.assertEqual(wolf["actor"]["kind"], "monster")
        self.assertEqual(BESTIARY["siege_troll"]["actor"]["footprint"], [2, 2])
        self.assertEqual(len(entries("Faune")), 4)
        self.assertEqual([e["tier"] for e in entries()],
                         sorted(e["tier"] for e in entries()))

    def test_placements_ranks_and_snapshot_stability(self):
        data = install_pack(arena())
        pos = find_free_cell(data, "field", "siege_troll")
        updated = place_entry(data, "field", "siege_troll", "troll", "enemy",
                              pos, rank="elite")
        actual = Content.from_dict(updated).missions["field"].units[-1]
        self.assertEqual(actual.footprint, (2, 2))
        self.assertEqual(actual.max_hp, 210 + 210 * 45 // 100)
        self.assertEqual(actual.hp, actual.max_hp)
        self.assertEqual(actual.attack, 22)
        self.assertIn("rank:elite", actual.tags)
        self.assertEqual(len(actual.occupied_cells()), 4)
        self.assertNotEqual(updated, data)
        with self.assertRaises(RuleError):
            place_entry(updated, "field", "wolf", "duplicate", "enemy", pos)
        with self.assertRaises(RuleError):
            place_entry(data, "field", "wolf", "w1", "enemy", [1, 1])
        with self.assertRaises(RuleError):
            place_entry(data, "field", "wolf", "w2", "enemy", [3, 3],
                        rank="legendary")
        self.assertEqual(Content.from_dict(data).missions["field"].units.__len__(), 2)

    def test_full_board_rejects_auto_position(self):
        data = install_pack(arena())
        data["missions"][0]["board"] = {"width": 2, "height": 1}
        data["missions"][0]["units"] = [
            {"id": "h", "name": "H", "team": "player", "pos": [0, 0]},
            {"id": "e", "name": "E", "team": "enemy", "pos": [1, 0]}]
        with self.assertRaisesRegex(RuleError, "No free location"):
            find_free_cell(data, "field", "wolf")

    def test_class_gates_talents_prepare_and_save_load(self):
        model = Content.from_dict(install_pack(arena()))
        campaign = Campaign(unlocked=["field"])
        with self.assertRaises(RuleError):
            campaign.set_job(model, "jeanne", "med_squire")
        campaign.set_job(model, "jeanne", "med_recruit")
        campaign.hero("jeanne").job_xp["med_recruit"] = 50
        campaign.set_job(model, "jeanne", "med_squire")
        campaign.hero("jeanne").job_xp["med_squire"] = 100
        campaign.set_job(model, "jeanne", "med_swordsman")
        campaign.hero("jeanne").job_xp["med_swordsman"] = 100
        before_jp = campaign.talent_catalog(model, "jeanne", "med_swordsman")
        self.assertEqual(before_jp["available_jp"], 2)
        campaign.learn_talent(model, "jeanne", "med_swordsman", "med_duel")
        self.assertEqual(campaign.talent_catalog(model, "jeanne",
                                                "med_swordsman")["available_jp"], 0)
        battle = campaign.prepare(model, "field")
        hero = battle.unit("jeanne")
        self.assertEqual(hero.attack, 10)
        self.assertIn("med_thrust", hero.skills)
        self.assertIn("med_sunder", hero.skills)
        self.assertNotIn("med_thrust", model.missions["field"].units[0].skills)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "slot.json"
            campaign.save(path)
            restored = Campaign.load(path)
            self.assertEqual(restored.hero("jeanne").job, "med_swordsman")
            self.assertEqual(restored.hero("jeanne").learned_talents,
                             {"med_swordsman": ["med_duel"]})
            self.assertEqual(restored.prepare(model, "field").unit("jeanne").attack, 10)

    def test_player_session_class_change_is_transactional(self):
        model = Content.from_dict(install_pack(arena()))
        project = GameProject.default(model)
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp) / "test.game.json"
            session = PlayerSession(model, project, profile)
            session.new_game("main", 1)
            self.assertEqual(session.set_job("jeanne", "med_recruit"), "med_recruit")
            self.assertEqual(session.progress.hero("jeanne").job, "med_recruit")
            with self.assertRaises(RuleError):
                session.set_job("jeanne", "med_knight")
            self.assertEqual(session.progress.hero("jeanne").job, "med_recruit")
            reloaded = PlayerSession(model, project, profile)
            reloaded.load_game("main", 1)
            self.assertEqual(reloaded.progress.hero("jeanne").job, "med_recruit")
            session.begin("field")
            with self.assertRaises(RuleError):
                session.set_job("jeanne", "med_archer")
            self.assertEqual(session.progress.hero("jeanne").job, "med_recruit")


if __name__ == "__main__":
    unittest.main()
