"""R27.C real Player puzzle controls, state visibility and verified resume.

No Studio GUI or Qt dependency is needed for these lifecycle regressions.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.player.controller import PlayerController
from drawtemp.player.qt_app import scene_for_player
from drawtemp.render.iso_scene import Camera, render_items
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.dungeon_authoring import DungeonStudio
from sporebound.tactical_rpg3 import authored_rules_for_document


def authored_puzzle(kind="key"):
    original, manifest = reference_project()
    maps = MapStudio(AuthoringSession.new(original, manifest))
    studio = DungeonStudio(maps)
    studio.create_dungeon("r27c_temple", "Temple des énigmes", width=16,
                          height=16)
    studio.build_room((3, 3), (12, 12), entrance=(7, 3))
    maps.paint([(8, 8)], "goal")
    if kind == "key":
        studio.place_puzzle("amber_key", "key", (7, 2), door_id="room_door")
        hero_pos = [7, 2]
    elif kind == "block":
        studio.place_puzzle("pad", "plate", (6, 2), door_id="room_door")
        studio.place_puzzle("stone_box", "block", (7, 2))
        hero_pos = [8, 2]
    else:
        raise ValueError(kind)
    pair = maps.snapshot()
    mission = next(row for row in pair["content"]["missions"]
                   if row["id"] == "r27c_temple")
    hero = next(unit for unit in mission["units"] if unit["team"] == "player")
    enemy = next(unit for unit in mission["units"] if unit["team"] == "enemy")
    hero["pos"] = hero_pos
    hero["speed"] = 100
    enemy["speed"] = 1
    raw = pair["content"]
    content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
    project_raw = pair["project"]
    project_raw["campaigns"][0]["start_mission"] = "r27c_temple"
    project = GameProject.from_dict(project_raw, content)
    return content, project


def playing_player(content, project, folder):
    player = PlayerController(content, project, "main", folder)
    player.new_game()
    player.choose("enter")
    player.start_mission("r27c_temple")
    state = player.state()
    assert state["screen"] == "battle", state["screen"]
    return player


class PuzzlePlayerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_key_context_and_invalid_action_cannot_change_autosave(self):
        content, project = authored_puzzle()
        player = playing_player(content, project, self.tmp.name)
        initial = player.state()
        self.assertTrue(initial["puzzle"]["enabled"])
        key = next(a for a in initial["puzzle"]["actions"]
                   if a["id"] == "amber_key")
        door = next(a for a in initial["puzzle"]["actions"]
                    if a["id"] == "room_door")
        self.assertTrue(key["enabled"])
        self.assertFalse(door["enabled"])
        self.assertEqual(key["command"],
                         {"kind": "interact", "object": "amber_key"})
        save_path = Path(self.tmp.name) / "autosave.json"
        before = save_path.read_bytes()
        revision = initial["revision"]
        recording = player.session.recording()
        with self.assertRaises(ValueError):
            player.puzzle_action("room_door")  # Missing key.
        with self.assertRaises(ValueError):
            player.puzzle_action("fabricated")
        self.assertEqual(before, save_path.read_bytes())
        self.assertEqual(recording, player.session.recording())
        self.assertEqual(revision, player.state()["revision"])
        player.select_cell(7, 2)
        self.assertEqual(before, save_path.read_bytes())
        self.assertEqual(revision, player.state()["revision"])

    def test_collect_key_updates_renderer_and_verified_checkpoint_resume(self):
        content, project = authored_puzzle()
        player = playing_player(content, project, self.tmp.name)
        player.puzzle_action("amber_key")
        state = player.state()
        self.assertGreater(state["revision"], 2)
        self.assertIn(
            "Récupérée",
            [row["detail"] for row in state["puzzle"]["status"]
             if row["id"] == "amber_key"])
        self.assertTrue(next(o for o in state["battle"]["objects"]
                             if o["id"] == "amber_key")["used"])
        scene = scene_for_player(player)
        key = next(o for o in scene["objects"] if o["id"] == "amber_key")
        self.assertTrue(key["used"])
        item = next(o for o in render_items(scene, Camera())
                    if o["kind"] == "object" and o["id"] == "amber_key")
        self.assertTrue(item["used"])
        saved = player.session.recording()
        player.save(1)
        reloaded = PlayerController(content, project, "main", self.tmp.name)
        reloaded.load(1)
        self.assertEqual(reloaded.state()["battle"], state["battle"])
        self.assertEqual(reloaded.session.recording(), saved)
        # Resume uses verified autosave, not a new puzzle-specific file.
        auto = PlayerController(content, project, "main", self.tmp.name)
        auto.load_autosave()
        self.assertEqual(auto.state()["battle"], state["battle"])

    def test_block_context_push_and_engine_collision_are_authoritative(self):
        content, project = authored_puzzle("block")
        player = playing_player(content, project, self.tmp.name)
        initial = player.state()
        push = next(a for a in initial["puzzle"]["actions"]
                    if a["id"] == "stone_box")
        self.assertTrue(push["enabled"])
        self.assertEqual(push["command"]["direction"], [-1, 0])
        player.puzzle_action("stone_box")
        state = player.state()
        block = next(o for o in state["battle"]["objects"]
                     if o["id"] == "stone_box")
        door = next(o for o in state["battle"]["objects"]
                    if o["id"] == "room_door")
        self.assertEqual(block["pos"], [6, 2])
        self.assertTrue(door["open"])
        self.assertEqual(
            next(row["detail"] for row in state["puzzle"]["status"]
                 if row["id"] == "pad"), "Activée")
        player.save(1)
        reloaded = PlayerController(content, project, "main", self.tmp.name)
        reloaded.load(1)
        self.assertEqual(reloaded.state()["battle"]["objects"],
                         state["battle"]["objects"])
        self.assertEqual(
            next(o for o in scene_for_player(reloaded)["objects"]
                 if o["id"] == "stone_box")["x"], 6)

    def test_legacy_reference_campaign_does_not_change_interaction_contract(self):
        original, project = reference_project()
        player = PlayerController(original, project, "main", self.tmp.name)
        player.new_game()
        player.choose("enter")
        player.start_mission(next(iter(original.missions)))
        state = player.state()
        self.assertFalse(state["puzzle"]["enabled"])
        self.assertEqual(state["puzzle"]["actions"], [])
        self.assertIn("gate", {o["id"] for o in state["battle"]["objects"]})


if __name__ == "__main__":
    unittest.main()
