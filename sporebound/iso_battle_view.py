"""Shared, presentation-only isometric battle scene for editor and Player.

The same render_isometric pipeline draws authored and live battle terrain.
The tactical model, movement, save schema and replay never depend on Tk.
"""
from .iso_architecture import architecture_instances, roof_cutaway
from .iso_depth import depth_order, visual_center

from .iso_map import IsoGeometry, IsoTerrainAtlas, render_isometric
from .iso_props import IsoPropAtlas
from .terrain_ambient import TerrainAmbientAnimator
from .iso_object_atlas import IsoObjectAtlas
from .iso_building_atlas import IsoBuildingAtlas
from .iso_fortification_atlas import IsoFortificationAtlas
from .iso_actor_atlas import (
    IsoActorAtlas, actor_style, actor_direction, actor_frame, actor_action)


def battle_layers(*, deploying=False, active_level=0):
    """Visible game layers, not authoring-only zones when battle has started."""
    return {'Terrain': True, 'Relief': True, 'Décors': True,
            'Bâtiments': True, 'Toitures': True, 'Déploiement': deploying,
            'Objectifs': True, 'Objets': True, 'Unités': True,
            'Intérieurs': active_level > 0, 'Étage actif': active_level}


def viewport_shift(geo, camera, viewport):
    """Center an isometric scene then apply the Player's reversible pan."""
    width, height = viewport
    if width <= 1 or height <= 1:
        width, height = 800, 500
    return (width / 2 - geo.width / 2 + camera.offset_x,
            height / 2 - geo.height / 2 + camera.offset_y)


def hit_test_battle(board, camera, viewport, screen):
    """Pure 2.5D picking. Returns None outside the projected board."""
    geo = IsoGeometry(board, camera.cell_size)
    dx, dy = viewport_shift(geo, camera, viewport)
    return geo.hit_test(screen[0] - dx, screen[1] - dy)


def anchored_iso_zoom(board, camera, viewport, steps, point, *, size=None):
    """Keep the pointed *tile center* stable at incremental or exact zoom."""
    from .presentation import Camera
    geo = IsoGeometry(board, camera.cell_size)
    old_dx, old_dy = viewport_shift(geo, camera, viewport)
    cell = geo.hit_test(point[0]-old_dx, point[1]-old_dy)
    size = max(16, min(128, camera.cell_size + 8*steps if size is None else size))
    if size == camera.cell_size:
        return camera
    updated = Camera(size, camera.offset_x, camera.offset_y)
    if cell is None:
        return updated
    new_geo = IsoGeometry(board, size)
    new_dx, new_dy = viewport_shift(new_geo, updated, viewport)
    old_xy = geo.center(cell)
    new_xy = new_geo.center(cell)
    return Camera(size,
                  camera.offset_x + old_xy[0] + old_dx - new_xy[0] - new_dx,
                  camera.offset_y + old_xy[1] + old_dy - new_xy[1] - new_dy)


class IsoBattleCanvas:
    """Reusable adapter: project Battle without simulating any action."""
    def __init__(self, canvas):
        self.canvas = canvas
        self.terrain = IsoTerrainAtlas(canvas)
        self.props = IsoPropAtlas(canvas)
        self.objects = IsoObjectAtlas(canvas)
        self.buildings = IsoBuildingAtlas(canvas)
        self.fortifications = IsoFortificationAtlas(canvas)
        self.actors = IsoActorAtlas(canvas)
        self.geometry = None
        self.shift = (0, 0)
        self.ambient = TerrainAmbientAnimator()
        # A frame is immutable and identical throughout each MotionDirector
        # animation. Preserve authored scenery on animation-only redraws.
        self._frame = None
        self._board = None
        self._camera = None
        self._viewport = None
        self._unit_ids = ()
        self._unit_state = ()
        self._positions = ()
        self._actor_sprite_states = ()
        self._architecture = ()
        self._objects = ()
        self._props = ()
        self._cutaways = ()
        self._level_map = {}
        self._floor_records = ()
        self._scene_rebuilds = 0
        self._actor_only_frames = 0

    def viewport(self):
        return (self.canvas.winfo_width(), self.canvas.winfo_height())

    def _cutaway_flags(self, frame, units, poses):
        return tuple(roof_cutaway(building, frame.selected, units, poses)
                     for building in self._architecture)

    def _pose_centers(self, units, poses):
        return tuple((x, y-self._level_map.get(actor.id, 0)*3*self.geometry.step)
                     for actor in units
                     for x, y in [visual_center(self.geometry, actor, poses)])

    @staticmethod
    def _actor_state(units):
        """Snapshot all actor data painted by the static Canvas groups."""
        return tuple((actor.id, actor.name, actor.team, actor.pos,
                      actor.footprint, actor.alive, actor.hp)
                     for actor in units)

    @staticmethod
    def _sprite_states(units, poses=None):
        return tuple((actor_style(actor),
                      actor_direction(actor, (poses or {}).get(actor.id)),
                      actor_frame((poses or {}).get(actor.id)),
                      actor.alive,
                      actor_action((poses or {}).get(actor.id))
                      if actor.alive else 'defeat')
                     for actor in units)

    def _refresh_sprite_frames(self, units, poses, camera):
        """Swap only image handles on a cached frame; never rebuild terrain."""
        states = self._sprite_states(units, poses)
        if states == self._actor_sprite_states:
            return
        # Fake headless canvases intentionally lack find_withtag/itemconfigure.
        if hasattr(self.canvas, 'find_withtag') and hasattr(self.canvas, 'itemconfigure'):
            for i, (before, after) in enumerate(zip(self._actor_sprite_states, states)):
                if before == after or (not after[3] and after[0] != 'jeanne'):
                    continue
                images = [item for item in self.canvas.find_withtag(
                          'iso_actor_unit_' + str(i))
                          if self.canvas.type(item) == 'image']
                if not images:
                    continue
                image = self.actors.sprite(*after[:3], camera.cell_size, after[4])
                if image is not None:
                    for item in images:
                        self.canvas.itemconfigure(item, image=image)
        self._actor_sprite_states = states

    @property
    def animates_when_idle(self):
        return self.ambient.active

    def draw(self, battle, frame, camera, *, poses=None, ambient_clock_ms=None):
        """Reuse the scene on motion ticks; repaint on any meaningful change.

        A changed frame, board, camera, viewport, actor list or roof-cutaway
        boundary forces a full redraw. During stable motion only the actor
        canvas groups are moved and their depth ordering recomputed.
        """
        units = battle.units
        viewport = self.viewport()
        ids = tuple(actor.id for actor in units)
        actor_state = self._actor_state(units)
        reusable = (
            self.geometry is not None
            and frame is self._frame
            and battle.board is self._board
            and camera == self._camera
            and viewport == self._viewport
            and ids == self._unit_ids
            and actor_state == self._unit_state
            and self._level_map == battle.unit_levels
            and self._cutaways == self._cutaway_flags(frame, units, poses)
            # The 2D Player renderer may have taken the *same* Canvas
            # between two ISO ticks. Never animate stale/destroyed item IDs.
            and (not hasattr(self.canvas, 'find_withtag')
                 or bool(self.canvas.find_withtag('iso_tile_0_0')))
        )
        if reusable:
            moved = False
            positions = self._pose_centers(units, poses)
            for index, (before, after) in enumerate(zip(self._positions, positions)):
                dx, dy = after[0] - before[0], after[1] - before[1]
                if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                    self.canvas.move('iso_actor_unit_' + str(index), dx, dy)
                    moved = True
            if moved:
                for tag in depth_order(self._architecture, units, poses,
                                       objects=self._objects, props=self._props):
                    self.canvas.tag_raise(tag)
                for index, actor in enumerate(units):
                    if self._level_map.get(actor.id, 0) > 0:
                        self.canvas.tag_raise('iso_actor_unit_' + str(index))
                self.canvas.tag_raise('selection')
            self._refresh_sprite_frames(units, poses, camera)
            self._positions = positions
            self._actor_only_frames += 1
            if ambient_clock_ms is not None:
                self.ambient.tick(self.canvas, ambient_clock_ms)
            return self.geometry

        geo = render_isometric(
            self.canvas, battle.board, battle.mission, units,
            cell_size=camera.cell_size,
            layers=battle_layers(
                deploying=battle.deploying,
                active_level=battle.unit_levels.get(battle.active_id, 0)
                if battle.active_id else 0),
            selected_cell=frame.selected, selected_tiles=(),
            reachable=frame.reachable, danger=frame.danger,
            active_id=frame.active_id, atlas=self.terrain, prop_atlas=self.props,
            building_atlas=self.buildings, fortification_atlas=self.fortifications,
            actor_atlas=self.actors, poses=poses,
            object_atlas=self.objects,
            unit_levels=battle.unit_levels)
        self.geometry = geo
        self.shift = viewport_shift(geo, camera, viewport)
        self.canvas.move('all', *self.shift)
        self.ambient.capture(self.canvas)
        if ambient_clock_ms is not None:
            self.ambient.tick(self.canvas, ambient_clock_ms)
        if frame.result:
            self.canvas.create_text(viewport[0]/2, 22,
                                    text=frame.result.upper(), fill='#ffe38d',
                                    font=('TkDefaultFont', 16, 'bold'),
                                    tags='iso_result')
        self._frame = frame
        self._board = battle.board
        self._camera = camera
        self._viewport = viewport
        self._unit_ids = ids
        self._unit_state = actor_state
        self._level_map = dict(battle.unit_levels)
        self._floor_records = tuple(battle.mission.interior_floors)
        self._architecture = architecture_instances(
            battle.board, getattr(battle.mission, 'structures', ()))
        self._objects = tuple(battle.mission.objects)
        self._props = tuple(c for c in geo.draw_order
                            if battle.board.tile(c).feature)
        self._cutaways = self._cutaway_flags(frame, units, poses)
        self._positions = self._pose_centers(units, poses)
        self._actor_sprite_states = self._sprite_states(units, poses)
        self._scene_rebuilds += 1
        return geo

    def hit_test(self, x, y, *, level=0):
        if self.geometry is None:
            return None
        px, py = x-self.shift[0], y-self.shift[1]
        if level > 0:
            from .interior_levels import floor_hit_test
            for building in reversed(self._architecture):
                for floor in self._floor_records:
                    if floor['structure_id'] == building.id and floor['level'] == level:
                        result = floor_hit_test(self.geometry, building, floor, px, py)
                        if result is not None:
                            return result
            return None
        return self.geometry.hit_test(px, py)

    def dispose(self):
        self.ambient.clear()
        self.geometry = None
        self._frame = None
        self._board = None
        self._camera = None
        self._viewport = None
        self._unit_ids = ()
        self._unit_state = ()
        self._architecture = ()
        self._objects = ()
        self._props = ()
        self._cutaways = ()
        self._positions = ()
        self._actor_sprite_states = ()
        self._floor_records = ()
        self._level_map = {}
        self.terrain._tiles.clear()
        self.props.clear_cache()
        self.objects.clear_cache()
        self.buildings.clear_cache()
        self.fortifications.clear_cache()
        self.actors.clear_cache()
