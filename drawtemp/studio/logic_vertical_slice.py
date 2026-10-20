"""R31.H — one-click authored Jeanne quest vertical slice, fail-closed.

This is a *recipe*, not a second mission/playback engine. It produces one R1
cross-document preview after validating a detached R1 Studio working copy.
No JSON hand-edit, UI fake state, runtime mocking or extra save schema.

Only the unmodified R0 reference mission/story are accepted: installing into
an arbitrary user mission would silently overwrite its objective and dialogue.
Other unrelated project assets/extensions are retained.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.logic_campaign import configure_export
from drawtemp.sdk.logic_graph import LogicGraphError, graphs_from_project
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.logic_graph_draft import LogicGraphDraft
from sporebound.logic_vertical_objective import OBJECTIVE, CHEST

GRAPH = "r31h_chest"
FLAG = "r31_chest_opened"
QUEST = "r31_quest_finished"
REWARD_SCENE = "r31h_reward"
CHEST_LOOT = 40
STORY_REWARD = 30


def _fail(text):
    raise LogicGraphError("r31h_reference_only", text)


def _reference_stage(content, project):
    reference_content, reference_project_manifest = reference_project()
    reference_raw = reference_content.to_dict()
    reference_mission = next(
        m for m in reference_raw["missions"] if m["id"] == MISSION)
    actual = next((m for m in content["missions"] if m["id"] == MISSION), None)
    if actual != reference_mission:
        _fail("R31.H can only install on the unmodified R0 Jeanne reference mission")
    if project.get("story", {}) != reference_project_manifest.story:
        _fail("R31.H can only replace the unmodified reference introduction")
    if any(row["id"] == GRAPH for row in graphs_from_project(project)):
        _fail("R31.H quest already authored")
    return actual


def _build_stage(content, project):
    mission = _reference_stage(content, project)
    mission["objective"] = OBJECTIVE
    mission["goal"] = [[6, 4]]
    # Leave the canonical original hero/mentor and lever/door intact.
    # Keyed door opens only through the existing lever interaction.
    door = next(row for row in mission["objects"] if row["id"] == "gate")
    door["locked"] = True
    door["open"] = False
    mission["objects"].append({
        "id": CHEST, "kind": "chest", "pos": [5, 4],
        "amount": CHEST_LOOT,
    })
    mentor = next(unit for unit in mission["units"]
                  if unit["id"] == "renaud_mentor")
    mentor["hp"] = mentor["max_hp"] = 9
    mentor["attack"] = 1
    mentor["speed"] = 1

    story = project["story"]
    introduction = next(scene for scene in story["scenes"]
                        if scene["id"] == "arrival")
    introduction.update(
        title="Le garde et la porte du village",
        speaker="Garde",
        text=("Jeanne, écoute : actionne le levier près de la porte, "
              "repousse Renaud, ouvre le coffre et rejoins la sortie."),
        choices=[{
            "id": "enter", "label": "Parler au garde et partir",
            "effects": [{"kind": "set_flag", "flag": "r31_npc_spoken",
                         "value": True}],
        }],
    )
    story.setdefault("after_mission", {})[MISSION] = REWARD_SCENE
    story["scenes"].append({
        "id": REWARD_SCENE,
        "title": "Le trésor du village",
        "speaker": "Garde",
        "text": ("Le coffre a-t-il été ouvert ? "
                 "La récompense est réservée à la quête achevée."),
        "choices": [
            {
                "id": "claim",
                "label": "Remettre le contenu du coffre au village",
                "when": {"flag": FLAG, "eq": True},
                "effects": [
                    {"kind": "set_flag", "flag": QUEST, "value": True},
                    {"kind": "gold", "amount": STORY_REWARD},
                ],
            },
            {"id": "leave", "label": "Repartir sans réclamer de récompense"},
        ],
    })
    return content, project


def preview_reference_quest(session: AuthoringSession):
    """Prevalidate full story+mission+graph+campaign binding on a disposable R1.

    The owner's single returned preview stages *all* changes atomically. Its
    source revision is checked at apply, and one Undo rolls back the entire
    quest. Even an invalid intermediate design never touches owner's history.
    """
    if not isinstance(session, AuthoringSession):
        raise TypeError("Use the shared R1 AuthoringSession")
    source = session.snapshot().to_dict()
    shadow = AuthoringSession.new(source["content"], source["project"])
    shadow.apply(shadow.preview_pair(
        _build_stage, kind="r31h.reference-stage", mission_id=MISSION))
    graph = LogicGraphDraft.new(
        MISSION, GRAPH, source_revision=shadow.revision)
    graph.edit_node("start", {"kind": "interact", "object_id": CHEST})
    graph.edit_node("message", {
        "kind": "message", "text": "Le coffre de Jeanne a été ouvert.",
    })
    graph.add_variable_after("message", FLAG, value=True)
    graph.apply(shadow)
    shadow.apply(configure_export(
        shadow, MISSION, FLAG, FLAG, result="victory"))
    completed = shadow.snapshot().to_dict()
    return session.preview_pair(
        lambda _content, _project: (
            deepcopy(completed["content"]), deepcopy(completed["project"])),
        kind="r31h.reference-quest", mission_id=MISSION)


def install_reference_quest(session: AuthoringSession):
    """Single history change, reversible in one Undo."""
    return session.apply(preview_reference_quest(session))
