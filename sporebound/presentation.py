"""Read-only projections for the headless tactical and strategic engines.

Renderers consume frames; they never decide moves, targets or damage.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy

from .model import RuleError


@dataclass(frozen=True)
class Camera:
    """Grid-to-viewport transform, including anchored zoom and pan."""
    cell_size: int = 48
    offset_x: float = 0.0
    offset_y: float = 0.0

    def __post_init__(self):
        if not 16 <= self.cell_size <= 128:
            raise ValueError("Cell size must be 16..128")

    def screen_to_cell(self, x, y):
        return (int((x - self.offset_x) // self.cell_size),
                int((y - self.offset_y) // self.cell_size))

    def cell_to_screen(self, cell):
        return (self.offset_x + cell[0] * self.cell_size,
                self.offset_y + cell[1] * self.cell_size)

    def zoomed(self, steps, anchor=(0, 0)):
        size = max(16, min(128, self.cell_size + 8 * steps))
        cell_x = (anchor[0] - self.offset_x) / self.cell_size
        cell_y = (anchor[1] - self.offset_y) / self.cell_size
        return Camera(size, anchor[0] - cell_x * size, anchor[1] - cell_y * size)

    def panned(self, dx, dy):
        return Camera(self.cell_size, self.offset_x + dx, self.offset_y + dy)


@dataclass(frozen=True)
class TileView:
    pos: tuple[int, int]
    height: int
    blocked: bool
    hazard: int
    cover: int


@dataclass(frozen=True)
class ActorView:
    id: str
    name: str
    team: str
    pos: tuple[int, int]
    footprint: tuple[int, int]
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    alive: bool
    active: bool
    statuses: tuple[str, ...]


@dataclass(frozen=True)
class ObjectView:
    id: str
    kind: str
    pos: tuple[int, int]
    opened: bool


@dataclass(frozen=True)
class BattleFrame:
    mission: str
    width: int
    height: int
    tick: int
    active_id: str | None
    deploying: bool
    result: str | None
    tiles: tuple[TileView, ...]
    actors: tuple[ActorView, ...]
    objects: tuple[ObjectView, ...]
    selected: tuple[int, int] | None
    reachable: tuple[tuple[int, int], ...]
    forecast: tuple[dict, ...]
    events: tuple[dict, ...]


@dataclass(frozen=True)
class FrontView:
    id: str
    mission: str
    doctrine: str
    status: str
    strength: int
    opposition: int
    focused: bool


@dataclass(frozen=True)
class StrategyFrame:
    turn: int
    focused: str
    fronts: tuple[FrontView, ...]
    events: tuple[dict, ...]


def battle_frame(battle, selected=None, skill=None):
    """Take an engine-owned frame without modifying Battle or advancing RNG."""
    if battle is None:
        return None
    board = battle.board
    selected = tuple(selected) if selected is not None else None
    reachable = ()
    forecast = ()
    active = battle.active
    if not battle.deploying and active and active.team == "player" and not battle.result:
        if not active.moved:
            reachable = tuple(sorted(battle.reachable(active)))
        if skill and selected is not None:
            try:
                forecast = tuple(deepcopy(battle.forecast(skill, selected, active)))
            except RuleError:
                pass
    return BattleFrame(
        mission=battle.mission.name, width=board.width, height=board.height,
        tick=battle.tick, active_id=battle.active_id,
        deploying=battle.deploying, result=battle.result,
        tiles=tuple(TileView(cell, tile.height, tile.blocked, tile.hazard, tile.cover)
                    for cell in board.cells() for tile in (board.tile(cell),)),
        actors=tuple(ActorView(u.id, u.name, u.team, tuple(u.pos),
                               tuple(u.footprint), u.hp, u.max_hp, u.mp,
                               u.max_mp, u.alive, u.id == battle.active_id,
                               tuple(sorted(u.statuses))) for u in battle.units),
        objects=tuple(ObjectView(o["id"], o["kind"], tuple(o["pos"]),
                                 bool(o.get("open", False))) for o in battle.mission.objects),
        selected=selected, reachable=reachable, forecast=forecast,
        events=tuple(deepcopy(battle.events[-30:])))


def strategy_frame(fronts):
    if fronts is None:
        return None
    timeline = fronts.timeline
    return StrategyFrame(
        turn=timeline.turn, focused=timeline.focused,
        fronts=tuple(
            FrontView(name, fronts.missions[name], row["doctrine"],
                      fronts.battles[name].result if row["status"] == "active"
                      and fronts.battles[name].result is not None else row["status"],
                      row["strength"], row["opposition"],
                      name == timeline.focused)
            for name, row in sorted(timeline.fronts.items())),
        events=tuple(deepcopy(timeline.events[-40:])))
