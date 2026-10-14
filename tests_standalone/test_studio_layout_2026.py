"""Studio workspace layout: tab identity and contextual presentation regression."""
import os
import unittest

from sporebound.studio_layout import SECTIONS, section_for


class NavigationClassificationTests(unittest.TestCase):
    def test_every_existing_family_has_a_home(self):
        expected = {
            "Carte et combat": "Carte & monde",
            "Monde": "Carte & monde",
            "Espace projet": "Projet",
            "Données JSON": "Projet",
            "Personnages et événements": "Contenu",
            "Personnages & règles": "Contenu",
            "Graphe des missions": "Campagne",
            "Campagne & siège": "Campagne",
            "Graphe des événements": "Événements",
            "Scénario & dialogues": "Événements",
            "Arbre narratif": "Événements",
            "Conditions & variables": "Événements",
            "Cinématique": "Présentation",
            "Son & musique": "Présentation",
            "Battle Lab": "Analyse",
            "Balance Matrix": "Analyse",
            "Visual Battle Lab": "Analyse",
            "Playtest Lab": "Analyse",
        }
        for label, group in expected.items():
            with self.subTest(label=label):
                self.assertEqual(section_for(label), group)
        self.assertEqual(section_for("Un autre éditeur"), "Autres")
        self.assertEqual(len(SECTIONS), len(set(SECTIONS)))


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Needs Tk display under Xvfb")
class NavigationWidgetTests(unittest.TestCase):
    def test_switch_and_external_notebook_selection(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.studio_layout import StudioNavigation

        root = tk.Tk()
        try:
            root.geometry("1280x800")
            nav_host = ttk.Frame(root)
            nav_host.pack(fill="x")
            tools = ttk.Notebook(root)
            tools.add(ttk.Frame(tools), text="Carte & combat")
            tools.pack(fill="x")
            notebook = ttk.Notebook(root)
            notebook.pack(fill="both", expand=True)
            map_tab = ttk.Frame(notebook)
            project_tab = ttk.Frame(notebook)
            play_tab = ttk.Frame(notebook)
            notebook.add(map_tab, text="Carte et combat")
            notebook.add(project_tab, text="Espace projet")
            notebook.add(play_tab, text="Playtest Lab")

            nav = StudioNavigation(nav_host, notebook, tools, map_tab, tk, ttk)
            root.update()
            self.assertEqual(notebook.cget("style"), "Studio.TNotebook")
            self.assertEqual(nav.view.get(), "Carte et combat")
            self.assertTrue(tools.winfo_manager())
            self.assertEqual(len(notebook.tabs()), 3)

            # Cross-editor navigation is still just notebook.select().
            notebook.select(play_tab)
            root.update()
            self.assertEqual(nav.section.get(), "Analyse")
            self.assertEqual(nav.view.get(), "Playtest Lab")
            self.assertFalse(tools.winfo_manager())
            nav.choose_section("Projet")
            root.update()
            self.assertEqual(notebook.select(), str(project_tab))
            nav.choose_section("Carte & monde")
            root.update()
            self.assertEqual(notebook.select(), str(map_tab))
            self.assertTrue(tools.winfo_manager())

            nav.show_tabs.set(True)
            nav.toggle_tabs()
            self.assertEqual(notebook.cget("style"), "TNotebook")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
