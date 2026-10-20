"""R43.B3 native CT target preview must match real Battle and mutate nothing."""
from copy import deepcopy
import unittest

from drawtemp.sdk.ability_contracts import AbilityError
from drawtemp.sdk.ability_targeting_r43 import native_target_preview
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.ability_authoring_r43 import new_ability
from drawtemp.render.iso_scene import (
    Camera, IsoProjection, TopDownProjection, scene_from_mission, pick,
)


class R43NativeTargetTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)
        self.mission = self.content.missions[MISSION]
        self.caster = next(unit for unit in self.mission.units
                           if unit.id == "jeanne")
        self.ability = new_ability("r43_trial")

    def test_self_target_uses_native_footprint_and_keeps_project_unchanged(self):
        before = self.session.snapshot().to_dict()
        spec = deepcopy(self.ability)
        spec["target"].update(team="self", range=0)
        result = native_target_preview(self.session, spec, MISSION,
                                       self.caster.id, self.caster.pos)
        self.assertTrue(result["legal"], result["rejection"])
        self.assertEqual(result["origin"], list(self.caster.pos))
        self.assertIn(list(self.caster.pos), result["available"])
        self.assertEqual(result["area"], [list(self.caster.pos)])
        self.assertTrue(any(row["unit"] == self.caster.id
                            for row in result["recipients"]))
        self.assertEqual(self.session.snapshot().to_dict(), before)
        self.assertEqual(self.session.revision, 0)

    def test_native_enemy_allies_and_radius_sides(self):
        enemies = [actor for actor in self.mission.units
                   if actor.alive and actor.team != self.caster.team
                   and self.mission.unit_levels.get(actor.id, 0) == 0]
        if not enemies:
            self.skipTest("Reference fixture has no ground enemy")
        enemy = enemies[0]
        spec = deepcopy(self.ability)
        spec["target"].update(range=16, shape="diamond", radius=1)
        aim = tuple(enemy.pos)
        report = native_target_preview(
            self.session, spec, MISSION, self.caster.id, aim)
        self.assertEqual(report["aim"], list(aim))
        self.assertIn(list(aim), report["area"])
        self.assertEqual(report["legal"], list(aim) in report["available"])
        if report["legal"]:
            self.assertTrue(any(row["unit"] == enemy.id
                                for row in report["recipients"]))
            for cell in report["area"]:
                self.assertLessEqual(abs(cell[0] - aim[0]) +
                                     abs(cell[1] - aim[1]), 1)

        spec["target"]["team"] = "ally"
        refused = native_target_preview(self.session, spec, MISSION,
                                        self.caster.id, aim)
        self.assertFalse(refused["legal"])
        self.assertNotIn(list(aim), refused["available"])
        self.assertEqual(refused["recipients"], [])

    def test_range_and_invalid_cells_fail_closed(self):
        pos = tuple(self.caster.pos)
        spec = deepcopy(self.ability)
        spec["target"].update(team="self", range=0)
        other = next((c for c in self.mission.board.cells()
                      if c != pos), None)
        self.assertIsNotNone(other)
        refused = native_target_preview(
            self.session, spec, MISSION, self.caster.id, other)
        self.assertFalse(refused["legal"])
        self.assertEqual(refused["recipients"], [])
        self.assertTrue(refused["rejection"])
        for aim in ((-1, 0), (999, 999), (True, 0), ["1", 0], (), None):
            with self.subTest(aim=aim):
                with self.assertRaises(AbilityError):
                    native_target_preview(
                        self.session, spec, MISSION, self.caster.id, aim)

    def test_native_line_of_sight_respects_blocked_intermediate_tile(self):
        from sporebound.model import Tile
        from sporebound.game_project import GameProject
        modified = deepcopy(self.content)
        # Jeanne (1,4), target (1,2), wall (1,3): native supercover LOS.
        mission = modified.missions[MISSION]
        self.assertEqual(tuple(self.caster.pos), (1, 4))
        mission.board.tiles[(1, 3)] = Tile(blocked=True)
        scoped = AuthoringSession.new(modified, GameProject.default(modified))
        spec = deepcopy(self.ability)
        spec["target"].update(team="ground", range=8)
        preview = native_target_preview(
            scoped, spec, MISSION, "jeanne", (1, 2))
        self.assertFalse(preview["line_of_sight"])
        self.assertFalse(preview["legal"])
        self.assertIn("Line of sight blocked", preview["rejection"])
        self.assertNotIn([1, 2], preview["available"])
        self.assertEqual(preview["recipients"], [])

    def test_unknown_ids_and_unsupported_ct_fail_closed(self):
        with self.assertRaises(AbilityError) as caught:
            native_target_preview(self.session, self.ability,
                                  "unknown", self.caster.id, (0, 0))
        self.assertEqual(caught.exception.code, "missing_mission")
        with self.assertRaises(AbilityError) as caught:
            native_target_preview(self.session, self.ability,
                                  MISSION, "unknown", (0, 0))
        self.assertEqual(caught.exception.code, "missing_actor")
        action = deepcopy(self.ability)
        action["profiles"] = ["ACTION_REALTIME"]
        action["timing"] = {"ACTION_REALTIME": {"windup": 0, "cooldown": 3}}
        with self.assertRaises(AbilityError) as caught:
            native_target_preview(self.session, action,
                                  MISSION, self.caster.id, self.caster.pos)
        self.assertEqual(caught.exception.code, "unsupported_mode")
        dynamic = deepcopy(self.ability)
        dynamic["effects"][0]["formula"] = {"op": "stat", "name": "attack"}
        with self.assertRaises(AbilityError) as caught:
            native_target_preview(self.session, dynamic,
                                  MISSION, self.caster.id, self.caster.pos)
        self.assertEqual(caught.exception.code, "unsupported_formula")

    def test_r3_pick_coordinate_uses_shared_renderer_contract(self):
        scene = scene_from_mission(self.mission)
        projections = (IsoProjection(), TopDownProjection())
        for projection in projections:
            cell = next(c for c in self.mission.board.cells()
                        if c not in [tuple(u.pos) for u in self.mission.units]
                        and c not in [tuple(o["pos"])
                                      for o in self.mission.objects])
            height = self.mission.board.tile(cell).height
            camera = Camera()
            camera.center(*projection.project(cell[0], cell[1], height))
            at = camera.screen(*projection.project(cell[0], cell[1], height))
            picked = pick(scene, camera, *at, projection)
            self.assertIsNotNone(picked)
            self.assertEqual(picked["kind"], "tile")
            self.assertEqual(picked["cell"], list(cell))


if __name__ == "__main__":
    unittest.main()
