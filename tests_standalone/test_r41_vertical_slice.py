"""R41.C VS-41 — create, recruit, travel, fight twice, claim, save and replay.

All player operations use real Simulation/GameSession. No fabricated state
changes, sidecar rewards or dependency on Jeanne's authored campaign.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from drawtemp.creator_examples.classic_rpg import build_relais_du_village
from drawtemp.export.templates import TEMPLATES, create_template
from drawtemp.player.controller import PlayerController
from drawtemp.sdk.simulation import SimulationError
from sporebound.classic_party import EXTENSION
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import Content, RuleError


def _defeat_enemy(player, enemy):
    for turn in range(24):
        state = player.state()["rpg"]
        if state["result"]:
            break
        player.rpg_action("attack", enemy)
    assert player.state()["rpg"]["result"] == "victory", player.state()["rpg"]


class VillageRelaySliceTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = build_relais_du_village()

    def test_original_template_is_usable_and_ct_mission_untouched(self):
        self.assertEqual(self.project.title, "Le relais du village")
        self.assertEqual(set(self.project.exploration),
                         {"village", "woods", "crypt"})
        self.assertEqual(len(self.project.extensions[EXTENSION]["data"][
            "campaigns"]["main"]["recruitable"]), 3)
        self.assertEqual(set(self.project.extensions[EXTENSION]["data"][
            "encounters"]), {"woods", "crypt"})
        self.assertTrue(all(self.project.scene_profile(mid)["combat"] == "TACTICAL_CT"
                            for mid in self.content.missions)
                        if hasattr(self.project, "scene_profile") else all(
            self.project.game_modes["scenes"][mid]["preset"] == "srpg"
            for mid in self.content.missions))
        self.assertEqual(GameProject.from_dict(
            json.loads(json.dumps(self.project.to_dict())),
            self.content).to_dict(), self.project.to_dict())
        self.assertEqual(Content.from_dict(
            json.loads(json.dumps(self.content.to_dict()))).to_dict(),
            self.content.to_dict())

    def test_registered_creator_template_is_atomic_two_file_project(self):
        self.assertIn("classic_rpg", TEMPLATES)
        with TemporaryDirectory() as directory:
            target = Path(directory) / "village-rpg"
            self.assertEqual(create_template("classic_rpg", target), target)
            raw = target / "game.json"
            authored = target / "game.game.json"
            self.assertTrue(raw.is_file())
            self.assertTrue(authored.is_file())
            content = Content.load(raw)
            project = GameProject.load(authored, content)
            self.assertEqual(project.to_dict(), self.project.to_dict())
            session = GameSession.new(content, project, "main")
            self.assertEqual(session.route_scene, "village")
            self.assertEqual(session.rpg_available(), [])
            with self.assertRaises(ValueError):
                create_template("classic_rpg", target)

    def test_three_heroes_two_fights_return_and_exactly_once_quest(self):
        with TemporaryDirectory() as directory:
            player = PlayerController(
                self.content, self.project, "main", Path(directory), seed=37)
            state = player.new_game()
            self.assertEqual(state["screen"], "exploration")
            self.assertEqual(len(state["party"]["recruitable"]), 2)
            self.assertEqual(state["party"]["active"], ["elya"])
            self.assertEqual(state["route_links"][0]["id"], "village_to_woods")
            with self.assertRaises(Exception):
                player.claim_rpg_quest()
            with self.assertRaises(ValueError):
                player.travel_route("woods_to_crypt")
            self.assertIn("lame_relais", {
                item["id"] for item in state["gear"]["inventory"]})
            with self.assertRaises(Exception):
                player.equip_hero("oren", "lame_relais")
            player.recruit_party_member("oren")
            player.recruit_party_member("mira")
            self.assertEqual(len(player.state()["party"]["recruitable"]), 0)
            player.toggle_party_member("oren")
            player.toggle_party_member("mira")
            self.assertEqual(set(player.state()["party"]["active"]),
                             {"elya", "oren", "mira"})
            player.equip_hero("elya", "lame_relais")
            player.equip_hero("mira", "cape_relais")
            self.assertEqual(player.state()["party"]["equipment"]["elya"][
                "weapon"], "lame_relais")
            self.assertEqual(player.state()["party"]["equipment"]["mira"][
                "armor"], "cape_relais")
            player.save(1)
            player.travel_route("village_to_woods")
            self.assertEqual(player.state()["exploration"]["scene_id"], "woods")
            self.assertEqual(player.state()["rpg_available"], ["woods"])
            with self.assertRaises(ValueError):
                player.travel_route("woods_to_crypt")
            player.start_rpg_encounter("woods")
            actors = {a["id"]: a for a in player.state()["rpg"]["actors"]}
            self.assertEqual(actors["elya"]["attack"], 15)
            self.assertEqual(actors["mira"]["max_hp"], 64)
            _defeat_enemy(player, "loup")
            player.finish_rpg_encounter()
            self.assertIn("woods_to_crypt", [
                x["id"] for x in player.state()["route_links"]])
            self.assertEqual(player.state()["rpg_quest"]["cleared"], ["woods"])
            player.save(2)
            player.travel_route("woods_to_crypt")
            self.assertEqual(player.state()["rpg_available"], ["crypt"])
            player.start_rpg_encounter("crypt")
            _defeat_enemy(player, "gardien")
            player.finish_rpg_encounter()
            self.assertFalse(player.state()["rpg_quest"]["ready"])
            player.travel_route("crypt_to_village")
            self.assertTrue(player.state()["rpg_quest"]["ready"])
            self.assertEqual(player.state()["rpg_quest"]["cleared"],
                             ["woods", "crypt"])
            self.assertEqual(player.state()["rpg_available"], [])
            progress_before = player.session.snapshot().progress
            self.assertEqual(progress_before["gold"], 36)
            player.claim_rpg_quest()
            progress = player.session.snapshot().progress
            self.assertEqual(progress["gold"], 61)
            self.assertEqual(progress["inventory"]["potion"], 3)
            self.assertEqual(progress["heroes"]["elya"]["xp"], 100)
            self.assertEqual(progress["heroes"]["mira"]["xp"], 100)
            self.assertTrue(player.state()["rpg_quest"]["completed"])
            with self.assertRaises(Exception):
                player.claim_rpg_quest()
            self.assertEqual(player.session.snapshot().progress, progress)
            player.save(3)
            restored = PlayerController(
                self.content, self.project, "main", Path(directory), seed=37)
            restored.load(3)
            self.assertEqual(restored.state()["screen"], "exploration")
            self.assertEqual(restored.state()["rpg_quest"], player.state()["rpg_quest"])
            self.assertEqual(restored.session.snapshot().progress, progress)
            self.assertEqual(restored.state()["party"], player.state()["party"])
            self.assertEqual(restored.state()["rpg_available"], [])
            self.assertEqual(restored.state()["exploration"]["scene_id"], "village")

    def test_invalid_quest_and_starter_inventory_fail_closed(self):
        for change in (
            lambda data: data["starting_inventory"].update(potion=True),
            lambda data: data["starting_inventory"].update(unknown_item=1),
            lambda data: data["quest"].update(encounters=["woods", "woods"]),
            lambda data: data["quest"].update(encounters=[["woods"]]),
            lambda data: data["quest"].update(return_scene="missing"),
            lambda data: data["quest"].update(reward_gold=True),
            lambda data: data["quest"].update(reward_quantity=-1),
        ):
            project = deepcopy(self.project)
            change(project.extensions[EXTENSION]["data"])
            with self.subTest(change=change), self.assertRaises(RuleError):
                project.validate(self.content)

    def test_equipment_is_replayed_from_campaign_not_save_actor_cache(self):
        session = GameSession.new(self.content, self.project, "main", seed=15)
        session.equip_hero("elya", "lame_relais")
        session.route_transition("village_to_woods")
        session.rpg_start("woods")
        checkpoint = session.recording()
        actor = next(row for row in checkpoint["rpg_encounter"]["view"]["actors"]
                     if row["id"] == "elya")
        self.assertEqual(actor["attack"], 15)
        loaded = GameSession.from_recording(
            checkpoint, self.content, self.project)
        self.assertEqual(loaded.rpg_state(), session.rpg_state())
        forged = deepcopy(checkpoint)
        forged["progress"]["heroes"]["elya"]["equipment"] = {}
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, self.content, self.project)

    def test_checkpoint_rejects_invented_quest_claim_or_combat_gate(self):
        session = GameSession.new(self.content, self.project, "main")
        before = session.recording()
        with self.assertRaises(RuleError):
            session.rpg_claim_quest()
        self.assertEqual(session.recording(), before)
        invalid = deepcopy(before)
        invalid["progress"]["story_flags"]["r41_crypt"] = "yes"
        invalid["digest"] = digest({k: v for k, v in invalid.items()
                                    if k != "digest"})
        # A non-boolean string cannot satisfy the typed R9 flag condition.
        restored = GameSession.from_recording(invalid, self.content, self.project)
        self.assertFalse(restored.rpg_quest_state()["ready"])
        self.assertEqual(restored.rpg_available(), [])


if __name__ == "__main__":
    unittest.main()
