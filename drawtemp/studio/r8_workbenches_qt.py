"""R8.B native Qt Widgets: class/talent DAG and real mission encounter authoring.

Views are projections of Content v1. No gameplay logic or document copies live
in Qt; all edits go through RulesWorkbench -> R1 AuthoringSession.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPen, QPainterPath
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.studio.r8_advanced import RulesWorkbench
from sporebound.character_authoring import parse_bonuses
from sporebound.model import RuleError
from sporebound.rules import default_rules


def _ids(text):
    return [value.strip() for value in text.split(",") if value.strip()]


def draw_dag(view, graph, *, title):
    """Read-only DAG projection of the existing validated class/talent graph."""
    scene = QGraphicsScene(view)
    positions = {row["id"]: (float(row["x"]), float(row["y"]))
                 for row in graph["nodes"]}
    pen = QPen(QColor("#64748b"), 2)
    for edge in graph["edges"]:
        start, end = positions[edge["from"]], positions[edge["to"]]
        scene.addLine(start[0] + 125, start[1] + 25,
                      end[0], end[1] + 25, pen)
    for node in graph["nodes"]:
        x, y = positions[node["id"]]
        path = QPainterPath()
        path.addRoundedRect(x, y, 125, 50, 7, 7)
        scene.addPath(path, QPen(QColor("#475569")),
                      QBrush(QColor("#e0f2fe")))
        label = str(node.get("label", node["id"]))
        if "jp" in node:
            label += " • " + str(node["jp"]) + " JP"
        text = scene.addText(label)
        text.setDefaultTextColor(QColor("#0f172a"))
        text.setPos(x + 5, y + 8)
    scene.setSceneRect(0, 0, max(400, graph["width"]),
                       max(175, graph["height"]))
    view.setScene(scene)
    view.setAccessibleName(title)


class TalentDialog(QDialog):
    """Class prerequisite and talent tree authoring, no JSON forms."""

    def __init__(self, session, *, selected_job="", on_change=None, parent=None):
        super().__init__(parent)
        self.workbench = RulesWorkbench(session)
        self.on_change = on_change
        self.setWindowTitle("R8 — Classes, talents et spécialisations")
        self.resize(1180, 780)
        outer = QVBoxLayout(self)
        controls = QHBoxLayout()
        outer.addLayout(controls)
        controls.addWidget(QLabel("Classe"))
        self.job = QComboBox()
        self.job.addItems(self.workbench.jobs())
        if selected_job:
            self.job.setCurrentText(selected_job)
        controls.addWidget(self.job, 2)
        controls.addWidget(QLabel("Classe requise"))
        self.parent_job = QComboBox()
        self.parent_job.addItem("—", "")
        for key in self.workbench.jobs():
            self.parent_job.addItem(key, key)
        controls.addWidget(self.parent_job, 2)
        self.level = QSpinBox()
        self.level.setRange(1, 20)
        controls.addWidget(QLabel("Niveau"))
        controls.addWidget(self.level)
        link = QPushButton("Appliquer le prérequis")
        link.clicked.connect(self._link)
        controls.addWidget(link)

        graphs = QSplitter(Qt.Horizontal)
        outer.addWidget(graphs, 2)
        self.job_graph = QGraphicsView()
        self.talent_graph = QGraphicsView()
        graphs.addWidget(self.job_graph)
        graphs.addWidget(self.talent_graph)
        graphs.setSizes([450, 650])

        form = QFormLayout()
        outer.addLayout(form)
        self.talent = QComboBox()
        self.talent.setEditable(True)
        self.talent.setAccessibleName("Identifiant de talent")
        form.addRow("Talent (nouvel ID ou existant)", self.talent)
        self.jp = QSpinBox()
        self.jp.setRange(1, 20)
        form.addRow("Coût JP", self.jp)
        self.requires = QLineEdit()
        self.requires.setPlaceholderText("talent_A, talent_B")
        form.addRow("Prérequis (IDs)", self.requires)
        self.exclusive = QLineEdit()
        form.addRow("Groupe de spécialisation exclusive", self.exclusive)
        self.bonuses = QLineEdit()
        self.bonuses.setPlaceholderText("defense=2, max_hp=5")
        form.addRow("Bonus", self.bonuses)
        self.skills = QLineEdit()
        self.skills.setPlaceholderText("competence_A, competence_B")
        form.addRow("Compétences accordées", self.skills)
        buttons = QHBoxLayout()
        outer.addLayout(buttons)
        for text, action in (("Créer le talent", self._create),
                             ("Modifier le talent", self._save),
                             ("Supprimer le talent", self._delete),
                             ("Fermer", self.close)):
            btn = QPushButton(text)
            btn.clicked.connect(action)
            buttons.addWidget(btn)
        self.info = QLabel("Les graphes sont dérivés des classes et talents réels.")
        outer.addWidget(self.info)
        self.job.currentTextChanged.connect(self._refresh)
        self.talent.currentTextChanged.connect(self._load_talent)
        self._refresh()

    def _refresh(self, *_):
        job_id = self.job.currentText()
        if not job_id:
            return
        spec = self.workbench.documents()["content"]["jobs"][job_id]
        parent = spec.get("requires", "")
        self.parent_job.blockSignals(True)
        self.parent_job.setCurrentIndex(self.parent_job.findData(parent))
        self.parent_job.blockSignals(False)
        self.level.setValue(spec.get("requires_level", 1))
        draw_dag(self.job_graph, self.workbench.class_graph(),
                 title="Graphe des classes")
        draw_dag(self.talent_graph, self.workbench.talent_graph(job_id),
                 title="Graphe des talents")
        selected = self.talent.currentText()
        self.talent.blockSignals(True)
        self.talent.clear()
        names = sorted(self.workbench.talents(job_id))
        self.talent.addItems(names)
        if selected in names:
            self.talent.setCurrentText(selected)
        else:
            self.talent.setCurrentIndex(0 if names else -1)
        self.talent.blockSignals(False)
        self._load_talent()
        self.info.setText(f"{job_id} — {len(names)} talent(s)")

    def _load_talent(self, *_):
        job = self.job.currentText()
        if not job:
            return
        row = self.workbench.talents(job).get(self.talent.currentText())
        if row is None:
            self.jp.setValue(1)
            self.requires.clear()
            self.exclusive.clear()
            self.bonuses.clear()
            self.skills.clear()
            return
        self.jp.setValue(row.get("jp", 1))
        self.requires.setText(", ".join(row.get("requires", [])))
        self.exclusive.setText(row.get("exclusive", ""))
        self.bonuses.setText(", ".join(
            f"{key}={value}" for key, value in sorted(row.get("bonuses", {}).items())))
        self.skills.setText(", ".join(row.get("skills", [])))

    def _apply(self, operation, *args, **kwargs):
        try:
            result = operation(*args, **kwargs)
        except (RuleError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Modification refusée", str(exc))
            return
        self._refresh()
        if self.on_change:
            self.on_change()
        return result

    def _form(self):
        return dict(jp=self.jp.value(), requires=_ids(self.requires.text()),
                    exclusive=self.exclusive.text(),
                    bonuses=parse_bonuses(self.bonuses.text(), equipment=True),
                    skills=_ids(self.skills.text()))

    def _create(self):
        try:
            fields = self._form()
        except RuleError as exc:
            QMessageBox.warning(self, "Bonus invalide", str(exc))
            return
        self._apply(self.workbench.save_talent, self.job.currentText(),
                    self.talent.currentText().strip(), creating=True, **fields)

    def _save(self):
        try:
            fields = self._form()
        except RuleError as exc:
            QMessageBox.warning(self, "Bonus invalide", str(exc))
            return
        self._apply(self.workbench.save_talent, self.job.currentText(),
                    self.talent.currentText().strip(), creating=False, **fields)

    def _delete(self):
        key = self.talent.currentText()
        if not key:
            return
        if QMessageBox.question(self, "Supprimer le talent",
                                f"Supprimer le talent {key} ?") != QMessageBox.Yes:
            return
        self._apply(self.workbench.remove_talent, self.job.currentText(), key)

    def _link(self):
        self._apply(self.workbench.link_class, self.job.currentText(),
                    self.parent_job.currentData(), self.level.value())


class MapPickScene(QGraphicsScene):
    """Explicit pick updates the coordinate form; clicking never mutates Content."""
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.tile_size = 28
        self.width_cells = 1
        self.height_cells = 1

    def mousePressEvent(self, event):
        pt = event.scenePos()
        x, y = int(pt.x() // self.tile_size), int(pt.y() // self.tile_size)
        if 0 <= x < self.width_cells and 0 <= y < self.height_cells:
            self.callback(x, y)
        super().mousePressEvent(event)


class EncounterDialog(QDialog):
    """R8.8 authoring of real Mission.units, objectives and formations."""

    def __init__(self, session, *, mission_id="", on_change=None, parent=None):
        super().__init__(parent)
        self.workbench = RulesWorkbench(session)
        self.on_change = on_change
        self.setWindowTitle("R8 — Rencontres et composition d'escouades")
        self.resize(1150, 760)
        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        outer.addLayout(top)
        top.addWidget(QLabel("Mission"))
        self.mission_box = QComboBox()
        for key, name in self.workbench.missions():
            self.mission_box.addItem(f"{name} ({key})", key)
        if mission_id:
            index = self.mission_box.findData(mission_id)
            if index >= 0:
                self.mission_box.setCurrentIndex(index)
        top.addWidget(self.mission_box, 2)
        self.objective = QComboBox()
        self.objective.addItems(sorted(key for key, _ in default_rules().objectives.entries))
        top.addWidget(QLabel("Objectif"))
        top.addWidget(self.objective)
        self.reward = QSpinBox()
        self.reward.setRange(0, 1000000)
        top.addWidget(QLabel("Récompense"))
        top.addWidget(self.reward)
        save = QPushButton("Appliquer l'objectif")
        save.clicked.connect(self._save_objective)
        top.addWidget(save)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)
        self.scene = MapPickScene(self._picked)
        self.map = QGraphicsView(self.scene)
        self.map.setAccessibleName("Placement des unités — cliquez pour choisir une cellule")
        split.addWidget(self.map)
        panel = QWidget()
        pane = QVBoxLayout(panel)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Nom", "Équipe", "X", "Y"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selected)
        pane.addWidget(self.table, 1)

        form = QFormLayout()
        pane.addLayout(form)
        self.x = QSpinBox()
        self.y = QSpinBox()
        coords = QHBoxLayout()
        coords.addWidget(self.x)
        coords.addWidget(self.y)
        form.addRow("Cellule X / Y", coords)
        self.role = QComboBox()
        self.role.addItems(["none", "medic", "protector"])
        form.addRow("Rôle", self.role)
        self.formation = QComboBox()
        self.formation.addItems(["none", "shield_wall", "phalanx", "escort"])
        form.addRow("Formation", self.formation)
        self.escort = QLineEdit()
        self.escort.setPlaceholderText("ID de l'allié à escorter")
        form.addRow("Allié escorté", self.escort)

        buttons = QHBoxLayout()
        pane.addLayout(buttons)
        for title, callback in (
            ("Placer modèle", self._place), ("Déplacer", self._move),
            ("Formation", self._formation), ("Retirer", self._remove),
        ):
            btn = QPushButton(title)
            btn.clicked.connect(callback)
            buttons.addWidget(btn)
        split.addWidget(panel)
        split.setSizes([610, 520])
        self.status = QLabel()
        outer.addWidget(self.status)
        self.mission_box.currentIndexChanged.connect(self._refresh)
        self._refresh()

    def _mission(self):
        return self.mission_box.currentData()

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return ""
        return self.table.item(row, 0).text()

    def _picked(self, x, y):
        self.x.setValue(x)
        self.y.setValue(y)

    def _refresh(self, *_):
        mid = self._mission()
        if not mid:
            return
        mission = self.workbench.mission(mid)
        previous = self._selected_id()
        self.objective.setCurrentText(mission["objective"])
        self.reward.setValue(mission["reward"])
        board = mission["board"]
        w, h = board["width"], board["height"]
        self.x.setRange(0, w - 1)
        self.y.setRange(0, h - 1)
        self.scene.width_cells, self.scene.height_cells = w, h
        scale = self.scene.tile_size
        self.scene.clear()
        background = self.scene.addRect(0, 0, w * scale, h * scale,
                             QPen(QColor("#64748b")), QBrush(QColor("#f8fafc")))
        for x in range(1, w):
            self.scene.addLine(x * scale, 0, x * scale, h * scale,
                               QPen(QColor("#dbe2ea")))
        for y in range(1, h):
            self.scene.addLine(0, y * scale, w * scale, y * scale,
                               QPen(QColor("#dbe2ea")))
        for tile in board.get("tiles", []):
            if tile.get("blocked"):
                x, y = tile["pos"]
                self.scene.addRect(x * scale, y * scale, scale, scale,
                    QPen(QColor("#334155")), QBrush(QColor("#94a3b8")))
        units = self.workbench.units(mid)
        self.table.setRowCount(len(units))
        chosen_row = 0
        for row, unit in enumerate(units):
            for column, value in enumerate((
                    unit.id, unit.name, unit.team, unit.x, unit.y)):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
            if unit.id == previous:
                chosen_row = row
            tint = QColor("#0284c7") if unit.team == "player" else QColor("#dc2626")
            self.scene.addEllipse(unit.x * scale + 3, unit.y * scale + 3,
                                  scale - 6, scale - 6, QPen(tint), QBrush(tint))
            label = self.scene.addText(unit.id[:8])
            label.setDefaultTextColor(QColor("#1e293b"))
            label.setPos(unit.x * scale + 8, unit.y * scale - 12)
        if units:
            self.table.selectRow(chosen_row)
        self.status.setText(
            f"{mid} • {sum(u.team == 'player' for u in units)} alliés / "
            f"{sum(u.team == 'enemy' for u in units)} ennemis • "
            "aperçu de placement, pas une simulation")
        self._selected()

    def _selected(self):
        unit_id = self._selected_id()
        if not unit_id:
            return
        unit = next((u for u in self.workbench.units(self._mission())
                     if u.id == unit_id), None)
        if unit:
            self._picked(unit.x, unit.y)
            mission = self.workbench.mission(self._mission())
            raw = next(row for row in mission["units"] if row["id"] == unit_id)
            tags = raw.get("tags", [])
            self.role.setCurrentText(next(
                (t for t in tags if t in {"medic", "protector"}), "none"))
            form = next((t.split(":", 1)[1] for t in tags
                         if t.startswith("formation:")), "none")
            self.formation.setCurrentText(form.split(":")[0])
            self.escort.setText(form.split(":")[1] if ":" in form else "")

    def _apply(self, operation, *args, **kwargs):
        try:
            result = operation(*args, **kwargs)
        except (RuleError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Rencontre non modifiée", str(exc))
            return
        self._refresh()
        if self.on_change:
            self.on_change()
        return result

    def _place(self):
        names = sorted(self.workbench.documents()["content"].get("archetypes", {}))
        if not names:
            QMessageBox.information(self, "Aucun archétype",
                                    "Créez un modèle dans la Base RPG d'abord.")
            return
        name, ok = QInputDialog.getItem(
            self, "Placer un modèle", "Archétype", names, 0, False)
        if not ok:
            return
        uid, ok = QInputDialog.getText(self, "Nouvelle unité", "ID stable")
        if not ok or not uid.strip():
            return
        title, ok = QInputDialog.getText(self, "Nouvelle unité", "Nom",
                                         text=uid.strip())
        if not ok:
            return
        team, ok = QInputDialog.getItem(self, "Équipe", "Camp",
                                       ["enemy", "player"], 0, False)
        if ok:
            self._apply(self.workbench.add_actor, self._mission(), name,
                        uid.strip(), name=title, team=team,
                        cell=(self.x.value(), self.y.value()))

    def _move(self):
        unit_id = self._selected_id()
        if unit_id:
            self._apply(self.workbench.move_actor, self._mission(), unit_id,
                        (self.x.value(), self.y.value()))

    def _remove(self):
        unit_id = self._selected_id()
        if unit_id and QMessageBox.question(
            self, "Retirer l'unité", f"Retirer {unit_id} de cette mission ?"
        ) == QMessageBox.Yes:
            self._apply(self.workbench.remove_actor, self._mission(), unit_id)

    def _formation(self):
        unit_id = self._selected_id()
        if unit_id:
            self._apply(self.workbench.set_formation, self._mission(), unit_id,
                        role=self.role.currentText(),
                        formation=self.formation.currentText(),
                        escort_target=self.escort.text().strip())

    def _save_objective(self):
        self._apply(self.workbench.set_objective, self._mission(),
                    self.objective.currentText(), self.reward.value())
