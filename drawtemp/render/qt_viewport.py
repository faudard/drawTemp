"""One Qt Quick scenegraph renderer for Studio and Player (R3 initial slice).

For GPU composition, clients embed the returned QQuickView as a native window
or display it directly. No tactical rules are evaluated in QML.
"""
import argparse
from pathlib import Path
import sys

from .iso_scene import Camera, IsoProjection, pick, render_items, scene_from_mission
from .event_overlay import project_event_markers
from .tile_chunks import TileChunkIndex
from .visual_compositor import actor_visual_position, automatic_cutaway
from .building_geometry import pick_surface
from .texture_batches import TerrainTextureBatches, make_image_provider


def default_atlas_url():
    """One atlas binding for all clients; missing optional art is harmless."""
    from importlib.resources import files
    atlas = files("sporebound").joinpath("content/art/iso/terrain.png")
    return Path(str(atlas)).resolve().as_uri() if atlas.is_file() else ""


def make_controller(scene, atlas_url=None, *, assets=None,
                    character_pack=None, character_variant=None):
    """Shared R3 renderer with optional R7 character pack, no gameplay changes."""
    from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QElapsedTimer
    from drawtemp.assets.character_runtime import CharacterPack
    from drawtemp.assets.characters import ACTIONS
    from drawtemp.assets.character_outfits import outfit_from_progress

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
            self._event_markers = []
            self._event_selected = ""
            self._base_items = []
            # Keep R4 atlas decoration separate from R7 frame state.
            # Missing R7 frames must fall back without stale imageUrl.
            self._visual_base_items = []
            self._elapsed_ms = 0
            self.assets = assets
            self._index = TileChunkIndex(scene)
            self.overlays = {}
            self.active_level = 0
            self._atlas = default_atlas_url() if atlas_url is None else atlas_url
            self._batch = TerrainTextureBatches(self._index, atlas_url=self._atlas)
            self._batch_enabled = False  # Enabled only when an engine owns the provider.
            self._image_provider = None
            self._rendered_items = []
            self._batch_rows = []
            self._batched_ids = set()
            self._character = (
                character_pack if isinstance(character_pack, CharacterPack)
                else CharacterPack(character_pack) if character_pack is not None
                else None)
            self._variant = character_variant
            if (self._character is not None and character_variant is not None
                    and character_variant not in self._character.variants):
                raise ValueError("Unknown character outfit: " + character_variant)
            self._outfits = {}
            self._progress_outfits = {}
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

        @staticmethod
        def _apply_character_art(row, art):
            """Expose R7 authored sprites through the canonical R4 Qt delegate."""
            if not art:
                return
            region, pivot = art["spriteRegion"], art["spritePivot"]
            row.update(art)
            row.update({
                "imageUrl": art["spriteUrl"],
                "atlasX": region[0], "atlasY": region[1],
                "frameWidth": region[2], "frameHeight": region[3],
                "pivotX": pivot[0], "pivotY": pivot[1],
            })

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
                outfit = self.outfit_for(actor_id)
                if outfit is None:
                    outfit = self._character.variants[0]
                direction = row.get("direction", "south")
                if not row.get("alive", True):
                    # Dead units hold the authored final pose; never animate idle
                    # as if they were alive. Missing death art falls back to the
                    # legacy desaturated vector silhouette.
                    death_ms = self._character.duration(outfit, "death", direction)
                    if death_ms:
                        self._apply_character_art(row, self._character.preview_actor(
                            actor_id, variant=outfit, action="death",
                            direction=direction, elapsed_ms=death_ms - 1))
                    continue
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
                    self._apply_character_art(row, art)

        def refresh(self):
            self._base_items = render_items(self.scene, self.camera, self.projection,
                                            self.selection, tile_index=self._index,
                                            overlays=self.overlays,
                                            active_level=self.active_level,
                                            cutaway=self._building_cutaway)
            self._items = (self.assets.decorate(self._base_items, elapsed_ms=self._elapsed_ms)
                           if self.assets is not None else self._base_items)
            if self._batch_enabled:
                self._batch_rows, self._batched_ids = self._batch.prepare(self._items)
            else:
                self._batch_rows, self._batched_ids = [], set()
            self._visual_base_items = self._items
            self._items = [dict(row) for row in self._visual_base_items]
            self.decorate_frames(self._items)
            self._filter_visible_items()
            self.sceneChanged.emit()
            self.cameraChanged.emit()

        def _filter_visible_items(self):
            # Keep the public items/scene contract intact for clients and R3 tests.
            # Only the actual QML scenegraph uses the much smaller displayItems.
            self._rendered_items = [
                row for row in self._items
                if row["id"] not in self._batched_ids or
                (row["kind"] == "tile" and
                 (row.get("selected") or row.get("overlay")))
            ]

        def attach_engine(self, engine):
            """Register a single image provider on a QQuickView/QQuickWidget engine.

            A standalone controller without an engine still uses the unchanged
            per-tile renderer; the Player and Studio both register before load.
            """
            if self._image_provider is not None:
                return
            provider = make_image_provider(self._batch)
            engine.addImageProvider("drawtemp-tiles", provider)
            self._image_provider = provider  # Qt owns it while engine is live.
            self._batch_enabled = True
            self.refresh()

        @Property(bool, notify=sceneChanged)
        def textureBatching(self):
            return self._batch_enabled

        def advance_frames(self):
            """Tick just the actor frames; do not recompute/cull terrain at 12 Hz."""
            if self._character is None:
                return
            # Re-sample from undecorated R4 rows rather than the previous
            # R7 frame; a missing idle/death frame must not display stale art.
            rows = [dict(row) for row in self._visual_base_items]
            self.decorate_frames(rows)
            if rows != self._items:
                self._items = rows
                self._filter_visible_items()
                self.sceneChanged.emit()

        def outfit_for(self, actor_id):
            return self._outfits.get(
                actor_id, self._progress_outfits.get(actor_id, self._variant))

        def sync_progress(self, progress, equipment):
            """Reconstruct costume from canonical equipment after load/equip.

            Does not change GameSession, Content, inventory or save format.
            Presentation-only temporary previews continue to take priority.
            """
            if self._character is None:
                return False
            hero_id = self._character.character_id
            desired = outfit_from_progress(
                progress, equipment, hero_id, self._character.variants)
            if self._progress_outfits.get(hero_id) == desired:
                return False
            self._progress_outfits[hero_id] = desired
            self.refresh()
            return True

        def clear_outfit_preview(self):
            """Discard unsaved costume previews on new/load/restore."""
            if self._outfits:
                self._outfits.clear()
                self.refresh()

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
        def tileBatches(self):
            return self._batch_rows

        @Property("QVariantList", notify=sceneChanged)
        def displayItems(self):
            return self._rendered_items

        @Slot(int, int, result=bool)
        def isBatchedCell(self, x, y):
            return "tile:%d:%d" % (x, y) in self._batched_ids

        @Property("QVariantMap", notify=sceneChanged)
        def textureStats(self):
            return {
                "tiles": len(self._batched_ids),
                "images": len(self._batch_rows),
                "bytes": self._batch.store.used_bytes,
                "budget": self._batch.store.budget,
                "hits": self._batch.store.hits,
                "misses": self._batch.store.misses,
            }

        @Property("QVariantList", notify=sceneChanged)
        def items(self):
            return self._items

        @Property("QVariantList", notify=sceneChanged)
        def eventMarkers(self):
            return project_event_markers(self.scene, self._event_markers,
                                         selected_id=self._event_selected,
                                         projection=self.projection)

        def setEventMarkers(self, markers, selected_id=""):
            """Read-only R9 overlay: opt-in, independent of Player render items."""
            from copy import deepcopy
            staged = deepcopy(markers)
            project_event_markers(self.scene, staged,
                                  selected_id=selected_id,
                                  projection=self.projection)
            self._event_markers = staged
            self._event_selected = selected_id
            self.sceneChanged.emit()

        @Property("QVariantMap", notify=cameraChanged)
        def cameraState(self):
            return {"zoom": self.camera.zoom, "panX": self.camera.pan_x,
                    "panY": self.camera.pan_y}

        @Property(bool, notify=sceneChanged)
        def animatedAssets(self):
            return self.assets is not None and self.assets.has_animations

        @Slot(str, str, str, int, result="QVariantMap")
        def animationFrame(self, actor_id, direction, pose, elapsed_ms):
            """Read-only frame for R12 committed event clips.

            The same project AssetRegistry and resolver power R3's idle actor
            and R12's action ghost. No new manifest, painter, or battle rules.
            """
            if self.assets is None:
                return {}
            try:
                return self.assets.actor_frame(
                    actor_id, direction=direction, pose=pose,
                    elapsed_ms=elapsed_ms) or {}
            except (OSError, ValueError, RuntimeError):
                return {}

        @Slot("QVariantMap", float, result="QVariantMap")
        def visualClipFrame(self, clip, phase):
            """Sample the committed event's true R7/R4 sprite, without CT ticks.

            This is shared by the Player TacticalBoard and the Studio renderer;
            it uses the existing character outfit projection and asset registry.
            No action pose is invented if the appropriate R7 clip is absent.
            """
            from .visual_clip_frames import clip_art_frame
            if not isinstance(clip, dict):
                return {}
            actor = next((item for item in self.scene["actors"]
                          if item["id"] == clip.get("actor")), None)
            if actor is None:
                return {}
            return clip_art_frame(
                clip, phase, actor=actor, character=self._character,
                variant=self.outfit_for(actor["id"]), assets=self.assets)

        @Slot(int)
        def advanceVisual(self, delta_ms):
            """Animate cosmetics only; never touch the tactical simulation."""
            if (type(delta_ms) is not int or not 1 <= delta_ms <= 1000):
                return
            if self.assets is not None and self.assets.has_animations:
                self._elapsed_ms += delta_ms
                self._visual_base_items = self.assets.decorate(
                    self._base_items, elapsed_ms=self._elapsed_ms)
                self._items = [dict(row) for row in self._visual_base_items]
                self.decorate_frames(self._items)
                self._filter_visible_items()
                self.sceneChanged.emit()

        def replace_assets(self, assets):
            self.assets = assets
            self._elapsed_ms = 0
            self.refresh()

        @Property("QVariantList", notify=sceneChanged)
        def autoCutawayStructures(self):
            return list(automatic_cutaway(self.scene, selected=self.selection,
                                          active_level=self.active_level))

        @Slot(int)
        def setActiveLevel(self, level):
            if type(level) is not int or level < 0:
                raise ValueError("Level must be a non-negative integer")
            self.active_level = level
            self.refresh()

        @Slot("QVariantMap", float, result="QVariantMap")
        def motionPoint(self, clip, phase):
            """Project a committed R12 clip; no gameplay state is touched."""
            actor_id = clip.get("actor") if hasattr(clip, "get") else None
            actor = next((a for a in self.scene["actors"] if a["id"] == actor_id), None)
            if actor is None:
                return {}
            return actor_visual_position(actor, dict(clip), phase,
                                         self._index.elevations, self.scene["width"],
                                         self.scene["height"], self.projection) or {}

        @Property(str, constant=True)
        def atlasUrl(self):
            return self._atlas

        @Property("QVariantList", constant=True)
        def characterOutfits(self):
            return list(self._character.variants) if self._character else []

        @Property(str, constant=True)
        def characterId(self):
            return self._character.character_id if self._character else ""

        @Property(str, notify=sceneChanged)
        def characterCurrentOutfit(self):
            if self._character is None:
                return ""
            return self.outfit_for(self._character.character_id) or self._character.variants[0]

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
            hit = pick(self.scene, self.camera, x, y, self.projection,
                       selected=self.selection, active_level=self.active_level)
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
            self.active_level = active_level
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
            if changed:
                self._event_markers = []
                self._event_selected = ""
                self._action_begins.clear()
            self.selection = None
            self.overlays = {}  # Never carry stale tactical previews across turns.
            if changed:
                self.active_level = 0
            if changed:
                self._index = TileChunkIndex(new_scene)
                self._batch.reset(self._index)
                self.center_scene()
            else:
                dirty = self._index.update(new_scene)
                self._batch.invalidate(dirty)
                self.refresh()

    return RendererController()


def create_view(scene, parent=None, *, assets=None,
                character_pack=None, character_variant=None):
    """Return (QQuickView, controller); caller retains both references.

    Studio can wrap the QQuickView with QWidget.createWindowContainer(view).
    Player uses the *same* QQuickView directly.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQuick import QQuickView
    controller = make_controller(scene, assets=assets,
                                 character_pack=character_pack,
                                 character_variant=character_variant)
    view = QQuickView(parent)
    controller.attach_engine(view.engine())
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
