"""Standalone Qt Quick Player 5.0 — no Studio/Tk dependencies in this process."""
import argparse
from importlib.resources import files
from pathlib import Path
import sys

from drawtemp.core import Content, GameProject
from drawtemp.player.controller import PlayerController


def build_controller(*, save_dir=None, reference=False):
    if reference:
        from drawtemp.sdk.reference import reference_project
        content, project = reference_project()
    else:
        resource = files("sporebound").joinpath("content")
        content = Content.load(resource.joinpath("jeanne.json"))
        project = GameProject.load(resource.joinpath("jeanne.game.json"), content)
    campaign = project.campaigns[0]["id"]
    directory = Path(save_dir) if save_dir else Path.home() / ".drawtemp" / "player5" / campaign
    return PlayerController(content, project, campaign, directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp 5 — Qt Quick Player (R12)")
    parser.add_argument("--smoke", action="store_true", help="Load the QML root and quit")
    parser.add_argument("--reference", action="store_true",
                        help="Run the deterministic R0 reference campaign")
    parser.add_argument("--save-dir", type=Path, help="Separate persistent save directory")
    args = parser.parse_args(argv)

    try:
        from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError as exc:
        print('Install the Qt 6 extra: python -m pip install ".[qt6]": ' +
              str(exc), file=sys.stderr)
        return 2

    class PlayerBridge(QObject):
        stateChanged = Signal()

        def __init__(self, controller):
            super().__init__()
            self.controller = controller

        @Property("QVariantMap", notify=stateChanged)
        def view(self):
            return self.controller.state()

        def invoke(self, call, *args):
            try:
                call(*args)
            except Exception as exc:
                # A rejected rule/invalid save leaves the canonical Simulation intact.
                self.controller.message = str(exc)
            self.stateChanged.emit()

        @Slot()
        def newGame(self):
            self.invoke(self.controller.new_game)

        @Slot(int)
        def loadGame(self, slot):
            self.invoke(self.controller.load, slot)

        @Slot(int)
        def saveGame(self, slot):
            self.invoke(self.controller.save, slot)

        @Slot()
        def titleScreen(self):
            self.invoke(self.controller.title)

        @Slot(str)
        def choose(self, choice):
            self.invoke(self.controller.choose, choice)

        @Slot(str)
        def startMission(self, mission):
            self.invoke(self.controller.start_mission, mission)

        @Slot(int, int)
        def exploreMove(self, dx, dy):
            self.invoke(self.controller.explore_move, dx, dy)

        @Slot(str)
        def exploreInteract(self, target):
            self.invoke(self.controller.explore_interact, target)

        @Slot(str, str)
        def exploreActor(self, actor, action):
            self.invoke(self.controller.explore_actor, actor, action)

        @Slot(int, int)
        def selectCell(self, x, y):
            self.invoke(self.controller.select_cell, x, y)

        @Slot(str)
        def command(self, kind):
            self.invoke(self.controller.command, kind)

        @Slot(str)
        def preview(self, kind):
            self.invoke(self.controller.preview, kind)

        @Slot()
        def enemyTurn(self):
            self.invoke(self.controller.advance_enemy)

        @Slot()
        def finishBattle(self):
            self.invoke(self.controller.finish_battle)

    app = QGuiApplication([sys.argv[0]])
    bridge = PlayerBridge(build_controller(save_dir=args.save_dir, reference=args.reference))
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("player", bridge)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("Main.qml"))))
    if not engine.rootObjects():
        print("R12 Player QML root failed to load", file=sys.stderr)
        return 1
    if args.smoke:
        QTimer.singleShot(125, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
