"""R15.6 non-destructive project import with preview and rollback by removal.

Only v1 is currently supported. Unknown legacy schema versions fail closed;
real migration adapters will be versioned and added only with fixtures.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from drawtemp.export.r15 import ExportError, preflight, project_path
from drawtemp.quality.r14 import safe_asset_path


def migration_preview(content_path):
    source = Path(content_path).resolve()
    target = project_path(source)
    result = {"schema": 1, "source": str(source), "project": str(target),
              "operation": "v1-copy", "supported": False,
              "warnings": [], "errors": []}
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
        project = json.loads(target.read_text(encoding="utf-8"))
        if raw.get("version") != 1 or project.get("version") != 1:
            raise ExportError("Unsupported legacy version; no automatic conversion")
        check = preflight(source)
        result["errors"].extend(check["errors"])
        result["warnings"].extend(check["warnings"])
        result["assets"] = check["assets"]
    except (ValueError, OSError, TypeError, AttributeError) as exc:
        result["errors"].append(str(exc))
    result["supported"] = not result["errors"]
    return result


def import_project(content_path, destination):
    """Back up untouched originals in the new location; source never changes."""
    source = Path(content_path).resolve()
    report = migration_preview(source)
    if not report["supported"]:
        raise ExportError("Import preview rejected: " + "; ".join(report["errors"]))
    output = Path(destination).absolute()
    if output.exists():
        raise ExportError("Import destination already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".drawtemp-import-", dir=output.parent) as folder:
        stage = Path(folder) / "project"
        original = stage / "originals"
        original.mkdir(parents=True)
        shutil.copy2(source, original / source.name)
        shutil.copy2(project_path(source), original / project_path(source).name)
        shutil.copy2(source, stage / "game.json")
        shutil.copy2(project_path(source), stage / "game.game.json")
        for relative in report["assets"]:
            asset = safe_asset_path(source.parent, relative)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset, target)
        after = preflight(stage / "game.json")
        if not after["passed"]:
            raise ExportError("Imported content did not revalidate")
        (stage / "import-report.json").write_text(
            json.dumps({"schema": 1, "source": str(source),
                        "operation": "v1-copy", "reversible": True,
                        "asset_count": len(report["assets"])},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(stage, output)
    return output
