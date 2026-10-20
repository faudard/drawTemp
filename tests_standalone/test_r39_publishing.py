"""R15 bundles with synthetic native headers exercise preflight, not execution."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.cli import main
from drawtemp.export.publishing import publication_plan, GAME_FAMILIES
from drawtemp.export.r15 import export_game, ExportError
from drawtemp.export.templates import create_template

from tests_standalone.test_r39_native import native_bytes

REV = 'a' * 40


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = create_template('blank', self.root / 'source')
        runtime = self.root / 'runtime'
        runtime.mkdir()
        self.exe = 'DrawTempPlayer.exe' if os.name == 'nt' else 'DrawTempPlayer'
        (runtime / self.exe).write_bytes(native_bytes(
            'windows-x86_64' if os.name == 'nt' else 'linux-x86_64'))
        self.bundle = export_game(source / 'game.json', runtime, self.root / 'bundle')
        self.target = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64'
        self.provenance = {
            'schema': 1, 'kind': 'drawtemp-r39-build-provenance',
            'revision': REV, 'target': self.target,
            'manifest_sha256': sha256((self.bundle / 'manifest.json').read_bytes()).hexdigest(),
            'dependencies': [{'name': 'Python', 'version': '3.12', 'license': 'PSF-2.0'}],
        }

    def plan(self, provenance=None, **kw):
        return publication_plan(self.bundle, self.provenance if provenance is None else provenance,
                                revision=kw.get('revision', REV),
                                target=kw.get('target', self.target),
                                family=kw.get('family', 'srpg'))

    def test_families_are_intent_not_certification(self):
        original = (self.bundle / 'manifest.json').read_bytes()
        for family in GAME_FAMILIES:
            result = self.plan(family=family)
            self.assertEqual(result['declared_family'], family)
            self.assertEqual(result['decision'], 'NO-GO')
            self.assertFalse(result['release_certified'])
            self.assertEqual(result['provenance_authenticity'], 'not-verified')
            self.assertTrue(result['blockers'])
        self.assertEqual(original, (self.bundle / 'manifest.json').read_bytes())
        self.assertEqual(self.plan(), self.plan())

    def test_substitution_and_tampering_rejected(self):
        bad = deepcopy(self.provenance)
        bad['manifest_sha256'] = '0' * 64
        with self.assertRaisesRegex(ExportError, 'manifest bytes'):
            self.plan(bad)
        (self.bundle / 'Player' / self.exe).write_bytes(b'tampered')
        with self.assertRaisesRegex(ExportError, 'integrity'):
            self.plan()

    def test_contract_rejections(self):
        for key, value in [('schema', True), ('revision', 'b' * 40),
                           ('dependencies', []), ('dependencies', [None]),
                           ('target', 'android-arm64')]:
            bad = deepcopy(self.provenance)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ExportError):
                self.plan(bad)
        for kw in [{'revision': 'master'}, {'target': 'web'}, {'family': 'unknown'}]:
            with self.subTest(kw=kw), self.assertRaises(ExportError):
                self.plan(**kw)
        bad = deepcopy(self.provenance)
        bad['dependencies'] *= 2
        with self.assertRaisesRegex(ExportError, 'Duplicate dependency'):
            self.plan(bad)

    def test_target_executable_mismatch(self):
        target = 'linux-x86_64' if os.name == 'nt' else 'windows-x86_64'
        bad = dict(self.provenance, target=target)
        with self.assertRaisesRegex(ExportError, 'executable identity'):
            self.plan(bad, target=target)

    def test_content_is_revalidated_after_integrity(self):
        path = self.bundle / 'game/game.json'
        path.write_text('{}')
        manifest_path = self.bundle / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        for row in manifest['files']:
            if row['path'] == 'game/game.json':
                row.update(size=path.stat().st_size, sha256=sha256(path.read_bytes()).hexdigest())
        manifest_path.write_text(json.dumps(manifest))
        self.provenance['manifest_sha256'] = sha256(manifest_path.read_bytes()).hexdigest()
        with self.assertRaises(ExportError):
            self.plan()

    def test_cli_and_duplicate_json(self):
        provenance = self.root / 'provenance.json'
        provenance.write_text(json.dumps(self.provenance))
        args = ['publish-plan', '--bundle', str(self.bundle), '--provenance', str(provenance),
                '--revision', REV, '--target', self.target, '--family', 'srpg']
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())['decision'], 'NO-GO')
        provenance.write_text('{"schema":1,"schema":1}')
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 1)


if __name__ == '__main__':
    unittest.main()
