"""Render narrative exploration through the shared 2.5D terrain/actor pipeline.

Exploration remains owned by GameSession; this module only builds a transient
visual Board for projection, never a tactical mission or a save payload.
"""
from .iso_actor_atlas import IsoActorAtlas
from .iso_environment_atlas import IsoEnvironmentAtlas
from .iso_map import IsoGeometry, IsoTerrainAtlas, render_isometric
from .iso_props import IsoPropAtlas
from .model import Board, Mission, Tile, Unit


# Exploration uses the same scalable 2.5D tiles as tactical battles.
CELL_SIZE = 48
MIN_CELL_SIZE = 20
MAX_CELL_SIZE = 96
ZOOM_STEP = 8


def exploration_visual_board(stage):
    """Convert the existing narrative grid into presentation-only terrain."""
    blocked = {tuple(cell) for cell in stage["blocked"]}
    theme = stage["theme"]
    tiles = {}
    for y in range(stage["height"]):
        for x in range(stage["width"]):
            cell = (x, y)
            solid = cell in blocked
            if solid:
                surface = "stone" if theme in ("village", "stone") else "rock"
                feature = "ruin" if theme == "village" else "boulder"
            elif theme == "fields":
                surface = "dirt" if y == 3 and x in (1, 2, 3) else "grass"
                feature = "reeds" if (x * 3 + y) % 4 == 0 else ""
            elif theme == "village":
                surface = "cobble" if (x + y) % 4 == 0 else "dirt"
                feature = ("ruin" if cell in {(2, 1), (5, 2), (7, 4)}
                           else "")
            elif theme == "forest":
                surface = "grass"
                feature = "tree" if (x * 3 + y) % 5 == 0 else ""
            else:
                surface = "stone" if (x + y) % 3 else "cobble"
                feature = ""
            tiles[cell] = Tile(blocked=solid, surface=surface, feature=feature)
    return Board(stage["width"], stage["height"], tiles)


def exploration_iso_shift(geometry, viewport):
    """Center a 2.5D stage without changing its logical grid coordinates."""
    return ((viewport[0] - geometry.width) / 2,
            (viewport[1] - geometry.height) / 2)


def exploration_iso_pick(geometry, shift, x, y):
    """Hit-test the same diamond geometry used by the Studio and Player."""
    return geometry.hit_test(x - shift[0], y - shift[1])


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

    def __init__(self, canvas, *, viewport=(690, 495),
                 cell_size=CELL_SIZE, pan=(0, 0)):
        self.canvas = canvas
        self.viewport = viewport
        self.cell_size = cell_size
        self.pan = pan
        self.board = None
        self.terrain = IsoTerrainAtlas(canvas)
        self.props = IsoPropAtlas(canvas)
        self.environment = IsoEnvironmentAtlas(canvas)
        self.actors = IsoActorAtlas(canvas)
        self.geometry = None
        self.shift = (0, 0)

    def draw(self, stage):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width > 1 and height > 1:
            self.viewport = (width, height)
        board = exploration_visual_board(stage)
        self.board = board
        # This ephemeral Mission is for the renderer only. It never enters
        # Battle, campaign progression, serialization or the command bus.
        scene = Mission("exploration_visual", stage["title"], board, [])
        hero = Unit("jeanne", "Jeanne", "player", tuple(stage["position"]))
        self.canvas.configure(background="#22372f")
        self.geometry = render_isometric(
            self.canvas, board, scene, [hero], cell_size=self.cell_size,
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

        # Read-only story overlays: do not turn hotspots/civilians into
        # tactical units or change their movement, deadlines or rewards.
        for point in stage["interactions"]:
            cx, cy = self._center(point["pos"])
            color = ("#79bea2" if point["visited"] else
                     "#87bde2" if point["exit"] else "#e1c878")
            self.canvas.create_oval(cx - 11, cy - 28, cx + 11, cy - 6,
                                    fill=color, outline="#17232b", width=2,
                                    tags=("exploration_hotspot",))
            self.canvas.create_text(cx, cy - 17,
                                    text="✓" if point["visited"] else "?",
                                    fill="#17232b", font=("TkDefaultFont", 11, "bold"),
                                    tags=("exploration_hotspot",))
            self.canvas.create_text(cx, cy + 14, text=point["title"][:14],
                                    fill="#fff3c8", font=("TkDefaultFont", 8, "bold"),
                                    tags=("exploration_hotspot",))
        for actor in stage.get("actors", ()):
            if actor["status"] == "rescued":
                continue
            cx, cy = self._center(actor["pos"])
            color = ("#82919a" if actor["status"] == "lost" else
                     "#f8c16f" if actor["kind"] == "civilian" else "#c5a6db")
            self.canvas.create_oval(cx - 10, cy - 26, cx + 10, cy - 6,
                                    fill=color, outline="#172d36", width=2,
                                    tags=("exploration_npc",))
            self.canvas.create_text(cx, cy - 16, text=actor["name"][:1],
                                    fill="#24302b", font=("TkDefaultFont", 9, "bold"),
                                    tags=("exploration_npc",))
            self.canvas.create_text(cx, cy + 15, text=actor["name"][:12],
                                    fill="#fff6dc", font=("TkDefaultFont", 8, "bold"),
                                    tags=("exploration_npc",))
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
        self.draw(stage)
        return True

    def pan_by(self, dx, dy):
        """Pan the view without recalculating gameplay or rebuilding sprites."""
        self.pan = (self.pan[0] + dx, self.pan[1] + dy)
        self.shift = (self.shift[0] + dx, self.shift[1] + dy)
        self.canvas.move("all", dx, dy)

    def recenter(self, stage):
        self.cell_size = CELL_SIZE
        self.pan = (0, 0)
        self.draw(stage)
