"""Xvfb end-to-end scene cutscene -> skip -> checkpoint -> resume -> dialogue."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests_standalone.test_scene_cinematics import (
    cinematic_project, start_at_breach)
from sporebound.authored_siege_player import AuthoredSiegeController
from sporebound.studio_siege_player_app import launch


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk/Xvfb')
class SceneCinematicPlayerGUITests(unittest.TestCase):
    def test_first_cutscene_skipped_second_resumes_and_audio_closes(self):
        import tkinter as tk
        from tkinter import ttk

        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)

        def button(root, name):
            return next(w for w in widgets(root)
                        if isinstance(w, ttk.Button)
                        and w.cget('text') == name)

        content, bp, project = cinematic_project()
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'castle.game.json'
            ctl = start_at_breach(content, bp, project, path)
            errors = []

            def drive_first(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()
                    button(root, 'Passer la cinématique').invoke()
                    root.update()
                    self.assertEqual(ctl.pending_cinematic()['id'], 'army_charge')
                    self.assertIsNotNone(button(root, 'Passer la cinématique'))
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive_first), \
                 patch('tkinter.messagebox.showerror') as pop:
                launch(content, bp, project, path, controller=ctl)
                pop.assert_not_called()
            resumed = AuthoredSiegeController(content, bp, path, project=project)
            resumed.continue_game()
            self.assertEqual(resumed.pending_cinematic()['id'], 'army_charge')

            def drive_resume(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()
                    button(root, 'Passer la cinématique').invoke()
                    root.update()
                    self.assertIsNone(resumed.pending_cinematic())
                    button(root, 'Avancer').invoke()
                    root.update()
                    self.assertIsNone(resumed.active_scene())
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive_resume), \
                 patch('tkinter.messagebox.showerror') as pop:
                launch(content, bp, project, path, controller=resumed)
                pop.assert_not_called()
            self.assertEqual(errors, [])
            final = AuthoredSiegeController(content, bp, path, project=project)
            final.continue_game()
            self.assertEqual([e['kind'] for e in final.story.events],
                             ['strategic', 'cinematic', 'cinematic', 'choice'])


if __name__ == '__main__':
    unittest.main()
