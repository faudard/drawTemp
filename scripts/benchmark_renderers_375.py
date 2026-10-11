#!/usr/bin/env python3
"""3.7.5 — compare optional display backends with identical Jeanne pixels.

Each invocation runs ONE backend in a fresh process. Output is machine-readable
JSON; no tactical state, live RNG, savegame or engine event is consumed.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
import tracemalloc
from pathlib import Path

ATLAS = Path(__file__).resolve().parents[1] / "sporebound/content/art/jeanne/jeanne_atlas.png"
WIDTH, HEIGHT = 800, 600
DIRECTIONS = ("south", "north", "east", "west")
ANIMATIONS = ("idle_0", "idle_1", "move_0", "move_1",
              "attack_0", "attack_1", "hit", "defeat")
CELL = 64


def positions(actors: int, tick: int, scale: int):
    """Deterministic coordinates, identical across all three backends."""
    width = WIDTH - CELL * scale
    height = HEIGHT - CELL * scale
    return tuple(((n * 47 + tick * 3) % (width + 1),
                  (n * 73 + tick * 2) % (height + 1))
                 for n in range(actors))


def quantile(values, percent):
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent
    lo, hi = int(index), min(len(ordered) - 1, int(index) + 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def setup_tk(scale, actors):
    import tkinter as tk
    window = tk.Tk()
    window.title("3.7.5 benchmark Tk")
    window.geometry(f"{WIDTH}x{HEIGHT}")
    canvas = tk.Canvas(window, width=WIDTH, height=HEIGHT, highlightthickness=0)
    canvas.pack()
    source = tk.PhotoImage(file=str(ATLAS), master=window)
    frame = tk.PhotoImage(master=window, width=CELL, height=CELL)
    frame.tk.call(str(frame), "copy", str(source),
                  "-from", 0, 0, CELL, CELL, "-to", 0, 0)
    if scale == 2:
        frame = frame.zoom(2, 2)
    window.update()

    def render(tick):
        canvas.delete("all")
        canvas.create_rectangle(0, 0, WIDTH, HEIGHT,
                                fill="#1c2b40", outline="")
        for x, y in positions(actors, tick, scale):
            canvas.create_image(x, y, image=frame, anchor="nw")
        window.update_idletasks()
        window.update()

    return render, window.destroy


def setup_pygame(scale, actors):
    import pygame  # Install with pip install pygame-ce
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("3.7.5 benchmark pygame-ce")
    atlas = pygame.image.load(str(ATLAS)).convert_alpha()
    sprite = atlas.subsurface((0, 0, CELL, CELL)).copy()
    if scale == 2:
        sprite = pygame.transform.scale(sprite, (CELL * 2, CELL * 2))

    def render(tick):
        pygame.event.pump()
        screen.fill((28, 43, 64))
        for x, y in positions(actors, tick, scale):
            screen.blit(sprite, (x, y))
        pygame.display.flip()

    return render, pygame.quit


def setup_qt(scale, actors):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])
    atlas = QPixmap(str(ATLAS))
    if atlas.isNull():
        raise RuntimeError("Unable to decode Jeanne atlas")
    sprite = atlas.copy(QRect(0, 0, CELL, CELL))
    if scale == 2:
        sprite = sprite.scaled(CELL * 2, CELL * 2)

    class Board(QWidget):
        tick = 0

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(28, 43, 64))
            for x, y in positions(actors, self.tick, scale):
                painter.drawPixmap(x, y, sprite)
            painter.end()

    board = Board()
    board.resize(WIDTH, HEIGHT)
    board.setWindowTitle("3.7.5 benchmark PySide6")
    board.show()
    app.processEvents()

    def render(tick):
        board.tick = tick
        board.repaint()  # Synchronous paint, rather than queue-only update.
        app.processEvents()

    return render, board.close


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("tk", "pygame", "qt"), default="tk")
    parser.add_argument("--actors", type=int, choices=(20, 80, 200), default=80)
    parser.add_argument("--scale", type=int, choices=(1, 2), default=1)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.frames < 20:
        parser.error("--frames must be >= 20")
    if not ATLAS.is_file():
        parser.error(f"Missing atlas: {ATLAS}")
    if args.dry_run:
        print(json.dumps({"backend": args.backend, "actors": args.actors,
                          "scale": args.scale, "frames": args.frames,
                          "first_positions": positions(args.actors, 0, args.scale)[:3],
                          "atlas": str(ATLAS), "dry_run": True}))
        return 0

    constructors = {"tk": setup_tk, "pygame": setup_pygame, "qt": setup_qt}
    # Any missing GUI module/display is an explicit failure, never a fake result.
    render, close = constructors[args.backend](args.scale, args.actors)
    try:
        for n in range(10):
            render(n)
        tracemalloc.start()
        samples = []
        for n in range(args.frames):
            start = time.perf_counter()
            render(n + 10)
            samples.append((time.perf_counter() - start) * 1000)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    finally:
        close()
    print(json.dumps({
        "backend": args.backend, "actors": args.actors, "scale": args.scale,
        "frames": args.frames, "p50_ms": round(quantile(samples, 0.50), 3),
        "p95_ms": round(quantile(samples, 0.95), 3),
        "mean_ms": round(statistics.mean(samples), 3),
        "peak_python_mb": round(peak / (1024 * 1024), 3),
        "platform": platform.platform(), "python": platform.python_version(),
        "scope": "full frame present incl. event pump, 800x600",
        "memory_scope": "tracemalloc Python allocations only; excludes native/GPU",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
