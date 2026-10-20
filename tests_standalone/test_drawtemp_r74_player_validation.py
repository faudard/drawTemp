"""R74.C3: real three-mission tactical replays, encounter/loot parity and export gates."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.export.r15 import ExportError, export_game, preflight
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r74_assisted_dungeons import (
    AssistedDungeonController, DungeonAssistError,
)
from drawtemp.studio.r74_player_validation import (
    _place_encounters, apply_r74_player_candidate,
    prepare_r74_player_candidate, verify_trilogy_player,
)
from sporebound.game_session import GameSession
from sporebound.tactical_rpg3 import authored_rules_for_document


class R74PlayerCertificationTests(unittest.TestCase):
    def setUp(self):
        self.session = AuthoringSession.new(*reference_project())
        self.controller = AssistedDungeonController(self.session)
        self.suggestions = self.controller.preview_variants(
            seed=74, count=3, rooms=8, branches=2, locked_goal=True,
            encounter_budget=2, loot_budget=2,
        )
        self.before = self.session.snapshot().to_dict()

    def prepare(self, prefix="r74p"):
        return prepare_r74_player_candidate(
            self.controller, self.suggestions, prefix=prefix)

    def test_real_game_session_solves_all_three_dungeons_and_replays(self):
        candidate = self.prepare()
        payload = candidate.to_dict()
        self.assertEqual(len(payload["gameplay"]["stages"]), 3)
        self.assertTrue(payload["gameplay"]["completed"])
        self.assertTrue(payload["headless_player_verified"])
        self.assertFalse(payload["native_player_export_certified"])
        self.assertFalse(payload["qt_gpu_certified"])
        for stage in payload["gameplay"]["stages"]:
            self.assertEqual(stage["result"], "victory")
            self.assertIn("r74_goal_key", stage["interactions"])
            self.assertIn("r74_goal_door", stage["interactions"])
            self.assertTrue(stage["completed"])
            self.assertGreater(stage["moves"], 0)
            self.assertGreater(stage["commands"], 0)
            self.assertLess(stage["commands"], 1800)
            self.assertEqual(len(stage["recording_digest"]), 64)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_materialized_encounter_and_25_gold_per_loot_unit(self):
        candidate = self.prepare()
        raw = candidate.plan.content
        from drawtemp.sdk.simulation import thaw
        actual = {m["id"]: m for m in thaw(raw)["missions"]}
        for report in candidate.encounter_reports:
            mission = actual[report["mission"]]
            enemies = [u for u in mission["units"] if u["team"] == "enemy"]
            self.assertEqual(len(enemies), report["encounter_budget"])
            self.assertEqual(len(enemies), report["spawned_enemies"])
            self.assertEqual(len({tuple(u["pos"]) for u in enemies}),
                             len(enemies))
            chests = [o for o in mission["objects"] if o["kind"] == "chest"]
            self.assertEqual(sum(chest["amount"] for chest in chests),
                             25 * report["loot_units"])
            self.assertEqual(report["real_chest_value"],
                             25 * report["loot_units"])
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_headless_player_controller_campaign_launch_and_save_resume(self):
        from drawtemp.player.controller import PlayerController
        from drawtemp.sdk.simulation import thaw
        candidate = self.prepare()
        docs = thaw(candidate.plan.content)
        content = Content.from_dict(
            docs, rules=authored_rules_for_document(docs))
        project = GameProject.from_dict(
            thaw(candidate.plan.project), content)
        with TemporaryDirectory() as folder:
            player = PlayerController(content, project,
                                      candidate.campaign_id, folder)
            state = player.new_game()
            self.assertEqual(state["screen"], "campaign")
            self.assertTrue(state["missions"])
            player.start_mission(candidate.missions[0])
            current = player.state()
            self.assertEqual(current["screen"], "battle")
            self.assertTrue(current["puzzle"]["enabled"])
            player.save(1)
            restored = PlayerController(content, project,
                                        candidate.campaign_id, folder)
            self.assertEqual(restored.load(1)["battle"], current["battle"])
            self.assertEqual(restored.session.recording(),
                             player.session.recording())
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_canonical_undo_redo_and_manual_content_save(self):
        candidate = self.prepare()
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        transition = apply_r74_player_candidate(self.controller, candidate)
        after = transition.snapshot.to_dict()
        self.assertEqual(after["revision"], self.before["revision"] + 1)
        self.assertEqual(after["content"]["missions"][:-3],
                         self.before["content"]["missions"])
        self.assertEqual(len(after["content"]["missions"]),
                         len(self.before["content"]["missions"]) + 3)
        self.assertEqual(self.session.undo().snapshot.to_dict()["content"],
                         self.before["content"])
        self.assertEqual(self.session.redo().snapshot.to_dict()["content"],
                         after["content"])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "player-dungeons.json"
            self.session.save_as(path)
            reopened = AuthoringSession.open(path).snapshot().to_dict()
            self.assertEqual(reopened["content"], after["content"])
            self.assertEqual(reopened["project"], after["project"])

    def test_strict_r15_preflight_passes_but_native_release_is_not_fabricated(self):
        candidate = self.prepare()
        self.assertTrue(candidate.export_preflight["passed"])
        self.assertFalse(candidate.export_preflight["native_runtime_included"])
        self.assertTrue(candidate.export_preflight["rights_attestations_checked"])
        with TemporaryDirectory() as folder:
            from drawtemp.sdk.simulation import thaw
            doc = AuthoringSession.new(
                thaw(candidate.plan.content), thaw(candidate.plan.project))
            path = Path(folder) / "r74.json"
            doc.save_as(path)
            report = preflight(path, require_licenses=True)
            self.assertTrue(report["passed"], report["errors"])
            runtime = Path(folder) / "runtime"
            runtime.mkdir()
            output = Path(folder) / "native-player"
            with self.assertRaises(ExportError):
                export_game(path, runtime, output, require_licenses=True,
                            release=True)
            self.assertFalse(output.exists())
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_stale_proposals_cannot_apply_and_no_existing_project_is_edited(self):
        preview = self.prepare()
        change = self.session.preview_project(
            lambda data: {**data, "title": "Other Studio edit"})
        self.session.apply(change)
        before = self.session.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            apply_r74_player_candidate(self.controller, preview)
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_changed_preflight_or_evidence_rejected_as_modified_candidate(self):
        preview = self.prepare()
        preview.gameplay["stages"][0]["result"] = "defeat"
        with self.assertRaises(DungeonAssistError) as err:
            apply_r74_player_candidate(self.controller, preview)
        self.assertEqual(err.exception.code, "modified_preview")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_zero_budget_fails_closed_without_default_enemy_fallback(self):
        proposals = self.controller.preview_variants(
            seed=74, count=3, rooms=8, branches=2, locked_goal=True,
            encounter_budget=0, loot_budget=2)
        with self.assertRaises(DungeonAssistError) as err:
            prepare_r74_player_candidate(self.controller, proposals)
        self.assertEqual(err.exception.code, "encounter_limit")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_above_supported_enemy_budget_is_not_silently_truncated(self):
        proposals = self.controller.preview_variants(
            seed=74, count=3, rooms=8, branches=2, locked_goal=True,
            encounter_budget=7, loot_budget=2)
        with self.assertRaises(DungeonAssistError) as err:
            prepare_r74_player_candidate(self.controller, proposals)
        self.assertEqual(err.exception.code, "encounter_limit")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)


if __name__ == "__main__":
    unittest.main()
