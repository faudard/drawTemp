"""R8.C: document-scoped integrity, variable usage and safe bulk renaming.

Only canonical Content v1 / GameProject fields are changed. Campaign saves,
replays and exported packages are external artifacts: callers must explicitly
acknowledge that their identifiers cannot be rewritten automatically.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass

from sporebound.model import RuleError, require

RENAMABLE = frozenset({"skills", "jobs", "equipment", "archetypes", "flags"})
PROJECT_FLAG_FIELDS = ("story", "campaign_flow", "battle_support")


@dataclass(frozen=True)
class FlagUse:
    identifier: str
    document: str
    path: str
    context: str
    value_type: str


def _visit(node, path=()):
    """Yield actual dictionary keys and values with a stable readable path."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = (*path, key)
            yield here, key, value, node
            yield from _visit(value, here)
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from _visit(value, (*path, index))


def _pointer(path):
    return "/" + "/".join(str(value).replace("~", "~0").replace("/", "~1")
                         for value in path)


def _flag_uses(document, source):
    for path, key, value, parent in _visit(document):
        if key != "flag" or not isinstance(value, str):
            continue
        parent_kind = parent.get("kind", "")
        if parent_kind in ("set_flag", "add_flag"):
            context = "write"
            value_type = (type(parent.get("value")).__name__
                          if parent_kind == "set_flag" else "int")
        elif any(x in parent for x in ("eq", "gte", "lte")):
            context = "condition"
            typed = next((parent.get(k) for k in ("eq", "gte", "lte") if k in parent), None)
            value_type = type(typed).__name__
        else:
            context, value_type = "reference", "unknown"
        yield FlagUse(value, source, _pointer(path), context, value_type)


def flag_usages(content, project):
    """Cross-document read/write inventory, without adding a shadow variable DB."""
    items = list(_flag_uses(content.get("missions", []), "Content.missions"))
    for section in PROJECT_FLAG_FIELDS:
        items.extend(_flag_uses(project.get(section, {}), "GameProject." + section))
    return tuple(sorted(items, key=lambda row: (row.identifier, row.document, row.path)))


def flags(content, project):
    grouped = defaultdict(list)
    for use in flag_usages(content, project):
        grouped[use.identifier].append(use)
    return dict(sorted((key, tuple(values)) for key, values in grouped.items()))


def _identifier(new_id):
    require(isinstance(new_id, str) and 0 < len(new_id) <= 64
            and all(ch.isalnum() or ch in "_-" for ch in new_id)
            and new_id == new_id.strip(),
            "Invalid resource id")


def _replace_key(document, key, old, new):
    """Rewrite semantic value references, never arbitrary free text/labels."""
    changed = 0
    for path, field, value, container in _visit(document):
        if field == key and value == old:
            container[field] = new
            changed += 1
    return changed


def _rename_skills(content, project, old, new):
    skills = content["skills"]
    require(any(row["id"] == old for row in skills), "Unknown skill")
    require(not any(row["id"] == new for row in skills), "Skill already exists")
    for row in skills:
        if row["id"] == old:
            row["id"] = new
    for path, key, value, container in _visit(content):
        if key == "skills":
            if isinstance(value, list):
                # Unit/archetype/talent lists, not a text search.
                container[key] = [new if item == old else item for item in value]
            elif isinstance(value, dict) and old in value:
                require(new not in value, "Duplicate job skill key")
                value[new] = value.pop(old)
        elif key in ("skill", "skill_id") and value == old:
            container[key] = new
    _replace_key(project, "skill", old, new)


def _rename_jobs(content, project, old, new):
    jobs = content.get("jobs", {})
    require(old in jobs, "Unknown job")
    require(new not in jobs, "Job already exists")
    jobs[new] = jobs.pop(old)
    for row in jobs.values():
        if row.get("requires", "") == old:
            row["requires"] = new
    for doc in (content, project):
        for key in ("job", "job_id"):
            _replace_key(doc, key, old, new)


def _rename_archetypes(content, project, old, new):
    collection = content.get("archetypes", {})
    require(old in collection, "Unknown archetype")
    require(new not in collection, "Archetype already exists")
    collection[new] = collection.pop(old)
    _replace_key(content, "archetype", old, new)
    _replace_key(project, "archetype", old, new)


def _rename_equipment(content, project, old, new):
    collection = content.get("equipment", {})
    require(old in collection, "Unknown equipment")
    require(new not in collection, "Equipment already exists")
    collection[new] = collection.pop(old)
    for doc in (content, project):
        _replace_key(doc, "item", old, new)


def _rename_flags(content, project, old, new):
    inventory = flags(content, project)
    require(old in inventory, "Unknown flag")
    require(new not in inventory, "Flag already exists")
    for doc in (content, project):
        _replace_key(doc, "flag", old, new)


def renamed_documents(content, project, family, old, new):
    """Pure revision-ready transform; AuthoringSession validates BOTH docs."""
    require(family in RENAMABLE, "This resource cannot be renamed safely")
    _identifier(new)
    require(isinstance(old, str) and old and old != new,
            "Choose a different identifier")
    content, project = deepcopy(content), deepcopy(project)
    {
        "skills": _rename_skills, "jobs": _rename_jobs,
        "archetypes": _rename_archetypes, "equipment": _rename_equipment,
        "flags": _rename_flags,
    }[family](content, project, old, new)
    return content, project


class IntegrityEditor:
    """R8.C references and refactoring; uses the same R1 history as R8.A/B."""

    def __init__(self, session):
        from drawtemp.sdk.authoring import AuthoringSession
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected AuthoringSession")
        self.session = session

    def flag_usages(self):
        pair = self.session.snapshot().to_dict()
        return flag_usages(pair["content"], pair["project"])

    def flags(self):
        pair = self.session.snapshot().to_dict()
        return flags(pair["content"], pair["project"])

    def plan_rename(self, family, old, new, *, acknowledge_external_saves=False):
        """External campaign slots/replays are never rewritten silently."""
        require(acknowledge_external_saves,
                "Renaming can invalidate external saves/replays; explicit acknowledgement required")
        return self.session.preview_pair(
            lambda content, project: renamed_documents(content, project, family, old, new),
            kind="r8-reference-rename",
            views=("workspace", "inspector"))

    def rename(self, family, old, new, *, acknowledge_external_saves=False):
        return self.session.apply(self.plan_rename(
            family, old, new,
            acknowledge_external_saves=acknowledge_external_saves))

    def plan_bulk(self, selections, fields):
        """One guarded edit for all instances; rejects duplicates and mixed kinds."""
        from drawtemp.studio.rpg_database import DatabaseEditor
        selections = tuple(selections)
        require(bool(selections) and isinstance(fields, dict) and bool(fields),
                "Choose resources and properties")
        require(len(set(selections)) == len(selections), "Duplicate selected resource")
        require(all(isinstance(row, tuple) and len(row) == 3
                    and row[0] in {"archetypes", "actors", "jobs", "skills", "equipment"}
                    for row in selections), "Invalid resource selection")
        require(len({row[0] for row in selections}) == 1,
                "Bulk edits require resources from one family")
        return DatabaseEditor(self.session).preview_many(
            [(family, "update", identifier, mission_id, deepcopy(fields))
             for family, identifier, mission_id in selections])

    def apply_bulk(self, selections, fields):
        return self.session.apply(self.plan_bulk(selections, fields))
