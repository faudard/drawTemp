"""R7.8 — Pure, opt-in contextual help for tactical Player interactions.

This module reads already-computed BattleFrame projections. It intentionally
does not execute commands, advance CT, compute LOS, query AI or save state.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CombatGuidance:
    phase: str
    title: str
    instruction: str
    notes: tuple[str, ...]


def combat_guidance(frame, action="", cell=None):
    """Explain the selected action and what is *known* from the current frame.

    This is instructional UI, not a rules validator: all legal moves,
    battle outcomes and damage forecasts still belong to Battle.
    """
    if frame is None:
        raise ValueError("A battle frame is required")
    selected = frame.selected if cell is None else tuple(cell)
    if selected is not None and not (0 <= selected[0] < frame.width
                                     and 0 <= selected[1] < frame.height):
        raise ValueError("Selected cell outside board")
    if frame.result:
        return CombatGuidance(
            "results", "Combat terminé",
            "Consultez les résultats puis revenez à la campagne.",
            ("La progression est enregistrée par le PlayerController.",))
    if frame.deploying:
        return CombatGuidance(
            "deployment", "Préparer le déploiement",
            "Choisissez un héros, sélectionnez sa case sur la carte et utilisez "
            "« deploy ». Lancez ensuite « start_battle » lorsque votre équipe est prête.",
            ("L'orientation choisie est transmise au moteur.",
             "Le moteur valide chaque position de déploiement."))
    active = next((u for u in frame.actors if u.id == frame.active_id), None)
    if active is None:
        return CombatGuidance(
            "waiting", "Ordonnancement CT",
            "Aucune unité n'est actuellement active.",
            ("La timeline CT est estimative lorsque les vitesses évoluent.",))
    if active.team != "player":
        return CombatGuidance(
            "enemy", "Activation ennemie",
            "Utilisez « Jouer l'activation IA » pour résoudre l'unité active.",
            ("Les charges sont des possibilités, pas des prédictions certaines.",
             "Les sorts programmés et réactions armées sont affichés séparément."))

    action = action or ""
    if action == "move":
        instruction = ("Sélectionnez une case puis exécutez « move ». "
                       "Les cases accessibles sont indiquées sur la carte.")
    elif action in ("attack", "level_attack"):
        instruction = ("Sélectionnez une cible puis exécutez l'attaque. "
                       "La portée et la ligne de vue sont validées par le moteur.")
    elif action == "level_move":
        instruction = ("Choisissez l'étage cible, puis une case. "
                       "Le moteur vérifie les liaisons entre étages.")
    elif action == "end":
        instruction = "Terminez l'activation de l'unité active."
    elif action.startswith("item:"):
        instruction = ("Choisissez la cible d'un objet et exécutez l'action. "
                       "Les ressources et cibles sont validées par le moteur.")
    elif action.startswith("object:"):
        instruction = ("Sélectionnez l'interaction avec cet objet. "
                       "Ses conditions et conséquences sont vérifiées à l'exécution.")
    elif action.startswith(("formation:", "prepare:", "relay:", "rally:")):
        instruction = ("La tactique choisie s'applique selon les conditions "
                       "de la formation, de la préparation ou du partenaire.")
    elif action in ("charge", "disengage", "reload"):
        instruction = ("La manœuvre choisie doit respecter les conditions "
                       "du moteur, notamment position et état de l'unité.")
    elif action:
        instruction = ("Sélectionnez une cible et exécutez cette compétence. "
                       "Les ressources, la portée et les effets sont validés par le moteur.")
    else:
        instruction = "Choisissez une action, puis une cible si elle est nécessaire."
    notes = []
    if selected is not None:
        if action == "move" and selected in frame.reachable:
            notes.append("Case sélectionnée : déplacement atteignable selon la projection moteur.")
        if action in ("attack", "level_attack") or (action and action not in
                ("move", "end", "level_move") and not action.startswith(
                    ("formation:", "prepare:", "object:", "rally:"))):
            if frame.forecast:
                notes.append("Prévision disponible : consulter le HUD avant de confirmer.")
            else:
                notes.append("Aucune prévision certifiée pour cette cible ou action.")
        dangers = {row["kind"] for row in frame.danger
                   if tuple(row["cell"]) == selected}
        danger_messages = {
            "hazard": "Terrain dangereux : effet connu.",
            "cast": "Incantation ennemie programmée.",
            "prepared": "Réaction ennemie armée.",
            "charge": "Couloir de charge possible (non garanti).",
        }
        notes.extend(danger_messages[k] for k in
                     ("hazard", "cast", "prepared", "charge") if k in dangers)
    notes.append("Aucune recommandation ne remplace la validation de Battle.")
    return CombatGuidance("player", "Aide · " + (action or "action"),
                          instruction, tuple(notes))
