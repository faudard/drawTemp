"""Headless acceptance gates for Campaign & Siege Studio 2.5.4."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from examples.siege_scenarios import siege_content
from sporebound.fronts import MultiFrontSession
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound import siege_authoring as edit


class CampaignSiegeStudioTests(unittest.TestCase):
    def setUp(self):
        self.content = siege_content()
        self.project = GameProject.default(self.content)

    def blueprint(self):
        bp = edit.new_blueprint("castle", "main", "castle_ram", front="gate")
        bp = edit.add_front(bp, "walls", "castle_ramparts",
                            strength=7, opposition=12, doctrine="assault")
        return bp

    def test_project_roundtrip_and_old_game_projects_remain_compatible(self):
        old = self.project.to_dict()
        self.assertNotIn("sieges", old)
        self.assertEqual(GameProject.from_dict(old, self.content).sieges, [])
        bp = self.blueprint()
        self.project = edit.replace_siege(self.project, self.content, bp)
        serialized = self.project.to_dict()
        self.assertEqual(serialized["sieges"], [bp])
        with TemporaryDirectory() as temp:
            file = Path(temp) / "castle.game.json"
            self.project.save(file, self.content)
            read = GameProject.load(file, self.content)
            self.assertEqual(read.sieges, [bp])
            self.assertEqual(read.campaign("main")["start_mission"],
                             self.project.campaign("main")["start_mission"])
        self.assertEqual(edit.delete_siege(self.project, self.content, "castle").sieges, [])

    def test_front_editing_is_transactional_and_validated(self):
        original = self.blueprint()
        project = edit.replace_siege(self.project, self.content, original)
        with self.assertRaises(RuleError):
            edit.replace_siege(project, self.content,
                               edit.add_front(original, "unknown", "not_a_mission"))
        with self.assertRaises(RuleError):
            edit.replace_siege(project, self.content,
                               edit.add_front(original, "gate", "castle_ram"))
        with self.assertRaises(RuleError):
            edit.replace_siege(project, self.content,
                               {**original, "focused": "unknown"})
        with self.assertRaises(RuleError):
            edit.replace_siege(project, self.content,
                               {**original, "specs": {**original["specs"],
                                    "gate": {"strength": -5, "opposition": 4,
                                             "doctrine": "hold"}}})
        self.assertEqual(project.sieges[0], original)

    def test_finale_requires_tactical_front_and_cannot_auto_win(self):
        bp = edit.set_finale(self.blueprint(), "walls",
                              {"gate": ["victory"]})
        project = edit.replace_siege(self.project, self.content, bp)
        self.assertEqual(project.sieges[0]["campaign"]["final_front"], "walls")
        session = edit.make_session(bp, self.content)
        self.assertIsInstance(session, MultiFrontSession)
        with self.assertRaises(RuleError):
            session.switch("walls")
        for _ in range(15):
            session.advance()
        self.assertEqual(session.timeline.fronts["walls"]["status"], "active")
        self.assertFalse(session.state()["campaign"]["unlocked"])
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())
        with self.assertRaises(RuleError):
            edit.replace_siege(project, self.content, {**bp, "focused": "walls"})
        # Preview never mutates the blueprint or creates a tactical win.
        before = deepcopy(bp)
        projection = edit.timeline_preview(bp, turns=3)
        self.assertEqual(len(projection), 4)
        self.assertEqual(projection[-1]["fronts"]["walls"]["status"], "active")
        self.assertEqual(bp, before)

    def test_front_event_link_is_real_engine_contract(self):
        bp = self.blueprint()
        link = {"id": "raise_herse", "source": "walls", "event": "interact",
                "match": {"object": "portcullis_lever"},
                "effects": [{"kind": "open_door", "front": "gate",
                             "object": "main_gate"}]}
        bp = edit.upsert_link(bp, link)
        edit.validate_blueprint(bp, self.content, {"main"})
        session = edit.make_session(bp, self.content)
        self.assertEqual(session.links, [link])
        invalid = deepcopy(link)
        invalid["effects"][0]["object"] = "not_a_gate"
        with self.assertRaises(RuleError):
            edit.replace_siege(self.project, self.content,
                               edit.upsert_link(bp, invalid))
        self.assertEqual(len(edit.remove_link(bp, link["id"])["links"]), 0)
        with self.assertRaises(RuleError):
            edit.remove_front(bp, "gate")

    def test_wave_authoring_uses_mission_trigger_and_rejects_duplicates(self):
        from sporebound.actor_catalog import create_archetype
        data = self.content.to_dict()
        # Same validated archetype creation API as the Character Studio.
        data = create_archetype(data, "guard_wave", kind="monster",
                                max_hp=20, attack=4, speed=8, move=3)
        before = deepcopy(data)
        updated = edit.add_wave(data, "castle_ram", "reinforcements_t3", 3,
                                "enemy_backup", "guard_wave", [10, 5])
        content = Content.from_dict(updated)
        bp = self.blueprint()
        self.assertIn(("gate", "reinforcements_t3", 3, "enemy_backup", "guard_wave"),
                      edit.waves_for(content, bp["fronts"]))
        with self.assertRaises(RuleError):
            edit.add_wave(data, "castle_ram", "invalid", -1,
                          "bad", "guard_wave", [1, 1])
        with self.assertRaises(RuleError):
            edit.add_wave(data, "castle_ram", "invalid", 3,
                          "bad", "missing_arch", [1, 1])
        restored = edit.remove_wave(updated, "castle_ram", "reinforcements_t3")
        self.assertFalse(edit.waves_for(Content.from_dict(restored), bp["fronts"]))
        self.assertEqual(data, before)

    def test_save_slot_is_replayable_and_rejects_wrong_siege(self):
        bp = self.blueprint()
        self.project = edit.replace_siege(self.project, self.content, bp)
        session = edit.make_session(bp, self.content, seed=7)
        session.advance()
        with TemporaryDirectory() as temp:
            path = Path(temp) / "test.game.json"
            slot = edit.save_siege_slot(path, bp, 1, session)
            self.assertTrue(slot.exists())
            saved = json.loads(slot.read_text(encoding="utf-8"))
            self.assertEqual(saved["siege_id"], "castle")
            read = edit.load_siege_slot(path, bp, 1, self.content)
            self.assertEqual(read.digest(), session.digest())
            changed = deepcopy(bp)
            changed["specs"]["walls"]["opposition"] = 11
            with self.assertRaises(RuleError):
                edit.load_siege_slot(path, changed, 1, self.content)
            with self.assertRaises(RuleError):
                edit.save_siege_slot(path, changed, 1, session)
            with self.assertRaises(RuleError):
                edit.save_siege_slot(path, bp, 0, session)


if __name__ == "__main__":
    unittest.main()
