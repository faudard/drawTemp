"""R7.9 — Engine-authored, read-only action previews for the Player.

No speculative A* / LOS / damage model: Battle.reachable, level_reachable,
forecast, vertical_forecast, can_interact and movement_threats are authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import RuleError


@dataclass(frozen=True)
class ActionPreview:
    action: str
    status: str  # available | blocked | conditional | inactive
    headline: str
    details: tuple[str, ...] = ()
    path: tuple[tuple[int, int], ...] = ()
    levels: tuple[int, ...] = ()
    cost: int | None = None
    destination: tuple[int, int] | None = None


def _preview(action, status, headline, details=(), *, path=(), levels=(),
             cost=None, destination=None):
    return ActionPreview(action, status, headline, tuple(details), tuple(path),
                         tuple(levels), cost, destination)


def _path_hazards(battle, path):
    hazards = [(cell, battle.board.tile(cell).hazard) for cell in path[1:]
               if battle.board.tile(cell).hazard > 0]
    result = []
    if hazards:
        result.append("Terrain dangereux traversé : " +
                      ", ".join(str(cell) + " (" + str(damage) + "/passage)"
                                for cell, damage in hazards))
    threats = battle.movement_threats(battle.active, list(path))
    if threats:
        kinds = ", ".join(sorted({str(row["kind"]) for row in threats}))
        result.append("Réactions/engagements possibles : " + kinds +
                      " (le chemin réel peut être interrompu)")
    return tuple(result)


def _forecast_details(rows):
    if not rows:
        return ("Aucun effet chiffré sur une unité ; l'action reste validée par le moteur.",)
    result = []
    for row in rows:
        label = str(row.get("unit", "?")) + " · " + str(row.get("kind", "effet"))
        if "amount" in row:
            label += " · valeur " + str(row["amount"])
        if "chance" in row:
            label += " · probabilité " + str(round(100 * row["chance"])) + "%"
        if row.get("redirected_to"):
            label += " · interception possible → " + str(row["redirected_to"])
        result.append(label)
    return tuple(result)


def action_preview(battle, action, cell, *, target_level=0):
    """Produce a projected explanation without executing a battle command.

    Status 'available' is used *only* following the engine's specific legality
    query, and never promises a successful RNG roll or uninterrupted movement.
    """
    if battle is None:
        raise ValueError("Battle required")
    cell = tuple(cell)
    if (len(cell) != 2 or any(type(v) is not int for v in cell)
            or not battle.board.contains(cell)):
        raise ValueError("Target outside board")
    if type(target_level) is not int:
        raise ValueError("Invalid target floor")
    action = str(action or "")
    unit = battle.active
    if battle.result:
        return _preview(action, "inactive", "Combat terminé")
    if battle.deploying:
        return _preview(action, "conditional", "Déploiement à valider",
                        ("Case choisie : " + str(cell),
                         "Le moteur contrôle les zones, unités et empreintes à l'exécution."),
                        destination=cell)
    if unit is None or unit.team != "player":
        return _preview(action, "inactive", "Attendre le tour du joueur")
    try:
        if action == "move":
            if unit.moved:
                return _preview(action, "blocked", "Déplacement déjà consommé")
            row = battle.reachable(unit).get(cell)
            if row is None or cell == tuple(unit.pos):
                return _preview(action, "blocked",
                                "Destination inaccessible selon le moteur",
                                destination=cell)
            cost, path = row
            path = tuple(tuple(pos) for pos in path)
            return _preview(action, "available",
                            "Trajet proposé · coût " + str(cost),
                            (*_path_hazards(battle, path),
                             "Trajet calculé par Battle.reachable ; arrivée non garantie."),
                            path=path, cost=cost, destination=cell)
        if action == "level_move":
            current_floor = battle.unit_levels.get(unit.id, 0)
            if target_level == current_floor == 0:
                return _preview(action, "blocked", "Utiliser move au rez-de-chaussée",
                                destination=cell)
            row = battle.level_reachable(unit).get((target_level, *cell))
            if row is None or (target_level, *cell) == (current_floor, *unit.pos):
                return _preview(action, "blocked", "Destination inter-étages inaccessible",
                                destination=cell)
            cost, nodes = row
            return _preview(action, "available",
                            "Trajet multi-étages · coût " + str(cost),
                            ("Passage par les connexions réellement définies dans la mission.",
                             "Réactions et interruptions restent conditionnelles."),
                            path=tuple((node[1], node[2]) for node in nodes),
                            levels=tuple(node[0] for node in nodes),
                            cost=cost, destination=cell)
        if action == "level_attack":
            shot = battle.vertical_forecast(target_level, cell, unit)
            return _preview(action, "available",
                            "Tir vertical validé · étage N" + str(target_level),
                            _forecast_details((shot,)),
                            destination=cell)
        if action == "attack" or action in unit.skills:
            rows = battle.forecast(action, cell, unit)
            skill = battle._skill(unit, action)
            return _preview(
                action, "available",
                "Cible validée · coût " + str(skill.cost) + " MP",
                _forecast_details(rows) +
                ("Portée, LOS, cible et ressources validées par Battle.forecast.",
                 "Dégâts et effets restent soumis à l'exécution."),
                destination=cell)
        if action.startswith("object:"):
            ident = action.split(":", 1)[1]
            obj = next((obj for obj in battle.mission.objects
                        if obj["id"] == ident), None)
            if obj is None:
                return _preview(action, "blocked", "Objet introuvable",
                                destination=cell)
            if not battle.can_interact(unit, ident):
                return _preview(action, "blocked",
                                "Interaction actuellement impossible",
                                ("Les conditions de l'objet ne sont pas remplies.",),
                                destination=tuple(obj["pos"]))
            return _preview(action, "available", "Interaction autorisée : " + ident,
                            ("Vérifiée par Battle.can_interact sur copie isolée.",
                             "Les conséquences ne sont pas simulées dans l'interface."),
                            destination=tuple(obj["pos"]))
        if action == "charge":
            option = next((row for row in battle.charge_options(unit)
                           if tuple(row["cell"]) == cell), None)
            if option is None:
                return _preview(action, "blocked",
                                "Pas de couloir de charge validé", destination=cell)
            landing = tuple(option["landing"])
            row = battle.reachable(unit).get(landing)
            path = tuple(tuple(p) for p in row[1]) if row is not None else ()
            return _preview(action, "available", "Charge proposée",
                            ("Coût CT : " + str(option["ct_cost"]),
                             "Réactions et attaque finale conditionnelles ; interruption possible."),
                            path=path, destination=cell)
    except RuleError as exc:
        return _preview(action, "blocked", "Action refusée par le moteur",
                        (str(exc),), destination=cell)
    return _preview(action, "conditional", "Action conditionnelle",
                    ("Les effets et cibles de cette action sont évalués à l'exécution.",
                     "Aucune probabilité ou validité supplémentaire n'est supposée."),
                    destination=cell)


def preview_screen_geometry(preview, camera, *, iso_geometry=None, shift=(0, 0)):
    """Project path/target to the *same* 2D or iso coordinates as the Player.

    Retains full level information separately; an upper-floor segment must
    never be drawn as if it were a ground-floor walkable route.
    """
    def center(cell):
        if iso_geometry is not None:
            x, y = iso_geometry.center(cell)
            return x + shift[0], y + shift[1]
        x, y = camera.cell_to_screen(cell)
        return x + camera.cell_size / 2, y + camera.cell_size / 2

    path = tuple(center(pos) for pos in preview.path)
    destination = (center(preview.destination)
                   if preview.destination is not None else None)
    return path, destination
