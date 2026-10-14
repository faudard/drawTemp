"""Reusable Tk loader for procedural 3.7.32J environment sprite sheets.

The art is authored in environment_atlas.py and can be exported as PNGs.
This adapter owns Tk PhotoImage references for every frame while a Canvas
uses them; it never decodes/regenerates pixels during animation ticks.
"""
from __future__ import annotations

from .environment_atlas import (KINDS, FRAME_SIZE, FRAME_COUNT,
                                environment_strip_png)
from .tk_images import crop_scaled


class IsoEnvironmentAtlas:
    """Shared Player/Studio 8-frame sprites at the current isometric zoom."""

    def __init__(self, canvas):
        self.canvas = canvas
        self._sources = {}
        self._frames = {}
        self._unavailable = False

    def frame(self, kind, cell_size, phase=0):
        if (self._unavailable or kind not in KINDS or
                type(cell_size) is not int or cell_size <= 0 or
                type(phase) is not int or not 0 <= phase < FRAME_COUNT):
            return None
        key = kind, cell_size, phase
        if key in self._frames:
            return self._frames[key]
        try:
            import base64
            import tkinter as tk
            if kind not in self._sources:
                self._sources[kind] = tk.PhotoImage(
                    data=base64.b64encode(environment_strip_png(kind)).decode('ascii'),
                    format='png', master=self.canvas)
                source = self._sources[kind]
                if (source.width(), source.height()) != (
                        FRAME_COUNT*FRAME_SIZE, FRAME_SIZE):
                    raise ValueError('Unexpected environment sprite-sheet size')
            target = max(1, round(FRAME_SIZE*cell_size/54))
            image = crop_scaled(
                self._sources[kind],
                (FRAME_SIZE*phase, 0, FRAME_SIZE, FRAME_SIZE),
                (target, target), master=self.canvas)
            self._frames[key] = image
            return image
        except (OSError, ValueError, RuntimeError, ImportError, tk.TclError):
            # A broken PNG decoder must not disable the legacy vector accents.
            self._unavailable = True
            return None

    def clear_cache(self):
        """Call after the Canvas stops referring to these Photos."""
        self._frames.clear()
        self._sources.clear()
