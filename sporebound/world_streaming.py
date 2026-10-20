"""R54.A: opt-in, replayable world-cell state and cancellable LRU loader.

Scene transitions remain canonical R25 GameSession commands. Worker results
are transient presentation data and never mutate saved gameplay.
"""
from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from copy import deepcopy
import json

from .model import RuleError, require

EXTENSION = "org.drawtemp.streaming"
VERSION = 1
MAX_EVENTS = 2048
MAX_HISTORY = 4096
MAX_CELL_BYTES = 2 * 1024 * 1024


def _id(value):
    return (type(value) is str and 1 <= len(value) <= 64 and
            all(ch.isascii() and (ch.isalnum() or ch in "_-") for ch in value))


def validate_world_streaming(spec, project):
    """Verify a finite symmetric cell graph against authored R25 scene links."""
    require(type(spec) is dict and set(spec) ==
            {"version", "start", "max_cache_bytes", "cells"},
            "Invalid R54 streaming manifest")
    require(type(spec["version"]) is int and spec["version"] == VERSION,
            "Unsupported R54 version")
    require(type(spec["max_cache_bytes"]) is int and
            1024 <= spec["max_cache_bytes"] <= 32 * 1024 * 1024,
            "Invalid R54 memory budget")
    require(type(spec["cells"]) is list and 1 <= len(spec["cells"]) <= 256,
            "R54 requires 1..256 cells")
    require(bool(project.scene_routes) and
            project.scene_routes.get("version") == 1,
            "R54 requires R25 canonical routes")
    cells, scenes, entities = {}, set(), set()
    for cell in spec["cells"]:
        require(type(cell) is dict and set(cell) ==
                {"id", "region", "scene", "neighbors", "entities"},
                "Invalid R54 cell fields")
        ident = cell["id"]
        require(_id(ident) and ident not in cells and
                _id(cell["region"]) and _id(cell["scene"]) and
                cell["scene"] in project.exploration and
                cell["scene"] not in scenes,
                "Invalid/duplicate cell, region or canonical scene")
        require(type(cell["neighbors"]) is list and
                len(cell["neighbors"]) <= 8 and
                all(_id(n) and n != ident for n in cell["neighbors"]) and
                len(set(cell["neighbors"])) == len(cell["neighbors"]),
                "Invalid R54 neighbors")
        require(type(cell["entities"]) is list and
                len(cell["entities"]) <= 64, "Invalid R54 entity list")
        for entity in cell["entities"]:
            require(type(entity) is dict and set(entity) == {"id", "initial"}
                    and _id(entity["id"]) and _id(entity["initial"])
                    and entity["id"] not in entities,
                    "Duplicate or invalid R54 entity")
            entities.add(entity["id"])
        cells[ident] = cell
        scenes.add(cell["scene"])
    start = spec["start"]
    require(_id(start) and start in cells and
            cells[start]["scene"] == project.scene_routes["start"],
            "R54 start does not match R25 route start")
    links = {(link["source"], link["destination"])
             for link in project.scene_routes["links"]}
    for ident, cell in cells.items():
        for neighbor in cell["neighbors"]:
            require(neighbor in cells and
                    ident in cells[neighbor]["neighbors"] and
                    (cell["scene"], cells[neighbor]["scene"]) in links,
                    "R54 edge lacks symmetric R25 portals")
    reached, todo = {start}, [start]
    while todo:
        for adjacent in cells[todo.pop()]["neighbors"]:
            if adjacent not in reached:
                reached.add(adjacent)
                todo.append(adjacent)
    require(len(reached) == len(cells), "Disconnected R54 cells")
    return deepcopy(spec)


class WorldStreamState:
    """Persistent state: route-linked cell cursor and once-only entity events."""

    def __init__(self, spec, project):
        self.spec = validate_world_streaming(spec, project)
        self.cells = {c["id"]: c for c in self.spec["cells"]}
        self.scenes = {c["scene"]: c["id"] for c in self.spec["cells"]}
        self.initial = {e["id"]: e["initial"] for c in self.spec["cells"]
                        for e in c["entities"]}
        self.history = [self.spec["start"]]
        self.events = []
        self.entities = dict(self.initial)

    @property
    def current(self):
        return self.history[-1]

    def enter_scene(self, scene):
        target = self.scenes.get(scene)
        if target is None or target == self.current:
            return False
        require(target in self.cells[self.current]["neighbors"],
                "Non-adjacent R54 cell transition")
        require(len(self.history) < MAX_HISTORY, "R54 travel history full")
        self.history.append(target)
        return True

    def assert_scene(self, scene):
        target = self.scenes.get(scene)
        require(target is None or target == self.current,
                "R54 world cursor does not match R25 scene")

    def apply(self, event_id, entity_id, before, after):
        """Compare-and-swap with persistent idempotency; no reward duplication."""
        require(all(_id(v) for v in (event_id, entity_id, before, after))
                and before != after, "Invalid R54 world event")
        event = {"id": event_id, "entity": entity_id,
                 "before": before, "after": after}
        for previous in self.events:
            if previous["id"] == event_id:
                require(previous == event, "Conflicting R54 event replay")
                return False
        require(entity_id in self.entities and
                self.entities[entity_id] == before,
                "Unknown entity or stale R54 world change")
        require(len(self.events) < MAX_EVENTS, "R54 world event ledger full")
        self.events.append(event)
        self.entities[entity_id] = after
        return True

    def recording(self):
        return {"version": VERSION, "history": list(self.history),
                "events": deepcopy(self.events)}

    def restore(self, data):
        """Replay and validate complete checkpoint before mutating the live state."""
        require(type(data) is dict and set(data) ==
                {"version", "history", "events"} and
                type(data["version"]) is int and data["version"] == VERSION,
                "Malformed R54 checkpoint")
        history, events = data["history"], data["events"]
        require(type(history) is list and 1 <= len(history) <= MAX_HISTORY
                and history[0] == self.spec["start"],
                "Invalid R54 saved path")
        for previous, current in zip(history, history[1:]):
            require(type(current) is str and previous in self.cells and
                    current in self.cells[previous]["neighbors"],
                    "Disconnected R54 checkpoint route")
        require(type(events) is list and len(events) <= MAX_EVENTS,
                "Invalid R54 checkpoint event ledger")
        values, seen = dict(self.initial), set()
        for event in events:
            require(type(event) is dict and set(event) ==
                    {"id", "entity", "before", "after"},
                    "Malformed R54 checkpoint event")
            ident, entity = event["id"], event["entity"]
            require(_id(ident) and ident not in seen and _id(entity)
                    and entity in values and _id(event["before"])
                    and _id(event["after"]) and event["before"] != event["after"]
                    and values[entity] == event["before"],
                    "Invalid/duplicate/conflicting R54 world event")
            seen.add(ident)
            values[entity] = event["after"]
        self.history = list(history)
        self.events = deepcopy(events)
        self.entities = values

    def view(self):
        return {"current": self.current, "history": list(self.history),
                "entities": deepcopy(self.entities),
                "regions": {c["id"]: c["region"] for c in self.spec["cells"]}}


class WorldCellCache:
    """Single-caller cache API; trusted loaders run off-thread, never in Core.

    A cancelled ticket is dropped before any delayed completion can enter LRU.
    Cache eviction does not affect GameSession checkpoints or entity identity.
    """

    def __init__(self, spec, loader, *, workers=2):
        require(callable(loader) and type(workers) is int and 1 <= workers <= 4,
                "Invalid trusted R54 cell loader")
        require(type(spec) is dict and type(spec.get("cells")) is list and
                type(spec.get("max_cache_bytes")) is int,
                "Invalid cache specification")
        self.cells = {c["id"]: deepcopy(c) for c in spec["cells"]}
        self.limit = spec["max_cache_bytes"]
        require(len(self.cells) == len(spec["cells"]) and
                1024 <= self.limit <= 32 * 1024 * 1024,
                "Invalid R54 cache budget or duplicate cells")
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.loader = loader
        self.cache = OrderedDict()
        self.bytes = 0
        self.pending = {}
        self.sequence = 0
        self.closed = False

    def get(self, cell_id):
        require(cell_id in self.cells, "Unknown R54 cell")
        if cell_id not in self.cache:
            return None
        self.cache.move_to_end(cell_id)
        return deepcopy(self.cache[cell_id][0])

    def request(self, cell_id):
        require(not self.closed and cell_id in self.cells,
                "R54 cell cache closed or unknown")
        if cell_id in self.cache:
            self.cache.move_to_end(cell_id)
            return None
        for token, (ident, _) in self.pending.items():
            if ident == cell_id:
                return token
        require(len(self.pending) < 8, "R54 pending queue full")
        self.sequence += 1
        future = self.executor.submit(self.loader, deepcopy(self.cells[cell_id]))
        self.pending[self.sequence] = (cell_id, future)
        return self.sequence

    def cancel(self, token):
        task = self.pending.pop(token, None)
        if task is None:
            return False
        task[1].cancel()
        return True

    def resolve(self, token, *, timeout=None):
        """Resolve a ticket on the owner thread; 0 timeout means poll."""
        require(not self.closed and token in self.pending,
                "Cancelled/unknown R54 request")
        name, future = self.pending[token]
        try:
            result = future.result(timeout=timeout)
        except TimeoutError:
            return None
        except Exception as exc:
            self.pending.pop(token, None)
            raise RuleError("R54 cell loader failed") from exc
        self.pending.pop(token, None)
        try:
            encoded = json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 allow_nan=False, separators=(",", ":"))
            size = len(encoded.encode("utf-8"))
            require(0 < size <= min(MAX_CELL_BYTES, self.limit),
                    "R54 payload exceeds cache budget")
            value = json.loads(encoded)
        except (ValueError, TypeError, UnicodeError, OverflowError) as exc:
            raise RuleError("Invalid R54 cell payload") from exc
        while self.cache and self.bytes + size > self.limit:
            _, (_, old_size) = self.cache.popitem(last=False)
            self.bytes -= old_size
        self.cache[name] = (value, size)
        self.bytes += size
        return deepcopy(value)

    def stats(self):
        return {"loaded": list(self.cache), "pending": len(self.pending),
                "resident_bytes": self.bytes, "budget_bytes": self.limit}

    def close(self):
        self.closed = True
        for token in list(self.pending):
            self.cancel(token)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.cache.clear()
        self.bytes = 0
