"""R11 transactional editing of canonical GameProject.cinematics.

No Qt imports, second schema, sidecar manifest or gameplay state mutation.
Each operation validates the entire project before it becomes visible.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

from sporebound.cinematic_authoring4 import (add_motion_keyframe, move_event,
                                              resize_event, update_motion_keyframe)
from sporebound.cinematics import cinematic_template, event_template, frame_at
from sporebound.audio_timeline import mix_at
from sporebound.game_project import GameProject
from sporebound.model import RuleError, require


def _digest(data):
    import json
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf8")).hexdigest()


def jeanne_intro(campaign_id, *, clip_id="jeanne_intro"):
    """Playable authoring example; unbound audio slots fall back to silence."""
    clip = cinematic_template(clip_id, "Jeanne — Les Cendres du Royaume",
                              "campaign_start", campaign_id)
    clip["duration_ms"] = 12000
    bg = event_template("background", "village", 0, 12000)
    bg["color"] = "#34485d"
    cam = event_template("camera", "approche", 0, 8500)
    cam.update({"from": [-0.2, 0.0], "to": [0.18, -0.12],
                "zoom_from": 0.9, "zoom_to": 1.2,
                "easing": "ease_in_out", "shot": "village",
                "transition": "dissolve"})
    actor = event_template("actor", "jeanne", 700, 8700)
    actor.update({"from": [0.18, 0.62], "to": [0.55, 0.62],
                  "easing": "ease_in_out"})
    line1 = event_template("dialogue", "appel", 1800, 3500)
    line1.update({"speaker": "Une voix", "text": "Jeanne, écoute ton destin.",
                  "portrait": "jeanne", "expression": "determined",
                  "chars_per_second": 26})
    line2 = event_template("dialogue", "reponse", 6100, 3500)
    line2.update({"speaker": "Jeanne", "text": "Je défendrai les miens.",
                  "portrait": "jeanne", "expression": "determined",
                  "chars_per_second": 26})
    music = event_template("sound", "musique", 0, 12000)
    music.update({"cue": "jeanne_theme", "bus": "music", "volume": 70,
                  "volume_to": 85, "loop": True,
                  "fade_in_ms": 1400, "fade_out_ms": 2000})
    wind = event_template("sound", "vent", 0, 10000)
    wind.update({"cue": "jeanne_wind", "bus": "ambience", "volume": 48,
                 "loop": True, "fade_in_ms": 500, "fade_out_ms": 1100})
    smoke = event_template("fx", "fumee", 8500, 3000)
    smoke.update({"effect": "smoke", "intensity": .65, "seed": 48,
                  "at": [.72, .52]})
    fade = event_template("fade", "noir", 10500, 1500)
    clip["events"] = [bg, cam, actor, line1, line2, music, wind, smoke, fade]
    return clip


class CinematicDocument:
    """Copy-on-validate undoable document with optional stale-disk protection."""

    def __init__(self, project, content, *, source_path=None):
        project.validate(content)
        self.content = content
        self.project = GameProject.from_dict(project.to_dict(), content)
        self.source_path = Path(source_path) if source_path else None
        self._file_digest = self._read_file_digest()
        self._saved_digest = _digest(self.project.to_dict())
        self._undo = []
        self._redo = []
        self.revision = 0

    def _read_file_digest(self):
        if self.source_path and self.source_path.exists():
            return hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        return None

    @property
    def dirty(self):
        return _digest(self.project.to_dict()) != self._saved_digest

    @property
    def clips(self):
        return deepcopy(self.project.cinematics)

    def clip(self, clip_id):
        clip = next((c for c in self.project.cinematics if c["id"] == clip_id), None)
        require(clip is not None, "Unknown cinematic: " + str(clip_id))
        return deepcopy(clip)

    def _edit(self, operation, *, expected_revision=None):
        require(expected_revision is None or expected_revision == self.revision,
                "Outdated cinematic editor revision")
        before = self.project.to_dict()
        working = deepcopy(before)
        operation(working)
        updated = GameProject.from_dict(working, self.content)
        require(_digest(updated.to_dict()) != _digest(before), "No cinematic changes")
        self._undo.append(before)
        self._undo = self._undo[-100:]
        self._redo.clear()
        self.project = updated
        self.revision += 1

    @staticmethod
    def _clip_in(data, clip_id):
        clip = next((c for c in data.get("cinematics", [])
                     if c["id"] == clip_id), None)
        require(clip is not None, "Unknown cinematic: " + str(clip_id))
        return clip

    @classmethod
    def _event_in(cls, data, clip_id, event_id):
        clip = cls._clip_in(data, clip_id)
        event = next((e for e in clip["events"] if e["id"] == event_id), None)
        require(event is not None, "Unknown cinematic event: " + str(event_id))
        return clip, event

    def add_clip(self, clip, *, expected_revision=None):
        payload = deepcopy(clip)
        self._edit(lambda data: data.setdefault("cinematics", []).append(payload),
                   expected_revision=expected_revision)

    def add_jeanne_intro(self):
        require(bool(self.project.campaigns), "A campaign is required")
        used = {c["id"] for c in self.project.cinematics}
        name = "jeanne_intro"
        n = 2
        while name in used:
            name = "jeanne_intro_" + str(n)
            n += 1
        self.add_clip(jeanne_intro(self.project.campaigns[0]["id"], clip_id=name))
        return name

    def edit_clip(self, clip_id, updates):
        changes = deepcopy(updates)
        require(set(changes) <= {"name", "duration_ms", "trigger"},
                "Unsupported cinematic header field")
        self._edit(lambda data: self._clip_in(data, clip_id).update(changes))

    def delete_clip(self, clip_id):
        def operation(data):
            self._clip_in(data, clip_id)
            data["cinematics"] = [c for c in data["cinematics"] if c["id"] != clip_id]
        self._edit(operation)

    def add_event(self, clip_id, event):
        payload = deepcopy(event)
        self._edit(lambda data: self._clip_in(data, clip_id)["events"].append(payload))

    def add_template(self, clip_id, kind, event_id, at_ms, duration_ms):
        self.add_event(clip_id, event_template(kind, event_id, at_ms, duration_ms))

    def edit_event(self, clip_id, event_id, updates):
        changes = deepcopy(updates)
        require("id" not in changes and "kind" not in changes,
                "Event identity and kind cannot be edited")
        def operation(data):
            clip, event = self._event_in(data, clip_id, event_id)
            if "start_ms" in changes:
                event.update(move_event(event, changes["start_ms"], clip["duration_ms"]))
            if "duration_ms" in changes:
                event.update(resize_event(event, changes["duration_ms"], clip["duration_ms"]))
            event.update(changes)
        self._edit(operation)

    def delete_event(self, clip_id, event_id):
        def operation(data):
            clip, _ = self._event_in(data, clip_id, event_id)
            clip["events"] = [e for e in clip["events"] if e["id"] != event_id]
        self._edit(operation)

    def add_keyframe(self, clip_id, event_id, local_time_ms):
        def operation(data):
            _, event = self._event_in(data, clip_id, event_id)
            event.update(add_motion_keyframe(event, local_time_ms))
        self._edit(operation)

    def update_keyframe(self, clip_id, event_id, local_time_ms, **changes):
        def operation(data):
            _, event = self._event_in(data, clip_id, event_id)
            event.update(update_motion_keyframe(event, local_time_ms, **changes))
        self._edit(operation)

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self.project.to_dict())
        self.project = GameProject.from_dict(self._undo.pop(), self.content)
        self.revision += 1
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self.project.to_dict())
        self.project = GameProject.from_dict(self._redo.pop(), self.content)
        self.revision += 1
        return True

    def sample(self, clip_id, ms):
        clip = self.clip(clip_id)
        return frame_at(clip, ms), mix_at(clip, ms)

    def save(self, path=None):
        target = Path(path) if path else self.source_path
        require(target is not None, "No project path specified")
        if self.source_path and target.resolve() == self.source_path.resolve():
            require(self._read_file_digest() == self._file_digest,
                    "Project changed on disk: reload before saving")
        self.project.save(target, self.content)
        self.source_path = target
        self._file_digest = self._read_file_digest()
        self._saved_digest = _digest(self.project.to_dict())
        return target
