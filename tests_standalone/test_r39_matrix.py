"""Cross-platform evidence must reject conflicting declarations and expose gaps."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.cli import main
from drawtemp.export.publishing import PC_TARGETS
from drawtemp.export.publication_matrix import publication_matrix
from drawtemp.export.r15 import ExportError

REV = 'a' * 40


def report(target):
    osname, arch, _ = PC_TARGETS[target]
    return {
        'schema': 1, 'kind': 'drawtemp-r39-build-evidence', 'revision': REV,
        'target': target, 'declared_family': 'srpg',
        'manifest_sha256': ('b' if target.startswith('linux') else 'c') * 64,
        'native_header': {'format': {'Linux': 'ELF64', 'Windows': 'PE32+', 'macOS': 'Mach-O64'}[osname],
                          'architecture': arch},
        'integrity': 'passed', 'asset_rights': 'passed', 'publication_preflight': 'passed',
        'runtime_inventory': 'caller-declared',
        'environment_inventory_scope': 'installed-python-distributions-not-runtime-sbom',
        'blockers': [], 'release_certified': False, 'decision': 'NO-GO',
    }


class MatrixTests(unittest.TestCase):
    def matrix(self, reports, **kwargs):
        return publication_matrix(reports, revision=REV, family='srpg', **kwargs)

    def test_complete_matrix_keeps_release_blocked_and_hashes_separate(self):
        reports = [report(target) for target in PC_TARGETS]
        result = self.matrix(reports)
        self.assertTrue(result['matrix_complete'])
        self.assertEqual(result['publication_preflight'], 'passed')
        self.assertEqual(result['decision'], 'NO-GO')
        self.assertFalse(result['release_certified'])
        self.assertEqual(result, self.matrix(list(reversed(reports))))
        self.assertNotEqual(result['targets']['linux-x86_64']['manifest_sha256'],
                            result['targets']['windows-x86_64']['manifest_sha256'])
        reports[0]['blockers'].append('changed by caller')
        self.assertEqual(result['targets']['windows-x86_64']['blockers'], [])

    def test_three_os_do_not_imply_both_macos_architectures(self):
        reports = [report(t) for t in ('linux-x86_64', 'windows-x86_64', 'macos-arm64')]
        result = self.matrix(reports)
        self.assertEqual(result['missing_targets'], ['macos-x86_64'])
        self.assertFalse(result['matrix_complete'])
        self.assertEqual(result['publication_preflight'], 'blocked')

    def test_missing_and_blocked_are_independent(self):
        item = report('linux-x86_64')
        item.update(asset_rights='blocked', publication_preflight='blocked', blockers=['Missing rights'])
        result = self.matrix([item])
        self.assertEqual(result['blocked_targets'], ['linux-x86_64'])
        self.assertEqual(len(result['missing_targets']), 3)
        self.assertEqual(result['targets']['linux-x86_64']['blockers'], ['Missing rights'])
        self.assertEqual(len(self.matrix([])['missing_targets']), 4)

    def test_reject_revision_family_identity_and_certification_forgery(self):
        for key, value in [('revision', 'd'*40), ('declared_family', 'roguelite'),
                           ('manifest_sha256', 'invalid'), ('release_certified', True),
                           ('decision', 'GO'), ('integrity', 'failed'), ('schema', True),
                           ('native_header', {'format': 'ELF64', 'architecture': 'arm64'})]:
            item = report('linux-x86_64')
            item[key] = value
            with self.subTest(key=key), self.assertRaises(ExportError):
                self.matrix([item])

    def test_reject_duplicate_unknown_extra_fields(self):
        item = report('linux-x86_64')
        with self.assertRaisesRegex(ExportError, 'duplicate'):
            self.matrix([item, deepcopy(item)])
        item['target'] = 'android-arm64'
        with self.assertRaises(ExportError):
            self.matrix([item])
        item = report('linux-x86_64')
        item['signed'] = True
        with self.assertRaises(ExportError):
            self.matrix([item])

    def test_reject_contradictory_statuses(self):
        for fields in ({'asset_rights': 'blocked'}, {'runtime_inventory': 'not-supplied'},
                       {'blockers': ['not ready']}, {'publication_preflight': 'blocked'},
                       {'blockers': [None]}, {'asset_rights': 'skipped'}):
            item = report('linux-x86_64')
            item.update(fields)
            with self.subTest(fields=fields), self.assertRaises(ExportError):
                self.matrix([item])

    def test_explicit_subset_is_preserved_not_expanded_to_full_pc_support(self):
        result = self.matrix([report('linux-x86_64')], targets=['linux-x86_64'])
        self.assertEqual(result['required_targets'], ['linux-x86_64'])
        self.assertEqual(result['publication_preflight'], 'passed')
        self.assertEqual(result['decision'], 'NO-GO')
        for targets in ([], ['linux-x86_64']*2, ['web'], 'linux-x86_64'):
            with self.subTest(targets=targets), self.assertRaises(ExportError):
                self.matrix([], targets=targets)

    def test_cli_empty_directory_strict_mode_and_duplicate_json(self):
        with TemporaryDirectory() as tmp:
            args = ['publication-matrix', '--directory', tmp, '--revision', REV,
                    '--family', 'srpg', '--require-preflight']
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(args), 2)
            self.assertEqual(len(json.loads(output.getvalue())['missing_targets']), 4)
            folder = Path(tmp) / 'artifact-linux'
            folder.mkdir()
            (folder / 'build-evidence.json').write_text(json.dumps(report('linux-x86_64')))
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(args + ['--targets', 'linux-x86_64']), 0)
            self.assertFalse(json.loads(output.getvalue())['release_certified'])
            (folder / 'build-evidence.json').write_text('{"schema":1,"schema":1}')
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 1)


if __name__ == '__main__':
    unittest.main()
