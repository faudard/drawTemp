"""R2 resource projection and transactional inspector operations.

The tree is a *view* of the canonical Content/GameProject pair, not an index
that owns resources or a second save format. Keep this module importable with
PySide6 and tkinter explicitly unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession


@dataclass(frozen=True)
class Resource:
    family: str
    resource_id: str
    title: str
    mission_id: str = ""

    @property
    def key(self):
        return (self.family, self.mission_id, self.resource_id)


FAMILY_LABELS = {
    "project": "Projet",
    "maps": "Cartes",
    "actors": "Personnages",
    "objects": "Objets",
    "events": "Événements",
    "campaigns": "Campagnes",
    "scenes": "Dialogues",
    "cinematics": "Cinématiques",
}


def resources(snapshot):
    """Flat, stable resource identities from one immutable session snapshot."""
    data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
    content, project = data["content"], data["project"]
    result = [Resource("project", "project", project.get("title", "DrawTemp"))]
    for mission in content.get("missions", []):
        mid = mission["id"]
        result.append(Resource("maps", mid, mission.get("name", mid)))
        for family, field in (("actors", "units"), ("objects", "objects"),
                              ("events", "triggers")):
            for item in mission.get(field, []):
                result.append(Resource(family, item["id"],
                                       item.get("name", item.get("title", item["id"])),
                                       mid))
    for campaign in project.get("campaigns", []):
        result.append(Resource("campaigns", campaign["id"],
                               campaign.get("name", campaign["id"])))
    for scene in project.get("story", {}).get("scenes", []):
        result.append(Resource("scenes", scene["id"],
                               scene.get("title", scene["id"])))
    for clip in project.get("cinematics", []):
        result.append(Resource("cinematics", clip["id"],
                               clip.get("name", clip["id"])))
    return tuple(result)


def _targets(data, selected):
    """Resolve each editable identity against the supplied detached document."""
    missions = {mission["id"]: mission for mission in data["missions"]}
    for resource in selected:
        if resource.family == "maps":
            if resource.resource_id not in missions:
                raise ValueError("Carte supprimée depuis la sélection")
            yield missions[resource.resource_id]
        elif resource.family in ("actors", "objects"):
            field = "units" if resource.family == "actors" else "objects"
            mission = missions.get(resource.mission_id)
            if mission is None:
                raise ValueError("Mission inconnue")
            target = next((row for row in mission.get(field, ())
                           if row["id"] == resource.resource_id), None)
            if target is None:
                raise ValueError("Ressource supprimée depuis la sélection")
            yield target
        else:
            raise ValueError("Ce type de ressource est en lecture seule")


def editable_name(selected):
    """Only names, never IDs/references, are editable by the generic inspector."""
    selected = tuple(selected)
    return bool(selected) and all(r.family in ("maps", "actors", "objects")
                                  for r in selected)


def common_name(selected):
    """Return (value, mixed) for a typed multi-selection."""
    values = {r.title for r in selected}
    return (next(iter(values)), False) if len(values) == 1 else ("", bool(values))


def edit_names(session: AuthoringSession, selected, new_name: str):
    """One R1 preview/apply and one Undo step for an arbitrary selection.

    The preview fails if a selection no longer exists or validators reject it.
    Never mutate the live session or perform blind ID replacement.
    """
    selected = tuple(selected)
    if not editable_name(selected):
        raise ValueError("Sélection non éditable")
    name = new_name.strip()
    if not name:
        raise ValueError("Le nom ne peut pas être vide")
    if len({r.key for r in selected}) != len(selected):
        raise ValueError("Sélection dupliquée")

    def transform(content, project):
        for target in _targets(content, selected):
            target["name"] = name
        return content, project

    plan = session.preview_pair(transform, kind="r2.inspector.rename",
                                views=("workspace", "inspector"))
    return session.apply(plan)


REFERENCE_FIELDS = frozenset({
    "link", "unit", "unit_id", "actor_id", "object_id", "target_id",
    "scene", "next_scene", "mission", "mission_id", "start_mission",
    "campaign", "campaign_id", "clip_id",
})


def reference_hints(snapshot, resource):
    """Advisory reference paths only. Not used to authorize deletion/renames."""
    data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
    found = []

    def walk(value, path, field=""):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, path + "." + str(key), key)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                walk(child, path + "[" + str(index) + "]", field)
        elif field in REFERENCE_FIELDS and value == resource.resource_id:
            found.append(path)

    walk(data["content"], "Content")
    walk(data["project"], "GameProject")
    return tuple(found[:50])
