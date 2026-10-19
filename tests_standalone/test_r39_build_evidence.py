"""Build evidence must preserve missing rights/inventory as blockers, not certify."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from drawtemp.export.build_evidence import collect_build_evidence, environment_inventory, host_target
from drawtemp.export.cli import main
from drawtemp.export.r15 import ExportError, export_game
from drawtemp.export.templates import create_template
from tests_standalone.test_r39_native import native_bytes

DEPS = [{'name': 'Python', 'version': '3.12', 'license': 'PSF-2.0'}]


class BuildEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = create_template('blank', self.root / 'source')
        runtime = self.root / 'runtime'
        runtime.mkdir()
        self.target = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64'
        exe = 'DrawTempPlayer.exe' if os.name == 'nt' else 'DrawTempPlayer'
        (runtime / exe).write_bytes(native_bytes(self.target))
        self.bundle = export_game(source / 'game.json', runtime, self.root / 'bundle')
        self.output = self.root / 'evidence'

    def collect(self, **kwargs):
        with patch('drawtemp.export.build_evidence.environment_inventory', return_value=DEPS):
            return collect_build_evidence(self.bundle, self.output, revision='a'*40,
                                          target=self.target, family='srpg', **kwargs)

    def test_environment_metadata_never_substitutes_runtime_inventory(self):
        report = self.collect()
        self.assertEqual(report['publication_preflight'], 'blocked')
        self.assertEqual(report['runtime_inventory'], 'not-supplied')
        self.assertFalse((self.output / 'build-provenance.json').exists())
        self.assertEqual(json.loads((self.output / 'build-environment.json').read_text()), DEPS)

    def test_valid_dossier_is_deterministic_and_not_certified(self):
        before = (self.bundle / 'manifest.json').read_bytes()
        report = self.collect(dependencies=DEPS)
        self.assertEqual(report['publication_preflight'], 'passed')
        self.assertFalse(report['release_certified'])
        self.assertEqual(report['decision'], 'NO-GO')
        provenance = json.loads((self.output / 'build-provenance.json').read_text())
        self.assertEqual(provenance['manifest_sha256'], report['manifest_sha256'])
        self.assertEqual(before, (self.bundle / 'manifest.json').read_bytes())
        first = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.output = self.root / 'evidence-again'
        self.collect(dependencies=DEPS)
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_missing_jeanne_rights_remain_blocked(self):
        source = create_template('jeanne', self.root / 'jeanne-source')
        (source / 'asset-licenses.json').unlink(missing_ok=True)
        runtime = self.root / 'runtime'
        self.bundle = export_game(source / 'game.json', runtime, self.root / 'jeanne')
        report = self.collect(dependencies=DEPS)
        self.assertEqual(report['asset_rights'], 'blocked')
        self.assertTrue(any('asset-licenses' in error for error in report['blockers']))
        self.assertFalse((self.output / 'build-provenance.json').exists())

    def test_invalid_inventory_is_blocked_and_not_published_as_provenance(self):
        report = self.collect(dependencies=[{'name': 'unknown'}])
        self.assertEqual(report['publication_preflight'], 'blocked')
        self.assertFalse((self.output / 'build-provenance.json').exists())

    def test_tampering_and_overwrite_fail_without_publishing(self):
        self.collect()
        with self.assertRaisesRegex(ExportError, 'never overwrite'):
            self.collect()
        self.output = self.root / 'tamper-evidence'
        (self.bundle / 'game/game.json').write_text('{}')
        with self.assertRaisesRegex(ExportError, 'integrity'):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_output_inside_bundle_refused(self):
        self.output = self.bundle / 'evidence'
        with self.assertRaisesRegex(ExportError, 'outside'):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_cli_strict_exit_retains_blocker_report(self):
        args = ['build-evidence', '--bundle', str(self.bundle), '--output', str(self.output),
                '--revision', 'a'*40, '--target', self.target, '--family', 'srpg', '--require-preflight']
        with patch('drawtemp.export.build_evidence.environment_inventory', return_value=DEPS), redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 2)
        self.assertTrue((self.output / 'build-evidence.json').exists())

    def test_environment_inventory_missing_licenses_and_duplicate_names(self):
        def dist(name, license_value=None):
            return SimpleNamespace(metadata={'Name': name, 'Version': '1', 'License': license_value})
        rows = environment_inventory([dist('Z', 'UNKNOWN'), dist('A', 'MIT')])
        self.assertEqual(rows, [{'name': 'A', 'version': '1', 'license': 'MIT'},
                                {'name': 'Z', 'version': '1', 'license': None}])
        with self.assertRaisesRegex(ExportError, 'Duplicate'):
            environment_inventory([dist('a-b'), dist('A_B')])
        self.assertIsNone(environment_inventory([dist('a', 'x'*513)])[0]['license'])

    def test_host_target_never_guesses_unknown_architecture(self):
        for system, machine, expected in [('Windows', 'AMD64', 'windows-x86_64'),
                                          ('Linux', 'x86_64', 'linux-x86_64'),
                                          ('Darwin', 'arm64', 'macos-arm64')]:
            with patch('platform.system', return_value=system), patch('platform.machine', return_value=machine):
                self.assertEqual(host_target(), expected)
        with patch('platform.system', return_value='Linux'), patch('platform.machine', return_value='riscv64'):
            with self.assertRaises(ExportError):
                host_target()


if __name__ == '__main__':
    unittest.main()
