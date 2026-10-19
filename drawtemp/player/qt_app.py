"""Standalone Qt Quick Player 5.0 — no Studio/Tk dependencies in this process."""
import argparse
import hashlib
from importlib.resources import files
from pathlib import Path
import sys

from drawtemp.core import Content, GameProject
from drawtemp.assets.runtime import PresentationAssets
from drawtemp.player.controller import PlayerController
from drawtemp.player.animation_controller import AnimationDirector
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
    project_manifest = None
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
        project_manifest = manifest
    else:
        resource = files("sporebound").joinpath("content")
        content = Content.load(resource.joinpath("jeanne.json"))
        project = GameProject.load(resource.joinpath("jeanne.game.json"), content)
        project_manifest = Path(str(resource.joinpath("jeanne.game.json"))).resolve()
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
    controller = PlayerController(content, project, campaign, directory)
    controller.asset_project_path = project_manifest
    return controller


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


def create_bridge(controller, renderer):
    """Share the real QML bridge with the R14 GUI driver, without a mock runtime."""
    from PySide6.QtCore import QObject, Property, Signal, Slot

    class PlayerBridge(QObject):
        stateChanged = Signal()

        def __init__(self, controller, renderer):
            super().__init__()
            self.controller = controller
            self.renderer = renderer
            self.animator = AnimationDirector()
            self._pending_recovery = None  # ephemeral confirmation, never gameplay
            self._recovery_notice = {}

        @Property("QVariantMap", notify=stateChanged)
        def view(self):
            return self.controller.state()

        @Property("QVariantMap", notify=stateChanged)
        def animationPlan(self):
            return self.animator.snapshot()

        @Property("QVariantMap", notify=stateChanged)
        def recoveryOffer(self):
            if self._pending_recovery is None:
                return {"pending": False}
            slot, _fingerprints = self._pending_recovery
            title = ("Autosauvegarde" if slot == 0 else
                     "Emplacement " + str(slot))
            return {
                "pending": True, "source": slot, "title": title,
                "description": (
                    "Le fichier principal est invalide ou absent. "
                    "Restaurer le secours vérifié peut revenir à une "
                    "progression antérieure. Le fichier corrompu sera "
                    "conservé pour diagnostic. Cette opération est irréversible "
                    "sans une autre copie de sauvegarde."),
            }

        @Property("QVariantMap", notify=stateChanged)
        def recoveryNotice(self):
            return dict(self._recovery_notice)

        def _display_error(self, error):
            code = getattr(error, "code", "operation_failed")
            if not isinstance(code, str):
                code = "operation_failed"
            guidance = {
                "primary_valid": ("Sauvegarde déjà valide",
                                  "La restauration risquerait de remplacer la progression actuelle."),
                "stale_recovery": ("Sauvegarde modifiée",
                                   "Les fichiers ont changé après confirmation. Examinez-les de nouveau."),
                "backup_invalid": ("Secours indisponible",
                                   "Aucune copie de secours vérifiée ne peut être restaurée."),
                "no_valid_save": ("Reprise impossible",
                                  "Choisissez un emplacement valide ou inspectez les copies de secours."),
                "recovery_required": ("Récupération nécessaire",
                                      "Examinez le secours avant de restaurer manuellement."),
                "incompatible_save": ("Sauvegarde incompatible",
                                      "Ce fichier ne correspond pas à la version ou au projet courant."),
                "wrong_campaign": ("Campagne incompatible",
                                   "La sauvegarde ne correspond pas à cette campagne."),
                "unsafe_path": ("Chemin de sauvegarde dangereux",
                                "Inspectez les fichiers sur disque avant toute nouvelle tentative."),
                "evidence_exists": ("Copie endommagée déjà présente",
                                    "Conservez les preuves et inspectez-les manuellement."),
                "io_error": ("Erreur d'accès au disque",
                             "Vérifiez l'espace libre, les permissions et le support."),
            }
            title, advice = guidance.get(
                code, ("Action impossible",
                       "Aucune sauvegarde n'a été restaurée automatiquement. "
                       "Vérifiez l'état des fichiers avant de réessayer."))
            self._recovery_notice = {
                "active": True, "code": code, "title": title,
                "advice": advice, "detail": str(error).replace("\n", " ")[:360],
            }
            self.controller.message = title + " : " + str(error)[:240]

        def _recovery_store(self, source):
            # 0 is a UI-only autosave selector, not a valid manual slot.
            if type(source) is not int:
                raise ValueError("Invalid recovery selection")
            if source == 0:
                return self.controller.saves._store("auto")
            return self.controller._store(source)

        @Slot(int)
        def requestRecovery(self, source):
            from drawtemp.sdk.slots import SlotError
            self._pending_recovery = None
            self._recovery_notice = {}
            try:
                store = self._recovery_store(source)
                status = store.inspect()
                if status.primary == "valid":
                    raise SlotError("primary_valid",
                                    "Le fichier principal est sain : restauration refusée")
                if status.backup != "valid":
                    raise SlotError("backup_invalid",
                                    "Aucune sauvegarde de secours valide")
                self._pending_recovery = (
                    source, store.recovery_fingerprints())
            except Exception as exc:
                self._display_error(exc)
            self.stateChanged.emit()

        @Slot()
        def cancelRecovery(self):
            if self._pending_recovery is not None:
                self._pending_recovery = None
                self.stateChanged.emit()

        @Slot()
        def dismissRecoveryNotice(self):
            if self._recovery_notice:
                self._recovery_notice = {}
                self.stateChanged.emit()

        @Slot()
        def confirmRecovery(self):
            pending = self._pending_recovery
            self._pending_recovery = None
            if pending is None:
                self._display_error(ValueError("Aucune restauration à confirmer"))
                self.stateChanged.emit()
                return
            source, fingerprints = pending
            if source == 0:
                self.invoke(self.controller.restore_autosave_backup,
                            expected_fingerprints=fingerprints)
            else:
                self.invoke(self.controller.restore_backup, source,
                            expected_fingerprints=fingerprints)

        def invoke(self, call, *args, visual=None, **kwargs):
            before = (self.controller.session.snapshot()
                      if self.controller.session is not None else None)
            try:
                call(*args, **kwargs)
                self._recovery_notice = {}
                self._pending_recovery = None
                after = (self.controller.session.snapshot()
                         if self.controller.session is not None else None)
                reset = (call.__name__ in
                         {"new_game", "load", "load_autosave", "continue_game",
                          "restore_backup", "restore_autosave_backup", "title"})
                if reset or self.controller.show_title:
                    self.animator.cancel()
                elif (before is not None and after is not None and
                      after.revision != before.revision):
                    self.animator.update(before, after)
                self.renderer.replace_scene(scene_for_player(self.controller))
                if self.controller.session is not None:
                    # Existing R8 equipment and injuries are already serialized
                    # in Campaign.progress, and validated by Simulation.load().
                    # No parallel visual save-state is introduced here.
                    if call.__name__ in ("new_game", "load", "load_autosave",
                                            "continue_game", "restore_backup",
                                            "restore_autosave_backup"):
                        self.renderer.clear_outfit_preview()
                    snapshot = self.controller.session.snapshot()
                    self.renderer.sync_progress(snapshot.progress,
                                                self.controller.content.equipment)
                    if snapshot.battle is not None:
                        active = snapshot.battle["active"]
                        floors = snapshot.battle.get("unit_levels", {})
                        level = int(floors.get(active, 0)) if active else 0
                        # An upstairs player must see the authored floor rather
                        # than an opaque roof after move, save/load or enemy CT.
                        self.renderer.setConstructionView(level, level > 0)
                    else:
                        self.renderer.setConstructionView(0, False)
                    self.renderer.selectCell(*self.controller.selected)
                if visual is not None:
                    self.renderer.play_actor(*visual)
            except Exception as exc:
                # An invalid rule does not publish a new clip or overwrite saves.
                # The user sees a deliberate action rather than a raw traceback.
                self._display_error(exc)
            self.stateChanged.emit()

        def settings_update(self, method, *args):
            # Presentation-only update: keep the R3 camera, selection and scene.
            try:
                method(*args)
            except Exception as exc:
                self.controller.message = str(exc)
            self.stateChanged.emit()

        @Slot(str)
        def selectProfile(self, profile):
            self.settings_update(self.controller.set_profile, profile)

        @Slot(str, str)
        def rebind(self, action, key):
            self.settings_update(self.controller.set_binding, action, key)

        @Slot()
        def resetBindings(self):
            self.settings_update(self.controller.reset_bindings)

        @Slot(str, bool)
        def setDisplayBool(self, option, value):
            self.settings_update(self.controller.set_display, option, value)

        @Slot(float)
        def setTextScale(self, value):
            self.settings_update(self.controller.set_display, "text_scale", value)

        @Slot()
        def newGame(self):
            self.invoke(self.controller.new_game)

        @Slot()
        def continueGame(self):
            self.invoke(self.controller.continue_game)

        @Slot()
        def loadAutosave(self):
            self.invoke(self.controller.load_autosave)

        @Slot()
        def restoreAutosaveBackup(self):
            self.invoke(self.controller.restore_autosave_backup)

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
            self.invoke(self.controller.explore_move, dx, dy,
                        visual=("jeanne", "walk"))

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
            actor_id = ""
            if self.controller.session is not None:
                battle = self.controller.session.snapshot().battle
                if battle is not None:
                    actor_id = battle.get("active", "")
            visual = ((actor_id, "walk" if kind == "move" else "attack")
                      if actor_id and kind in ("move", "attack") else None)
            self.invoke(self.controller.command, kind, visual=visual)

        @Slot(str, str)
        def equipHero(self, actor_id, item_id):
            self.invoke(self.controller.equip_hero, actor_id, item_id)

        @Slot(str, str)
        def unequipHero(self, actor_id, slot):
            self.invoke(self.controller.unequip_hero, actor_id, slot)

        @Slot(str, str)
        def previewOutfit(self, actor_id, variant):
            """Presentation-only preview; equipment and saves remain canonical."""
            try:
                self.renderer.set_outfit(actor_id, variant)
            except ValueError as exc:
                self.controller.message = str(exc)
            self.stateChanged.emit()

        @Slot(str)
        def useSkill(self, skill):
            self.invoke(self.controller.use_skill, skill)

        @Slot(str)
        def useItem(self, item):
            self.invoke(self.controller.use_item, item)

        @Slot(str)
        def interactObject(self, object_id):
            self.invoke(self.controller.interact_object, object_id)

        @Slot(int, int, int)
        def levelMove(self, level, x, y):
            self.invoke(self.controller.level_move, level, (x, y))

        @Slot(int, int, int)
        def levelAttack(self, level, x, y):
            self.invoke(self.controller.level_attack, level, (x, y))

        @Slot(str)
        def inspectSkill(self, skill):
            self.invoke(self.controller.inspect_skill, skill)

        @Slot(str)
        def toggleDoor(self, object_id):
            self.invoke(self.controller.toggle_door, object_id)

        @Slot(str)
        def preview(self, kind):
            self.invoke(self.controller.preview, kind)

        @Slot()
        def enemyTurn(self):
            self.invoke(self.controller.advance_enemy)

        @Slot()
        def finishBattle(self):
            self.invoke(self.controller.finish_battle)


    return PlayerBridge(controller, renderer)

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
    parser.add_argument("--character-pack", type=Path, help="Published R7 atlas export directory")
    parser.add_argument("--character-variant", help="Initial authored outfit ID")
    parser.add_argument("--gui-journey", action="store_true",
                        help="R14 Qt input journey: title, story, battle, F5, menu, reload")
    args = parser.parse_args(argv)
    if args.gui_journey and (not args.reference or args.smoke or args.save_dir is None):
        parser.error("--gui-journey requires --reference and an isolated --save-dir")

    # R15: a frozen Player must never run unverified or substitute game data.
    if getattr(sys, "frozen", False):
        from drawtemp.export.r15 import verify_bundle
        bundle = Path(sys.executable).resolve().parent.parent
        try:
            if args.reference or args.content or args.project:
                raise ValueError("Native Player only accepts its verified game bundle")
            manifest = verify_bundle(bundle)
            args.content = bundle / manifest["content"]
        except (OSError, ValueError) as exc:
            print("Standalone game integrity failure: " + str(exc), file=sys.stderr)
            return 1

    try:
        from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError as exc:
        print('Install the Qt 6 extra: python -m pip install ".[qt6]": ' +
              str(exc), file=sys.stderr)
        return 2


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
    presentation = (PresentationAssets.for_project(
        controller.project, controller.asset_project_path)
        if controller.asset_project_path is not None else None)
    renderer = make_controller(scene_for_player(controller), assets=presentation,
                               character_pack=args.character_pack,
                               character_variant=args.character_variant)
    if controller.session is not None:
        renderer.sync_progress(controller.session.snapshot().progress,
                               controller.content.equipment)
    bridge = create_bridge(controller, renderer)
    engine = QQmlApplicationEngine()
    renderer.attach_engine(engine)
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
