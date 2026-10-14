"""Render narrative exploration through the shared 2.5D terrain/actor pipeline.

Exploration remains owned by GameSession; this module only builds a transient
visual Board for projection, never a tactical mission or a save payload.
"""
from .iso_actor_atlas import IsoActorAtlas
from .iso_environment_atlas import IsoEnvironmentAtlas
from .iso_map import IsoGeometry, IsoTerrainAtlas, render_isometric
from .iso_props import IsoPropAtlas
from .model import Board, Mission, Tile, Unit


CELL_SIZE = 28
MIN_CELL_SIZE = 20
MAX_CELL_SIZE = 96
ZOOM_STEP = 8


def exploration_visual_board(stage):
    """Paint narrative scenes without changing their pathfinding or save data.

    Deliberately deterministic: a redraw, resize or reopened save always
    produces the same scene. Terrain features are decorative, not blockers.
    """
    blocked = {tuple(cell) for cell in stage["blocked"]}
    occupied = {tuple(stage.get("position", (0, 0)))}
    occupied.update(tuple(point["pos"]) for point in stage.get("interactions", ()))
    occupied.update(tuple(actor["pos"]) for actor in stage.get("actors", ()))
    width, height, theme = stage["width"], stage["height"], stage["theme"]
    tiles = {}
    for y in range(height):
        for x in range(width):
            cell = (x, y)
            solid = cell in blocked
            edge = min(x, y, width - 1 - x, height - 1 - y)
            # Small variations create continuous, recognizable landscape
            # shapes rather than random, disconnected chessboard tiles.
            variation = (x * 17 + y * 29 + x * y * 7) % 19
            if solid:
                surface = "stone" if theme in ("village", "stone") else "rock"
                feature = "ruin" if theme == "village" else "boulder"
            elif theme == "fields":
                trail = (y == min(3, height - 1) and 1 <= x < width - 1)
                surface = "dirt" if trail and cell not in occupied else "grass"
                feature = ("bush" if edge == 0 and variation in (0, 3, 7)
                           else "reeds" if variation in (2, 11, 13) else "")
            elif theme == "village":
                street = abs(y - (height // 2)) <= 1
                surface = ("cobble" if street and variation % 4 != 0
                           else "dirt" if variation % 5 else "stone")
                feature = ("ruin" if cell in {(2, 1), (5, 2), (7, 4)}
                           else "lantern" if edge > 0 and variation == 0
                           else "bush" if edge == 0 and variation in (3, 9)
                           else "")
            elif theme == "forest":
                surface = "grass" if variation != 0 else "dirt"
                feature = ("tree" if (edge == 0 or variation in (2, 5))
                           else "bush" if variation in (10, 12) else "")
            else:
                surface = "cobble" if variation in (1, 3, 5, 7) else "stone"
                feature = "boulder" if edge == 0 and variation == 4 else ""
            if cell in occupied and not solid:
                feature = ""  # Keep Jeanne, civilians and story goals visible.
            tiles[cell] = Tile(blocked=solid, surface=surface, feature=feature)
    return Board(width, height, tiles)


def exploration_visual_cast(stage):
    """Presentation-only extras drawn by the real isometric actor pipeline."""
    cast = [Unit("jeanne", "Jeanne", "player", tuple(stage["position"]))]
    for actor in stage.get("actors", ()):
        if actor["status"] != "active":
            continue
        cast.append(Unit(
            "story_" + str(actor["id"]), actor["name"], "player",
            tuple(actor["pos"])))
    return cast


def exploration_iso_shift(geometry, viewport):
    """Center a 2.5D stage without changing its logical grid coordinates."""
    return ((viewport[0] - geometry.width) / 2,
            (viewport[1] - geometry.height) / 2)


def exploration_iso_pick(geometry, shift, x, y):
    """Hit-test the same diamond geometry used by the Studio and Player."""
    return geometry.hit_test(x - shift[0], y - shift[1])


def exploration_iso_cell_size(stage, viewport):
    """Fit the small narrative map inside the available fullscreen viewport."""
    extent = max(1, stage["width"] + stage["height"])
    return max(CELL_SIZE, min(88, int(min(
        viewport[0] * .82 / extent,
        viewport[1] * 1.30 / extent))))


def anchored_exploration_zoom(board, old_size, new_size, viewport, pan, anchor):
    """Keep the hovered logical tile under the cursor during zoom.

    The camera is presentation-only: the board and saved player position are
    never scaled or rewritten.
    """
    before = IsoGeometry(board, old_size)
    after = IsoGeometry(board, new_size)
    old_shift = exploration_iso_shift(before, viewport)
    new_shift = exploration_iso_shift(after, viewport)
    current = (old_shift[0] + pan[0], old_shift[1] + pan[1])
    cell = exploration_iso_pick(before, current, *anchor)
    if cell is None:
        return pan
    bx, by = before.center(cell)
    ax, ay = after.center(cell)
    return (current[0] + bx - new_shift[0] - ax,
            current[1] + by - new_shift[1] - ay)


class IsoExplorationCanvas:
    """Disposable view adapter. Keep image atlases alive while Canvas exists."""

    def __init__(self, canvas, *, viewport=(690, 495), adaptive=False,
                 cell_size=None, pan=(0, 0)):
        self.canvas = canvas
        self.viewport = viewport
        self.adaptive = adaptive
        self.cell_size = cell_size
        self._manual_zoom = cell_size is not None
        self.pan = pan
        self.board = None
        self.terrain = IsoTerrainAtlas(canvas)
        self.props = IsoPropAtlas(canvas)
        self.environment = IsoEnvironmentAtlas(canvas)
        self.actors = IsoActorAtlas(canvas)
        self.geometry = None
        self.shift = (0, 0)

    def _paint_atmosphere(self, theme):
        """Quiet painted backdrop around the diamond, behind every sprite."""
        gradients = {
            "fields": ("#1d3431", "#426044"),
            "village": ("#302a2a", "#61463a"),
            "forest": ("#142c30", "#395747"),
            "stone": ("#252c35", "#4a4d52"),
        }
        top, bottom = gradients.get(theme, gradients["stone"])
        def rgb(value):
            return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        a, b = rgb(top), rgb(bottom)
        width, height = self.viewport
        for index in range(28):
            t = index / 27
            color = "#" + "".join(
                format(round(a[i] * (1 - t) + b[i] * t), "02x")
                for i in range(3))
            self.canvas.create_rectangle(
                0, height * index / 28, width, height * (index + 1) / 28 + 1,
                fill=color, outline="", tags=("exploration_atmosphere",))
        self.canvas.tag_lower("exploration_atmosphere")

    def _draw_story_markers(self, stage, size):
        """Gold/blue wayfinding symbols; actors are PNGs, not colored discs."""
        for point in stage["interactions"]:
            cx, cy = self._center(point["pos"])
            visited = point["visited"]
            color = ("#8ac7ad" if visited else
                     "#98c6d8" if point["exit"] else "#f4ca7f")
            tip_y = cy - max(24, size * .55)
            r = max(6, min(11, size * .14))
            # A hollow ground ring leaves the hand-painted terrain visible.
            self.canvas.create_oval(
                cx - r * 1.7, cy - r * .55, cx + r * 1.7, cy + r * .55,
                fill="", outline=color, width=2,
                tags=("exploration_hotspot",))
            self.canvas.create_polygon(
                cx, tip_y - r, cx + r, tip_y, cx, tip_y + r,
                cx - r, tip_y, fill="#243338", outline=color, width=2,
                tags=("exploration_hotspot",))
            self.canvas.create_text(
                cx, tip_y, text="✓" if visited else "!",
                fill=color, font=("Segoe UI", max(9, round(size * .17)), "bold"),
                tags=("exploration_hotspot",))
            label = point["title"][:22]
            self.canvas.create_text(
                cx + 1, cy + max(15, size * .28) + 1, text=label,
                fill="#192527", font=("Segoe UI", 9, "bold"),
                tags=("exploration_hotspot",))
            self.canvas.create_text(
                cx, cy + max(15, size * .28), text=label, fill="#fff0cd",
                font=("Segoe UI", 9, "bold"),
                tags=("exploration_hotspot",))
        for actor in stage.get("actors", ()):
            if actor["status"] == "rescued":
                continue
            cx, cy = self._center(actor["pos"])
            if actor["status"] == "lost":
                # An unresolved civilian is still locatable, but never a
                # living chibi unit or an invented tactical combatant.
                self.canvas.create_oval(
                    cx - 9, cy - 7, cx + 9, cy + 6,
                    fill="#53545a", outline="#a3a4a5", width=2,
                    tags=("exploration_npc",))
                self.canvas.create_text(
                    cx, cy - 18, text=actor["name"][:15],
                    fill="#d9cebf", font=("Segoe UI", 9),
                    tags=("exploration_npc",))
                continue
            tint = "#edbd77" if actor["kind"] == "civilian" else "#b0c7d9"
            self.canvas.create_oval(
                cx - 12, cy - 5, cx + 12, cy + 7,
                fill="", outline=tint, width=2,
                tags=("exploration_npc",))
        # A subtle hero locator; does not steal a cell from hit-testing.
        hx, hy = self._center(stage["position"])
        self.canvas.create_oval(
            hx - 16, hy - 7, hx + 16, hy + 8, fill="",
            outline="#f5d39b", width=2, tags=("exploration_hero_focus",))

    def draw(self, stage):
        board = exploration_visual_board(stage)
        self.board = board
        # This ephemeral Mission is for the renderer only. It never enters
        # Battle, campaign progression, serialization or the command bus.
        scene = Mission("exploration_visual", stage["title"], board, [])
        self.canvas.configure(background="#1d3431")
        size = (self.cell_size if self._manual_zoom else
                exploration_iso_cell_size(stage, self.viewport)
                if self.adaptive else CELL_SIZE)
        self.cell_size = size
        self.geometry = render_isometric(
            self.canvas, board, scene, exploration_visual_cast(stage),
            cell_size=size,
            layers={"Terrain": True, "Relief": True, "Décors": True,
                    "Bâtiments": False, "Toitures": False, "Unités": True,
                    "Objets": False, "Objectifs": False, "Déploiement": False,
                    "AutoBlend": True, "Ambiance": True},
            selected_cell=None, selected_tiles=(),
            active_id=None, atlas=self.terrain, prop_atlas=self.props,
            actor_atlas=self.actors, ambient_atlas=self.environment,
            omit_architecture=True, draw_selection=False)
        center = exploration_iso_shift(self.geometry, self.viewport)
        self.shift = (center[0] + self.pan[0], center[1] + self.pan[1])
        self.canvas.move("all", *self.shift)
        self._paint_atmosphere(stage["theme"])
        self._draw_story_markers(stage, size)
        return self.geometry

    def _center(self, cell):
        x, y = self.geometry.center(tuple(cell))
        return x + self.shift[0], y + self.shift[1]

    def hit_test(self, x, y):
        if self.geometry is None:
            return None
        return exploration_iso_pick(self.geometry, self.shift, x, y)

    def zoom_at(self, direction, stage, anchor=None):
        """Zoom around a tile, preserving selection and hotspot picking."""
        size = max(MIN_CELL_SIZE, min(MAX_CELL_SIZE,
                                      self.cell_size + direction * ZOOM_STEP))
        if size == self.cell_size:
            return False
        if anchor is None:
            anchor = (self.viewport[0] / 2, self.viewport[1] / 2)
        if self.board is not None:
            self.pan = anchored_exploration_zoom(
                self.board, self.cell_size, size, self.viewport, self.pan, anchor)
        self.cell_size = size
        self._manual_zoom = True
        self.canvas.delete("all")
        self.draw(stage)
        return True

    def pan_by(self, dx, dy):
        """Pan the view without recalculating gameplay or rebuilding sprites."""
        self.pan = (self.pan[0] + dx, self.pan[1] + dy)
        self.shift = (self.shift[0] + dx, self.shift[1] + dy)
        self.canvas.move("all", dx, dy)

    def recenter(self, stage):
        self.cell_size = None if self.adaptive else CELL_SIZE
        self._manual_zoom = False
        self.pan = (0, 0)
        self.canvas.delete("all")
        self.draw(stage)
