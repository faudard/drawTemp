"""Chapter I demo screens: Tk presentation only, no gameplay state changes.

The mixin reuses the existing PlayerController, narrative choices, ISO renderer,
session checkpoints and results. Never store its timers or projections in saves.
"""
from .jeanne_chapter1 import (
    CHAPTER_SCENE_KICKERS, chapter_auto_enemy,
    chapter_mission_card, chapter_progress,
)


class JeanneChapterUiMixin:
    def _chapter_cover(self, parent):
        """Use the actual Jeanne portrait already registered in the project."""
        from .tk_renderer import CanvasRenderer

        hero = self.ttk.Frame(parent)
        hero.pack(fill="x", pady=(0, 12))
        portrait = CanvasRenderer(
            hero, registry=self.registry,
            asset_root=self.asset_root).image("portrait", "Jeanne")
        if portrait is not None:
            from .tk_images import resize_photo
            try:
                portrait = resize_photo(portrait, 104, 104, master=hero)
            except (ValueError, self.tk.TclError):
                pass
            label = self.ttk.Label(hero, image=portrait)
            label.image = portrait
            label.pack(side="left", padx=(0, 18))
        self.ttk.Label(
            hero,
            text="Jeanne d'Arc\nLES CENDRES",
            font=("TkDefaultFont", 20, "bold"),
            justify="left").pack(side="left", anchor="center", pady=12)

    def _chapter_scene_header(self, panel, scene):
        self.ttk.Label(
            panel, text=CHAPTER_SCENE_KICKERS[scene["id"]],
            font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 9))
        notes = {
            "sc_a1_camp": (
                "Un seul compagnon pourra partir avec Jeanne. Le recrutement "
                "et l'équipement influeront réellement sur les combats."),
            "sc_a1_dilemme": (
                "Une seule voie est possible. Ce choix rendra "
                "l'autre mission inaccessible."),
            "sc_a1_fin": (
                "Dernière décision du chapitre : votre appui pour "
                "la suite sera conservé dans la sauvegarde."),
        }
        if scene["id"] in notes:
            self.ttk.Label(
                panel, text=notes[scene["id"]],
                wraplength=780).pack(anchor="w", pady=(0, 14))

    def _chapter_briefing(self, mission_id):
        """Briefing introduces an existing mission, without beginning it."""
        card = chapter_mission_card(mission_id)
        self._clear()
        self.presentation.transition("chapter_briefing")
        self._heading("ÉTAPE " + card["ordinal"] + " / 05", card["chapter"])
        board = self.ttk.Frame(self.view, padding=26)
        board.pack(fill="both", expand=True, padx=65, pady=15)
        self.ttk.Label(
            board, text=card["context"], wraplength=760,
            font=("TkDefaultFont", 14)).pack(anchor="w", pady=(4, 25))
        self.ttk.Label(
            board, text="VOTRE OBJECTIF",
            font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        self.ttk.Label(
            board, text=card["objective"], wraplength=760,
            font=("TkDefaultFont", 15, "bold")).pack(anchor="w", pady=(8, 18))
        self.ttk.Label(
            board, text="CONSEIL TACTIQUE",
            font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        self.ttk.Label(
            board, text=card["tip"], wraplength=760).pack(anchor="w", pady=(8, 23))
        self.ttk.Label(
            board, text="Vue isométrique 2.5D · Cliquez pour sélectionner "
                        "· Exécuter pour confirmer · Molette pour zoomer "
                        "· Les ennemis jouent automatiquement (désactivable).",
            wraplength=760).pack(anchor="w", pady=(0, 19))
        start = self._button(
            board, "Entrer en mission →",
            lambda: self._launch_mission(mission_id))
        start.pack(fill="x", pady=(0, 8))
        start.focus_set()
        self._button(
            board, "Revenir au camp", self.campaign_screen).pack(fill="x")

    def _chapter_ending_panel(self, progress):
        report = chapter_progress(progress)
        panel = self.ttk.Frame(self.view, padding=22)
        panel.pack(fill="both", expand=True, padx=65, pady=14)
        self.ttk.Label(
            panel, text="FIN DU CHAPITRE I",
            font=("TkDefaultFont", 21, "bold")).pack(anchor="w", pady=(2, 12))
        self.ttk.Label(
            panel, text="À Vaucouleurs, Jeanne a enfin obtenu une audience. "
                        "Elle a trouvé un compagnon, protégé les réfugiés "
                        "et choisi la manière de défendre le royaume.",
            wraplength=750, font=("TkDefaultFont", 13)).pack(
                anchor="w", pady=(0, 18))
        for title, value in (
            ("Étapes accomplies", str(report["completed"]) + " / 5"),
            ("Compagnon", report["companion"]),
            ("Décision majeure", report["branch"]),
            ("Appui pour l'avenir", report["support"]),
        ):
            self.ttk.Label(
                panel, text=title + "  ·  " + value,
                font=("TkDefaultFont", 12)).pack(anchor="w", pady=4)
        self.ttk.Label(
            panel, text="À SUIVRE — LA ROUTE D'ORLÉANS",
            font=("TkDefaultFont", 15, "bold")).pack(
                anchor="w", pady=(20, 10))
        self.ttk.Label(
            panel, text="La démonstration s'arrête ici. Votre partie et "
                        "vos choix sont conservés dans cet emplacement.",
            wraplength=750).pack(anchor="w", pady=(0, 15))
        self._button(
            panel, "Retour au menu principal",
            self.title_screen).pack(anchor="w")

    def _chapter_schedule_ai(self):
        """Schedule an enemy activation, only when it remains legal."""
        if self._chapter_enemy_job is not None:
            return
        if chapter_auto_enemy(self.player.session, self.chapter_auto_ai.get()):
            self._chapter_enemy_job = self.root.after(
                550, self._chapter_enemy_tick)

    def _chapter_enemy_tick(self):
        self._chapter_enemy_job = None
        if chapter_auto_enemy(self.player.session, self.chapter_auto_ai.get()):
            # Same rollback, validation and checkpoint as the manual button.
            self._safe(lambda: self._change(self.player.ai_turn))
