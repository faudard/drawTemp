"""3.7.25E: deterministic visual prefab categories and thumbnails."""
import unittest

from sporebound.prefab_catalog import (
    CATEGORIES, PrefabCard, prefab_card, prefab_category,
    filter_prefab_cards, thumbnail_rectangles, thumbnail_model)


class PrefabCatalogTests(unittest.TestCase):
    @staticmethod
    def source(*, name='Jardin', structures=(), units=(), objects=(),
               tiles=(), groups=()):
        return {
            'name': name,
            'size': [6, 4],
            'structures': list(structures),
            'units': list(units),
            'objects': list(objects),
            'tiles': list(tiles),
            'groups': list(groups),
        }

    def test_category_precedence(self):
        self.assertEqual(prefab_category(self.source(
            tiles=[{'pos': [0, 0], 'tile': None}])), 'Décors')
        self.assertEqual(prefab_category(self.source(
            objects=[{'kind': 'chest', 'pos': [0, 0]}])), 'Interactifs')
        self.assertEqual(prefab_category(self.source(
            units=[{'pos': [0, 0]}])), 'Personnages')
        self.assertEqual(prefab_category(self.source(
            structures=[{'name': 'Maison'}])), 'Bâtiments')
        self.assertEqual(prefab_category(self.source(
            structures=[{'name': 'Pont'}])), 'Fortifications')
        self.assertEqual(prefab_category(self.source(
            structures=[{'name': 'Maison'}, {'name': 'Tour'}])), 'Quartiers')
        self.assertIn('Fortifications', CATEGORIES)

    def test_thumbnails_have_stable_geometry_and_distinct_entities(self):
        data = self.source(
            name='Entrée fortifiée',
            tiles=[{'pos': [0, 0],
                    'tile': {'surface': 'water', 'feature': ''}},
                   {'pos': [1, 1],
                    'tile': {'surface': 'grass', 'feature': 'tree'}}],
            objects=[{'id': 'lever', 'kind': 'switch', 'pos': [3, 1]}],
            units=[{'id': 'hero', 'pos': [5, 3]}])
        card = prefab_card('fortified.json', data)
        self.assertEqual(card.name, 'Entrée fortifiée')
        self.assertEqual(card.category, 'Interactifs')
        pixels = thumbnail_rectangles(card, width=160, height=90)
        self.assertEqual(len(pixels), 4)
        self.assertEqual(pixels, thumbnail_rectangles(card, 160, 90))
        self.assertTrue(all(0 <= x0 < x1 <= 160 and
                            0 <= y0 < y1 <= 90
                            for x0, y0, x1, y1, _ in pixels))
        self.assertEqual(len(set(item[4] for item in pixels)), 4)

    def test_search_and_filter_are_case_insensitive_and_preserve_order(self):
        inputs = [
            prefab_card('maison.json', self.source(
                name='Maison villageoise',
                structures=[{'name': 'Maison'}])),
            prefab_card('pont.json', self.source(
                name='Pont fortifié',
                structures=[{'name': 'Pont'}])),
            prefab_card('arbre.json', self.source(
                name='Forêt',
                tiles=[{'pos': [0, 0], 'tile': None}])),
        ]
        self.assertEqual([x.name for x in filter_prefab_cards(
            inputs, 'FORTIFIÉ')], ['Pont fortifié'])
        self.assertEqual([x.name for x in filter_prefab_cards(
            inputs, category='Décors')], ['Forêt'])
        self.assertEqual([x.name for x in filter_prefab_cards(
            inputs, category='Tous')], [x.name for x in inputs])
        self.assertEqual(filter_prefab_cards(inputs,
                                             category='UNKNOWN'), ())
        self.assertEqual(thumbnail_model(self.source()), ())
