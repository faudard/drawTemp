"""R30.F read-only Qt CPU profiling dashboard.

Loads validated offline CPU profiles; intentionally never advertises GPU FPS,
real frame times or production certification. Measurement is performed by the
separate headless CLI so large runs cannot block the Qt editor event loop.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.quality.r30_scale import (
    compare_profiles, _load_report,
)


class LatencyBars(QWidget):
    """Measured p95/p99 CPU bars; no fake GPU frame chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.setAccessibleName("Graphique des latences CPU p95 et p99 mesurées")
        self.setMinimumHeight(310)

    def set_rows(self, rows):
        self.rows = list(rows)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.fillRect(self.rect(), self.palette().base())
            painter.setPen(self.palette().text().color())
            if not self.rows:
                painter.drawText(self.rect(), Qt.AlignCenter,
                                 "Charger un profil CPU pour afficher le graphique")
                return
            left, right = 175, 85
            space = max(20, self.width() - left - right)
            highest = max(row["p99_ms"] for row in self.rows) or 1.0
            height = max(28, (self.height() - 36) // len(self.rows))
            for index, row in enumerate(self.rows):
                y = 12 + index * height
                painter.setPen(self.palette().text().color())
                painter.drawText(QRect(8, y, left - 12, height - 6),
                                 Qt.AlignVCenter | Qt.AlignLeft,
                                 row["operation"].replace("_", " "))
                for offset, field, color in (
                    (0, "p95_ms", QColor("#2469b8")),
                    (13, "p99_ms", QColor("#db9243")),
                ):
                    value = row[field]
                    width = max(1, int(space * value / highest))
                    painter.fillRect(left, y + offset, width, 10, color)
                painter.setPen(self.palette().text().color())
                painter.drawText(
                    QRect(left + space + 4, y, right - 6, height - 6),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    f"{row['p95_ms']:.2f}ms")
        finally:
            painter.end()


class R30ScaleDashboard(QDialog):
    """Show CPU headless evidence; no implicit file writes or live session edits."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("r30f-scale-dashboard")
        self.setWindowTitle("DrawTemp R30.F — Performance CPU & budgets d'assets")
        self.resize(1070, 690)
        self.report = None
        root = QVBoxLayout(self)
        self.banner = QLabel(
            "Graphiques de latence CPU p95/p99 mesurée, mémoire Python et "
            "budget d'assets. Ceci n'est PAS un profil GPU ni une certification Player.")
        self.banner.setWordWrap(True)
        root.addWidget(self.banner)
        actions = QHBoxLayout()
        open_button = QPushButton("Ouvrir un rapport R30.F…")
        open_button.clicked.connect(self._choose_report)
        actions.addWidget(open_button)
        self.compare_button = QPushButton("Comparer avec une baseline locale…")
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(self._choose_baseline)
        actions.addWidget(self.compare_button)
        root.addLayout(actions)
        self.chart = LatencyBars(self)
        root.addWidget(self.chart)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ("Opération", "p50 ms", "p95 ms", "p99 ms", "Max ms", "Pic mémoire Python (octets)"))
        self.table.setAccessibleName("Résultats chiffrés CPU et mémoire")
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table)
        self.assets_label = QLabel("Budget des assets : rapport non chargé.")
        self.assets_label.setWordWrap(True)
        root.addWidget(self.assets_label)
        self.status = QLabel(
            "Générer un JSON en ligne de commande : "
            "python -m drawtemp.quality.r30_scale --output rapport.json")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("État du rapport et de la comparaison CPU")
        root.addWidget(self.status)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        root.addWidget(close)

    def _choose_report(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un profil CPU R30.F", "", "Rapport JSON (*.json)")
        if path:
            self.open_report(path)

    def open_report(self, path):
        try:
            report = _load_report(Path(path))
        except (OSError, ValueError, TypeError) as exc:
            self.status.setText("Rapport invalide : " + str(exc))
            QMessageBox.warning(self, "Rapport rejeté", str(exc))
            return False
        self.report = report
        self.chart.set_rows(report["metrics"])
        self.table.setRowCount(len(report["metrics"]))
        for i, row in enumerate(report["metrics"]):
            for col, value in enumerate((
                row["operation"], row["p50_ms"], row["p95_ms"],
                row["p99_ms"], row["max_ms"],
                row["python_traced_peak_bytes"],
            )):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(i, col, cell)
        budget = report["asset_budget"]
        self.assets_label.setText(
            f"Assets déclarés : {budget['registry_entries']} | "
            f"Fichiers contrôlés : {budget['disk_files_checked']} | "
            f"Volume déclaré/stat : {budget['bytes']:,} octets | "
            f"Volumes disque vérifiés : {budget['bytes_verified']}")
        workload = report["workload"]
        self.status.setText(
            f"CPU {report['environment']['os']} / {report['environment']['python']} "
            f"— {workload['samples']} mesures/opération, "
            f"{workload['warmups']} préchauffages. "
            "p99 exploratoire si moins de 100 mesures. "
            "Statut : informatif, pas de GPU certifié.")
        self.compare_button.setEnabled(True)
        return True

    def _choose_baseline(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un profil CPU baseline", "", "Rapport JSON (*.json)")
        if path:
            self.compare_baseline(path)

    def compare_baseline(self, path):
        if self.report is None:
            return None
        try:
            result = compare_profiles(_load_report(Path(path)), self.report)
        except (OSError, ValueError, TypeError) as exc:
            self.status.setText("Comparaison refusée : " + str(exc))
            QMessageBox.warning(self, "Baseline incompatible", str(exc))
            return None
        changed = [row["operation"] for row in result["changes"] if row["regressed"]]
        self.status.setText(
            ("RÉGRESSION p95 : " + ", ".join(changed)
             if changed else "Pas de dépassement du budget p95 pour ce profil")
            + " — Gate optionnel CPU uniquement, aucun statut de certification.")
        return result
