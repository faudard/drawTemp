"""R18.D Studio first-project journey: truthful, per-document evidence.

No Qt imports, no inferred completion from visiting a workspace without a
project, and no player/game save-state changes. The shell records observations
*only after* each real user operation succeeds.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

STEP_IDS = ("project", "map", "actor", "save", "playtest")

GUIDE_UI = {
    "fr": {
        "intro": "Créez un projet et découvrez les ateliers sans modifier de fichiers JSON.",
        "progress": "Premiers pas — {done}/{total} étapes vérifiées",
        "complete": "Parcours terminé : vérifiez le Player, les interactions et les diagnostics avant publication.",
        "new": "Démarrer le projet…",
        "workspace": "Ouvrir l'atelier",
        "save": "Enregistrer",
        "playtest": "Lancer le Player",
        "hide": "Masquer le guide",
        "panel": "Visite guidée du premier projet",
        "steps": "Progression du premier projet",
        "hint": "Instruction de la prochaine étape",
        "next": "Effectuer la prochaine étape",
        "warning": "Événements et Cinématiques : consultation possible ; édition complète depuis le shell encore à certifier.",
    },
    "en": {
        "intro": "Create a project and explore the workspaces without editing JSON files.",
        "progress": "Getting started — {done}/{total} verified steps",
        "complete": "Journey complete: verify the Player, interactions and diagnostics before publishing.",
        "new": "Create a project…",
        "workspace": "Open workspace",
        "save": "Save project",
        "playtest": "Launch Player",
        "hide": "Hide guide",
        "panel": "First-project guided tour",
        "steps": "First-project progress",
        "hint": "Next-step instructions",
        "next": "Perform the next step",
        "warning": "Events and Cinematics: browsing is available; full editing in the shell still requires certification.",
    },
}

TRANSLATIONS = {
    "fr": (
        ("Ouvrir ou créer un projet", "Fichier → Nouveau projet, ou Ouvrir. Un dossier est créé seulement après votre validation."),
        ("Découvrir l'atelier Carte", "Ouvrez une carte pour découvrir le viewport, ses pinceaux et ses outils."),
        ("Découvrir les Personnages", "Parcourez les personnages dans la Base RPG et l'inspecteur."),
        ("Enregistrer Content et GameProject", "Enregistrez les deux documents ensemble via le Studio."),
        ("Lancer un Playtest", "Démarrez le Player Qt avec le projet enregistré et vérifiez le jeu."),
    ),
    "en": (
        ("Open or create a project", "Use File → New project or Open. Nothing is created before confirmation."),
        ("Explore the Map workspace", "Open a map to discover the viewport and editing tools."),
        ("Explore the Characters workspace", "Inspect characters in the RPG database and inspector."),
        ("Save Content and GameProject", "Save both documents together from the Studio."),
        ("Launch a Playtest", "Launch the Qt Player for the saved project and check its flow."),
    ),
}

BLOCKERS = {
    "fr": {
        "project": "Aucun fichier projet ouvert. Créez un projet ou ouvrez-en un.",
        "map": "Aucune carte présente : créez une carte dans l'atelier Carte.",
        "actor": "Aucun personnage présent : ajoutez un personnage dans la Base RPG.",
        "save": "Enregistrement impossible tant que le projet n'est pas ouvert.",
        "playtest": "Enregistrez le projet avant de lancer le Player.",
    },
    "en": {
        "project": "No project file is open. Create or open a project.",
        "map": "No map found. Create one from the Map workspace.",
        "actor": "No character found. Add one in the RPG database.",
        "save": "Open a project before saving it.",
        "playtest": "Save your project before launching the Player.",
    },
}


@dataclass(frozen=True)
class JourneyStep:
    identifier: str
    title: str
    instructions: str
    done: bool
    available: bool
    blocker: str


def project_key(content_path):
    """Stable opaque QSettings key; never store arbitrary file paths as keys."""
    if content_path is None:
        return None
    absolute = str(Path(content_path).expanduser().resolve(strict=False))
    return "onboarding/projects/" + sha256(absolute.encode("utf-8")).hexdigest()


def normalize_completed(stored):
    if isinstance(stored, str):
        stored = [stored]
    if not isinstance(stored, (list, tuple, set)):
        return frozenset()
    return frozenset(str(value) for value in stored if value in STEP_IDS)


def completed_steps(completed, *, project_open):
    observed = normalize_completed(completed)
    if not project_open:
        return frozenset()
    # A previous or current, explicitly successful project open is required.
    return frozenset(observed | {"project"})


def journey_steps(snapshot, completed=(), *, content_path=None, language="fr"):
    """Compute actionable steps from canonical resources and verified events."""
    if language not in TRANSLATIONS:
        language = "fr"
    done = completed_steps(completed, project_open=content_path is not None)
    pair = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
    missions = pair.get("content", {}).get("missions", [])
    has_map = bool(missions)
    has_actor = any(mission.get("units") for mission in missions)
    available = {
        "project": True,
        "map": bool(content_path) and has_map,
        "actor": bool(content_path) and has_actor,
        "save": bool(content_path),
        "playtest": bool(content_path) and "save" in done,
    }
    output = []
    for identifier, (title, instructions) in zip(
            STEP_IDS, TRANSLATIONS[language]):
        complete = identifier in done
        can_do = available[identifier]
        blocker = ""
        if not complete and not can_do:
            blocker = BLOCKERS[language][identifier]
            if identifier in ("map", "actor") and not content_path:
                blocker = BLOCKERS[language]["project"]
        output.append(JourneyStep(identifier, title, instructions,
                                  complete, can_do, blocker))
    return tuple(output)


def next_step(steps):
    return next((step for step in steps if not step.done), None)
