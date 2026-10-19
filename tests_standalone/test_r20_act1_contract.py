"""R20.A guardrails for the canonical Jeanne production pack (no mock victories)."""
from copy import deepcopy
from pathlib import Path
import unittest

from scripts.audit_r20_act1 import audit_pack, CONTENT_PATH, PROJECT_PATH
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.game_session import GameSession


class JeanneR20ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT_PATH)
        cls.project = GameProject.load(PROJECT_PATH, cls.content)

    def test_canonical_prologue_and_act_i_authoring_pack(self):
        report = audit_pack(self.content, self.project)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["scope"], "authoring-only")
        self.assertEqual(report["missions"], 11)

    def test_branch_drift_detected_even_when_schema_is_valid(self):
        copy = deepcopy(self.project)
        scene = next(s for s in copy.story["scenes"]
                     if s["id"] == "sc_a1_dilemme")
        choice = next(c for c in scene["choices"]
                      if c["id"] == "prendre_archives")
        effect = next(e for e in choice["effects"]
                      if e["kind"] == "set_flag")
        effect["value"] = "otages"  # legal scalar, wrong narrative meaning
        copy.validate(self.content)
        report = audit_pack(self.content, copy)
        self.assertFalse(report["ok"])
        self.assertTrue(any("persistent decision" in issue
                            for issue in report["errors"]))

    def test_route_target_drift_detected_even_when_schema_is_valid(self):
        copy = deepcopy(self.project)
        scene = next(s for s in copy.story["scenes"]
                     if s["id"] == "sc_a1_dilemme")
        choice = next(c for c in scene["choices"]
                      if c["id"] == "liberer_otages")
        effect = next(e for e in choice["effects"]
                      if e["kind"] == "unlock_mission")
        effect["mission"] = "a1_04a_archives"
        copy.validate(self.content)
        report = audit_pack(self.content, copy)
        self.assertFalse(report["ok"])
        self.assertIn("Branch does not unlock expected mission a1_04b_otages",
                      report["errors"])

    def test_final_support_is_conditional_on_route(self):
        # Pure narrative fixture; this does not simulate or certify victories.
        for route, expected, forbidden in (
            ("archives", "preuve_officielle", "parole_otages"),
            ("otages", "parole_otages", "preuve_officielle"),
        ):
            with self.subTest(route=route):
                session = GameSession.new(self.content, self.project,
                                          "jeanne", seed=17)
                session.progress.story_pending = "sc_a1_fin"
                session.progress.story_flags["acte1_choix"] = route
                available = {c["id"] for c in session.available_choices()}
                self.assertIn(expected, available)
                self.assertIn("appel_de_jeanne", available)
                self.assertNotIn(forbidden, available)

    def test_missing_branch_fails_closed(self):
        copy = deepcopy(self.project)
        scene = next(s for s in copy.story["scenes"]
                     if s["id"] == "sc_a1_fin")
        choice = next(c for c in scene["choices"]
                      if c["id"] == "parole_otages")
        choice.pop("when")
        copy.validate(self.content)
        report = audit_pack(self.content, copy)
        self.assertFalse(report["ok"])
        self.assertIn("Ending must respect the authored branch: parole_otages",
                      report["errors"])


if __name__ == "__main__":
    unittest.main()
