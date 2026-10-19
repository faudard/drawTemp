"""R22.1 headless project wizard planning and creation.

The Qt form is a client of this module. No competing content schema: every
creation uses the R15 template factory and canonical Content/GameProject.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drawtemp.export.r15 import ExportError
from drawtemp.export.templates import TEMPLATES, create_template


@dataclass(frozen=True)
class ProjectSpec:
    template: str
    destination: str | Path
    title: str | None = None
    subtitle: str | None = None
    language: str = "fr"
    save_slots: int = 3
    fullscreen: bool = False


def project_preview(spec: ProjectSpec) -> dict:
    """Non-mutating validation; never claim runtime/export certification."""
    errors = []
    if spec.template not in TEMPLATES:
        errors.append("Modèle de projet inconnu")
    raw_destination = str(spec.destination)
    if not raw_destination.strip():
        errors.append("Choisissez un dossier de destination")
    try:
        destination = Path(raw_destination).absolute()
        if destination.exists() or destination.is_symlink():
            errors.append("Le dossier de destination existe déjà")
        if destination == destination.parent:
            errors.append("La destination doit être un nouveau sous-dossier")
    except (ValueError, OSError) as exc:
        errors.append("Destination invalide : " + str(exc))
        destination = Path(".").absolute()
    if spec.title is not None and (not isinstance(spec.title, str) or
                                   not 0 < len(spec.title.strip()) <= 120):
        errors.append("Titre : entre 1 et 120 caractères")
    if spec.subtitle is not None and (not isinstance(spec.subtitle, str) or
                                      len(spec.subtitle) > 240):
        errors.append("Sous-titre : au plus 240 caractères")
    if spec.language not in ("fr", "en"):
        errors.append("Langue : français ou anglais")
    if type(spec.save_slots) is not int or not 1 <= spec.save_slots <= 9:
        errors.append("Nombre de sauvegardes : entre 1 et 9")
    if type(spec.fullscreen) is not bool:
        errors.append("Plein écran : valeur booléenne requise")
    return {
        "kind": "r22.1-project-preview",
        "template": spec.template,
        "destination": str(destination),
        "content": str(destination / "game.json"),
        "identity": {"title": spec.title, "subtitle": spec.subtitle,
                     "language": spec.language, "save_slots": spec.save_slots,
                     "fullscreen": spec.fullscreen},
        "passed": not errors,
        "errors": errors,
        "note": "Aucun fichier modifié. Le préflight des assets sera exécuté à la création.",
    }


def create_project(spec: ProjectSpec) -> Path:
    """Create a canonical project without overwriting any destination.

    Returns the Content JSON path ready for AuthoringSession.open().
    """
    report = project_preview(spec)
    if not report["passed"]:
        raise ExportError("; ".join(report["errors"]))
    output = create_template(
        spec.template, report["destination"], title=spec.title,
        subtitle=spec.subtitle, language=spec.language,
        save_slots=spec.save_slots, fullscreen=spec.fullscreen,
    )
    return output / "game.json"
