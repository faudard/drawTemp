"""Tk Canvas 2D/2.5D renderer consuming only immutable presentation frames.

Importing this module is display-free. All tactical rules remain headless.
"""
from pathlib import Path

from .model import RuleError


class CanvasRenderer:
    def __init__(self, canvas, *, registry=None, asset_root=None):
        self.canvas = canvas
        self.registry = registry
        self.asset_root = Path(asset_root) if asset_root is not None else None
        self._images = {}

    def image(self, kind, slot):
        """Optional portable sprite/portrait binding with a safe vector fallback."""
        if self.registry is None or self.asset_root is None:
            return None
        try:
            spec = self.registry.binding(kind, slot)
            if spec is None:
                return None
            key = spec["id"]
            if key not in self._images:
                import tkinter as tk
                path = self.registry.resolve(key, self.asset_root)
                self._images[key] = tk.PhotoImage(file=str(path), master=self.canvas)
            return self._images[key]
        except (RuleError, OSError, RuntimeError, ValueError):
            return None

    def draw(self, frame, camera):
        canvas = self.canvas
        canvas.delete("all")
        if frame is None:
            return
        cell = camera.cell_size
        selected = frame.selected
        reachable = set(frame.reachable)
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
            x, y = camera.cell_to_screen(actor.pos)
            width, height = actor.footprint
            w, h = cell * width, cell * height
            if actor.active:
                canvas.create_rectangle(x + 2, y + 2, x + w - 2, y + h - 2,
                                        outline="#facc15", width=3)
            sprite = self.image("sprite", actor.id) or self.image("sprite", actor.team)
            if sprite is not None and width == height == 1:
                canvas.create_image(x + w / 2, y + h / 2, image=sprite)
            else:
                color = "#648cdb" if actor.team == "player" else "#d26b7b"
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
