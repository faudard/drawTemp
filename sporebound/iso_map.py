"""Pure-coordinate isometric map view for the mission authoring canvas.

This is an editor visualization; the tactical board and all pathfinding remain
orthogonal. Geometry and hit-testing work without importing tkinter.
"""
from dataclasses import dataclass

SURFACES = frozenset({'grass', 'dirt', 'stone', 'cobble', 'sand',
                      'rock', 'water', 'bridge'})
FEATURES = frozenset({'', 'tree', 'bush', 'boulder', 'ruin', 'crate',
                      'lantern', 'stairs', 'stone_wall'})
SURFACE_COLORS = {
    'grass': '#9aa66c', 'dirt': '#c6a875', 'stone': '#aca69a',
    'cobble': '#c6b9a0', 'sand': '#dec897', 'rock': '#8e978d',
    'water': '#4d92ac', 'bridge': '#c5b496',
}


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
        self.origin_y = self.max_height * self.step + self.cell_size + 40
        self.width = (self.board.width + self.board.height + 3) * self.half_width + 72
        self.height = ((self.board.width + self.board.height + 3) *
                       self.half_height + self.max_height * self.step + 120)

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
        for cell in sorted(self.board.cells(), key=lambda c: (sum(c), c[0]), reverse=True):
            cx, cy = self.center(cell)
            if (abs(px-cx) / self.half_width +
                    abs(py-cy) / self.half_height <= 1):
                return cell
        return None


def render_isometric(canvas, board, mission, units, *, cell_size, layers,
                     selected_cell, selected_tiles, reachable=()):
    """Draw walkable 2.5D blocks, water, bridges and decorative props on Tk Canvas."""
    geo = IsoGeometry(board, cell_size)
    canvas.delete('all')
    canvas.configure(scrollregion=(0, 0, geo.width, geo.height))
    goals = set(mission.goal)
    deploy = {tuple(c) for z in mission.deployment for c in z['cells']}
    actors = {}
    for actor in units:
        actors.setdefault(tuple(actor.pos), []).append(actor)
    objects = {}
    for obj in mission.objects:
        objects.setdefault(tuple(obj['pos']), []).append(obj)
    reachable = set(reachable)

    for c in sorted(board.cells(), key=lambda cell: (sum(cell), cell[0])):
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
        if surface == 'water' and layers.get('Terrain', True):
            # Local ripples; the low and high banks are naturally defined by
            # adjacent surface boundaries and the relief geometry.
            canvas.create_line(cx-cell_size*.28,cy-2, cx,cy-2-cell_size*.13,
                               fill='#b3dadd', width=2)
            canvas.create_line(cx,cy+cell_size*.15, cx+cell_size*.28,cy,
                               fill='#81c2ce', width=2)
        elif surface in ('bridge', 'cobble', 'stone') and layers.get('Terrain', True):
            for fraction in (-.35, 0, .35):
                px = cx + fraction*cell_size
                canvas.create_line(px-cell_size*.15,cy+cell_size*.2,
                                   px+cell_size*.15,cy-cell_size*.2,
                                   fill='#918b7d', width=1)
            if surface == 'bridge':
                canvas.create_line(*west, *north, fill='#f1dfb8', width=3)
                canvas.create_line(*south, *east, fill='#766655', width=3)
        if c in deploy and layers.get('Déploiement', True):
            canvas.create_polygon(*_flatten(corners), outline='#3b9ec0', fill='',
                                  width=3)
        if c in goals and layers.get('Objectifs', True):
            canvas.create_oval(cx-8, cy-6, cx+8, cy+6, fill='#eec65a', outline='')
        if c in reachable:
            canvas.create_polygon(*_flatten(corners), outline='#25a885', fill='',
                                  width=2)
        if layers.get('Décors', True):
            _draw_feature(canvas, tile.feature, cx, cy, cell_size)
        if layers.get('Objets', True):
            for obj in objects.get(c, ()):
                canvas.create_rectangle(cx-9,cy-18,cx+9,cy-4,
                                        fill='#9264ab',outline='#3d2554')
                canvas.create_text(cx,cy-22,text=obj['kind'][:4],font=('TkDefaultFont',8))
        if layers.get('Unités', True):
            for actor in actors.get(c, ()):
                color = '#3b82c6' if actor.team == 'player' else '#ca6654'
                canvas.create_oval(cx-10,cy-24,cx+10,cy-5,fill=color,outline='#323441')
                canvas.create_text(cx,cy-28,text=actor.name[:6],
                                   font=('TkDefaultFont',8,'bold'))
        if c in selected_tiles:
            canvas.create_polygon(*_flatten(corners),outline='#23689e',fill='',width=3,
                                  tags='selection')
        if c == selected_cell:
            canvas.create_polygon(*_flatten(corners),outline='#2361ff',fill='',width=3,
                                  tags='selection')
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
