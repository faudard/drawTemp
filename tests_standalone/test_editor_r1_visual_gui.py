"""R1.9 — visual Studio interactions, not just the JSON pane.

Runs in the existing Linux Tk/Xvfb editor CI job. Uses real map pointer
events, an entity inspector, a contextual gate-event wizard and history UI.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.editor import launch
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content
from sporebound.studio_transaction import StudioTransactionStore
from sporebound.tactical_rpg3 import authored_rules_for_document
from tests_standalone.test_editor_r1_gui_gate import R1StudioGuiGate


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk display and Xvfb')
class VisualR1Acceptance(unittest.TestCase):
    MID = R1StudioGuiGate.MID

    @staticmethod
    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from VisualR1Acceptance.walk(child)

    def test_pointer_inspector_gate_wizard_and_one_step_cross_document_undo(self):
        import tkinter as tk
        from tkinter import ttk

        initial, project = R1StudioGuiGate.prepared(self)
        actor = next(m for m in initial['missions'] if m['id'] == self.MID)['units'][0]
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'visual.json'
            store = StudioTransactionStore(path)
            store.save(initial, project)
            callback_errors = []

            def drive(root):
                try:
                    root.geometry('1500x1000')
                    root.report_callback_exception = (
                        lambda *err: callback_errors.append(err))
                    root.update()
                    widgets = list(self.walk(root))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    sources = [w for w in widgets
                               if isinstance(w, tk.Text) and
                               '"missions"' in w.get('1.0', 'end')]
                    self.assertEqual(len(sources), 1)
                    source = sources[0]
                    self.assertTrue(all(x in buttons for x in (
                        'Annuler', 'Rétablir', 'Enregistrer tout',
                        'Créer événement lié à la porte')))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    mission_box = next(w for w in widgets
                                       if isinstance(w, ttk.Combobox)
                                       and self.MID in w['values'])
                    tool_box = next(w for w in widgets
                                    if isinstance(w, ttk.Combobox)
                                    and 'Sélection structure' in w['values'])
                    iso = next(w for w in widgets
                               if isinstance(w, ttk.Checkbutton) and
                               w.cget('text') == 'Vue isométrique 2.5D')
                    if bool(int(iso.getvar(iso.cget('variable')))):
                        iso.invoke()
                    mission_box.set(self.MID)
                    mission_box.event_generate('<<ComboboxSelected>>')
                    root.update()
                    canvas.xview_moveto(0)
                    canvas.yview_moveto(0)

                    def content():
                        return json.loads(source.get('1.0', 'end'))

                    def mission():
                        return next(m for m in content()['missions']
                                    if m['id'] == self.MID)

                    def cell_event(sequence, x, y):
                        canvas.event_generate(sequence, x=x * 54 + 15,
                                              y=y * 54 + 15)
                        root.update()

                    def click(x, y):
                        cell_event('<Button-1>', x, y)
                        cell_event('<ButtonRelease-1>', x, y)

                    def inspector(kind, entity_id, pos):
                        tool_box.set('Inspecter entité')
                        click(*pos)
                        dialog = next(w for w in root.winfo_children()
                                      if isinstance(w, tk.Toplevel) and
                                      w.title() == 'Inspecteur — Acteurs et objets')
                        selector = next(w for w in self.walk(dialog)
                                        if isinstance(w, ttk.Combobox)
                                        and f'{kind}:{entity_id}' in w['values'])
                        selector.set(f'{kind}:{entity_id}')
                        selector.event_generate('<<ComboboxSelected>>')
                        root.update()
                        return dialog

                    def form_field(dialog, label):
                        caption = next(w for w in self.walk(dialog)
                                       if isinstance(w, ttk.Label)
                                       and w.cget('text') == label)
                        return next(w for w in caption.master.winfo_children()
                                    if isinstance(w, (ttk.Entry, ttk.Combobox)))

                    def apply_inspector(dialog):
                        apply = next(w for w in self.walk(dialog)
                                     if isinstance(w, ttk.Button) and
                                     w.cget('text') == 'Appliquer')
                        apply.invoke()
                        root.update()
                        self.assertFalse(callback_errors)

                    snapshots = [deepcopy(content())]
                    self.assertEqual(mission()['structures'][-1]['anchor'], [6, 6])

                    # 1. True mouse down, drag and release on the multi-cell bridge.
                    tool_box.set('Sélection structure')
                    cell_event('<Button-1>', 6, 6)
                    cell_event('<B1-Motion>', 8, 8)
                    cell_event('<ButtonRelease-1>', 8, 8)
                    self.assertEqual(mission()['structures'][-1]['anchor'], [8, 8])
                    snapshots.append(deepcopy(content()))

                    # 2. Edit the actor through its real visual inspector.
                    dialog = inspector('actor', actor['id'], actor['pos'])
                    name = form_field(dialog, 'Nom')
                    name.delete(0, 'end')
                    name.insert(0, 'Jeanne · inspecteur R1.9')
                    apply_inspector(dialog)
                    self.assertEqual(next(u['name'] for u in mission()['units']
                                          if u['id'] == actor['id']),
                                     'Jeanne · inspecteur R1.9')
                    snapshots.append(deepcopy(content()))

                    # 3. Relink the switch using the dropdown populated from
                    # the very same mission's two door IDs.
                    dialog = inspector('object', 'r1_switch', (2, 3))
                    target = form_field(dialog, 'Porte cible')
                    self.assertIn('r1_door_b', target['values'])
                    target.set('r1_door_b')
                    apply_inspector(dialog)
                    self.assertEqual(next(o['link'] for o in mission()['objects']
                                          if o['id'] == 'r1_switch'),
                                     'r1_door_b')
                    snapshots.append(deepcopy(content()))

                    # 4. Open the contextual gate wizard FROM the map and
                    # commit a tactical trigger + cinematic in one history item.
                    tool_box.set('Sélection')
                    click(4, 3)
                    buttons['Créer événement lié à la porte'].invoke()
                    root.update()
                    danger = next(w for w in self.walk(root)
                                  if isinstance(w, ttk.Label) and
                                  w.cget('text') == 'Case danger (x,y)')
                    # Studio form fields share a parent: select the exact
                    # entry in the same grid row as its caption.
                    danger_row = int(danger.grid_info()['row'])
                    danger_field = next(
                        w for w in danger.master.grid_slaves(row=danger_row,
                                                             column=1)
                        if isinstance(w, ttk.Entry))
                    danger_field.delete(0, 'end')
                    danger_field.insert(0, '12,12')
                    buttons['Créer et simuler'].invoke()
                    root.update()
                    eid = 'open_r1_door_b'
                    clip_id = 'cin_' + eid
                    self.assertIn(eid, {e['id'] for e in mission()['triggers']})
                    snapshots.append(deepcopy(content()))

                    # Saving exposes the other side of the single transaction:
                    # GameProject must contain its referenced cinematic.
                    buttons['Enregistrer tout'].invoke()
                    root.update()
                    saved_project = json.loads(
                        store.project_path.read_text(encoding='utf-8'))
                    self.assertIn(clip_id,
                                  {c['id'] for c in saved_project['cinematics']})
                    observed = Content.from_dict(
                        content(), rules=authored_rules_for_document(content()))
                    battle = GameSession.new(
                        observed, GameProject.from_dict(saved_project, observed),
                        'main', seed=42).start_mission(self.MID)
                    self.assertIn(eid, {e['id'] for e in battle.mission.triggers})

                    # Undo event: Content trigger and GameProject cinematic must
                    # disappear together, not in two unrelated history steps.
                    buttons['Annuler'].invoke()
                    root.update()
                    self.assertEqual(content(), snapshots[3])
                    buttons['Enregistrer tout'].invoke()
                    root.update()
                    project_after_undo = json.loads(store.project_path.read_text(
                        encoding='utf-8'))
                    self.assertNotIn(clip_id, {c['id'] for c in
                                               project_after_undo.get('cinematics', [])})
                    for expected in reversed(snapshots[:3]):
                        buttons['Annuler'].invoke()
                        root.update()
                        self.assertEqual(content(), expected)
                    for expected in snapshots[1:]:
                        buttons['Rétablir'].invoke()
                        root.update()
                        self.assertEqual(content(), expected)
                    buttons['Enregistrer tout'].invoke()
                    root.update()
                    self.assertEqual(
                        json.loads(path.read_text(encoding='utf-8')),
                        snapshots[-1])
                    restored = json.loads(store.project_path.read_text(
                        encoding='utf-8'))
                    self.assertIn(clip_id,
                                  {c['id'] for c in restored['cinematics']})
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
