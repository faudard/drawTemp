"""R41.B3 — canonical routed exploration → RPG encounter → exploration gates.

The tests use the R25 SceneRouter and R41.B2 actual GameSession/Simulation.
They do not substitute a mock combat engine or forge an unverified save.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r41_encounter import encounter_fixture


def routed_rpg_fixture():
    content, project = encounter_fixture()
    project.story["scenes"].append({
        "id": "forest", "title": "Chemin forestier",
        "speaker": "", "text": "Le chemin mène à l'auberge",
        "choices": [{"id": "continue", "label": "Continuer"}],
    })
    project.exploration["forest"] = {
        "title": "Chemin forestier", "theme": "forest",
        "width": 4, "height": 4, "start": [0, 0], "blocked": [],
        "interactions": [{
            "id": "exit", "title": "Auberge",
            "text": "Retour au village", "pos": [1, 2],
            "required": False, "exit": True,
        }],
    }
    project.scene_routes = {
        "version": 1, "start": "inn", "links": [
            {"id": "to_forest", "source": "inn",
             "destination": "forest", "spawn": [1, 1]},
            {"id": "back_to_inn", "source": "forest",
             "destination": "inn", "spawn": [1, 1]},
        ],
    }
    project.validate(content)
    return content, project


class R41RoutedEncounterTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = routed_rpg_fixture()

    def test_other_scene_is_not_authorized_and_return_keeps_position(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        self.assertEqual(session.rpg_available(), ["sparring"])
        session.route_move(1, 0)
        location = session.route_state()["position"]
        self.assertEqual(location, [1, 1])
        session.route_transition("to_forest")
        self.assertEqual(session.route_scene, "forest")
        self.assertEqual(session.rpg_available(), [])
        with self.assertRaises(RuleError):
            session.rpg_start("sparring")
        session.route_transition("back_to_inn")
        self.assertEqual(session.route_scene, "inn")
        self.assertEqual(session.rpg_available(), ["sparring"])
        starting = deepcopy(session.route_state())
        history = list(session.route_history)
        session.rpg_start("sparring")
        self.assertEqual(session.mode, "rpg")
        self.assertEqual(session.route_state(), starting)
        self.assertEqual(session.route_history, history)
        self.assertEqual(session.rpg_state()["scene"], "inn")
        session.rpg_action({"kind": "flee", "actor": "jeanne"})
        session.rpg_finish()
        self.assertEqual(session.mode, "campaign")
        self.assertEqual(session.route_scene, "inn")
        self.assertEqual(session.route_history, history)
        self.assertEqual(session.route_state(), starting)
        self.assertEqual(session.rpg_available(), ["sparring"])

    def test_routed_mid_combat_save_replay_and_valid_but_wrong_route(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        session.route_move(1, 0)
        position = session.route_state()["position"]
        session.rpg_start("sparring")
        session.rpg_action({"kind": "guard", "actor": "jeanne"})
        checkpoint = session.recording()
        self.assertEqual(checkpoint["mode"], "rpg")
        self.assertEqual(checkpoint["scene_route"]["current"], "inn")
        self.assertEqual(checkpoint["rpg_encounter"]["view"]["scene"], "inn")
        recovered = GameSession.from_recording(
            checkpoint, self.content, self.project)
        self.assertEqual(recovered.recording(), checkpoint)
        self.assertEqual(recovered.route_state()["position"], position)

        with TemporaryDirectory() as directory:
            target = Path(directory) / "r41-routed.json"
            session.save(target)
            loaded = GameSession.load(target, self.content, self.project)
            self.assertEqual(loaded.recording(), checkpoint)
            loaded.rpg_action({"kind": "flee", "actor": "jeanne"})
            loaded.rpg_finish()
            self.assertEqual(loaded.route_state()["position"], position)

        # Both route cursor AND history are individually valid, but point to a
        # different scene than the replayed encounter. That must still reject.
        forged = deepcopy(checkpoint)
        forged["scene_route"] = {
            "version": 1, "current": "forest", "history": ["to_forest"]}
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, self.content, self.project)

        forged = deepcopy(checkpoint)
        forged["scene_route"]["history"] = []
        forged["scene_route"]["current"] = "forest"
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, self.content, self.project)

    def test_victory_reward_survives_travel_and_reload_once(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        session.progress.inventory["potion"] = 2
        session.route_move(1, 0)
        session.rpg_start("sparring")
        before = session.recording()
        with self.assertRaises(RuleError):
            session.route_transition("to_forest")
        self.assertEqual(session.recording(), before)
        for _ in range(20):
            current = session.rpg_state()
            if current["result"]:
                break
            session.rpg_action({
                "kind": "attack", "actor": current["active"],
                "target": "renaud_mentor"})
        self.assertEqual(session.rpg_state()["result"], "victory")
        session.rpg_finish()
        self.assertEqual(session.progress.gold, 17)
        self.assertEqual(session.progress.heroes["jeanne"].xp, 50)
        self.assertEqual(session.progress.inventory["potion"], 2)
        self.assertEqual(session.rpg_available(), [])
        session.route_transition("to_forest")
        session.route_transition("back_to_inn")
        self.assertEqual(session.rpg_available(), [])
        with TemporaryDirectory() as directory:
            target = Path(directory) / "r41-completed.json"
            session.save(target)
            loaded = GameSession.load(target, self.content, self.project)
            self.assertEqual(loaded.recording(), session.recording())
            self.assertEqual(loaded.progress.gold, 17)
            self.assertEqual(loaded.progress.heroes["jeanne"].xp, 50)
            self.assertEqual(loaded.progress.inventory["potion"], 2)
            self.assertEqual(loaded.rpg_available(), [])
            with self.assertRaises(RuleError):
                loaded.rpg_start("sparring")

    def test_player_in_routed_exploration_actions_and_recovery(self):
        with TemporaryDirectory() as directory:
            player = PlayerController(
                self.content, self.project, "main", Path(directory), seed=17)
            state = player.new_game()
            self.assertEqual(state["screen"], "exploration")
            self.assertEqual(state["rpg_available"], ["sparring"])
            player.explore_move(1, 0)
            origin = player.state()["exploration"]["position"]
            player.start_rpg_encounter("sparring")
            state = player.state()
            self.assertEqual(state["screen"], "rpg_battle")
            self.assertEqual(state["rpg"]["scene"], "inn")
            routed = player.session.rpg_route_state(
                expected_revision=state["revision"])
            self.assertEqual(thaw(routed)["position"], origin)
            player.rpg_action("guard")
            player.save(1)

            restored = PlayerController(
                self.content, self.project, "main", Path(directory), seed=17)
            restored.load(1)
            self.assertEqual(restored.state()["screen"], "rpg_battle")
            self.assertEqual(restored.state()["rpg"], player.state()["rpg"])
            old = restored.session.snapshot().revision
            with self.assertRaises(SimulationError):
                restored.session.rpg_route_state(expected_revision=old - 1)
            restored.rpg_action("flee")
            restored.finish_rpg_encounter()
            self.assertEqual(restored.state()["screen"], "exploration")
            self.assertEqual(restored.state()["exploration"]["position"], origin)
            self.assertEqual(restored.state()["rpg_available"], ["sparring"])


if __name__ == "__main__":
    unittest.main()
