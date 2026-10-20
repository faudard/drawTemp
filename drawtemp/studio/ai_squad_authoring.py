"""R37.D3 — transactional squad role/radio authoring using the shared R1 owner."""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.advanced_ai import EXTENSION
from sporebound.ai_squad import validate_squad


class AISquadDesigner:
    """No shadow project: one validated preview, one canonical Undo transaction."""

    def __init__(self, session):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected shared AuthoringSession")
        self.session = session

    def members(self):
        project = self.session.snapshot().to_dict()["project"]
        document = project.get("extensions", {}).get(
            EXTENSION, {}).get("data", {})
        return [
            {"id": agent["id"], "mode": agent["mode"],
             "sensor": "sensor" in agent,
             "squad": deepcopy(agent.get("squad"))}
            for agent in document.get("agents", [])
        ]

    def preview(self, actor_id, squad, *, expected_revision=None):
        """Stage an optional binding to a sensor-equipped R35 actor."""
        if type(actor_id) is not str or actor_id not in {
                row["id"] for row in self.members()}:
            raise ValueError("Unknown R37 actor")
        if expected_revision is not None and expected_revision != self.session.revision:
            raise ValueError("Stale R37 squad editor; reload changes")
        validated = validate_squad(squad) if squad is not None else None

        def edit(project):
            agents = project["extensions"][EXTENSION]["data"]["agents"]
            current = next(a for a in agents if a["id"] == actor_id)
            if validated is None:
                current.pop("squad", None)
            else:
                current["squad"] = deepcopy(validated)
            return project

        return self.session.preview_project(edit, kind="r37.ai-squad")

    def apply(self, plan):
        return self.session.apply(plan)
