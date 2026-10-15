"""Stable Qt-friendly projection of the legacy Player's cinematic state."""
from pathlib import Path

from sporebound.cinematics import frame_at, effects_at
from sporebound.audio_timeline import mix_at
from sporebound.model import RuleError


def _asset_uri(registry, root, kind, slot):
    if registry is None or root is None:
        return ""
    try:
        binding = registry.binding(kind, slot)
        if binding is not None:
            return Path(registry.resolve(binding["id"], root)).as_uri()
    except (RuleError, OSError, ValueError):
        pass
    return ""


def _animation_uri(registry, root, slot, elapsed_ms):
    """Select a real atlas frame from the canonical animation registry."""
    if registry is None or root is None or not slot:
        return ""
    try:
        spec = registry.binding("animation", slot)
        if spec is None:
            return ""
        frames = spec["frames"]
        total = sum(frame["duration_ms"] for frame in frames)
        elapsed = max(0, int(elapsed_ms))
        elapsed = elapsed % total if spec["loop"] else min(elapsed, total - 1)
        for frame in frames:
            if elapsed < frame["duration_ms"]:
                return Path(registry.resolve(frame["sprite"], root)).as_uri()
            elapsed -= frame["duration_ms"]
    except (RuleError, OSError, ValueError):
        pass
    return ""


def frame_payload(clip, time_ms, *, registry=None, asset_root=None):
    """Studio and Player use this exact projection; only renderer owns pixels."""
    frame = frame_at(clip, time_ms)
    actors = []
    actor_events = sorted((e for e in clip["events"] if e["kind"] == "actor"
                           and e["start_ms"] <= frame.time_ms),
                          key=lambda event: event["start_ms"])
    for actor, (x, y) in frame.actors:
        track = next((e for e in reversed(actor_events) if e["actor"] == actor), {})
        pose = track.get("pose", "")
        image = (_animation_uri(registry, asset_root, track.get("animation", ""),
                                frame.time_ms - track.get("start_ms", 0))
                 or (_asset_uri(registry, asset_root, "sprite", actor + "_" + pose)
                     if pose else "")
                 or _asset_uri(registry, asset_root, "sprite", actor))
        actors.append({"name": actor, "x": x, "y": y, "image": image})
    detail = frame.dialogue_presentation
    portrait = (detail.portrait if detail else "") if frame.dialogue else ""
    expression = detail.expression if detail else "neutral"
    portrait_uri = (
        _asset_uri(registry, asset_root, "portrait", portrait + "_" + expression)
        or _asset_uri(registry, asset_root, "portrait", portrait)
        if portrait else ""
    )
    return {
        "timeMs": frame.time_ms, "background": frame.background,
        "actors": actors, "cameraX": frame.camera[0], "cameraY": frame.camera[1],
        "zoom": frame.zoom, "shot": frame.shot or "",
        "transition": (frame.shot_transition[0] if frame.shot_transition else ""),
        "transitionOpacity": (1.0 - frame.shot_transition[1]
                              if frame.shot_transition else 0.0),
        "fadeColor": frame.fade[0] if frame.fade else "#000000",
        "fadeOpacity": frame.fade[1] if frame.fade else 0.0,
        "speaker": frame.dialogue[0] if frame.dialogue else "",
        "dialogue": detail.visible_text if detail else (frame.dialogue[1]
                     if frame.dialogue else ""),
        "expression": expression, "portrait": portrait_uri,
        "effects": [{"kind": effect[0], "power": effect[1], "seed": effect[2],
                     "x": effect[3][0], "y": effect[3][1], "phase": effect[4]}
                    for effect in effects_at(clip, time_ms)],
    }


def audio_payload(clip, time_ms):
    return [{"id": t.event_id, "cue": t.cue, "bus": t.bus,
             "level": t.level, "loop": t.loop}
            for t in mix_at(clip, time_ms)]
