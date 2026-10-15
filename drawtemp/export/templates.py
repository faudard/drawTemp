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

TEMPLATES = ("blank", "tactical", "narrative", "jeanne")
_TITLES = {"blank": "Nouveau RPG", "tactical": "Prototype tactique",
           "narrative": "Histoire interactive",
           "jeanne": "Jeanne d'Arc — Les Cendres du Royaume"}


def create_template(kind, destination):
    """Create a detached, playable starter; never touch an existing project."""
    if kind not in TEMPLATES:
        raise ExportError("Unknown creator template: " + str(kind))
    output = Path(destination).absolute()
    if output.exists():
        raise ExportError("A project already exists at this destination")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".drawtemp-template-", dir=output.parent) as folder:
        stage = Path(folder) / "project"
        stage.mkdir()
        if kind == "jeanne":
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
        report = preflight(stage / "game.json")
        if not report["passed"]:
            raise ExportError("Template failed validation: " + str(report["errors"]))
        os.replace(stage, output)
    return output
