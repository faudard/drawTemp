"""R62.C: real PlayerController farm→harvest→R55 sale→R35 NPC social loop.

Uses the actual Simulation, Campaign, autosave, slot store and project fixture.
The test seeds inventory explicitly as its scenario setup; gameplay never
hands out free inventory and the production Player does not bypass the rules.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.simulation import SimulationError
from sporebound.system_design import EXTENSION as SYSTEMS_EXTENSION
from sporebound.relationship_life import EXTENSION as SOCIAL_EXTENSION
from tests_standalone.test_r62_farming_life import fixture as farm_fixture
from tests_standalone.test_r62_relationship_life import social_spec
from tests_standalone.test_r25_scene_router import scene_fixture


def village_fixture():
    content, project = farm_fixture()
    project.extensions[SOCIAL_EXTENSION] = {
        "schema_version": 1, "data": social_spec(), "references": []}
    project.extensions[SYSTEMS_EXTENSION] = {
        "schema_version": 1, "references": [],
        "data": {
            "version": 1,
            "resources": [{"id": "cape_de_route", "initial": 0, "capacity": 10}],
            "producers": [],
            "merchants": [{"id": "trader", "resource": "cape_de_route",
                           "scene": "arrival", "buy_price": 8, "sell_price": 4}],
            "quests": [],
        },
    }
    project.validate(content)
    return content, project


class R62VillagePlayerTests(unittest.TestCase):
    def make_player(self, content, project, directory):
        return PlayerController(content, project, "main", Path(directory), seed=62)

    def test_full_canonical_village_loop_save_load_and_receipt_idempotence(self):
        content, project = village_fixture()
        with TemporaryDirectory() as folder:
            player = self.make_player(content, project, folder)
            initial = player.new_game()
            self.assertEqual(initial["screen"], "exploration")
            self.assertTrue(initial["village"]["enabled"])
            self.assertEqual(initial["village"]["day"], 0)
            self.assertEqual(initial["village"]["season"], "spring")
            self.assertEqual(initial["village"]["plots"][0]["id"], "field")
            self.assertFalse(initial["village"]["plots"][0]["crops"][0]["available"])
            before = player.session.recording()
            for _ in range(3):
                self.assertEqual(player.state()["village"], initial["village"])
            self.assertEqual(player.session.recording(), before)
            with self.assertRaises(SimulationError):
                player.farm_plant("field", "herb_crop")
            self.assertEqual(player.session.recording(), before)
            # Explicit scenario grant (not a production command); subsequent
            # actions transfer only this canonical Campaign inventory.
            player.session._session.progress.inventory["epee_de_jacques"] = 2
            refreshed = player.state()
            self.assertTrue(refreshed["village"]["plots"][0]["crops"][0]["available"])
            player.farm_plant("field", "herb_crop")
            self.assertEqual(player.session.snapshot().progress["inventory"]
                             ["epee_de_jacques"], 1)
            with self.assertRaises(SimulationError):
                player.farm_harvest("field")
            planted = player.state()["village"]["plots"][0]
            self.assertEqual(planted["crop"], "herb_crop")
            self.assertFalse(planted["can_harvest"])
            with self.assertRaises(ValueError):
                player.farm_wait_day(True)
            player.farm_wait_day(1)
            ready = player.state()["village"]
            self.assertEqual(ready["day"], 1)
            self.assertTrue(ready["plots"][0]["can_harvest"])
            player.farm_harvest("field")
            self.assertEqual(player.session.snapshot().progress["inventory"]
                             ["cape_de_route"], 2)
            player.session._session.progress.story_flags["market_open"] = True
            player.world_wait(480 * 2)
            self.assertTrue(next(p for p in player.state()["village"]["people"]
                                 if p["id"] == "merchant")["can_talk"])
            player.system_trade("trader", "sell", 1)
            self.assertEqual(player.session.snapshot().progress["gold"], 4)
            merchant = next(p for p in player.state()["village"]["people"]
                            if p["id"] == "merchant")
            self.assertEqual(merchant["gifts"][1]["owned"], 1)
            player.relationship_gift("merchant", "cape_de_route")
            self.assertEqual(player.session.snapshot().progress["inventory"]
                             ["cape_de_route"], 0)
            self.assertEqual(next(p for p in player.state()["village"]["people"]
                                  if p["id"] == "merchant")["score"], 1)
            player.relationship_talk("merchant")
            self.assertEqual(next(p for p in player.state()["village"]["people"]
                                  if p["id"] == "merchant")["score"], 4)
            self.assertFalse(next(p for p in player.state()["village"]["people"]
                                  if p["id"] == "merchant")["can_talk"])
            journal = player.session.recording()
            self.assertEqual(len(journal["farming"]["journal"]), 2)
            self.assertEqual(len(journal["relationships"]["journal"]), 2)
            self.assertEqual(len(journal["systems"]["journal"]), 1)
            player.save(1)
            resumed = self.make_player(content, project, folder)
            load_state = resumed.load(1)
            self.assertEqual(load_state["village"], player.state()["village"])
            self.assertEqual(resumed.session.recording(), player.session.recording())
            before_retry = resumed.session.recording()
            resumed.relationship_gift("merchant", "cape_de_route",
                                      receipt_id="r62-social-0")
            resumed.farm_harvest("field", receipt_id="r62-farm-1")
            after_retry = resumed.session.recording()
            self.assertEqual(after_retry["progress"]["inventory"],
                             before_retry["progress"]["inventory"])
            self.assertEqual(after_retry["relationships"], before_retry["relationships"])
            self.assertEqual(after_retry["farming"], before_retry["farming"])
            self.assertEqual(after_retry["systems"], before_retry["systems"])

    def test_disabled_legacy_and_rejected_action_never_touch_save(self):
        content, project = scene_fixture()
        with TemporaryDirectory() as folder:
            player = self.make_player(content, project, folder)
            self.assertFalse(player.new_game()["village"]["enabled"])
            before = player.session.recording()
            for operation in (
                lambda: player.farm_plant("field", "herb_crop"),
                lambda: player.relationship_talk("merchant"),
                lambda: player.farm_wait_day(1),
            ):
                with self.assertRaises(ValueError):
                    operation()
                self.assertEqual(before, player.session.recording())

    def test_calendar_carries_social_cooldown_off_focus_without_shadow_state(self):
        content, project = village_fixture()
        with TemporaryDirectory() as folder:
            player = self.make_player(content, project, folder)
            player.new_game()
            player.relationship_talk("traveler")
            people = {p["id"]: p for p in player.state()["village"]["people"]}
            self.assertTrue(people["traveler"]["talked_today"])
            player.farm_wait_day(1)
            people = {p["id"]: p for p in player.state()["village"]["people"]}
            self.assertFalse(people["traveler"]["talked_today"])
            self.assertEqual(player.session.recording()["relationships"]["day"], 1)
            self.assertEqual(player.session.recording()["farming"]["day"], 1)
            self.assertEqual(player.session.recording()["living_world"]["ticks"],
                             (1440 - 479) * 2)


if __name__ == "__main__":
    unittest.main()
