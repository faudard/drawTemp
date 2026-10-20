"""R53.A — replay, roster ownership and fail-closed foundation tests."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.classic_party import EXTENSION
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r41_classic_party import party_fixture


def fixture():
    content, project = party_fixture()
    project.extensions[EXTENSION]["data"]["orchestration"] = {
        "version": 1, "pause_policy": "freeze_on_encounter",
        "combos": [{"id": "duo_guard", "members": ["jeanne", "margot"],
                    "modes": ["RPG_TURN", "TACTICAL_CT"]}],
    }
    project.validate(content)
    return content, project


def recompute_checksum(data):
    data["digest"] = digest({key: value for key, value in data.items()
                             if key != "digest"})
    return data


class R53OrchestrationTests(unittest.TestCase):
    def test_recruit_active_leader_formation_and_canonical_items(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=37)
        session.progress.inventory["potion"] = 4
        session.progress.hero("jeanne").xp = 95
        self.assertEqual(session.party_orchestration_state()["leader"], "jeanne")
        self.assertEqual(session.party_orchestration_state()["eligible_combos"], [])
        session.party_recruit("margot")
        session.party_set_active(["margot", "jeanne"])
        session.party_switch_leader("margot")
        session.party_set_formation(["rear", "front"])
        state = session.party_orchestration_state()
        self.assertEqual(state["leader"], "margot")
        self.assertEqual(state["active"], ["margot", "jeanne"])
        self.assertEqual(state["formation"], ["rear", "front"])
        self.assertEqual(state["eligible_combos"], ["duo_guard"])
        self.assertEqual(session.party_orchestration_state(
            combat="ACTION_REALTIME")["eligible_combos"], [])
        self.assertEqual(session.progress.inventory["potion"], 4)
        self.assertEqual(session.progress.heroes["jeanne"].xp, 95)
        self.assertEqual(set(session.progress.heroes), {"jeanne", "margot"})

    def test_save_replay_both_journals_and_inventory_survives(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=22)
        session.party_recruit("margot")
        session.party_set_active(["jeanne", "margot"])
        session.party_switch_leader("margot")
        session.party_set_formation(["left", "front"])
        session.progress.inventory["potion"] = 2
        expected = session.recording()
        restored = GameSession.from_recording(expected, content, project)
        self.assertEqual(restored.recording(), expected)
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "r53.json"
            session.save(file)
            loaded = GameSession.load(file, content, project)
            self.assertEqual(loaded.recording(), expected)
            self.assertEqual(loaded.progress.inventory["potion"], 2)
            self.assertEqual(loaded.party_state(), session.party_state())

    def test_failed_changes_are_atomic_and_combat_freezes_edits(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main")
        original = session.recording()
        invalid = (
            lambda: session.party_switch_leader("jeanne"),
            lambda: session.party_switch_leader("margot"),
            lambda: session.party_set_formation(["front"]),
            lambda: session.party_set_formation(["front", "right"]),
            lambda: session.party_orchestration_state(combat="invalid"),
        )
        for operation in invalid:
            with self.subTest(operation=operation), self.assertRaises(RuleError):
                operation()
            self.assertEqual(session.recording(), original)
        session.party_recruit("margot")
        session.party_set_active(["jeanne", "margot"])
        session.start_mission(next(iter(content.missions)))
        encounter = session.recording()
        with self.assertRaises(RuleError):
            session.party_switch_leader("margot")
        with self.assertRaises(RuleError):
            session.party_set_formation(["front", "right"])
        self.assertEqual(session.recording(), encounter)

    def test_recomputed_checksum_cannot_forge_or_skip_r41_party_events(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main")
        session.party_recruit("margot")
        session.party_set_active(["jeanne", "margot"])
        session.party_switch_leader("margot")
        valid = session.recording()
        mutated = []
        missing = deepcopy(valid)
        del missing["party_orchestration"]
        mutated.append(missing)
        unknown = deepcopy(valid)
        unknown["party_orchestration"]["unknown"] = 10
        mutated.append(unknown)
        lying = deepcopy(valid)
        lying["party_orchestration"]["leader"] = "jeanne"
        mutated.append(lying)
        repeated = deepcopy(valid)
        repeated["party_orchestration"]["events"].append({
            "op": "active", "heroes": ["margot", "jeanne"]})
        mutated.append(repeated)
        wrong_order = deepcopy(valid)
        wrong_order["party_orchestration"]["events"][0]["heroes"] = [
            "margot", "jeanne"]
        mutated.append(wrong_order)
        missing_sync = deepcopy(valid)
        missing_sync["party_orchestration"]["events"] = [
            row for row in missing_sync["party_orchestration"]["events"]
            if row["op"] != "active"]
        mutated.append(missing_sync)
        for row in mutated:
            with self.subTest(row=row), self.assertRaises(RuleError):
                GameSession.from_recording(
                    recompute_checksum(row), content, project)
        self.assertEqual(GameSession.from_recording(
            valid, content, project).recording(), valid)

    def test_schema_rejects_unknown_fields_versions_actors_and_modes(self):
        content, project = fixture()
        errors = [
            lambda obj: obj.update(version=True),
            lambda obj: obj.update(pause_policy="continue"),
            lambda obj: obj.update(extra=1),
            lambda obj: obj.update(combos=[{
                "id": "duo", "members": ["jeanne", "unknown"],
                "modes": ["RPG_TURN"]}]),
            lambda obj: obj.update(combos=[{
                "id": "duo", "members": ["jeanne", "jeanne"],
                "modes": ["RPG_TURN"]}]),
            lambda obj: obj.update(combos=[{
                "id": "duo", "members": ["jeanne", "margot"],
                "modes": ["ACTION_REALTIME", "ACTION_REALTIME"]}]),
        ]
        for mutation in errors:
            changed = deepcopy(project)
            mutation(changed.extensions[EXTENSION]["data"]["orchestration"])
            with self.subTest(mutation=mutation), self.assertRaises(RuleError):
                changed.validate(content)

    def test_unconfigured_r41_checkpoints_remain_unchanged(self):
        content, project = party_fixture()
        legacy = GameSession.new(content, project, "main", seed=23)
        data = legacy.recording()
        self.assertNotIn("party_orchestration", data)
        self.assertEqual(GameSession.from_recording(
            data, content, project).recording(), data)
        with self.assertRaises(RuleError):
            legacy.party_orchestration_state()
        forged = deepcopy(data)
        forged["party_orchestration"] = {
            "version": 1, "active": ["jeanne"], "leader": "jeanne",
            "formation": ["front"], "events": []}
        with self.assertRaises(RuleError):
            GameSession.from_recording(
                recompute_checksum(forged), content, project)


if __name__ == "__main__":
    unittest.main()
