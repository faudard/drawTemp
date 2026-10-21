"""R76.C: read-only viewer for offline measured R15 bundle benchmarks.

Never runs expensive subprocess samples on the Qt GUI thread, nor promotes a
measured Python load time to native Player startup or GPU performance.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from drawtemp.quality.r76_bench import (
    BenchmarkError, _safe_report, compare, validate_report,
)


class R76BenchmarkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("r76-benchmark-dialog")
        self.setWindowTitle("R76.C — Performance & Bundle Evidence (NO-GO)")
        self.resize(1020, 620)
        self.baseline = None
        self.candidate = None
        layout = QVBoxLayout(self)
        heading = QLabel(
            "Rapports mesurés hors ligne : Python chargement de projet, "
            "empreinte réelle du bundle R15 et mémoire process si disponible. "
            "AUCUNE mesure native Player / FPS / GPU ni certification release.")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        controls = QHBoxLayout()
        before = QPushButton("Charger référence…")
        before.setObjectName("r76-load-baseline")
        before.clicked.connect(lambda: self.choose("baseline"))
        controls.addWidget(before)
        after = QPushButton("Charger candidat…")
        after.setObjectName("r76-load-candidate")
        after.clicked.connect(lambda: self.choose("candidate"))
        controls.addWidget(after)
        self.comparison = QPushButton("Comparer les profils")
        self.comparison.setObjectName("r76-compare")
        self.comparison.clicked.connect(self.compare_loaded)
        controls.addWidget(self.comparison)
        layout.addLayout(controls)
        self.summary = QLabel("Chargez un ou deux rapports R76.C.")
        self.summary.setObjectName("r76-bench-summary")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("r76-bench-metrics")
        self.table.setAccessibleName("Mesures benchmark et coût fichier")
        self.table.setHorizontalHeaderLabels(
            ["Mesure réelle", "Référence", "Candidat"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        footer = QLabel(
            "La comparaison est informative. Un p99 sur moins de 100 "
            "observations reste exploratoire ; tests hardware tri-OS, "
            "R14 et vérification du gameplay nécessaires.")
        footer.setWordWrap(True)
        layout.addWidget(footer)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.refresh()

    def choose(self, position):
        name, _ = QFileDialog.getOpenFileName(
            self, "Choisir un rapport R76.C", "", "JSON (*.json)")
        if name:
            try:
                self.load_report(position, Path(name))
            except (BenchmarkError, OSError, ValueError) as exc:
                QMessageBox.warning(self, "Rapport refusé", str(exc))

    def load_report(self, position, path):
        if position not in ("baseline", "candidate"):
            raise BenchmarkError("Expected baseline or candidate")
        validated = validate_report(_safe_report(path))
        setattr(self, position, validated)
        self.refresh()

    @staticmethod
    def _fields(report):
        if report is None:
            return {}
        bench = report["measurements"]
        size = report["bundle"]
        t = bench["project_load_process_ms"]
        p = bench["python_traced_peak_bytes"]
        rss = bench["process_peak_rss_bytes"]
        return {
            "Dossier de corpus": report["corpus"],
            "Révision Git": report["revision"][:12],
            "Octets bundle (réels)": str(size["bundle_bytes"]),
            "Octets Player (réels)": str(size["player_bytes"]),
            "Octets game (réels)": str(size["game_bytes"]),
            "Fichiers physiques": str(size["file_count"]),
            "Python projet-load p50 ms": str(t["p50"]),
            "Python projet-load p95 ms": str(t["p95"]),
            "Python projet-load p99 ms": str(t["p99"]),
            "Python projet-load variance ms²": str(t["variance"]),
            "Python heap tracé p95 bytes": str(p["p95"]),
            "Processus RSS pic p95 bytes": str(rss["p95"]) if rss else "non mesuré",
            "Exécutions observées": str(report["workload"]["samples"]),
            "P99 exploratoire": "oui" if t["tail_exploratory"] else "non",
            "GPU physique": "NON MESURÉ",
            "Player natif startup": "NON MESURÉ",
        }

    def refresh(self):
        baseline = self._fields(self.baseline)
        candidate = self._fields(self.candidate)
        names = list(dict.fromkeys((*baseline, *candidate)))
        self.table.setRowCount(len(names))
        for row, name in enumerate(names):
            for col, value in enumerate((name, baseline.get(name, "—"),
                                         candidate.get(name, "—"))):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.comparison.setEnabled(
            self.baseline is not None and self.candidate is not None)
        if self.baseline and self.candidate:
            self.summary.setText(
                "Deux rapports chargés ; lancer la comparaison. "
                "Une différence de matériel, corpus, révision ou Content la bloquera.")
        else:
            self.summary.setText(
                "Lecture seule : aucun benchmark exécuté dans le processus Qt.")

    def compare_loaded(self):
        if self.baseline is None or self.candidate is None:
            return False
        try:
            result = compare(self.baseline, self.candidate)
        except (BenchmarkError, ValueError, KeyError) as exc:
            self.summary.setText("Comparaison refusée : " + str(exc))
            return False
        verdict = "Régression de latence p95" if result["latency_regressed"] else (
            "Pas de régression p95 au seuil indicatif")
        self.summary.setText(
            verdict + " · coût bundle Δ " + str(result["bundle_delta_bytes"]) +
            " octets · p95 Δ " + str(result["p95_delta_ms"]) +
            " ms · statut INFORMATIF / NO-GO release.")
        return True
