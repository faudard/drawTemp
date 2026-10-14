"""R10 Qt 6 Campaign, World & Siege workspace (optional PySide6 only)."""
from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QGraphicsScene,
    QGraphicsView, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter, QTabWidget,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.campaign_studio import CampaignStudio
from sporebound.campaign_path_certification import certify_path
from sporebound.studio_transaction import StudioTransactionStore


def _pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _button(label, callback, parent):
    button = QPushButton(label, parent)
    button.clicked.connect(callback)
    return button


class _CertificateSignals(QObject):
    ready = Signal(object, int)
    failed = Signal(str, int)


class _CertificateWorker(QRunnable):
    """Certify on detached documents, never against a live editor handle."""

    def __init__(self, content, project, plan, revision):
        super().__init__()
        self.content, self.project = content, project
        self.plan, self.revision = plan, revision
        self.signals = _CertificateSignals()

    def run(self):
        try:
            report = certify_path(self.content, self.project, self.plan)
        except Exception as exc:
            self.signals.failed.emit(str(exc), self.revision)
        else:
            self.signals.ready.emit(report, self.revision)


class CampaignWindow(QMainWindow):
    def __init__(self, studio, *, source=None, opened=False):
        super().__init__()
        self.studio = studio
        self.source = Path(source) if source is not None else None
        self.opened = opened
        self._worker = None
        self.setWindowTitle("DrawTemp 5.0 — Campagnes & sièges")
        self.resize(1350, 850)

        root = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("EXPLORATEUR DE CAMPAGNE"))
        self.campaign = QComboBox()
        self.campaign.currentIndexChanged.connect(self._select_campaign)
        left_layout.addWidget(self.campaign)
        self.explorer = QTreeWidget()
        self.explorer.setHeaderLabels(["Campagne / missions", "État"])
        left_layout.addWidget(self.explorer)
        root.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        toolbar = QHBoxLayout()
        for label, action in [
            ("Annuler", self._undo), ("Rétablir", self._redo),
            ("Enregistrer", self._save), ("Enregistrer sous…", self._save_as),
        ]:
            toolbar.addWidget(_button(label, action, right))
        toolbar.addStretch(1)
        right_layout.addLayout(toolbar)
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)
        root.addWidget(right)
        root.setStretchFactor(0, 1)
        root.setStretchFactor(1, 3)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Les changements sont validés avant leur application.")
        self._graph_tab()
        self._world_tab()
        self._flow_tab()
        self._siege_tab()
        self._qa_tab()
        self._refresh()

    def _form_tab(self, name):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.tabs.addTab(page, name)
        return page, layout

    def _graph_tab(self):
        page, layout = self._form_tab("Graphe de missions")
        self.graph_scene = QGraphicsScene()
        layout.addWidget(QGraphicsView(self.graph_scene), 1)
        bar = QHBoxLayout()
        self.origin = QComboBox()
        self.destination = QComboBox()
        bar.addWidget(QLabel("De"))
        bar.addWidget(self.origin, 1)
        bar.addWidget(QLabel("Vers"))
        bar.addWidget(self.destination, 1)
        layout.addLayout(bar)
        controls = QHBoxLayout()
        for label, callback in [
            ("Relier", lambda: self._link(True)),
            ("Délier", lambda: self._link(False)),
            ("Définir comme départ", self._set_start),
        ]:
            controls.addWidget(_button(label, callback, page))
        layout.addLayout(controls)
        layout.addWidget(QLabel(
            "Arêtes = next_missions canonique. Les actes et chapitres sont "
            "regroupés visuellement par distance depuis la mission initiale."))

    def _world_tab(self):
        page, layout = self._form_tab("Carte du monde")
        self.world_scene = QGraphicsScene()
        layout.addWidget(QGraphicsView(self.world_scene), 1)
        bar = QHBoxLayout()
        self.theme = QComboBox()
        self.theme.addItems(["parchment", "kingdom", "forest", "winter"])
        bar.addWidget(QLabel("Ambiance"))
        bar.addWidget(self.theme)
        bar.addWidget(_button("Créer la carte", self._init_world, page))
        layout.addLayout(bar)
        fields = QHBoxLayout()
        self.world_x, self.world_y = QSpinBox(), QSpinBox()
        for spin in (self.world_x, self.world_y):
            spin.setRange(24, 4000)
        self.world_x.setValue(160)
        self.world_y.setValue(160)
        self.region = QLineEdit()
        self.region.setPlaceholderText("Région")
        for label, widget in [("X", self.world_x), ("Y", self.world_y),
                              ("Région", self.region)]:
            fields.addWidget(QLabel(label))
            fields.addWidget(widget)
        fields.addWidget(_button("Positionner la mission sélectionnée",
                                 self._move_world, page))
        layout.addLayout(fields)
        layout.addWidget(QLabel(
            "Les points de la carte ne changent jamais les coordonnées tactiques."))

    def _flow_tab(self):
        page, layout = self._form_tab("Conditions & conséquences")
        gate = QGroupBox("Déverrouillage et fins")
        form = QFormLayout(gate)
        self.condition_target = QComboBox()
        self.condition_target.addItems(["gate", "ending"])
        self.condition_id = QLineEdit()
        self.condition_id.setPlaceholderText(
            "ID de mission (gate) ou ID de fin (ending)")
        self.condition_kind = QComboBox()
        self.condition_kind.addItems([
            "flag_eq", "flag_gte", "flag_lte", "completed_mission", "gold_gte"])
        self.condition_key = QLineEdit()
        self.condition_value = QLineEdit()
        for name, widget in [
            ("Cible", self.condition_target), ("Identifiant", self.condition_id),
            ("Prédicat", self.condition_kind), ("Flag / mission", self.condition_key),
            ("Valeur", self.condition_value),
        ]:
            form.addRow(name, widget)
        form.addRow(_button("Appliquer la condition", self._set_condition, page))
        form.addRow(_button("Supprimer la condition", self._remove_condition, page))
        layout.addWidget(gate)

        effects = QGroupBox("Conséquence après mission")
        ef = QFormLayout(effects)
        self.result = QComboBox()
        self.result.addItems(["victory", "defeat"])
        self.effect_kind = QComboBox()
        self.effect_kind.addItems([
            "set_flag", "add_flag", "unlock_mission", "recruit_hero",
            "grant_item", "equip_hero", "gold", "wound", "heal_wound"])
        self.effect_name = QLineEdit()
        self.effect_value = QLineEdit()
        for name, widget in [
            ("Résultat", self.result), ("Effet", self.effect_kind),
            ("Flag / personnage / objet", self.effect_name),
            ("Valeur / quantité", self.effect_value),
        ]:
            ef.addRow(name, widget)
        ef.addRow(_button("Ajouter à la mission sélectionnée",
                          self._add_consequence, page))
        layout.addWidget(effects)
        layout.addWidget(QLabel(
            "Les scènes, spawns et changements de carte déjà définis restent "
            "dans les systèmes StoryBook / Exploration existants."))
        layout.addStretch(1)

    def _siege_tab(self):
        page, layout = self._form_tab("Siège multi-fronts")
        actions = QHBoxLayout()
        self.siege = QComboBox()
        actions.addWidget(QLabel("Siège"))
        actions.addWidget(self.siege, 1)
        actions.addWidget(_button("Créer un siège", self._create_siege, page))
        layout.addLayout(actions)
        form = QFormLayout()
        self.front_id = QLineEdit()
        self.front_id.setPlaceholderText("ex. remparts")
        self.strength, self.opposition = QSpinBox(), QSpinBox()
        for spin in (self.strength, self.opposition):
            spin.setRange(0, 1000)
            spin.setValue(10)
        self.doctrine = QComboBox()
        self.doctrine.addItems(["hold", "assault", "delay", "retreat"])
        for name, widget in [
            ("Nouveau front", self.front_id), ("Force", self.strength),
            ("Opposition", self.opposition), ("Doctrine", self.doctrine),
        ]:
            form.addRow(name, widget)
        form.addRow(_button("Ajouter le front (mission sélectionnée)",
                            self._add_front, page))
        layout.addLayout(form)
        finale = QHBoxLayout()
        self.final_front = QComboBox()
        self.required_front = QComboBox()
        finale.addWidget(QLabel("Final"))
        finale.addWidget(self.final_front)
        finale.addWidget(QLabel("Requiert victoire de"))
        finale.addWidget(self.required_front)
        finale.addWidget(_button("Configurer la finale", self._finale, page))
        layout.addLayout(finale)
        layout.addWidget(_button("Simuler 8 tours stratégiques (hors combat)",
                                 self._siege_timeline, page))
        self.siege_output = QTextEdit()
        self.siege_output.setReadOnly(True)
        layout.addWidget(self.siege_output, 1)

    def _qa_tab(self):
        page, layout = self._form_tab("Simulation & certification")
        layout.addWidget(QLabel(
            "Simulation symbolique : aucune victoire tactique ne peut être certifiée ici."))
        row = QHBoxLayout()
        self.simulation_action = QComboBox()
        row.addWidget(self.simulation_action, 1)
        row.addWidget(_button("Appliquer l'hypothèse", self._simulation_step, page))
        row.addWidget(_button("Branche alternative", self._fork, page))
        layout.addLayout(row)
        toolbar = QHBoxLayout()
        toolbar.addWidget(_button("Audit des chemins", self._audit, page))
        self.certify_button = _button("Certifier la branche par combat + replay",
                                      self._certify, page)
        toolbar.addWidget(self.certify_button)
        toolbar.addWidget(_button("Exporter le jeu (ZIP source)", self._export, page))
        layout.addLayout(toolbar)
        self.qa_output = QTextEdit()
        self.qa_output.setReadOnly(True)
        layout.addWidget(self.qa_output, 1)

    def _selected_mission(self):
        return self.origin.currentData()

    def _selected_siege(self):
        return self.siege.currentData()

    def _act(self, operation, message="Modification appliquée"):
        try:
            result = operation()
            self._refresh()
            self.statusBar().showMessage(message, 5000)
            return result
        except Exception as exc:
            QMessageBox.warning(self, "Modification refusée", str(exc))
            return None

    def _populate(self, combo, rows):
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for title, value in rows:
            combo.addItem(title, value)
        index = combo.findData(previous)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _refresh(self):
        data = self.studio.overview()
        campaigns = [(row["name"], row["id"]) for row in data["campaigns"]]
        self._populate(self.campaign, campaigns)
        self.campaign.setCurrentIndex(self.campaign.findData(data["active_campaign"]))
        missions = [(row["name"], row["id"]) for row in data["missions"]]
        self._populate(self.origin, missions)
        self._populate(self.destination, missions)
        self._populate(self.siege, [(row["id"], row["id"]) for row in data["sieges"]])
        self._refresh_tree(data)
        self._draw_graph(data)
        self._draw_world(data)
        current = self._selected_siege()
        blueprint = next((x for x in data["sieges"] if x["id"] == current), None)
        fronts = [(fid, fid) for fid in blueprint["fronts"]] if blueprint else []
        self._populate(self.final_front, fronts)
        self._populate(self.required_front, fronts)
        self.siege_output.setPlainText(
            _pretty(blueprint) if blueprint else "Créer un siège depuis une mission.")
        try:
            self._refresh_simulation()
        except Exception as exc:
            self.qa_output.setPlainText(str(exc))
        self.setWindowTitle(
            "DrawTemp 5.0 — Campagnes & sièges" + (" *" if data["dirty"] else ""))

    def _refresh_tree(self, data):
        self.explorer.clear()
        graph = data["graph"]
        depths = {mid: int((xy[0] - 80) / 190)
                  for mid, xy in graph["positions"].items()}
        root = QTreeWidgetItem([data["active_campaign"], "Campagne"])
        self.explorer.addTopLevelItem(root)
        chapters = {}
        for mission in data["missions"]:
            mid = mission["id"]
            depth = depths.get(mid, -1)
            if depth not in chapters:
                item = QTreeWidgetItem(
                    [("Hors parcours" if mid in graph["unreachable"]
                      else "Étape " + str(depth + 1)), "Groupe visuel"])
                root.addChild(item)
                chapters[depth] = item
            chapters[depth].addChild(QTreeWidgetItem([mission["name"], mid]))
        if data["scenes"]:
            scenes = QTreeWidgetItem(["Événements", str(len(data["scenes"]))])
            root.addChild(scenes)
            for scene in data["scenes"]:
                scenes.addChild(QTreeWidgetItem(
                    [scene.get("title", scene["id"]), scene["id"]]))
        endings = QTreeWidgetItem(
            ["Fins", str(len(data["flow"].get("endings", {})))])
        root.addChild(endings)
        for ending in data["flow"].get("endings", {}):
            endings.addChild(QTreeWidgetItem([ending, "Fin conditionnelle"]))
        self.explorer.expandToDepth(1)

    def _draw_graph(self, data):
        scene = self.graph_scene
        scene.clear()
        positions = data["graph"]["positions"]
        pen = QPen(QColor("#75879a"), 2)
        for source, target in data["graph"]["edges"]:
            x1, y1 = positions[source]
            x2, y2 = positions[target]
            scene.addLine(x1 + 35, y1 + 20, x2 + 35, y2 + 20, pen)
        names = {row["id"]: row["name"] for row in data["missions"]}
        for mid, (x, y) in positions.items():
            unreachable = mid in data["graph"]["unreachable"]
            scene.addRoundedRect(x, y, 152, 54, 12, 12,
                                 QPen(QColor("#596d82")),
                                 QBrush(QColor("#8f5555" if unreachable else "#31516f")))
            item = scene.addText(names[mid][:26])
            item.setDefaultTextColor(QColor("#ffffff"))
            item.setPos(x + 8, y + 8)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-30, -30, 35, 35))

    def _draw_world(self, data):
        scene = self.world_scene
        scene.clear()
        world = data["world"]
        positions = {n["mission"]: (n["x"], n["y"]) for n in world["nodes"]}
        for start, end in world["edges"]:
            a, b = positions[start], positions[end]
            scene.addLine(*a, *b, QPen(QColor("#a79c75"), 3))
        for node in world["nodes"]:
            x, y = node["x"], node["y"]
            scene.addEllipse(x - 11, y - 11, 22, 22,
                             QPen(QColor("#233c44"), 2),
                             QBrush(QColor("#c9aa67")))
            item = scene.addText(node["label"][:24])
            item.setPos(x + 14, y - 17)
        scene.setSceneRect(0, 0, world["width"], world["height"])

    def _refresh_simulation(self):
        actions = self.studio.simulation_actions()
        self._populate(self.simulation_action, [
            (("Choix : " + row.get("label", row["id"]))
             if row["kind"] == "choice" else
             "Mission : " + row["id"] + " → " + row["outcome"],
             (row["kind"], row["id"], row.get("outcome")))
            for row in actions])
        self.qa_output.setPlainText(_pretty(self.studio.simulation_inspect()))

    def _select_campaign(self, _index):
        cid = self.campaign.currentData()
        if cid and cid != self.studio.campaign_id:
            self._act(lambda: self.studio.select_campaign(cid), "Campagne sélectionnée")

    def _link(self, enabled):
        self._act(lambda: self.studio.link_missions(
            self._selected_mission(), self.destination.currentData(), enabled))

    def _set_start(self):
        self._act(lambda: self.studio.set_start_mission(self._selected_mission()))

    def _init_world(self):
        self._act(lambda: self.studio.initialize_world(self.theme.currentText()))

    def _move_world(self):
        self._act(lambda: self.studio.move_location(
            self._selected_mission(), self.world_x.value(), self.world_y.value(),
            self.region.text()))

    def _set_condition(self):
        name = self.condition_id.text().strip()
        if self.condition_target.currentText() == "gate" and not name:
            name = self._selected_mission()
        self._act(lambda: self.studio.set_condition(
            self.condition_target.currentText(), name,
            self.condition_kind.currentText(),
            self.condition_key.text(), self.condition_value.text()))

    def _remove_condition(self):
        name = self.condition_id.text().strip()
        if self.condition_target.currentText() == "gate" and not name:
            name = self._selected_mission()
        self._act(lambda: self.studio.remove_condition(
            self.condition_target.currentText(), name))

    def _add_consequence(self):
        self._act(lambda: self.studio.add_consequence(
            self._selected_mission(), self.result.currentText(),
            self.effect_kind.currentText(), self.effect_name.text(),
            self.effect_value.text()))

    def _create_siege(self):
        name, ok = QInputDialog.getText(self, "Nouveau siège", "Identifiant")
        if ok and name.strip():
            self._act(lambda: self.studio.create_siege(
                name.strip(), self._selected_mission()))

    def _add_front(self):
        self._act(lambda: self.studio.add_siege_front(
            self._selected_siege(), self.front_id.text().strip(),
            self._selected_mission(), strength=self.strength.value(),
            opposition=self.opposition.value(),
            doctrine=self.doctrine.currentText()))

    def _finale(self):
        self._act(lambda: self.studio.set_siege_finale(
            self._selected_siege(), self.final_front.currentData(),
            {self.required_front.currentData(): ["victory"]}))

    def _siege_timeline(self):
        try:
            self.siege_output.setPlainText(_pretty(
                self.studio.siege_timeline(self._selected_siege())))
        except Exception as exc:
            QMessageBox.warning(self, "Aperçu refusé", str(exc))

    def _simulation_step(self):
        action = self.simulation_action.currentData()
        if not action:
            return
        if action[0] == "choice":
            self._act(lambda: self.studio.simulation_choose(action[1]),
                      "Hypothèse narrative (sans combat)")
        else:
            self._act(lambda: self.studio.simulation_resolve(action[1], action[2]),
                      "Hypothèse de résultat (non certifiée)")

    def _fork(self):
        self._act(lambda: self.studio.simulation_fork(),
                  "Branche symbolique créée")

    def _audit(self):
        try:
            self.qa_output.setPlainText(_pretty(self.studio.audit()))
        except Exception as exc:
            QMessageBox.warning(self, "Audit refusé", str(exc))

    def _certify(self):
        try:
            plan = self.studio.candidate_path()
            content, project = self.studio._models()
            worker = _CertificateWorker(content, project, plan, self.studio.revision)
        except Exception as exc:
            QMessageBox.warning(self, "Parcours incomplet", str(exc))
            return
        self.certify_button.setEnabled(False)
        self.qa_output.setPlainText("Certification tactique réelle en cours…")
        worker.signals.ready.connect(self._certificate_ready)
        worker.signals.failed.connect(self._certificate_failed)
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def _certificate_ready(self, report, revision):
        self.certify_button.setEnabled(True)
        self._worker = None
        if revision != self.studio.revision:
            self.qa_output.setPlainText(
                "Document modifié pendant la vérification : preuve obsolète.\n" +
                _pretty(report))
        else:
            self.qa_output.setPlainText(_pretty(report))

    def _certificate_failed(self, message, revision):
        self.certify_button.setEnabled(True)
        self._worker = None
        self.qa_output.setPlainText(
            "Échec de certification à la révision " +
            str(revision) + "\n" + message)

    def _undo(self):
        self._act(self.studio.undo, "Annulation effectuée")

    def _redo(self):
        self._act(self.studio.redo, "Rétablissement effectué")

    def _save(self):
        if not self.opened:
            self._save_as()
        else:
            self._act(self.studio.save, "Contenu et projet enregistrés")

    def _save_as(self):
        candidate, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le contenu et son projet", str(self.source or "content.json"),
            "Content JSON (*.json)")
        if candidate:
            def save():
                paths = self.studio.save_as(candidate)
                self.opened, self.source = True, Path(candidate)
                return paths
            self._act(save, "Deux documents enregistrés atomiquement")

    def _export(self):
        destination, _ = QFileDialog.getSaveFileName(
            self, "Exporter les sources jouables (Python et Tk requis)",
            "campaign.zip", "ZIP (*.zip)")
        if not destination:
            return
        assets = QFileDialog.getExistingDirectory(
            self, "Répertoire racine des assets",
            str(self.source.parent if self.source else Path.cwd()))
        if not assets:
            return
        self._act(lambda: self.studio.export_source_bundle(assets, destination),
                  "Bundle ZIP source exporté (pas un exécutable Qt)")

    def closeEvent(self, event):
        if self.studio.authoring.snapshot().dirty:
            choice = QMessageBox.question(
                self, "Modifications non enregistrées",
                "Quitter sans enregistrer les modifications ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()


def _open_studio(path, campaign):
    content_path = Path(path) if path else Path(
        str(files("sporebound").joinpath("content/jeanne.json")))
    store = StudioTransactionStore(content_path)
    if store.pending:
        raise ValueError("Journal de sauvegarde interrompue : restauration explicite requise")
    existing = [p.is_file() for p in store.paths]
    if all(existing):
        return CampaignStudio.open(content_path, campaign), content_path, True
    if any(existing):
        raise ValueError("Un seul des deux documents existe : réparation nécessaire")
    content = Content.load(content_path)
    project = GameProject.default(content)
    return CampaignStudio.new(content, project, campaign), content_path, False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", help="Contenu tactique JSON existant")
    parser.add_argument("--campaign", default="main")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    try:
        studio, content_path, opened = _open_studio(args.content, args.campaign)
    except Exception as exc:
        parser.error(str(exc))
    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = CampaignWindow(studio, source=content_path, opened=opened)
    window.show()
    if args.smoke:
        QTimer.singleShot(150, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
