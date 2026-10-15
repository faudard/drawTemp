"""Qt 6 Visual Battle Lab: executed AI decisions and observed HP flow.

The view only paints an R13.8 SDK trace model. All bars and lines are
measured events; click a step to navigate the canonical replay table.
"""
from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QScrollArea, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

PLAYER = QColor("#408dc8")
ENEMY = QColor("#d88754")
DAMAGE = QColor("#db645a")
HEAL = QColor("#3c9f78")
INK = QColor("#25374a")
GRID = QColor("#adbac6")
MUTED = QColor("#65798b")


class DecisionsCanvas(QWidget):
    """Action histogram grouped by real team; never an AI 'quality' score."""

    actionSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.filter_team = "all"
        self.rows = []
        self.setMinimumWidth(360)

    def set_report(self, model, *, team="all"):
        self.model = model
        self.filter_team = team
        totals = defaultdict(lambda: defaultdict(int))
        if model is not None:
            for row in model["team_actions"]:
                if team == "all" or row["team"] == team:
                    totals[row["action"]][row["team"]] += row["count"]
        self.rows = sorted(totals.items())
        self.setMinimumHeight(max(230, 78 + 48 * len(self.rows)))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), self.palette().base())
        p.setPen(INK)
        p.drawText(9, 22, "COMMANDES IA EXÉCUTÉES · PAR ÉQUIPE")
        if not self.rows:
            p.setPen(MUTED)
            p.drawText(QRectF(12, 36, self.width()-24, 66),
                       Qt.AlignmentFlag.AlignVCenter,
                       "Aucune trace de décisions pour ce filtre.")
            p.end()
            return
        left = 115
        available = max(40, self.width() - left - 85)
        peak = max(1, max(max(v.values()) for _, v in self.rows))
        for i, (action, counts) in enumerate(self.rows):
            y = 51 + i*48
            p.setPen(INK)
            p.drawText(QRectF(8, y, left - 12, 35),
                       Qt.AlignmentFlag.AlignVCenter, action)
            for j, (team, count) in enumerate(sorted(counts.items())):
                if j >= 3:
                    break
                color = PLAYER if team == "player" else (
                    ENEMY if team == "enemy" else MUTED)
                h = 9
                bar_y = y + 1 + j*12
                w = round(count / peak * available)
                if w:
                    p.fillRect(QRectF(left, bar_y, w, h), color)
                p.setPen(INK)
                p.drawText(QRectF(left + available + 6, bar_y - 4, 78, 18),
                           Qt.AlignmentFlag.AlignVCenter,
                           f"{team}: {count}")
            p.setPen(QPen(GRID, 1))
            p.drawLine(QPointF(9, y+40), QPointF(self.width()-9, y+40))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = int((event.position().y() - 51) // 48)
            if (event.position().y() >= 51 and
                    0 <= index < len(self.rows)):
                self.actionSelected.emit(self.rows[index][0])
                event.accept()
                return
        super().mousePressEvent(event)


class CombatCurve(QWidget):
    """Cumulative actual damage received and healing received by step."""

    stepSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.side = "all"
        self.actor_id = None
        self.series = []
        self.selected_step = None
        self.setMinimumSize(400, 250)
        self.setMouseTracking(True)

    def set_report(self, model, *, side="all", actor_id=None):
        self.model = model
        self.side = side
        self.actor_id = actor_id
        self.selected_step = None
        self._recompute()
        self.update()

    def _recompute(self):
        self.series = []
        if self.model is None:
            return
        if self.actor_id:
            selected = self.actor_id
            delta = defaultdict(lambda: [0, 0])
            for event in self.model["combat_events"]:
                if event["target"] == selected:
                    delta[event["step"]][0 if event["kind"] == "damage" else 1] += event["amount"]
            d = h = 0
            for point in self.model["curve"]:
                amount = delta[point["step"]]
                d += amount[0]
                h += amount[1]
                self.series.append((point["step"], d, h))
            return
        for point in self.model["curve"]:
            if self.side == "all":
                d = point["damage_player"] + point["damage_enemy"]
                h = point["heal_player"] + point["heal_enemy"]
            else:
                d = point["damage_" + self.side]
                h = point["heal_" + self.side]
            self.series.append((point["step"], d, h))

    def _bounds(self):
        return 56, 62, max(40, self.width() - 91), max(55, self.height() - 123)

    def _nearest(self, px):
        if not self.series:
            return None
        x, _, w, _ = self._bounds()
        ratio = min(1., max(0., (px-x)/w))
        return min(len(self.series)-1, int(round(ratio * (len(self.series)-1))))

    def select_step(self, step):
        if self.model is None:
            return
        if type(step) is int and 0 <= step < len(self.series):
            self.selected_step = step
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), self.palette().base())
        p.setPen(INK)
        p.drawText(11, 23, "DÉGÂTS / SOINS OBSERVÉS · CUMUL PAR COMMANDE")
        if not self.series:
            p.setPen(MUTED)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Simuler un combat pour examiner ses événements réels.")
            p.end()
            return
        x, y, w, h = self._bounds()
        peak = max(1, max(max(d, heal) for _, d, heal in self.series))
        for fraction in (0, .25, .5, .75, 1):
            yv = y + h*(1-fraction)
            p.setPen(QPen(GRID, 1))
            p.drawLine(QPointF(x, yv), QPointF(x+w, yv))
            p.setPen(MUTED)
            p.drawText(QRectF(5, yv-9, x-11, 18),
                       Qt.AlignmentFlag.AlignRight,
                       str(round(peak*fraction)))
        for col, color in ((1, DAMAGE), (2, HEAL)):
            poly = QPolygonF([
                QPointF(x+(i / max(1, len(self.series)-1))*w,
                        y+h-(point[col]/peak)*h)
                for i, point in enumerate(self.series)
            ])
            p.setPen(QPen(color, 2.4))
            p.drawPolyline(poly)
        p.setPen(INK)
        p.drawText(QRectF(x, y+h+5, w, 20),
                   Qt.AlignmentFlag.AlignCenter,
                   f"Commande (0 à {self.series[-1][0]})")
        p.setPen(QPen(DAMAGE, 3))
        p.drawLine(QPointF(x+10, y+h+34), QPointF(x+39, y+h+34))
        p.setPen(INK)
        p.drawText(x+44, y+h+39, "PV perdus")
        p.setPen(QPen(HEAL, 3))
        p.drawLine(QPointF(x+150, y+h+34), QPointF(x+179, y+h+34))
        p.setPen(INK)
        p.drawText(x+184, y+h+39, "PV soignés")
        if self.selected_step is not None:
            i = self.selected_step
            px = x+(i / max(1, len(self.series)-1))*w
            p.setPen(QPen(MUTED, 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(px, y), QPointF(px, y+h))
        p.end()

    def mouseMoveEvent(self, event):
        index = self._nearest(event.position().x())
        if index is not None:
            step, damage, healing = self.series[index]
            self.setToolTip(
                f"Commande #{step}\nPV perdus cumulés : {damage}\n"
                f"PV restaurés cumulés : {healing}")
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.series):
            index = self._nearest(event.position().x())
            if index is not None:
                self.select_step(index)
                self.stepSelected.emit(self.series[index][0])
                event.accept()
                return
        super().mousePressEvent(event)


class R13AICombatPanel(QWidget):
    """Integrated AI decisions, HP flow and existing diagnostic signal evidence."""

    stepSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        outer = QVBoxLayout(self)
        self.summary = QLabel("Lancer une simulation avec trace pour analyser décisions et PV.")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)
        controls = QHBoxLayout()
        outer.addLayout(controls)
        controls.addWidget(QLabel("Équipe IA"))
        self.team = QComboBox()
        for title, value in (("Toutes", "all"), ("Joueurs", "player"),
                             ("Ennemis", "enemy")):
            self.team.addItem(title, value)
        self.team.currentIndexChanged.connect(self._refresh_decisions)
        controls.addWidget(self.team)
        controls.addWidget(QLabel("Dégâts / soins"))
        self.focus = QComboBox()
        self.focus.addItem("Toutes les équipes", ("all", None))
        self.focus.addItem("Équipe joueur", ("player", None))
        self.focus.addItem("Équipe ennemie", ("enemy", None))
        self.focus.currentIndexChanged.connect(self._refresh_curve)
        controls.addWidget(self.focus, 1)
        content = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(content, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.decisions = DecisionsCanvas()
        self.decisions.actionSelected.connect(self._select_action)
        scroll.setWidget(self.decisions)
        content.addWidget(scroll)
        self.curve = CombatCurve()
        self.curve.stepSelected.connect(self._step_from_curve)
        content.addWidget(self.curve)
        content.setSizes([430, 720])
        self.details = QLabel("")
        self.details.setWordWrap(True)
        outer.addWidget(self.details)
        outer.addWidget(QLabel(
            "Diagnostics IA (indices heuristiques, pas une preuve de mauvais choix)"))
        self.signals = QTableWidget(0, 4)
        self.signals.setHorizontalHeaderLabels(
            ["Commande", "Unité", "Signal", "Interprétation"])
        self.signals.itemSelectionChanged.connect(self._signal_selected)
        self.signals.setMaximumHeight(160)
        outer.addWidget(self.signals)

    def clear(self):
        self.model = None
        self.decisions.set_report(None)
        self.curve.set_report(None)
        self.focus.blockSignals(True)
        self.focus.clear()
        for label, value in (("Toutes les équipes", ("all", None)),
                             ("Équipe joueur", ("player", None)),
                             ("Équipe ennemie", ("enemy", None))):
            self.focus.addItem(label, value)
        self.focus.blockSignals(False)
        self.signals.setRowCount(0)
        self.details.clear()
        self.summary.setText(
            "Lancer une simulation avec trace pour analyser décisions et PV.")

    def set_report(self, model):
        if model.get("kind") != "r13_ai_combat_visuals":
            raise ValueError("A verified R13 AI and HP telemetry model is required")
        self.model = model
        self.summary.setText(
            f"Mission {model['mission']} · seed {model['seed']} · "
            f"{model['steps']} commandes · replay vérifié. "
            "Dégâts et soins effectivement enregistrés, sans temps humain estimé.")
        self.focus.blockSignals(True)
        self.focus.clear()
        self.focus.addItem("Toutes les équipes", ("all", None))
        self.focus.addItem("Équipe joueur", ("player", None))
        self.focus.addItem("Équipe ennemie", ("enemy", None))
        for uid in sorted(model["unit_teams"]):
            self.focus.addItem(
                f"Unité : {uid} ({model['unit_teams'][uid]})",
                ("all", uid))
        self.focus.setCurrentIndex(0)
        self.focus.blockSignals(False)
        self._refresh_decisions()
        self._refresh_curve()
        evidence = model["signal_evidence"]
        self.signals.setRowCount(len(evidence))
        for index, signal in enumerate(evidence):
            fields = [
                signal["step"], signal["actor"], signal["signal"],
                "À vérifier dans le replay : signal heuristique",
            ]
            for col, value in enumerate(fields):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.signals.setItem(index, col, item)
        self.details.setText(
            "Dégâts reçus : joueurs {} PV, ennemis {} PV · "
            "Soins reçus : joueurs {} PV, ennemis {} PV".format(
                model["team_damage_received"].get("player", 0),
                model["team_damage_received"].get("enemy", 0),
                model["team_healing_received"].get("player", 0),
                model["team_healing_received"].get("enemy", 0)))

    def _refresh_decisions(self, _index=None):
        self.decisions.set_report(
            self.model, team=self.team.currentData() or "all")

    def _refresh_curve(self, _index=None):
        side, actor = self.focus.currentData() or ("all", None)
        self.curve.set_report(self.model, side=side, actor_id=actor)

    def _select_action(self, action):
        if self.model is None:
            return
        counts = [
            f"{row['team']}: {row['count']}"
            for row in self.model["team_actions"] if row["action"] == action
        ]
        self.details.setText(
            f"Commande {action} · " + ", ".join(counts)
            + " · actions exécutées, pas intentions écartées par l'IA.")

    def _step_from_curve(self, step):
        if step > 0:
            self.stepSelected.emit(step)

    def _signal_selected(self):
        row = self.signals.currentRow()
        if self.model is None or row < 0:
            return
        step = int(self.signals.item(row, 0).text())
        self.curve.select_step(step)
        self.stepSelected.emit(step)

    def select_step(self, step):
        self.curve.select_step(step)
