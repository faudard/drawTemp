"""R49.B1: readable, non-mutating Creator preflight presentation.

The R28 capability report remains the source of truth. This formatter never
upgrades an unavailable genre to a supported runtime mode, and it does not
create a second gameplay/project schema.
"""
from __future__ import annotations

from collections.abc import Mapping

_ALLOWED_STATUSES = frozenset({"available-v1", "blocked-dependency"})


def creator_preflight_text(report: Mapping[str, object]) -> str:
    """Turn the canonical R28 report into creator-facing text, not JSON."""
    if not isinstance(report, Mapping):
        raise TypeError("A creator preflight report mapping is required")
    if report.get("status") not in _ALLOWED_STATUSES:
        raise ValueError("Unknown project preflight status")
    passed = report.get("passed")
    if type(passed) is not bool:
        raise ValueError("Preflight passed must be boolean")
    errors = report.get("errors")
    if not isinstance(errors, (list, tuple)) or any(
            not isinstance(error, str) for error in errors):
        raise ValueError("Preflight errors must be text")
    profile = report.get("proposed_profile")
    if not isinstance(profile, Mapping):
        raise ValueError("Missing proposed profile")
    if passed and errors:
        raise ValueError("Successful preflight cannot contain blockers")
    if passed and report["status"] != "available-v1":
        raise ValueError("Unavailable mode cannot be marked ready")
    if not passed and not errors:
        raise ValueError("Blocked preflight must explain why")

    def field(key: str) -> str:
        value = profile.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Missing profile field: " + key)
        return value

    genre = report.get("label")
    destination = report.get("destination")
    if not isinstance(genre, str) or not genre.strip():
        raise ValueError("Missing genre label")
    if not isinstance(destination, str):
        raise ValueError("Invalid destination")

    status = "Création disponible" if passed else "Création bloquée"
    lines = [
        status,
        "",
        "Genre : " + genre,
        "Dossier : " + (destination or "à sélectionner"),
        "Déplacement : " + field("movement"),
        "Combat : " + field("combat"),
        "Caméra : " + field("camera"),
        "",
    ]
    if errors:
        lines.append("Points à corriger :")
        lines.extend("• " + error for error in errors)
    else:
        lines.append("Le modèle sera créé sans modifier les projets existants.")
    lines.extend([
        "",
        "Aperçu uniquement : aucune écriture, aucun profil de jeu appliqué.",
        "Création : paire canonique Content + GameProject, validée par R15.",
        "Cet écran ne certifie ni export autonome ni gameplay multi-genres.",
    ])
    return "\n".join(lines)
