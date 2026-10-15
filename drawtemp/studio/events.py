"""R9 Event & Narrative Studio adapter over the canonical tactical/story authoring APIs.

This layer has no Qt imports, duplicate event schema or event interpreter.
Every edit is a revisioned Content + GameProject transaction in R1's
AuthoringSession. Live Battle/GameSession objects are never edited.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringSession
from sporebound import event_composer, event_graph, story_authoring
from sporebound import event_pages
from sporebound.entity_event_studio import author_gate_sequence
from sporebound.event_branch_builder import author_choice_fork
from sporebound.branch_qa_363 import (audit_branch_coverage, format_branch_qa,
                                      probe_story_choices, probe_tactical_branches)
from drawtemp.studio.event_debug_controller import EventDebugController
from drawtemp.studio.event_command_catalog import tactical_action, story_effect
from drawtemp.studio.event_presentation import add_event_cue
from drawtemp.render.iso_scene import scene_from_mission
from sporebound.event_context import inspect_event, preview_event, format_preview_report
from sporebound.event_debugger import EventDebugger, format_debug_report


class EventStudio:
    """Headless view-model shared by the Qt event workspace and its tests."""

    def __init__(self, session: AuthoringSession):
        self.session = session

    def documents(self):
        return self.session.snapshot().to_dict()

    def missions(self):
        return [(m["id"], m["name"]) for m in self.documents()["content"]["missions"]]

    def _mission(self, mission_id):
        for mission in self.documents()["content"]["missions"]:
            if mission["id"] == mission_id:
                return mission
        raise ValueError("Unknown mission: " + mission_id)

    def events(self, mission_id):
        return deepcopy(self._mission(mission_id).get("triggers", []))

    def event(self, mission_id, event_id):
        for row in self.events(mission_id):
            if row["id"] == event_id:
                return row
        raise ValueError("Unknown event: " + event_id)

    def inspect(self, mission_id, event_id):
        state = self.documents()
        content = Content.from_dict(state["content"])
        project = GameProject.from_dict(state["project"], content)
        return inspect_event(state["content"], mission_id, event_id, project)

    def _commit(self, mission_id, kind, transform):
        plan = self.session.preview_pair(
            lambda content, project: (transform(content), project),
            kind="event." + kind, mission_id=mission_id,
            views=("renderer", "minimap", "inspector", "workspace"))
        return self.session.apply(plan)

    def create(self, mission_id, event_id, condition, actions):
        """Never silently overwrite an event with a reused ID."""
        def edit(data):
            mission = next(m for m in data["missions"] if m["id"] == mission_id)
            if any(e["id"] == event_id for e in mission.get("triggers", [])):
                raise ValueError("Event already exists: " + event_id)
            return event_composer.save_event(data, mission_id, event_id,
                                             condition, actions)
        return self._commit(mission_id, "create", edit)

    def set_condition(self, mission_id, event_id, condition):
        return self._commit(mission_id, "condition", lambda data:
                            event_graph.update_condition(data, mission_id, event_id,
                                                         condition))

    def add_predicate(self, mission_id, event_id, predicate, *, join="all", negate=False):
        return self._commit(mission_id, "predicate", lambda data:
                            event_graph.extend_condition(data, mission_id, event_id,
                                                         predicate, join=join,
                                                         negate=negate))

    def edit_predicate(self, mission_id, event_id, path, *, operation,
                       predicate=None, join="all", direction=0):
        return self._commit(mission_id, "predicate", lambda data:
                            event_graph.edit_composite_node(
                                data, mission_id, event_id, path, operation=operation,
                                predicate=predicate, join=join, direction=direction))

    def clear_predicates(self, mission_id, event_id):
        return self._commit(mission_id, "predicate", lambda data:
                            event_graph.clear_composite_condition(data, mission_id,
                                                                  event_id))

    def add_action(self, mission_id, event_id, action, *, index=None):
        return self._commit(mission_id, "action", lambda data:
                            event_graph.add_action(data, mission_id, event_id,
                                                   action, index=index))

    def replace_action(self, mission_id, event_id, index, action):
        return self._commit(mission_id, "action", lambda data:
                            event_graph.update_action(data, mission_id, event_id,
                                                      index, action))

    def event_pages(self, mission_id, event_id):
        """Base is always available; extra pages are stored in this trigger."""
        trigger = self.event(mission_id, event_id)
        base = {"id": "base", "priority": 0,
                "enabled": trigger.get("enabled", True),
                "repeat": trigger.get("repeat", False),
                "cooldown_ticks": trigger.get("cooldown_ticks", 1),
                "condition": trigger["condition"],
                "actions": deepcopy(trigger["actions"])}
        return [base, *deepcopy(trigger.get("pages", []))]

    def add_page(self, mission_id, event_id, *, page_id, priority,
                 condition, actions, enabled=True, repeat=False,
                 cooldown_ticks=1):
        return self._commit(
            mission_id, "page-create",
            lambda data: event_pages.create_page(
                data, mission_id, event_id, page_id=page_id,
                priority=priority, condition=condition, actions=actions,
                enabled=enabled, repeat=repeat,
                cooldown_ticks=cooldown_ticks))

    def configure_page(self, mission_id, event_id, page_id, *,
                       priority=None, enabled=None, repeat=None,
                       cooldown_ticks=None):
        return self._commit(
            mission_id, "page-configure",
            lambda data: event_pages.update_page(
                data, mission_id, event_id, page_id,
                priority=priority, enabled=enabled, repeat=repeat,
                cooldown_ticks=cooldown_ticks))

    def delete_page(self, mission_id, event_id, page_id):
        return self._commit(
            mission_id, "page-delete",
            lambda data: event_pages.remove_page(data, mission_id,
                                                 event_id, page_id))

    def edit_page(self, mission_id, event_id, page_id, *,
                  condition=None, actions=None):
        return self._commit(
            mission_id, "page-commands",
            lambda data: event_pages.update_page_commands(
                data, mission_id, event_id, page_id,
                condition=condition, actions=actions))

    def add_tactical_command(self, mission_id, event_id, kind, fields):
        """Every action goes through the legacy registered rule contract."""
        return self.add_action(mission_id, event_id, tactical_action(kind, fields))

    def replace_tactical_command(self, mission_id, event_id, index, kind, fields):
        return self.replace_action(mission_id, event_id, index,
                                   tactical_action(kind, fields))

    def add_presentation_cue(self, mission_id, event_id, *, clip_id,
                             clip_name, kind, cue_id,
                             start_ms=0, duration_ms=1000, fields=None):
        """Typed dialogue/audio/actor/camera/FX on the existing Player cinematic hook."""
        self.event(mission_id, event_id)
        return self._pair(
            mission_id, "presentation-cue",
            lambda data, project: (
                data, add_event_cue(
                    project, mission_id, event_id,
                    clip_id=clip_id, clip_name=clip_name,
                    kind=kind, cue_id=cue_id,
                    start_ms=start_ms, duration_ms=duration_ms,
                    fields=fields)))

    def add_story_effect(self, mission_id, scene_id, choice_id, kind, fields):
        """Change a REAL StoryBook choice's variables/items as one R1 transaction."""
        payload = story_effect(kind, fields)
        return self._pair(
            mission_id, "story-choice-effect",
            lambda data, project: (
                data, story_authoring.add_effect(
                    project, Content.from_dict(data), scene_id, choice_id,
                    payload)))

    def iso_scene(self, mission_id):
        """Canonical Content → shared R3 Renderer scene, detached from the editor."""
        from sporebound.tactical_rpg3 import authored_rules_for_document
        data = self.documents()["content"]
        content = Content.from_dict(data, rules=authored_rules_for_document(data))
        return scene_from_mission(content.missions[mission_id])

    def move_action(self, mission_id, event_id, index, direction):
        return self._commit(mission_id, "action", lambda data:
                            event_graph.reorder_action(data, mission_id, event_id,
                                                       index, direction))

    def remove_action(self, mission_id, event_id, index):
        return self._commit(mission_id, "action", lambda data:
                            event_graph.remove_action(data, mission_id, event_id, index))

    def link(self, mission_id, event_id, predecessor_id, *, any_of=False):
        fn = event_graph.link_alternative if any_of else event_graph.link_event
        return self._commit(mission_id, "link", lambda data:
                            fn(data, mission_id, event_id, predecessor_id))

    def unlink(self, mission_id, event_id, predecessor_id, *, any_of=False):
        fn = event_graph.unlink_alternative if any_of else event_graph.unlink_event
        return self._commit(mission_id, "link", lambda data:
                            fn(data, mission_id, event_id, predecessor_id))

    def schedule(self, mission_id, event_id, **kwargs):
        return self._commit(mission_id, "schedule", lambda data:
                            event_graph.configure_schedule(
                                data, mission_id, event_id, **kwargs))

    def delete(self, mission_id, event_id):
        return self._commit(mission_id, "delete", lambda data:
                            event_graph.delete_event(data, mission_id, event_id))

    def duplicate(self, mission_id, event_id, new_id):
        return self._commit(mission_id, "duplicate", lambda data:
                            event_graph.duplicate_event(data, mission_id, event_id, new_id))

    def move_event(self, mission_id, event_id, direction):
        return self._commit(mission_id, "order", lambda data:
                            event_graph.reorder_event(data, mission_id, event_id,
                                                      direction))

    def _pair(self, mission_id, kind, edit):
        def transform(content, project):
            game_project = GameProject.from_dict(project, Content.from_dict(content))
            new_content, new_project = edit(content, game_project)
            if isinstance(new_project, GameProject):
                new_project = new_project.to_dict()
            return new_content, new_project
        return self.session.apply(self.session.preview_pair(
            transform, kind="event." + kind, mission_id=mission_id,
            views=("renderer", "minimap", "inspector", "workspace")))

    def create_scene(self, mission_id, scene_id, title, text, *, speaker=""):
        """A scene is stored only in GameProject.story; event references remain canonical."""
        return self._pair(mission_id, "scene", lambda data, project:
                          (data, story_authoring.create_scene(
                              project, Content.from_dict(data), scene_id, title, text,
                              speaker=speaker)))

    def bind_scene(self, mission_id, event_id, scene_id):
        return self._pair(mission_id, "scene-binding", lambda data, project:
                          (data, story_authoring.set_tactical_scene(
                              project, Content.from_dict(data), mission_id,
                              event_id, scene_id)))

    def gate_wizard(self, mission_id, **kwargs):
        """Full lever/door/dialogue/cinematic sequence, one cross-file undo step."""
        return self._pair(mission_id, "gate-wizard", lambda data, project:
                          author_gate_sequence(data, project, mission_id, **kwargs))

    def create_choice_fork(self, mission_id, *, origin_event_id, origin_cell,
                           scene_id, title, text, branches,
                           reunion_event_id="", reunion_message="", speaker=""):
        """One Undo transaction for the narrative choice scene and tactical forks.

        All branching semantics are delegated to the existing production
        author_choice_fork validator; no sidecar editor graph is persisted.
        """
        return self._pair(
            mission_id, "choice-fork",
            lambda data, project: author_choice_fork(
                data, project, mission_id, origin_event_id=origin_event_id,
                origin_cell=origin_cell, scene_id=scene_id, title=title,
                text=text, branches=branches,
                reunion_event_id=reunion_event_id,
                reunion_message=reunion_message, speaker=speaker))

    def bind_choice(self, mission_id, event_id, scene_id, choice_id):
        """Gate an existing tactical event on a validated narrative choice."""
        return self._commit(mission_id, "choice-guard", lambda data:
                            event_graph.bind_choice(data, mission_id, event_id,
                                                    scene_id, choice_id))

    def clear_choice(self, mission_id, event_id):
        return self._commit(mission_id, "choice-guard", lambda data:
                            event_graph.clear_choice(data, mission_id, event_id))

    def branch_qa(self, mission_id, *, probe=False):
        """Read-only branch diagnostics; synthetic previews are not replay proof."""
        state = self.documents()
        content = state["content"]
        project = GameProject.from_dict(state["project"], Content.from_dict(content))
        structural = audit_branch_coverage(project.story, content, mission_id)
        results = [structural]
        if probe:
            results.extend((
                probe_story_choices(content, project),
                probe_tactical_branches(content, project, mission_id)))
        return {
            "reports": results,
            "lines": [line for report in results
                      for line in format_branch_qa(report)],
            "replay_verified": False,
        }

    def start_debug(self, mission_id, event_id, *,
                    scenario="satisfied", tick=0):
        return EventDebugController(self.session, mission_id, event_id,
                                    scenario=scenario, tick=tick)

    def graph(self, mission_id):
        return event_graph.build_event_graph(self.documents()["content"], mission_id)

    def diagnostics(self, mission_id):
        """Conservative structural checks; canonical validators own referential integrity."""
        events = self.events(mission_id)
        ids = {e["id"] for e in events}
        problems = []
        for event in events:
            for key in ("after", "after_any", "cancel_after"):
                for dependency in event.get(key, []):
                    if dependency not in ids:
                        problems.append({"event_id": event["id"],
                                         "severity": "error",
                                         "message": "Broken " + key + ": " + dependency})
            if event.get("after") and event["id"] in event["after"]:
                problems.append({"event_id": event["id"],
                                 "severity": "error",
                                 "message": "Event depends on itself"})
        graph = self.graph(mission_id)
        if graph["truncated"]:
            problems.append({"event_id": "", "severity": "warning",
                             "message": "Graph exceeds the visible node limit"})
        return problems

    def map_markers(self, mission_id):
        """Read-only trigger markers for the Qt map overlay / future R5 GPU viewport."""
        mission = self._mission(mission_id)
        objects = {obj["id"]: obj for obj in mission.get("objects", [])}
        markers = []
        for event in self.events(mission_id):
            origin = None
            if event["condition"] == "enter":
                origin = event["pos"]
            elif event["condition"] == "interact":
                obj = objects.get(event["object"])
                origin = obj["pos"] if obj else None
            if origin is not None:
                markers.append({"event_id": event["id"],
                                "pos": list(origin), "kind": "trigger"})
            for action in event["actions"]:
                if action["kind"] == "hazard":
                    markers.append({"event_id": event["id"],
                                    "pos": list(action["pos"]), "kind": "effect"})
                if action["kind"] == "spawn":
                    markers.append({"event_id": event["id"],
                                    "pos": list(action["actor"]["pos"]),
                                    "kind": "effect"})
                if action["kind"] in ("wave", "queue_wave"):
                    for actor in action["actors"]:
                        markers.append({"event_id": event["id"],
                                        "pos": list(actor["pos"]),
                                        "kind": "effect"})
        return markers

    def preview(self, mission_id, event_id, *, scenario="satisfied", tick=0):
        """Synthetic setup is always labelled; never claimed as a verified replay."""
        state = self.documents()
        report = preview_event(state["content"], mission_id, event_id,
                               scenario=scenario, tick=tick)
        return {"report": report, "lines": format_preview_report(report)}

    def debugger(self, mission_id, event_id, *, scenario="satisfied"):
        state = self.documents()
        game_project = GameProject.from_dict(
            state["project"], Content.from_dict(state["content"]))
        engine = EventDebugger(state["content"], mission_id, event_id,
                               project=game_project, scenario=scenario)
        for _ in range(len(engine.chain)):
            if engine.report()["exhausted"]:
                break
            engine.step()
        report = engine.report()
        return {"report": report, "lines": format_debug_report(report)}

    def undo(self):
        return self.session.undo()

    def redo(self):
        return self.session.redo()

    def save(self):
        return self.session.save()

    def save_as(self, path):
        return self.session.save_as(path)
