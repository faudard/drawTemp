"""Pure-coordinate isometric map view for the mission authoring canvas.

This is an editor visualization; the tactical board and all pathfinding remain
orthogonal. Geometry and hit-testing work without importing tkinter.
"""
from dataclasses import dataclass
from pathlib import Path

from .tk_images import crop_scaled
from .iso_depth import visual_center

from .iso_connections import (shoreline_mask, waterfall_mask, bridge_axis,
                              transition_segments, bridge_rails)

SURFACES = frozenset({'grass', 'dirt', 'stone', 'cobble', 'sand',
                      'rock', 'water', 'bridge'})
FEATURES = frozenset({'', 'tree', 'bush', 'boulder', 'ruin', 'crate',
                      'lantern', 'stairs', 'stone_wall',
                      'arch', 'fence', 'reeds', 'pillar'})
SURFACE_COLORS = {
    'grass': '#9aa66c', 'dirt': '#c6a875', 'stone': '#aca69a',
    'cobble': '#c6b9a0', 'sand': '#dec897', 'rock': '#8e978d',
    'water': '#4d92ac', 'bridge': '#c5b496',
}



# Original 8 x 2 textured PNG atlas; 96 x 48 per transparent isometric tile.
ATLAS_MATERIALS = ('grass', 'dirt', 'stone', 'cobble',
                   'sand', 'rock', 'water', 'bridge')
ATLAS_VARIANTS = 2
ATLAS_TILE_SIZE = (96, 48)
DEFAULT_TERRAIN_ATLAS = Path(__file__).parent / 'content' / 'art' / 'iso' / 'terrain.png'


class IsoTerrainAtlas:
    """Load one PNG once; resize cropped regions at each requested Tk zoom.

    The editor remains functional if the file is absent or Tk cannot display it.
    Image refs stay alive as long as this loader stays alive.
    """
    def __init__(self, canvas, path=DEFAULT_TERRAIN_ATLAS):
        self.canvas = canvas
        self.path = Path(path)
        self._source = None
        self._tiles = {}
        self._unavailable = False

    def tile(self, surface, cell_size, variant=0):
        if self._unavailable or surface not in ATLAS_MATERIALS:
            return None
        if type(cell_size) is not int or cell_size < 1:
            return None
        variant %= ATLAS_VARIANTS
        key = surface, cell_size, variant
        if key in self._tiles:
            return self._tiles[key]
        try:
            import tkinter as tk
        except ImportError:
            self._unavailable = True
            return None
        try:
            if self._source is None:
                self._source = tk.PhotoImage(file=str(self.path), master=self.canvas)
                required = len(ATLAS_MATERIALS) * ATLAS_VARIANTS * ATLAS_TILE_SIZE[0]
                if (self._source.width() != required or
                        self._source.height() != ATLAS_TILE_SIZE[1]):
                    raise ValueError('Unexpected terrain atlas dimensions')
            source_width, source_height = ATLAS_TILE_SIZE
            target_width, target_height = 2*cell_size, cell_size
            sx = ATLAS_MATERIALS.index(surface) * ATLAS_VARIANTS + variant
            x = sx * source_width
            photo = crop_scaled(self._source,
                                (x, 0, source_width, source_height),
                                (target_width, target_height), master=self.canvas)
            self._tiles[key] = photo
            return photo
        except (OSError, ValueError, RuntimeError, ImportError, tk.TclError):
            self._unavailable = True
            return None

def _flatten(points):
    return tuple(coord for point in points for coord in point)


def _line_cells(first, last):
    """Integer raster stroke: no holes when the pointer jumps between cells."""
    x0, y0 = first
    x1, y1 = last
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    error = dx + dy
    while True:
        yield (x0, y0)
        if (x0, y0) == (x1, y1):
            return
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


@dataclass
class IsoGeometry:
    board: object
    cell_size: int

    def __post_init__(self):
        self.half_width = self.cell_size
        self.half_height = self.cell_size / 2
        self.step = max(5, self.cell_size // 4)
        self.max_height = max((t.height for t in self.board.tiles.values()), default=0)
        self.origin_x = (self.board.height + 1) * self.half_width + 36
        self.origin_y = self.max_height * self.step + 2*self.cell_size + 48
        self.width = (self.board.width + self.board.height + 3) * self.half_width + 72
        self.height = ((self.board.width + self.board.height + 3) *
                       self.half_height + self.max_height * self.step
                       + 2*self.cell_size + 120)
        self.draw_order = tuple(sorted(self.board.cells(),
                                       key=lambda c: (sum(c), c[0])))
        # Spatial buckets avoid O(width*height) mouse hit tests on each move.
        self._bucket_size = max(16, self.cell_size * 2)
        self._pick_buckets = {}
        for cell in self.draw_order:
            cx, cy = self.center(cell)
            left = int((cx-self.half_width)//self._bucket_size)
            right = int((cx+self.half_width)//self._bucket_size)
            top = int((cy-self.half_height)//self._bucket_size)
            bottom = int((cy+self.half_height)//self._bucket_size)
            for by in range(top, bottom+1):
                for bx in range(left, right+1):
                    self._pick_buckets.setdefault((bx, by), []).append(cell)

    def center(self, cell):
        x, y = cell
        return (self.origin_x + (x - y) * self.half_width,
                self.origin_y + (x + y) * self.half_height
                - self.board.tile(cell).height * self.step)

    def polygon(self, cell):
        cx, cy = self.center(cell)
        w, h = self.half_width, self.half_height
        return ((cx, cy-h), (cx+w, cy), (cx, cy+h), (cx-w, cy))

    def hit_test(self, px, py):
        # Reverse painter's order: pick the uppermost visible diamond.
        bucket = (int(px//self._bucket_size), int(py//self._bucket_size))
        for cell in reversed(self._pick_buckets.get(bucket, ())):
            cx, cy = self.center(cell)
            if (abs(px-cx) / self.half_width +
                    abs(py-cy) / self.half_height <= 1):
                return cell
        return None


def render_isometric(canvas, board, mission, units, *, cell_size, layers,
                     selected_cell, selected_tiles, reachable=(), danger=(), active_id=None,
                     atlas=None, prop_atlas=None,
                     building_atlas=None, fortification_atlas=None,
                     actor_atlas=None, poses=None):
    """Draw walkable 2.5D blocks, water, bridges and decorative props on Tk Canvas."""
    geo = IsoGeometry(board, cell_size)
    canvas.delete('all')
    canvas.configure(scrollregion=(0, 0, geo.width, geo.height))
    goals = set(mission.goal)
    deploy = {tuple(c) for z in mission.deployment for c in z['cells']}
    actors = {}
    for index, actor in enumerate(units):
        actors.setdefault(tuple(actor.pos), []).append((index, actor))
    objects = {}
    for obj in mission.objects:
        objects.setdefault(tuple(obj['pos']), []).append(obj)
    reachable = set(reachable)
    # Source-of-truth tactical intents use the same priority as CanvasRenderer.
    danger_priority = {'hazard': 0, 'charge': 1, 'prepared': 2, 'cast': 3}
    danger_colors = {'hazard': '#fd766f', 'charge': '#f5ae60',
                     'prepared': '#f5d07a', 'cast': '#c69df8'}
    threats = {}
    for entry in danger:
        cell, kind = tuple(entry['cell']), entry['kind']
        if kind in danger_priority and (cell not in threats or
                danger_priority[kind] > danger_priority[threats[cell]]):
            threats[cell] = kind

    for c in geo.draw_order:
        tile = board.tile(c)
        corners = geo.polygon(c)
        north, east, south, west = corners
        cx, cy = geo.center(c)
        surface = tile.surface if layers.get('Terrain', True) else 'stone'
        top = SURFACE_COLORS[surface]
        if tile.blocked and surface not in ('water', 'bridge'):
            top = '#777b71'
        elif tile.hazard:
            top = '#ce9978'
        elif tile.cost > 1 and surface == 'grass':
            top = '#ad9d71'
        # Visible vertical sides; neighbouring higher blocks hide their own face.
        if layers.get('Relief', True):
            for dx, dy, edge, shade in ((1, 0, (east, south), '#777766'),
                                        (0, 1, (south, west), '#8d8876')):
                nx, ny = c[0]+dx, c[1]+dy
                neighbour = (board.tile((nx, ny)).height if board.contains((nx, ny))
                             else -1)
                if tile.height > neighbour:
                    drop = (tile.height - max(-1, neighbour)) * geo.step
                    p, q = edge
                    canvas.create_polygon(*_flatten((p, q, (q[0], q[1]+drop),
                                                    (p[0], p[1]+drop))),
                                          fill=shade, outline='#615d52', width=1)
        canvas.create_polygon(*_flatten(corners), fill=top, outline='#777c6f', width=1)
        photo = None
        if atlas is not None and layers.get('Terrain', True):
            photo = atlas.tile(surface, cell_size,
                               variant=(c[0]*37 + c[1]*19) % ATLAS_VARIANTS)
        if photo is not None:
            canvas.create_image(cx-cell_size, cy-cell_size/2,
                                image=photo, anchor='nw')
        if surface == 'water' and layers.get('Terrain', True):
            # Stable, neighbour-aware banks; no seams between water cells.
            mask = shoreline_mask(board, c)
            for p, q in transition_segments(corners, mask):
                canvas.create_line(*p, *q, fill='#335e68',
                                   width=max(2,cell_size//13))
                canvas.create_line(p[0]*.78+q[0]*.22,
                                   p[1]*.78+q[1]*.22,
                                   p[0]*.22+q[0]*.78,
                                   p[1]*.22+q[1]*.78,
                                   fill='#c2e4dc', width=max(1,cell_size//25))
            canvas.create_line(cx-cell_size*.28,cy-2, cx,cy-2-cell_size*.13,
                               fill='#b3dadd', width=2)
            canvas.create_line(cx,cy+cell_size*.15, cx+cell_size*.28,cy,
                               fill='#81c2ce', width=2)
            # A descending water-to-water edge becomes a visible waterfall.
            for p, q in transition_segments(corners, waterfall_mask(board, c)):
                # The drop is equal to the neighbouring tactical elevation.
                dx, dy = ((1, 0) if (p, q) == (east, south) else (0, 1))
                drop = (tile.height - board.tile((c[0]+dx,c[1]+dy)).height)*geo.step
                canvas.create_polygon(*_flatten(
                    (p,q,(q[0],q[1]+drop),(p[0],p[1]+drop))),
                    fill='#71b3cc', outline='#acdfe6', width=1)
                canvas.create_line((p[0]*.65+q[0]*.35), (p[1]*.65+q[1]*.35),
                                   (p[0]*.65+q[0]*.35), (p[1]*.65+q[1]*.35+drop),
                                   fill='#e2f7ef', width=max(1,cell_size//24))
        elif surface in ('bridge', 'cobble', 'stone') and layers.get('Terrain', True):
            for fraction in (-.35, 0, .35):
                px = cx + fraction*cell_size
                canvas.create_line(px-cell_size*.15,cy+cell_size*.2,
                                   px+cell_size*.15,cy-cell_size*.2,
                                   fill='#918b7d', width=1)
            if surface == 'bridge':
                # Rails follow the local channel direction, even on a rotated river.
                for p, q in bridge_rails(corners, bridge_axis(board, c)):
                    canvas.create_line(*p, *q,fill='#73604b',width=max(3,cell_size//10))
                    raise_by = max(5, cell_size//7)
                    canvas.create_line(p[0],p[1]-raise_by,q[0],q[1]-raise_by,
                                       fill='#ead6aa',width=max(2,cell_size//13))
                    for r in (p,q):
                        canvas.create_line(r[0],r[1],r[0],r[1]-raise_by,
                                           fill='#a69070',width=max(2,cell_size//15))
        if c in deploy and layers.get('Déploiement', True):
            canvas.create_polygon(*_flatten(corners), outline='#3b9ec0', fill='',
                                  width=3)
        if c in goals and layers.get('Objectifs', True):
            canvas.create_oval(cx-8, cy-6, cx+8, cy+6, fill='#eec65a', outline='')
        if c in reachable:
            canvas.create_polygon(*_flatten(corners), outline='#25a885', fill='',
                                  width=2, tags='iso_reachable')
        if c in threats:
            kind = threats[c]
            canvas.create_polygon(*_flatten(corners),
                                  outline=danger_colors[kind], fill='', width=3,
                                  dash=(5, 3) if kind == 'charge' else (2, 3),
                                  tags=('iso_danger', 'iso_danger_' + kind))
        if layers.get('Décors', True) and tile.feature:
            sprite = (prop_atlas.sprite(tile.feature, cell_size)
                      if prop_atlas is not None else None)
            if sprite is not None:
                canvas.create_image(cx, cy + cell_size*18/54, image=sprite,
                                    anchor='s', tags='decor_sprite')
            else:
                _draw_feature(canvas, tile.feature, cx, cy, cell_size)
        if layers.get('Objets', True):
            for obj in objects.get(c, ()):
                canvas.create_rectangle(cx-9,cy-18,cx+9,cy-4,
                                        fill='#9264ab',outline='#3d2554')
                canvas.create_text(cx,cy-22,text=obj['kind'][:4],font=('TkDefaultFont',8))
        if layers.get('Unités', True):
            for actor_index, actor in actors.get(c, ()):
                # MotionDirector feeds fractional positions, not tactical
                # moves. Do not change the board cell used for game logic.
                ax, ay = visual_center(geo, actor, poses)
                actor_tags = ('iso_actor', 'iso_actor_unit_' + str(actor_index))
                color = '#3b82c6' if actor.team == 'player' else '#ca6654'
                if not actor.alive:
                    color = '#888d94'
                active = actor.id == active_id
                photo = None
                if actor_atlas is not None and actor.alive:
                    from .iso_actor_atlas import actor_direction, actor_frame, actor_style
                    pose = (poses or {}).get(actor.id)
                    photo = actor_atlas.sprite(actor_style(actor),
                                              actor_direction(actor, pose),
                                              actor_frame(pose), cell_size)
                if photo is not None:
                    # The avatar foot (lower image edge) follows the SAME
                    # interpolated cell projection as the legacy oval.
                    canvas.create_image(ax, ay+cell_size*5/54, image=photo,
                                        anchor='s', tags=actor_tags + ('iso_actor_sprite',))
                    if active:
                        canvas.create_oval(ax-12, ay-6, ax+12, ay+5,
                                          outline='#ffe78a', width=2,
                                          tags=actor_tags)
                else:
                    canvas.create_oval(ax-10,ay-24,ax+10,ay-5,fill=color,
                                       outline='#ffe78a' if active else '#323441',
                                       width=3 if active else 1, tags=actor_tags)
                canvas.create_text(ax,ay-30,text=actor.name[:6],
                                   font=('TkDefaultFont',8,'bold'),tags=actor_tags)
                if active_id is not None:
                    canvas.create_text(ax,ay+2,text=f'{actor.hp} PV',
                                       font=('TkDefaultFont',8,'bold'),
                                       fill='#ffffff',tags=actor_tags)
        if c in selected_tiles:
            canvas.create_polygon(*_flatten(corners),outline='#23689e',fill='',width=3,
                                  tags='selection')
        if c == selected_cell:
            canvas.create_polygon(*_flatten(corners),outline='#2361ff',fill='',width=3,
                                  tags='selection')
    # Derive roof/facade overlays from intact 3.7.12 stamps. No new content
    # fields, no rendered logic in the tactical simulation or battle engine.
    from .iso_architecture import draw_architecture
    draw_architecture(canvas, geo, board, units, selected_cell, layers,
                      atlas=building_atlas, scenery_atlas=fortification_atlas,
                      poses=poses)
    return geo


def _draw_feature(canvas, feature, cx, cy, size):
    if not feature:
        return
    s = size / 54
    if feature == 'tree':
        canvas.create_line(cx,cy-3*s,cx,cy-48*s,fill='#745337',width=max(2,int(7*s)))
        for dx, dy, r in ((-12,-47,19),(10,-52,18),(0,-64,21)):
            canvas.create_oval(cx+(dx-r)*s,cy+(dy-r)*s,
                               cx+(dx+r)*s,cy+(dy+r)*s,
                               fill='#668456',outline='#415f42',width=2)
    elif feature == 'bush':
        for dx, dy in ((-11,-7),(0,-15),(10,-7)):
            canvas.create_oval(cx+(dx-11)*s,cy+(dy-10)*s,
                               cx+(dx+11)*s,cy+(dy+10)*s,
                               fill='#78945d',outline='#557049')
    elif feature == 'boulder':
        canvas.create_polygon(cx-16*s,cy-2*s,cx-13*s,cy-19*s,
                              cx+4*s,cy-25*s,cx+18*s,cy-10*s,cx+13*s,cy+4*s,
                              fill='#9c9c8c',outline='#666c63')
    elif feature in ('stone_wall', 'ruin'):
        canvas.create_polygon(cx-18*s,cy-4*s,cx-18*s,cy-29*s,
                              cx,cy-38*s,cx+17*s,cy-28*s,cx+17*s,cy-5*s,
                              fill='#c0b29b',outline='#6e6a61')
        canvas.create_line(cx-18*s,cy-16*s,cx+17*s,cy-16*s,fill='#877d6d')
        if feature == 'ruin':
            canvas.create_polygon(cx+4*s,cy-37*s,cx+18*s,cy-33*s,
                                  cx+18*s,cy-23*s,cx+8*s,cy-26*s,
                                  fill=SURFACE_COLORS['grass'],outline='#817566')
    elif feature == 'crate':
        canvas.create_rectangle(cx-12*s,cy-23*s,cx+12*s,cy-3*s,
                                fill='#b58e59',outline='#694a30',width=2)
        canvas.create_line(cx-12*s,cy-23*s,cx+12*s,cy-3*s,fill='#765332',width=2)
    elif feature == 'lantern':
        canvas.create_line(cx,cy,cx,cy-54*s,fill='#654d35',width=max(2,int(4*s)))
        canvas.create_rectangle(cx-6*s,cy-53*s,cx+6*s,cy-39*s,
                                fill='#efca73',outline='#63523e')
    elif feature == 'stairs':
        for i in range(4):
            canvas.create_line(cx-14*s+i*3*s,cy+8*s-i*5*s,
                               cx+8*s+i*3*s,cy-5*s-i*5*s,
                               fill='#efdfbd',width=max(1,int(3*s)))

    elif feature == 'arch':
        canvas.create_rectangle(cx-20*s,cy-44*s,cx-10*s,cy,
                                fill='#c0b29b',outline='#6e6a61')
        canvas.create_rectangle(cx+10*s,cy-44*s,cx+20*s,cy,
                                fill='#c0b29b',outline='#6e6a61')
        canvas.create_arc(cx-21*s,cy-71*s,cx+21*s,cy-20*s,
                          start=0,extent=180,style='arc',
                          outline='#c0b29b',width=max(3,int(10*s)))
    elif feature == 'fence':
        for dx in (-18,0,18):
            canvas.create_line(cx+dx*s,cy,cx+dx*s,cy-25*s,
                               fill='#8d6e45',width=max(2,int(4*s)))
        for dy in (8,18):
            canvas.create_line(cx-19*s,cy-dy*s,cx+19*s,cy-dy*s,
                               fill='#af8153',width=max(2,int(3*s)))
    elif feature == 'reeds':
        for i in range(7):
            dx=(i-3)*5
            canvas.create_line(cx+dx*s,cy,cx+(dx+3-i)*s,cy-(23+i%3*6)*s,
                               fill='#739357',width=max(1,int(2*s)))
    elif feature == 'pillar':
        canvas.create_rectangle(cx-9*s,cy-52*s,cx+9*s,cy-3*s,
                                fill='#b7a992',outline='#777267')
        canvas.create_rectangle(cx-13*s,cy-56*s,cx+13*s,cy-50*s,
                                fill='#d5c4a7',outline='#777267')
