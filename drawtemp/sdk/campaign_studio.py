"""R10 Campaign/World/Siege Studio facade over canonical DrawTemp rules.

Authoring mutations are one Content/GameProject transaction; simulation never
writes a game slot. The symbolic route explorer is not a tactical certificate.
This module must remain importable without Qt or Tk.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from drawtemp.core import Content, GameProject, RuleError
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.campaign_flow import audit_campaign, inspect_campaign
from sporebound.campaign_flow_authoring import (
    build_effect, change_condition, change_effect,
)
from sporebound.campaign_flow_simulation import CampaignSimulation
from sporebound.campaign_graph import inspect_graph, set_link
from sporebound.campaign_path_certification import certify_path
from sporebound.game_export4 import export_game
from sporebound.siege_authoring import (
    add_front, new_blueprint, replace_siege, set_finale, timeline_preview,
)
from sporebound.world_map import (
    default_world, upsert_location, world_projection,
)


class CampaignStudio:
    """Single transactional document owner and read-only campaign sandbox."""

    def __init__(self, authoring: AuthoringSession, campaign_id: str = "main"):
        self.authoring = authoring
        self.campaign_id = campaign_id
        self._sandbox = None
        self._models()  # Fail early on invalid documents and campaign IDs.

    @classmethod
    def open(cls, content_path, campaign_id="main"):
        return cls(AuthoringSession.open(content_path), campaign_id)

    @classmethod
    def new(cls, content, project, campaign_id="main"):
        return cls(AuthoringSession.new(content, project), campaign_id)

    @property
    def revision(self):
        return self.authoring.revision

    def _models(self):
        document = self.authoring.snapshot().to_dict()
        content = Content.from_dict(document["content"])
        project = GameProject.from_dict(document["project"], content)
        if project.campaign(self.campaign_id) is None:
            raise RuleError("Unknown campaign: " + self.campaign_id)
        return content, project

    def select_campaign(self, campaign_id):
        content, project = self._models()
        if project.campaign(campaign_id) is None:
            raise RuleError("Unknown campaign: " + str(campaign_id))
        self.campaign_id = campaign_id
        self._sandbox = None

    def _apply(self, transform, kind):
        plan = self.authoring.preview_pair(
            transform, kind=kind, views=("workspace", "inspector"))
        result = self.authoring.apply(plan)
        self._sandbox = None
        return result

    def _project_edit(self, editor, kind):
        def change(content_data, project_data):
            content = Content.from_dict(content_data)
            project = GameProject.from_dict(project_data, content)
            replacement = editor(content, project)
            return content_data, replacement.to_dict()
        return self._apply(change, kind)

    def overview(self):
        content, project = self._models()
        starts = [project.campaign(self.campaign_id)["start_mission"]]
        graph = inspect_graph(content, starts)
        progress = project.new_game(self.campaign_id, content)
        campaigns = deepcopy(project.campaigns)
        return {
            "revision": self.revision,
            "dirty": self.authoring.snapshot().dirty,
            "campaigns": campaigns,
            "active_campaign": self.campaign_id,
            "missions": [
                {"id": mid, "name": mission.name, "reward": mission.reward,
                 "next_missions": list(mission.next_missions)}
                for mid, mission in content.missions.items()
            ],
            "graph": graph,
            "world": world_projection(project.world, content),
            "scenes": deepcopy(project.story.get("scenes", [])),
            "flow": deepcopy(project.campaign_flow),
            "state": inspect_campaign(progress, project.campaign_flow),
            "sieges": [deepcopy(s) for s in project.sieges
                       if s["campaign_id"] == self.campaign_id],
        }

    def link_missions(self, origin, destination, enabled=True):
        return self._apply(
            lambda content, project: (
                set_link(content, origin, destination, enabled), project),
            "r10-mission-link")

    def set_start_mission(self, mission_id):
        def edit(content, project):
            data = project.to_dict()
            campaign = next(x for x in data["campaigns"]
                            if x["id"] == self.campaign_id)
            campaign["start_mission"] = mission_id
            return GameProject.from_dict(data, content)
        return self._project_edit(edit, "r10-start-mission")

    def set_condition(self, target, name, kind, key, value):
        """Typed gate or ending; no raw expression JSON editing."""
        return self._project_edit(
            lambda content, project: change_condition(
                project, content, target, name, "replace",
                kind=kind, key=key, value=value),
            "r10-condition")

    def remove_condition(self, target, name):
        return self._project_edit(
            lambda content, project: change_condition(
                project, content, target, name, "delete"),
            "r10-condition-remove")

    def add_consequence(self, mission_id, outcome, kind, name="", value=""):
        def edit(content, project):
            effect = build_effect(kind, name, value, content=content)
            return change_effect(project, content, mission_id, outcome,
                                 "add", effect=effect)
        return self._project_edit(edit, "r10-consequence")

    def initialize_world(self, theme="parchment"):
        def edit(content, project):
            data = project.to_dict()
            if data.get("world"):
                raise RuleError("World already initialized; use move_location")
            data["world"] = default_world(content, project.campaigns, theme=theme)
            return GameProject.from_dict(data, content)
        return self._project_edit(edit, "r10-world-create")

    def move_location(self, mission_id, x, y, region=""):
        def edit(content, project):
            data = project.to_dict()
            data["world"] = upsert_location(
                project.world, content, project.campaigns,
                mission_id, (x, y), region=region)
            return GameProject.from_dict(data, content)
        return self._project_edit(edit, "r10-world-location")

    def create_siege(self, siege_id, mission_id, front="approach"):
        return self._project_edit(
            lambda content, project: replace_siege(
                project, content,
                new_blueprint(siege_id, self.campaign_id, mission_id, front=front)),
            "r10-siege-create")

    def _edit_siege(self, siege_id, modify, kind):
        def edit(content, project):
            blueprint = next(
                (row for row in project.sieges
                 if row["id"] == siege_id and
                 row["campaign_id"] == self.campaign_id), None)
            if blueprint is None:
                raise RuleError("Unknown siege in this campaign: " + str(siege_id))
            return replace_siege(project, content, modify(blueprint))
        return self._project_edit(edit, kind)

    def add_siege_front(self, siege_id, front, mission_id, *,
                        strength=10, opposition=10, doctrine="hold"):
        return self._edit_siege(
            siege_id,
            lambda blueprint: add_front(
                blueprint, front, mission_id, strength=strength,
                opposition=opposition, doctrine=doctrine),
            "r10-siege-front")

    def set_siege_finale(self, siege_id, final, required):
        return self._edit_siege(
            siege_id, lambda blueprint: set_finale(blueprint, final, required),
            "r10-siege-finale")

    def siege_timeline(self, siege_id, *, turns=8):
        _content, project = self._models()
        blueprint = next(
            (row for row in project.sieges
             if row["id"] == siege_id and row["campaign_id"] == self.campaign_id),
            None)
        if blueprint is None:
            raise RuleError("Unknown siege")
        return deepcopy(timeline_preview(blueprint, turns=turns))

    def sandbox(self):
        if self._sandbox is None:
            content, project = self._models()
            self._sandbox = CampaignSimulation(
                content, project, self.campaign_id)
        return self._sandbox

    def simulation_inspect(self):
        return self.sandbox().inspect()

    def simulation_actions(self):
        return self.sandbox().actions()

    def simulation_choose(self, choice_id):
        return self.sandbox().choose(choice_id)

    def simulation_resolve(self, mission_id, outcome):
        return self.sandbox().resolve(mission_id, outcome)

    def simulation_fork(self, label="Alternative"):
        return self.sandbox().fork(label)

    def simulation_select(self, node_id):
        return self.sandbox().select(node_id)

    def simulation_coverage(self):
        return self.sandbox().coverage()

    def audit(self, *, max_states=384, max_depth=32):
        content, project = self._models()
        return audit_campaign(
            content, project, self.campaign_id,
            max_states=max_states, max_depth=max_depth)

    def candidate_path(self, *, seed=7):
        """A proposed path, explicitly NOT a tactical certificate."""
        return self.sandbox().certification_plan(seed=seed)

    def certify(self, plan, *, max_commands=1600):
        """Real tactical Battle commands and checkpoint replay; may take time."""
        content, project = self._models()
        if plan.get("campaign") != self.campaign_id:
            raise RuleError("Certificate targets another campaign")
        return certify_path(content, project, deepcopy(plan),
                            max_commands=max_commands)

    def export_source_bundle(self, asset_root, destination):
        """Canonical validated ZIP; requires Python + Tk, not a native Qt binary."""
        content, project = self._models()
        return export_game(content, project, Path(asset_root), Path(destination))

    def undo(self):
        transition = self.authoring.undo()
        self._sandbox = None
        return transition

    def redo(self):
        transition = self.authoring.redo()
        self._sandbox = None
        return transition

    def save(self):
        return self.authoring.save()

    def save_as(self, path):
        return self.authoring.save_as(path)
