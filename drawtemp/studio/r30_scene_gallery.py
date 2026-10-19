"""R30.E — curated, non-executable narrative templates for the Creator gallery.

The four genre labels are discovery tags, not declarations of playable engines.
Only canonical GameProject.story scenes are copied. All edits are staged in the
single existing AuthoringSession, and committed only by explicit apply/Undo.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from importlib.resources import files
import json
import re

from drawtemp.sdk.authoring import AuthoringSession, AuthoringPlan

_GENRES = {"srpg", "action-adventure", "classic-rpg", "hybrid"}
_ENTRY = re.compile(r"[a-z][a-z0-9-]{1,31}\Z")
_SCENE = re.compile(r"[a-z][a-z0-9_-]{0,23}\Z")
_NAMESPACE = re.compile(r"[a-z][a-z0-9-]{0,15}\Z")


class GalleryError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class GalleryEntry:
    template_id: str
    genre: str
    title: str
    description: str
    readiness: str
    scene_count: int

    def to_dict(self):
        return {
            "id": self.template_id,
            "genre": self.genre,
            "title": self.title,
            "description": self.description,
            "readiness": self.readiness,
            "scene_count": self.scene_count,
            "playable_genre_certified": False,
        }


@dataclass(frozen=True)
class GalleryPreview:
    template_id: str
    genre: str
    namespace: str
    campaign_id: str | None
    scene_ids: tuple[str, ...]
    source_revision: int

    def to_dict(self):
        return {
            "id": self.template_id, "genre": self.genre,
            "namespace": self.namespace, "campaign_id": self.campaign_id,
            "scenes": list(self.scene_ids), "revision": self.source_revision,
            "playable_genre_certified": False,
            "applied": False,
        }


def validate_catalog(document) -> dict:
    """Strict schema for bundled snippets; no user-controlled script or DSL."""
    if (not isinstance(document, dict) or set(document) !=
            {"schema", "kind", "entries"} or
            type(document["schema"]) is not int or document["schema"] != 1 or
            document["kind"] != "drawtemp-r30e-scene-gallery"):
        raise GalleryError("invalid_catalog", "Unsupported scene gallery catalog")
    entries = document["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
        raise GalleryError("invalid_catalog", "Expected 1..32 gallery templates")
    ids = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "id", "genre", "title", "description", "readiness", "scenes"
        }:
            raise GalleryError("invalid_entry", "Unknown or missing gallery fields")
        template_id = entry["id"]
        if (not isinstance(template_id, str) or not _ENTRY.fullmatch(template_id) or
                template_id in ids):
            raise GalleryError("invalid_entry", "Duplicate or invalid template id")
        ids.add(template_id)
        if entry["genre"] not in _GENRES:
            raise GalleryError("invalid_genre", "No supported discovery tag")
        if entry["readiness"] != "narrative-scene-only":
            raise GalleryError("invalid_readiness", "Cannot claim unqualified gameplay")
        for key, limit in (("title", 120), ("description", 500)):
            value = entry[key]
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
                raise GalleryError("invalid_entry", "Invalid template " + key)
        scenes = entry["scenes"]
        if not isinstance(scenes, list) or not 1 <= len(scenes) <= 16:
            raise GalleryError("invalid_scenes", "Expected 1..16 narrative scenes")
        scene_ids = set()
        links = {}
        for scene in scenes:
            if not isinstance(scene, dict) or set(scene) != {
                "id", "title", "speaker", "text", "choices"
            }:
                raise GalleryError("invalid_scene", "Scene is not canonical")
            identifier = scene["id"]
            if (not isinstance(identifier, str) or not _SCENE.fullmatch(identifier)
                    or identifier in scene_ids):
                raise GalleryError("invalid_scene", "Bad or duplicate scene id")
            scene_ids.add(identifier)
            for key, limit in (("title", 120), ("speaker", 120), ("text", 5000)):
                field = scene[key]
                if not isinstance(field, str) or len(field) > limit or (
                        key != "speaker" and not field.strip()):
                    raise GalleryError("invalid_scene", "Invalid scene text field")
            choices = scene["choices"]
            if not isinstance(choices, list) or not 1 <= len(choices) <= 20:
                raise GalleryError("invalid_choices", "Scene requires 1..20 choices")
            seen_choices = set()
            targets = []
            for choice in choices:
                if (not isinstance(choice, dict) or
                        not {"id", "label"} <= set(choice) <=
                        {"id", "label", "next_scene"}):
                    raise GalleryError("invalid_choices", "Only inert choices are supported")
                cid, label = choice["id"], choice["label"]
                if (not isinstance(cid, str) or not _SCENE.fullmatch(cid) or
                        cid in seen_choices or not isinstance(label, str) or
                        not 1 <= len(label.strip()) <= 240):
                    raise GalleryError("invalid_choices", "Invalid or duplicate choice")
                seen_choices.add(cid)
                if "next_scene" in choice:
                    target = choice["next_scene"]
                    if not isinstance(target, str):
                        raise GalleryError("invalid_choices", "Invalid next_scene")
                    targets.append(target)
            links[identifier] = targets
        if any(dest not in scene_ids for targets in links.values() for dest in targets):
            raise GalleryError("broken_graph", "Missing narrative scene target")
        visiting, visited = set(), set()
        def walk(node):
            if node in visiting:
                raise GalleryError("cyclic_graph", "Narrative graph must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for child in links[node]:
                walk(child)
            visiting.remove(node)
            visited.add(node)
        for scene_id in scene_ids:
            walk(scene_id)
    return deepcopy(document)


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GalleryError("duplicate_json_key", "Gallery JSON contains duplicate keys")
        result[key] = value
    return result


def load_catalog() -> dict:
    """Read the bundled, reviewed examples without network or filesystem writes."""
    source = files("drawtemp.studio").joinpath("data/r30e_scene_gallery.json")
    raw = source.read_bytes()
    if len(raw) > 256 * 1024:
        raise GalleryError("oversized_catalog", "Gallery catalog exceeds budget")
    return validate_catalog(json.loads(raw.decode("utf-8"),
                                       object_pairs_hook=_unique_json))


def gallery_entries() -> tuple[GalleryEntry, ...]:
    return tuple(
        GalleryEntry(item["id"], item["genre"], item["title"],
                     item["description"], item["readiness"], len(item["scenes"]))
        for item in load_catalog()["entries"]
    )


class GalleryController:
    """Preview/commit namespaced scene clones in one canonical Studio session."""

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise GalleryError("invalid_session", "An AuthoringSession is required")
        self.session = session
        self.invalidate()

    def preview(self, template_id: str, namespace: str, *,
                campaign_id: str | None = None) -> GalleryPreview:
        self.invalidate()
        if not isinstance(template_id, str):
            raise GalleryError("unknown_template", "Select a catalog entry")
        entry = next((item for item in load_catalog()["entries"]
                      if item["id"] == template_id), None)
        if entry is None:
            raise GalleryError("unknown_template", "Unknown gallery template")
        if not isinstance(namespace, str) or not _NAMESPACE.fullmatch(namespace):
            raise GalleryError("invalid_namespace", "Namespace: 1..16 lower-case chars")
        snap = self.session.snapshot().to_dict()
        content, project = snap["content"], deepcopy(snap["project"])
        story = project.get("story", {}) or {}
        if not isinstance(story, dict):
            raise GalleryError("invalid_story", "Invalid existing story")
        story = deepcopy(story)
        scenes = story.setdefault("scenes", [])
        existing = {scene["id"].casefold() for scene in scenes}
        mapping = {}
        for item in entry["scenes"]:
            name = "r30e_" + namespace + "_" + template_id + "_" + item["id"]
            if len(name) > 64:
                raise GalleryError("namespace_too_long", "Generated scene id is over 64 chars")
            if name.casefold() in existing:
                raise GalleryError("duplicate_scene", "Scene already exists: " + name)
            existing.add(name.casefold())
            mapping[item["id"]] = name
        for item in entry["scenes"]:
            cloned = deepcopy(item)
            cloned["id"] = mapping[item["id"]]
            for choice in cloned["choices"]:
                if "next_scene" in choice:
                    choice["next_scene"] = mapping[choice["next_scene"]]
            scenes.append(cloned)
        if campaign_id is not None:
            if (not isinstance(campaign_id, str) or
                    campaign_id not in {item["id"] for item in project["campaigns"]}):
                raise GalleryError("unknown_campaign", "Choose a real project campaign")
            attached = story.setdefault("entry_scenes", {})
            if campaign_id in attached:
                raise GalleryError("existing_entry", "Campaign already has an intro scene")
            attached[campaign_id] = mapping[entry["scenes"][0]["id"]]
        project["story"] = story

        # AuthoringSession previews invoke validate_pair, including narrative
        # references and cycle checks; the renderer/CT/replay are untouched.
        plan = self.session.preview_project(
            lambda _project: project, kind="r30e-gallery-scene")
        preview = GalleryPreview(template_id, entry["genre"], namespace,
                                 campaign_id, tuple(mapping.values()),
                                 snap["revision"])
        self._plan = plan
        self._preview = preview
        return preview

    def apply(self, preview: GalleryPreview):
        if self._preview is not preview or self._plan is None:
            raise GalleryError("stale_preview", "Re-preview after changing the selection")
        plan = self._plan
        self.invalidate()
        return self.session.apply(plan)

    def invalidate(self):
        self._plan: AuthoringPlan | None = None
        self._preview: GalleryPreview | None = None
