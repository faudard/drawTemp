"""3.3.3: guided three-front siege composition over the canonical project.

No standalone campaign schema, fake battle result, or implicit save migration.
All authored data is validated before either Studio document is replaced.
"""
from copy import deepcopy

from . import siege_authoring, strategic_events
from .game_project import GameProject
from .map_authoring import paint_deployment
from .model import Content, require
from .tactical_rpg3 import authored_rules_for_document


FRONTS = ("walls", "gate", "throne")


def readiness(content, missions):
    """Stable, actionable diagnostics; not a speculative battle outcome."""
    content.validate()
    require(isinstance(missions, (tuple, list)) and len(missions) == 3
            and all(isinstance(mid, str) and mid in content.missions
                    for mid in missions),
            "Choisir trois missions existantes.")
    require(len(set(missions)) == 3, "Les trois fronts doivent utiliser des missions différentes.")
    diagnostics = []
    for front, mid in zip(FRONTS, missions):
        mission = content.missions[mid]
        players = [u for u in mission.units if u.team == 'player' and u.alive]
        enemies = [u for u in mission.units if u.team == 'enemy' and u.alive]
        if not players:
            diagnostics.append(("error", front, "Aucun personnage joueur vivant."))
        if not enemies:
            diagnostics.append(("warning", front, "Aucun adversaire vivant au départ."))
        if not mission.deployment:
            diagnostics.append(("warning", front,
                                "Aucune zone de déploiement : utiliser Préparer déploiement."))
    if content.missions[missions[2]].objective != 'eliminate':
        diagnostics.append(("info", 'throne',
                            "La finale n'a pas pour objectif l'élimination ; vérifier le boss."))
    return tuple(diagnostics)


def prepare_deployment(content_data, project, missions):
    """Optional explicit Studio action; leaves existing zones untouched."""
    content = Content.from_dict(content_data,
                                rules=authored_rules_for_document(content_data))
    readiness(content, missions)
    result = deepcopy(content_data)
    for mid in dict.fromkeys(missions):
        mission = content.missions[mid]
        if mission.deployment:
            continue
        player = next((u for u in mission.units if u.team == 'player' and u.alive), None)
        require(player is not None, "Créer un personnage joueur avant le déploiement : " + mid)
        result = paint_deployment(result, mid, 'studio_start', [list(player.pos)])
    project.validate(Content.from_dict(
        result, rules=authored_rules_for_document(result)))
    return result


def build_guided_siege(project, content, *, siege_id, campaign_id, missions,
                       reserves=3, supplies=6, escorts=1, capacity=4,
                       link_lever='', link_door='', set_campaign_start=False):
    """Produce a fully validated NEW GameProject, without mutating either input.

    The two attack fronts are playable in any order. Both must win before the
    final throne front unlocks. No instant victory, auto-play, or inferred
    tactical object interaction is authored. The cross-front lever link is opt-in.
    """
    require(isinstance(project, GameProject) and isinstance(content, Content),
            "Projet ou contenu manquant.")
    project.validate(content)
    require(project.campaign(campaign_id) is not None,
            "Campagne parente inconnue.")
    diagnostics = readiness(content, missions)
    require(not any(level == 'error' for level, _, _ in diagnostics),
            "Chaque front nécessite au moins un combattant joueur vivant.")
    require(type(set_campaign_start) is bool, "Option de démarrage invalide.")
    require(all(type(value) is int for value in
                (reserves, supplies, escorts, capacity)),
            "Les ressources doivent être des nombres entiers.")
    require(bool(link_lever) == bool(link_door),
            "Choisir à la fois le levier des remparts et la porte cible.")
    require(all(isinstance(value, str) for value in (link_lever, link_door)),
            "Références tactiques invalides.")

    draft = siege_authoring.new_blueprint(
        siege_id, campaign_id, missions[0], front=FRONTS[0])
    draft = siege_authoring.add_front(draft, FRONTS[1], missions[1])
    draft = siege_authoring.add_front(draft, FRONTS[2], missions[2])
    draft = siege_authoring.set_finale(
        draft, FRONTS[2], {"walls": ["victory"], "gate": ["victory"]})
    logistics = {
        "reserves": {"player": reserves, "enemy": 0},
        "supplies": {"player": supplies, "enemy": 0},
        "escorts": escorts,
        "capacity": capacity,
        "routes": [{"from": "reserve", "to": front, "turns": 2}
                   for front in FRONTS],
    }
    draft = siege_authoring.set_logistics(draft, logistics, content)
    if link_lever:
        draft = strategic_events.upsert(draft, content, {
            "id": "walls_open_gate",
            "when": {"battle_event": {
                "front": "walls", "kind": "interact", "value": link_lever}},
            "effects": [{"kind": "open_door", "front": "gate",
                         "object": link_door}],
        })

    require(not any(row['id'] == siege_id for row in project.sieges),
            "Un siège avec cet identifiant existe déjà ; le parcours guidé ne l'écrase pas.")
    data = project.to_dict()
    if set_campaign_start:
        next(c for c in data['campaigns'] if c['id'] == campaign_id)[
            'start_mission'] = missions[0]
    candidate = GameProject.from_dict(data, content)
    return siege_authoring.replace_siege(candidate, content, draft)
