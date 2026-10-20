"""R15.4 creator templates validated against the canonical v1 project schema."""
from copy import deepcopy
from importlib.resources import files
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from drawtemp.core import Content, GameProject
from drawtemp.export.r15 import ExportError, preflight
from drawtemp.sdk.reference import reference_project
from sporebound.studio_transaction import validate_pair
from drawtemp.quality.r14 import safe_asset_path

TEMPLATES = ("blank", "tactical", "narrative", "jeanne", "asterion")
_TITLES = {"blank": "Nouveau RPG", "tactical": "Prototype tactique",
           "narrative": "Histoire interactive",
           "jeanne": "Jeanne d'Arc — Les Cendres du Royaume",
           "asterion": "Asterion — Les Veilleurs du Signal"}


def create_template(kind, destination, *, title=None, subtitle=None,
                    language=None, save_slots=None, fullscreen=None):
    """Create a detached starter using the canonical two-file project schema.

    Validate identity/options before making directories; the content + assets
    are published together only after the staging preflight passes.
    """
    if kind not in TEMPLATES:
        raise ExportError("Unknown creator template: " + str(kind))
    if title is not None and (not isinstance(title, str) or
                              not 0 < len(title.strip()) <= 120):
        raise ExportError("Project title must contain 1..120 characters")
    if subtitle is not None and (not isinstance(subtitle, str) or
                                 len(subtitle) > 240):
        raise ExportError("Project subtitle must have at most 240 characters")
    if language is not None and language not in ("fr", "en"):
        raise ExportError("Language must be fr or en")
    if save_slots is not None and (type(save_slots) is not int or
                                   not 1 <= save_slots <= 9):
        raise ExportError("Save slots must be between 1 and 9")
    if fullscreen is not None and type(fullscreen) is not bool:
        raise ExportError("Fullscreen must be a boolean")
    output = Path(destination).absolute()
    if output.exists() or output.is_symlink():
        raise ExportError("A project already exists at this destination")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".drawtemp-template-", dir=output.parent) as folder:
        stage = Path(folder) / "project"
        stage.mkdir()
        if kind == "asterion":
            # Independent second game, included in the installed wheel.
            source = files("drawtemp").joinpath("creator_examples/asterion.json")
            source_project = files("drawtemp").joinpath("creator_examples/asterion.game.json")
            content = Content.from_dict(json.loads(source.read_text(encoding="utf-8")))
            project = GameProject.from_dict(
                json.loads(source_project.read_text(encoding="utf-8")), content)
            valid_content, valid_project = validate_pair(
                content.to_dict(), project.to_dict())
            (stage / "game.json").write_text(
                json.dumps(valid_content, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            (stage / "game.game.json").write_text(
                json.dumps(valid_project, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        elif kind == "jeanne":
            source = Path(str(files("sporebound").joinpath("content/jeanne.json")))
            source_project = source.with_name("jeanne.game.json")
            report = preflight(source)
            if not report["passed"]:
                raise ExportError("Jeanne template assets incomplete: " + str(report["errors"]))
            shutil.copy2(source, stage / "game.json")
            shutil.copy2(source_project, stage / "game.game.json")
            for relative in report["assets"]:
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(safe_asset_path(source.parent, relative), target)
        else:
            if kind == "narrative":
                content, project = reference_project()
                project.title = _TITLES[kind]
            else:
                source = Path(str(files("sporebound").joinpath("content/jeanne.json")))
                data = json.loads(source.read_text(encoding="utf-8"))
                first = deepcopy(data["missions"][0])
                first["name"] = ("Première carte" if kind == "blank"
                                 else "Entraînement tactique")
                first["triggers"] = []
                first["next_missions"] = []
                if kind == "blank":
                    first["board"] = {"width": 12, "height": 12, "tiles": []}
                    first["units"][0]["pos"] = [2, 2]
                    first["units"][1]["pos"] = [8, 8]
                data["missions"] = [first]
                content = Content.from_dict(data)
                project = GameProject.default(content)
                project.title = _TITLES[kind]
            project.validate(content)
            valid_content, valid_project = validate_pair(
                content.to_dict(), project.to_dict())
            (stage / "game.json").write_text(
                json.dumps(valid_content, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            (stage / "game.game.json").write_text(
                json.dumps(valid_project, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        if any(value is not None for value in (
                title, subtitle, language, save_slots, fullscreen)):
            manifest_path = stage / "game.game.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if title is not None:
                manifest["title"] = title.strip()
            if subtitle is not None:
                manifest["subtitle"] = subtitle
            if language is not None:
                manifest["options"]["language"] = language
            if save_slots is not None:
                manifest["save_slots"] = save_slots
            if fullscreen is not None:
                manifest["options"]["fullscreen"] = fullscreen
            content_data = json.loads((stage / "game.json").read_text(encoding="utf-8"))
            _, canonical_project = validate_pair(content_data, manifest)
            manifest_path.write_text(
                json.dumps(canonical_project, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        report = preflight(stage / "game.json")
        if not report["passed"]:
            raise ExportError("Template failed validation: " + str(report["errors"]))
        os.replace(stage, output)
    return output
