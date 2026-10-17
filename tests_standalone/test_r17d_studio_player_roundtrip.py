"""R17.D Studio -> authored documents -> standalone Player -> verified resume.

No synthetic dispatch or private battle mutation: events are authored through
the R1 session, saved as real Content/GameProject and played via the R12 API.
The optional Qt test drives the same QML PlayerBridge, offscreen only.
"""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from drawtemp.player.qt_app import build_controller, scene_for_player
from sporebound.event_composer import action, condition
from sporebound.game_session import GameSession
from sporebound.cinematics import triggered_tactical_cinematics


GATE_EVENT = "r17d_jeanne_gate"
PAGE = "opened"
STORY = "r17d_gate_story"
CINEMATIC = "r17d_gate_movie"


def author_demo(folder):
    """Exercise normal Studio transaction/Save As instead of handcrafted JSON."""
    content, project = reference_project()
    editor = EventStudio(AuthoringSession.new(content, project))
    initial = editor.documents()
    editor.gate_wizard(
        MISSION, door_id="gate", lever_id="lever", lever_cell=[2, 4],
        event_id=GATE_EVENT, danger_cell=[1, 3], danger=7,
        dialogue="Jeanne ouvre la porte", cinematic_id=CINEMATIC)
    editor.add_page(
        MISSION, GATE_EVENT, page_id=PAGE, priority=70,
        condition=condition("interact", object_id="lever"),
        actions=[action("message", text="Le passage est libre"),
                 action("hazard", pos=[1, 3], amount=7)])
    editor.create_scene(
        MISSION, STORY, "La porte du château", "Jeanne, entrez !", speaker="Garde")
    editor.bind_scene(MISSION, GATE_EVENT, STORY)
    # GameProject editing must still work AFTER pages made default rules
    # insufficient to validate this Content.
    editor.add_presentation_cue(
        MISSION, GATE_EVENT, clip_id=CINEMATIC,
        clip_name="La porte du château", kind="sound",
        cue_id="r17d_bell", fields={"cue": "bell"})
    self_contained = editor.documents()
    assert self_contained["content"] != initial["content"]
    assert self_contained["project"] != initial["project"]
    target = Path(folder) / "jeanne-gate.json"
    editor.save_as(target)
    return target, self_contained


def _player(folder, content):
    return build_controller(
        content_path=content, save_dir=Path(folder) / "saves", campaign_id="main")


class StudioPlayerRoundtripTests(unittest.TestCase):
    def test_gate_page_dialogue_movie_and_verified_player_save_resume(self):
        with TemporaryDirectory() as folder:
            path, authored = author_demo(folder)
            self.assertTrue(path.is_file())
            self.assertTrue(path.with_suffix(".game.json").is_file())
            fresh = EventStudio(AuthoringSession.open(path))
            self.assertEqual(fresh.documents()["content"], authored["content"])
            self.assertEqual(fresh.documents()["project"], authored["project"])
            self.assertEqual(fresh.event_pages(MISSION, GATE_EVENT)[1]["id"], PAGE)

            game = _player(folder, path)
            self.assertEqual(game.new_game()["screen"], "dialogue")
            game.choose("enter")
            game.start_mission(MISSION)
            before = game.state()["battle"]
            self.assertFalse(next(x for x in before["objects"]
                                  if x["id"] == "gate")["open"])
            scene_before = scene_for_player(game)
            # Same projection contract as the canonical Studio authoring
            # preview; no second geometry / terrain renderer.
            scene_studio = fresh.iso_scene(MISSION)
            self.assertEqual((scene_before["width"], scene_before["height"]),
                             (scene_studio["width"], scene_studio["height"]))
            game.interact_object("lever")
            fired_state = game.state()
            self.assertEqual(fired_state["screen"], "dialogue")
            self.assertEqual(fired_state["scene"]["id"], STORY)
            self.assertIn("continue", [row["id"] for row in fired_state["choices"]])
            opened = next(x for x in fired_state["battle"]["objects"]
                          if x["id"] == "gate")
            self.assertTrue(opened["open"])
            game.save(1)
            save_path = Path(folder) / "saves" / "slot_1.json"
            original = save_path.read_bytes()
            restored = GameSession.load(save_path, game.content, game.project)
            battle = restored.active_battle
            events = [x for x in battle.events if
                      x["kind"] == "trigger" and x.get("id") == GATE_EVENT]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["page"], PAGE)
            self.assertEqual(battle.board.tile((1, 3)).hazard, 7)
            clips, _ = triggered_tactical_cinematics(game.project, battle)
            self.assertIn(CINEMATIC, [clip["id"] for clip in clips])
            self.assertIn("r17d_bell", [
                cue["id"] for clip in clips for cue in clip["events"]])

            restarted = _player(folder, path)
            self.assertEqual(restarted.load(1)["screen"], "dialogue")
            self.assertEqual(restarted.state()["battle"], fired_state["battle"])
            self.assertEqual(save_path.read_bytes(), original)
            restarted.choose("continue")
            self.assertEqual(restarted.state()["screen"], "battle")
            restarted.save(1)
            after = GameSession.load(save_path, restarted.content, restarted.project)
            self.assertEqual(sum(x["kind"] == "trigger" and
                                 x.get("id") == GATE_EVENT
                                 for x in after.active_battle.events), 1)
            self.assertTrue(next(x for x in restarted.state()["battle"]["objects"]
                                 if x["id"] == "gate")["open"])
            self.assertEqual(_player(folder, path).load(1)["screen"], "battle")

    def test_rejected_cross_workshop_edit_retains_documents_and_disk(self):
        with TemporaryDirectory() as folder:
            path, _ = author_demo(folder)
            editor = EventStudio(AuthoringSession.open(path))
            before = deepcopy(editor.documents())
            old_disk = (path.read_bytes(), path.with_suffix(".game.json").read_bytes())
            revision = editor.session.revision
            with self.assertRaises(AuthoringError):
                editor.add_page(
                    MISSION, GATE_EVENT, page_id="bad_priority", priority=101,
                    condition=condition("tick", tick=0),
                    actions=[action("message", text="bad")])
            self.assertEqual(editor.documents(), before)
            self.assertEqual(editor.session.revision, revision)
            self.assertEqual((path.read_bytes(),
                              path.with_suffix(".game.json").read_bytes()), old_disk)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "PySide6 optional; QT workflow provides it")
class StudioPlayerQtBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication(["r17d-bridge"])

    def test_authored_gate_renders_through_player_qml_bridge(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.qt_app import create_bridge
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as folder:
            path, _ = author_demo(folder)
            player = _player(folder, path)
            renderer = make_controller(scene_for_player(player))
            bridge = create_bridge(player, renderer)
            engine = QQmlApplicationEngine()
            engine.setInitialProperties({"smokeMode": True})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            engine.load(QUrl.fromLocalFile(str(
                Path(__file__).resolve().parents[1] / "drawtemp/player/Main.qml")))
            self.assertTrue(engine.rootObjects(), "Real QML Player failed to load")
            window = engine.rootObjects()[0]
            try:
                bridge.newGame()
                bridge.choose("enter")
                bridge.startMission(MISSION)
                bridge.interactObject("lever")
                self.assertEqual(player.state()["screen"], "dialogue")
                self.assertEqual(renderer.scene["mission"], MISSION)
                self.assertTrue(next(x for x in renderer.scene["objects"]
                                     if x["id"] == "gate")["open"])
                bridge.saveGame(1)
                bridge.titleScreen()
                bridge.loadGame(1)
                self.assertEqual(player.state()["scene"]["id"], STORY)
                self.assertEqual(renderer.scene["mission"], MISSION)
            finally:
                window.close()
                engine.deleteLater()


if __name__ == "__main__":
    unittest.main()
