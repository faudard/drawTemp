"""R6.10 production regression: doors, stacked movement, LOS and persistence."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.player.controller import PlayerController
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.construction import ConstructionWorkspace
from drawtemp.sdk.reference import MISSION, reference_project
from examples.layered_house_3720c import create
from sporebound.building_gameplay import add_building_door
from sporebound.engine import Battle
from sporebound.interior_levels import edit_interior_tile
from sporebound.level_navigation import floor_line_of_sight, place_unit_on_level
from sporebound.model import RuleError
from tests_standalone.test_drawtemp5_r6 import available_anchor


def house_scenario(*, opened=False, locked=False, gap=False, crate=False):
    """Real canonical Content: one ground actor, one upstairs enemy, one stair."""
    data, mid = create()
    mission = next(m for m in data["missions"] if m["id"] == mid)
    house = mission["structures"][0]
    player = next(u["id"] for u in mission["units"] if u["team"] == "player")
    data = place_unit_on_level(data, mid, player, 0, (4, 6))
    data = add_building_door(data, mid, house["id"], opened=opened, locked=locked)
    if gap:
        data = edit_interior_tile(data, mid, house["id"], 1,
                                  (5, 5), present=False)
    if crate:
        data = edit_interior_tile(data, mid, house["id"], 1,
                                  (5, 5), feature="crate")
    mission = next(m for m in data["missions"] if m["id"] == mid)
    for unit in mission["units"]:
        unit["speed"] = 1000 if unit["team"] == "player" else 1
    content = Content.from_dict(data)
    door = next(o["id"] for o in mission["objects"] if o["kind"] == "door")
    return content, mid, door


class BuildingGameplayR610Tests(unittest.TestCase):
    def test_transactional_stairs_and_door_authoring_undo_redo(self):
        content, project = reference_project()
        session = AuthoringSession.new(content, project)
        workspace = ConstructionWorkspace(session, MISSION)
        anchor = available_anchor(content)
        workspace.apply(workspace.preview_place("Maison", anchor))
        info = workspace.inspect()
        workspace.apply(workspace.preview_floor_add(1))
        workspace.apply(workspace.preview_floor_add(2))
        landing = info.entry
        before = session.snapshot()
        preview = workspace.preview_staircase(landing, from_level=0)
        self.assertEqual(before, session.snapshot())
        workspace.apply(preview)
        workspace.apply(workspace.preview_staircase(landing, from_level=1))
        workspace.apply(workspace.preview_gameplay_door())
        data = session.snapshot().to_dict()["content"]
        mission = next(m for m in data["missions"] if m["id"] == MISSION)
        self.assertEqual(len(mission["level_links"]), 2)
        self.assertEqual({e["cost"] for e in mission["level_links"]}, {1})
        self.assertTrue(any(obj["kind"] == "door" and tuple(obj["pos"]) == landing
                            for obj in mission["objects"]))
        workspace.undo()
        # R0's fixture already owns a switch-linked gate. Undo must remove
        # only the newly authored building entrance, never that original door.
        undone = next(m for m in session.snapshot().to_dict()["content"]["missions"]
                      if m["id"] == MISSION)
        self.assertFalse(any(o["id"] != "gate" and o["kind"] == "door"
                             for o in undone["objects"]))
        self.assertTrue(any(o["id"] == "gate" for o in undone["objects"]))
        workspace.redo()
        self.assertEqual(len(workspace.inspect().levels), 2)
        with TemporaryDirectory() as folder:
            file = Path(folder) / "building.json"
            session.save_as(file)
            reopened = AuthoringSession.open(file)
            self.assertEqual(reopened.snapshot().content, session.snapshot().content)

    def test_staircase_rejects_blocked_or_missing_floor_and_preserves_history(self):
        content, project = reference_project()
        s = AuthoringSession.new(content, project)
        w = ConstructionWorkspace(s, MISSION)
        anchor = available_anchor(content)
        w.apply(w.preview_place("Maison", anchor))
        baseline = s.snapshot()
        with self.assertRaises(AuthoringError):
            w.preview_staircase(w.inspect().entry, from_level=0)
        with self.assertRaises(AuthoringError):
            w.preview_staircase((999, 999), from_level=0)
        with self.assertRaises(AuthoringError):
            w.preview_staircase(w.inspect().entry, from_level=True)
        self.assertEqual(s.snapshot(), baseline)
        w.apply(w.preview_floor_add(1))
        wall = anchor
        with self.assertRaises(AuthoringError):
            w.preview_staircase(wall, from_level=0)

    def test_door_closed_blocks_path_then_stairs_and_replay(self):
        content, mid, door = house_scenario()
        b = Battle(content, mid, seed=17, battle_id="r610-door")
        self.assertEqual(b.active.team, "player")
        self.assertTrue(b.board.tile((4, 5)).blocked)
        self.assertNotIn((0, 4, 5), b.level_reachable())
        self.assertNotIn((1, 4, 5), b.level_reachable())
        b.execute({"kind": "door_toggle", "object": door})
        self.assertFalse(b.board.tile((4, 5)).blocked)
        self.assertTrue(next(o for o in b.mission.objects if o["id"] == door)["open"])
        self.assertIn((1, 4, 5), b.level_reachable())
        b.execute({"kind": "level_move", "level": 1, "cell": [4, 5]})
        self.assertEqual(b.unit_levels[b.active.id], 1)
        self.assertEqual(b.active.pos, (4, 5))
        self.assertTrue(b.line_of_sight((4, 5), (4, 4), level=1))
        self.assertEqual(Battle.replay(b.recording()).digest(), b.digest())
        events = [row["kind"] for row in b.events]
        self.assertIn("door_state", events)
        self.assertIn("level_move", events)

    def test_two_upper_floors_are_traversable_with_explicit_stair_links(self):
        from sporebound.interior_levels import add_interior_floor
        from sporebound.level_navigation import add_level_link
        data, mid = create()
        house_id = next(m for m in data["missions"] if m["id"] == mid)["structures"][0]["id"]
        data = add_interior_floor(data, mid, house_id, 2)
        data = add_level_link(data, mid, [1, 4, 5], [2, 4, 5])
        mission = next(m for m in data["missions"] if m["id"] == mid)
        player = next(u["id"] for u in mission["units"] if u["team"] == "player")
        data = place_unit_on_level(data, mid, player, 0, (4, 6))
        data = add_building_door(data, mid, house_id, opened=True)
        for actor in next(m for m in data["missions"] if m["id"] == mid)["units"]:
            actor["speed"] = 1000 if actor["team"] == "player" else 1
        battle = Battle(Content.from_dict(data), mid, seed=42,
                        battle_id="r610-two-decks")
        self.assertIn((2, 4, 5), battle.level_reachable())
        battle.execute({"kind": "level_move", "level": 2, "cell": [4, 5]})
        self.assertEqual(battle.unit_levels[battle.active.id], 2)
        self.assertEqual(battle.active.pos, (4, 5))
        self.assertEqual(Battle.replay(battle.recording()).digest(), battle.digest())

    def test_door_close_rejects_occupancy_and_invalid_access_atomically(self):
        content, mid, door = house_scenario(opened=True)
        b = Battle(content, mid, seed=29, battle_id="r610-occupied")
        actor = b.active
        actor.pos = (4, 5)
        before = b.digest()
        with self.assertRaisesRegex(RuleError, "Cannot close"):
            b.execute({"kind": "door_toggle", "object": door})
        self.assertEqual(b.digest(), before)
        self.assertFalse(b.board.tile((4, 5)).blocked)
        # A rejected Battle.execute rolls back by restoring its own deep copy.
        # The old local 'actor' is detached from the restored Battle object.
        b.active.pos = (4, 6)
        before = b.digest()
        with self.assertRaises(RuleError):
            b.execute({"kind": "door_toggle", "object": "missing"})
        self.assertEqual(b.digest(), before)
        with self.assertRaises(RuleError):
            b.execute({"kind": "door_toggle", "object": door, "open": False})
        self.assertEqual(b.digest(), before)
        b.execute({"kind": "door_toggle", "object": door})
        self.assertTrue(b.board.tile((4, 5)).blocked)
        self.assertFalse(next(o for o in b.mission.objects if o["id"] == door)["open"])

    def test_locked_and_upstairs_door_actions_fail(self):
        content, mid, door = house_scenario(locked=True)
        b = Battle(content, mid, seed=3, battle_id="r610-locked")
        before = b.digest()
        with self.assertRaisesRegex(RuleError, "locked"):
            b.execute({"kind": "door_toggle", "object": door})
        self.assertEqual(b.digest(), before)
        content, mid, door = house_scenario(opened=True)
        b = Battle(content, mid, seed=5, battle_id="r610-upper")
        b.active.pos = (4, 5)
        b.unit_levels[b.active.id] = 1
        before = b.digest()
        with self.assertRaisesRegex(RuleError, "ground-floor"):
            b.execute({"kind": "door_toggle", "object": door})
        self.assertEqual(b.digest(), before)

    def test_upper_floor_collision_gap_and_supercover_los(self):
        for variant in ("gap", "crate"):
            content, mid, _ = house_scenario(**{variant: True})
            mission = content.missions[mid]
            b = Battle(content, mid, seed=17, battle_id="r610-los-" + variant)
            from sporebound.level_navigation import walkable_levels
            self.assertNotIn((5, 5), walkable_levels(mission)[1])
            self.assertFalse(floor_line_of_sight(mission, 1, (4, 5), (5, 4)))
            self.assertFalse(b.line_of_sight((4, 5), (5, 4), level=1))
            self.assertTrue(b.line_of_sight((4, 5), (4, 4), level=1))
            self.assertTrue(b.line_of_sight((4, 5), (4, 5), level=1))

    def test_player_save_load_preserves_door_and_floor(self):
        content, mid, door = house_scenario()
        project = GameProject.default(content)
        project.campaigns[0]["start_mission"] = mid
        project.validate(content)
        with TemporaryDirectory() as folder:
            player = PlayerController(content, project, "main", folder, seed=17)
            player.new_game()
            player.start_mission(mid)
            initial = player.state()
            self.assertEqual(initial["screen"], "battle")
            self.assertTrue(initial["battle"]["level_links"])
            player.toggle_door(door)
            self.assertTrue(next(o for o in player.state()["battle"]["objects"]
                                 if o["id"] == door)["open"])
            player.level_move(1, (4, 5))
            battle = player.state()["battle"]
            self.assertEqual(battle["unit_levels"][battle["active"]], 1)
            player.save(1)
            restored = PlayerController(content, project, "main", folder, seed=17)
            restored.load(1)
            self.assertEqual(restored.state()["battle"]["unit_levels"],
                             player.state()["battle"]["unit_levels"])
            self.assertEqual(restored.state()["battle"]["objects"],
                             player.state()["battle"]["objects"])


if __name__ == "__main__":
    unittest.main()
