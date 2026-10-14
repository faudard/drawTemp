"""Pure preference and category tests for the existing asset library."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from sporebound.asset_browser_state import (
    AssetBrowserState, FAMILIES, collection_key, family_for,
)
from sporebound.asset_palette import ENTRIES
from sporebound.watercolor_catalog import WatercolorCatalog


class AssetBrowserStateTests(unittest.TestCase):
    def test_existing_families_include_placeable_and_gallery_assets(self):
        self.assertEqual(family_for(next(e for e in ENTRIES if e.kind == 'surface')),
                         'terrain')
        self.assertEqual(family_for(next(e for e in ENTRIES if e.kind == 'feature')),
                         'decor')
        self.assertEqual(family_for(next(e for e in ENTRIES if e.kind == 'structure')),
                         'structures')
        actor = SimpleNamespace(kind='actor', id='actor:jeanne')
        obj = SimpleNamespace(kind='object', id='object:door')
        watercolor = SimpleNamespace(kind='watercolor', id='watercolor:jeanne_idle')
        self.assertEqual(family_for(actor), 'characters')
        self.assertEqual(family_for(obj), 'interactions')
        self.assertEqual(family_for(watercolor, watercolor_group='jeanne'), 'characters')
        self.assertEqual(family_for(watercolor, watercolor_group='vfx'), 'effects')
        self.assertEqual(family_for(watercolor, watercolor_group='props'), 'decor')
        self.assertEqual(collection_key(watercolor, watercolor_group='jeanne'),
                         'watercolor-group:jeanne')
        self.assertEqual(collection_key(actor), 'actor:jeanne')
        self.assertEqual(len(FAMILIES), 6)
        self.assertTrue(WatercolorCatalog().has_metadata())

    def test_persistent_favorites_and_ordered_bounded_recents(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'map.asset-browser.json'
            prefs = AssetBrowserState.load(path)
            self.assertTrue(prefs.toggle_favorite('watercolor-group:jeanne'))
            self.assertTrue(prefs.toggle_favorite('surface:grass'))
            prefs.touch('surface:grass')
            prefs.touch('structure:Pont')
            prefs.touch('surface:grass')
            loaded = AssetBrowserState.load(path)
            self.assertEqual(loaded.recents[:2], ['surface:grass', 'structure:Pont'])
            self.assertEqual(loaded.favorites,
                             {'watercolor-group:jeanne', 'surface:grass'})
            self.assertTrue(loaded.contains('favorites', 'surface:grass', 'terrain'))
            self.assertTrue(loaded.contains('recents', 'surface:grass', 'terrain'))
            self.assertFalse(loaded.contains('terrain', 'surface:grass', 'decor'))
            self.assertFalse(loaded.toggle_favorite('surface:grass'))
            self.assertNotIn('surface:grass', AssetBrowserState.load(path).favorites)
            for i in range(40):
                loaded.touch('feature:test_' + str(i))
            self.assertEqual(len(AssetBrowserState.load(path).recents), 20)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['version'], 1)

    def test_invalid_or_stale_ui_metadata_is_ignored_not_placed(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'broken.asset-browser.json'
            path.write_text('{not json}', encoding='utf-8')
            self.assertEqual(AssetBrowserState.load(path).favorites, set())
            path.write_text(json.dumps({
                'version': 1,
                'favorites': ['watercolor-group:jeanne', None, '', 'surface:grass',
                              'surface:grass', 'x' * 300],
                'recents': ['structure:Pont', 'structure:Pont', 23, 'broken'],
            }), encoding='utf-8')
            prefs = AssetBrowserState.load(path)
            self.assertEqual(prefs.favorites,
                             {'watercolor-group:jeanne', 'surface:grass'})
            self.assertEqual(prefs.recents, ['structure:Pont'])
            self.assertFalse(prefs.contains('favorites', 'missing:asset', 'decor'))


if __name__ == '__main__':
    unittest.main()
