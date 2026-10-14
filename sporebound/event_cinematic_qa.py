"""R7.16: strict, headless event → scene → cinematic → consequence QA.

This is a read-only authoring certificate, not a new event executor. Actual
choices and tactical effects still run through StoryBook / GameSession.
"""
from dataclasses import asdict, dataclass
import hashlib
import json

from .audio_timeline import mix_at
from .cinematics import frame_at, matching_cinematics
from .game_project import GameProject
from .model import require


@dataclass(frozen=True)
class CinematicPathAudit:
    source_kind: str
    source_id: str
    scene_id: str
    cinematic_ids: tuple
    choice_id: str
    gameplay_effects: tuple
    next_scene: str
    timeline_sha256: str


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _source_scene(project, content, kind, target):
    if kind == "tactical_event":
        known = {f"{mission.id}/{event['id']}"
                 for mission in content.missions.values()
                 for event in mission.triggers}
        require(target in known, "Unknown tactical event source")
        links = project.story.get("during_tactical_event", {})
    elif kind == "strategic_event":
        known = {f"{siege['id']}/{node['id']}"
                 for siege in project.sieges
                 for node in siege.get("event_graph", [])}
        require(target in known, "Unknown strategic event source")
        links = project.story.get("after_strategic_event", {})
    else:
        require(False, "QA source must be tactical_event or strategic_event")
    scene_id = links.get(target)
    require(scene_id is not None, "Event is not linked to a narrative scene")
    return scene_id


def _timeline_signature(clips):
    """Verify seek/replay order and preserve the visual/audio result in the report."""
    signature = []
    for clip in clips:
        duration = clip["duration_ms"]
        points = sorted({0, duration // 4, duration // 2,
                         max(0, duration - 1), duration})
        def sample(ms):
            return (ms, asdict(frame_at(clip, ms)),
                    [asdict(track) for track in mix_at(clip, ms)])
        forward = [sample(ms) for ms in points]
        backward = [sample(ms) for ms in reversed(points)]
        require(forward == list(reversed(backward)),
                "Cinematic / audio projection is not deterministic")
        signature.append({"clip": clip["id"], "samples": forward})
    return hashlib.sha256(_canonical(signature).encode("utf-8")).hexdigest()


def audit_event_cinematic_path(project, content, *, source_kind, source_id,
                               choice_id):
    """Certificate of a linked authored path; does not execute gameplay.

    A nonempty choice consequence (campaign/tactical effect or next scene) is
    mandatory for this gate. Conditional choices are reported as authored,
    not as automatically reachable in every runtime campaign state.
    """
    project.validate(content)
    scene_id = _source_scene(project, content, source_kind, source_id)
    scene = next(scene for scene in project.story["scenes"]
                 if scene["id"] == scene_id)
    choice = next((row for row in scene["choices"]
                   if row["id"] == choice_id), None)
    require(choice is not None, "Unknown narrative choice")
    consequences = (*choice.get("effects", ()),
                    *choice.get("tactical_effects", ()))
    next_scene = choice.get("next_scene", "")
    require(bool(consequences or next_scene),
            "Choice has no authored gameplay or narrative consequence")
    clips = matching_cinematics(project, "scene", scene_id)
    require(bool(clips), "Linked scene has no cinematic")
    # The complete serialized manifest must survive strict validation.
    restored = GameProject.from_dict(project.to_dict(), content)
    signature = _timeline_signature(clips)
    require(signature == _timeline_signature(
        matching_cinematics(restored, "scene", scene_id)),
        "Cinematic result changed after project serialization")
    return CinematicPathAudit(
        source_kind, source_id, scene_id,
        tuple(clip["id"] for clip in clips), choice_id,
        tuple(effect["kind"] for effect in consequences),
        next_scene, signature)
