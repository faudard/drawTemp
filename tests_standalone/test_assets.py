"""Portable, renderer-free asset contracts and failure diagnostics."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest

from sporebound.assets import AssetRegistry
from sporebound.model import RuleError


def manifest():
    return {'version': 1, 'entries': [
        {'id': 'idle', 'kind': 'animation', 'loop': True,
         'frames': [{'sprite': 'hero', 'duration_ms': 100}]},
        {'id': 'hero', 'kind': 'sprite', 'path': 'art/hero.png'},
        {'id': 'face', 'kind': 'portrait', 'path': 'art/face.png'},
        {'id': 'music', 'kind': 'sound', 'path': 'audio/music.ogg'},
        {'id': 'hit', 'kind': 'sound', 'path': 'audio/hit.wav'},
    ], 'bindings': {'sprite': {'hero': 'hero'}, 'animation': {'hero_idle': 'idle'},
                    'portrait': {'hero': 'face'}, 'sound': {'title': 'music'}}}


def populate(root):
    (root / 'art').mkdir()
    (root / 'audio').mkdir()
    for name in ('hero', 'face'):
        (root / 'art' / f'{name}.png').write_bytes(b'\x89PNG\r\n\x1a\n')
    (root / 'audio/music.ogg').write_bytes(b'OggS')
    (root / 'audio/hit.wav').write_bytes(b'RIFF\x00\x00\x00\x00WAVE')


class AssetTests(unittest.TestCase):
    def test_forward_references_and_copy_isolation(self):
        data = manifest()
        registry = AssetRegistry(data)
        data['entries'].clear()
        exported = registry.to_dict()
        exported['entries'].clear()
        entry = registry.binding('animation', 'hero_idle')
        entry['frames'].clear()
        self.assertEqual(registry.to_dict(), manifest())
        self.assertIsNone(registry.binding('sprite', 'missing'))
        with self.assertRaises(RuleError):
            registry.require_reference('hero', 'sound')

    def test_references_and_malformed_contracts(self):
        variants = [None, [], {}, {'version': 2, 'entries': [], 'bindings': {}}]
        for mutation in (
            lambda d: d['entries'].append(deepcopy(d['entries'][1])),
            lambda d: d['entries'][1].update(id='IDLE'),
            lambda d: d['entries'][0]['frames'][0].update(sprite='missing'),
            lambda d: d['entries'][0]['frames'][0].update(sprite='idle'),
            lambda d: d['entries'][0]['frames'][0].update(sprite=[]),
            lambda d: d['entries'][0]['frames'][0].update(duration_ms=True),
            lambda d: d['entries'][0].update(frames=[]),
            lambda d: d['entries'][0].update(loop=1),
            lambda d: d['entries'][1].update(kind=[]),
            lambda d: d['bindings']['sprite'].update(hero='music'),
            lambda d: d['bindings'].update(unknown={}),
        ):
            data = manifest()
            mutation(data)
            variants.append(data)
        # None explicitly requests an empty registry.
        for data in variants[1:]:
            with self.subTest(data=data), self.assertRaises(RuleError):
                AssetRegistry(data)

    def test_nonportable_paths(self):
        for path in ('../x.png', '/tmp/x.png', 'C:/x.png', 'C:x.png',
                     'art\\x.png', 'art//x.png', './x.png', 'art/../x.png',
                     'NUL.png', 'art/CON.txt', 'art./x.png', 'art/x?.png',
                     'art/x\x00.png', 'art/x.jpg', ''):
            data = manifest()
            data['entries'][1]['path'] = path
            with self.subTest(path=path), self.assertRaises(RuleError):
                AssetRegistry(data)

    def test_relocated_project_and_deterministic_diagnostics(self):
        registry = AssetRegistry(manifest())
        with TemporaryDirectory() as folder:
            root = Path(folder) / 'first'
            root.mkdir()
            populate(root)
            self.assertEqual(registry.diagnostics(root), [])
            moved = Path(folder) / 'moved'
            shutil.move(str(root), moved)
            self.assertEqual(registry.diagnostics(moved), [])
            self.assertEqual(registry.resolve('hero', moved), (moved / 'art/hero.png').resolve())
            (moved / 'art/hero.png').unlink()
            (moved / 'audio/music.ogg').write_bytes(b'not audio')
            issues = registry.diagnostics(moved)
            self.assertEqual([i['asset_id'] for i in issues], ['hero', 'music'])
            with self.assertRaises(RuleError):
                registry.resolve('idle', moved)

    def test_symlink_escape(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / 'project'
            root.mkdir()
            outside = Path(folder) / 'outside.png'
            outside.write_bytes(b'\x89PNG\r\n\x1a\n')
            try:
                (root / 'escape.png').symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest('Symlinks unavailable')
            registry = AssetRegistry({'version': 1, 'entries': [
                {'id': 'escape', 'kind': 'sprite', 'path': 'escape.png'}], 'bindings': {}})
            self.assertIn('escapes project root', registry.diagnostics(root)[0]['message'])


class ProjectAssetTests(unittest.TestCase):
    def setUp(self):
        from sporebound.__main__ import DEFAULT_CONTENT
        from sporebound.model import Content
        from sporebound.game_project import GameProject
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.load(DEFAULT_CONTENT.with_suffix('.game.json'), self.content)

    def test_old_project_serialization_and_session_replay_are_unchanged(self):
        from sporebound.__main__ import DEFAULT_CONTENT
        from sporebound.game_session import GameSession
        import json
        original = json.loads(DEFAULT_CONTENT.with_suffix('.game.json').read_text(encoding='utf-8'))
        self.assertEqual(self.project.to_dict(), original)
        self.assertNotIn('assets', self.project.to_dict())
        session = GameSession.new(self.content, self.project, 'main')
        session.start_mission('garden')
        session.execute({'kind': 'end', 'facing': [0, 1]})
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'save.json'
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.recording(), session.recording())

    def test_asset_project_roundtrip_and_headless_session(self):
        from sporebound.game_project import GameProject
        from sporebound.game_session import GameSession
        self.project.assets = manifest()
        with TemporaryDirectory() as folder:
            # Artwork deliberately absent: structural validation and replay are headless.
            path = Path(folder) / 'game.json'
            self.project.save(path, self.content)
            loaded = GameProject.load(path, self.content)
            self.assertEqual(loaded.to_dict(), self.project.to_dict())
            session = GameSession.new(self.content, loaded, 'main')
            session.start_mission('garden')
            save = Path(folder) / 'session.json'
            session.save(save)
            restored = GameSession.load(save, self.content, loaded)
            self.assertEqual(restored.recording(), session.recording())

    def test_cli_validates_project_relative_files_and_reports_all_errors(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from sporebound.__main__ import main
        import json
        self.project.assets = manifest()
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'game.json'
            self.project.save(path, self.content)
            populate(root)
            with redirect_stdout(StringIO()):
                self.assertEqual(main(['validate', '--project', str(path)]), 0)
            (root / 'art/hero.png').unlink()
            (root / 'audio/hit.wav').write_bytes(b'broken')
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(['validate', '--project', str(path)]), 1)
            errors = json.loads(output.getvalue())
            self.assertFalse(errors['valid'])
            self.assertEqual([i['asset_id'] for i in errors['assets']], ['hero', 'hit'])

    def test_invalid_project_asset_payloads(self):
        from sporebound.game_project import GameProject
        for payload in ([], None, 1, {'version': 10}):
            data = self.project.to_dict()
            data['assets'] = payload
            with self.subTest(payload=payload), self.assertRaises(RuleError):
                GameProject.from_dict(data, self.content)
