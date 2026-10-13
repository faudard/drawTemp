"""Tk/Xvfb test of the contextual actor and object inspector."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.entity_editing import edit_entity, get_entity, remove_entity
from sporebound.iso_actor_atlas import IsoActorAtlas
from sporebound.model import Content
from sporebound.studio_entity_inspector import EntityInspector


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a real Tk/Xvfb display')
class EntityInspectorGuiTests(unittest.TestCase):
    def test_actor_facing_pose_object_link_and_target_mode(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            mid = 'gui_entities'
            data = add_blank_mission(
                Content.load(DEFAULT_CONTENT).to_dict(), mid, 'Village', 12, 12)
            data = add_object(data, mid, 'gate', 'door', (5, 5))
            data = add_object(data, mid, 'lever', 'switch', (4, 5), link='gate')
            data = add_object(data, mid, 'ram', 'ram', (6, 5), link='gate')
            state = {'data': data, 'target': None}
            canvas = tk.Canvas(root)
            def commit(operation, kind, identifier, values):
                if operation == 'edit':
                    state['data'] = edit_entity(
                        state['data'], mid, kind, identifier, **values)
                else:
                    state['data'] = remove_entity(state['data'], mid, kind, identifier)
                return True
            def begin_target(operation, kind, identifier):
                state['target'] = (operation, kind, identifier)
                return True
            inspector = EntityInspector(
                root, snapshot=lambda: (state['data'], mid),
                actors=IsoActorAtlas(canvas), commit=commit,
                begin_target=begin_target, cell_size=lambda: 54)
            player = next(u for u in next(m for m in data['missions']
                         if m['id'] == mid)['units'] if u['team'] == 'player')
            inspector.show_at(player['pos'])
            root.update()
            inspector.vars['facing'].set('north')
            inspector.pose.set('move')
            inspector.redraw()
            self.assertIsNotNone(inspector.photo)
            inspector.apply()
            self.assertEqual(get_entity(state['data'], mid, 'actor', player['id'])['facing'],
                             (0, -1))
            inspector.target('duplicate')
            self.assertEqual(state['target'], ('duplicate', 'actor', player['id']))
            self.assertFalse(inspector.window.winfo_viewable())
            inspector.show_at((4, 5))
            self.assertTrue(inspector.rows['link'].winfo_manager())
            self.assertEqual(inspector.vars['link'].get(), 'gate')
            inspector.apply()
            self.assertEqual(get_entity(state['data'], mid, 'object', 'lever')['link'],
                             'gate')
            inspector.show_at((6, 5))
            self.assertEqual(inspector.vars['team'].get(), 'player')
            self.assertEqual(inspector.vars['power'].get(), '1')
            self.assertEqual(inspector.changes(), {})
            inspector.apply()  # No-op must not materialize default fields.
            self.assertNotIn('team', get_entity(state['data'], mid, 'object', 'ram'))
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
