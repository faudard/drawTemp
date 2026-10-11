"""Renderer-neutral, clock-driven poses derived exclusively from BattleFrame.

Animation is cosmetic: it never alters an actor, RNG, tick, save or command.
The caller supplies a monotonic millisecond clock for reproducible samples.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActorPose:
    x: float
    y: float
    action: str
    direction: str


class MotionDirector:
    """Interpolate consecutive battle projections without delaying gameplay."""

    def __init__(self, duration_ms=280):
        if type(duration_ms) is not int or duration_ms < 1:
            raise ValueError("duration_ms must be a positive integer")
        self.duration_ms = duration_ms
        self.reset()

    def reset(self):
        self._current = None
        self._previous = None
        self._started = 0.
        self._actions = {}
        self._directions = {}

    @staticmethod
    def _new_events(old_events, new_events):
        # Frames retain a rolling journal; find the largest shared suffix/prefix.
        limit = min(len(old_events), len(new_events))
        for overlap in range(limit, -1, -1):
            if overlap == 0 or old_events[-overlap:] == new_events[:overlap]:
                return new_events[overlap:]
        return new_events

    def observe(self, frame, now_ms):
        """Set the newest authoritative frame. Harmless redraws do not restart motion."""
        if frame is None:
            self.reset()
            return
        old = self._current
        if old is None or frame.mission != old.mission or frame.tick < old.tick:
            self.reset()
            self._current = frame
            return
        if old.actors == frame.actors and old.events == frame.events:
            self._current = frame
            return

        previous_actors = {actor.id: actor for actor in old.actors}
        actions = {}
        added = self._new_events(old.events, frame.events)
        for actor in frame.actors:
            before = previous_actors.get(actor.id)
            if before is None:
                actions[actor.id] = "idle"
                continue
            dx, dy = actor.pos[0] - before.pos[0], actor.pos[1] - before.pos[1]
            if dx or dy:
                self._directions[actor.id] = (
                    "east" if abs(dx) >= abs(dy) and dx > 0 else
                    "west" if abs(dx) >= abs(dy) else
                    "south" if dy > 0 else "north")
            if before.alive and not actor.alive:
                action = "defeat"
            elif actor.hp < before.hp:
                action = "hit"
            elif dx or dy:
                action = "move"
            elif any(event.get("unit") == actor.id and
                     event.get("kind") in {"skill", "charge", "siege_hit"}
                     for event in added):
                action = "attack"
            else:
                action = "idle"
            actions[actor.id] = action
        self._previous = old
        self._current = frame
        self._actions = actions
        self._started = float(now_ms)

    def elapsed_ms(self, now_ms):
        return max(0, int(float(now_ms) - self._started))

    def active(self, now_ms):
        return (self._previous is not None and
                self.elapsed_ms(now_ms) < self.duration_ms and
                any(action != "idle" for action in self._actions.values()))

    def poses(self, now_ms):
        if self._current is None:
            return {}
        progress = min(1., self.elapsed_ms(now_ms) / self.duration_ms)
        before = ({a.id: a for a in self._previous.actors}
                  if self._previous is not None else {})
        result = {}
        for actor in self._current.actors:
            old = before.get(actor.id)
            action = self._actions.get(actor.id, "idle") if progress < 1. else (
                "defeat" if not actor.alive else "idle")
            if old is not None and self._actions.get(actor.id) == "move" and progress < 1.:
                x = old.pos[0] + (actor.pos[0] - old.pos[0]) * progress
                y = old.pos[1] + (actor.pos[1] - old.pos[1]) * progress
            else:
                x, y = actor.pos
            result[actor.id] = ActorPose(
                x, y, action, self._directions.get(actor.id, "south"))
        return result


def animation_sprite_id(registry, actor_id, team, action, direction, elapsed_ms):
    """Pick a portable PNG sprite ID, never load images or access the filesystem.

    Supported slots: hero_move_east, hero_move, player_move_east,
    player_move, and corresponding idle fallbacks. The registry owns
    references, duration validation, and path security.
    """
    if registry is None:
        return None
    if direction not in {"north", "south", "east", "west"}:
        direction = "south"
    slots = []
    for pose in (action, "idle") if action != "idle" else ("idle",):
        for identity in (actor_id, team):
            slots.extend((f"{identity}_{pose}_{direction}", f"{identity}_{pose}"))
    for slot in slots:
        spec = registry.binding("animation", slot)
        if spec is None:
            continue
        frames = spec["frames"]
        duration = sum(frame["duration_ms"] for frame in frames)
        instant = max(0, int(elapsed_ms))
        instant = instant % duration if spec["loop"] else min(instant, duration - 1)
        for frame in frames:
            if instant < frame["duration_ms"]:
                return frame["sprite"]
            instant -= frame["duration_ms"]
    return None
