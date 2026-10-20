"""R31.I test attestation never claims success from skipped/unexecuted suites."""
import unittest

from scripts.r31i_certify import HEADLESS, QT, verdict


class CertificationGateTests(unittest.TestCase):
    def test_a_passing_suite_requires_real_executions(self):
        self.assertEqual(verdict(
            tested=13, failures=0, errors=0, skipped=0,
            successful=True), "pass")
        self.assertEqual(verdict(
            tested=0, failures=0, errors=0, skipped=0,
            successful=True), "fail")

    def test_any_failure_error_or_skip_is_no_go(self):
        for failures, errors, skipped in ((1, 0, 0), (0, 1, 0),
                                           (0, 0, 1), (1, 2, 3)):
            with self.subTest(failures=failures, errors=errors, skipped=skipped):
                self.assertEqual(verdict(
                    tested=40, failures=failures, errors=errors,
                    skipped=skipped, successful=False), "fail")
        self.assertEqual(verdict(
            tested=12, failures=0, errors=0, skipped=1,
            successful=True), "fail")

    def test_scope_keeps_headless_and_qt_distinct(self):
        self.assertIn("tests_standalone.test_drawtemp_r31_logic_vertical_slice",
                      HEADLESS)
        self.assertIn("tests_standalone.test_drawtemp_r31_logic_campaign",
                      HEADLESS)
        self.assertIn("tests_standalone.test_drawtemp_r31_logic_variables",
                      HEADLESS)
        self.assertIn("tests_standalone.test_drawtemp_r31_logic_qt.VisualLogicQtTests",
                      QT)
        self.assertNotIn(QT[0], HEADLESS)


if __name__ == "__main__":
    unittest.main()
