"""Catalog stays headless and maps only to already-supported authoring tools."""
import subprocess
import sys
import unittest

from sporebound.asset_palette import ENTRIES, search_entries
from sporebound.iso_map import SURFACES, FEATURES
from sporebound.iso_structures import STRUCTURE_NAMES


class AssetPaletteTests(unittest.TestCase):
    def test_exact_existing_tool_coverage_and_unique_ids(self):
        self.assertEqual(len({e.id for e in ENTRIES}), len(ENTRIES))
        for kind, expected in [('surface', SURFACES), ('feature', FEATURES - {''}),
                               ('structure', set(STRUCTURE_NAMES))]:
            self.assertEqual({e.value for e in ENTRIES if e.kind == kind}, expected)

    def test_search_category_accents_tokens_and_empty_results(self):
        self.assertEqual([e.value for e in search_entries('PAVES', 'Sols')], ['cobble'])
        self.assertEqual([e.value for e in search_entries('vegetation roseaux')], ['reeds'])
        self.assertFalse(search_entries('Maison', 'Sols'))
        self.assertFalse(search_entries('inexistant'))
        self.assertEqual(len(search_entries(category='Structures')), 6)

    def test_footprint_tracks_real_rotation_and_effect_is_explicit(self):
        house = next(e for e in ENTRIES if e.id == 'structure:Maison')
        self.assertEqual(house.footprint(0), (4, 3))
        self.assertEqual(house.footprint(1), (3, 4))
        for entry in ENTRIES:
            self.assertTrue(entry.effect)
        self.assertIn('bloque', next(e for e in ENTRIES if e.value == 'water').effect)

    def test_catalog_import_does_not_load_tk_or_pillow(self):
        subprocess.run([sys.executable, '-c',
                        'import sys; import sporebound.asset_palette; '
                        'assert "tkinter" not in sys.modules; '
                        'assert "PIL" not in sys.modules'], check=True)
