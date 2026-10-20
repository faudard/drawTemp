"""R31.G — transaction-bound Studio authoring of tactical-to-campaign mappings."""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.logic_graph import LogicGraphError
from sporebound.logic_campaign_bridge import (
    EXTENSION, OUTCOMES, bridge_bindings,
)
from sporebound.logic_variables import _VARIABLE


def configure_export(session, mission, source, target, *, result="victory"):
    """Return a validated R1 project preview; no write without apply()."""
    if not isinstance(session, AuthoringSession):
        raise TypeError("Shared AuthoringSession required")
    if (type(mission) is not str or type(source) is not str or
            type(target) is not str or type(result) is not str or
            _VARIABLE.fullmatch(source) is None or
            _VARIABLE.fullmatch(target) is None or result not in OUTCOMES):
        raise LogicGraphError("invalid_binding", "R31.G mapping parameters are invalid")

    def edit(project):
        updated = deepcopy(project)
        from sporebound.game_project import GameProject
        from sporebound.logic_campaign_bridge import validate_bridge
        # Authoring validation uses the paired Content snapshot, not the UI.
        raw_content = session.snapshot().to_dict()["content"]
        from sporebound.model import Content
        content = Content.from_dict(raw_content)
        existing = updated.setdefault("extensions", {}).get(EXTENSION)
        mappings = bridge_bindings(
            GameProject.from_dict(updated, content)) if existing is not None else []
        if any(row["target"] == target for row in mappings):
            raise LogicGraphError("duplicate_binding",
                                  "Campaign flag is already exported")
        mappings.append({"mission": mission, "source": source,
                         "target": target, "result": result})
        updated["extensions"][EXTENSION] = {
            "schema_version": 1, "data": {"bindings": mappings},
            "references": [
                {"kind": "mission", "id": mid}
                for mid in sorted({row["mission"] for row in mappings})],
        }
        validate_bridge(GameProject.from_dict(updated, content), content)
        return updated

    return session.preview_project(edit, kind="r31.logic.campaign-export")


def remove_export(session, target):
    """Removal is explicit and is also R1 Undo/Redo-able."""
    if not isinstance(session, AuthoringSession):
        raise TypeError("Shared AuthoringSession required")
    if type(target) is not str:
        raise LogicGraphError("invalid_binding", "Target flag must be text")

    def edit(project):
        updated = deepcopy(project)
        extension = updated.get("extensions", {}).get(EXTENSION)
        if extension is None:
            raise LogicGraphError("unknown_binding", "No campaign mappings")
        from sporebound.game_project import GameProject
        from sporebound.model import Content
        content = Content.from_dict(session.snapshot().to_dict()["content"])
        mappings = bridge_bindings(GameProject.from_dict(updated, content))
        if not any(row["target"] == target for row in mappings):
            raise LogicGraphError("unknown_binding", "Campaign flag mapping not found")
        mappings = [row for row in mappings if row["target"] != target]
        if mappings:
            updated["extensions"][EXTENSION] = {
                "schema_version": 1, "data": {"bindings": mappings},
                "references": [
                    {"kind": "mission", "id": mid}
                    for mid in sorted({row["mission"] for row in mappings})],
            }
        else:
            del updated["extensions"][EXTENSION]
            if not updated["extensions"]:
                del updated["extensions"]
        return updated

    return session.preview_project(edit, kind="r31.logic.campaign-unexport")
