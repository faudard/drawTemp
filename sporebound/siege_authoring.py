"""Validated authoring of multi-front siege blueprints; independent of Tk.

Sieges are stored in the GameProject manifest, while reinforcement waves are
normal mission triggers in Content.  No parallel simulation rules are invented.
"""
from copy import deepcopy

from . import front_links
from .campaign_strategy import SiegeCampaign
from .fronts import FrontDirector, MultiFrontSession
from .model import Content, RuleError, require
from .storage import write_json


DOCTRINES = ("hold", "assault", "delay", "retreat")
OUTCOMES = ("victory", "partial", "negotiated")


def _identifier(value, label):
    require(isinstance(value, str) and 0 < len(value) <= 64
            and all(c.isalnum() or c in "_-" for c in value),
            f"Invalid {label}")


def validate_blueprint(blueprint, content, campaign_ids):
    require(isinstance(blueprint, dict)
            and set(blueprint) == {"id", "campaign_id", "fronts", "focused",
                                   "specs", "links", "campaign"},
            "Invalid siege blueprint structure")
    _identifier(blueprint["id"], "siege id")
    require(blueprint["campaign_id"] in campaign_ids, "Unknown parent campaign")
    missions = blueprint["fronts"]
    require(isinstance(missions, dict) and 1 <= len(missions) <= 16,
            "Siege requires 1..16 fronts")
    for front, mid in missions.items():
        _identifier(front, "front id")
        require(isinstance(mid, str) and mid in content.missions,
                "Unknown tactical mission in siege")
    require(blueprint["focused"] in missions, "Initial focus must be a front")
    specs = blueprint["specs"]
    require(isinstance(specs, dict) and set(specs) == set(missions),
            "Every front needs strategic settings")
    for row in specs.values():
        require(isinstance(row, dict)
                and set(row) == {"strength", "opposition", "doctrine"},
                "Invalid strategic front fields")
    FrontDirector(specs, blueprint["focused"])
    front_links.validate(content, missions, blueprint["links"])
    campaign = blueprint["campaign"]
    if campaign is not None:
        require(len(missions) >= 2, "Finale needs at least two fronts")
        policy = SiegeCampaign(campaign, content, missions)
        require(blueprint["focused"] != policy.final,
                "Initial focus cannot be the locked final sector")


def validate_all(sieges, content, campaigns):
    require(isinstance(sieges, list), "Sieges must be a list")
    ids = set()
    campaign_ids = {c["id"] for c in campaigns}
    for blueprint in sieges:
        validate_blueprint(blueprint, content, campaign_ids)
        require(blueprint["id"] not in ids, "Duplicate siege id")
        ids.add(blueprint["id"])


def new_blueprint(sid, campaign_id, mission_id, *, front="approach"):
    _identifier(sid, "siege id")
    _identifier(front, "front id")
    return {"id": sid, "campaign_id": campaign_id,
            "fronts": {front: mission_id}, "focused": front,
            "specs": {front: {"strength": 10, "opposition": 10, "doctrine": "hold"}},
            "links": [], "campaign": None}


def replace_siege(project, content, blueprint):
    """Transactional replacement, including references and engine contracts."""
    data = project.to_dict()
    rows = data.setdefault("sieges", [])
    position = next((i for i, row in enumerate(rows)
                     if row["id"] == blueprint["id"]), None)
    if position is None:
        rows.append(deepcopy(blueprint))
    else:
        rows[position] = deepcopy(blueprint)
    return project.from_dict(data, content)


def delete_siege(project, content, sid):
    data = project.to_dict()
    rows = data.get("sieges", [])
    require(any(row["id"] == sid for row in rows), "Unknown siege")
    data["sieges"] = [row for row in rows if row["id"] != sid]
    return project.from_dict(data, content)


def add_front(blueprint, front, mission, *, strength=10, opposition=10,
              doctrine="hold"):
    result = deepcopy(blueprint)
    _identifier(front, "front id")
    require(front not in result["fronts"], "Front already exists")
    result["fronts"][front] = mission
    result["specs"][front] = {"strength": strength, "opposition": opposition,
                              "doctrine": doctrine}
    return result


def remove_front(blueprint, front):
    result = deepcopy(blueprint)
    require(front in result["fronts"] and len(result["fronts"]) > 1,
            "Cannot remove the only siege front")
    require(not any(link["source"] == front
                    or any(effect["front"] == front for effect in link["effects"])
                    for link in result["links"]),
            "Remove connected event links first")
    campaign = result["campaign"]
    require(campaign is None or (front != campaign["final_front"]
            and front not in campaign["required_fronts"]),
            "Remove finale requirements before deleting this front")
    result["fronts"].pop(front)
    result["specs"].pop(front)
    if result["focused"] == front:
        result["focused"] = next(iter(result["fronts"]))
    return result


def set_finale(blueprint, final, required):
    """An empty final disables the strategic finale; no fictitious results."""
    result = deepcopy(blueprint)
    if not final:
        result["campaign"] = None
        return result
    require(final in result["fronts"] and final != result["focused"],
            "Final sector must exist and differ from the initial focus")
    require(isinstance(required, dict) and bool(required),
            "A finale needs at least one required tactical front")
    current = result["campaign"]
    if current is not None and current["final_front"] == final:
        current["required_fronts"] = deepcopy(required)
    else:
        result["campaign"] = {"final_front": final,
                              "required_fronts": deepcopy(required),
                              "partial": {}, "negotiation": {}, "retreat": {}}
    return result


def upsert_link(blueprint, link):
    result = deepcopy(blueprint)
    require(isinstance(link, dict) and "id" in link, "Link needs an id")
    rows = result["links"]
    for i, row in enumerate(rows):
        if row["id"] == link["id"]:
            rows[i] = deepcopy(link)
            break
    else:
        rows.append(deepcopy(link))
    return result


def remove_link(blueprint, link_id):
    result = deepcopy(blueprint)
    result["links"] = [link for link in result["links"] if link["id"] != link_id]
    return result


def add_wave(data, mission_id, event_id, tick, actor_id, archetype,
             pos, *, team="enemy", lifetime=None):
    """Attach an actual queue_wave trigger, never a synthetic strategic event."""
    from .event_composer import action, condition, save_event
    require(type(tick) is int and 0 <= tick <= 100000,
            "Wave turn must be a nonnegative integer")
    require(archetype in data.get("archetypes", {}), "Unknown archetype")
    require(isinstance(pos, (tuple, list)) and len(pos) == 2,
            "Spawn requires x,y")
    trigger = condition("tick", tick=tick)
    wave = action("queue_wave", actor_id=actor_id, archetype=archetype,
                  pos=pos, team=team, name=actor_id, lifetime=lifetime)
    return save_event(data, mission_id, event_id, trigger, [wave])


def remove_wave(data, mission_id, event_id):
    from .model import Content
    result = deepcopy(data)
    mission = next((m for m in result["missions"] if m["id"] == mission_id), None)
    require(mission is not None, "Unknown mission")
    trigger = next((t for t in mission.get("triggers", [])
                    if t["id"] == event_id), None)
    require(trigger is not None and len(trigger["actions"]) == 1
            and trigger["actions"][0]["kind"] == "queue_wave",
            "Only a dedicated reinforcement trigger can be removed here")
    mission["triggers"] = [t for t in mission["triggers"] if t["id"] != event_id]
    return Content.from_dict(result).to_dict()


def waves_for(content, missions):
    result = []
    for front, mid in missions.items():
        for trigger in content.missions[mid].triggers:
            if trigger.get("condition") != "tick":
                continue
            for act in trigger["actions"]:
                if act["kind"] == "queue_wave":
                    actors = act["actors"]
                    result.append((front, trigger["id"], trigger["value"],
                                   ", ".join(actor["id"] for actor in actors),
                                   ", ".join(actor.get("archetype", "") for actor in actors)))
    return result


def timeline_preview(blueprint, *, turns=8):
    """Read-only aggregate projection, not a prediction of tactical victory."""
    require(type(turns) is int and 0 <= turns <= 40,
            "Preview turns must be between 0 and 40")
    clock = FrontDirector(blueprint["specs"], blueprint["focused"])
    if blueprint["campaign"] is not None:
        clock.tactical_only = {blueprint["campaign"]["final_front"]}
    history = [clock.state()]
    for _ in range(turns):
        history.append(clock.advance())
    return history


def make_session(blueprint, content, *, seed=1, rules=None):
    validate_blueprint(blueprint, content, {blueprint["campaign_id"]})
    return MultiFrontSession(content, blueprint["fronts"], blueprint["focused"],
                             seed=seed, rules=rules, specs=blueprint["specs"],
                             links=blueprint["links"],
                             campaign=blueprint["campaign"])


def _save_path(project_path, blueprint_id, slot):
    from pathlib import Path
    _identifier(blueprint_id, "siege id")
    require(type(slot) is int and 1 <= slot <= 9, "Invalid siege save slot")
    p = Path(project_path)
    return p.with_name(p.stem + "_saves") / ("siege_" + blueprint_id) / f"slot_{slot}.json"


def save_siege_slot(project_path, blueprint, slot, session):
    require(session.missions == blueprint["fronts"]
            and session.initial_specs == blueprint["specs"]
            and session.links == blueprint["links"]
            and session.initial_campaign == blueprint["campaign"],
            "Session no longer matches the siege definition")
    path = _save_path(project_path, blueprint["id"], slot)
    write_json(path, {"version": 1, "siege_id": blueprint["id"],
                      "recording": session.recording()})
    return path


def load_siege_slot(project_path, blueprint, slot, content, *, rules=None):
    import json
    from pathlib import Path
    path = _save_path(project_path, blueprint["id"], slot)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(data, dict) and set(data) == {"version", "siege_id", "recording"}
            and data["version"] == 1 and data["siege_id"] == blueprint["id"],
            "Invalid siege checkpoint")
    session = MultiFrontSession.replay(data["recording"], rules=rules)
    require(session.content.to_dict() == content.to_dict(),
            "Siege content has changed since this checkpoint")
    require(session.missions == blueprint["fronts"]
            and session.initial_specs == blueprint["specs"]
            and session.links == blueprint["links"]
            and session.initial_campaign == blueprint["campaign"],
            "Checkpoint belongs to an older siege definition")
    return session
