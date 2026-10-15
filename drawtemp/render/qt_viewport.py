"""One Qt Quick scenegraph renderer for Studio and Player (R3 initial slice).

For GPU composition, clients embed the returned QQuickView as a native window
or display it directly. No tactical rules are evaluated in QML.
"""
import argparse
from pathlib import Path
import sys

from .iso_scene import Camera, IsoProjection, pick, render_items, scene_from_mission
from .building_geometry import pick_surface


def default_atlas_url():
    """One atlas binding for all clients; missing optional art is harmless."""
    from importlib.resources import files
    atlas = files("sporebound").joinpath("content/art/iso/terrain.png")
    return Path(str(atlas)).resolve().as_uri() if atlas.is_file() else ""


def make_controller(scene, atlas_url=None):
    """Create a QObject only when Qt is installed; keep headless module import safe."""
    from PySide6.QtCore import QObject, Property, Signal, Slot

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
            self._building_level = 0
            self._building_cutaway = False
            self._items = []
            self._atlas = default_atlas_url() if atlas_url is None else atlas_url
            self.center_scene()

        def center_scene(self):
            x, y = self.projection.project((self.scene["width"] - 1) / 2,
                                           (self.scene["height"] - 1) / 2)
            self.camera.center(x, y)
            self.refresh()

        def refresh(self):
            self._items = render_items(self.scene, self.camera, self.projection,
                                       self.selection, cutaway=self._building_cutaway,
                                       active_level=self._building_level)
            self.sceneChanged.emit()
            self.cameraChanged.emit()

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

        @Slot(float, float, result="QVariantMap")
        def buildingAt(self, x, y):
            """Exact R6 hit against the SAME visible polygons drawn by Qt Quick."""
            return pick_surface(self._items, self.camera, x, y) or {}

        @Slot(int, bool)
        def setConstructionView(self, active_level, cutaway):
            if type(active_level) is not int or not 0 <= active_level <= 3:
                raise ValueError("Invalid construction floor")
            if type(cutaway) is not bool:
                raise ValueError("Cutaway must be boolean")
            self._building_level = active_level
            self._building_cutaway = cutaway
            self.refresh()

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
            self.selection = None
            if changed:
                self.center_scene()
            else:
                self.refresh()

    return RendererController()


def create_view(scene, parent=None):
    """Return (QQuickView, controller); caller retains both references.

    Studio can wrap the QQuickView with QWidget.createWindowContainer(view).
    Player uses the *same* QQuickView directly.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQuick import QQuickView
    controller = make_controller(scene)
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
    view, controller = create_view(scene)
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
