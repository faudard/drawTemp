"""R57 non-certifying translation QA evidence and CLI gate."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.localization import seeded_for_project
from drawtemp.localization.qa import audit_project, main
from tests_standalone.test_drawtemp5_r57 import PROJECT


class R57CoverageGateTests(unittest.TestCase):
    def full_catalog(self, project=None):
        project = project or PROJECT
        catalog, _ = seeded_for_project(project)
        for key, entry in sorted(catalog.data["entries"].items()):
            catalog = catalog.with_translation(
                key, "en", entry["source"] + " EN")
        return catalog

    def test_missing_and_stale_sources_are_failing_evidence(self):
        cat, _ = seeded_for_project(PROJECT)
        report = audit_project(PROJECT, cat)
        self.assertFalse(report["automated_pass"])
        self.assertGreater(report["keys_total"], 0)
        self.assertEqual(report["keys_translated"], 0)
        self.assertIn({"key": "project.title", "kind": "missing"},
                      report["issues"])
        self.assertEqual(report["rtl_pseudo_failures"], [])
        valid = self.full_catalog()
        changed = dict(PROJECT, title="Changement de titre")
        stale = audit_project(changed, valid)
        self.assertFalse(stale["automated_pass"])
        self.assertIn("project.title", stale["source_drift"])

    def test_full_two_language_coverage_passes_automated_only(self):
        report = audit_project(PROJECT, self.full_catalog())
        self.assertTrue(report["automated_pass"])
        self.assertEqual(report["keys_translated"], report["keys_total"])
        self.assertEqual(report["source_drift"], [])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["rtl_pseudo_failures"], [])
        self.assertIn("physical gamepad",
                      " ".join(report["manual_gates"]))
        self.assertEqual(report["target_language"], "en")

    def test_extra_legacy_catalog_keys_do_not_inflate_project_coverage(self):
        catalog = self.full_catalog()
        raw = catalog.data
        raw["entries"]["legacy.unused.button"] = {
            "source": "Ancien bouton",
            "context": "Historical UI label no longer in this GameProject",
            "max_length": 100, "translations": {},
        }
        catalog = Catalog(raw)
        report = audit_project(PROJECT, catalog)
        required_count = len(self.full_catalog().data["entries"])
        self.assertEqual(report["keys_total"], required_count)
        self.assertEqual(report["keys_translated"], required_count)
        self.assertEqual(
            report["additional_catalog_keys"], ["legacy.unused.button"])
        self.assertTrue(report["automated_pass"])

    def test_pseudo_rtl_plural_forms_use_each_forms_placeholders(self):
        from drawtemp.localization import Catalog
        catalog = self.full_catalog()
        raw = catalog.data
        raw["entries"]["catalog.count"] = {
            "source": {
                "one": "{single} article",
                "other": "{many} articles et {count} objets",
            },
            "translations": {"en": {
                "one": "{single} item",
                "other": "{many} items and {count} objects",
            }},
            "context": "Plural test", "max_length": 200,
        }
        catalog = Catalog(raw)
        # Manually authored extra catalog entries are not in the canonical
        # project's coverage denominator but remain valid runtime messages.
        self.assertIn("\u2067", catalog.render(
            "catalog.count", "qps-plocm", count=1, single="One"))
        self.assertIn("\u2069", catalog.render(
            "catalog.count", "qps-plocm", count=2, many="Many"))
        report = audit_project(PROJECT, catalog)
        self.assertEqual(report["rtl_pseudo_failures"], [])
        self.assertEqual(report["additional_catalog_keys"], ["catalog.count"])
        self.assertTrue(report["automated_pass"])

    def test_required_language_coverage_does_not_depend_on_unused_extras(self):
        from drawtemp.localization import Catalog
        source, _ = seeded_for_project(PROJECT)
        raw = source.data
        raw["entries"]["legacy.unused"] = {
            "source": "Ancien", "context": "Old",
            "max_length": 120, "translations": {"en": "Old"},
        }
        result = audit_project(PROJECT, Catalog(raw))
        self.assertEqual(result["keys_translated"], 0)
        self.assertFalse(result["automated_pass"])
        self.assertEqual(result["keys_total"],
                         len(source.data["entries"]))

    def test_nested_v2_line_keys_are_audited(self):
        project = deepcopy(PROJECT)
        project["story"]["schema_version"] = 2
        project["story"]["scenes"][0]["lines"] = [
            {"id": "first", "speaker": "Jeanne", "text": "Bonjour"},
            {"id": "reply", "speaker": "Capitaine", "text": "Salut"},
        ]
        cat = self.full_catalog(project)
        result = audit_project(project, cat)
        self.assertTrue(result["automated_pass"])
        self.assertGreaterEqual(result["keys_total"], 10)
        incomplete, _ = seeded_for_project(project)
        problem = audit_project(project, incomplete)
        self.assertIn(
            {"key": "story.intro.line.reply.text", "kind": "missing"},
            problem["issues"])

    def test_cli_json_evidence_and_non_destructive_failure(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            project_file = root / "game.game.json"
            catalog_file = root / "game.l10n.json"
            out = root / "evidence" / "r57.json"
            project_file.write_text(json.dumps(PROJECT), encoding="utf-8")
            cat = self.full_catalog()
            cat.save(catalog_file)
            src = project_file.read_bytes()
            catalog_src = catalog_file.read_bytes()
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = main([str(project_file), str(catalog_file),
                             "--json-out", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(out.read_text(encoding="utf-8"))
                            ["automated_pass"])
            self.assertEqual(src, project_file.read_bytes())
            self.assertEqual(catalog_src, catalog_file.read_bytes())
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(
                    main([str(project_file), str(catalog_file),
                          "--json-out", str(project_file)]), 2)
                self.assertEqual(
                    main([str(project_file), str(catalog_file),
                          "--json-out", str(catalog_file)]), 2)
            self.assertEqual(src, project_file.read_bytes())
            self.assertEqual(catalog_src, catalog_file.read_bytes())
            changed = dict(PROJECT, title="Changement")
            project_file.write_text(json.dumps(changed), encoding="utf-8")
            with redirect_stdout(StringIO()):
                self.assertEqual(main([str(project_file), str(catalog_file)]), 1)
            catalog_file.unlink()
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main([str(project_file), str(catalog_file)]), 2)


if __name__ == "__main__":
    unittest.main()
