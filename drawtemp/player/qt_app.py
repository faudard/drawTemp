"""Standalone Qt Quick Player 5.0 — no Studio/Tk dependencies in this process."""
import argparse
from importlib.resources import files
from pathlib import Path
import sys

from drawtemp.core import Content, GameProject
from drawtemp.player.controller import PlayerController
from drawtemp.render.iso_scene import scene_from_mission, scene_from_exploration
from drawtemp.render.qt_viewport import make_controller


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


def scene_for_player(controller):
    """Use exactly the R3 scene projection, never reassemble tiles in QML.

    Current Battle and exploration views come exclusively from the R1
    Simulation snapshot. Outside gameplay, show the first authored map.
    """
    if controller.session is not None:
        snapshot = controller.session.snapshot()
        if snapshot.battle is not None:
            mission_id = snapshot.battle["mission_id"]
            return scene_from_mission(controller.content.missions[mission_id], snapshot)
        if snapshot.exploration is not None and not snapshot.exploration["completed"]:
            return scene_from_exploration(snapshot.exploration, revision=snapshot.revision)
    return scene_from_mission(next(iter(controller.content.missions.values())))


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp 5 — Qt Quick Player (R12)")
    parser.add_argument("--smoke", action="store_true", help="Load the QML root and quit")
    parser.add_argument("--gui-journey", action="store_true",
                        help="R14 Qt input journey: title, story, battle, F5, menu, reload")
    parser.add_argument("--reference", action="store_true",
                        help="Run the deterministic R0 reference campaign")
    parser.add_argument("--smoke-scene", choices=("title", "battle", "exploration"),
                        default="title", help="Exercise a real game scene during Qt smoke")
    parser.add_argument("--save-dir", type=Path, help="Separate persistent save directory")
    args = parser.parse_args(argv)
    if args.gui_journey and (not args.reference or args.smoke or args.save_dir is None):
        parser.error("--gui-journey requires --reference and an isolated --save-dir")

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

        def __init__(self, controller, renderer):
            super().__init__()
            self.controller = controller
            self.renderer = renderer

        @Property("QVariantMap", notify=stateChanged)
        def view(self):
            return self.controller.state()

        def invoke(self, call, *args):
            try:
                call(*args)
                self.renderer.replace_scene(scene_for_player(self.controller))
                if self.controller.session is not None:
                    self.renderer.selectCell(*self.controller.selected)
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

        @Slot(int)
        def restoreBackup(self, slot):
            self.invoke(self.controller.restore_backup, slot)

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
        def useSkill(self, skill):
            self.invoke(self.controller.use_skill, skill)

        @Slot(str)
        def useItem(self, item):
            self.invoke(self.controller.use_item, item)

        @Slot(str)
        def interactObject(self, object_id):
            self.invoke(self.controller.interact_object, object_id)

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
    controller = build_controller(save_dir=args.save_dir, reference=args.reference)
    if args.smoke and args.smoke_scene == "battle":
        if not args.reference:
            parser.error("--smoke-scene battle requires --reference")
        from drawtemp.sdk.reference import MISSION
        controller.new_game()
        controller.choose("enter")
        controller.start_mission(MISSION)
    elif args.smoke and args.smoke_scene == "exploration":
        if args.reference:
            parser.error("--smoke-scene exploration requires packaged campaign")
        controller.new_game()
        if controller.state()["screen"] != "exploration":
            parser.error("No exploration stage in the current campaign")
    renderer = make_controller(scene_for_player(controller))
    bridge = PlayerBridge(controller, renderer)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"smokeMode": args.smoke})
    engine.rootContext().setContextProperty("renderer", renderer)
    engine.rootContext().setContextProperty("player", bridge)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("Main.qml"))))
    if not engine.rootObjects():
        print("R12 Player QML root failed to load", file=sys.stderr)
        return 1
    if args.gui_journey:
        # Drives production QML and the actual PlayerBridge. This intentionally
        # runs in a separate QGuiApplication process from the Widgets Studio.
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtTest import QTest

        def journey():
            try:
                window = engine.rootObjects()[0]
                window.requestActivate()
                QTest.qWait(60)

                def click(name):
                    item = window.findChild(QObject, name)
                    if item is None or not item.isVisible() or not item.isEnabled():
                        raise AssertionError("Missing visible/enabled QML control: " + name)
                    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
                    QTest.mouseClick(window, Qt.LeftButton,
                                     pos=QPoint(round(point.x()), round(point.y())))
                    QTest.qWait(80)

                def assert_screen(expected):
                    actual = controller.state()["screen"]
                    if actual != expected:
                        raise AssertionError(f"Expected screen {expected}, got {actual}")

                assert_screen("title")
                click("r14NewGame")
                assert_screen("dialogue")
                click("r14Choice-enter")
                assert_screen("campaign")
                from drawtemp.sdk.reference import MISSION
                click("r14Mission-" + MISSION)
                if controller.state()["screen"] not in ("battle", "result"):
                    raise AssertionError("Reference battle did not start")
                before = controller.state()
                QTest.keyClick(window, Qt.Key_F5)
                QTest.qWait(100)
                if 1 not in controller.slots():
                    raise AssertionError("F5 did not save slot 1 through the QML Shortcut")
                click("r14PauseMenu")
                click("r14TitleFromPause")
                assert_screen("title")
                click("r14Continue")
                after = controller.state()
                if after["screen"] != before["screen"] or after["battle"] != before["battle"]:
                    raise AssertionError("GUI save/reload changed the canonical battle state")
                print("R14 Player QML GUI input: title -> dialogue -> campaign -> "
                      "battle -> F5 -> pause/title -> reload OK", flush=True)
                app.exit(0)
            except Exception:
                import traceback
                traceback.print_exc()
                app.exit(1)

        QTimer.singleShot(300, journey)
    elif args.smoke:
        QTimer.singleShot(125, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
