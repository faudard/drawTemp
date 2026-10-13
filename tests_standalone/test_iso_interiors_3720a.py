"""3.7.20A — read-only interiors: persisted + legacy, rendering, undo."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import MagicMock

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_architecture import architecture_instances, draw_architecture
from sporebound.iso_interiors import interior_plan
from sporebound.iso_map import IsoGeometry
from sporebound.iso_structures import place_structure, structure_template
from sporebound.map_authoring import paste_terrain
from sporebound.model import Content


class InteriorCutawayTests(TestCase):
    MID = 'interiors_3720a'

    def setUp(self):
        content = Content.load(DEFAULT_CONTENT)
        source = add_blank_mission(content.to_dict(), self.MID,
                                   'Interior test', 16, 16)
        self.doc = Document(Content.from_dict(source))

    def scene(self):
        return Content.from_dict(self.doc.data).missions[self.MID]

    def place_house(self):
        self.doc.replace(place_structure(
            self.doc.data, self.MID, 'Maison', (3, 3)))
        scene = self.scene()
        instance = architecture_instances(scene.board, scene.structures)[0]
        return scene, instance

    def test_plan_uses_live_walkability_and_furniture(self):
        scene, house = self.place_house()
        plan = interior_plan(scene.board, house)
        self.assertEqual(len(plan.floors), 4)
        self.assertEqual(len(plan.walls), 8)
        self.assertEqual(plan.doors, frozenset({(4, 5)}))
        self.assertEqual(plan.furnishings, ())
        self.doc.paint_many(self.MID, [(4, 4)], 'feature:crate')
        scene = self.scene()
        modified = interior_plan(scene.board, house)
        self.assertIn(((4, 4), 'crate'), modified.furnishings)
        self.doc.paint_many(self.MID, [(4, 5)], 'wall')
        closed = interior_plan(self.scene().board, house)
        self.assertNotIn((4, 5), closed.floors)
        self.assertFalse(closed.doors)
        self.doc.undo()
        self.assertEqual(interior_plan(self.scene().board, house).doors,
                         frozenset({(4, 5)}))
        self.doc.redo()
        self.assertFalse(interior_plan(self.scene().board, house).doors)

    def test_manual_cutaway_skips_opaque_roof_and_draws_floors(self):
        scene, house = self.place_house()
        geometry = IsoGeometry(scene.board, 54)
        atlas = MagicMock()
        atlas.sprite.return_value = object()
        layers = {'Bâtiments': True, 'Toitures': True}
        exterior = MagicMock()
        draw_architecture(exterior, geometry, scene.board, [], None,
                          layers, atlas=atlas, structures=scene.structures)
        self.assertEqual(exterior.create_image.call_count, 1)
        self.assertFalse(any(
            'architecture_interior' in call.kwargs.get('tags', ())
            for call in exterior.create_polygon.call_args_list))

        interior = MagicMock()
        before = deepcopy(self.doc.data)
        draw_architecture(interior, geometry, scene.board, [], None,
                          {**layers, 'Intérieurs': True}, atlas=atlas,
                          structures=scene.structures)
        self.assertEqual(interior.create_image.call_count, 0)
        self.assertEqual(sum(
            'architecture_interior' in call.kwargs.get('tags', ())
            for call in interior.create_polygon.call_args_list),
            len(interior_plan(scene.board, house).floors))
        self.assertEqual(self.doc.data, before)

    def test_legacy_structures_support_same_interiors_without_migration(self):
        original = deepcopy(self.doc.data)
        legacy = paste_terrain(original, self.MID,
                               structure_template('Maison'), (3, 3))
        content = Content.from_dict(legacy)
        self.assertEqual(content.to_dict(), legacy)
        scene = content.missions[self.MID]
        self.assertEqual(scene.structures, [])
        found = architecture_instances(scene.board, scene.structures)
        self.assertEqual(len(found), 1)
        self.assertEqual(len(interior_plan(scene.board, found[0]).floors), 4)

    def test_cutaway_mode_does_not_alter_content_or_combat(self):
        scene, _ = self.place_house()
        before = deepcopy(self.doc.data)
        battle = self.doc.playtest(self.MID, seed=19)
        digest = battle.digest()
        renderer = MagicMock()
        draw_architecture(renderer, IsoGeometry(scene.board, 54),
                          scene.board, scene.units, None,
                          {'Bâtiments': True, 'Toitures': True, 'Intérieurs': True},
                          structures=scene.structures)
        self.assertEqual(self.doc.data, before)
        self.assertEqual(self.doc.playtest(self.MID, seed=19).digest(), digest)
