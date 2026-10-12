"""Shared, presentation-only isometric battle scene for editor and Player.

The same render_isometric pipeline draws authored and live battle terrain.
The tactical model, movement, save schema and replay never depend on Tk.
"""
from dataclasses import dataclass

from .iso_map import IsoGeometry, IsoTerrainAtlas, render_isometric
from .iso_props import IsoPropAtlas
from .iso_building_atlas import IsoBuildingAtlas
from .iso_fortification_atlas import IsoFortificationAtlas


def battle_layers(*, deploying=False):
    """Visible game layers, not authoring-only zones when battle has started."""
    return {'Terrain': True, 'Relief': True, 'Décors': True,
            'Bâtiments': True, 'Toitures': True, 'Déploiement': deploying,
            'Objectifs': True, 'Objets': True, 'Unités': True}


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


def anchored_iso_zoom(board, camera, viewport, steps, point):
    """Keep the pointed *tile center* stable when changing isometric zoom."""
    from .presentation import Camera
    geo = IsoGeometry(board, camera.cell_size)
    old_dx, old_dy = viewport_shift(geo, camera, viewport)
    cell = geo.hit_test(point[0]-old_dx, point[1]-old_dy)
    size = max(16, min(128, camera.cell_size + 8*steps))
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
        self.buildings = IsoBuildingAtlas(canvas)
        self.fortifications = IsoFortificationAtlas(canvas)
        self.geometry = None
        self.shift = (0, 0)

    def viewport(self):
        return (self.canvas.winfo_width(), self.canvas.winfo_height())

    def draw(self, battle, frame, camera):
        """One snapshot: authored terrain, actors, reachable and danger overlays."""
        geo = render_isometric(
            self.canvas, battle.board, battle.mission, battle.units,
            cell_size=camera.cell_size,
            layers=battle_layers(deploying=battle.deploying),
            selected_cell=frame.selected, selected_tiles=(),
            reachable=frame.reachable, danger=frame.danger,
            active_id=frame.active_id, atlas=self.terrain, prop_atlas=self.props,
            building_atlas=self.buildings, fortification_atlas=self.fortifications)
        self.geometry = geo
        self.shift = viewport_shift(geo, camera, self.viewport())
        self.canvas.move('all', *self.shift)
        if frame.result:
            self.canvas.create_text(self.viewport()[0]/2, 22,
                                    text=frame.result.upper(), fill='#ffe38d',
                                    font=('TkDefaultFont', 16, 'bold'),
                                    tags='iso_result')
        # render_isometric manages the same roof cutaways as in the editor.
        return geo

    def hit_test(self, x, y):
        if self.geometry is None:
            return None
        return self.geometry.hit_test(x-self.shift[0], y-self.shift[1])

    def dispose(self):
        self.geometry = None
        self.terrain._tiles.clear()
        self.props.clear_cache()
        self.buildings.clear_cache()
        self.fortifications.clear_cache()
