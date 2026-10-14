"""R7.18: portable structural audiovisual goldens using the real Canvas renderer.

No Tk, font metrics, audio output device or native screenshot dependency.
A golden records visible scene semantics and real draw-command geometry rather
than per-platform pixels. Pixel-perfect certification remains an optional,
separate platform-specific review, not a falsely portable CI gate.
"""
import hashlib
import json

from .audio_timeline import mix_at
from .cinematic_player import draw_frame
from .model import require


def _coordinate(value):
    if isinstance(value, float):
        return 0.0 if abs(value) < 0.00005 else round(value, 4)
    return value


class _CanvasCapture:
    """Only the Canvas primitives actually used by draw_frame()."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.calls = []

    def delete(self, tag):
        require(tag == "all", "Golden capture requires a cleared stage")
        self.calls.clear()

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def _record(self, kind, coords, kwargs):
        self.calls.append((kind, tuple(coords), dict(kwargs)))
        return len(self.calls)

    def create_rectangle(self, *coords, **kwargs):
        return self._record("rectangle", coords, kwargs)

    def create_oval(self, *coords, **kwargs):
        return self._record("oval", coords, kwargs)

    def create_text(self, *coords, **kwargs):
        return self._record("text", coords, kwargs)

    def create_image(self, *coords, **kwargs):
        return self._record("image", coords, kwargs)


class _SymbolicPortraitRenderer:
    """Non-asset stub: optional expression portrait used in reference images."""

    def image(self, kind, slot):
        if kind == "portrait" and slot.endswith("_determined"):
            return "portrait:" + slot
        return None


def golden_at(clip, time_ms, *, viewport=(800, 500), portrait=False):
    """Capture source-of-truth frame + mixer + actual Canvas draw geometry.

    The sample captures the same `draw_frame` used by Studio preview and Player.
    The reference is independent of font rasterization, host DPI and audio APIs.
    """
    require(type(time_ms) is int, "Golden time must be integer ms")
    require(isinstance(viewport, (list, tuple)) and len(viewport) == 2
            and all(type(value) is int and 320 <= value <= 4096
                    for value in viewport),
            "Golden viewport must be a bounded integer pixel pair")
    canvas = _CanvasCapture(*viewport)
    frame = draw_frame(canvas, clip, time_ms,
                       _SymbolicPortraitRenderer() if portrait else None)
    tracks = mix_at(clip, time_ms)
    calls = canvas.calls
    def centers(kind):
        return [[_coordinate((coords[0] + coords[2]) / 2),
                 _coordinate((coords[1] + coords[3]) / 2)]
                for operation, coords, _ in calls if operation == kind]

    portraits = [options["image"] for operation, _, options in calls
                 if operation == "image" and
                 isinstance(options.get("image"), str) and
                 options["image"].startswith("portrait:")]
    dialogue_boxes = [[_coordinate(coord) for coord in coords]
                      for operation, coords, options in calls
                      if operation == "rectangle" and
                      options.get("fill") == "#091523"]
    labels = [options.get("text", "") for operation, _, options in calls
              if operation == "text"]
    data = {
        "ms": frame.time_ms,
        "viewport": list(viewport),
        "background": frame.background,
        "actors": [[actor, [_coordinate(x), _coordinate(y)]]
                   for actor, (x, y) in frame.actors],
        "actor_centers": centers("oval"),
        "camera": [_coordinate(x) for x in frame.camera],
        "zoom": _coordinate(frame.zoom),
        "shot": frame.shot,
        "transition": ([frame.shot_transition[0],
                        _coordinate(frame.shot_transition[1])]
                       if frame.shot_transition else None),
        "dialogue": ({
            "speaker": frame.dialogue[0],
            "visible": (frame.dialogue_presentation.visible_text
                        if frame.dialogue_presentation else frame.dialogue[1]),
            "expression": (frame.dialogue_presentation.expression
                           if frame.dialogue_presentation else "neutral"),
            "portrait": (frame.dialogue_presentation.portrait
                         if frame.dialogue_presentation else ""),
        } if frame.dialogue else None),
        "dialogue_boxes": dialogue_boxes,
        "portrait_images": portraits,
        "labels": labels,
        "fade": ([frame.fade[0], _coordinate(frame.fade[1])]
                 if frame.fade else None),
        "mix": [[track.event_id, track.bus, _coordinate(track.level),
                 track.loop] for track in tracks],
    }
    # Lightweight renderer layer-order gate: dialogue belongs above the wipe;
    # fades obscure everything. A changed ordering is a visible regression.
    if frame.dialogue:
        panels = [i for i, (kind, _, kw) in enumerate(calls)
                  if kind == "rectangle" and kw.get("fill") == "#091523"]
        require(len(panels) == 1, "Expected exactly one dialogue panel")
        if frame.shot_transition:
            transitions = [i for i, (kind, _, kw) in enumerate(calls)
                           if kind == "rectangle" and kw.get("fill") == "#101a2b"]
            require(not transitions or transitions[-1] < panels[0],
                    "Camera transition covered the dialogue UI")
        if frame.fade and frame.fade[1] > 0:
            require(calls[-1][0] == "rectangle" and
                    calls[-1][2].get("fill") == frame.fade[0],
                    "Final fade must cover the entire scene")
    return data


def golden_sha256(samples):
    return hashlib.sha256(json.dumps(
        samples, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def assert_golden_matches(clips, fixture):
    """Fail closed; never overwrite reviewed reference data in ordinary tests."""
    require(isinstance(fixture, dict) and fixture.get("version") == 1
            and isinstance(fixture.get("samples"), list)
            and bool(fixture["samples"]), "Invalid golden fixture")
    results = []
    for sample in fixture["samples"]:
        clip = clips.get(sample["clip"])
        require(clip is not None, "Unknown cinematic in golden fixture")
        current = golden_at(clip, sample["expected"]["ms"],
                            viewport=sample["expected"]["viewport"],
                            portrait=sample.get("portrait", False))
        require(current == sample["expected"],
                "Golden changed for %s at %d ms; inspect the diff before "
                "explicitly updating the reference" %
                (sample["clip"], sample["expected"]["ms"]))
        results.append(current)
    return golden_sha256(results)
