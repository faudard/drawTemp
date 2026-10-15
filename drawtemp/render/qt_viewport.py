"""One Qt Quick scenegraph renderer for Studio and Player (R3 initial slice).

For GPU composition, clients embed the returned QQuickView as a native window
or display it directly. No tactical rules are evaluated in QML.
"""
import argparse
from pathlib import Path
import sys

from .iso_scene import Camera, IsoProjection, pick, render_items, scene_from_mission
from .tile_chunks import TileChunkIndex


def default_atlas_url():
    """One atlas binding for all clients; missing optional art is harmless."""
    from importlib.resources import files
    atlas = files("sporebound").joinpath("content/art/iso/terrain.png")
    return Path(str(atlas)).resolve().as_uri() if atlas.is_file() else ""


def make_controller(scene, atlas_url=None, *, assets=None):
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
            self._items = []
            self._base_items = []
            self._elapsed_ms = 0
            self.assets = assets
            self._index = TileChunkIndex(scene)
            self.overlays = {}
            self._atlas = default_atlas_url() if atlas_url is None else atlas_url
            self.center_scene()

        def center_scene(self):
            x, y = self.projection.project((self.scene["width"] - 1) / 2,
                                           (self.scene["height"] - 1) / 2)
            self.camera.center(x, y)
            self.refresh()

        def refresh(self):
            self._base_items = render_items(self.scene, self.camera, self.projection,
                                            self.selection, tile_index=self._index,
                                            overlays=self.overlays)
            self._items = (self.assets.decorate(self._base_items, elapsed_ms=self._elapsed_ms)
                           if self.assets is not None else self._base_items)
            self.sceneChanged.emit()
            self.cameraChanged.emit()

        @Property("QVariantList", notify=sceneChanged)
        def items(self):
            return self._items

        @Property("QVariantMap", notify=cameraChanged)
        def cameraState(self):
            return {"zoom": self.camera.zoom, "panX": self.camera.pan_x,
                    "panY": self.camera.pan_y}

        @Property(bool, notify=sceneChanged)
        def animatedAssets(self):
            return self.assets is not None and self.assets.has_animations

        @Slot(int)
        def advanceVisual(self, delta_ms):
            """Animate cosmetics only; never touch the tactical simulation."""
            if (type(delta_ms) is not int or not 1 <= delta_ms <= 1000):
                return
            if self.assets is not None and self.assets.has_animations:
                self._elapsed_ms += delta_ms
                self._items = self.assets.decorate(
                    self._base_items, elapsed_ms=self._elapsed_ms)
                self.sceneChanged.emit()

        def replace_assets(self, assets):
            self.assets = assets
            self._elapsed_ms = 0
            self.refresh()

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

        @Slot("QVariantMap")
        def setOverlays(self, overlays):
            """Set cosmetic [x,y] cell sets for reach, path, LOS, range, intents.

            Validation runs before mutating the live viewport. Gameplay and
            authoring remain owned by the R1/R5 controllers, not this adapter.
            """
            from .iso_scene import OVERLAY_COLORS
            candidate = {}
            if not hasattr(overlays, "items"):
                raise ValueError("Overlays must be a mapping")
            for kind, cells in overlays.items():
                if kind not in OVERLAY_COLORS:
                    raise ValueError("Unknown overlay: " + str(kind))
                if not isinstance(cells, (tuple, list)):
                    raise ValueError("Overlay cells must be a sequence")
                normalized = []
                for cell in cells:
                    if not isinstance(cell, (tuple, list)) or len(cell) != 2:
                        raise ValueError("Overlay cells must be [x,y]")
                    x, y = cell
                    if type(x) is not int or type(y) is not int:
                        raise ValueError("Overlay coordinates must be integers")
                    if not (0 <= x < self.scene["width"] and
                            0 <= y < self.scene["height"]):
                        raise ValueError("Overlay cell outside the map")
                    normalized.append((x, y))
                candidate[kind] = tuple(normalized)
            self.overlays = candidate
            self.refresh()

        @Slot()
        def clearOverlays(self):
            self.overlays = {}
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
            self.selection = None
            self.overlays = {}  # Never carry stale tactical previews across turns.
            if changed:
                self._index = TileChunkIndex(new_scene)
                self.center_scene()
            else:
                self._index.update(new_scene)
                self.refresh()

    return RendererController()


def create_view(scene, parent=None, *, assets=None):
    """Return (QQuickView, controller); caller retains both references.

    Studio can wrap the QQuickView with QWidget.createWindowContainer(view).
    Player uses the *same* QQuickView directly.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQuick import QQuickView
    controller = make_controller(scene, assets=assets)
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
