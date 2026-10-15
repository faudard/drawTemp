"""R9.B: canonical branching authoring and revision-bound debugging regressions."""
from copy import deepcopy
import tempfile
import unittest
from pathlib import Path

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from sporebound.event_branch_builder import branch_recipe
from sporebound.event_composer import action, condition


class R9BranchingAndDebugTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.studio = EventStudio(self.session)

    @staticmethod
    def recipe():
        return branch_recipe(
            first_id="fight", first_label="Combattre",
            first_event="r9_fight", first_action="hazard",
            first_text="Attaquer", first_amount=5,
            second_id="talk", second_label="Parler",
            second_event="r9_talk", second_action="message",
            second_text="Jeanne négocie", second_amount=0)

    def author_fork(self, **overrides):
        values = dict(origin_event_id="r9_origin", origin_cell=[2, 3],
                      scene_id="r9_decision", title="La décision",
                      text="Quel chemin emprunter ?", branches=self.recipe(),
                      reunion_event_id="r9_reunion",
                      reunion_message="Les chemins se rejoignent",
                      speaker="Jeanne")
        values.update(overrides)
        return self.studio.create_choice_fork(MISSION, **values)

    def test_fork_is_one_atomic_cross_document_transaction(self):
        before = self.studio.documents()
        transition = self.author_fork()
        self.assertEqual(transition.kind, "event.choice-fork")
        state = self.studio.documents()
        self.assertEqual(state["project"]["story"]["during_tactical_event"][
                         MISSION + "/r9_origin"], "r9_decision")
        self.assertEqual(self.studio.event(MISSION, "r9_fight")["after_choice"],
                         {"scene": "r9_decision", "choice": "fight"})
        self.assertEqual(self.studio.event(MISSION, "r9_reunion")["after_any"],
                         ["r9_fight", "r9_talk"])
        self.assertEqual(self.session.revision, 1)
        self.studio.undo()
        self.assertEqual(self.studio.documents()["content"], before["content"])
        self.assertEqual(self.studio.documents()["project"], before["project"])
        self.studio.redo()
        self.assertEqual(self.studio.documents()["content"], state["content"])
        self.assertEqual(self.studio.documents()["project"], state["project"])

    def test_invalid_choice_ids_do_not_partially_save(self):
        baseline = self.studio.documents()
        recipe = self.recipe()
        recipe[1]["id"] = recipe[0]["id"]
        with self.assertRaises(AuthoringError):
            self.author_fork(branches=recipe)
        self.assertEqual(self.studio.documents(), baseline)
        self.assertEqual(self.session.revision, 0)

    def test_branch_qa_structural_evidence_and_detached_project(self):
        self.author_fork()
        state = self.studio.documents()
        result = self.studio.branch_qa(MISSION)
        self.assertFalse(result["replay_verified"])
        self.assertEqual(result["reports"][0]["kind"], "structural")
        self.assertTrue(any(row["event_id"] == "r9_fight"
                            for row in result["reports"][0]["guarded_events"]))
        self.assertIn("BRANCH QA", "\n".join(result["lines"]))
        self.assertEqual(self.studio.documents(), state)

    def test_choice_guard_roundtrip(self):
        self.author_fork()
        self.studio.clear_choice(MISSION, "r9_talk")
        self.assertNotIn("after_choice", self.studio.event(MISSION, "r9_talk"))
        self.studio.bind_choice(MISSION, "r9_talk", "r9_decision", "talk")
        self.assertEqual(self.studio.event(MISSION, "r9_talk")["after_choice"],
                         {"scene": "r9_decision", "choice": "talk"})

    def test_debug_step_breakpoint_and_stale_editor_revisions(self):
        self.studio.create(MISSION, "r9_debug_first", condition("tick", tick=0),
                           [action("message", text="Signal")])
        self.studio.create(MISSION, "r9_debug_next", condition("tick", tick=0),
                           [action("message", text="Réponse")])
        self.studio.link(MISSION, "r9_debug_next", "r9_debug_first")
        before = self.studio.documents()
        debug = self.studio.start_debug(MISSION, "r9_debug_first")
        self.assertEqual(debug.chain_ids(), ("r9_debug_first", "r9_debug_next"))
        self.assertFalse(debug.inspect("r9_debug_next")["passed"])
        debug.breakpoint("r9_debug_next")
        paused = debug.resume()["report"]
        self.assertEqual(paused["paused_on"], "r9_debug_next")
        self.assertEqual(paused["fired_ids"], ["r9_debug_first"])
        self.assertEqual(debug.step()["report"]["fired_ids"],
                         ["r9_debug_first", "r9_debug_next"])
        self.assertIsNone(debug.report()["report"]["replay_verified"])
        detached = debug.report()
        detached["report"]["timeline"].clear()
        self.assertEqual(len(debug.report()["report"]["timeline"]), 2)
        self.assertEqual(self.studio.documents(), before)
        self.studio.undo()
        with self.assertRaises(AuthoringError) as exc:
            debug.step()
        self.assertEqual(exc.exception.code, "stale_revision")

    def test_save_load_branch_pair_without_duplicate_documents(self):
        self.author_fork()
        with tempfile.TemporaryDirectory() as tmp:
            content_path = Path(tmp) / "branch.json"
            self.studio.save_as(content_path)
            reopened = EventStudio(AuthoringSession.open(content_path))
            self.assertEqual(reopened.event(MISSION, "r9_fight")["after_choice"]["choice"],
                             "fight")
            self.assertEqual(reopened.documents()["project"]["story"][
                "during_tactical_event"][MISSION + "/r9_origin"], "r9_decision")
            self.assertFalse(reopened.session.snapshot().dirty)


if __name__ == "__main__":
    unittest.main()
