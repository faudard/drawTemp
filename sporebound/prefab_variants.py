"""R38.2 controlled authoring variants for the existing R6 group-prefab format.

GameProject.extensions stores *only provenance and editable scalar overrides*.
Canonical Content remains the sole owner of placed map objects and units.
The source group prefab v1 is supplied explicitly; a source-hash mismatch
fails closed. Existing place_group_prefab performs geometry and ID mapping.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re

from .group_prefabs import _validate_prefab, place_group_prefab
from .model import RuleError, require

NAMESPACE = "org.drawtemp.prefabvariants"
KIND = "drawtemp_group_prefab_variant"
VERSION = 1
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
FIELDS = {
    "groups": frozenset({"name"}),
    "units": frozenset({"name", "hp", "attack", "defense"}),
    "objects": frozenset({"name", "hp", "locked", "amount"}),
}
MAX_VARIANTS = 32
MAX_INSTANCES = 128
MAX_OVERRIDES = 32


def _id(value, label):
    require(type(value) is str and _ID.fullmatch(value) is not None,
            label + " must be 1..64 ASCII identifier characters")
    return value


def _sha(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True,
                     allow_nan=False, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


def prefab_digest(prefab):
    _validate_prefab(prefab)
    return _sha(prefab)


def _patches(prefab, patches):
    require(type(patches) is list and len(patches) <= MAX_OVERRIDES,
            "Expected up to 32 variant overrides")
    targets = {(section, item["id"]): item
               for section in FIELDS for item in prefab[section]}
    edited, seen = deepcopy(prefab), set()
    affected = {(section, item["id"]): item
                for section in FIELDS for item in edited[section]}
    for patch in patches:
        require(type(patch) is dict and set(patch) == {
            "section", "id", "field", "value"}, "Invalid variant override")
        section, identifier, field = (patch[key] for key in
                                      ("section", "id", "field"))
        require(section in FIELDS and field in FIELDS[section] and
                (section, identifier) in targets,
                "Variant field or target does not exist in source prefab")
        key = (section, identifier, field)
        require(key not in seen, "Duplicate variant override")
        seen.add(key)
        old, value = targets[(section, identifier)].get(field), patch["value"]
        require(field in targets[(section, identifier)] and
                type(old) is type(value), "Override must preserve the field's type")
        require((type(value) is str and 1 <= len(value.strip()) <= 80)
                or (type(value) is int and 0 <= value <= 10000)
                or type(value) is bool, "Unsupported variant scalar value")
        affected[(section, identifier)][field] = deepcopy(value)
    return edited


def validate_variant(prefab, variant):
    digest = prefab_digest(prefab)
    require(type(variant) is dict and set(variant) == {
        "kind", "version", "id", "base_sha256", "overrides"},
        "Variant descriptor has unknown or missing fields")
    require(variant["kind"] == KIND and type(variant["version"]) is int
            and variant["version"] == VERSION, "Unsupported prefab variant schema")
    _id(variant["id"], "Variant ID")
    require(variant["base_sha256"] == digest,
            "Prefab changed since variant authoring; rebase it explicitly")
    resolved = _patches(prefab, variant["overrides"])
    _validate_prefab(resolved)
    return deepcopy(variant)


def resolve_variant(prefab, variant, instance_overrides=()):
    validate_variant(prefab, variant)
    overrides = list(instance_overrides)
    # Overrides on a placed instance always win over inherited variant values.
    return _validate_prefab(_patches(
        _patches(prefab, variant["overrides"]), overrides))


def _empty():
    return {"variants": [], "instances": []}


def _read(project):
    envelope = project.get("extensions", {}).get(NAMESPACE)
    return deepcopy(envelope["data"]) if envelope is not None else _empty()


def _write(project, data):
    extensions = project.setdefault("extensions", {})
    ids = sorted({instance["mission_id"] for instance in data["instances"]})
    extensions[NAMESPACE] = {
        "schema_version": VERSION,
        "data": deepcopy(data),
        "references": [{"kind": "mission", "id": mid} for mid in ids],
    }


def _stored(data, variant_id):
    return next((row for row in data["variants"] if row["id"] == variant_id), None)


def validate_prefab_extensions(envelope, content):
    """Validate persisted provenance and canonical IDs during GameProject load.

    Source files are deliberately not opened during project loading. Their
    digests are checked whenever the author requests placement or an update.
    """
    require(type(envelope) is dict and envelope.get("schema_version") == VERSION,
            "Unsupported prefab variant extension")
    data = envelope.get("data")
    require(type(data) is dict and set(data) == {"variants", "instances"},
            "Malformed prefab variant catalog")
    variants, instances = data["variants"], data["instances"]
    require(type(variants) is list and len(variants) <= MAX_VARIANTS and
            type(instances) is list and len(instances) <= MAX_INSTANCES,
            "Prefab catalog size limit")
    keys = set()
    for v in variants:
        require(type(v) is dict and set(v) == {
            "kind", "version", "id", "base_sha256", "overrides"},
            "Malformed stored prefab variant")
        _id(v["id"], "Variant ID")
        require(v["kind"] == KIND and type(v["version"]) is int
                and v["version"] == VERSION and
                type(v["base_sha256"]) is str and
                bool(re.fullmatch(r"[0-9a-f]{64}", v["base_sha256"])) and
                type(v["overrides"]) is list and
                len(v["overrides"]) <= MAX_OVERRIDES,
                "Invalid prefab variant metadata")
        require(v["id"] not in keys, "Duplicate prefab variant ID")
        keys.add(v["id"])
        for patch in v["overrides"]:
            require(type(patch) is dict and set(patch) ==
                    {"section", "id", "field", "value"} and
                    patch["section"] in FIELDS and
                    patch["field"] in FIELDS[patch["section"]],
                    "Invalid persisted prefab override")
            _id(patch["id"], "Prefab member ID")
    existing_instances, occupied = set(), set()
    for instance in instances:
        require(type(instance) is dict and set(instance) == {
            "id", "variant_id", "mission_id", "base_sha256",
            "variant_sha256", "mapping", "overrides"},
            "Malformed prefab instance")
        _id(instance["id"], "Instance ID")
        mission_id = instance["mission_id"]
        require(mission_id in content.missions and
                instance["variant_id"] in keys and
                instance["base_sha256"] ==
                _stored(data, instance["variant_id"])["base_sha256"] and
                type(instance["variant_sha256"]) is str and
                bool(re.fullmatch(r"[0-9a-f]{64}", instance["variant_sha256"])),
                "Stale prefab instance source or missing mission")
        require(instance["id"] not in existing_instances, "Duplicate prefab instance ID")
        existing_instances.add(instance["id"])
        mapping = instance["mapping"]
        require(type(mapping) is dict and set(mapping) == set(FIELDS),
                "Malformed prefab instance member mapping")
        mission = content.missions[mission_id]
        available = {
            "groups": {group["id"] for group in mission.editor_groups},
            "units": {unit.id for unit in mission.units},
            "objects": {obj["id"] for obj in mission.objects},
        }
        for section in FIELDS:
            names = mapping[section]
            require(type(names) is dict, "Invalid member mapping")
            for source_id, placed_id in names.items():
                _id(source_id, "Source member")
                _id(placed_id, "Placed member")
                handle = (mission_id, section, placed_id)
                require(placed_id in available[section] and handle not in occupied,
                        "Prefab instance member was deleted or claimed twice")
                occupied.add(handle)
        require(type(instance["overrides"]) is list and
                len(instance["overrides"]) <= MAX_OVERRIDES,
                "Invalid instance overrides")
        for patch in instance["overrides"]:
            require(type(patch) is dict and set(patch) ==
                    {"section", "id", "field", "value"} and
                    patch["section"] in FIELDS and
                    patch["field"] in FIELDS[patch["section"]] and
                    patch["id"] in mapping[patch["section"]],
                    "Invalid instance override target")
    ids = sorted({x["mission_id"] for x in instances})
    require(envelope.get("references", []) ==
            [{"kind": "mission", "id": mid} for mid in ids],
            "Prefab instance mission references do not match catalog")
    return deepcopy(data)


def _require_source(source, variant):
    validate_variant(source, variant)


def _session(session):
    from drawtemp.sdk.authoring import AuthoringSession
    require(isinstance(session, AuthoringSession),
            "Expected canonical R1 AuthoringSession")


def preview_register_variant(session, prefab, variant):
    """Create a versioned descriptor; never overwrite existing variants."""
    _session(session)
    descriptor = validate_variant(prefab, variant)

    def transform(project):
        data = _read(project)
        require(_stored(data, descriptor["id"]) is None,
                "Variant already exists; use preview_update_variant")
        require(len(data["variants"]) < MAX_VARIANTS, "Variant catalog full")
        data["variants"].append(deepcopy(descriptor))
        _write(project, data)
        return project

    return session.preview_project(transform, kind="r38.prefab.register")


def _mapping(before, after, source):
    mappings = {}
    for section, field in (("groups", "editor_groups"),
                           ("units", "units"), ("objects", "objects")):
        old_ids = {row["id"] for row in before.get(field, ())}
        fresh = [row["id"] for row in after.get(field, ())
                 if row["id"] not in old_ids]
        require(len(fresh) == len(source[section]), "Prefab placement identity mismatch")
        mappings[section] = {row["id"]: identifier for row, identifier in
                             zip(source[section], fresh)}
    return mappings


def preview_place_variant(session, prefab, variant_id, mission_id, anchor,
                          instance_id, *, overrides=()):
    """Stage one R1 Content placement and GameProject provenance transaction."""
    _session(session)
    _id(instance_id, "Instance ID")
    instance_overrides = deepcopy(list(overrides))

    def transform(content, project):
        data = _read(project)
        variant = _stored(data, variant_id)
        require(variant is not None, "Unknown registered prefab variant")
        _require_source(prefab, variant)
        require(not any(row["id"] == instance_id for row in data["instances"]),
                "Prefab instance ID already exists")
        require(len(data["instances"]) < MAX_INSTANCES, "Too many prefab instances")
        resolved = resolve_variant(prefab, variant, instance_overrides)
        before = next((m for m in content["missions"] if m["id"] == mission_id), None)
        require(before is not None, "Unknown target mission")
        placed = place_group_prefab(content, mission_id, resolved, anchor)
        after = next(m for m in placed["missions"] if m["id"] == mission_id)
        data["instances"].append({
            "id": instance_id, "variant_id": variant_id,
            "mission_id": mission_id, "base_sha256": prefab_digest(prefab),
            "variant_sha256": _sha(variant), "mapping": _mapping(before, after, resolved),
            "overrides": deepcopy(instance_overrides),
        })
        _write(project, data)
        return placed, project

    return session.preview_pair(transform, mission_id=mission_id,
                                kind="r38.prefab.place",
                                views=("workspace", "inspector", "map"))


def _patch_map(prefab, variant):
    resolved = resolve_variant(prefab, variant)
    return {(section, row["id"], field): deepcopy(row[field])
            for section, fields in FIELDS.items()
            for row in resolved[section] for field in fields if field in row}


def preview_update_variant(session, prefab, replacement):
    """Update only inherited scalars, preserving per-instance overrides.

    If an author edited an inherited value directly in Content, fail *all*
    updates instead of overwriting their work or claiming false success.
    """
    _session(session)
    descriptor = validate_variant(prefab, replacement)

    def transform(content, project):
        data = _read(project)
        previous = _stored(data, descriptor["id"])
        require(previous is not None, "Variant not registered")
        _require_source(prefab, previous)
        old_values = _patch_map(prefab, previous)
        new_values = _patch_map(prefab, descriptor)
        changed = {key for key in old_values if old_values[key] != new_values[key]}
        require(old_values.keys() == new_values.keys(), "Variant structure changed")
        for instance in data["instances"]:
            if instance["variant_id"] != descriptor["id"]:
                continue
            require(instance["variant_sha256"] == _sha(previous),
                    "Instance variant revision differs; explicit rebase required")
            mission = next(m for m in content["missions"]
                           if m["id"] == instance["mission_id"])
            excluded = {(o["section"], o["id"], o["field"])
                        for o in instance["overrides"]}
            for section, source_id, field in sorted(changed - excluded):
                target_id = instance["mapping"][section].get(source_id)
                require(target_id is not None, "Missing linked prefab member")
                stored_field = "editor_groups" if section == "groups" else section
                target = next((row for row in mission.get(stored_field, ())
                               if row["id"] == target_id), None)
                require(target is not None, "Placed prefab member missing")
                require(target.get(field) == old_values[section, source_id, field],
                        "Manual edit conflict: " + instance["id"] + "/" +
                        section + "/" + source_id + "/" + field)
                target[field] = deepcopy(new_values[section, source_id, field])
            instance["variant_sha256"] = _sha(descriptor)
        data["variants"] = [
            deepcopy(descriptor) if row["id"] == descriptor["id"] else row
            for row in data["variants"]]
        _write(project, data)
        return content, project

    return session.preview_pair(transform, kind="r38.prefab.update",
                                views=("workspace", "inspector", "map"))


def preview_override_instance(session, prefab, instance_id, patches):
    """Override selected inherited fields on an existing placed instance."""
    _session(session)
    _id(instance_id, "Instance ID")
    patches = deepcopy(list(patches))

    def transform(content, project):
        data = _read(project)
        instance = next((i for i in data["instances"] if i["id"] == instance_id),
                        None)
        require(instance is not None, "Unknown prefab instance")
        variant = _stored(data, instance["variant_id"])
        _require_source(prefab, variant)
        require(instance["variant_sha256"] == _sha(variant),
                "Instance revision mismatch")
        old = resolve_variant(prefab, variant, instance["overrides"])
        changed = _patch_map(prefab, variant)
        effective = _patches(old, patches)
        newly = {(s, row["id"], f): row[f] for s, fields in FIELDS.items()
                 for row in effective[s] for f in fields if f in row}
        applied = set()
        mission = next(m for m in content["missions"]
                       if m["id"] == instance["mission_id"])
        for section, source_id, field in sorted(changed):
            key = (section, source_id, field)
            prior = next((row[field] for row in old[section]
                          if row["id"] == source_id and field in row), None)
            wanted = newly[key]
            if wanted == prior:
                continue
            stored_field = "editor_groups" if section == "groups" else section
            placed_id = instance["mapping"][section][source_id]
            target = next(row for row in mission[stored_field]
                          if row["id"] == placed_id)
            require(target.get(field) == prior, "Manual instance edit conflict")
            target[field] = deepcopy(wanted)
            applied.add(key)
        overrides = {(p["section"], p["id"], p["field"]): p
                     for p in instance["overrides"]}
        for patch in patches:
            key = (patch["section"], patch["id"], patch["field"])
            if key in applied or key in overrides:
                overrides[key] = deepcopy(patch)
        require(len(overrides) <= MAX_OVERRIDES, "Too many instance overrides")
        instance["overrides"] = [overrides[key] for key in sorted(overrides)]
        _write(project, data)
        return content, project

    return session.preview_pair(transform, kind="r38.prefab.override",
                                views=("workspace", "inspector", "map"))
