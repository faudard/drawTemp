"""Standalone Qt Quick Player 5.0 — no Studio/Tk dependencies in this process."""
import argparse
import hashlib
from importlib.resources import files
from pathlib import Path
import sys

from drawtemp.core import Content, GameProject
from drawtemp.player.controller import PlayerController
from drawtemp.render.iso_scene import scene_from_mission, scene_from_exploration
from drawtemp.render.qt_viewport import make_controller


def build_controller(*, save_dir=None, reference=False, content_path=None,
                     project_path=None, campaign_id=None):
    """Load the packaged demo, R0 reference, or a validated authored pair.

    A custom project owns a distinct default save directory so two unrelated
    creator projects cannot accidentally share the same checkpoint files.
    """
    if reference and (content_path is not None or project_path is not None):
        raise ValueError("--reference cannot be combined with authored content")
    if project_path is not None and content_path is None:
        raise ValueError("--project requires --content")
    if reference:
        from drawtemp.sdk.reference import reference_project
        content, project = reference_project()
    elif content_path is not None:
        source = Path(content_path).expanduser().resolve()
        manifest = (Path(project_path).expanduser().resolve()
                    if project_path is not None
                    else source.with_suffix(".game.json"))
        # Reuse the validated Content/Project pair and its authored rules.
        import json
        from sporebound.tactical_rpg3 import authored_rules_for_document
        data = json.loads(source.read_text(encoding="utf-8"))
        content = Content.from_dict(data, rules=authored_rules_for_document(data))
        project = GameProject.load(manifest, content)
    else:
        resource = files("sporebound").joinpath("content")
        content = Content.load(resource.joinpath("jeanne.json"))
        project = GameProject.load(resource.joinpath("jeanne.game.json"), content)
    campaign = campaign_id or project.campaigns[0]["id"]
    if project.campaign(campaign) is None:
        raise ValueError("Unknown campaign: " + str(campaign))
    if save_dir is not None:
        directory = Path(save_dir)
    elif content_path is not None:
        identity = hashlib.sha256(
            (str(source) + "\\0" + str(manifest)).encode("utf-8")
        ).hexdigest()[:16]
        directory = (Path.home() / ".drawtemp" / "player5" /
                     "authored" / identity / campaign)
    else:
        directory = Path.home() / ".drawtemp" / "player5" / campaign
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
    parser.add_argument("--reference", action="store_true",
                        help="Run the deterministic R0 reference campaign")
    parser.add_argument("--smoke-scene", choices=("title", "battle", "exploration"),
                        default="title", help="Exercise a real game scene during Qt smoke")
    parser.add_argument("--save-dir", type=Path, help="Separate persistent save directory")
    parser.add_argument("--content", type=Path, help="Custom canonical Content JSON")
    parser.add_argument("--project", type=Path, help="Paired GameProject JSON (defaults to <content>.game.json)")
    parser.add_argument("--campaign", help="Campaign ID from the selected project")
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
    try:
        controller = build_controller(
            save_dir=args.save_dir, reference=args.reference,
            content_path=args.content, project_path=args.project,
            campaign_id=args.campaign)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.smoke and args.smoke_scene == "battle":
        if not args.reference:
            parser.error("--smoke-scene battle requires --reference")
        from drawtemp.sdk.reference import MISSION
        controller.new_game()
        controller.choose("enter")
        controller.start_mission(MISSION)
    elif args.smoke and args.smoke_scene == "exploration":
        if args.reference:
            parser.error("--smoke-scene exploration requires a campaign with exploration")
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
    if args.smoke:
        QTimer.singleShot(125, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
