"""One Qt Quick scenegraph renderer for Studio and Player (R3 initial slice).

For GPU composition, clients embed the returned QQuickView as a native window
or display it directly. No tactical rules are evaluated in QML.
"""
import argparse
from pathlib import Path
import sys

from .iso_scene import Camera, IsoProjection, pick, render_items, scene_from_mission


def default_atlas_url():
    """One atlas binding for all clients; missing optional art is harmless."""
    from importlib.resources import files
    atlas = files("sporebound").joinpath("content/art/iso/terrain.png")
    return Path(str(atlas)).resolve().as_uri() if atlas.is_file() else ""


def make_controller(scene, atlas_url=None, *, character_pack=None,
                    character_variant=None):
    """One renderer for Studio/Player; character art is optional and cosmetic."""
    from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QElapsedTimer
    from drawtemp.assets.character_runtime import CharacterPack
    from drawtemp.assets.characters import ACTIONS

    class RendererController(QObject):
        sceneChanged = Signal()
        cameraChanged = Signal()
        picked = Signal("QVariantMap")

        def __init__(self):
            super().__init__()
            self.scene = scene
            self.camera = Camera()
            self.projection = IsoProjection()
            self.selection = None
            self._items = []
            self._atlas = default_atlas_url() if atlas_url is None else atlas_url
            self._character = (
                character_pack if isinstance(character_pack, CharacterPack)
                else CharacterPack(character_pack) if character_pack is not None
                else None)
            self._variant = character_variant
            if (self._character is not None and character_variant is not None
                    and character_variant not in self._character.variants):
                raise ValueError("Unknown character outfit: " + character_variant)
            self._outfits = {}
            self._action_begins = {}
            self._clock = QElapsedTimer()
            self._clock.start()
            self._sprite_timer = QTimer(self)
            self._sprite_timer.setInterval(80)
            self._sprite_timer.timeout.connect(self.advance_frames)
            self.center_scene()
            if self._character is not None:
                self._sprite_timer.start()

        def center_scene(self):
            x, y = self.projection.project((self.scene["width"] - 1) / 2,
                                           (self.scene["height"] - 1) / 2)
            self.camera.center(x, y)
            self.refresh()

        def decorate_frames(self, rows):
            """Add sprite presentation to visible actor rows without Core mutation."""
            if self._character is None:
                return
            now = self._clock.elapsed()
            for row in rows:
                if (row["kind"] != "actor" or
                        row["id"] != self._character.character_id):
                    continue
                for field in ("spriteReady", "spriteUrl", "spriteRegion", "spritePivot"):
                    row.pop(field, None)
                actor_id = row["id"]
                outfit = self._outfits.get(actor_id, self._variant)
                if outfit is None:
                    outfit = self._character.variants[0]
                direction = row.get("direction", "south")
                action, beginning = self._action_begins.get(actor_id, ("idle", 0))
                elapsed = now - beginning if action != "idle" else now
                duration = self._character.duration(outfit, action, direction)
                if action != "idle" and (not duration or elapsed >= duration):
                    self._action_begins.pop(actor_id, None)
                    action, elapsed = "idle", now
                art = self._character.preview_actor(
                    actor_id, variant=outfit, action=action,
                    direction=direction, elapsed_ms=elapsed)
                if art is not None:
                    row.update(art)

        def refresh(self):
            self._items = render_items(self.scene, self.camera, self.projection, self.selection)
            self.decorate_frames(self._items)
            self.sceneChanged.emit()
            self.cameraChanged.emit()

        def advance_frames(self):
            """Tick just the actor frames; do not recompute/cull terrain at 12 Hz."""
            if self._character is None:
                return
            rows = [dict(row) for row in self._items]
            self.decorate_frames(rows)
            if rows != self._items:
                self._items = rows
                self.sceneChanged.emit()

        def set_outfit(self, actor_id, variant):
            """Change a visual preview, never an equipment rule or save field."""
            if (self._character is None or actor_id != self._character.character_id
                    or variant not in self._character.variants):
                raise ValueError("Unknown character/outfit")
            self._outfits[actor_id] = variant
            self._action_begins.pop(actor_id, None)
            self.refresh()

        def play_actor(self, actor_id, action):
            """Play one authored clip cycle, then restore idle presentation."""
            if action not in ACTIONS:
                raise ValueError("Unknown character action")
            if (self._character is None or actor_id != self._character.character_id):
                return False
            self._action_begins[actor_id] = (action, self._clock.elapsed())
            self.refresh()
            return True

        @Property("QVariantList", notify=sceneChanged)
        def items(self):
            return self._items

        @Property("QVariantMap", notify=cameraChanged)
        def cameraState(self):
            return {"zoom": self.camera.zoom, "panX": self.camera.pan_x,
                    "panY": self.camera.pan_y}

        @Property(str, constant=True)
        def atlasUrl(self):
            return self._atlas

        @Property("QVariantList", constant=True)
        def characterOutfits(self):
            return list(self._character.variants) if self._character else []

        @Property(str, constant=True)
        def characterId(self):
            return self._character.character_id if self._character else ""

        @Slot(float, float)
        def resizeViewport(self, width, height):
            if width > 0 and height > 0:
                self.camera.width, self.camera.height = width, height
                self.refresh()

        @Slot(float, float)
        def panBy(self, dx, dy):
            self.camera.pan_x += dx
            self.camera.pan_y += dy
            self.refresh()

        @Slot(float, float, float)
        def zoomAt(self, angle, x, y):
            self.camera.zoom_at(1.15 if angle > 0 else 1 / 1.15, x, y)
            self.refresh()

        @Slot(float, float, result="QVariantMap")
        def cellAt(self, x, y):
            """Return a terrain cell even when an actor/object obscures it.

            R5 paint gestures and R12 tactical selection use this same R3
            altitude-aware picking contract. Empty maps return an empty map.
            """
            wx, wy = self.camera.world(x, y)
            elevations = {(tile["x"], tile["y"]): tile["height"]
                          for tile in self.scene["tiles"] if tile["height"]}
            cell = self.projection.pick(wx, wy, self.scene["width"],
                                        self.scene["height"], elevations)
            return {"x": cell[0], "y": cell[1]} if cell is not None else {}

        @Slot(float, float)
        def pickAt(self, x, y):
            hit = pick(self.scene, self.camera, x, y, self.projection)
            self.selection = tuple(hit["cell"]) if hit and hit["kind"] == "tile" else None
            self.refresh()
            if hit is not None:
                self.picked.emit(hit)

        @Slot(int, int)
        def selectCell(self, x, y):
            self.selection = (x, y) if (
                0 <= x < self.scene["width"] and
                0 <= y < self.scene["height"]) else None
            self.refresh()

        def replace_scene(self, new_scene):
            """Keep zoom/pan through edits and turns, recenter for a new map."""
            changed = (self.scene["mission"] != new_scene["mission"] or
                       self.scene["width"] != new_scene["width"] or
                       self.scene["height"] != new_scene["height"])
            self.scene = new_scene
            if changed:
                self._action_begins.clear()
            self.selection = None
            if changed:
                self.center_scene()
            else:
                self.refresh()

    return RendererController()


def create_view(scene, parent=None, *, character_pack=None, character_variant=None):
    """Return (QQuickView, controller); caller retains both references.

    Studio can wrap the QQuickView with QWidget.createWindowContainer(view).
    Player uses the *same* QQuickView directly.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQuick import QQuickView
    controller = make_controller(scene, character_pack=character_pack,
                                 character_variant=character_variant)
    view = QQuickView(parent)
    view.rootContext().setContextProperty("renderer", controller)
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).with_name("IsoViewport.qml").resolve())))
    if view.status() == QQuickView.Error:
        raise RuntimeError("QML renderer: " + "; ".join(str(e) for e in view.errors()))
    return view, controller


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp 5 shared Qt Quick ISO viewport")
    parser.add_argument("--mode", choices=("studio", "player"), default="player")
    parser.add_argument("--smoke", action="store_true", help="Load real scene and exit")
    parser.add_argument("--character-pack", type=Path, help="R7 exported character pack")
    parser.add_argument("--character-variant", help="Authored outfit ID")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QGuiApplication
    except ImportError:
        parser.error('PySide6 missing: install with python -m pip install ".[qt6]"')
    from drawtemp.sdk.reference import MISSION, reference_project
    content, _ = reference_project()
    scene = scene_from_mission(content.missions[MISSION])
    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    view, controller = create_view(scene, character_pack=args.character_pack,
                                   character_variant=args.character_variant)
    view.setTitle("DrawTemp 5 — " + args.mode.capitalize() + " / Shared ISO")
    view.resize(960, 640)
    view.show()
    if args.smoke:
        QTimer.singleShot(350, app.quit)
    status = app.exec()
    if view.rootObject() is None:
        return 1
    print(f"Shared ISO {args.mode}: {len(controller.items)} visible items")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
