"""Pure Qt Widgets visualizations for R13.8 paired Battle Lab metrics.

No QtCharts, QML, matplotlib or backend AI dependency. The SDK supplies the
validated metric model; this module ONLY paints those observations.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPoint, Qt, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

BLUE = QColor("#4187bf")
ORANGE = QColor("#dd8149")
GRID = QColor("#d7dfe5")
INK = QColor("#263646")
MUTED = QColor("#62758a")
LINE_HEIGHT = 50


class BarCanvas(QWidget):
    """Accessible text-labelled bar chart; row click selects an observed seed."""

    seedSelected = Signal(int)

    def __init__(self, *, per_seed=False, parent=None):
        super().__init__(parent)
        self.per_seed = per_seed
        self.report = None
        self.metric = "ticks"
        self._selected = None
        self.setMinimumWidth(500)
        self.setMinimumHeight(250)
        self.setMouseTracking(True)

    def set_report(self, report, metric=None):
        self.report = report
        if metric is not None:
            self.metric = metric
        count = (len(report["seed_order"]) if self.per_seed
                 else len(report["metrics"])) if report else 0
        self.setMinimumHeight(max(230, 72 + count * LINE_HEIGHT))
        self.update()

    def select_seed(self, seed):
        self._selected = seed
        self.update()

    def _rows(self):
        if self.report is None:
            return []
        if self.per_seed:
            return [
                (str(seed), seed, [
                    s["samples"][i][self.metric]
                    for s in self.report["series"]
                ]) for i, seed in enumerate(self.report["seed_order"])
            ]
        return [
            (metric["label"], None, [
                s["aggregate"][metric["id"]]
                for s in self.report["series"]
            ]) for metric in self.report["metrics"]
        ]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), self.palette().base())
        if self.report is None:
            p.setPen(MUTED)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Lancer une simulation pour afficher les mesures.")
            p.end()
            return
        width = self.width()
        left = 92 if self.per_seed else 190
        right = 95
        usable = max(40, width - left - right)
        font = QFont(self.font())
        font.setPointSize(10)
        p.setFont(font)
        p.setPen(INK)
        p.drawText(14, 24, "PAR SEED" if self.per_seed else "INDICATEURS AGRÉGÉS")
        for i, source in enumerate(self.report["series"]):
            colour = BLUE if i == 0 else ORANGE
            x = left + i * 175
            p.fillRect(QRectF(x, 36, 12, 10), colour)
            p.setPen(MUTED)
            p.drawText(x + 17, 46, source["label"])
        rows = self._rows()
        for index, (label, seed, values) in enumerate(rows):
            y = 67 + index * LINE_HEIGHT
            if seed is not None and seed == self._selected:
                p.fillRect(QRectF(0, y - 4, width, LINE_HEIGHT - 2),
                           QColor("#dfebf7"))
            p.setPen(INK)
            p.drawText(QRectF(8, y, left - 18, 34),
                       Qt.AlignmentFlag.AlignVCenter, label)
            max_value = max([*values, 0.000001])
            p.setPen(QPen(GRID, 1))
            p.drawLine(left, y + 1, left, y + 35)
            for si, value in enumerate(values):
                colour = BLUE if si == 0 else ORANGE
                bar_y = y + 3 + si * 17
                bar_width = max(1, round(value / max_value * usable))
                p.fillRect(QRectF(left, bar_y, bar_width, 12), colour)
                p.setPen(INK)
                shown = (f"{value:.2f}" if isinstance(value, float)
                         and not value.is_integer() else str(int(value)))
                p.drawText(QRectF(left + usable + 7, bar_y - 2, right - 13, 18),
                           Qt.AlignmentFlag.AlignVCenter, shown)
            p.setPen(QPen(GRID, 1))
            p.drawLine(8, y + 44, width - 8, y + 44)
        p.end()

    def _row_index(self, y):
        row = int((y - 67) // LINE_HEIGHT)
        return row if y >= 67 and 0 <= row < len(self._rows()) else None

    def mouseMoveEvent(self, event):
        if not self.per_seed or self.report is None:
            return super().mouseMoveEvent(event)
        index = self._row_index(event.position().y())
        if index is None:
            self.setToolTip("")
            return
        details = [f"Seed {self.report['seed_order'][index]}"]
        for source in self.report["series"]:
            sample = source["samples"][index]
            details.append(
                f"{source['label']} · {sample['result']} · "
                f"{sample['ticks']} ticks CT · {sample['commands']} commandes · "
                f"{sample['activations_ct']} activations")
        self.setToolTip("\n".join(details))

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.per_seed and self.report is not None):
            index = self._row_index(event.position().y())
            if index is not None:
                seed = self.report["seed_order"][index]
                self.select_seed(seed)
                self.seedSelected.emit(seed)
                event.accept()
                return
        return super().mousePressEvent(event)


class R13ComparisonCharts(QWidget):
    """Two synchronized visuals: aggregate bars and seed-paired bars."""

    seedSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report = None
        layout = QVBoxLayout(self)
        self.notice = QLabel(
            "Aucune simulation à comparer. Les durées sont exprimées "
            "en ticks CT simulés, pas en minutes réelles.")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.aggregate_plot = BarCanvas()
        layout.addWidget(self.aggregate_plot)
        selectors = QHBoxLayout()
        layout.addLayout(selectors)
        selectors.addWidget(QLabel("Comparaison par seed"))
        self.metric_selector = QComboBox()
        self.metric_selector.addItem("Ticks CT", "ticks")
        self.metric_selector.addItem("Commandes", "commands")
        self.metric_selector.addItem("Activations CT", "activations_ct")
        self.metric_selector.currentIndexChanged.connect(self._change_metric)
        selectors.addWidget(self.metric_selector)
        selectors.addStretch()
        self.seed_scroll = QScrollArea()
        self.seed_scroll.setWidgetResizable(True)
        self.seed_plot = BarCanvas(per_seed=True)
        self.seed_plot.seedSelected.connect(self.seedSelected.emit)
        self.seed_scroll.setWidget(self.seed_plot)
        self.seed_scroll.setMinimumHeight(200)
        layout.addWidget(self.seed_scroll, 1)

    def clear(self):
        self.report = None
        self.aggregate_plot.set_report(None)
        self.seed_plot.set_report(None)
        self.notice.setText(
            "Aucune simulation à comparer. Les durées sont exprimées "
            "en ticks CT simulés, pas en minutes réelles.")

    def set_report(self, report, *, warning=""):
        if report["kind"] != "r13_visual_metrics":
            raise ValueError("R13 chart payload expected")
        self.report = report
        self.aggregate_plot.set_report(report)
        self.seed_plot.set_report(report, self.metric_selector.currentData())
        self.seed_plot.select_seed(None)
        if report["comparison"] is None:
            status = "Simulation unique · aucune référence appariée chargée."
        else:
            gate = report["comparison"]
            status = ("Comparaison validée" if gate["passed"] else
                      "Écarts / contrôle requis")
            if gate["issues"]:
                status += " — " + "; ".join(gate["issues"])
            if gate["human_signoff_required"]:
                status += " · revue humaine nécessaire"
        outcomes = " · ".join(
            "{}: {}/{}".format(series["label"],
                               series["outcomes"]["victory"], report["runs"])
            for series in report["series"])
        self.notice.setText(
            f"{report['mission']} · {report['runs']} seeds · {status}\n"
            f"Victoires : {outcomes}\n{report['units_note']}"
            + ("\n" + warning if warning else ""))

    def _change_metric(self, _index):
        self.seed_plot.set_report(
            self.report, self.metric_selector.currentData())

    def select_seed(self, seed):
        self.seed_plot.select_seed(seed)

    def export_png(self, destination):
        """Write both complete plots to a lossless PNG, never overwrite a file.

        This export paints the full seed chart, including rows outside the
        on-screen scroll viewport. It is presentation only; raw JSON metrics
        remain the reproducible scientific evidence.
        """
        if self.report is None:
            raise ValueError("Simuler avant d'exporter les graphiques.")
        target = Path(destination)
        if target.suffix.lower() != ".png":
            raise ValueError("Le format d'export pris en charge est PNG.")
        if target.exists():
            raise FileExistsError("Le fichier existe déjà : " + str(target))
        if not target.parent.is_dir():
            raise FileNotFoundError("Dossier d'export introuvable.")

        width = max(650, self.aggregate_plot.width(), self.seed_plot.width())
        heading = 102
        spacing = 18
        height = (heading + self.aggregate_plot.height() + spacing
                  + self.seed_plot.height() + spacing)
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        if image.isNull():
            raise OSError("Impossible de créer l'image d'export.")
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        try:
            painter.setPen(INK)
            font = QFont(self.font())
            font.setBold(True)
            font.setPointSize(13)
            painter.setFont(font)
            painter.drawText(12, 22, "DrawTemp — Visual Battle Lab R13.8")
            font.setBold(False)
            font.setPointSize(9)
            painter.setFont(font)
            painter.setPen(MUTED)
            painter.drawText(QRectF(12, 29, width - 24, 70),
                             Qt.AlignmentFlag.AlignTop
                             | Qt.TextFlag.TextWordWrap, self.notice.text())
            self.aggregate_plot.render(painter, QPoint(0, heading))
            self.seed_plot.render(
                painter, QPoint(0, heading + self.aggregate_plot.height() + spacing))
        finally:
            painter.end()
        # Exclusive creation matters: a chart export must never replace
        # authored Content, a baseline or any pre-existing user file.
        buffer = QByteArray()
        device = QBuffer(buffer)
        if not device.open(QIODevice.OpenModeFlag.WriteOnly):
            raise OSError("Impossible d'ouvrir le tampon PNG.")
        try:
            if not image.save(device, "PNG"):
                raise OSError("Encodage PNG impossible.")
        finally:
            device.close()
        try:
            with target.open("xb") as destination_file:
                destination_file.write(bytes(buffer))
        except Exception:
            # Exclusive open fails without touching pre-existing files.
            # Other errors propagate so the user sees that export failed.
            raise
        return target
