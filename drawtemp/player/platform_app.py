"""R32.D opt-in side-view Player diagnostic over canonical GameSession.

This is an interactive engineering preview (Qt Widgets), NOT the certified
R3 renderer or published Player. Physics, campaign and CT remain headless.
Launch: python -m drawtemp.player.platform_app [--smoke] [--save-dir PATH]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description="R32 interactive platform preview")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--save-dir", type=Path,
                        default=Path.home() / ".drawtemp" / "r32-platform-preview")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QColor, QBrush, QPen
        from PySide6.QtWidgets import (
            QApplication, QGraphicsScene, QGraphicsView,
            QLabel, QMainWindow, QVBoxLayout, QWidget,
        )
    except ImportError as exc:
        print("R32 Qt preview requires .[qt6]: " + str(exc), file=sys.stderr)
        return 2

    from drawtemp.player.action_clock import ActionStepClock
    from drawtemp.player.platform_reference import platform_demo_project
    from sporebound.game_session import GameSession

    content, project = platform_demo_project()
    app = QApplication([sys.argv[0]])

    class PlatformWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.content, self.project = content, project
            self.game = GameSession.new(content, project, "main", seed=17)
            self.path = args.save_dir / "game.json"
            self.pressed = set()
            self.edge_jump = False
            self.edge_interact = False
            self.clock = ActionStepClock(hz=60)
            self.last_ns = time.monotonic_ns()
            self.paused = False
            self.setWindowTitle("DrawTemp R32 • plateforme (preview non certifiée)")
            body = QWidget()
            layout = QVBoxLayout(body)
            self.hud = QLabel()
            self.hud.setWordWrap(True)
            layout.addWidget(self.hud)
            self.world = QGraphicsView()
            self.world.setFocusPolicy(Qt.NoFocus)
            self.display = QGraphicsScene()
            self.world.setScene(self.display)
            self.world.setMinimumSize(760, 410)
            layout.addWidget(self.world)
            self.setCentralWidget(body)
            self.setFocusPolicy(Qt.StrongFocus)
            self.timer = QTimer(self)
            self.timer.setInterval(16)
            self.timer.timeout.connect(self.pulse)
            self.timer.start()
            self.draw()

        def reset_clock(self):
            self.clock.reset()
            self.last_ns = time.monotonic_ns()

        def keyPressEvent(self, event):
            if event.isAutoRepeat():
                return
            key = event.key()
            if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_A, Qt.Key_D):
                self.pressed.add(key)
            elif key == Qt.Key_Space:
                self.edge_jump = True
            elif key == Qt.Key_E:
                self.edge_interact = True
            elif key == Qt.Key_P:
                self.paused = not self.paused
                self.reset_clock()
            elif key == Qt.Key_S and event.modifiers() & Qt.ControlModifier:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.game.save(self.path)
                    self.hud.setText("Sauvegarde R32 écrite : " + str(self.path))
                except Exception as exc:
                    self.hud.setText("Sauvegarde refusée : " + str(exc))
            elif key == Qt.Key_L and event.modifiers() & Qt.ControlModifier:
                try:
                    self.game = GameSession.load(self.path, self.content, self.project)
                    self.reset_clock()
                    self.draw()
                except Exception as exc:
                    self.hud.setText("Reprise refusée : " + str(exc))
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                if self.game.mode == "campaign":
                    try:
                        options = self.game.route_platform_state()["available_routes"]
                        if options:
                            self.game.route_platform_travel(options[0])
                    except Exception as exc:
                        self.hud.setText("Portail refusé : " + str(exc))
                self.reset_clock()
                self.draw()
            elif key == Qt.Key_R and self.game.mode == "battle":
                try:
                    self.game.abandon_encounter()
                    self.game.route_transition("retreat")
                except Exception as exc:
                    self.hud.setText("Retour refusé : " + str(exc))
                self.reset_clock()
                self.draw()
            else:
                super().keyPressEvent(event)

        def keyReleaseEvent(self, event):
            if not event.isAutoRepeat():
                self.pressed.discard(event.key())

        def pulse(self):
            now = time.monotonic_ns()
            delta = max(0, now - self.last_ns)
            self.last_ns = now
            if self.paused or self.game.mode != "campaign":
                self.reset_clock()
                return
            n = self.clock.advance(delta)
            if not n:
                return
            left = Qt.Key_Left in self.pressed or Qt.Key_A in self.pressed
            right = Qt.Key_Right in self.pressed or Qt.Key_D in self.pressed
            horizontal = int(right) - int(left)
            try:
                for _ in range(n):
                    self.game.route_platform_step(
                        horizontal, jump=self.edge_jump, interact=self.edge_interact)
                    self.edge_jump = False
                    self.edge_interact = False
            except Exception as exc:
                self.paused = True
                self.hud.setText("Simulation refusée : " + str(exc))
                self.reset_clock()
                return
            self.draw()

        def draw(self):
            self.display.clear()
            if self.game.mode != "campaign":
                self.display.addText("Combat CT authentique actif dans GameSession. R = abandonner et revenir.")
                self.hud.setText("CT actif • R = revenir • Ctrl+S/L = sauvegarder/reprendre")
                return
            state = self.game.route_platform_state()
            authored = self.game._platform_definition()
            factor = .06
            self.display.addRect(0, 0, authored["width"] * factor,
                                 authored["height"] * factor,
                                 pen=QPen(QColor("#4b5870")))
            disabled = set(state["disabled_colliders"])
            for row in authored["colliders"]:
                if row["id"] in disabled:
                    continue
                x, y, w, h = row["rect"]
                if row["id"] in state["movers"]:
                    x = state["movers"][row["id"]]["x"]
                color = "#985acd" if row["trigger"] else (
                    "#24a38d" if row["one_way"] else "#627d9c")
                self.display.addRect(x * factor, y * factor,
                                     w * factor, h * factor,
                                     brush=QBrush(QColor(color)))
            body = state["actor"]
            w, h = authored["hero"]["size"]
            self.display.addRect(body["x"] * factor, body["y"] * factor,
                                 w * factor, h * factor,
                                 brush=QBrush(QColor("#e9c35b")))
            self.world.fitInView(self.display.itemsBoundingRect(), Qt.KeepAspectRatio)
            self.hud.setText(
                "A/D ou ←/→ : marcher • Espace : sauter • E : interrupteur • "
                "Entrée : portail • P : pause • Ctrl+S/L : sauvegarder/reprendre"
                + " | Tick " + str(state["tick"])
                + " | Portes ouvertes : " + str(len(disabled))
                + (" | Portail disponible" if state["available_routes"] else ""))

    window = PlatformWindow()
    window.resize(890, 540)
    if args.smoke:
        QTimer.singleShot(0, app.quit)
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
