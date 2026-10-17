"""Qt 6 R9 Event & Narrative Studio.

Launch: python -m drawtemp.studio.event_studio --smoke
Qt is an optional dependency; the canonical R9 view-model remains headless.
This is a standalone workspace until the R2 QMainWindow shell is merged.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.events import EventStudio
from sporebound.event_composer import action, condition
from sporebound.event_graph import action_title, condition_summary
from drawtemp.studio.event_command_catalog import action_catalogue, STORY_FIELDS
from drawtemp.studio.event_presentation import PRESENTATION_FIELDS
from drawtemp.render.qt_viewport import make_controller


def _coordinate_pair(text):
    values = [part.strip() for part in text.split(",")]
    if len(values) != 2:
        raise ValueError("Saisir des coordonnées x,y")
    return [int(v) for v in values]


def make_condition(kind, value):
    parts = [part.strip() for part in value.split(",")]
    if kind == "tick":
        return condition("tick", tick=int(value))
    if kind == "interact":
        return condition("interact", object_id=value.strip())
    if kind == "enter":
        return condition("enter", pos=_coordinate_pair(value))
    if kind == "defeated":
        return condition("defeated", unit=value.strip())
    if kind == "hp_below":
        if len(parts) != 2:
            raise ValueError("PV : saisir acteur,pourcentage")
        return condition("hp_below", unit=parts[0], percent=int(parts[1]))
    if kind == "wave_capacity":
        return condition("wave_capacity", max_alive=int(value))
    raise ValueError("Déclencheur non supporté : " + kind)


def make_action(kind, value):
    parts = [part.strip() for part in value.split(",")]
    if kind == "message":
        return action("message", text=value.strip())
    if kind == "hazard":
        if len(parts) != 3:
            raise ValueError("Danger : saisir x,y,puissance")
        return action("hazard", pos=[int(parts[0]), int(parts[1])],
                      amount=int(parts[2]))
    if kind == "status":
        if len(parts) != 3:
            raise ValueError("Statut : saisir acteur,statut,durée")
        return action("status", unit=parts[0], status=parts[1],
                      duration=int(parts[2]))
    if kind == "despawn":
        return action("despawn", unit=value.strip())
    raise ValueError("Action non supportée : " + kind)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", help="Fichier Content JSON et .game.json associé")
    parser.add_argument("--smoke", action="store_true", help="Afficher puis fermer Qt")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import Qt, QTimer, QUrl
        from PySide6.QtGui import QAction, QBrush, QColor, QPen, QKeySequence
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
            QFileDialog, QFormLayout,
            QHBoxLayout, QInputDialog, QLabel, QLineEdit,
            QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox,
            QSplitter, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
        )
        from PySide6.QtQuickWidgets import QQuickWidget
        from drawtemp.studio.event_graph_qt import EventGraphView
    except ImportError as exc:
        print('PySide6 requis : pip install ".[qt6]". ' + str(exc), file=sys.stderr)
        return 2

    class Window(QMainWindow):
        def __init__(self, studio):
            super().__init__()
            self.studio = studio
            self.debug_session = None
            self.setWindowTitle("DrawTemp 5.0 · Studio des événements")
            self.resize(1360, 820)

            root = QWidget()
            self.setCentralWidget(root)
            vertical = QVBoxLayout(root)
            controls = QHBoxLayout()
            vertical.addLayout(controls)
            controls.addWidget(QLabel("Mission"))
            self.missions = QComboBox()
            for mission_id, title in studio.missions():
                self.missions.addItem(title, mission_id)
            controls.addWidget(self.missions, 1)
            for label, callback in (("Ouvrir…", self.open_file),
                                    ("Enregistrer", self.save),
                                    ("Annuler", self.undo), ("Rétablir", self.redo)):
                button = QPushButton(label)
                button.clicked.connect(callback)
                controls.addWidget(button)
            splitter = QSplitter(Qt.Horizontal)
            vertical.addWidget(splitter, 1)
            aside = QWidget()
            aside_layout = QVBoxLayout(aside)
            aside_layout.addWidget(QLabel("Événements — ordre d'exécution"))
            self.event_list = QListWidget()
            aside_layout.addWidget(self.event_list, 1)
            for label, callback in (("+ Événement", self.create_event),
                                    ("Dupliquer", self.duplicate_event),
                                    ("Supprimer", self.delete_event)):
                button = QPushButton(label)
                button.clicked.connect(callback)
                aside_layout.addWidget(button)
            splitter.addWidget(aside)

            self.tabs = QTabWidget()
            splitter.addWidget(self.tabs)
            splitter.setStretchFactor(1, 4)

            basics = QWidget()
            basic_form = QFormLayout(basics)
            self.event_label = QLabel("Sélectionnez un événement")
            self.event_label.setWordWrap(True)
            basic_form.addRow(self.event_label)
            self.condition_kind = QComboBox()
            self.condition_kind.addItems(["tick", "interact", "enter", "defeated",
                                          "hp_below", "wave_capacity"])
            self.condition_value = QLineEdit("0")
            self.condition_value.setPlaceholderText("0 | levier | x,y | acteur | acteur,%")
            basic_form.addRow("Déclencheur", self.condition_kind)
            basic_form.addRow("Valeur", self.condition_value)
            basic_form.addRow(self.button("Modifier déclencheur", self.set_condition))
            self.tabs.addTab(basics, "Propriétés")

            # R9.D: pages share the canonical trigger identity. The highest
            # eligible priority wins; policies are validated in Content.
            page_tab = QWidget()
            page_form = QFormLayout(page_tab)
            self.page_list = QComboBox()
            self.page_list.currentIndexChanged.connect(self.page_selected)
            self.page_priority = QSpinBox()
            self.page_priority.setRange(-100, 100)
            self.page_enabled = QCheckBox("Page active")
            self.page_repeat = QCheckBox("Répéter (une fois par cooldown)")
            self.page_cooldown = QSpinBox()
            self.page_cooldown.setRange(1, 10000)
            self.page_cooldown.setValue(1)
            self.page_condition = QComboBox()
            self.page_condition.addItems(["tick", "interact", "enter", "defeated",
                                          "hp_below", "wave_capacity"])
            self.page_value = QLineEdit("0")
            self.page_value.setPlaceholderText("0 | levier | x,y | unité | unité,%")
            self.page_actions = QListWidget()
            self.page_actions.setMaximumHeight(115)
            page_form.addRow("Page", self.page_list)
            page_form.addRow("Priorité", self.page_priority)
            page_form.addRow(self.page_enabled)
            page_form.addRow(self.page_repeat)
            page_form.addRow("Cooldown (ticks)", self.page_cooldown)
            page_form.addRow("Condition de la page", self.page_condition)
            page_form.addRow("Valeur", self.page_value)
            page_form.addRow("Actions de la page", self.page_actions)
            page_form.addRow(self.button("Créer une page…", self.create_page))
            page_form.addRow(self.button("Appliquer la politique", self.configure_page))
            page_form.addRow(self.button("Modifier la condition", self.set_page_condition))
            page_form.addRow(self.button("Ajouter une action…", self.add_page_action))
            page_form.addRow(self.button("Retirer l'action sélectionnée", self.remove_page_action))
            page_form.addRow(self.button("Supprimer la page", self.delete_page))
            self.tabs.addTab(page_tab, "Pages & états")

            predicates = QWidget()
            predicates_form = QFormLayout(predicates)
            self.pred_kind = QComboBox()
            self.pred_kind.addItems(["tick", "interact", "enter", "defeated",
                                     "hp_below", "wave_capacity"])
            self.pred_value = QLineEdit("0")
            self.pred_join = QComboBox()
            self.pred_join.addItems(["ET", "OU"])
            self.pred_negation = QComboBox()
            self.pred_negation.addItems(["Affirmatif", "NON"])
            predicates_form.addRow("Condition secondaire", self.pred_kind)
            predicates_form.addRow("Valeur", self.pred_value)
            predicates_form.addRow("Groupe", self.pred_join)
            predicates_form.addRow("Inversion", self.pred_negation)
            predicates_form.addRow(self.button("Ajouter à l'arbre", self.add_predicate))
            predicates_form.addRow(self.button("Effacer conditions secondaires",
                                                self.clear_predicates))
            self.pred_summary = QLabel()
            self.pred_summary.setWordWrap(True)
            predicates_form.addRow("Expression active", self.pred_summary)
            self.tabs.addTab(predicates, "Conditions ET/OU/NON")

            actions_tab = QWidget()
            actions_layout = QVBoxLayout(actions_tab)
            self.actions_list = QListWidget()
            actions_layout.addWidget(self.actions_list, 1)
            action_row = QHBoxLayout()
            self.action_kind = QComboBox()
            self.action_kind.addItems(list(action_catalogue()))
            self.action_value = QLineEdit()
            self.action_value.setPlaceholderText("Texte | x,y,puissance | acteur,statut,durée")
            action_row.addWidget(self.action_kind)
            action_row.addWidget(self.action_value, 1)
            actions_layout.addLayout(action_row)
            for label, callback in (("Ajouter l'action", self.add_action),
                                    ("Modifier l'action…", self.edit_action),
                                    ("Monter ↑", lambda: self.move_action(-1)),
                                    ("Descendre ↓", lambda: self.move_action(1)),
                                    ("Retirer", self.remove_action)):
                actions_layout.addWidget(self.button(label, callback))
            actions_layout.addWidget(QLabel("Pistes de présentation (dialogue, son, caméra, acteurs, FX)"))
            self.cue_kind = QComboBox()
            self.cue_kind.addItems(list(PRESENTATION_FIELDS))
            actions_layout.addWidget(self.cue_kind)
            actions_layout.addWidget(self.button("Ajouter une piste à cet événement…",
                                                  self.add_presentation))
            self.tabs.addTab(actions_tab, "Commandes")

            graph_tab = QWidget()
            graph_layout = QVBoxLayout(graph_tab)
            graph_layout.addWidget(QLabel("Graphe des triggers — arêtes persistées dans Content"))
            self.graph_view = EventGraphView()
            self.graph_view.eventSelected.connect(self.select_graph_event)
            self.graph_view.connectRequested.connect(self.link_from_graph)
            graph_layout.addWidget(self.graph_view, 1)
            self.graph_link_mode = QCheckBox("Relier deux événements par clic (source → cible)")
            self.graph_link_mode.toggled.connect(self.update_graph_mode)
            graph_layout.addWidget(self.graph_link_mode)
            dep = QHBoxLayout()
            self.predecessors = QComboBox()
            dep.addWidget(self.predecessors, 1)
            self.link_join = QComboBox()
            self.link_join.addItems(["ET", "OU"])
            self.link_join.currentIndexChanged.connect(self.update_graph_mode)
            dep.addWidget(self.link_join)
            dep.addWidget(self.button("Relier", self.link))
            dep.addWidget(self.button("Délier", self.unlink))
            graph_layout.addLayout(dep)
            graph_layout.addWidget(self.button(
                "Créer un embranchement narratif (2 choix)…", self.create_fork))
            self.tabs.addTab(graph_tab, "Graphe")

            timeline = QWidget()
            timeline_form = QFormLayout(timeline)
            self.delay_ticks = QSpinBox()
            self.delay_ticks.setRange(0, 10000)
            self.expire_ticks = QSpinBox()
            self.expire_ticks.setRange(0, 10000)
            self.delay_activations = QSpinBox()
            self.delay_activations.setRange(0, 10000)
            self.expire_activations = QSpinBox()
            self.expire_activations.setRange(0, 10000)
            self.cancel_after = QLineEdit()
            self.cancel_after.setPlaceholderText("ID événement, ID événement")
            timeline_form.addRow("Délai (ticks)", self.delay_ticks)
            timeline_form.addRow("Délai (activations)", self.delay_activations)
            timeline_form.addRow("Expiration (ticks)", self.expire_ticks)
            timeline_form.addRow("Expiration (activations)", self.expire_activations)
            timeline_form.addRow("Annuler après", self.cancel_after)
            timeline_form.addRow(self.button("Appliquer au trigger", self.set_schedule))
            self.tabs.addTab(timeline, "Timeline")

            narrative = QWidget()
            narrative_form = QFormLayout(narrative)
            self.scene_id = QLineEdit()
            self.scene_title = QLineEdit()
            self.scene_speaker = QLineEdit("Jeanne")
            self.scene_text = QTextEdit()
            self.scene_text.setMaximumHeight(130)
            narrative_form.addRow("ID scène", self.scene_id)
            narrative_form.addRow("Titre", self.scene_title)
            narrative_form.addRow("Personnage", self.scene_speaker)
            narrative_form.addRow("Dialogue", self.scene_text)
            narrative_form.addRow(self.button("Créer scène narrative", self.create_scene))
            narrative_form.addRow(self.button("Lier scène à l'événement", self.bind_scene))
            narrative_form.addRow(self.button("Attendre un choix de cette scène…", self.bind_choice))
            narrative_form.addRow(self.button("Effacer la garde narrative", self.clear_choice))
            narrative_form.addRow(self.button("Ajouter effet de choix (variable / objet)…",
                                               self.add_story_effect))
            self.tabs.addTab(narrative, "Narration")

            map_tab = QWidget()
            map_layout = QVBoxLayout(map_tab)
            map_layout.addWidget(QLabel(
                "Viewport R3 partagé · repères au relief · cliquer pour sélectionner un événement"))
            self.renderer = make_controller(self.studio.iso_scene(self.missions.currentData()))
            self.map_viewport = QQuickWidget(self)
            self.map_viewport.setResizeMode(QQuickWidget.SizeRootObjectToView)
            self.map_viewport.rootContext().setContextProperty("renderer", self.renderer)
            qml_path = Path(__file__).resolve().parents[1] / "render" / "IsoViewport.qml"
            self.map_viewport.setSource(QUrl.fromLocalFile(str(qml_path)))
            if self.map_viewport.status() == QQuickWidget.Error:
                raise RuntimeError("; ".join(str(e) for e in self.map_viewport.errors()))
            map_root = self.map_viewport.rootObject()
            map_root.setProperty("interactionMode", "select")
            map_root.setProperty("showEventMarkers", True)
            map_root.setProperty("showLegend", False)
            map_root.cellSelected.connect(self.select_map_cell)
            map_layout.addWidget(self.map_viewport, 1)
            self.tabs.addTab(map_tab, "Carte / triggers")

            diagnostic_tab = QWidget()
            diagnostic_layout = QVBoxLayout(diagnostic_tab)
            diagnostic_commands = QHBoxLayout()
            diagnostic_commands.addWidget(self.button("Prévisualiser (F5)", self.preview))
            diagnostic_commands.addWidget(self.button("Démarrer", self.debug_start))
            diagnostic_commands.addWidget(self.button("Pas →", self.debug_step))
            diagnostic_commands.addWidget(self.button("Continuer", self.debug_continue))
            diagnostic_commands.addWidget(self.button("Inspecter", self.debug_inspect))
            diagnostic_layout.addLayout(diagnostic_commands)
            breakpoint_row = QHBoxLayout()
            breakpoint_row.addWidget(QLabel("Point d'arrêt avant"))
            self.debug_target = QComboBox()
            self.debug_target.currentTextChanged.connect(self.debug_selection_changed)
            breakpoint_row.addWidget(self.debug_target, 1)
            self.debug_breakpoint = QCheckBox("Actif")
            breakpoint_row.addWidget(self.debug_breakpoint)
            self.debug_breakpoint.toggled.connect(self.debug_toggle_breakpoint)
            diagnostic_layout.addLayout(breakpoint_row)
            checks = QHBoxLayout()
            checks.addWidget(self.button("QA structure", self.qa))
            checks.addWidget(self.button("QA + sondes de choix", self.qa_probe))
            diagnostic_layout.addLayout(checks)
            self.diagnostics = QTextEdit()
            self.diagnostics.setReadOnly(True)
            diagnostic_layout.addWidget(self.diagnostics, 1)
            self.tabs.addTab(diagnostic_tab, "Simulation / diagnostic")

            self.statusBar().showMessage("R9 : événements canoniques ; simulations isolées")
            self.missions.currentIndexChanged.connect(self.refresh_events)
            self.event_list.currentRowChanged.connect(self.select_event)
            for caption, keys, callback in (
                ("Annuler", "Ctrl+Z", self.undo),
                ("Rétablir", "Ctrl+Shift+Z", self.redo),
                ("Enregistrer", "Ctrl+S", self.save),
                ("Prévisualiser", "F5", self.preview),
            ):
                command = QAction(caption, self)
                command.setShortcut(QKeySequence(keys))
                command.triggered.connect(callback)
                self.addAction(command)
            self.refresh_events()

        def button(self, title, callback):
            widget = QPushButton(title)
            widget.clicked.connect(callback)
            return widget

        def mid(self):
            return self.missions.currentData()

        def eid(self):
            item = self.event_list.currentItem()
            return item.data(Qt.UserRole) if item else None

        def perform(self, callback, *, selected=None):
            try:
                callback()
                self.debug_session = None
                self.debug_target.clear()
                self.debug_breakpoint.blockSignals(True)
                self.debug_breakpoint.setChecked(False)
                self.debug_breakpoint.blockSignals(False)
                self.refresh_events(selected=selected)
            except Exception as exc:
                QMessageBox.warning(self, "Édition refusée", str(exc))
            self.statusBar().showMessage("Révision " + str(self.studio.session.revision))

        def refresh_events(self, *_args, selected=None):
            if not self.mid():
                return
            selected = selected or self.eid()
            rows = self.studio.events(self.mid())
            self.event_list.blockSignals(True)
            self.event_list.clear()
            for row in rows:
                self.event_list.addItem(row["id"])
                self.event_list.item(self.event_list.count()-1).setData(Qt.UserRole,
                                                                        row["id"])
            self.event_list.blockSignals(False)
            index = next((n for n, row in enumerate(rows)
                          if row["id"] == selected), 0)
            if rows:
                self.event_list.setCurrentRow(index)
            self.select_event()

        def select_event(self, *_args):
            mid, eid = self.mid(), self.eid()
            self.actions_list.clear()
            self.predecessors.clear()
            for event in self.studio.events(mid) if mid else ():
                if event["id"] != eid:
                    self.predecessors.addItem(event["id"])
            if eid:
                event = self.studio.event(mid, eid)
                self.event_label.setText(event["id"] + " — " +
                                         condition_summary(event))
                self.pred_summary.setText(condition_summary(event))
                for item in event["actions"]:
                    self.actions_list.addItem(action_title(item))
                self.delay_ticks.setValue(event.get("delay_ticks", 0))
                self.expire_ticks.setValue(event.get("expire_after_ticks", 0))
                self.delay_activations.setValue(event.get("delay_activations", 0))
                self.expire_activations.setValue(event.get("expire_after_activations", 0))
                self.cancel_after.setText(", ".join(event.get("cancel_after", [])))
            else:
                self.event_label.setText("Sélectionnez un événement")
                self.pred_summary.clear()
            self.refresh_pages()
            self.render_graph()
            self.render_map()

        def refresh_pages(self):
            self.page_list.blockSignals(True)
            chosen = self.page_list.currentData()
            self.page_list.clear()
            if self.eid():
                for page in self.studio.event_pages(self.mid(), self.eid()):
                    self.page_list.addItem(
                        page["id"] + " (priorité " +
                        str(page.get("priority", 0)) + ")", page["id"])
            match = self.page_list.findData(chosen)
            self.page_list.setCurrentIndex(max(0, match))
            self.page_list.blockSignals(False)
            self.page_selected()

        def page_selected(self, *_):
            if not self.eid():
                return
            chosen = self.page_list.currentData() or "base"
            page = next((p for p in self.studio.event_pages(self.mid(), self.eid())
                         if p["id"] == chosen), None)
            if page is None:
                return
            self.page_priority.setValue(page.get("priority", 0))
            self.page_priority.setEnabled(chosen != "base")
            self.page_enabled.setChecked(page.get("enabled", True))
            self.page_repeat.setChecked(page.get("repeat", False))
            self.page_cooldown.setValue(page.get("cooldown_ticks", 1))
            self.page_condition.setCurrentText(page["condition"])
            self.page_actions.clear()
            for action in page["actions"]:
                self.page_actions.addItem(action_title(action))

        def create_page(self):
            if not self.eid():
                return
            page_id, ok = QInputDialog.getText(
                self, "Nouvelle page", "ID unique de la page")
            if not ok or not page_id.strip():
                return
            self.perform(lambda: self.studio.add_page(
                self.mid(), self.eid(), page_id=page_id.strip(),
                priority=self.page_priority.value(),
                condition=make_condition(self.page_condition.currentText(),
                                         self.page_value.text()),
                actions=[action("message", text="Nouvelle page")],
                enabled=self.page_enabled.isChecked(),
                repeat=self.page_repeat.isChecked(),
                cooldown_ticks=self.page_cooldown.value()))

        def configure_page(self):
            if self.eid() and self.page_list.currentData():
                page_id = self.page_list.currentData()
                priority = self.page_priority.value() if page_id != "base" else None
                self.perform(lambda: self.studio.configure_page(
                    self.mid(), self.eid(), page_id, priority=priority,
                    enabled=self.page_enabled.isChecked(),
                    repeat=self.page_repeat.isChecked(),
                    cooldown_ticks=(self.page_cooldown.value()
                                    if self.page_repeat.isChecked() else None)))

        def set_page_condition(self):
            if not self.eid() or self.page_list.currentData() == "base":
                return
            self.perform(lambda: self.studio.edit_page(
                self.mid(), self.eid(), self.page_list.currentData(),
                condition=make_condition(self.page_condition.currentText(),
                                         self.page_value.text())))

        def add_page_action(self):
            if not self.eid() or self.page_list.currentData() == "base":
                return
            try:
                edited = self._command_dialog()
                if edited:
                    from drawtemp.studio.event_command_catalog import tactical_action
                    kind, fields = edited
                    page_id = self.page_list.currentData()
                    page = next(p for p in self.studio.event_pages(
                        self.mid(), self.eid()) if p["id"] == page_id)
                    actions = page["actions"] + [tactical_action(kind, fields)]
                    self.perform(lambda: self.studio.edit_page(
                        self.mid(), self.eid(), page_id, actions=actions))
            except Exception as exc:
                QMessageBox.warning(self, "Commande invalide", str(exc))

        def remove_page_action(self):
            if not self.eid() or self.page_list.currentData() == "base":
                return
            index = self.page_actions.currentRow()
            if index < 0:
                return
            page_id = self.page_list.currentData()
            page = next(p for p in self.studio.event_pages(
                self.mid(), self.eid()) if p["id"] == page_id)
            self.perform(lambda: self.studio.edit_page(
                self.mid(), self.eid(), page_id,
                actions=[a for i, a in enumerate(page["actions"]) if i != index]))

        def delete_page(self):
            if self.eid() and self.page_list.currentData() not in (None, "base"):
                page_id = self.page_list.currentData()
                self.perform(lambda: self.studio.delete_page(
                    self.mid(), self.eid(), page_id))

        def create_event(self):
            mid = self.mid()
            eid, ok = QInputDialog.getText(self, "Nouvel événement", "Identifiant")
            if not ok or not eid.strip():
                return
            self.perform(lambda: self.studio.create(
                mid, eid.strip(),
                make_condition(self.condition_kind.currentText(),
                               self.condition_value.text()),
                [action("message", text="Nouvel événement")]), selected=eid.strip())

        def duplicate_event(self):
            if not self.eid():
                return
            eid, ok = QInputDialog.getText(self, "Dupliquer", "Nouvel identifiant")
            if ok and eid.strip():
                self.perform(lambda: self.studio.duplicate(
                    self.mid(), self.eid(), eid.strip()), selected=eid.strip())

        def delete_event(self):
            if self.eid() and QMessageBox.question(
                    self, "Supprimer", "Supprimer l'événement sélectionné ?") == QMessageBox.Yes:
                self.perform(lambda: self.studio.delete(self.mid(), self.eid()))

        def set_condition(self):
            if self.eid():
                self.perform(lambda: self.studio.set_condition(
                    self.mid(), self.eid(),
                    make_condition(self.condition_kind.currentText(),
                                   self.condition_value.text())))

        def add_predicate(self):
            if self.eid():
                self.perform(lambda: self.studio.add_predicate(
                    self.mid(), self.eid(),
                    make_condition(self.pred_kind.currentText(),
                                   self.pred_value.text()),
                    join="all" if self.pred_join.currentIndex() == 0 else "any",
                    negate=self.pred_negation.currentIndex() == 1))

        def clear_predicates(self):
            if self.eid():
                self.perform(lambda: self.studio.clear_predicates(self.mid(), self.eid()))

        def _command_dialog(self, *, existing=None):
            kind = existing["kind"] if existing else self.action_kind.currentText()
            if kind not in action_catalogue():
                raise ValueError("Action non prise en charge par le moteur tactique")
            dialog = QDialog(self)
            dialog.setWindowTitle(("Modifier " if existing else "Ajouter ") + kind)
            form = QFormLayout(dialog)
            editors = {}
            for key, label, type_name in action_catalogue()[kind]:
                value = ""
                if existing:
                    value = existing.get(key, "")
                    if key == "actor_id":
                        value = existing.get("actor", {}).get("id", "") if kind == "spawn" else (
                            existing.get("actors", [{}])[0].get("id", ""))
                    elif key in ("name", "team", "archetype", "pos") and kind in (
                            "spawn", "wave", "queue_wave"):
                        actor = (existing.get("actor", {}) if kind == "spawn" else
                                 existing.get("actors", [{}])[0])
                        value = actor.get(key, "")
                    elif key == "max_active":
                        value = existing.get("max_active", 14)
                if type_name == "cell" and isinstance(value, (list, tuple)):
                    value = ",".join(map(str, value))
                if type_name == "integer":
                    editor = QSpinBox()
                    editor.setRange(0, 10000)
                    editor.setValue(int(value) if value != "" else
                                    (14 if key == "max_active" else 1))
                elif type_name == "boolean":
                    editor = QComboBox()
                    editor.addItems(["true", "false"])
                    editor.setCurrentText("true" if value is True else
                                          "false" if value is False else "true")
                elif type_name == "team":
                    editor = QComboBox()
                    editor.addItems(["enemy", "player"])
                    editor.setCurrentText(str(value or "enemy"))
                else:
                    editor = QLineEdit(str(value) if value else "")
                    if key == "pos" and not value:
                        editor.setPlaceholderText("x,y")
                editors[key] = editor
                form.addRow(label, editor)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.Accepted:
                return None
            raw = {}
            for key, _, type_name in action_catalogue()[kind]:
                editor = editors[key]
                raw[key] = (editor.value() if type_name == "integer" else
                            editor.currentText() if type_name in ("team", "boolean") else
                            editor.text())
            return kind, raw

        def add_action(self):
            if not self.eid():
                return
            try:
                edited = self._command_dialog()
                if edited:
                    kind, fields = edited
                    self.perform(lambda: self.studio.add_tactical_command(
                        self.mid(), self.eid(), kind, fields))
            except Exception as exc:
                QMessageBox.warning(self, "Action invalide", str(exc))

        def edit_action(self):
            if not self.eid() or self.actions_list.currentRow() < 0:
                return
            index = self.actions_list.currentRow()
            try:
                existing = self.studio.event(self.mid(), self.eid())["actions"][index]
                edited = self._command_dialog(existing=existing)
                if edited:
                    kind, fields = edited
                    self.perform(lambda: self.studio.replace_tactical_command(
                        self.mid(), self.eid(), index, kind, fields))
            except Exception as exc:
                QMessageBox.warning(self, "Modification impossible", str(exc))

        def add_presentation(self):
            if not self.eid():
                return
            kind = self.cue_kind.currentText()
            dialog = QDialog(self)
            dialog.setWindowTitle("Piste Player : " + kind)
            form = QFormLayout(dialog)
            clip_id = QLineEdit("cin_" + self.eid())
            clip_name = QLineEdit("Scène " + self.eid())
            cue_id = QLineEdit(kind + "_" + self.eid())
            start = QSpinBox()
            start.setRange(0, 7999)
            duration = QSpinBox()
            duration.setRange(1, 8000)
            duration.setValue(1000)
            for label, widget in (("ID cinématique", clip_id),
                                  ("Nom cinématique", clip_name),
                                  ("ID piste", cue_id),
                                  ("Début (ms)", start), ("Durée (ms)", duration)):
                form.addRow(label, widget)
            entries = {}
            defaults = {"speaker": "Jeanne", "text": "", "cue": "",
                        "actor": "jeanne", "color": "#243c56",
                        "effect": "fire"}
            for key, label in PRESENTATION_FIELDS[kind]:
                edit = QLineEdit(defaults.get(key, ""))
                form.addRow(label, edit)
                entries[key] = edit
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.Accepted:
                return
            fields = {key: editor.text() for key, editor in entries.items()}
            self.perform(lambda: self.studio.add_presentation_cue(
                self.mid(), self.eid(), clip_id=clip_id.text().strip(),
                clip_name=clip_name.text().strip(), kind=kind,
                cue_id=cue_id.text().strip(), start_ms=start.value(),
                duration_ms=duration.value(), fields=fields))

        def move_action(self, direction):
            if self.eid() and self.actions_list.currentRow() >= 0:
                self.perform(lambda: self.studio.move_action(
                    self.mid(), self.eid(), self.actions_list.currentRow(), direction))

        def remove_action(self):
            if self.eid() and self.actions_list.currentRow() >= 0:
                self.perform(lambda: self.studio.remove_action(
                    self.mid(), self.eid(), self.actions_list.currentRow()))

        def link(self):
            if self.eid() and self.predecessors.currentText():
                self.perform(lambda: self.studio.link(
                    self.mid(), self.eid(), self.predecessors.currentText(),
                    any_of=self.link_join.currentIndex() == 1))

        def unlink(self):
            if self.eid() and self.predecessors.currentText():
                self.perform(lambda: self.studio.unlink(
                    self.mid(), self.eid(), self.predecessors.currentText(),
                    any_of=self.link_join.currentIndex() == 1))

        def set_schedule(self):
            if self.eid():
                self.perform(lambda: self.studio.schedule(
                    self.mid(), self.eid(), delay_ticks=self.delay_ticks.value(),
                    delay_activations=self.delay_activations.value(),
                    expire_after_ticks=self.expire_ticks.value(),
                    expire_after_activations=self.expire_activations.value(),
                    cancel_after=[v.strip() for v in self.cancel_after.text().split(",")
                                  if v.strip()]))

        def create_scene(self):
            self.perform(lambda: self.studio.create_scene(
                self.mid(), self.scene_id.text().strip(), self.scene_title.text(),
                self.scene_text.toPlainText(), speaker=self.scene_speaker.text()))

        def bind_scene(self):
            if self.eid():
                self.perform(lambda: self.studio.bind_scene(
                    self.mid(), self.eid(), self.scene_id.text().strip()))

        def bind_choice(self):
            if not self.eid():
                return
            scene_id = self.scene_id.text().strip()
            choice_id, ok = QInputDialog.getText(
                self, "Choix attendu", "Identifiant du choix narratif")
            if ok and choice_id.strip():
                self.perform(lambda: self.studio.bind_choice(
                    self.mid(), self.eid(), scene_id, choice_id.strip()))

        def clear_choice(self):
            if self.eid():
                self.perform(lambda: self.studio.clear_choice(
                    self.mid(), self.eid()))

        def add_story_effect(self):
            if not self.mid():
                return
            scene_id = self.scene_id.text().strip()
            choice_id, ok = QInputDialog.getText(
                self, "Effet de choix", "Identifiant du choix de la scène")
            if not ok or not choice_id.strip():
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Effet StoryBook · " + scene_id + "/" + choice_id)
            form = QFormLayout(dialog)
            kind_combo = QComboBox()
            kind_combo.addItems(list(STORY_FIELDS))
            form.addRow("Opération", kind_combo)
            controls = {}
            for name in {name for fields in STORY_FIELDS.values()
                         for name, _, _ in fields}:
                edit = QLineEdit()
                edit.setPlaceholderText(name)
                controls[name] = edit
                form.addRow(name, edit)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.Accepted:
                return
            kind = kind_combo.currentText()
            fields = {key: controls[key].text()
                      for key, _, _ in STORY_FIELDS[kind]}
            self.perform(lambda: self.studio.add_story_effect(
                self.mid(), scene_id, choice_id.strip(), kind, fields))

        def create_fork(self):
            if not self.mid():
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Nouvel embranchement — deux décisions")
            dialog.resize(540, 540)
            form = QFormLayout(dialog)
            def field(label, initial=""):
                edit = QLineEdit(initial)
                form.addRow(label, edit)
                return edit

            source = field("Événement de départ", self.eid() or "choice_origin")
            cell = field("Case d'entrée (x,y)", "2,3")
            scene = field("ID scène du choix", "jeanne_choice")
            title = field("Titre", "Quelle voie choisir ?")
            text = field("Dialogue", "Jeanne doit décider de la suite.")
            speaker = field("Interlocuteur", "Jeanne")
            branches = []
            for index, defaults in enumerate((
                    ("fight", "Combattre", "fight_event", "hazard", "5"),
                    ("talk", "Négocier", "talk_event", "message", "0"))):
                form.addRow(QLabel("Choix " + str(index + 1)))
                choice = field("ID du choix", defaults[0])
                label = field("Libellé", defaults[1])
                event = field("ID événement tactique", defaults[2])
                kind = QComboBox()
                kind.addItems(["message", "hazard"])
                kind.setCurrentText(defaults[3])
                form.addRow("Conséquence", kind)
                detail = field("Message de conséquence", label.text())
                amount = QSpinBox()
                amount.setRange(0, 10000)
                amount.setValue(int(defaults[4]))
                form.addRow("Danger (hazard seulement)", amount)
                branches.append((choice, label, event, kind, detail, amount))
            reunion = field("ID de réunion (facultatif)", "choice_reunion")
            reunion_message = field("Texte de réunion", "Les chemins se rejoignent.")
            actions = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            actions.accepted.connect(dialog.accept)
            actions.rejected.connect(dialog.reject)
            form.addRow(actions)
            if dialog.exec() != QDialog.Accepted:
                return

            def apply():
                rows = [{
                    "id": choice.text().strip(),
                    "label": label.text().strip(),
                    "event_id": event.text().strip(),
                    "kind": kind.currentText(),
                    "text": detail.text().strip(),
                    "amount": amount.value(),
                } for choice, label, event, kind, detail, amount in branches]
                self.studio.create_choice_fork(
                    self.mid(), origin_event_id=source.text().strip(),
                    origin_cell=_coordinate_pair(cell.text()),
                    scene_id=scene.text().strip(), title=title.text().strip(),
                    text=text.text().strip(), speaker=speaker.text().strip(),
                    branches=rows, reunion_event_id=reunion.text().strip(),
                    reunion_message=reunion_message.text().strip())

            self.perform(apply, selected=source.text().strip())

        def update_graph_mode(self, *_):
            self.graph_view.set_connect_mode(
                self.graph_link_mode.isChecked(),
                any_of=self.link_join.currentIndex() == 1)

        def select_graph_event(self, event_id):
            self.select_event_id(event_id)

        def select_event_id(self, event_id):
            for index in range(self.event_list.count()):
                if self.event_list.item(index).data(Qt.UserRole) == event_id:
                    self.event_list.setCurrentRow(index)
                    return

        def link_from_graph(self, source, target, any_of):
            self.perform(lambda: self.studio.link(
                self.mid(), target, source, any_of=any_of), selected=target)

        def render_graph(self):
            if self.mid():
                self.graph_view.render_events(
                    self.studio.events(self.mid()), self.mid(),
                    selected_id=self.eid())

        def select_map_cell(self, x, y):
            if not self.mid():
                return
            markers = self.studio.map_markers(self.mid())
            matches = [m["event_id"] for m in markers
                       if m["pos"] == [x, y]]
            if matches:
                self.select_event_id(matches[0])

        def render_map(self):
            if not self.mid():
                return
            self.renderer.replace_scene(self.studio.iso_scene(self.mid()))
            self.renderer.setEventMarkers(
                self.studio.map_markers(self.mid()), selected_id=self.eid() or "")

        def preview(self):
            if not self.eid():
                return
            try:
                result = self.studio.preview(self.mid(), self.eid())
                self.diagnostics.setPlainText("\n".join(result["lines"]))
                self.tabs.setCurrentIndex(self.tabs.count()-1)
            except Exception as exc:
                QMessageBox.warning(self, "Simulation impossible", str(exc))

        def _render_debug(self, result):
            self.diagnostics.setPlainText("\n".join(result["lines"]))
            self.tabs.setCurrentIndex(self.tabs.count() - 1)

        def debug_start(self):
            if not self.eid():
                return
            try:
                self.debug_session = self.studio.start_debug(
                    self.mid(), self.eid(), scenario="satisfied")
                self.debug_target.blockSignals(True)
                self.debug_target.clear()
                self.debug_target.addItems(self.debug_session.chain_ids())
                self.debug_target.blockSignals(False)
                self.debug_breakpoint.blockSignals(True)
                self.debug_breakpoint.setChecked(False)
                self.debug_breakpoint.blockSignals(False)
                self._render_debug(self.debug_session.report())
            except Exception as exc:
                self.debug_session = None
                QMessageBox.warning(self, "Débogueur indisponible", str(exc))

        def debug(self):
            self.debug_start()

        def debug_step(self):
            if self.debug_session is None:
                self.debug_start()
                return
            try:
                self._render_debug(self.debug_session.step())
            except Exception as exc:
                QMessageBox.warning(self, "Pas à pas interrompu", str(exc))

        def debug_continue(self):
            if self.debug_session is None:
                self.debug_start()
                return
            try:
                self._render_debug(self.debug_session.resume())
            except Exception as exc:
                QMessageBox.warning(self, "Diagnostic interrompu", str(exc))

        def debug_selection_changed(self, event_id):
            if self.debug_session is None:
                return
            try:
                enabled = event_id in self.debug_session.report()["report"]["breakpoints"]
                self.debug_breakpoint.blockSignals(True)
                self.debug_breakpoint.setChecked(enabled)
                self.debug_breakpoint.blockSignals(False)
            except Exception:
                self.debug_breakpoint.blockSignals(False)

        def debug_inspect(self):
            if self.debug_session is None:
                self.debug_start()
                if self.debug_session is None:
                    return
            event_id = self.debug_target.currentText()
            if not event_id:
                return
            try:
                details = self.debug_session.inspect(event_id)
                lines = ["INSPECTION DES CONDITIONS : " + event_id,
                         "Évaluation : " + ("vrai" if details["passed"] else "faux")]
                for row in details["conditions"]:
                    lines.append(
                        ("✓ " if row["passed"] else "✕ ") + row["label"])
                lines.extend(["", *self.debug_session.report()["lines"]])
                self.diagnostics.setPlainText("\n".join(lines))
                self.tabs.setCurrentIndex(self.tabs.count()-1)
            except Exception as exc:
                QMessageBox.warning(self, "Inspection impossible", str(exc))

        def debug_toggle_breakpoint(self, enabled):
            if self.debug_session is None or not self.debug_target.currentText():
                return
            try:
                self._render_debug(self.debug_session.breakpoint(
                    self.debug_target.currentText(), enabled))
            except Exception as exc:
                QMessageBox.warning(self, "Point d'arrêt refusé", str(exc))

        def qa(self):
            self._run_qa(False)

        def qa_probe(self):
            self._run_qa(True)

        def _run_qa(self, probe):
            if not self.mid():
                return
            try:
                issues = self.studio.diagnostics(self.mid())
                report = self.studio.branch_qa(self.mid(), probe=probe)
                sections = ["CONTRÔLES ÉVÉNEMENTS — "+
                            (", ".join(p["message"] for p in issues)
                             if issues else "aucune anomalie détectée"),
                            "", *report["lines"],
                            "", "Rejeu Player complet : NON CERTIFIÉ"]
                self.diagnostics.setPlainText("\n".join(sections))
                self.tabs.setCurrentIndex(self.tabs.count()-1)
            except Exception as exc:
                QMessageBox.warning(self, "QA indisponible", str(exc))

        def undo(self):
            self.perform(self.studio.undo)

        def redo(self):
            self.perform(self.studio.redo)

        def save(self):
            try:
                self.studio.save()
                self.statusBar().showMessage("Content + GameProject enregistrés")
            except Exception as exc:
                if getattr(exc, "code", "") == "no_destination":
                    destination, _ = QFileDialog.getSaveFileName(
                        self, "Enregistrer Content", "", "JSON (*.json)")
                    if destination:
                        self.perform(lambda: self.studio.save_as(destination))
                else:
                    QMessageBox.warning(self, "Enregistrement refusé", str(exc))

        def open_file(self):
            if not self.confirm_close():
                return
            destination, _ = QFileDialog.getOpenFileName(
                self, "Ouvrir Content + GameProject", "", "JSON (*.json)")
            if destination:
                try:
                    self.studio = EventStudio(AuthoringSession.open(destination))
                    self.missions.clear()
                    for mid, title in self.studio.missions():
                        self.missions.addItem(title, mid)
                    self.refresh_events()
                except Exception as exc:
                    QMessageBox.warning(self, "Ouverture refusée", str(exc))

        def confirm_close(self):
            if self.studio.session.snapshot().dirty:
                return QMessageBox.question(
                    self, "Modifications non enregistrées",
                    "Abandonner les changements non enregistrés ?") == QMessageBox.Yes
            return True

        def closeEvent(self, event):
            event.accept() if self.confirm_close() else event.ignore()

    try:
        if args.content:
            session = AuthoringSession.open(args.content)
        else:
            content, project = reference_project()
            session = AuthoringSession.new(content, project)
        app = QApplication([sys.argv[0]])
        window = Window(EventStudio(session))
        window.show()
        if args.smoke:
            QTimer.singleShot(150, app.quit)
        return app.exec()
    except Exception as exc:
        print("R9 Studio: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
