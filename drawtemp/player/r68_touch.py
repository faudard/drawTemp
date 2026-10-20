"""R68.B1: experimental platform-neutral touch and lifecycle input driver.

Only the existing R26 ActionPlayerController commits game ticks. This module
uses its canonical clock and step API; it is not an Android/Web runtime and
does not change the R39 publication targets.
"""
from __future__ import annotations

import math
import time

from drawtemp.player.action_clock import ActionStepClock

_MAX_FINGERS = 10
# Fractional centers shared with MobileTouchOverlay.qml, tested headlessly.
_ACTION_CENTERS = {
    "interact": (0.67, 0.59),
    "attack": (0.84, 0.63),
    "guard": (0.67, 0.83),
    "dodge": (0.85, 0.86),
}


class TouchInput:
    """Full-frame finger snapshots -> held motion/actions and one-shot edges."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.dx = 0
        self.dy = 0
        self.attack = False
        self.guard = False
        self._held = frozenset()
        self._dodge_edge = False
        self._interact_edge = False

    def update(self, points, width, height):
        if (type(width) is not int or type(height) is not int or
                width < 240 or height < 160 or
                type(points) not in (list, tuple) or len(points) > _MAX_FINGERS):
            raise ValueError("Invalid touch viewport or finger list")
        directions = []
        held = set()
        ids = set()
        for point in points:
            if type(point) is not dict or set(point) != {"id", "x", "y"}:
                raise ValueError("Touch point needs id, x, y")
            ident, x, y = point["id"], point["x"], point["y"]
            if (type(ident) is not int or not 0 <= ident <= 9999 or
                    ident in ids or type(x) not in (int, float) or
                    type(y) not in (int, float) or
                    not math.isfinite(x) or not math.isfinite(y)):
                raise ValueError("Invalid or duplicate touch point")
            ids.add(ident)
            if not (0 <= x <= width and 0 <= y <= height):
                continue  # Dragged outside; never synthesize an input.
            if x < width * .47 and y > height * .35:
                center_x, center_y = .20 * width, .75 * height
                delta_x, delta_y = x - center_x, y - center_y
                deadzone = max(18., min(width, height) * .045)
                directions.append((
                    (1 if delta_x >= deadzone else -1 if delta_x <= -deadzone else 0),
                    (1 if delta_y >= deadzone else -1 if delta_y <= -deadzone else 0),
                ))
                continue
            radius = min(54., width * .09, height * .15)
            for name, (center_x, center_y) in _ACTION_CENTERS.items():
                if ((x - center_x * width) ** 2 +
                        (y - center_y * height) ** 2) <= radius ** 2:
                    held.add(name)
                    break
        self.dx = max(-1, min(1, sum(direction[0] for direction in directions)))
        self.dy = max(-1, min(1, sum(direction[1] for direction in directions)))
        self._dodge_edge |= "dodge" in held and "dodge" not in self._held
        self._interact_edge |= "interact" in held and "interact" not in self._held
        self._held = frozenset(held)
        self.attack = "attack" in held
        self.guard = "guard" in held

    def consume_edges(self):
        result = self._dodge_edge, self._interact_edge
        self._dodge_edge = self._interact_edge = False
        return result


class PortableActionDriver:
    """Clock + Qt-independent platform adapter for the existing R26 controller."""

    def __init__(self, controller, *, now_ns=None):
        self.controller = controller
        self.touch = TouchInput()
        self.clock = ActionStepClock()
        self._now = now_ns if now_ns is not None else time.monotonic_ns
        self.active = True
        self._last_ns = self._now()
        self._pending_dodge = False
        self._pending_interact = False

    def reset(self):
        self.clock.reset()
        self._last_ns = self._now()
        self._pending_dodge = False
        self._pending_interact = False
        self.touch.reset()

    def set_active(self, active):
        if type(active) is not bool:
            raise ValueError("Platform active flag must be bool")
        if self.active != active:
            self.active = active
            self.reset()

    def update_touch(self, points, width, height):
        if not self.active:
            return
        self.touch.update(points, width, height)

    def pulse(self, dx, dy, attack=False, dodge=False, guard=False, interact=False):
        now = self._now()
        elapsed = max(0, now - self._last_ns)
        self._last_ns = now
        if not self.active or self.controller.paused or not self.controller.runtime.hero["alive"]:
            self.reset()
            return 0

        tdodge, tinteract = self.touch.consume_edges()
        self._pending_dodge |= bool(dodge) or tdodge
        self._pending_interact |= bool(interact) or tinteract
        dx = max(-1, min(1, dx + self.touch.dx))
        dy = max(-1, min(1, dy + self.touch.dy))
        steps = self.clock.advance(elapsed)
        for _ in range(steps):
            if not self.controller.runtime.hero["alive"]:
                break
            self.controller.step(
                dx, dy, attack=bool(attack) or self.touch.attack,
                dodge=self._pending_dodge,
                guard=bool(guard) or self.touch.guard,
                interact=self._pending_interact)
            self._pending_dodge = False
            self._pending_interact = False
        return steps


__all__ = ["PortableActionDriver", "TouchInput"]
