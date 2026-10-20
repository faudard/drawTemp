"""R62.A regression: opt-in deterministic farms, daily replay and atomic inventory."""
from copy import deepcopy
import unittest

from drawtemp.sdk.simulation import Simulation, SimulationError
from sporebound.farming_life import (
    EXTENSION, FarmingLife, validate_farming,
)
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r35_commerce import merchant_fixture


def farm_spec():
    return {
        "version": 1, "seed": 62, "season_days": 3, "weather": True,
        "plots": [
            {"id": "field", "scene": "arrival", "soil": "loam"},
        ],
        "crops": [
            {"id": "herb_crop", "seed_item": "epee_de_jacques", "yield_item": "cape_de_route",
             "yield_quantity": 2, "grow_days": 1,
             "soils": ["loam"], "seasons": ["spring"]},
        ],
        "animals": [
            {"id": "hen", "scene": "arrival", "feed_item": "epee_de_jacques",
             "yield_item": "cape_de_route", "yield_quantity": 1, "interval_days": 1},
        ],
    }


def fixture():
    content, project = merchant_fixture()
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": farm_spec(), "references": []}
    project.validate(content)
    return content, project


def next_day(session):
    clock = session._living_world
    ticks = (1440 - clock.minute) * clock.spec["ticks_per_minute"]
    session.living_world_advance(ticks)


class R62FarmingLifeTests(unittest.TestCase):
    def test_schema_validation_and_optin_dependency(self):
        content, project = fixture()
        known = set(content.equipment)
        self.assertEqual(validate_farming(farm_spec(), {"arrival"}, known), farm_spec())
        variants = (
            lambda spec: spec.update(weather=1),
            lambda spec: spec["plots"].append(deepcopy(spec["plots"][0])),
            lambda spec: spec["crops"][0].update(grow_days=True),
            lambda spec: spec["crops"][0].update(seed_item="nonexistent"),
            lambda spec: spec["crops"][0].update(soils=[{}]),
            lambda spec: spec["animals"][0].update(interval_days=0),
            lambda spec: spec["animals"][0].update(scene="missing"),
            lambda spec: spec.update(version=2),
        )
        for mutate in variants:
            modified = deepcopy(farm_spec())
            mutate(modified)
            with self.subTest(modified=modified), self.assertRaises(RuleError):
                validate_farming(modified, {"arrival"}, known)
        from sporebound.living_world import EXTENSION as CLOCK_EXTENSION
        del project.extensions[CLOCK_EXTENSION]
        with self.assertRaises(RuleError):
            project.validate(content)

    def test_season_weather_and_off_focus_calendar(self):
        content, project = fixture()
        farm = FarmingLife(farm_spec(), set(project.exploration), set(content.equipment))
        weather = [farm.weather(day) for day in range(12)]
        self.assertEqual(weather, [farm.weather(day) for day in range(12)])
        self.assertEqual(farm.view()["season"], "spring")
        farm.sync(3)
        self.assertEqual(farm.view()["season"], "summer")
        farm.sync(12)
        self.assertEqual(farm.view()["season"], "spring")
        with self.assertRaises(RuleError):
            farm.sync(11)
        with self.assertRaises(RuleError):
            farm.view(scene="not_a_scene")
        disabled = farm_spec()
        disabled["weather"] = False
        self.assertIsNone(FarmingLife(disabled, set(project.exploration),
                                      set(content.equipment)).weather())

    def test_plant_harvest_animal_and_reload_never_duplicate(self):
        content, project = fixture()
        s = GameSession.new(content, project, "main", seed=62)
        s.progress.inventory["epee_de_jacques"] = 3
        initial = s.recording()
        self.assertEqual(s.farming_state()["day"], 0)
        self.assertTrue(s.farming_plant("field", "herb_crop", "sow-1"))
        self.assertEqual(s.progress.inventory["epee_de_jacques"], 2)
        self.assertFalse(s.farming_plant("field", "herb_crop", "sow-1"))
        with self.assertRaises(RuleError):
            s.farming_harvest("field", "early")
        self.assertTrue(s.farming_feed("hen", "feed-0"))
        with self.assertRaises(RuleError):
            s.farming_feed("hen", "feed-again")
        next_day(s)
        self.assertEqual(s.farming_state()["day"], 1)
        self.assertTrue(s.farming_state()["plots"]["field"]["ready"])
        self.assertTrue(s.farming_harvest("field", "harvest-1"))
        self.assertEqual(s.progress.inventory["cape_de_route"], 2)
        self.assertFalse(s.farming_harvest("field", "harvest-1"))
        self.assertTrue(s.farming_collect("hen", "collect-1"))
        self.assertEqual(s.progress.inventory["cape_de_route"], 3)
        with self.assertRaises(RuleError):
            s.farming_collect("hen", "collect-twice")
        recorded = s.recording()
        restored = GameSession.from_recording(recorded, content, project)
        self.assertEqual(restored.recording(), recorded)
        self.assertEqual(restored.farming_state(), s.farming_state())
        self.assertFalse(restored.farming_collect("hen", "collect-1"))
        self.assertFalse(restored.farming_harvest("field", "harvest-1"))
        self.assertEqual(restored.recording(), recorded)
        self.assertEqual(initial["farming"]["day"], 0)
        self.assertEqual(initial["farming"]["journal"], [])
        next_day(restored)
        self.assertFalse(restored.farming_harvest("field", "harvest-1"))
        self.assertFalse(restored.farming_collect("hen", "collect-1"))

    def test_canonical_r55_sale_of_harvested_goods(self):
        from sporebound.system_design import EXTENSION as SYSTEMS_EXTENSION
        content, project = fixture()
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
        session = GameSession.new(content, project, "main", seed=62)
        session.progress.inventory["epee_de_jacques"] = 1
        session.progress.gold = 0
        self.assertTrue(session.farming_plant("field", "herb_crop", "seed-sale"))
        next_day(session)
        self.assertTrue(session.farming_harvest("field", "harvest-sale"))
        self.assertEqual(session.progress.inventory["cape_de_route"], 2)
        self.assertTrue(session.system_trade("trader", "sell", 1, "sale-r62"))
        self.assertEqual(session.progress.inventory["cape_de_route"], 1)
        self.assertEqual(session.system_state()["stocks"]["cape_de_route"], 1)
        self.assertEqual(session.progress.gold, 4)
        restored = GameSession.from_recording(session.recording(), content, project)
        self.assertFalse(restored.system_trade("trader", "sell", 1, "sale-r62"))
        self.assertFalse(restored.farming_harvest("field", "harvest-sale"))
        self.assertEqual(restored.recording(), session.recording())

    def test_failed_commands_are_atomic_and_fail_closed_on_tamper(self):
        content, project = fixture()
        s = GameSession.new(content, project, "main")
        checkpoint = s.recording()
        for call in (
            lambda: s.farming_plant("field", "herb_crop", "no_seed"),
            lambda: s.farming_plant("field", "unknown", "bad_crop"),
            lambda: s.farming_feed("missing", "bad_target"),
            lambda: s.farming_feed("hen", ""),
            lambda: s.farming_harvest("field", "empty"),
        ):
            with self.assertRaises(RuleError):
                call()
            self.assertEqual(s.recording(), checkpoint)
        s.progress.inventory["epee_de_jacques"] = 2
        s.farming_plant("field", "herb_crop", "sow")
        next_day(s)
        s.farming_harvest("field", "harvest")
        original = s.recording()
        for mutate in (
            lambda x: x["farming"]["plots"].update(
                field={"crop": "herb_crop", "day": 0}),
            lambda x: x["farming"]["journal"][0].update(day=30),
            lambda x: x["farming"]["journal"].append(
                deepcopy(x["farming"]["journal"][0])),
            lambda x: x["farming"].update(day=8),
        ):
            forged = deepcopy(original)
            mutate(forged)
            forged["digest"] = digest({k: v for k, v in forged.items()
                                       if k != "digest"})
            with self.subTest(forged=forged["farming"]), self.assertRaises(RuleError):
                GameSession.from_recording(forged, content, project)
        self.assertEqual(s.recording(), original)

    def test_sdk_revision_and_legacy_save_shape(self):
        content, project = fixture()
        s = GameSession.new(content, project, "main")
        s.progress.inventory["epee_de_jacques"] = 1
        sdk = Simulation(s)
        view = sdk.farming_state()
        self.assertEqual(view["season"], "spring")
        with self.assertRaises(TypeError):
            view["plots"]["field"]["crop"] = "forged"
        transition = sdk.farming_plant("field", "herb_crop", "sdk-plant",
                                       expected_revision=0)
        self.assertEqual(transition.snapshot.revision, 1)
        with self.assertRaises(SimulationError) as error:
            sdk.farming_harvest("field", "early", expected_revision=0)
        self.assertEqual(error.exception.code, "stale_revision")
        self.assertEqual(sdk.snapshot().revision, 1)
        legacy_content, legacy_project = merchant_fixture()
        legacy = GameSession.new(legacy_content, legacy_project, "main")
        self.assertNotIn("farming", legacy.recording())
        self.assertEqual(GameSession.from_recording(
            legacy.recording(), legacy_content, legacy_project).recording(),
            legacy.recording())


if __name__ == "__main__":
    unittest.main()
