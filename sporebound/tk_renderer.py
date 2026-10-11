"""Tk Canvas 2D/2.5D renderer consuming only immutable presentation frames.

Importing this module is display-free. All tactical rules remain headless.
"""
from pathlib import Path

from .model import RuleError
from .visual_motion import animation_sprite_id


class CanvasRenderer:
    def __init__(self, canvas, *, registry=None, asset_root=None):
        self.canvas = canvas
        self.registry = registry
        self.asset_root = Path(asset_root) if asset_root is not None else None
        self._images = {}
        self._missing = set()

    def _photo(self, asset_id):
        if self.registry is None or self.asset_root is None:
            return None
        if asset_id in self._images:
            return self._images[asset_id]
        if asset_id in self._missing:
            return None
        try:
            import tkinter as tk
            path = self.registry.resolve(asset_id, self.asset_root)
            self._images[asset_id] = tk.PhotoImage(file=str(path), master=self.canvas)
            return self._images[asset_id]
        except (ImportError, RuleError, OSError, RuntimeError, ValueError, tk.TclError):
            self._missing.add(asset_id)
            return None

    def image(self, kind, slot):
        """Resolve a static image binding, falling back to vector geometry."""
        if self.registry is None:
            return None
        try:
            spec = self.registry.binding(kind, slot)
            return self._photo(spec["id"]) if spec else None
        except (RuleError, ValueError):
            return None

    def animates_when_idle(self, frame):
        if self.registry is None or frame is None:
            return False
        for actor in frame.actors:
            for slot in (f"{actor.id}_idle", f"{actor.team}_idle",
                         f"{actor.id}_idle_south", f"{actor.team}_idle_south"):
                spec = self.registry.binding("animation", slot)
                if spec and spec["loop"] and len(spec["frames"]) > 1:
                    return True
        return False

    def draw(self, frame, camera, *, poses=None, elapsed_ms=0, clock_ms=0):
        canvas = self.canvas
        canvas.delete("all")
        if frame is None:
            return
        cell = camera.cell_size
        selected = frame.selected
        reachable = set(frame.reachable)
        # Source-of-truth engine telegraphs; distinguish scheduled and possible.
        priority = {"hazard": 0, "charge": 1, "prepared": 2, "cast": 3}
        threat_style = {"hazard": "#fd766f", "charge": "#f5ae60",
                        "prepared": "#f5d07a", "cast": "#c69df8"}
        threats = {}
        for threat in getattr(frame, "danger", ()):
            pos = tuple(threat["cell"])
            if pos not in threats or priority[threat["kind"]] > priority[threats[pos]]:
                threats[pos] = threat["kind"]
        # Tile height, cover, danger and blockage are presentation only.
        for tile in frame.tiles:
            x, y = camera.cell_to_screen(tile.pos)
            color = ("#45546a" if tile.blocked else "#7c4433" if tile.hazard
                     else "#446b5b" if tile.height else "#26384b")
            canvas.create_rectangle(x, y, x + cell, y + cell,
                                    fill=color, outline="#405166")
            if tile.height:
                h = min(cell // 3, tile.height * 3)
                canvas.create_rectangle(x + 2, y + cell - h - 2,
                                        x + cell - 2, y + cell - 2,
                                        fill="#759b87", outline="")
            if tile.cover:
                canvas.create_line(x + 4, y + 5, x + cell - 4, y + 5,
                                   fill="#e2ce91", width=2)
            if tile.pos in reachable:
                canvas.create_rectangle(x + 4, y + 4, x + cell - 4, y + cell - 4,
                                        outline="#58d6cd", width=2, dash=(3, 3))
            if tile.pos in threats:
                kind = threats[tile.pos]
                canvas.create_rectangle(x + 6, y + 6, x + cell - 6, y + cell - 6,
                                        outline=threat_style[kind], width=3,
                                        dash=(5, 3) if kind == "charge" else (2, 3))
            if selected == tile.pos:
                canvas.create_rectangle(x + 2, y + 2, x + cell - 2, y + cell - 2,
                                        outline="#ffe78a", width=3)
        for obj in frame.objects:
            x, y = camera.cell_to_screen(obj.pos)
            canvas.create_rectangle(x + cell // 4, y + cell // 4,
                                    x + 3 * cell // 4, y + 3 * cell // 4,
                                    fill="#47b9a4" if obj.opened else "#d99554",
                                    outline="#101b2d", width=2)
            canvas.create_text(x + cell / 2, y + cell - 5,
                               text=obj.id[:10], fill="#ffffff",
                               font=("TkDefaultFont", max(7, cell // 7)))
        for actor in frame.actors:
            pose = poses.get(actor.id) if poses is not None else None
            x, y = camera.cell_to_screen((pose.x, pose.y) if pose else actor.pos)
            action = pose.action if pose else ("defeat" if not actor.alive else "idle")
            direction = pose.direction if pose else "south"
            width, height = actor.footprint
            w, h = cell * width, cell * height
            if actor.active:
                canvas.create_rectangle(x + 2, y + 2, x + w - 2, y + h - 2,
                                        outline="#facc15", width=3)
            animated_id = animation_sprite_id(
                self.registry, actor.id, actor.team, action, direction,
                clock_ms if action == "idle" else elapsed_ms)
            sprite = (self._photo(animated_id) if animated_id else None)
            sprite = sprite or self.image("sprite", actor.id) or self.image("sprite", actor.team)
            if sprite is not None and width == height == 1:
                canvas.create_image(x + w / 2, y + h / 2, image=sprite)
            else:
                color = "#648cdb" if actor.team == "player" else "#d26b7b"
                if action == "hit":
                    color = "#f8a56a"
                if not actor.alive:
                    color = "#697383"
                canvas.create_oval(x + 7, y + 7, x + w - 7, y + h - 8,
                                   fill=color, outline="#1c293a", width=2)
                canvas.create_text(x + w / 2, y + h / 2,
                                   text=actor.name[:max(2, cell // 9)],
                                   fill="#ffffff", font=("TkDefaultFont", max(9, cell // 5), "bold"))
            # Health bar is a read-only visual of actor data.
            pct = max(0, actor.hp) / max(1, actor.max_hp)
            canvas.create_rectangle(x + 5, y + h - 7, x + w - 5, y + h - 3,
                                    fill="#121a27", outline="")
            canvas.create_rectangle(x + 5, y + h - 7,
                                    x + 5 + (w - 10) * pct, y + h - 3,
                                    fill="#66d48b" if actor.team == "player" else "#ffa08c",
                                    outline="")
        if frame.result:
            canvas.create_text(camera.offset_x + frame.width * cell / 2,
                               camera.offset_y + 14,
                               text=frame.result.upper(), fill="#ffe38d",
                               font=("TkDefaultFont", 17, "bold"))

    def dispose(self):
        self._images.clear()
        self._missing.clear()
