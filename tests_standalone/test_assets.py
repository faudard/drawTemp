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
            self.assertEqual(registry.resolve('hero', moved), moved / 'art/hero.png')
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
