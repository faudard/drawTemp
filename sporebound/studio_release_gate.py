"""Read-only release checks for Studio's portable Game Studio 4 bundles.

The check does not extract arbitrary archive members or write a save into an
author's workspace. Its temporary profile exercises the exact Player controller
which the generated launcher imports.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from .game_project import GameProject
from .model import Content, RuleError, require
from .player_controller import PlayerController
from .tactical_rpg3 import authored_rules_for_document


def verify_game_bundle(path):
    """Verify integrity, parse gameplay and test a new/resumed save per campaign.

    Returns a small diagnostic report. No rendering, Studio process, or actual
    player profile is required; invalid/tampered archives fail closed.
    """
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)), "Duplicate archive members")
            require(all(
                name and not name.startswith("/") and "\\" not in name
                and ":" not in name and ".." not in PurePosixPath(name).parts
                for name in names), "Unsafe archive path")
            require("export_manifest.json" in names, "Missing export manifest")
            manifest = json.loads(archive.read("export_manifest.json"))
            require(manifest.get("format") == "game-studio-4-source-bundle"
                    and manifest.get("version") == 1, "Unknown bundle format")
            declared = manifest.get("files")
            require(isinstance(declared, dict)
                    and set(names) == set(declared) | {"export_manifest.json"},
                    "Export manifest does not describe every archive member")
            for name in sorted(declared):
                require(isinstance(declared[name], str)
                        and len(declared[name]) == 64,
                        "Invalid export SHA-256")
                digest = hashlib.sha256(archive.read(name)).hexdigest()
                require(digest == declared[name],
                        "Corrupt export member: " + name)
            require({"run_game.py", "game/content.json", "game/project.game.json",
                     "sporebound/player_app.py", "sporebound/player_controller.py"}
                    <= set(declared), "Incomplete playable source bundle")
            document = json.loads(archive.read("game/content.json"))
            content = Content.from_dict(
                document, rules=authored_rules_for_document(document))
            project = GameProject.from_dict(
                json.loads(archive.read("game/project.game.json")), content)
    except (BadZipFile, KeyError, OSError, ValueError, TypeError) as exc:
        raise RuleError("Export unreadable or invalid: " + str(exc)) from exc

    with TemporaryDirectory(prefix="studio-release-gate-") as root:
        profile = Path(root) / "profile.json"
        for row in project.campaigns:
            cid = row["id"]
            writer = PlayerController(content, project, profile)
            writer.new_game(cid, 1)
            before = writer.session.recording()
            reader = PlayerController(content, project, profile)
            reader.load_game(cid, 1)
            require(reader.session.recording() == before,
                    "New-game save did not resume: " + cid)
    return {"verified": True, "campaigns": len(project.campaigns),
            "missions": len(content.missions), "files": len(declared)}
