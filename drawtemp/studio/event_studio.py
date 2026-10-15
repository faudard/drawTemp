"""Qt 6 R9 Event & Narrative Studio.

Launch: python -m drawtemp.studio.event_studio --smoke
Qt is an optional dependency; the canonical R9 view-model remains headless.
This is a standalone workspace until the R2 QMainWindow shell is merged.
"""
from __future__ import annotations

import argparse
import sys

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.events import EventStudio
from sporebound.event_composer import action, condition
from sporebound.event_graph import action_title, condition_summary


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
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QAction, QBrush, QColor, QPen, QKeySequence
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
            QFileDialog, QFormLayout, QGraphicsScene,
            QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
            QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox,
            QSplitter, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
        )
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
            self.action_kind.addItems(["message", "hazard", "status", "despawn"])
            self.action_value = QLineEdit()
            self.action_value.setPlaceholderText("Texte | x,y,puissance | acteur,statut,durée")
            action_row.addWidget(self.action_kind)
            action_row.addWidget(self.action_value, 1)
            actions_layout.addLayout(action_row)
            for label, callback in (("Ajouter l'action", self.add_action),
                                    ("Monter ↑", lambda: self.move_action(-1)),
                                    ("Descendre ↓", lambda: self.move_action(1)),
                                    ("Retirer", self.remove_action)):
                actions_layout.addWidget(self.button(label, callback))
            self.tabs.addTab(actions_tab, "Commandes")

            graph_tab = QWidget()
            graph_layout = QVBoxLayout(graph_tab)
            graph_layout.addWidget(QLabel("Graphe des triggers — arêtes persistées dans Content"))
            self.graph_scene = QGraphicsScene()
            self.graph_view = QGraphicsView(self.graph_scene)
            graph_layout.addWidget(self.graph_view, 1)
            dep = QHBoxLayout()
            self.predecessors = QComboBox()
            dep.addWidget(self.predecessors, 1)
            self.link_join = QComboBox()
            self.link_join.addItems(["ET", "OU"])
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
            self.tabs.addTab(narrative, "Narration")

            map_tab = QWidget()
            map_layout = QVBoxLayout(map_tab)
            map_layout.addWidget(QLabel("Repères de triggers/effets (schéma 2D ; viewport GPU R5 à intégrer)"))
            self.map_scene = QGraphicsScene()
            map_layout.addWidget(QGraphicsView(self.map_scene), 1)
            self.tabs.addTab(map_tab, "Carte / triggers")

            diagnostic_tab = QWidget()
            diagnostic_layout = QVBoxLayout(diagnostic_tab)
            diagnostic_commands = QHBoxLayout()
            diagnostic_commands.addWidget(self.button("Prévisualiser (F5)", self.preview))
            diagnostic_commands.addWidget(self.button("Démarrer", self.debug_start))
            diagnostic_commands.addWidget(self.button("Pas →", self.debug_step))
            diagnostic_commands.addWidget(self.button("Continuer", self.debug_continue))
            diagnostic_layout.addLayout(diagnostic_commands)
            breakpoint_row = QHBoxLayout()
            breakpoint_row.addWidget(QLabel("Point d'arrêt avant"))
            self.debug_target = QComboBox()
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
            self.render_graph()
            self.render_map()

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

        def add_action(self):
            if self.eid():
                self.perform(lambda: self.studio.add_action(
                    self.mid(), self.eid(),
                    make_action(self.action_kind.currentText(), self.action_value.text())))

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

        def render_graph(self):
            self.graph_scene.clear()
            if not self.mid():
                return
            graph = self.studio.graph(self.mid())
            nodes = {tuple(row["key"]): row for row in graph["nodes"]}
            for edge in graph["edges"]:
                source, target = nodes.get(tuple(edge["source"])), nodes.get(tuple(edge["target"]))
                if source and target:
                    self.graph_scene.addLine(
                        source["x"]+92, source["y"]+16, target["x"], target["y"]+16,
                        QPen(QColor("#8595aa"), 1.5))
            for node in graph["nodes"]:
                focus = node["event_id"] == self.eid()
                self.graph_scene.addRect(
                    node["x"], node["y"], 210, 40,
                    QPen(QColor("#3d7dda") if focus else QColor("#7d8fa4")),
                    QBrush(QColor("#e9f1ff") if focus else QColor("#f8fafc")))
                label = self.graph_scene.addText(node["label"][:34])
                label.setPos(node["x"]+8, node["y"]+6)
            self.graph_scene.setSceneRect(0, 0, graph["width"], graph["height"])

        def render_map(self):
            self.map_scene.clear()
            if not self.mid():
                return
            mission = self.studio._mission(self.mid())
            width, height = mission["board"]["width"], mission["board"]["height"]
            scale = max(12, min(30, 600 // max(width, height)))
            for x in range(width):
                for y in range(height):
                    self.map_scene.addRect(x*scale, y*scale, scale, scale,
                                           QPen(QColor("#d0d7de")))
            for marker in self.studio.map_markers(self.mid()):
                x, y = marker["pos"]
                self.map_scene.addEllipse(
                    x*scale+3, y*scale+3, max(2,scale-6), max(2,scale-6),
                    QPen(QColor("#1457a5")),
                    QBrush(QColor("#e99e3b") if marker["kind"]=="effect"
                           else QColor("#317ed8")))
                if marker["event_id"] == self.eid():
                    text = self.map_scene.addText(marker["event_id"][:12])
                    text.setPos(x*scale, (y+1)*scale)

        def preview(self):
            if not self.eid():
                return
            try:
                result = self.studio.preview(self.mid(), self.eid())
                self.diagnostics.setPlainText("\n".join(result["lines"]))
                self.tabs.setCurrentIndex(self.tabs.count()-1)
            except Exception as exc:
                QMessageBox.warning(self, "Simulation impossible", str(exc))

        def debug(self):
            if not self.eid():
                return
            try:
                result = self.studio.debugger(self.mid(), self.eid())
                self.diagnostics.setPlainText("\n".join(result["lines"]))
                self.tabs.setCurrentIndex(self.tabs.count()-1)
            except Exception as exc:
                QMessageBox.warning(self, "Diagnostic impossible", str(exc))

        def qa(self):
            try:
                issues = self.studio.diagnostics(self.mid())
                self.diagnostics.setPlainText(
                    "\n".join(row["severity"] + " : " + row["message"]
                               for row in issues) if issues else
                    "Intégrité structurelle validée par Content / GameProject.\n"
                    "Atteignabilité narrative complète et replay certifié : à intégrer.")
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
