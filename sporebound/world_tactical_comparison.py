"""3.7.24H: paired tactical evidence for authored World Route alternatives.

Runs Battle Lab's canonical AI/replay telemetry with each variant's Campaign
snapshot. A mission is evaluated only if the actual GameSession can enter it.
No simulated battle is committed to Campaign and no outcome is described as
a guaranteed result for human players.
"""
from copy import deepcopy

from .battle_lab import compare_reports, run_lab
from .model import require
from .world_route_comparison import WorldRouteComparison


def contextual_battle_comparison(comparison, mission_id, *,
                                 seeds=(1, 7), max_commands=40, rules=None):
    """Pair reproducible seeds while respecting narrative unlock/travel gates."""
    require(isinstance(comparison, WorldRouteComparison)
            and comparison.variants, "Enregistrer au moins un parcours")
    require(isinstance(mission_id, str)
            and mission_id in comparison.checkpoint.session.content.missions,
            "Sélectionner une mission existante")
    require(isinstance(seeds, (tuple, list)) and len(seeds) <= 20,
            "La comparaison accepte au maximum 20 seeds")
    require(type(max_commands) is int and 1 <= max_commands <= 2000,
            "Limiter chaque simulation à 1..2000 commandes")
    outcome = {}
    reference = None
    reference_name = ""
    for name, lab in comparison.variants.items():
        session = lab.session
        if not session.world_can_enter(mission_id):
            scene = session.active_scene()
            state = session.world_state()
            if scene is not None:
                reason = "Dialogue non résolu : " + scene["id"]
            elif state["traveling"]:
                reason = "Voyage non terminé vers " + state["goal"]
            elif mission_id in session.progress.completed:
                reason = "Mission déjà terminée"
            elif mission_id not in session.progress.unlocked:
                reason = "Mission verrouillée"
            else:
                reason = "Le groupe n'est pas sur ce lieu"
            outcome[name] = {"status": "unavailable", "reason": reason}
            continue
        support = session._battle_support(mission_id)
        report = run_lab(
            session.content, mission_id, seeds=seeds,
            max_commands=max_commands, rules=rules or session.rules,
            progress=deepcopy(session.progress), initial_state=support)
        item = {
            "status": "measured", "victory_rate": report["victory_rate"],
            "outcomes": deepcopy(report["outcomes"]),
            "commands_p95": report["commands_p95"],
            "ticks_p95": report["ticks_p95"],
            "activations_ct": report["activations_ct"],
            "possible_stalls": report["possible_stalls"],
            "support_potions": report["initial_inventory"]["potion"],
            "setup_sha256": report["setup_sha256"],
            "replay_verified": all(s["replay_verified"] for s in report["samples"]),
            "report": report,
        }
        if reference is None:
            reference = report
            reference_name = name
            item["vs_reference"] = None
        else:
            item["vs_reference"] = compare_reports(reference, report)
        outcome[name] = item
    return {
        "kind": "world_route_tactical_comparison",
        "mission": mission_id,
        "seeds": list(seeds),
        "max_commands": max_commands,
        "reference": reference_name,
        "variants": outcome,
        "caution": "Simulations IA Battle Lab, sans garantie de durée réelle "
                   "ou de résultat joueur ; aucune sauvegarde modifiée.",
    }


def tactical_rows(result):
    """Small, aligned UI projection from a measured tactical comparison."""
    names = list(result["variants"])
    variants = list(result["variants"].values())
    metrics = [
        ("Disponibilité", lambda v: "Prête" if v["status"] == "measured"
                             else v["reason"]),
        ("Potions au départ", lambda v: str(v["support_potions"])
         if v["status"] == "measured" else "—"),
        ("Victoires IA", lambda v: "{:.0%}".format(v["victory_rate"])
         if v["status"] == "measured" else "—"),
        ("Commandes p95", lambda v: str(v["commands_p95"])
         if v["status"] == "measured" else "—"),
        ("Ticks CT p95", lambda v: str(v["ticks_p95"])
         if v["status"] == "measured" else "—"),
        ("Activations CT", lambda v: str(v["activations_ct"])
         if v["status"] == "measured" else "—"),
        ("Blocages suspects", lambda v: str(v["possible_stalls"])
         if v["status"] == "measured" else "—"),
        ("Replays vérifiés", lambda v: (
            "oui" if v["replay_verified"] else "non")
         if v["status"] == "measured" else "—"),
    ]
    return {"names": names, "rows": [
        {"metric": metric, "values": [getter(v) for v in variants]}
        for metric, getter in metrics]}
