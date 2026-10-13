"""Visual authoring helpers for world-route encounters.

Only the optional GameProject.world.events projection is mutated; routes still
derive exclusively from Content.missions[].next_missions and narrative choices
still belong to StoryBook. Functions return new manifests for StudioHistory.
"""
from copy import deepcopy

from .model import require
from .world_map import validate_world


def authored_roads(world, content):
    """Canonical directed display edge for each physical road."""
    if not world:
        return []
    visible = {node["mission"] for node in world["nodes"]}
    result, used = [], set()
    for source in sorted(visible):
        for target in sorted(content.missions[source].next_missions):
            pair = frozenset((source, target))
            if target in visible and source != target and pair not in used:
                used.add(pair)
                result.append((source, target))
    return result


def events_on_road(world, source, target):
    return sorted(
        (deepcopy(event) for event in world.get("events", [])
         if {event["from"], event["to"]} == {source, target}),
        key=lambda row: (row.get("step", 4) if row["from"] == source else
                         8 - row.get("step", 4), row["id"]))


def closest_road(world, content, point, *, radius=13):
    """Select closest authored segment, excluding node disks handled by UI."""
    if not world:
        return None
    xy = {node["mission"]: (node["x"], node["y"]) for node in world["nodes"]}
    px, py = point
    best = (radius * radius, None)
    for source, target in authored_roads(world, content):
        ax, ay = xy[source]
        bx, by = xy[target]
        length_sq = (bx - ax) ** 2 + (by - ay) ** 2
        if not length_sq:
            continue
        parameter = min(1.0, max(0.0,
                        ((px - ax) * (bx - ax) + (py - ay) * (by - ay))
                        / length_sq))
        if not 0.0 < parameter < 1.0:
            continue
        x, y = ax + (bx - ax) * parameter, ay + (by - ay) * parameter
        distance = (px - x) ** 2 + (py - y) ** 2
        if distance < best[0]:
            best = (distance, (source, target))
    return best[1]


def upsert_road_event(world, content, campaigns, story, event, *, original_id=None):
    """Create/edit one event atomically after full GameProject validation."""
    require(bool(world), "Créer d'abord une carte du monde")
    require(isinstance(event, dict), "Événement attendu")
    candidate = deepcopy(world)
    events = candidate.setdefault("events", [])
    original_id = original_id if original_id is not None else event.get("id")
    index = next((i for i, old in enumerate(events)
                  if old["id"] == original_id), None)
    if index is None:
        events.append(deepcopy(event))
    else:
        events[index] = deepcopy(event)
    validate_world(candidate, content, campaigns, story)
    return candidate


def delete_road_event(world, content, campaigns, story, event_id):
    require(bool(world), "Créer d'abord une carte du monde")
    candidate = deepcopy(world)
    events = candidate.get("events", [])
    require(any(row["id"] == event_id for row in events),
            "Sélectionner un événement existant")
    candidate["events"] = [row for row in events if row["id"] != event_id]
    if not candidate["events"]:
        candidate.pop("events")
    validate_world(candidate, content, campaigns, story)
    return candidate


def set_road_choice(world, content, campaigns, story, event_id, choice_id,
                    kind, mission=""):
    """Associate a *StoryBook choice ID* with travel, not a new dialogue node."""
    require(kind in ("continue", "return", "destination"),
            "Action de voyage inconnue")
    candidate = deepcopy(world)
    event = next((row for row in candidate.get("events", [])
                  if row["id"] == event_id), None)
    require(event is not None, "Sélectionner un événement existant")
    choices = {row["id"] for scene in story.get("scenes", [])
               if scene["id"] == event["scene"]
               for row in scene["choices"]}
    require(choice_id in choices, "Choisir une décision narrative existante")
    routes = event.setdefault("routes", {})
    if kind == "continue":
        routes.pop(choice_id, None)
        if not routes:
            event.pop("routes", None)
    else:
        routes[choice_id] = ({"kind": kind, "mission": mission}
                             if kind == "destination" else {"kind": kind})
    validate_world(candidate, content, campaigns, story)
    return candidate


def preview_road_event(world, story, event_id):
    """Static, side-effect-free authoring preview; never runs GameSession."""
    event = next((row for row in world.get("events", [])
                  if row["id"] == event_id), None)
    require(event is not None, "Événement introuvable")
    scene = next((row for row in story.get("scenes", [])
                  if row["id"] == event["scene"]), None)
    require(scene is not None, "Scène narrative introuvable")
    output = [
        f'{scene["title"]} ({event["id"]})',
        f'Route : {event["from"]} → {event["to"]} · étape {event.get("step", 4)}/8',
        f'{scene["speaker"]} : {scene["text"]}',
    ]
    if "when" in event:
        output.append("Condition narrative : " + str(event["when"]))
    for choice in scene["choices"]:
        action = event.get("routes", {}).get(choice["id"], {"kind": "continue"})
        effect = action["kind"]
        if effect == "continue":
            route = "continuer"
        elif effect == "return":
            route = "revenir au carrefour"
        else:
            route = "bifurquer vers " + action["mission"]
        consequences = len(choice.get("effects", []))
        condition = " (conditionnel)" if "when" in choice else ""
        output.append(f'• {choice["label"]}{condition} → {route} '
                      f'· {consequences} effet(s) StoryBook')
    output.append("Aperçu des données : aucune sauvegarde ni règle modifiée.")
    return "\n".join(output)
