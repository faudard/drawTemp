"""R31.G: real victory/defeat settlement, Campaign checkpoint and authoring."""
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.logic_campaign import configure_export, remove_export
from drawtemp.sdk.logic_graph import LogicGraphError
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.logic_graph_draft import LogicGraphDraft
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, IncompatibleSaveError
from sporebound.logic_campaign_bridge import EXTENSION, apply_bridge, bridge_bindings
from sporebound.logic_variables import variables_from_journal
from sporebound.model import Content, RuleError


def fixture(kill="renaud_mentor", result="victory", target="r31_gate_open", value=True):
    session = AuthoringSession.new(*reference_project())
    draft = LogicGraphDraft.new(MISSION, "quest", source_revision=0)
    draft.edit_node("message", {"kind": "despawn", "unit": kill})
    draft.add_variable_after("message", "r31_door_unlocked", value=value)
    draft.apply(session)
    session.apply(configure_export(session, MISSION, "r31_door_unlocked",
                                   target, result=result))
    snap = session.snapshot().to_dict()
    content = Content.from_dict(snap["content"])
    project = GameProject.from_dict(snap["project"], content)
    return session, content, project


def game_start(content, project):
    game = GameSession(content, project, project.campaigns[0]["id"], seed=3)
    if game.active_scene() is not None:
        game.choose_story_option("enter")
    battle = game.start_mission(MISSION)
    return game, battle


class CampaignBridgeTests(unittest.TestCase):
    def test_victory_exports_after_real_battle_end_and_restores_checkpoint(self):
        session, content, project = fixture()
        self.assertEqual(len(bridge_bindings(project)), 1)
        game = GameSession(content, project, project.campaigns[0]["id"], seed=3)
        if game.active_scene() is not None:
            game.choose_story_option("enter")
        self.assertNotIn("r31_gate_open", game.progress.story_flags)
        battle = game.start_mission(MISSION)
        self.assertEqual(battle.result, "victory")
        self.assertEqual(variables_from_journal(battle),
                         {"r31_door_unlocked": True})
        self.assertIs(game.progress.story_flags["r31_gate_open"], True)
        self.assertTrue(game.finalized)
        self.assertEqual([row["result"] for row in battle.events
                          if row["kind"] == "battle_end"], ["victory"])
        saved = game.recording()
        resumed = GameSession.from_recording(saved, content, project)
        self.assertEqual(resumed.recording(), saved)
        self.assertIs(resumed.progress.story_flags["r31_gate_open"], True)
        resumed._settle()
        self.assertEqual(resumed.recording(), saved)
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "quest.json"
            session.save_as(file)
            again = AuthoringSession.open(file)
            self.assertEqual(
                again.snapshot().to_dict()["project"]["extensions"][EXTENSION],
                project.extensions[EXTENSION])

    def test_defeat_does_not_export_victory_and_can_export_defeat(self):
        _, content, project = fixture(kill="jeanne")
        game, battle = game_start(content, project)
        self.assertEqual(battle.result, "defeat")
        self.assertTrue(game.finalized)
        self.assertNotIn("r31_gate_open", game.progress.story_flags)
        _, content, project = fixture(
            kill="jeanne", result="defeat", target="r31_defeated", value=13)
        game, battle = game_start(content, project)
        self.assertEqual(battle.result, "defeat")
        self.assertEqual(game.progress.story_flags["r31_defeated"], 13)

    def test_atomic_undo_redo_and_explicit_remove(self):
        session = AuthoringSession.new(*reference_project())
        draft = LogicGraphDraft.new(MISSION, "mapped", source_revision=0)
        draft.add_variable_after("message", "r31_potion", value=5)
        draft.apply(session)
        initial = session.snapshot().to_dict()
        plan = configure_export(session, MISSION, "r31_potion",
                                "r31_supplies", result="both")
        self.assertEqual(initial, session.snapshot().to_dict())
        session.apply(plan)
        added = session.snapshot().to_dict()
        session.undo()
        self.assertEqual(session.snapshot().to_dict(), initial)
        session.redo()
        self.assertEqual(session.snapshot().to_dict(), added)
        session.apply(remove_export(session, "r31_supplies"))
        self.assertNotIn(EXTENSION, session.snapshot().to_dict()["project"]["extensions"])

    def test_reference_catalog_sorted_unique_and_bad_binding_rejected(self):
        bindings = [
            {"mission": "beta", "source": "r31_b", "target": "r31_b_flag",
             "result": "both"},
            {"mission": "alpha", "source": "r31_a", "target": "r31_a_flag",
             "result": "victory"},
            {"mission": "beta", "source": "r31_c", "target": "r31_c_flag",
             "result": "defeat"},
        ]
        project = GameProject(extensions={
            EXTENSION: {
                "schema_version": 1,
                "data": {"bindings": bindings},
                "references": [
                    {"kind": "mission", "id": "alpha"},
                    {"kind": "mission", "id": "beta"},
                ],
            },
        })
        self.assertEqual(bridge_bindings(project), bindings)
        project.extensions[EXTENSION]["data"]["bindings"].append(None)
        with self.assertRaises(RuleError):
            bridge_bindings(project)

    def test_validation_rejects_unknown_and_malformed_bindings(self):
        session, content, project = fixture()
        original = project.to_dict()
        corruptions = [
            lambda d: d["extensions"][EXTENSION]["data"]["bindings"][0].update(
                source="r31_missing"),
            lambda d: d["extensions"][EXTENSION]["data"]["bindings"][0].update(
                target="world_flag"),
            lambda d: d["extensions"][EXTENSION]["data"]["bindings"][0].update(
                result="invalid"),
            lambda d: d["extensions"][EXTENSION]["data"]["bindings"].append(
                deepcopy(d["extensions"][EXTENSION]["data"]["bindings"][0])),
            lambda d: d["extensions"][EXTENSION]["references"].clear(),
        ]
        for modify in corruptions:
            invalid = deepcopy(original)
            modify(invalid)
            with self.assertRaises((RuleError, LogicGraphError)):
                GameProject.from_dict(invalid, content)
        before = session.snapshot().to_dict()
        with self.assertRaises((RuleError, LogicGraphError)):
            session.apply(configure_export(
                session, MISSION, "r31_door_unlocked", "r31_gate_open",
                result="both"))
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_unconfigured_and_missing_values_do_not_default_to_false(self):
        _, content, project = fixture()
        data = project.to_dict()
        del data["extensions"][EXTENSION]
        no_bridge = GameProject.from_dict(data, content)
        game, battle = game_start(content, no_bridge)
        self.assertNotIn("r31_gate_open", game.progress.story_flags)
        detached = apply_bridge(game.progress, no_bridge, battle)
        self.assertEqual(detached.story_flags, game.progress.story_flags)

    def test_checkpoint_digest_detects_changed_bridge_definition(self):
        _, content, project = fixture()
        game, _ = game_start(content, project)
        saved = game.recording()
        tampered = project.to_dict()
        tampered["extensions"][EXTENSION]["data"]["bindings"][0]["target"] = (
            "r31_other")
        other = GameProject.from_dict(tampered, content)
        with self.assertRaises(IncompatibleSaveError) as error:
            GameSession.from_recording(saved, content, other)
        self.assertEqual(error.exception.dimension, "project")

    def test_existing_flag_type_is_preserved_on_failed_export(self):
        _, content, project = fixture()
        game, battle = game_start(content, project)
        previous = deepcopy(game.progress)
        previous.story_flags["r31_gate_open"] = 22
        with self.assertRaises(RuleError):
            apply_bridge(previous, project, battle)
        self.assertEqual(previous.story_flags["r31_gate_open"], 22)


if __name__ == "__main__":
    unittest.main()
