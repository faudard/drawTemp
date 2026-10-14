"""R1.8: the real Tk Studio history and canonical Player gate under Xvfb.

The four edits are entered through the existing JSON authoring pane (no new UI
or synthetic command stack). Undo/redo/save are exercised through real buttons;
the Player loads the actual saved Content/GameProject pair.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import launch
from sporebound.editor_architecture import (
    EntityCommand, StructureCommand, TacticalEventCommand)
from sporebound.event_composer import save_event, action, condition
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.iso_structures import place_structure
from sporebound.model import Content
from sporebound.studio_transaction import StudioTransactionStore
from sporebound.tactical_rpg3 import authored_rules_for_document


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Run under a real Tk display/Xvfb')
class R1StudioGuiGate(unittest.TestCase):
    MID = 'r1_gui_gate'

    def prepared(self):
        content = add_blank_mission(
            Content.load(DEFAULT_CONTENT).to_dict(), self.MID, 'R1 GUI gate',
            20, 20)
        content = place_structure(content, self.MID, 'Pont', (6, 6))
        content = add_object(content, self.MID, 'r1_door_a', 'door', [3, 3])
        content = add_object(content, self.MID, 'r1_door_b', 'door', [4, 3])
        content = add_object(content, self.MID, 'r1_switch', 'switch', [2, 3],
                             link='r1_door_a')
        content = save_event(
            content, self.MID, 'r1_alarm', condition('tick', tick=8),
            [action('message', text='Défendez le pont')])
        game = GameProject.default(Content.from_dict(content)).to_dict()
        game['campaigns'][0]['start_mission'] = self.MID
        return content, game

    @staticmethod
    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from R1StudioGuiGate.walk(child)

    def test_gui_four_edits_undo_redo_save_and_player(self):
        import tkinter as tk
        from tkinter import ttk

        initial, project = self.prepared()
        actor_id = next(m for m in initial['missions']
                        if m['id'] == self.MID)['units'][0]['id']
        operations = (
            StructureCommand((6, 6), anchor=(9, 9)),
            EntityCommand('edit', 'actor', actor_id,
                          fields=(('name', 'Éclaireuse R1'),)),
            EntityCommand('edit', 'object', 'r1_switch',
                          fields=(('link', 'r1_door_b'),)),
            TacticalEventCommand('r1_alarm', condition('tick', tick=12)),
        )

        def observed(content_raw, project_raw):
            content = Content.from_dict(
                content_raw, rules=authored_rules_for_document(content_raw))
            manifest = GameProject.from_dict(project_raw, content)
            battle = GameSession.new(content, manifest, 'main', seed=42).start_mission(
                self.MID)
            mission = battle.mission
            return (
                tuple(next(s['anchor'] for s in mission.structures
                           if s['name'] == 'Pont')),
                next(u.name for u in battle.units if u.id == actor_id),
                next(o['link'] for o in mission.objects if o['id'] == 'r1_switch'),
                next(t['value'] for t in mission.triggers if t['id'] == 'r1_alarm'),
            )

        with TemporaryDirectory() as directory:
            path = Path(directory) / 'r1.json'
            store = StudioTransactionStore(path)
            store.save(initial, project)
            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = (
                        lambda *args: callback_errors.append(args))
                    root.update()
                    widgets = list(self.walk(root))
                    buttons = {}
                    for w in widgets:
                        if isinstance(w, ttk.Button):
                            buttons.setdefault(w.cget('text'), w)
                    source = next(w for w in widgets
                                  if isinstance(w, tk.Text) and
                                  '"missions"' in w.get('1.0', 'end'))
                    for name in ('Valider et appliquer', 'Annuler',
                                 'Rétablir', 'Enregistrer tout'):
                        self.assertIn(name, buttons)

                    def current():
                        return json.loads(source.get('1.0', 'end'))

                    self.assertEqual(current(), initial)
                    before_runtime = observed(current(), project)
                    original = deepcopy(current())
                    for operation in operations:
                        # Simulate authoring from the actual JSON editor and
                        # run the public Apply command (StudioHistory records).
                        candidate = operation.transform(current(), self.MID)
                        source.delete('1.0', 'end')
                        source.insert('1.0', json.dumps(
                            candidate, indent=2, ensure_ascii=False))
                        buttons['Valider et appliquer'].invoke()
                        root.update()
                        self.assertEqual(current(), candidate)

                    edited = deepcopy(current())
                    self.assertEqual(observed(edited, project),
                                     ((9, 9), 'Éclaireuse R1', 'r1_door_b', 12))

                    for _ in range(4):
                        buttons['Annuler'].invoke()
                        root.update()
                    self.assertEqual(current(), original)
                    self.assertEqual(observed(current(), project),
                                     before_runtime)

                    for _ in range(4):
                        buttons['Rétablir'].invoke()
                        root.update()
                    self.assertEqual(current(), edited)
                    self.assertEqual(observed(current(), project),
                                     ((9, 9), 'Éclaireuse R1', 'r1_door_b', 12))

                    buttons['Enregistrer tout'].invoke()
                    root.update()
                    persisted = json.loads(path.read_text(encoding='utf-8'))
                    persisted_project = json.loads(
                        store.project_path.read_text(encoding='utf-8'))
                    self.assertEqual(persisted, edited)
                    self.assertEqual(
                        observed(persisted, persisted_project),
                        ((9, 9), 'Éclaireuse R1', 'r1_door_b', 12))
                    self.assertFalse(store.pending)
                    self.assertFalse(callback_errors)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.messagebox.showerror') as showerror:
                launch(path)
                showerror.assert_not_called()


if __name__ == '__main__':
    unittest.main()
