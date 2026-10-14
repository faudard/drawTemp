"""Desktop player for GameSession: campaign -> deployment -> combat -> results.

Uses Tk only at launch, and sends every player intent through PlayerController.
No game mechanics, AI rules, dice or persistence schemas live in this module.
"""
import json
import time
from pathlib import Path

from .audio_stage import AudioStage
from .exploration_view import draw_exploration, draw_story_backdrop
from .exploration_iso_view import IsoExplorationCanvas
from .game_project import GameProject
from .profile_paths import default_profile_path
from .model import Content, RuleError
from .player_controller import PlayerController
from .presentation import Camera, battle_frame, strategy_frame
from .siege import available_operations
from .tactical_actions import tactical_action_options, tactical_command
from .tactical_rpg3 import authored_rules_for_document
from .tk_renderer import CanvasRenderer
from .iso_battle_view import IsoBattleCanvas, anchored_iso_zoom
from .world_map import world_projection
from .world_map_view import draw_world_map, pick_world_mission
from .visual_motion import MotionDirector
from .player_ux import (KeyBindings, PresentationState, combat_hud,
                        clamp_selection, zoom_to, ZOOM_PRESETS)
from .player_preferences import load_preferences, save_preferences
from .player_guidance import combat_guidance
from .player_action_preview import action_preview, preview_screen_geometry
from .player_hud_layout import combat_hud_sections
from .jeanne_chapter_ui import JeanneChapterUiMixin
from .jeanne_chapter1 import (CHAPTER_SCENE_KICKERS, chapter_mission_card,
                             chapter_progress)


class PlayerApplication(JeanneChapterUiMixin):
    def __init__(self, content_path, project_path=None, profile_path=None, *, chapter_one=False):
        import tkinter as tk
        from tkinter import ttk, messagebox

        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.presentation = PresentationState()
        content_path = Path(content_path)
        project_path = (Path(project_path) if project_path is not None
                        else content_path.with_suffix(".game.json"))
        # Validate advanced formations/bosses with their opt-in rules from load.
        document = json.loads(content_path.read_text(encoding="utf-8"))
        content = Content.from_dict(document, rules=authored_rules_for_document(document))
        project = (GameProject.load(project_path, content) if project_path.is_file()
                   else GameProject.default(content))
        if chapter_one:
            from .jeanne_chapter1 import chapter_one_project
            project = chapter_one_project(content, project)
        # The opt-in chapter never shares the original prologue's save profile.
        profile_source = (project_path.with_name("jeanne.chapitre1.game.json")
                          if chapter_one else project_path)
        profile = (Path(profile_path) if profile_path is not None
                   else default_profile_path(profile_source))
        self.chapter_one = chapter_one
        preferences, self.preferences_error = load_preferences(profile)
        self.keymap = KeyBindings(preferences["keybindings"])
        self.player = PlayerController(content, project, profile)
        # Local playtest capture is opt-in, separate from savegames.
        from .playtest_telemetry import PlaytestRecorder
        self.playtest_recorder = PlaytestRecorder(content=content,
                                                  rules=self.player.rules)
        self.player.playtest = self.playtest_recorder
        self.playtest_exported_revision = -1
        self.project_path = project_path
        self.project = project
        self.registry = project.asset_registry()
        self.asset_root = project_path.parent
        self.audio = AudioStage(self.registry, self.asset_root,
                                effects_volume=project.options["effects_volume"],
                                music_volume=project.options["music_volume"])
        self.root = tk.Tk()
        self.playtest_optin = tk.BooleanVar(value=False)
        self.long_save_var = tk.BooleanVar(value=False)
        self.text_scale = tk.IntVar(value=preferences["text_scale"])
        self.high_contrast = tk.BooleanVar(value=preferences["high_contrast"])
        self.compact_hud = tk.BooleanVar(value=preferences["compact_hud"])
        self.feedback_var = tk.StringVar()
        self.guidance_enabled = tk.BooleanVar(value=chapter_one)
        self.guidance_var = tk.StringVar()
        self.guide_panel = None
        self.hud_log_visible = tk.BooleanVar(value=False)
        self.hud_sidebar_visible = tk.BooleanVar(value=True)
        self.hud_timeline_var = tk.StringVar()
        self.hud_focus_var = tk.StringVar()
        self.hud_objective_var = tk.StringVar()
        self.hud_party_var = tk.StringVar()
        self.hud_notebook = None
        self.hud_sidebar = None
        self.hud_panes = None
        self.hud_journal = None
        self.hud_party = None
        self.hud_portrait = None
        self.hud_portrait_renderer = None
        self._hud_portrait_unit = None
        self.preview_enabled = tk.BooleanVar(value=chapter_one)
        self.preview_var = tk.StringVar()
        self.preview_panel = None
        self._preview_result = None
        self._preview_hover = None
        self._preview_job = None
        self._preview_paint_key = None
        self.root.title(project.title)
        self.root.geometry("1160x820")
        self.root.minsize(800, 580)
        self.root.configure(background="#101a2b")
        self.root.attributes("-fullscreen", project.options["fullscreen"])
        self._style()
        self.view = ttk.Frame(self.root, padding=18)
        self.view.pack(fill="both", expand=True)
        self.campaign_var = tk.StringVar(value=project.campaigns[0]["id"])
        self.slot_var = tk.StringVar(value="1")
        self.action_var = tk.StringVar(value="move")
        self.level_var = tk.IntVar(value=0)
        self.unit_var = tk.StringVar()
        self.facing_var = tk.StringVar(value="south")
        self.front_var = tk.StringVar()
        self.route_var = tk.StringVar(value="breach")
        self.doctrine_var = tk.StringVar(value="hold")
        self.logistics_dest_var = tk.StringVar()
        self.logistics_transfer_dest_var = tk.StringVar()
        self.logistics_actor_var = tk.StringVar(value="reserve_1")
        self.logistics_x_var = tk.StringVar(value="1")
        self.logistics_y_var = tk.StringVar(value="1")
        self.convoy_var = tk.StringVar()
        self.selection = (0, 0)
        self.iso_view_var = tk.BooleanVar(value=True)
        self.camera = Camera(52, 8, 8)
        self.motion = MotionDirector()
        self._motion_source = None
        self._motion_frame = None
        self._motion_job = None
        self._hud_resize_job = None
        self.canvas = None
        self.renderer = None
        self.iso_renderer = None
        self.info = None
        self.cinematic = None
        # Presentation-only acknowledgements. Saved battles already contain
        # the authoritative fired trigger IDs and replay command log.
        self._seen_tactical_cinematics = {}
        self._typewriter_job = None
        self._stage_job = None
        self._world_job = None
        self._chapter_enemy_job = None
        self.chapter_auto_ai = tk.BooleanVar(value=chapter_one)
        self._resume_world_after_scene = False
        self._explore_feedback = ""
        self._explore_scene_id = None
        self._explore_zoom = None
        self._explore_pan = (0, 0)
        self._audible_scene = None
        self._closing = False
        self._pause_dialog = None
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", self._handle_escape)
        self.root.bind("<F5>", lambda event: self._game_shortcut(self._quick_save))
        self.root.bind("<F9>", lambda event: self._game_shortcut(self._quick_load))
        self.root.bind("<F3>", lambda event: self._game_shortcut(
            self._campaign_flow_inspector, campaign_only=True))
        self.title_screen()

    def _style(self):
        """Use one accessible, Jeanne-themed skin across all Player views."""
        from .player_visual_theme import apply_player_theme
        self.palette = apply_player_theme(
            self.root, self.ttk, scale=self.text_scale.get() / 100,
            high_contrast=self.high_contrast.get())

    def _clear(self):
        self._close_pause()
        self.presentation.transition(self.presentation.screen)
        if self.cinematic is not None:
            self.cinematic.close()
            self.cinematic = None
        if self._typewriter_job is not None:
            self.root.after_cancel(self._typewriter_job)
            self._typewriter_job = None
        if self._stage_job is not None:
            self.root.after_cancel(self._stage_job)
            self._stage_job = None
        if self._world_job is not None:
            self.root.after_cancel(self._world_job)
            self._world_job = None
        if self._chapter_enemy_job is not None:
            self.root.after_cancel(self._chapter_enemy_job)
            self._chapter_enemy_job = None
        if self._motion_job is not None:
            self.root.after_cancel(self._motion_job)
            self._motion_job = None
        if self._hud_resize_job is not None:
            self.root.after_cancel(self._hud_resize_job)
            self._hud_resize_job = None
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
            self._preview_job = None
        self._preview_result = None
        self._preview_hover = None
        self._preview_paint_key = None
        self._motion_frame = None
        for key in ("<Up>", "<Down>", "<Left>", "<Right>", "w", "a", "s", "d", "z", "q", "e", "r", "<space>"):
            self.root.unbind(key)
        if self.renderer:
            self.renderer.dispose()
            self.renderer = None
        if self.iso_renderer:
            self.iso_renderer.dispose()
            self.iso_renderer = None
        for child in self.view.winfo_children():
            child.destroy()
        self.view.configure(padding=18)
        self._title_menu = None
        self.canvas = None
        self.info = None
        self.guide_panel = None
        self.preview_panel = None
        self.hud_notebook = None
        self.hud_sidebar = None
        self.hud_panes = None
        self.hud_journal = None
        self.hud_party = None
        self.hud_portrait = None
        self.hud_portrait_renderer = None
        self._hud_portrait_unit = None

    def _heading(self, text, subtitle=""):
        self.ttk.Label(self.view, text=text,
                       style="Player.Title.TLabel").pack(
                           anchor="w", pady=(4, 11))
        if subtitle:
            self.ttk.Label(self.view, text=subtitle,
                           style="Player.Subtitle.TLabel").pack(
                               anchor="w", pady=(0, 12))

    def _button(self, parent, text, action, **kwargs):
        if "style" not in kwargs and text in (
                "Exécuter", "Continuer", "Nouvelle partie", "Commencer",
                "Confirmer", "Valider"):
            kwargs["style"] = "Player.Accent.TButton"
        return self.ttk.Button(parent, text=text,
                               command=lambda: self._safe(action), **kwargs)

    def _safe(self, action):
        try:
            return action()
        except (RuleError, ValueError, TypeError, OSError, KeyError,
                IndexError, StopIteration) as exc:
            self.messagebox.showerror("Action refusée", str(exc))
            return None

    def _game_shortcut(self, action, *, campaign_only=False):
        """Route player shortcuts only while playing, never in title/options."""
        if self.player.session is None or self.presentation.screen not in (
                ("campaign",) if campaign_only else ("campaign", "world", "battle")):
            return
        self._safe(action)
        return "break"

    def _handle_escape(self, event=None):
        menu = getattr(self, "_title_menu", None)
        if menu is not None and menu.overlay is not None:
            menu._close_overlay()
            return "break"
        if self.player.session is not None and self.presentation.screen in (
                "campaign", "world", "battle"):
            # The tactical Canvas uses Escape to cancel its own selection.
            if (self.presentation.screen == "battle" and self.canvas is not None
                    and event is not None and event.widget is self.canvas
                    and self.keymap.get("cancel") == "<Escape>"):
                return
            self._pause_menu()
            return "break"
        if self.presentation.screen == "title":
            self.root.attributes("-fullscreen", False)
        return "break"

    def _close_pause(self):
        dialog = getattr(self, "_pause_dialog", None)
        self._pause_dialog = None
        if dialog is not None and dialog.winfo_exists():
            dialog.grab_release()
            dialog.destroy()
        if self.canvas is not None and self.canvas.winfo_exists():
            self.canvas.focus_set()

    def _pause_menu(self):
        if self._pause_dialog is not None:
            self._close_pause()
            return
        dialog = self.tk.Toplevel(self.root)
        self._pause_dialog = dialog
        dialog.title("Pause")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.protocol("WM_DELETE_WINDOW", self._close_pause)
        dialog.bind("<Escape>", lambda _event: self._close_pause())
        panel = self.ttk.Frame(dialog, padding=22)
        panel.pack(fill="both", expand=True)
        self.ttk.Label(panel, text="PAUSE",
                       font=("TkDefaultFont", 19, "bold")).pack(pady=(0, 10))
        self.ttk.Label(panel, text="Échap : reprendre   ·   F5 : sauvegarder"
                       "   ·   F9 : charger").pack(pady=(0, 12))

        def go(action):
            self._close_pause()
            self._safe(action)

        resume = self._button(panel, "Reprendre", self._close_pause)
        resume.pack(fill="x", pady=4)
        self._button(panel, "Sauvegarder (F5)",
                     lambda: go(self._quick_save)).pack(fill="x", pady=4)
        self._button(panel, "Charger (F9)",
                     lambda: go(self._quick_load)).pack(fill="x", pady=4)
        self._button(panel, "Gestion des sauvegardes",
                     lambda: go(self.save_manager_screen)).pack(fill="x", pady=4)
        self.ttk.Checkbutton(
            panel, text="Vue isométrique 2.5D", variable=self.iso_view_var,
            command=lambda: go(self.show)).pack(anchor="w", pady=7)
        self._button(panel, "Options",
                     lambda: go(lambda: self.options_screen(
                         return_to_game=True))).pack(fill="x", pady=4)
        self._button(panel, "Menu principal",
                     lambda: go(self.title_screen)).pack(fill="x", pady=4)
        dialog.grab_set()
        resume.focus_set()

    def _quick_save(self):
        """Save the current slot using the existing validated persistence."""
        self.player.save()
        if (self.presentation.screen == "campaign"
                and self.player.session.active_scene() is not None
                and self.player.session.exploration_state() is not None):
            self._explore_feedback = "Progression sauvegardée (F5)."
            self.show()

    def _quick_load(self):
        """Reload only the active slot, with explicit confirmation."""
        if not self.messagebox.askyesno(
                "Charger la partie",
                "Recharger la dernière sauvegarde de cet emplacement ? "
                "La progression non enregistrée sera perdue."):
            return
        self.campaign_var.set(self.player.campaign_id)
        self.slot_var.set(str(self.player.slot))
        self.long_save_var.set(self.player.long_mode)
        self._load_game()

    def _change(self, action):
        action()
        if not self._show_new_tactical_cinematics():
            self.show()

    def _show_new_tactical_cinematics(self):
        """Play only newly fired authored cues, never replay on a plain redraw."""
        from .cinematics import triggered_tactical_cinematics

        session = self.player.session
        battle = session.active_battle if session is not None else None
        if battle is None:
            return False
        previous = self._seen_tactical_cinematics.get(battle.battle_id, ())
        clips, observed = triggered_tactical_cinematics(
            self.project, battle, previous)
        self._seen_tactical_cinematics[battle.battle_id] = observed
        if not clips:
            return False
        self._play_cinematic_clips(clips, self.show)
        return True

    def _acknowledge_loaded_tactical_cinematics(self):
        """A reloaded save resumes combat, not already-fired movie sequences."""
        self._seen_tactical_cinematics.clear()
        session = self.player.session
        battle = session.active_battle if session is not None else None
        if battle is not None:
            self._seen_tactical_cinematics[battle.battle_id] = set(battle.fired)

    def title_screen(self):
        """Display the cinematic menu without exposing save maintenance."""
        self._audible_scene = None
        self._resume_world_after_scene = False
        self.audio.music_for("title")
        self._clear()
        self.presentation.transition("title")
        self.view.configure(padding=0)
        from .title_menu_cinematic import CinematicTitleMenu
        self._title_menu = CinematicTitleMenu(self)

    def _authored_siege_menu(self):
        self._clear()
        self._heading("Sièges du Studio", "Jouer vos fronts, missions et événements personnalisés")
        selected = self.tk.StringVar(value=self.project.sieges[0]["id"])
        slot = self.tk.StringVar(value="1")
        frame = self.ttk.LabelFrame(self.view, text="Choisir le scénario et la sauvegarde",
                                    padding=18)
        frame.pack(fill="x", padx=100, pady=30)
        self.ttk.Combobox(frame, textvariable=selected, state="readonly",
                          values=[bp["id"] for bp in self.project.sieges],
                          width=28).pack(pady=8)
        self.ttk.Combobox(frame, textvariable=slot, state="readonly",
                          values=[str(i) for i in range(1, 10)], width=10).pack(pady=8)

        def launch_selected():
            from .studio_siege_player_app import launch
            from .tactical_rpg3 import authored_rules_for_document
            blueprint = next(bp for bp in self.project.sieges if bp["id"] == selected.get())
            content = self.player.content
            rules = authored_rules_for_document(content.to_dict())
            launch(content, blueprint, self.project, self.project_path,
                   int(slot.get()), rules=rules, master=self.root)

        self._button(frame, "Ouvrir ce siège", launch_selected).pack(
            fill="x", pady=8)
        self._button(frame, "Retour", self.title_screen).pack(
            fill="x", pady=5)

    def _open_castle(self):
        from examples.castle_vertical_slice import castle_content, castle_blueprint
        from .tactical_rpg3 import tactical_rpg_rules
        from .castle_player_app import launch as launch_castle
        save_path = self.player.profile.with_name(
            self.player.profile.stem + "_castle.json")
        return launch_castle(castle_content(), castle_blueprint(), save_path,
                             rules=tactical_rpg_rules(), master=self.root)

    def save_manager_screen(self):
        """R8.19: read-only slot browser and explicitly confirmed archive actions.

        The headless SaveManagerModel is the only source of saved-state facts.
        No file-system manipulation or replay logic is implemented in Tk.
        """
        from .save_manager import SaveManagerModel
        model = SaveManagerModel(self.player)
        self._clear()
        self.presentation.transition("title" if self.player.session is None else "campaign")
        self._heading("Gestionnaire de sauvegardes",
                      "Inspecter, comparer et restaurer sans remplacer la partie actuelle")
        toolbar = self.ttk.Frame(self.view)
        toolbar.pack(fill="x", pady=(0, 12))
        self.ttk.Label(toolbar, text="Campagne").pack(side="left", padx=(0, 8))
        campaign = self.tk.StringVar(value=(
            self.player.campaign_id or self.campaign_var.get()))
        campaign_box = self.ttk.Combobox(
            toolbar, textvariable=campaign, state="readonly",
            values=[c["id"] for c in self.project.campaigns], width=24)
        campaign_box.pack(side="left")
        self._button(toolbar, "Retour", self.show if self.player.session
                     is not None else self.title_screen).pack(side="right")
        self.ttk.Label(
            self.view, text="La restauration crée une copie sur un AUTRE slot libre."
        ).pack(anchor="w", pady=(0, 8))

        area = self.ttk.Panedwindow(self.view, orient="horizontal")
        area.pack(fill="both", expand=True)
        sidebar = self.ttk.Frame(area, padding=8)
        detail = self.ttk.Frame(area, padding=8)
        area.add(sidebar, weight=1)
        area.add(detail, weight=2)

        self.ttk.Label(sidebar, text="Emplacements · v2 et sessions longues").pack(
            anchor="w", pady=5)
        slots = self.ttk.Treeview(
            sidebar, columns=("kind", "health", "history"),
            show="tree headings", height=13, selectmode="browse")
        slots.heading("#0", text="Slot")
        slots.heading("kind", text="Type")
        slots.heading("health", text="Intégrité")
        slots.heading("history", text="Archives")
        slots.column("#0", width=74, stretch=False)
        slots.column("kind", width=80, stretch=False)
        slots.column("health", width=105, stretch=False)
        slots.column("history", width=72, anchor="center", stretch=False)
        slots.pack(fill="both", expand=True)

        self.ttk.Label(detail, text="Versions vérifiées").pack(anchor="w")
        history = self.ttk.Treeview(
            detail, columns=("mode", "digest", "integrity"),
            show="tree headings", height=7, selectmode="browse")
        history.heading("#0", text="Version")
        history.heading("mode", text="Mode")
        history.heading("digest", text="Empreinte")
        history.heading("integrity", text="État")
        history.column("#0", width=240)
        history.column("mode", width=95, stretch=False)
        history.column("digest", width=100, stretch=False)
        history.column("integrity", width=75, stretch=False)
        history.pack(fill="x", pady=(4, 6))

        self.ttk.Label(detail, text="Diagnostic et comparaison").pack(anchor="w")
        report = self.tk.Text(detail, height=11, wrap="word", borderwidth=1,
                              relief="solid", font=("TkDefaultFont", 10))
        report.pack(fill="both", expand=True, pady=5)
        report.configure(state="disabled")

        controls = self.ttk.Frame(detail)
        controls.pack(fill="x", pady=(6, 0))
        target = self.tk.StringVar(value=str(min(2, self.project.save_slots)))
        self.ttk.Label(controls, text="Copie vers slot libre").pack(side="left")
        self.ttk.Combobox(
            controls, state="readonly", textvariable=target, width=5,
            values=[str(i) for i in range(1, self.project.save_slots + 1)]
        ).pack(side="left", padx=8)

        selected = {"slot": None, "kind": None}

        def info(text):
            report.configure(state="normal")
            report.delete("1.0", "end")
            report.insert("1.0", str(text))
            report.configure(state="disabled")

        def row_key(slot, kind):
            return "%s:%s" % (slot, kind)

        def load_details(_event=None):
            focused = slots.focus()
            if not focused:
                return
            slot, kind = focused.split(":", 1)
            selected.update(slot=int(slot), kind=kind)
            state = model.inspect_slot(campaign.get(), int(slot), kind)
            for item in history.get_children():
                history.delete(item)
            items = model.history(campaign.get(), int(slot), kind)
            for item in items:
                state_text = "OK" if item["verified"] else "INVALIDE"
                mode = item.get("summary", {}).get("mode", "—")
                name = ("Actuelle" if item["id"] == "current"
                        else item["id"].replace("gen-", "")[:27])
                history.insert(
                    "", "end", iid=item["id"], text=name,
                    values=(mode, item.get("digest", "")[:12], state_text))
            problems = state.get("issues", [])
            lines = [
                "Campagne : %s · Emplacement %s · %s" %
                (campaign.get(), slot, kind),
                "Intégrité : %s" % state["status"],
                "Source : %s · Séquence : %s" %
                (state.get("source", "—"), state.get("sequence", "—")),
                "Empreinte : %s" % state.get("session_digest", "—"),
                "Archives détectées : %s" % len(state.get("archives", [])),
            ]
            if problems:
                lines.extend(["", "Anomalies :"] +
                             ["• " + message for message in problems[:8]])
            if state.get("incomplete_archives"):
                lines.append("Archives interrompues conservées pour diagnostic.")
            if kind == "v2":
                lines.append("\nLes sauvegardes v2 restent en lecture seule "
                             "dans ce gestionnaire.")
            info("\n".join(lines))
            if items:
                history.selection_set(items[0]["id"])
                history.focus(items[0]["id"])

        def refresh_slots(_event=None):
            for item in slots.get_children():
                slots.delete(item)
            for row in model.list_slots(campaign.get()):
                slots.insert("", "end", iid=row_key(row["slot"], row["kind"]),
                             text=str(row["slot"]),
                             values=("Longue" if row["kind"] == "long" else "v2",
                                     row["status"], len(row.get("archives", []))))
            preferred = row_key(int(self.slot_var.get()),
                                "long" if self.long_save_var.get() else "v2")
            if not slots.exists(preferred):
                first = slots.get_children()
                preferred = first[0] if first else None
            if preferred:
                slots.selection_set(preferred)
                slots.focus(preferred)
                load_details()

        def selected_archive():
            require_slot = selected["slot"]
            if require_slot is None or selected["kind"] != "long":
                raise RuleError("Choisir un emplacement de session longue.")
            generation = history.focus()
            if not generation or generation == "current":
                raise RuleError("Choisir une archive historique vérifiée.")
            matching = next((v for v in model.history(
                campaign.get(), require_slot, "long")
                if v["id"] == generation and v["verified"]), None)
            if matching is None:
                raise RuleError("Archive absente ou corrompue.")
            return require_slot, generation

        def compare():
            slot, generation = selected_archive()
            outcome = model.compare_archive(campaign.get(), slot, generation)
            lines = ["Comparaison avec : " + generation,
                     "Même état : " + ("oui" if outcome["same"] else "non"),
                     "", outcome["warning"], ""]
            for change in outcome["fields"]:
                lines.append("%s : %s → %s" %
                             (change["field"], change["current"],
                              change["selected"]))
            if outcome["truncated"]:
                lines.append("D'autres écarts ne sont pas affichés.")
            info("\n".join(lines))

        def archive_current():
            if selected["slot"] is None or selected["kind"] != "long":
                raise RuleError("Choisir une session longue saine.")
            if not self.messagebox.askyesno(
                    "Créer une archive",
                    "Créer une copie vérifiée du slot sélectionné, "
                    "sans modifier la partie active ?"):
                return
            manager = model._maintenance(campaign.get(), selected["slot"])
            copied = manager.archive_verified()
            self.messagebox.showinfo(
                "Archive créée", "Copie vérifiée : " + copied["name"])
            refresh_slots()

        def restore():
            slot, generation = selected_archive()
            destination = int(target.get())
            preview = model.restoration_plan(
                campaign.get(), slot, generation, destination)
            diff = preview["comparison"]
            count = len(diff["fields"])
            message = (
                "Source : slot %s / %s\n" % (slot, generation) +
                "Destination : slot %s (doit être vide)\n" % destination +
                "Mode : %s\n" % preview["summary"]["mode"] +
                "Différences visibles : %s\n\n" % count +
                diff["warning"] + "\n\n" + preview["warning"] +
                "\n\nCréer cette copie maintenant ?")
            if not self.messagebox.askyesno(
                    "Confirmer la restauration", message):
                return
            restored = model.restore_to_free_slot(
                campaign.get(), slot, generation, destination,
                expected_token=preview["token"])
            self.messagebox.showinfo(
                "Restauration vérifiée",
                "Copie créée au slot %s. La partie en cours est inchangée." %
                restored["slot"])
            self.campaign_var.set(campaign.get())
            self.slot_var.set(str(destination))
            self.long_save_var.set(True)
            refresh_slots()

        def retention():
            if selected["slot"] is None or selected["kind"] != "long":
                raise RuleError("Choisir une session longue saine.")
            manager = model._maintenance(campaign.get(), selected["slot"])
            plan = manager.retention_plan(keep=3)
            if not plan["remove"]:
                self.messagebox.showinfo(
                    "Conservation", "Aucune archive ancienne à supprimer.")
                return
            if not self.messagebox.askyesno(
                    "Conservation — suppression irréversible",
                    "%s anciennes copies seront supprimées. "
                    "Trois archives vérifiées seront conservées.\n\n%s\n\n"
                    "Les sauvegardes actives et fichiers de secours "
                    "resteront intacts. Confirmer ?" %
                    (len(plan["remove"]), "\n".join(plan["remove"]))):
                return
            manager.prune_archives(keep=3, expected_token=plan["token"])
            refresh_slots()

        slots.bind("<<TreeviewSelect>>", load_details)
        campaign_box.bind("<<ComboboxSelected>>", refresh_slots)
        actions = self.ttk.Frame(detail)
        actions.pack(fill="x", pady=(8, 0))
        self._button(actions, "Comparer", compare).pack(side="left", padx=3)
        self._button(actions, "Créer archive", archive_current).pack(
            side="left", padx=3)
        self._button(actions, "Restaurer vers slot libre", restore).pack(
            side="left", padx=3)
        self._button(actions, "Conserver 3 archives", retention).pack(
            side="left", padx=3)
        self._button(actions, "Actualiser", refresh_slots).pack(
            side="right", padx=3)
        refresh_slots()

    def _new_game(self):
        cid, slot = self.campaign_var.get(), int(self.slot_var.get())
        if self.long_save_var.get():
            # No destructive overwrite of an opt-in long-session slot.
            self.player.new_long_game(cid, slot)
        else:
            path = self.player.path_for(cid, slot)
            exists = path.exists() or path.with_name(path.name + ".bak").exists()
            if exists and not self.messagebox.askyesno("Nouvelle partie",
                                                        "Recommencer cet emplacement ?"):
                return
            self.player.new_game(cid, slot, overwrite=exists)
        self._seen_tactical_cinematics.clear()
        self._cinematic_sequence("campaign_start", cid, self.show)

    def _load_game(self):
        cid, slot = self.campaign_var.get(), int(self.slot_var.get())
        if self.long_save_var.get():
            status = self.player.inspect_long_game(cid, slot)
            if status.source == "backup" or status.degraded:
                if not self.messagebox.askyesno(
                        "Reprise après interruption",
                        "Le fichier principal est endommagé. Une sauvegarde "
                        "antérieure a été vérifiée, mais des actions récentes "
                        "peuvent manquer.\\n\\nRestaurer explicitement cette "
                        "version ? Le fichier principal sera conservé en .damaged."):
                    return
                self.player.restore_long_game(
                    cid, slot, expected_digest=status.session.recording()["digest"])
            self.player.load_long_game(cid, slot)
        else:
            self.player.load_game(cid, slot)
        self._acknowledge_loaded_tactical_cinematics()
        status = self.player.last_load_status
        if status is not None and status.source == "backup":
            self.messagebox.showwarning(
                "Récupération de sauvegarde",
                "Le fichier principal est invalide. Une copie de secours a été "
                "chargée en mémoire, sans modifier les fichiers. "
                "Une partie de la progression récente peut manquer.")
        self.show()

    def _migrate_long_game(self):
        if not self.messagebox.askyesno(
                "Migration non destructive",
                "Créer une COPIE séparée de cette sauvegarde (v1 ou v2) "
                "au format sessions longues ? L'original reste intact et "
                "les règles de jeu ne sont pas converties."):
            return
        self.player.migrate_to_long_game(
            self.campaign_var.get(), int(self.slot_var.get()))
        self.long_save_var.set(True)
        self.messagebox.showinfo(
            "Copie vérifiée", "La sauvegarde originale est conservée. "
            "La session longue utilise un autre fichier.")
        self._load_game()

    def _migrate_game(self):
        if not self.messagebox.askyesno(
                "Migration explicite",
                "Convertir la sauvegarde v1 sélectionnée vers le format v2 ? "
                "Une copie de l'original sera conservée en .bak. "
                "Les règles et les données du jeu ne seront pas converties."):
            return
        self.player.migrate_game(self.campaign_var.get(), int(self.slot_var.get()))
        self.messagebox.showinfo(
            "Migration terminée", "Sauvegarde v2 vérifiée. L'original v1 est conservé.")
        self._load_game()

    def _toggle_playtest(self):
        if self.playtest_optin.get():
            self.playtest_recorder.enable(
                self.player.session.active_battle
                if self.player.session is not None else None)
        else:
            self.playtest_recorder.disable()

    def _export_playtest(self):
        from tkinter import filedialog
        from .playtest_telemetry import save_playtest
        report = self.playtest_recorder.report()
        if not report["sessions"]:
            self.messagebox.showinfo("Playtest", "Aucune session de playtest enregistrée.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Exporter les mesures playtest localement",
            initialfile="playtest_telemetry.json",
            defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            save_playtest(path, report)
            self.playtest_exported_revision = self.playtest_recorder.revision
            self.messagebox.showinfo(
                "Playtest", "Rapport exporté localement. Aucune donnée envoyée.")

    def options_screen(self, *, return_to_game=False):
        """Single scrolling Player settings screen; development tools are opt-in."""
        import os
        from .player_ux import (ACTION_LABELS, DEFAULT_KEYS, KEY_BY_LABEL,
                                KEY_CHOICES, KEY_LABELS)

        self._clear()
        self.presentation.transition("options")
        self._heading("Options", "Affichage, son et commandes sur une seule page")

        # Fixed footer keeps navigation accessible on smaller window sizes.
        footer = self.ttk.Frame(self.view)
        footer.pack(side="bottom", fill="x", pady=(10, 0))
        scrollbar = self.ttk.Scrollbar(self.view, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        canvas = self.tk.Canvas(
            self.view, background=self.root.cget("background"),
            borderwidth=0, highlightthickness=0, yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=canvas.yview)
        body = self.ttk.Frame(canvas, padding=(4, 6, 18, 12))
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda event: canvas.itemconfigure(window, width=event.width))

        def wheel(event):
            if event.num in (4, 5):
                step = -1 if event.num == 4 else 1
            elif event.delta:
                step = -1 if event.delta > 0 else 1
            else:
                return
            canvas.yview_scroll(step * 3, "units")

        # Only labels/frames own scrolling; comboboxes retain native wheel use.
        def scroll_surface(widget):
            widget.bind("<MouseWheel>", wheel, add="+")
            widget.bind("<Button-4>", wheel, add="+")
            widget.bind("<Button-5>", wheel, add="+")

        scroll_surface(canvas)
        scroll_surface(body)

        def section(title):
            panel = self.ttk.LabelFrame(body, text=title, padding=14)
            panel.pack(fill="x", pady=(0, 12))
            scroll_surface(panel)
            return panel

        full = self.tk.BooleanVar(value=bool(self.root.attributes("-fullscreen")))
        graphics = section("Affichage")
        self.ttk.Checkbutton(graphics, text="Plein écran", variable=full).pack(
            anchor="w", pady=4)
        label = self.ttk.Label(
            graphics, text="En mode fenêtré, ajustez la taille depuis les bords de la fenêtre.")
        label.pack(anchor="w", pady=(2, 4))
        scroll_surface(label)

        effects = self.tk.IntVar(value=round(self.audio.effects_volume * 100))
        music = self.tk.IntVar(value=round(self.audio.music_volume * 100))
        audio = section("Son")
        for title, variable in (("Effets sonores", effects), ("Musique", music)):
            line = self.ttk.Frame(audio)
            line.pack(fill="x", pady=(0, 8))
            scroll_surface(line)
            header = self.ttk.Frame(line)
            header.pack(fill="x")
            scroll_surface(header)
            text = self.ttk.Label(header, text=title)
            text.pack(side="left")
            scroll_surface(text)
            percentage = self.tk.StringVar(value=f"{variable.get()} %")
            number = self.ttk.Label(header, textvariable=percentage)
            number.pack(side="right")
            scroll_surface(number)
            self.ttk.Scale(
                line, from_=0, to=100, variable=variable,
                command=lambda value, output=percentage:
                    output.set(f"{round(float(value))} %")).pack(fill="x", pady=(5, 0))

        controls = section("Commandes")
        note = self.ttk.Label(
            controls, text="Touches modifiables : flèches, A à Z, chiffres et fonctions. "
                           "Les raccourcis tactiques agissent lorsque la carte a le focus.",
            wraplength=850)
        note.pack(anchor="w", pady=(0, 10))
        scroll_surface(note)
        key_vars = {}
        choices = tuple(KEY_LABELS.get(sequence, sequence)
                        for sequence in KEY_CHOICES)
        shortcuts = self.ttk.Frame(controls)
        shortcuts.pack(fill="x")
        scroll_surface(shortcuts)
        shortcuts.columnconfigure(0, weight=1)
        shortcuts.columnconfigure(1, weight=1)
        for index, (action, sequence) in enumerate(self.keymap.items()):
            variable = self.tk.StringVar(value=KEY_LABELS.get(sequence, sequence))
            key_vars[action] = variable
            field = self.ttk.Frame(shortcuts)
            field.grid(row=index // 2, column=index % 2,
                       sticky="ew", padx=(0, 16), pady=4)
            field.columnconfigure(0, weight=1)
            scroll_surface(field)
            name = self.ttk.Label(field, text=ACTION_LABELS.get(action, action))
            name.grid(row=0, column=0, sticky="w", padx=(0, 8))
            scroll_surface(name)
            self.ttk.Combobox(
                field, state="readonly", textvariable=variable,
                values=choices, width=19).grid(row=0, column=1, sticky="e")

        def reset_keys():
            for action, sequence in DEFAULT_KEYS.items():
                key_vars[action].set(KEY_LABELS.get(sequence, sequence))

        self._button(controls, "Réinitialiser les touches", reset_keys).pack(
            anchor="e", pady=(10, 0))

        access = section("Accessibilité")
        contrast = self.tk.BooleanVar(value=self.high_contrast.get())
        compact = self.tk.BooleanVar(value=self.compact_hud.get())
        scale = self.tk.IntVar(value=self.text_scale.get())
        self.ttk.Checkbutton(access, text="Contraste renforcé",
                             variable=contrast).pack(anchor="w", pady=3)
        self.ttk.Checkbutton(access, text="HUD compact",
                             variable=compact).pack(anchor="w", pady=3)
        line = self.ttk.Frame(access)
        line.pack(anchor="w", pady=(7, 0))
        self.ttk.Label(line, text="Taille des textes").pack(side="left", padx=(0, 12))
        self.ttk.Combobox(line, state="readonly", textvariable=scale,
                          values=(100, 125, 150), width=9).pack(side="left")
        self.ttk.Label(line, text="%").pack(side="left", padx=(5, 0))

        # QA recording stays available without exposing JSON/dev jargon to players.
        if os.environ.get("DRAWTEMP_DEVELOPER_OPTIONS") == "1":
            dev = section("Outils de développement")
            self.ttk.Checkbutton(
                dev, text="Enregistrer les playtests (activation volontaire)",
                variable=self.playtest_optin,
                command=self._toggle_playtest).pack(anchor="w", pady=4)
            self._button(dev, "Exporter rapport playtest JSON",
                         self._export_playtest).pack(anchor="w", pady=4)
            if self.preferences_error:
                self.ttk.Label(dev, text=self.preferences_error,
                               wraplength=750).pack(anchor="w")

        def apply():
            assignments = {}
            for action, variable in key_vars.items():
                label = variable.get()
                if label not in KEY_BY_LABEL:
                    raise ValueError("Touche non prise en charge : " + label)
                assignments[action] = KEY_BY_LABEL[label]
            used = {}
            for action, sequence in assignments.items():
                if sequence in used:
                    raise ValueError(
                        "La touche " + KEY_LABELS[sequence] + " est attribuée à "
                        + ACTION_LABELS[used[sequence]] + " et "
                        + ACTION_LABELS[action] + ".")
                used[sequence] = action
            proposed_keys = KeyBindings(assignments)
            settings = {
                "version": 1,
                "keybindings": dict(proposed_keys.items()),
                "text_scale": scale.get(),
                "high_contrast": contrast.get(),
                "compact_hud": compact.get(),
            }
            # Retain the existing atomic sidecar and schema; cancel changes nothing.
            save_preferences(self.player.profile, settings)
            self.keymap = proposed_keys
            self.preferences_error = None
            self.text_scale.set(scale.get())
            self.high_contrast.set(contrast.get())
            self.compact_hud.set(compact.get())
            self._style()
            self.audio.effects_volume = effects.get() / 100
            self.audio.music_volume = music.get() / 100
            self.root.attributes("-fullscreen", full.get())
            self.show() if return_to_game else self.title_screen()

        self._button(footer, "Appliquer", apply).pack(side="right", padx=(8, 0))
        self._button(footer, "Retour sans enregistrer",
                     self.show if return_to_game else self.title_screen).pack(side="right")

    def show(self):
        session = self.player.session
        if session is None:
            self.title_screen()
        elif session.tactical_story_pending:
            # Story UI is modal over the current Battle, not a campaign screen.
            self._clear()
            self.presentation.transition("tactical_story")
            self._heading("Décision pendant la bataille")
            self._narrative_scene(
                session.tactical_scene(), choices=session.tactical_choices(),
                on_choice=lambda cid: self._change(
                    lambda: self.player.choose_tactical_story_option(cid)))
        elif session.mode == "fronts":
            self.battle_screen()
        elif session.mode == "battle":
            if session.finalized:
                self.results_screen()
            else:
                self.battle_screen()
        elif (self._resume_world_after_scene and self.project.world
              and session.active_scene() is None):
            self._resume_world_after_scene = False
            self.world_screen()
        else:
            self.campaign_screen()

    def _cinematic_sequence(self, kind, target, finished):
        """Play authored presentation beats without mutating the saved game."""
        from .cinematics import matching_cinematics
        from .cinematic_player import CinematicPlayback

        clips = matching_cinematics(self.project, kind, target)
        self._play_cinematic_clips(clips, finished)

    def _play_cinematic_clips(self, clips, finished):
        """Shared playback for campaign, mission, scene and tactical events."""
        from .cinematic_player import CinematicPlayback

        def next_clip(index=0, revision=None):
            if revision is not None and not self.presentation.current(revision):
                return  # A newer screen interrupted this cinematic.
            self.cinematic = None
            if index >= len(clips):
                finished()
                return
            self._clear()
            token = self.presentation.transition("cinematic")
            self.cinematic = CinematicPlayback(
                self.view, self.tk, self.ttk, clips[index],
                lambda: next_clip(index + 1, token), audio=self.audio,
                registry=self.registry, asset_root=self.asset_root)

        next_clip()

    def _start_mission_with_cinematic(self, mission_id):
        if self.chapter_one:
            return self._chapter_briefing(mission_id)
        return self._launch_mission(mission_id)

    def _launch_mission(self, mission_id):
        self._cinematic_sequence(
            "before_mission", mission_id,
            lambda: self._safe(lambda: self._change(
                lambda: self.player.start_mission(mission_id))))

    def _finish_mission_with_cinematic(self):
        battle = self.player.session.active_battle
        mission_id = battle.mission.id
        self.player.return_to_campaign()
        self._cinematic_sequence("after_mission", mission_id, self.show)

    def campaign_screen(self):
        session = self.player.session
        self._clear()
        self.presentation.transition("campaign")
        scene = session.active_scene()
        stage = session.exploration_state() if scene else None
        if stage is not None and not stage["completed"]:
            self.audio.music_for(f'music_scene_{scene["id"]}', "campaign")
            if self._audible_scene != scene["id"]:
                self.audio.cue(f'scene_enter_{scene["id"]}')
                self._audible_scene = scene["id"]
            # Exploration is a game viewport, not a Studio inspection form.
            self.view.configure(padding=0)
            self._exploration_screen(scene, stage)
            return
        self._heading(self.project.campaign(session.campaign_id)["name"],
                      "Or : " + str(session.progress.gold) +
                      "    Missions terminées : " + str(len(session.progress.completed)))
        # Pack navigation before large story content so it cannot disappear below the window.
        if self.chapter_one:
            progress = chapter_progress(session.progress)
            self.ttk.Label(
                self.view, text=f"CHAPITRE I  ·  {progress['completed']}/5 étapes "
                                f"· Compagnon : {progress['companion']}",
                font=("TkDefaultFont", 12, "bold")
            ).pack(anchor="w", pady=(0, 10))
        # Visible roster: recruitment and equipment have actual tactical effects.
        if session.progress.heroes:
            roster = self.ttk.LabelFrame(self.view, text="Équipe et progression", padding=8)
            roster.pack(fill="x", padx=60, pady=(2, 8))
            for uid, hero in sorted(session.progress.heroes.items()):
                if uid.startswith("otage_") or uid == "refugie":
                    continue
                gear = ", ".join(hero.equipment.values()) or "sans équipement"
                self.ttk.Label(roster, text=f"{uid} · niveau {hero.level} · {hero.job} · {gear}").pack(anchor="w")
            bonds = [(key[6:], value) for key, value in sorted(session.progress.story_flags.items())
                     if key.startswith("trust_") and type(value) is int]
            if bonds:
                self.ttk.Label(roster, text="Relations : " +
                    ", ".join(f"{name} {value}" for name, value in bonds)).pack(anchor="w")
        if scene:
            self.audio.music_for(f'music_scene_{scene["id"]}', "campaign")
            if self._audible_scene != scene["id"]:
                self.audio.cue(f'scene_enter_{scene["id"]}')
                self._audible_scene = scene["id"]
            self._narrative_scene(scene)
        else:
            self._audible_scene = None
            self.audio.music_for("campaign")
            available = session.available_missions()
            if self.project.world:
                self._button(self.view, "Carte du monde",
                             self.world_screen).pack(fill="x", padx=80, pady=(3, 9))
            self.ttk.Label(
                self.view, text=("PROCHAINE ÉTAPE" if self.chapter_one
                                 else "Choisir une mission :")
            ).pack(anchor="w", pady=8)
            journey = session.world_state() if self.project.world else None
            world_missions = ({node["mission"] for node in self.project.world["nodes"]}
                              if self.project.world else set())
            for mission_id in available:
                mission = self.player.content.missions[mission_id]
                if (journey is not None and mission_id in world_missions
                        and not session.world_can_enter(mission_id)):
                    self._button(self.view, mission.name + " — rejoindre sur la carte",
                                 self.world_screen).pack(fill="x", padx=80, pady=5)
                else:
                    self._button(
                        self.view,
                        ("Étape " + chapter_mission_card(mission_id)["ordinal"] +
                         " · " + chapter_mission_card(mission_id)["chapter"] +
                         "  →  Préparer" if self.chapter_one else
                         mission.name + " — " + mission.objective),
                        lambda mid=mission_id: self._start_mission_with_cinematic(mid)
                    ).pack(fill="x", padx=80, pady=5)
            # Studio blueprints are distinct from ad-hoc multi-front battles.
            # Locked or duplicate-mission plans remain visible but not playable.
            sieges = self.player.available_sieges()
            if sieges:
                section = self.ttk.LabelFrame(
                    self.view, text="Sièges créés dans le Studio", padding=12)
                section.pack(fill="x", padx=80, pady=12)
                for siege in sieges:
                    if siege["ready"]:
                        self._button(
                            section, "Jouer le siège : " + siege["id"] +
                            " (" + str(siege["fronts"]) + " fronts)",
                            lambda sid=siege["id"]: self._change(
                                lambda: self.player.start_configured_siege(sid))).pack(
                                    fill="x", pady=3)
                    else:
                        detail = (", ".join(siege["locked"]) if siege["locked"] else
                                  "missions répétées ou autre rencontre active")
                        self.ttk.Label(
                            section, text=siege["id"] + " — bloqué : " + detail).pack(
                                anchor="w", pady=3)
            if len(available) >= 2:
                self._button(self.view, "Commandement multi-fronts",
                             lambda: self.front_setup(available)).pack(pady=16)
            if not available:
                finished = (self.chapter_one and
                            session.progress.story_flags.get("acte1_complete"))
                message = ("Chapitre I terminé — Vaucouleurs. Votre décision "
                           "est conservée pour la suite." if finished else
                           "Campagne terminée : aucun objectif disponible.")
                if finished:
                    self._chapter_ending_panel(session.progress)
                else:
                    self.ttk.Label(self.view, text=message).pack(pady=20)

    def _campaign_flow_inspector(self):
        """Read-only campaign state panel, sourced from the live session."""
        report = self.player.session.campaign_inspector()
        dialog = self.tk.Toplevel(self.root)
        dialog.title("Campaign Flow — état persistant")
        dialog.geometry("820x590")
        dialog.transient(self.root)
        frame = self.ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        self.ttk.Label(frame, text="État des missions, variables, ressources et conséquences",
                       font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        text = self.tk.Text(frame, wrap="word", state="normal")
        scroll = self.ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True, pady=10)
        for section, values in report.items():
            text.insert("end", section.replace("_", " ").title() + "\n", "header")
            text.insert("end", json.dumps(values, ensure_ascii=False, indent=2,
                                          sort_keys=True) + "\n\n")
        text.tag_configure("header", font=("TkDefaultFont", 11, "bold"))
        text.configure(state="disabled")
        self._button(frame, "Fermer", dialog.destroy).pack(anchor="e")

    def world_screen(self):
        """Walk the canonical campaign roads; save each visible travel step."""
        session = self.player.session
        if session is None or not self.project.world:
            self.campaign_screen() if session is not None else self.title_screen()
            return
        if session.active_scene():
            self.campaign_screen()
            return
        projection = world_projection(
            self.project.world, self.player.content,
            available=session.available_missions(),
            completed=session.progress.completed)
        self._clear()
        self.presentation.transition("world")
        self._heading("Carte du monde", "Déplacez votre groupe sur les routes. "
                      "Cliquez à nouveau sur un lieu atteint pour y combattre.")
        surface = self.ttk.Frame(self.view)
        surface.pack(fill="both", expand=True, padx=24, pady=8)
        surface.columnconfigure(0, weight=1)
        surface.rowconfigure(0, weight=1)
        canvas = self.tk.Canvas(surface, width=900, height=490,
                                highlightthickness=0)
        scrollbar_y = self.ttk.Scrollbar(surface, orient="vertical",
                                          command=canvas.yview)
        scrollbar_x = self.ttk.Scrollbar(surface, orient="horizontal",
                                          command=canvas.xview)
        canvas.configure(xscrollcommand=scrollbar_x.set,
                         yscrollcommand=scrollbar_y.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        draw_world_map(canvas, projection)
        label = self.tk.StringVar(value="Choisissez une destination accessible.")
        self.ttk.Label(self.view, textvariable=label).pack(anchor="w", padx=26)

        def paint(state):
            canvas.delete("world_party")
            if state is None:
                return
            x, y = state["position"]
            canvas.create_oval(x-13, y-32, x+13, y-6, fill="#f4c75a",
                               outline="#172b44", width=3, tags=("world_party",))
            canvas.create_text(x, y-19, text="◆", fill="#192d46",
                               font=("TkDefaultFont", 12, "bold"),
                               tags=("world_party",))
            if state["traveling"]:
                label.set("En route : " + " → ".join(state["route"]))
            else:
                label.set("Groupe à " + state["at"] +
                          " — cliquez sur ce lieu pour jouer s'il est disponible.")

        def tick():
            self._world_job = None
            if not canvas.winfo_exists():
                return
            state = self.player.world_advance()
            paint(state)
            if self.player.session.active_scene() is not None:
                # Canonical StoryBook choices interrupt travel at the road
                # midpoint, then the Player returns here on completion.
                self._resume_world_after_scene = True
                self.show()
            elif state["traveling"]:
                self._world_job = self.root.after(125, lambda: self._safe(tick))

        def choose(event):
            mid = pick_world_mission(canvas, projection, event)
            if mid is None:
                return
            location = next(node for node in projection["nodes"]
                            if node["mission"] == mid)
            state = session.world_state()
            if location["status"] == "locked":
                label.set(location["label"] + " — destination verrouillée")
                return
            if state is None:
                # A partial world belonging to another campaign retains 3.7.24A.
                if location["status"] == "available":
                    self._start_mission_with_cinematic(mid)
                return
            if state["traveling"]:
                label.set("Terminez votre trajet avant de changer de destination.")
                return
            if mid == state["at"]:
                if session.world_can_enter(mid):
                    self._start_mission_with_cinematic(mid)
                else:
                    label.set(location["label"] + " — mission déjà terminée")
                return
            paint(self.player.world_destination(mid))
            self._world_job = self.root.after(125, lambda: self._safe(tick))

        canvas.bind("<Button-1>", lambda e: self._safe(lambda: choose(e)))
        current = session.world_state()
        paint(current)
        if current is not None and current["traveling"]:
            self._world_job = self.root.after(125, lambda: self._safe(tick))
        footer = self.ttk.Frame(self.view)
        footer.pack(fill="x", pady=12)
        self._button(footer, "Retour à la campagne",
                     self.campaign_screen).pack(side="left", padx=12)
        self._button(footer, "Sauvegarder",
                     self.player.save).pack(side="left", padx=12)

    def _exploration_step(self, dx, dy):
        self._explore_feedback = ""
        self._change(lambda: self.player.explore_move(dx, dy))

    def _exploration_interact(self, point_id):
        def apply():
            result = self.player.explore_interact(point_id)
            self._explore_feedback = result["title"] + " — " + result["text"]
        self._change(apply)

    def _exploration_wait(self):
        self._explore_feedback = "Le temps passe. Les habitants continuent à se déplacer."
        self._change(self.player.explore_wait)

    def _exploration_actor(self, actor_id, action):
        def apply():
            result = self.player.explore_actor(actor_id, action)
            self._explore_feedback = result["title"] + " — " + result["text"]
        self._change(apply)

    def _exploration_screen(self, scene, stage):
        """Fullscreen exploration; only contextual instructions overlay the map."""
        if self._explore_scene_id != scene["id"]:
            self._explore_feedback = ""
            self._explore_scene_id = scene["id"]
            self._explore_zoom = None
            self._explore_pan = (0, 0)
        board = self.tk.Canvas(self.view, highlightthickness=0,
                               background=self.palette.background, takefocus=1)
        board.pack(fill="both", expand=True)
        self.canvas = board
        iso_scene = (IsoExplorationCanvas(
                         board, adaptive=True, cell_size=self._explore_zoom,
                         pan=self._explore_pan)
                     if self.iso_view_var.get() else None)
        if iso_scene is not None:
            board.iso_scene = iso_scene  # Keep PhotoImages alive.
        ortho_shift = [0, 0]
        px, py = stage["position"]
        nearest = [point for point in stage["interactions"]
                   if abs(point["pos"][0] - px) + abs(point["pos"][1] - py) <= 1]
        nearby_actors = [actor for actor in stage.get("actors", ())
                         if actor["status"] != "lost"
                         and abs(actor["pos"][0] - px) +
                         abs(actor["pos"][1] - py) <= 1]
        rescue = next((actor for actor in nearby_actors
                       if actor["kind"] == "civilian"
                       and actor["status"] == "active"), None)

        def repaint(width, height):
            if width < 2 or height < 2:
                return
            board.delete("all")
            if iso_scene is not None:
                iso_scene.viewport = (width, height)
                iso_scene.draw(stage)
            else:
                draw_exploration(board, stage)
                # Legacy orthogonal view also fills its available canvas neatly.
                ortho_shift[:] = [max(0, (width - stage["width"] * 58 - 84) / 2),
                                  max(0, (height - stage["height"] * 58 - 100) / 2)]
                board.move("all", *ortho_shift)
            # Compact in-world overlay, not a permanent right-side inspector.
            board.create_rectangle(12, 12, min(width - 12, 480), 104,
                                   fill=self.palette.panel, outline=self.palette.border,
                                   tags=("explore_hud",))
            board.create_text(26, 24, anchor="nw", text=stage["title"],
                              width=max(120, min(width - 60, 420)),
                              fill=self.palette.text,
                              font=("Georgia", 14, "bold"),
                              tags=("explore_hud",))
            controls = "Flèches/ZQSD : marcher · Molette : zoom · Échap : pause"
            board.create_text(26, 77, anchor="nw", text=controls,
                              fill=self.palette.muted, font=("Segoe UI", 10),
                              tags=("explore_hud",))
            prompts = []
            if nearby_actors:
                prompts.append("E : parler à " + nearby_actors[0]["name"])
            elif nearest:
                prompts.append("E : examiner " + nearest[0]["title"])
            if rescue is not None:
                prompts.append("R : secourir " + rescue["name"])
            if stage.get("actors"):
                prompts.append("Espace : attendre")
            message = self._explore_feedback or "   ·   ".join(prompts)
            if message:
                # Discovery text can be several lines long.
                panel_height = (min(height * .4, max(60, 40 + len(message) // 75 * 22))
                                if self._explore_feedback else 60)
                bottom = max(116, height - panel_height - 12)
                board.create_rectangle(12, bottom, width - 12,
                                       height - 12, fill=self.palette.panel,
                                       outline=self.palette.border, tags=("explore_hud",))
                board.create_text(26, bottom + 12, anchor="nw", text=message,
                                  width=max(100, width - 64), fill=self.palette.text,
                                  font=("Segoe UI", 11),
                                  tags=("explore_hud",))

        def click(event):
            if iso_scene is not None:
                cell = iso_scene.hit_test(event.x, event.y)
                if cell is None:
                    return
                x, y = cell
            else:
                x = int((event.x - ortho_shift[0] - 42) // 58)
                y = int((event.y - ortho_shift[1] - 25) // 58)
                if not (0 <= x < stage["width"] and 0 <= y < stage["height"]):
                    return
            if abs(x - px) + abs(y - py) == 1:
                self._safe(lambda: self._exploration_step(x - px, y - py))

        board.bind("<Configure>", lambda event: repaint(event.width, event.height))
        board.bind("<Button-1>", click)

        # Camera changes are purely presentational: no board or save mutation.
        def zoom_camera(direction, anchor=None):
            if iso_scene is None:
                return
            if iso_scene.zoom_at(direction, stage, anchor=anchor):
                self._explore_zoom = iso_scene.cell_size
                self._explore_pan = iso_scene.pan
                repaint(board.winfo_width(), board.winfo_height())

        def pan_camera(dx, dy):
            if iso_scene is None:
                return
            iso_scene.pan_by(dx, dy)
            self._explore_pan = iso_scene.pan
            repaint(board.winfo_width(), board.winfo_height())

        if iso_scene is not None:
            board.bind("<MouseWheel>", lambda event:
                       zoom_camera(1 if event.delta > 0 else -1,
                                   (event.x, event.y)) if event.delta else None)
            board.bind("<Button-4>",
                       lambda event: zoom_camera(1, (event.x, event.y)))
            board.bind("<Button-5>",
                       lambda event: zoom_camera(-1, (event.x, event.y)))
            pan_origin = [0, 0]
            def start_pan(event):
                pan_origin[:] = [event.x, event.y]
            def drag_pan(event):
                dx, dy = event.x - pan_origin[0], event.y - pan_origin[1]
                pan_origin[:] = [event.x, event.y]
                pan_camera(dx, dy)
            board.bind("<ButtonPress-2>", start_pan)
            board.bind("<B2-Motion>", drag_pan)
            board.bind("<plus>", lambda event: zoom_camera(1))
            board.bind("<minus>", lambda event: zoom_camera(-1))
            def reset_camera(_event):
                iso_scene.recenter(stage)
                self._explore_zoom = None
                self._explore_pan = (0, 0)
                repaint(board.winfo_width(), board.winfo_height())
            board.bind("<Control-0>", reset_camera)
        moves = {"<Up>": (0, -1), "<Down>": (0, 1),
                 "<Left>": (-1, 0), "<Right>": (1, 0),
                 "w": (0, -1), "z": (0, -1), "a": (-1, 0),
                 "q": (-1, 0), "s": (0, 1), "d": (1, 0)}
        for key, delta in moves.items():
            self.root.bind(key, lambda event, vector=delta:
                           self._safe(lambda: self._exploration_step(*vector)))
        if nearby_actors:
            self.root.bind("e", lambda event: self._safe(
                lambda: self._exploration_actor(nearby_actors[0]["id"], "talk")))
        elif nearest:
            self.root.bind("e", lambda event: self._safe(
                lambda: self._exploration_interact(nearest[0]["id"])))
        if rescue is not None:
            self.root.bind("r", lambda event: self._safe(
                lambda: self._exploration_actor(rescue["id"], "rescue")))
        if stage.get("actors"):
            self.root.bind("<space>", lambda event: self._safe(
                self._exploration_wait))
        board.after_idle(lambda: board.focus_set() if board.winfo_exists() else None)

    def _narrative_scene(self, scene, *, choices=None, on_choice=None):
        """Keep dialogue choices visible at every supported window size.

        Only the illustrated narrative body scrolls; the actual decisions are
        pinned at the bottom, above the campaign navigation. No story flags
        or save data are modified by this presentation layout.
        """
        if choices is None:
            choices = self.player.session.available_choices()
        if on_choice is None:
            on_choice = lambda cid: self._change(
                lambda: self.player.choose_story_option(cid))

        panel = self.ttk.LabelFrame(self.view, text=scene["title"], padding=12)
        panel.pack(fill="both", expand=True, padx=20, pady=(6, 8))

        decisions = self.ttk.Frame(panel)
        decisions.pack(side="bottom", fill="x", pady=(8, 0))
        if choices:
            self.ttk.Label(decisions, text="Votre décision — choisissez pour continuer :"
                           ).pack(anchor="w", pady=(0, 4))
            for choice in choices:
                self._button(
                    decisions, choice["label"],
                    lambda cid=choice["id"]: on_choice(cid)
                ).pack(fill="x", padx=4, pady=3)
        else:
            self.ttk.Label(
                decisions,
                text="Aucune décision accessible dans cette scène.",
                wraplength=550
            ).pack(anchor="w", pady=4)

        viewport = self.ttk.Frame(panel)
        viewport.pack(side="top", fill="both", expand=True)
        scroll = self.tk.Canvas(viewport, height=220, highlightthickness=0,
                                background="#101a2b")
        scroll_bar = self.ttk.Scrollbar(viewport, orient="vertical",
                                      command=scroll.yview)
        scroll.configure(yscrollcommand=scroll_bar.set)
        scroll_bar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        body = self.ttk.Frame(scroll)
        body_window = scroll.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _event:
                  scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event:
                    scroll.itemconfigure(body_window, width=event.width))

        # Start with the dialogue, not a tall decorative illustration: the
        # player sees the current narrative context without scrolling.
        dialogue = self.ttk.Frame(body)
        dialogue.pack(fill="x", padx=8, pady=(8, 12))
        picture = CanvasRenderer(
            dialogue, registry=self.registry, asset_root=self.asset_root
        ).image("portrait", scene["speaker"])
        if picture is not None:
            picture_label = self.ttk.Label(dialogue, image=picture)
            picture_label.image = picture  # Tk must retain the PhotoImage.
            picture_label.pack(side="left", anchor="n", padx=(0, 14))
        copy = self.ttk.Frame(dialogue)
        copy.pack(side="left", fill="both", expand=True)
        if scene["speaker"]:
            speaker_label = self.ttk.Label(
                copy, text=scene["speaker"],
                font=("TkDefaultFont", 14, "bold"))
            speaker_label.pack(anchor="w", pady=(0, 7))
        narrative_text = self.tk.Label(
            copy, text="", fg="#f2f0d9", bg="#101a2b",
            justify="left", wraplength=440, anchor="nw",
            font=("TkDefaultFont", 12))
        narrative_text.pack(anchor="w", fill="x", pady=(0, 8))
        def resize_text(event):
            narrative_text.configure(wraplength=max(180, event.width - 12))
        copy.bind("<Configure>", resize_text)

        # Typewriter and background animation are presentation-only.
        message = scene["text"]
        def reveal(n=0):
            if not narrative_text.winfo_exists():
                return
            narrative_text.configure(text=message[:n])
            if n < len(message):
                self._typewriter_job = self.root.after(
                    8, reveal, min(n + 4, len(message)))
            else:
                self._typewriter_job = None
        reveal()

        art = None
        if scene["id"].startswith("sc_p0_"):
            art = self.tk.Canvas(body, height=160, highlightthickness=0)
            art.pack(fill="x", padx=8, pady=(0, 8))
            def animate(frame=0):
                if not art.winfo_exists():
                    return
                draw_story_backdrop(art, scene["id"], frame)
                art.scale("all", 0, 0, max(0.1, art.winfo_width() / 860), 160 / 210)
                self._stage_job = self.root.after(170, animate, frame + 1)
            animate()

        # The scrollbar is always available; the mouse wheel is restricted to
        # the narrative region so it cannot move the tactical camera or menus.
        def wheel(event):
            step = (-1 if getattr(event, "num", None) == 4 or
                    getattr(event, "delta", 0) > 0 else 1)
            scroll.yview_scroll(step * 3, "units")
            return "break"
        for widget in (scroll, body, dialogue, copy, narrative_text):
            for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                widget.bind(event, wheel)
        if picture is not None:
            for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                picture_label.bind(event, wheel)
        if art is not None:
            for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                art.bind(event, wheel)

    def front_setup(self, available):
        self._clear()
        self.presentation.transition("fronts_setup")
        self._heading("Préparer une opération multi-fronts",
                      "Choisir deux secteurs pour une timeline stratégique commune.")
        choices = [(mid, self.tk.BooleanVar(value=i < 2))
                   for i, mid in enumerate(available)]
        for mid, variable in choices:
            self.ttk.Checkbutton(self.view,
                                 text=self.player.content.missions[mid].name,
                                 variable=variable).pack(anchor="w", pady=6)
        def start():
            selected = [mid for mid, variable in choices if variable.get()]
            if len(selected) < 2:
                raise RuleError("Sélectionner au moins deux missions")
            self._change(lambda: self.player.start_fronts(
                {mid: mid for mid in selected}, selected[0]))
        self._button(self.view, "Déployer plusieurs fronts", start).pack(pady=18)
        self._button(self.view, "Retour", self.campaign_screen).pack()

    def battle_screen(self):
        session = self.player.session
        battle = session.active_battle
        self._clear()
        self.presentation.transition("battle")
        if battle is None:
            self.strategy_screen()
            return
        self.audio.music_for(f"mission_{battle.mission.id}", "battle")
        title_row = self.ttk.Frame(self.view)
        title_row.pack(fill="x", pady=(0, 3))
        self.ttk.Label(
            title_row, text=battle.mission.name + " · " + str(battle.mission.objective),
            font=("TkDefaultFont", round(11 * self.text_scale.get() / 100),
                  "bold"), wraplength=760).pack(side="left")
        self.ttk.Label(
            title_row, text=("Tick " + str(battle.tick) + " · " +
                 ("Résultat : " + str(battle.result) if battle.result else
                  "Déploiement" if battle.deploying else
                  "Actif : " + (battle.active.name if battle.active else "CT"))),
            font=("TkDefaultFont", round(10 * self.text_scale.get() / 100))
        ).pack(side="right")

        self.feedback_var.set("")
        self.ttk.Label(self.view, textvariable=self.feedback_var,
                       wraplength=1050).pack(anchor="w", pady=(3, 5))
        nav = self.ttk.Frame(self.view)
        nav.pack(fill="x", pady=4)
        if self.chapter_one and not session.finalized:
            self.ttk.Checkbutton(
                nav, text="Tours ennemis automatiques",
                variable=self.chapter_auto_ai,
                command=self._chapter_schedule_ai).pack(side="left", padx=3)
        if session.mode == "fronts":
            self._button(nav, "Timeline / Fronts", self.strategy_screen).pack(side="left", padx=4)
            if session.fronts.recovery_battles:
                self.ttk.Label(
                    nav, text="Reconquête tactique : " +
                    sorted(session.fronts.recovery_battles)[0]).pack(
                        side="left", padx=6)
        elif session.finalized:
            self._button(nav, "Résultats → Campagne",
                         self._finish_mission_with_cinematic).pack(
                             side="left", padx=4)
        self._button(nav, "Sauvegarder", self.player.save).pack(side="right", padx=4)
        self._button(nav, "Exporter playtest",
                     self._export_playtest).pack(side="right", padx=4)
        self.ttk.Checkbutton(nav, text="Suivi playtest",
                             variable=self.playtest_optin,
                             command=self._toggle_playtest).pack(side="right", padx=4)
        # R7.10 shell: fixed action toolbar below a flexible battle viewport.
        # Only three thin rows sit above the map (title, navigation, CT).
        self.hud_footer = self.ttk.LabelFrame(
            self.view, text="Actions tactiques", padding=(7, 4))
        self.hud_footer.pack(side="bottom", fill="x", pady=(4, 0))
        self.hud_workspace = self.ttk.Frame(self.view)
        self.hud_workspace.pack(fill="both", expand=True)
        ct_strip = self.ttk.LabelFrame(
            self.hud_workspace, text="Ordre des activations · CT estimé", padding=(8, 3))
        ct_strip.pack(fill="x", pady=(2, 4))
        self.ttk.Label(ct_strip, textvariable=self.hud_timeline_var,
                       wraplength=1000, justify="left").pack(anchor="w")
        self.hud_panes = self.ttk.Panedwindow(
            self.hud_workspace, orient="horizontal")
        self.hud_panes.pack(fill="both", expand=True)
        self.hud_map = self.ttk.Frame(self.hud_panes)
        self.hud_sidebar = self.ttk.Frame(self.hud_panes, width=320)
        self.hud_panes.add(self.hud_map, weight=4)
        if self.hud_sidebar_visible.get():
            self.hud_panes.add(self.hud_sidebar, weight=1)
        self.hud_tools = self.ttk.Frame(self.hud_sidebar)
        self.hud_tools.pack(fill="x", pady=(0, 4))
        self.ttk.Checkbutton(
            self.hud_tools, text="Vue 2.5D", variable=self.iso_view_var,
            command=self._switch_projection).grid(row=0, column=0, sticky="w")
        self.ttk.Checkbutton(
            self.hud_tools, text="Aide", variable=self.guidance_enabled,
            command=self._toggle_guidance).grid(row=0, column=1, sticky="w")
        self.ttk.Checkbutton(
            self.hud_tools, text="Aperçu", variable=self.preview_enabled,
            command=self._toggle_action_preview).grid(row=0, column=2, sticky="w")
        self.ttk.Checkbutton(
            self.hud_tools, text="Journal", variable=self.hud_log_visible,
            command=self._toggle_combat_log).grid(row=1, column=0, sticky="w")
        self.hud_tools.columnconfigure(0, weight=1)
        self.hud_tools.columnconfigure(1, weight=1)
        self.hud_tools.columnconfigure(2, weight=1)
        focus = self.ttk.LabelFrame(
            self.hud_sidebar, text="Personnage actif", padding=(6, 4))
        focus.pack(fill="x", pady=(0, 4))
        self.hud_portrait = self.ttk.Label(focus, width=5)
        self.hud_portrait.pack(side="left", padx=(0, 7))
        self.ttk.Label(
            focus, textvariable=self.hud_focus_var, wraplength=225,
            justify="left").pack(side="left", fill="x", expand=True)
        self.hud_portrait_renderer = CanvasRenderer(
            focus, registry=self.registry, asset_root=self.asset_root)
        self.ttk.Label(
            self.hud_sidebar, textvariable=self.hud_objective_var,
            wraplength=285, justify="left").pack(anchor="w", pady=(0, 4))
        self.hud_notebook = self.ttk.Notebook(self.hud_sidebar)
        self.hud_notebook.pack(fill="both", expand=True)
        self.hud_tactics_tab = self.ttk.Frame(self.hud_notebook)
        self.hud_journal_tab = self.ttk.Frame(self.hud_notebook)
        self.hud_party_tab = self.ttk.Frame(self.hud_notebook)
        self.hud_assistance_tab = self.ttk.Frame(self.hud_notebook)
        self.hud_notebook.add(self.hud_tactics_tab, text="Tactique")
        self.hud_notebook.add(self.hud_journal_tab, text="Journal")
        self.hud_notebook.add(self.hud_party_tab, text="Équipe")
        self.hud_notebook.add(self.hud_assistance_tab, text="Assistance")
        self.hud_journal = self.tk.Text(
            self.hud_journal_tab, wrap="word", height=7,
            bg="#000000" if self.high_contrast.get() else "#182a40",
            fg="#ffffff" if self.high_contrast.get() else "#e9f2fc",
            font=("TkDefaultFont", round(10 * self.text_scale.get() / 100)),
            relief="flat", state="disabled")
        self.hud_journal.pack(fill="both", expand=True)
        self.hud_party = self.tk.Text(
            self.hud_party_tab, wrap="word", height=6,
            bg="#000000" if self.high_contrast.get() else "#182a40",
            fg="#ffffff" if self.high_contrast.get() else "#e9f2fc",
            font=("TkDefaultFont", round(10 * self.text_scale.get() / 100)),
            relief="flat", state="disabled")
        self.hud_party.pack(fill="both", expand=True)
        if not self.hud_log_visible.get():
            self.hud_notebook.hide(self.hud_journal_tab)
        # Sidebar may be collapsed without losing the tactical action bar.
        self._button(nav, "Panneau latéral", self._toggle_hud_sidebar).pack(
            side="left", padx=3)
        if not session.finalized and not battle.result:
            actions = self.ttk.Frame(self.hud_footer)
            actions.pack(fill="x", pady=1)
            select_row = self.ttk.Frame(actions)
            select_row.pack(fill="x")
            commit_row = self.ttk.Frame(actions)
            commit_row.pack(fill="x")
            if battle.deploying:
                options = ["deploy", "start_battle"]
                players = [u.id for u in battle.units if u.team == "player" and u.alive]
                if self.unit_var.get() not in players:
                    self.unit_var.set(players[0] if players else "")
                self.ttk.Label(select_row, text="Héros").pack(side="left")
                hero_box = self.ttk.Combobox(
                    select_row, textvariable=self.unit_var,
                    values=players, state="readonly", width=11)
                hero_box.pack(side="left", padx=5)
                hero_box.bind("<<ComboboxSelected>>",
                              lambda _event: self._redraw())
            elif battle.active is None:
                options = []
            elif battle.active.team == "enemy":
                options = []
                self._button(commit_row, "Jouer l'activation IA",
                             lambda: self._change(self.player.ai_turn)).pack(side="left")
            else:
                active_level = battle.unit_levels.get(battle.active.id, 0)
                if battle.mission.level_links:
                    if active_level:
                        options = ["level_move", "level_attack", "attack", "end"]
                    else:
                        options = (["move", "level_move", "level_attack",
                                    "attack", *battle.active.skills,
                                    "item:potion", "item:ether", "item:phoenix",
                                    *["object:" + obj["id"] for obj in battle.mission.objects],
                                    *available_operations(battle, battle.active)])
                        options += tactical_action_options(battle)
                        options += ["end"]
                else:
                    options = (["move", "attack", *battle.active.skills,
                                "item:potion", "item:ether", "item:phoenix",
                                *["object:" + obj["id"] for obj in battle.mission.objects],
                                *available_operations(battle, battle.active)])
                    options += tactical_action_options(battle)
                    options += ["end"]
            if options:
                if self.action_var.get() not in options:
                    self.action_var.set(options[0])
                self.ttk.Label(select_row, text="Action").pack(side="left", padx=5)
                action_box = self.ttk.Combobox(
                    select_row, textvariable=self.action_var,
                    values=options, state="readonly", width=23)
                action_box.pack(side="left", padx=7)
                action_box.bind("<<ComboboxSelected>>",
                                lambda _event: self._redraw())
                if battle.mission.level_links:
                    self.ttk.Label(select_row, text="Étage cible").pack(side="left")
                    floor_box = self.ttk.Combobox(
                        select_row, textvariable=self.level_var, state="readonly",
                        values=tuple(range(0, 1+max(
                            max(row["from"][0], row["to"][0])
                            for row in battle.mission.level_links))),
                        width=3)
                    floor_box.pack(side="left")
                    floor_box.bind("<<ComboboxSelected>>",
                                   lambda _event: self._redraw())
                self.ttk.Label(commit_row, text="Orientation").pack(side="left")
                self.ttk.Combobox(commit_row, textvariable=self.facing_var, state="readonly",
                                  values=["north", "south", "east", "west"],
                                  width=9).pack(side="left", padx=6)
                self._button(commit_row, "Exécuter", self._execute).pack(side="left", padx=5)
                if not battle.deploying:
                    self._button(commit_row, "Fin de tour", self._end).pack(side="left", padx=5)
        self.guide_panel = self.ttk.LabelFrame(
            self.hud_assistance_tab, text="Aide tactique contextuelle",
            padding=6)
        self.ttk.Label(
            self.guide_panel, textvariable=self.guidance_var,
            wraplength=970, justify="left").pack(anchor="w")
        if self.guidance_enabled.get():
            self.guide_panel.pack(fill="x", pady=4)
        self.preview_panel = self.ttk.LabelFrame(
            self.hud_assistance_tab, text="Prévision de l'action (sans l'exécuter)",
            padding=6)
        self.ttk.Label(self.preview_panel, textvariable=self.preview_var,
                       wraplength=950, justify="left").pack(anchor="w")
        if self.preview_enabled.get():
            self.preview_panel.pack(fill="x", pady=3)
        body = self.ttk.Frame(self.hud_map)
        body.pack(fill="both", expand=True)
        self.canvas = self.tk.Canvas(
            body, background="#172638", takefocus=1, highlightthickness=2,
            highlightcolor="#ffeb70", highlightbackground="#446077")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.renderer = CanvasRenderer(self.canvas, registry=self.registry,
                                       asset_root=self.asset_root)
        self.iso_renderer = IsoBattleCanvas(self.canvas)
        self.canvas.bind("<Button-1>", self._select_cell)
        self.canvas.bind("<Configure>", self._on_battle_canvas_resize)
        self.canvas.bind("<Motion>", self._preview_motion)
        self.canvas.bind("<Leave>", self._preview_leave)
        self._bind_battle_keys()
        self.canvas.bind("<MouseWheel>", self._zoom)
        self.canvas.bind("<Button-4>", lambda _: self._zoom_step(1))
        self.canvas.bind("<Button-5>", lambda _: self._zoom_step(-1))
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_drag)
        self.info = self.tk.Text(
            self.hud_tactics_tab, width=30, wrap="word",
            fg="#ffffff" if self.high_contrast.get() else "#e9f2fc",
            bg="#000000" if self.high_contrast.get() else "#182a40",
            font=("TkDefaultFont", round(11 * self.text_scale.get() / 100)),
            relief="flat")
        self.info.pack(fill="both", expand=True)
        self._redraw()
        # Action instructions remain in Options and Assistance; do not consume
        # another permanent 40px row under the map.
        self.canvas.focus_set()
        if self.chapter_one:
            self._chapter_schedule_ai()
        if not session.finalized:
            self._button(nav, "Abandonner l'opération",
                         self._abandon).pack(side="left", padx=3)


    def _bind_battle_keys(self):
        """Canvas-scoped shortcuts leave ttk inputs and dialogs unaffected."""
        for action, sequence in self.keymap.items():
            self.canvas.bind(sequence, lambda _event, name=action:
                             self._key_action(name))

    def _update_hud_portrait(self, battle):
        """Present the selected deploy hero or current unit, with safe fallback."""
        if self.hud_portrait is None:
            return
        active = battle.active
        if active is None and battle.deploying:
            active = next(
                (u for u in battle.units if u.id == self.unit_var.get()
                 and u.team == "player"), None)
        if active is None or self._hud_portrait_unit == active.id:
            return
        self._hud_portrait_unit = active.id
        if battle.deploying:
            self.hud_focus_var.set(
                active.name + " · PV " + str(active.hp) + "/" + str(active.max_hp)
                + " · MP " + str(active.mp) + "/" + str(active.max_mp))
        image = self.hud_portrait_renderer.image("portrait", active.id)
        if image is not None:
            try:
                from .tk_images import resize_photo
                thumb = resize_photo(image, 48, 48, master=self.hud_portrait)
                self.hud_portrait.configure(image=thumb, text="")
                self.hud_portrait.image = thumb
                return
            except (ValueError, self.tk.TclError):
                pass
        self.hud_portrait.configure(image="", text=active.name[:1].upper())
        self.hud_portrait.image = None

    def _on_battle_canvas_resize(self, event):
        """Refresh renderer cache and isometric centering after a resize."""
        if self.canvas is not None and event.widget is self.canvas:
            self._schedule_battle_viewport_refresh()

    def _schedule_battle_viewport_refresh(self):
        if self._hud_resize_job is not None:
            return
        revision = self.presentation.revision
        def refresh():
            self._hud_resize_job = None
            if (self.presentation.current(revision)
                    and self.presentation.screen == "battle"
                    and self.canvas is not None):
                self._redraw()
        self._hud_resize_job = self.root.after_idle(refresh)

    def _toggle_hud_sidebar(self):
        if self.hud_panes is None or self.hud_sidebar is None:
            return
        if self.hud_sidebar_visible.get():
            self.hud_panes.forget(self.hud_sidebar)
            self.hud_sidebar_visible.set(False)
        else:
            self.hud_panes.add(self.hud_sidebar, weight=1)
            self.hud_sidebar_visible.set(True)
        if self.canvas is not None:
            self.canvas.focus_set()
            self._schedule_battle_viewport_refresh()

    def _toggle_combat_log(self):
        if self.hud_notebook is None:
            return
        if self.hud_log_visible.get():
            self.hud_notebook.add(self.hud_journal_tab, text="Journal")
            self.hud_notebook.select(self.hud_journal_tab)
        else:
            self.hud_notebook.select(self.hud_tactics_tab)
            self.hud_notebook.hide(self.hud_journal_tab)
        if self.canvas is not None:
            self.canvas.focus_set()

    def _toggle_guidance(self):
        if self.guide_panel is None:
            return
        if self.guidance_enabled.get():
            self.guide_panel.pack(fill="x", pady=4)
            if self.hud_notebook is not None:
                self.hud_notebook.select(self.hud_assistance_tab)
            self._redraw()
        else:
            self.guide_panel.pack_forget()
        # The map retains keyboard navigation after toggling the help panel.
        if self.canvas is not None:
            self.canvas.focus_set()

    def _toggle_action_preview(self):
        if self.preview_panel is None or self.canvas is None:
            return
        if self.preview_enabled.get():
            self.preview_panel.pack(fill="x", pady=3)
            if self.hud_notebook is not None:
                self.hud_notebook.select(self.hud_assistance_tab)
            self._update_action_preview()
        else:
            self.preview_panel.pack_forget()
            if self._preview_job is not None:
                self.root.after_cancel(self._preview_job)
                self._preview_job = None
            self._preview_hover = None
            self._preview_result = None
            self._preview_paint_key = None
            self.canvas.delete("player_action_preview")
        self.canvas.focus_set()

    def _preview_motion(self, event):
        if not self.preview_enabled.get() or self.iso_renderer is None:
            return
        battle = self.player.session.active_battle
        if battle is None:
            return
        if self.iso_view_var.get():
            floor = (self.level_var.get()
                     if self.action_var.get() in {"level_move", "level_attack"}
                     else battle.unit_levels.get(battle.active_id, 0)
                     if battle.active_id else 0)
            cell = self.iso_renderer.hit_test(event.x, event.y, level=floor)
        else:
            cell = self.camera.screen_to_cell(event.x, event.y)
        if cell is None or not battle.board.contains(cell):
            self._preview_leave()
            return
        if self._preview_hover == cell:
            return
        self._preview_hover = cell
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
        # Avoid running Dijkstra / forecast on every mouse-motion event.
        self._preview_job = self.root.after(90, self._flush_action_preview)

    def _flush_action_preview(self):
        self._preview_job = None
        self._update_action_preview()

    def _preview_leave(self, event=None):
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
            self._preview_job = None
        if self._preview_hover is not None:
            self._preview_hover = None
            self._update_action_preview()

    def _update_action_preview(self):
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
            self._preview_job = None
        if not self.preview_enabled.get() or self.canvas is None:
            return
        session = self.player.session
        battle = session.active_battle if session is not None else None
        if battle is None:
            return
        cell = self._preview_hover if self._preview_hover is not None else self.selection
        try:
            preview = action_preview(
                battle, self.action_var.get(), cell,
                target_level=self.level_var.get())
        except (RuleError, ValueError) as exc:
            self._preview_result = None
            self.preview_var.set("Prévision indisponible : " + str(exc))
            self.canvas.delete("player_action_preview")
            return
        self._preview_result = preview
        display = ("[" + preview.status + "] " + preview.headline +
                   (" · " + ", ".join(map(str, preview.path)) if preview.path else "") +
                   ("\n" + "\n".join(preview.details) if preview.details else ""))
        self.preview_var.set(display)
        self._draw_action_preview()

    def _draw_action_preview(self):
        if self.canvas is None:
            return
        preview = self._preview_result
        if not self.preview_enabled.get() or preview is None:
            self.canvas.delete("player_action_preview")
            self._preview_paint_key = None
            return
        iso = self.iso_view_var.get()
        geo = self.iso_renderer.geometry if iso and self.iso_renderer else None
        if iso and geo is None:
            self.canvas.delete("player_action_preview")
            self._preview_paint_key = None
            return
        shift = self.iso_renderer.shift if geo is not None else (0, 0)
        # Preserve Canvas items on idle animation ticks when nothing changed.
        # If a renderer rebuilt the scene, find_withtag detects the invalidation.
        paint_key = (preview, self.camera, iso, id(geo), shift)
        if (paint_key == self._preview_paint_key
                and self.canvas.find_withtag("player_action_preview")):
            return
        self._preview_paint_key = paint_key
        self.canvas.delete("player_action_preview")
        coords, destination = preview_screen_geometry(
            preview, self.camera, iso_geometry=geo, shift=shift)
        tags = ("player_action_preview",)
        # Never draw an upstairs destination as a ground-plane polygon.
        # The guidance panel retains the authoritative floor/path details.
        session = self.player.session
        battle = session.active_battle if session is not None else None
        actor_floor = (battle.unit_levels.get(battle.active_id, 0)
                       if battle is not None and battle.active_id else 0)
        requested_floor = (self.level_var.get() if preview.action in
                           {"level_move", "level_attack"} else actor_floor)
        if (requested_floor > 0 or
                preview.levels and any(level > 0 for level in preview.levels)):
            return
        if len(coords) > 1:
            flat = tuple(n for xy in coords for n in xy)
            targeting = (preview.action == "attack" or
                         preview.action in (battle.active.skills
                                            if battle and battle.active else ()))
            line_color = "#ffe38d" if targeting else "#3bf1d0"
            self.canvas.create_line(
                *flat, fill=line_color, width=3,
                dash=(3, 5) if targeting else (7, 4),
                arrow="last", tags=tags)
            if not targeting:
                for x, y in coords[1:-1]:
                    self.canvas.create_oval(
                        x-3, y-3, x+3, y+3,
                        outline=line_color, width=2, tags=tags)
        if destination is not None:
            if preview.status == "available":
                color = "#3bf1d0"
            elif preview.status == "blocked":
                color = "#ff8888"
            else:
                color = "#ffe38d"
            if geo is not None:
                polygon = tuple(v + shift[i % 2] for point in
                                geo.polygon(preview.destination)
                                for i, v in enumerate(point))
                self.canvas.create_polygon(
                    *polygon, fill="", outline=color, width=3, tags=tags)
            else:
                x, y = self.camera.cell_to_screen(preview.destination)
                size = self.camera.cell_size
                self.canvas.create_rectangle(
                    x+2, y+2, x+size-2, y+size-2,
                    outline=color, width=3, tags=tags)

    def _submit_tactical(self, command):
        """Show expected engine refusal inline, without a blocking dialog.

        The controller owns rollback/checkpointing; no GUI-side save on error.
        Unexpected IO errors still propagate to the existing _safe handler.
        """
        try:
            self._change(lambda: self.player.execute(command))
        except RuleError as exc:
            self.feedback_var.set("Action refusée par le moteur : " + str(exc))
            if self.canvas is not None:
                self.canvas.focus_set()

    def _key_action(self, action):
        battle = self.player.session.active_battle
        if battle is None:
            return "break"
        if action in {"north", "south", "west", "east"}:
            movement = {"north": (0, -1), "south": (0, 1),
                        "west": (-1, 0), "east": (1, 0)}[action]
            self.selection = clamp_selection(
                (self.selection[0] + movement[0],
                 self.selection[1] + movement[1]),
                battle.board.width, battle.board.height)
            self._redraw()
        elif action.startswith("pan_"):
            movement = {"pan_north": (0, 48), "pan_south": (0, -48),
                        "pan_west": (48, 0), "pan_east": (-48, 0)}[action]
            self.camera = self.camera.panned(*movement)
            self._redraw()
        elif action == "cancel":
            self.selection = (tuple(battle.active.pos)
                              if battle.active is not None else (0, 0))
            self._redraw()
        elif action in {"zoom_in", "zoom_out"}:
            self._zoom_step(1 if action == "zoom_in" else -1,
                            self._canvas_center())
        elif action.startswith("zoom_"):
            self._zoom_preset(int(action.partition("_")[2]))
        elif action == "execute" and not battle.result:
            if battle.deploying or battle.active and battle.active.team == "player":
                self._safe(self._execute)
        elif action == "end" and not battle.deploying and not battle.result:
            if battle.active is not None and battle.active.team == "player":
                self._safe(self._end)
        return "break"

    def _canvas_center(self):
        return (max(1, self.canvas.winfo_width()) / 2,
                max(1, self.canvas.winfo_height()) / 2)

    def _zoom_preset(self, size):
        """Exact 24/54/96px zoom in both projections, preserving the anchor."""
        if size not in ZOOM_PRESETS:
            raise ValueError("Unsupported zoom preset")
        anchor = self._canvas_center()
        if self.iso_view_var.get() and self.iso_renderer is not None:
            battle = self.player.session.active_battle
            self.camera = anchored_iso_zoom(
                battle.board, self.camera, self.iso_renderer.viewport(),
                0, anchor, size=size)
        else:
            self.camera = zoom_to(self.camera, size, anchor)
        self._redraw()

    def results_screen(self):
        """Presentation-only results checkpoint before campaign progression."""
        session = self.player.session
        battle = session.active_battle
        if battle is None or not session.finalized:
            self.show()
            return
        self._clear()
        self.presentation.transition("results")
        self.audio.music_for("campaign")
        self._heading(
            "Résultats · " + battle.mission.name,
            "Issue : " + ({"victory": "Victoire", "defeat": "Défaite"}.get(
                battle.result, str(battle.result))
                if self.chapter_one else str(battle.result)))
        if self.chapter_one:
            card = chapter_mission_card(battle.mission.id)
            self.ttk.Label(
                self.view, text=("VICTOIRE — " + card["victory"] if
                                 battle.result == "victory" else
                                 "Défaite — vous pouvez reprendre votre "
                                 "partie depuis une sauvegarde."),
                font=("TkDefaultFont", 14, "bold"),
                wraplength=780).pack(anchor="w", pady=(6, 14))
        self.ttk.Label(
            self.view, text="Objectif : " +
                            (chapter_mission_card(battle.mission.id)["objective"]
                             if self.chapter_one else str(battle.mission.objective))
        ).pack(anchor="w", pady=5)
        self.ttk.Label(self.view, text="Tick final : " + str(battle.tick)
                       ).pack(anchor="w", pady=5)
        frame = battle_frame(battle)
        for actor in frame.actors:
            self.ttk.Label(
                self.view, text=actor.name + " · " +
                ({"player": "Allié", "enemy": "Ennemi"}.get(
                    actor.team, actor.team) if self.chapter_one else actor.team) +
                " · PV " + str(actor.hp) + "/" + str(actor.max_hp) +
                (" · hors combat" if not actor.alive else "")
            ).pack(anchor="w", pady=2)
        self.ttk.Label(self.view,
                       text="Partie enregistrée. Le retour à la campagne applique "
                            "la progression par le contrôleur existant.").pack(
                                anchor="w", pady=14)
        self._button(self.view, "Voir le champ de bataille",
                     self.battle_screen).pack(anchor="w", pady=5)
        self._button(self.view, "Continuer vers la campagne",
                     self._finish_mission_with_cinematic).pack(anchor="w", pady=5)

    def _motion_tick(self):
        self._motion_job = None
        self._render_motion(time.monotonic() * 1000)

    def _render_motion(self, clock_ms):
        if self.renderer is None or self.canvas is None or self._motion_frame is None:
            return
        if self.iso_view_var.get() and self.iso_renderer is not None:
            # Same scene as Editor playtest. Use the engine snapshot for this
            # rendering gate; interpolated actor poses remain in 2D mode.
            battle = self.player.session.active_battle
            if battle is not None:
                self.iso_renderer.draw(
                    battle, self._motion_frame, self.camera,
                    poses=self.motion.poses(clock_ms),
                    ambient_clock_ms=clock_ms)
            self._draw_action_preview()
            # Drive ambient iso animation using the presentation loop, even
            # when no tactical MotionDirector animation is active.
            moving = self.motion.active(clock_ms)
            ambient = (battle is not None and self.iso_renderer is not None
                       and self.iso_renderer.animates_when_idle)
            if (moving or ambient) and self._motion_job is None:
                self._motion_job = self.root.after(
                    60 if moving else 125, self._motion_tick)
            return
        self.renderer.draw(
            self._motion_frame, self.camera, poses=self.motion.poses(clock_ms),
            elapsed_ms=self.motion.elapsed_ms(clock_ms), clock_ms=int(clock_ms))
        self._draw_action_preview()
        if (self.motion.active(clock_ms) or
                self.renderer.animates_when_idle(self._motion_frame)):
            if self._motion_job is None:
                self._motion_job = self.root.after(60, self._motion_tick)

    def _redraw(self):
        if self.canvas is None:
            return
        battle = self.player.session.active_battle
        skill = self.action_var.get()
        skill = skill if skill == "attack" or skill in (
            battle.active.skills if battle.active else ()) else None
        frame = battle_frame(battle, self.selection, skill)
        if battle is not self._motion_source:
            self.motion.reset()
            self._motion_source = battle
        clock_ms = time.monotonic() * 1000
        self.motion.observe(frame, clock_ms)
        self._motion_frame = frame
        self._render_motion(clock_ms)
        self.audio.observe(battle)
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
            self._preview_job = None
        self._preview_hover = None
        self._update_action_preview()
        hud = combat_hud(frame, battle.mission.objective, self.selection)
        sections = combat_hud_sections(
            frame, battle.mission.objective, compact=self.compact_hud.get())
        self.hud_timeline_var.set(
            "  |  ".join(sections.timeline) if sections.timeline
            else "Aucune activation CT actuellement disponible")
        self.hud_focus_var.set(sections.focus)
        self._update_hud_portrait(battle)
        display_objective = (
            chapter_mission_card(battle.mission.id)["objective"]
            if self.chapter_one else sections.objective)
        self.hud_objective_var.set("Objectif : " + display_objective)
        self.hud_party_var.set("\n".join(sections.party))
        for widget, content in ((self.hud_journal,
                                  "\n".join(sections.journal)
                                  if sections.journal else "Aucun événement récent"),
                                 (self.hud_party, self.hud_party_var.get())):
            if widget is not None:
                widget.configure(state="normal")
                widget.delete("1.0", "end")
                widget.insert("1.0", content)
                widget.configure(state="disabled")
        self.feedback_var.set(hud.selection_summary)
        if self.guidance_enabled.get():
            guide = combat_guidance(frame, self.action_var.get(), self.selection)
            self.guidance_var.set(
                guide.title + " — " + guide.instruction +
                ("\n" + " | ".join(guide.notes) if guide.notes else ""))
        rows = ["Objectif : " + display_objective, hud.headline,
                hud.selection_summary, "", "Escouades"]
        if self.action_var.get() == 'level_attack' and battle.active is not None:
            try:
                rows.append('Tir vertical : ' + str(battle.vertical_forecast(
                    self.level_var.get(), self.selection)))
            except RuleError as exc:
                rows.append('Tir vertical indisponible : ' + str(exc))
        if battle.mission.level_links:
            rows.insert(1, "Étage actif : N" + str(
                battle.unit_levels.get(battle.active_id, 0) if battle.active_id else 0))
        rows.extend(hud.roster)
        if hud.forecasts:
            rows.extend(["", "Prévisions moteur (sans simulation cachée)"])
            rows.extend(hud.forecasts)
        elif skill and battle.active is not None and battle.active.team == "player":
            # A rejected engine forecast explains LOS/range/target rules;
            # never invent a success percentage when prediction is unavailable.
            try:
                battle.forecast(skill, self.selection, battle.active)
            except RuleError as exc:
                rows.append("Action indisponible : " + str(exc))
        if self.action_var.get().startswith("object:"):
            oid = self.action_var.get().split(":", 1)[1]
            obj = next((item for item in battle.mission.objects
                        if item["id"] == oid), None)
            if obj is not None:
                rows.append("Interaction : " + str(obj["kind"]) +
                            " (" + oid + ") · conséquence déterminée à l'exécution")
        # Clarity: scheduled casts, armed reactions and hypothetical charges
        # are not equivalent to certain environmental damage.
        threats = {}
        for danger in frame.danger:
            threats.setdefault(danger["kind"], set()).add(tuple(danger["cell"]))
        labels = (("hazard", "Danger du terrain (certain)"),
                  ("cast", "Sort programmé"),
                  ("prepared", "Réaction armée"),
                  ("charge", "Charge possible (non garantie)"))
        if frame.squads:
            rows.extend(["", "Intentions d'escouade ennemie (possibles)"])
            for squad in frame.squads:
                stance = (squad["formation"] +
                          (" active" if squad["formation_active"] else " non active"))
                goal = (" / zone " + str(squad["goal_cells"])
                        if squad["goal_cells"] else "")
                rows.append(squad["unit"] + " : " + squad["role"] +
                            " / " + squad["intent"] + " / " + stance + goal)
        rows.extend(["", "Menaces visibles"])
        rows.extend(f"{title} : {len(threats[kind])} cases"
                    for kind, title in labels if threats.get(kind))
        on_cell = [title for kind, title in labels
                   if tuple(self.selection) in threats.get(kind, set())]
        rows.append("Case sélectionnée : " +
                    (", ".join(on_cell) if on_cell else "aucune menace signalée"))
        # CT has its own persistent top strip; don't duplicate it in the sidebar.
        if frame.casts:
            rows.extend(["", "Incantations annoncées"])
            rows.extend(f"{cast['unit']} : {cast['skill']} dans {cast['remaining_ticks']} ticks"
                        for cast in frame.casts)
        if frame.charges:
            rows.extend(["", "Charges possibles (non garanties)"])
            rows.extend(f"{charge['unit']} → {charge['target']}" for charge in frame.charges)
        # Journal has a dedicated, collapsible notebook tab.
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", "\n".join(rows))
        self.info.configure(state="disabled")

    def _switch_projection(self):
        # CanvasRenderer caches item IDs. Force a rebuild after swapping
        # the image-oriented and vector-oriented Canvas item sets.
        if self.renderer is not None:
            self.renderer.dispose()
        self._redraw()

    def _select_cell(self, event):
        self.canvas.focus_set()
        battle = self.player.session.active_battle
        if self.iso_view_var.get() and self.iso_renderer is not None:
            floor = (self.level_var.get() if self.action_var.get() in {'level_move', 'level_attack'}
                     else battle.unit_levels.get(battle.active_id, 0)
                     if battle.active_id else 0)
            cell = self.iso_renderer.hit_test(event.x, event.y, level=floor)
        else:
            cell = self.camera.screen_to_cell(event.x, event.y)
        if cell is not None and battle.board.contains(cell):
            self.selection = cell
            self._redraw()

    def _zoom(self, event):
        self._zoom_step(1 if event.delta > 0 else -1, (event.x, event.y))

    def _zoom_step(self, direction, anchor=(300, 200)):
        if self.iso_view_var.get() and self.iso_renderer is not None:
            battle = self.player.session.active_battle
            if battle is not None:
                self.camera = anchored_iso_zoom(
                    battle.board, self.camera, self.iso_renderer.viewport(),
                    direction, anchor)
        else:
            self.camera = self.camera.zoomed(direction, anchor)
        self._redraw()

    def _pan_start(self, event):
        self._pan_point = (event.x, event.y)

    def _pan_drag(self, event):
        before = getattr(self, "_pan_point", (event.x, event.y))
        self.camera = self.camera.panned(event.x - before[0], event.y - before[1])
        self._pan_point = (event.x, event.y)
        self._redraw()

    def _facing(self):
        return {"north": [0, -1], "south": [0, 1],
                "east": [1, 0], "west": [-1, 0]}[self.facing_var.get()]

    def _execute(self):
        kind = self.action_var.get()
        if kind == "start_battle":
            command = {"kind": "start_battle"}
        elif kind == "deploy":
            command = {"kind": "deploy", "unit": self.unit_var.get(),
                       "cell": list(self.selection), "facing": self._facing()}
        elif kind == "move":
            command = {"kind": "move", "cell": list(self.selection)}
        elif kind == "level_move":
            command = {"kind": "level_move", "level": self.level_var.get(),
                       "cell": list(self.selection)}
        elif kind == "level_attack":
            command = {"kind": "level_attack", "level": self.level_var.get(),
                       "cell": list(self.selection)}
        elif kind == "end":
            command = {"kind": "end", "facing": self._facing()}
        elif kind.startswith("item:"):
            command = {"kind": "item", "item": kind[5:], "cell": list(self.selection)}
        elif kind.startswith("object:"):
            command = {"kind": "interact", "object": kind[7:]}
        elif kind.startswith("siege-attack:"):
            command = {"kind": "siege_attack", "object": kind[len("siege-attack:"):]}
        elif kind.startswith("repair-siege:"):
            command = {"kind": "repair_siege", "object": kind[len("repair-siege:"):]}
        elif kind == "charge" or kind == "disengage" or kind.startswith(
                ("formation:", "prepare:", "relay:")):
            command = tactical_command(kind, self.selection)
        else:
            command = {"kind": "act", "skill": kind, "cell": list(self.selection)}
        self._submit_tactical(command)

    def _end(self):
        self._submit_tactical({"kind": "end", "facing": self._facing()})

    def _abandon(self):
        if self.messagebox.askyesno("Abandonner",
                                    "Perdre la progression tactique de cette opération ?"):
            self._change(self.player.abandon_encounter)

    def strategy_screen(self):
        session = self.player.session
        self.audio.music_for("battle")
        if session.mode != "fronts":
            self.show()
            return
        self._clear()
        self.presentation.transition("strategy")
        frame = strategy_frame(session.fronts)
        self._heading("Siège : " + session.siege_id
                      if session.siege_id else "Commandement des fronts",
                      "Tour stratégique " + str(frame.turn) +
                      "    Front actif : " + frame.focused)
        tree = self.ttk.Treeview(self.view,
                                 columns=("mission", "doctrine", "ally", "enemy", "state"),
                                 show="headings", selectmode="browse", height=9)
        for key, label in [("mission", "Mission"), ("doctrine", "Doctrine"),
                           ("ally", "Alliés"), ("enemy", "Ennemis"), ("state", "État")]:
            tree.heading(key, text=label)
            tree.column(key, width=150, anchor="center")
        for front in frame.fronts:
            tree.insert("", "end", iid=front.id,
                        values=(front.mission, front.doctrine, front.strength,
                                front.opposition, front.status))
        tree.selection_set(frame.focused)
        tree.pack(fill="both", expand=True, pady=10)
        self.front_var.set(frame.focused)
        def select(_event=None):
            selection = tree.selection()
            if selection:
                self.front_var.set(selection[0])
        tree.bind("<<TreeviewSelect>>", select)
        controls = self.ttk.Frame(self.view)
        controls.pack(fill="x", pady=12)
        self.ttk.Label(controls, text="Doctrine").pack(side="left")
        self.ttk.Combobox(controls, textvariable=self.doctrine_var,
                          values=("hold", "assault", "delay", "retreat"),
                          state="readonly", width=11).pack(side="left", padx=8)
        self._button(controls, "Appliquer", lambda: self._change(
            lambda: self.player.set_doctrine(self.front_var.get(),
                                            self.doctrine_var.get()))).pack(side="left", padx=4)
        self._button(controls, "Changer de front", lambda: self._change(
            lambda: self.player.switch_front(self.front_var.get()))).pack(side="left", padx=4)
        self._button(controls, "Avancer la timeline", lambda: self._change(
            self.player.advance_fronts)).pack(side="left", padx=4)
        self._button(controls, "Jouer le secteur", self.battle_screen).pack(
            side="left", padx=4)
        if session.fronts.logistics is not None:
            self._logistics_panel(session.fronts)
        if session.fronts.campaign is not None:
            self._campaign_routes_panel(session.fronts)
        log = self.tk.Text(self.view, height=9, fg="#e9f2fc", bg="#182a40",
                           wrap="word", relief="flat")
        log.pack(fill="both", expand=True, pady=8)
        log.insert("1.0", "\n".join(str(event) for event in frame.events[-25:]))
        log.configure(state="disabled")
        footer = self.ttk.Frame(self.view)
        footer.pack(fill="x")
        self._button(footer, "Sauvegarder", self.player.save).pack(side="left", padx=6)
        self._button(footer, "Quitter l'opération", self._abandon).pack(side="right", padx=6)
        if all(f.status != "active" for f in frame.fronts):
            self._button(footer, "Résultats → Campagne", lambda: self._change(
                self.player.return_to_campaign)).pack(side="right", padx=6)

    def _logistics_panel(self, fronts):
        """Display real convoy state and dispatch orders, never visual-only actors."""
        logistics = fronts.logistics
        panel = self.ttk.LabelFrame(self.view, text="Routes et ravitaillement", padding=8)
        panel.pack(fill="x", pady=7)
        state = logistics.state()
        supplies = state.get("supplies")
        summary = ("Réserves : " + str(state["reserves"]) +
                   "   Capacité : " + str(state["capacity"]) +
                   ("   Vivres : " + str(supplies) if supplies is not None else "") +
                   "   Escorts : " + str(state.get("escorts", 0)))
        self.ttk.Label(panel, text=summary).pack(anchor="w", pady=2)
        routes = state["routes"]
        self.ttk.Label(
            panel, text="Routes : " + (" ; ".join(
                r["from"] + " → " + r["to"] + " (" + str(r["turns"]) + " tours)"
                for r in routes) if routes else "aucune route configurée"),
            wraplength=1030).pack(anchor="w", pady=2)
        pending = state["in_transit"]
        self.ttk.Label(
            panel, text="Convois : " + (" ; ".join(
                row["id"] + " → " + row["to"] + " / arrivée T" +
                str(row["arrival"]) +
                (" [bloqué]" if row.get("stranded") else "")
                for row in pending) if pending else "aucun"),
            wraplength=1030).pack(anchor="w", pady=2)

        orders = self.ttk.Frame(panel)
        orders.pack(fill="x", pady=5)
        destinations = sorted({r["to"] for r in routes
                               if r["from"] == "reserve"})
        transfers = sorted({r["to"] for r in routes
                            if r["from"] == fronts.timeline.focused})
        if self.logistics_dest_var.get() not in destinations:
            self.logistics_dest_var.set(destinations[0] if destinations else "")
        if self.logistics_transfer_dest_var.get() not in transfers:
            self.logistics_transfer_dest_var.set(transfers[0] if transfers else "")
        self.ttk.Label(orders, text="Vers (réserves)").pack(side="left")
        self.ttk.Combobox(
            orders, textvariable=self.logistics_dest_var,
            values=destinations, width=14, state="readonly").pack(
                side="left", padx=4)
        for caption, variable, width in (
                ("Unité", self.logistics_actor_var, 13),
                ("X", self.logistics_x_var, 4),
                ("Y", self.logistics_y_var, 4)):
            self.ttk.Label(orders, text=caption).pack(side="left", padx=(5, 1))
            self.ttk.Entry(orders, textvariable=variable, width=width).pack(
                side="left")
        if destinations:
            self._button(orders, "Envoyer réserves", lambda: self._change(
                lambda: self.player.send_reserves(
                    self.logistics_dest_var.get(),
                    [{"id": self.logistics_actor_var.get(),
                      "name": self.logistics_actor_var.get(),
                      "team": "player",
                      "pos": [int(self.logistics_x_var.get()),
                              int(self.logistics_y_var.get())]}]))).pack(
                                  side="left", padx=4)
        if transfers:
            transfers_row = self.ttk.Frame(panel)
            transfers_row.pack(anchor="w", pady=3)
            self.ttk.Label(transfers_row, text="Vers (transfert)").pack(side="left")
            self.ttk.Combobox(
                transfers_row, textvariable=self.logistics_transfer_dest_var,
                values=transfers, width=14, state="readonly").pack(
                    side="left", padx=4)
            self._button(transfers_row, "Transférer unité", lambda: self._change(
                lambda: self.player.transfer_units(
                    self.logistics_transfer_dest_var.get(),
                    {self.logistics_actor_var.get():
                     [int(self.logistics_x_var.get()),
                      int(self.logistics_y_var.get())]}))).pack(
                          side="left", padx=4)
        if pending:
            convoy_ids = [r["id"] for r in pending]
            if self.convoy_var.get() not in convoy_ids:
                self.convoy_var.set(convoy_ids[0])
            convoy_actions = self.ttk.Frame(panel)
            convoy_actions.pack(anchor="w", pady=3)
            self.ttk.Label(convoy_actions, text="Convoi").pack(side="left")
            self.ttk.Combobox(
                convoy_actions, textvariable=self.convoy_var,
                values=convoy_ids, state="readonly", width=17).pack(
                    side="left", padx=5)
            self._button(convoy_actions, "Assigner escorte", lambda: self._change(
                lambda: self.player.escort_convoy(self.convoy_var.get()))).pack(
                    side="left", padx=4)
            self._button(convoy_actions, "Secourir (vivres)", lambda: self._change(
                lambda: self.player.rescue_convoy(self.convoy_var.get()))).pack(
                    side="left", padx=4)

    def _campaign_routes_panel(self, fronts):
        """Only genuine tactical results/events can unlock routes or treaties."""
        policy = fronts.campaign.state(fronts)
        panel = self.ttk.LabelFrame(self.view, text="Routes, accords et reconquête",
                                    padding=7)
        panel.pack(fill="x", pady=5)
        self.ttk.Label(panel, text=(
            "Finale : " + policy["final_front"] +
            "   | Statut : " + policy["status"] +
            "   | Accès : " + ("ouvert" if policy["unlocked"] else "verrouillé") +
            "   | Conditions : " + ", ".join(
                name + "=" + row["status"] +
                (" ✓" if row["accepted"] else " ✗")
                for name, row in policy["required"].items())),
            wraplength=1050).pack(anchor="w", pady=3)

        if fronts.route_policy is not None:
            routes = fronts.route_policy.routes
            if self.route_var.get() not in routes:
                self.route_var.set("breach")
            line = self.ttk.Frame(panel)
            line.pack(fill="x")
            self.ttk.Label(line, text="Approche").pack(side="left", padx=3)
            self.ttk.Combobox(
                line, textvariable=self.route_var, state="readonly",
                values=sorted(routes), width=16).pack(side="left", padx=4)
            self._button(line, "Engager itinéraire",
                         lambda: self._change(
                            lambda: self.player.select_route(
                                self.route_var.get()))).pack(side="left", padx=4)
            self.ttk.Label(
                line, text="Choix actuel : " + fronts.route_selected +
                (" (définitif)" if fronts.route_locked else ""),
                wraplength=400).pack(side="left", padx=5)
            current = routes[self.route_var.get()]
            self.ttk.Label(
                panel, text=("Coûts : " + str(current["supplies"]) + " vivres, " +
                            str(current["strength_loss"]) +
                            " soldats ; conditions : " +
                            str(current["required"])), wraplength=1050).pack(
                                anchor="w", pady=2)

        decisions = self.ttk.Frame(panel)
        decisions.pack(fill="x", pady=4)
        front = fronts.timeline.focused
        if fronts.recovery_battles:
            recovering = sorted(fronts.recovery_battles)[0]
            self._button(decisions, "Reprendre reconquête", self.battle_screen).pack(
                side="left", padx=4)
            self._button(
                decisions, "Abandonner reconquête", lambda: self._change(
                    lambda: self.player.abandon_recovery(recovering))).pack(
                        side="left", padx=4)
            return
        for category, label, action in (
            ("negotiation", "Négocier le passage", self.player.negotiate_front),
            ("partial", "Valider objectif partiel", self.player.partial_front),
            ("retreat", "Ordre de retraite", self.player.withdraw_front)):
            if front in fronts.campaign.spec[category] and (
                    fronts.timeline.fronts[front]["status"] == "active"):
                self._button(
                    decisions, label,
                    lambda selected=front, perform=action: self._change(
                        lambda: perform(selected))).pack(side="left", padx=4)
        chosen = self.front_var.get()
        if (fronts.route_policy is not None
                and chosen in fronts.route_policy.recovery
                and fronts.timeline.fronts[chosen]["status"] in
                ("defeat", "withdrawn")):
            self._button(
                decisions, "Reconquérir ce secteur", lambda: self._change(
                    lambda: self.player.start_recovery(
                        self.front_var.get()))).pack(side="left", padx=4)

    def close(self):
        # Multiple WM_DELETE/button callbacks must never double-close audio/Tk.
        if self._closing:
            return
        self._closing = True
        try:
            if self.player.session is not None:
                try:
                    self.player.save()
                except (RuleError, OSError, ValueError) as exc:
                    if not self.messagebox.askyesno(
                            "Sauvegarde impossible",
                            str(exc) + "\nQuitter malgré l'échec ?"):
                        self._closing = False
                        return
            # Test helpers and partially initialized apps may lack a recorder.
            # Closing still has to release audio and destroy the Tk root.
            recorder = getattr(self, "playtest_recorder", None)
            if recorder is not None:
                if recorder.enabled and recorder.active is not None:
                    recorder.finish("interrupted")
                if (recorder.report()["sessions"]
                        and recorder.revision !=
                        self.playtest_exported_revision):
                    if self.messagebox.askyesno(
                            "Playtest non exporté",
                            "La télémétrie restera uniquement en mémoire et sera "
                            "perdue en quittant. Exporter le rapport maintenant ?"):
                        self._export_playtest()
                        if recorder.revision != self.playtest_exported_revision:
                            self._closing = False
                            return
            self.audio.close()
            self.root.destroy()
        except Exception:
            self._closing = False
            raise

    def run(self):
        self.root.mainloop()


def launch(content_path, project_path=None, profile_path=None, *, chapter_one=False):
    PlayerApplication(content_path, project_path, profile_path,
                      chapter_one=chapter_one).run()
