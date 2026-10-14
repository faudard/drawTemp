"""R6.6B integration: live terrain, arrived waves, multi-CT area casts."""
import unittest

from sporebound.ai import choose_command
from sporebound.boss_encounter_r6b import (
    arrived_reinforcements, reinforcement_pressure, telegraphed_cast_command)
from sporebound.elite_boss_r6 import boss_r6_telegraph
from sporebound.engine import Battle
from sporebound.model import Content, Effect, Skill, Tile
from sporebound.tactical_intents import tactical_intents
from sporebound.tactical_r6 import tactical_r6_rules
from tests_standalone.test_elite_boss_r6 import encounter


def advance_to(battle, predicate, *, limit=36):
    """Drive only real End commands, keeping the recording replayable."""
    for _ in range(limit):
        if predicate():
            return
        if battle.result:
            break
        battle.execute({"kind": "end"})
    raise AssertionError("Required encounter state was not reached")


class BossEncounterR6BTests(unittest.TestCase):
    def test_real_cast_announced_across_ticks_then_dodged_with_replay(self):
        content = encounter(hero=(5, 3), boss=(1, 3),
                            footprint=(1, 1), phase=2)
        content.skills["quake"] = Skill(
            "quake", "Quake", [Effect("damage", 22)],
            target="ground", range=5, radius=1,
            cast_ticks=30, lock="cell")
        content.missions["throne"].units[1].skills = ["quake"]
        rules = tactical_r6_rules()
        battle = Battle(content, "throne", seed=17, rules=rules)
        battle.active_id = "warden"
        battle.unit("warden").ct = 100
        before = battle.digest()
        planned = telegraphed_cast_command(battle, battle.unit("warden"))
        self.assertEqual(planned, {"kind": "act", "skill": "quake",
                                   "cell": [5, 3]})
        self.assertEqual(choose_command(battle), planned)
        self.assertEqual(battle.digest(), before)
        battle.execute(planned)
        self.assertEqual(battle.unit("warden").cast["remaining"], 30)
        view = boss_r6_telegraph(battle, "warden")
        self.assertEqual(view["cast"]["certainty"], "scheduled")
        self.assertIn([5, 3], view["cast"]["cells"])
        self.assertEqual(view["cast"]["remaining_ticks"], 30)
        self.assertEqual(tactical_intents(battle)["casts"][0]["certainty"],
                         "scheduled")
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())

        # The target can escape a cell-locked telegraph during the real CT
        # countdown; the skill does not magically retarget or hit it later.
        advance_to(battle, lambda: battle.active_id == "hero")
        self.assertIn((7, 5), battle.reachable(battle.unit("hero")))
        battle.execute({"kind": "move", "cell": [7, 5]})
        battle.execute({"kind": "end"})
        advance_to(battle, lambda: battle.unit("warden").cast is None, limit=35)
        self.assertEqual(battle.unit("hero").hp, 40)
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())

    def test_live_hazard_trigger_changes_boss_path_without_new_schema(self):
        content = encounter(hero=(6, 3), boss=(1, 1), phase=2,
                            triggers=[{
                                "id": "burning_passage", "condition": "tick",
                                "value": 10, "actions": [{
                                    "kind": "hazard", "pos": [3, 1],
                                    "amount": 1000}]}])
        rules = tactical_r6_rules()
        battle = Battle(content, "throne", seed=4, rules=rules)
        self.assertEqual(battle.board.tile((3, 1)).hazard, 0)
        advance_to(battle, lambda: (
            battle.board.tile((3, 1)).hazard == 1000
            and battle.active_id == "warden"))
        self.assertIn("burning_passage", battle.fired)
        prior = battle.digest()
        command = choose_command(battle)
        self.assertEqual(battle.digest(), prior)
        if command["kind"] == "move":
            destination = tuple(command["cell"])
            _, path = battle.reachable(battle.active)[destination]
            # The entire 2x2 footprint is checked at each step.
            self.assertFalse(any(
                battle.board.tile(cell).hazard for anchor in path[1:]
                for cell in battle.active.occupied_cells(anchor)))
        battle.execute(command)
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())

    def test_arrived_wave_influences_support_but_queued_wave_cannot(self):
        soldier = {"id": "reserve", "name": "Reserve", "team": "enemy",
                   "pos": [5, 3], "attack": 6, "weapon": "melee"}
        content = encounter(hero=(6, 3), boss=(1, 1), footprint=(1, 1),
                            phase=2, triggers=[{
                                "id": "call_reinforcement", "condition": "tick",
                                "value": 10,
                                "actions": [{"kind": "queue_wave",
                                             "actors": [soldier]}]}])
        rules = tactical_r6_rules()
        battle = Battle(content, "throne", seed=6, rules=rules)
        boss = battle.unit("warden")
        hero = battle.unit("hero")
        self.assertEqual(arrived_reinforcements(battle, boss), [])
        self.assertEqual(reinforcement_pressure(
            battle, boss, (4, 3), hero), 0)
        advance_to(battle, lambda: (
            any(u.id == "reserve" for u in battle.units)
            and battle.active_id == "warden"))
        self.assertIn("call_reinforcement", battle.fired)
        allies = arrived_reinforcements(battle, boss)
        self.assertEqual([unit.id for unit in allies], ["reserve"])
        self.assertEqual(reinforcement_pressure(
            battle, boss, (4, 3), hero), 1)
        view = boss_r6_telegraph(battle, "warden")
        self.assertEqual(view["arrived_reinforcements"], [{
            "unit": "reserve", "cell": [5, 3], "certainty": "observed"}])
        before = battle.digest()
        command = choose_command(battle)
        self.assertEqual(battle.digest(), before)
        battle.execute(command)
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())


if __name__ == "__main__":
    unittest.main()
