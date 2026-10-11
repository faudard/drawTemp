"""Game Studio 4.0 end-to-end headless acceptance gates."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematics import cinematic_template, event_template
from sporebound.game_export4 import export_game
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.studio_index4 import StudioIndex


class GameStudio4Tests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.mid = next(iter(self.content.missions))

    def enriched_project(self):
        project = GameProject.from_dict(self.project.to_dict(), self.content)
        project.story = {
            'scenes': [{'id': 'intro', 'title': 'Le château',
                        'speaker': 'Jeanne', 'text': 'Aux remparts !',
                        'choices': [{'id': 'go', 'label': 'Aller'}]}],
            'entry_scenes': {'main': 'intro'},
        }
        project.cinematics = [cinematic_template(
            'opening', 'Le départ', 'campaign_start', 'main')]
        project.cinematics[0]['events'].append(
            event_template('sound', 'music', 0, 1000))
        project.cinematics[0]['events'][0]['cue'] = 'title'
        project.assets = {
            'version': 1,
            'entries': [{'id': 'music_asset', 'kind': 'sound',
                         'path': 'audio/title.ogg'}],
            'bindings': {'sound': {'title': 'music_asset'}},
        }
        project.validate(self.content)
        return project

    def test_references_and_search_are_live_and_read_only(self):
        original = self.project.to_dict()
        index = StudioIndex(self.content, self.project)
        self.assertEqual(index.search('nothing_found_999'), ())
        self.assertIn('campaign:main', index.nodes)
        self.assertIn('mission:' + self.mid,
                      [edge.target for edge in index.outgoing('campaign:main')])
        self.assertEqual(self.project.to_dict(), original)

        project = self.enriched_project()
        with TemporaryDirectory() as root:
            path = Path(root) / 'audio' / 'title.ogg'
            path.parent.mkdir()
            path.write_bytes(b'OggS' + bytes(20))
            index = StudioIndex(self.content, project)
            self.assertIn('scene:intro',
                          [edge.target for edge in index.outgoing('campaign:main')])
            self.assertIn('cinematic:opening',
                          [edge.target for edge in index.outgoing('campaign:main')])
            self.assertIn('asset:music_asset',
                          [edge.target for edge in index.outgoing('cinematic:opening')])
            self.assertTrue(index.search('château'))
            self.assertEqual(index.diagnostics(root), ())

    def test_portable_export_is_deterministic_and_contains_all_assets(self):
        project = self.enriched_project()
        with TemporaryDirectory() as root:
            base = Path(root)
            sound = base / 'audio' / 'title.ogg'
            sound.parent.mkdir()
            sound.write_bytes(b'OggS' + bytes(20))
            first = export_game(self.content, project, base, base / 'a.zip')
            second = export_game(self.content, project, base, base / 'b.zip')
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertNotIn('saves', first.read_bytes().decode('latin1').split(
                'export_manifest.json')[0].split())
            with ZipFile(first) as archive:
                names = set(archive.namelist())
                self.assertTrue({'run_game.py', 'game/content.json',
                                 'game/project.game.json', 'game/audio/title.ogg',
                                 'sporebound/player_app.py',
                                 'export_manifest.json'} <= names)
                manifest = json.loads(archive.read('export_manifest.json'))
                for name, digest in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(),
                                     digest)
                self.assertEqual(
                    json.loads(archive.read('game/project.game.json'))['title'],
                    project.title)

    def test_missing_asset_blocks_export_without_clobbering(self):
        project = self.enriched_project()
        with TemporaryDirectory() as root:
            archive = Path(root) / 'game.zip'
            archive.write_bytes(b'keep me')
            with self.assertRaises(RuleError):
                export_game(self.content, project, root, archive)
            self.assertEqual(archive.read_bytes(), b'keep me')

    def test_invalid_filename_rejected(self):
        with TemporaryDirectory() as root:
            with self.assertRaises(RuleError):
                export_game(self.content, self.project, root,
                            Path(root) / 'game.exe')


if __name__ == '__main__':
    unittest.main()
