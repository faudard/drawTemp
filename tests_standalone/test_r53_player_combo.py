"""R53.B2: Player-facing native RPG combo, save/reload and QML contract."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from tests_standalone.test_r53_combo_rpg import combo_fixture


class R53PlayerComboTests(unittest.TestCase):
    def test_player_combo_is_real_simulation_action_and_survives_reload(self):
        content, project = combo_fixture()
        with TemporaryDirectory() as dirname:
            folder = Path(dirname)
            player = PlayerController(content, project, "main", folder, seed=31)
            player.new_game()
            player.start_rpg_encounter("sparring")
            initial = player.state()
            self.assertEqual(initial["screen"], "rpg_battle")
            self.assertEqual(initial["rpg"]["combos"], ["combined_strike"])
            first = {row["id"]: row for row in initial["rpg"]["actors"]}
            rev = initial["revision"]
            player.rpg_action("combo", "renaud_mentor", "combined_strike")
            result = player.state()
            self.assertGreater(result["revision"], rev)
            self.assertEqual(result["screen"], "rpg_battle")
            current = {row["id"]: row for row in result["rpg"]["actors"]}
            self.assertLess(current["renaud_mentor"]["hp"],
                            first["renaud_mentor"]["hp"])
            self.assertLess(current["jeanne"]["mp"], first["jeanne"]["mp"])
            self.assertLess(current["etienne"]["mp"], first["etienne"]["mp"])
            player.save(1)
            replay = PlayerController(content, project, "main", folder, seed=31)
            replay.load(1)
            self.assertEqual(replay.state()["rpg"], result["rpg"])
            self.assertEqual(replay.session.recording(),
                             player.session.recording())

    def test_no_new_qml_authority_and_legacy_view_stays_without_combos(self):
        content, project = combo_fixture(with_skills=False)
        with TemporaryDirectory() as dirname:
            player = PlayerController(
                content, project, "main", Path(dirname), seed=31)
            player.new_game()
            player.start_rpg_encounter("sparring")
            self.assertNotIn("combos", player.state()["rpg"])
            before = player.session.recording()
            with self.assertRaises(Exception):
                player.rpg_action("combo", "renaud_mentor", "combined_strike")
            self.assertEqual(player.session.recording(), before)

        qml = Path("drawtemp/player/Main.qml").read_text(encoding="utf-8")
        self.assertIn('objectName: "r53-rpg-combo-picker"', qml)
        self.assertIn('sequence: "C"', qml)
        self.assertIn('root.playerData.rpg.combos || []', qml)
        self.assertIn('player.rpgAction(kind', qml)
        self.assertIn('root.playerData.rpg.combo_skip || []', qml)


if __name__ == "__main__":
    unittest.main()
