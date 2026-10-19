"""R23.F headless end-to-end *real Studio APIs* -> R15 export -> Player.

Uses synthetic runtime bytes exclusively as an export-container fixture. This
does NOT run a frozen native GUI; R23.D separately smoke-tests real binaries.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

from drawtemp.export.r15 import ExportError, export_game, verify_bundle
from drawtemp.player.qt_app import build_controller
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.quality.r23f import _revision
from tests_standalone.test_r17d_studio_player_roundtrip import (
    author_demo, GATE_EVENT, MISSION, STORY,
)


def run_journey(*, revision, platform):
    _revision(revision)
    if platform not in ("Linux", "Windows", "macOS"):
        raise ValueError("Invalid R23.F platform")
    start = perf_counter()
    checks = {}
    with TemporaryDirectory(prefix="drawtemp-r23f-") as folder:
        root = Path(folder)
        authoring = root / "creator"
        authoring.mkdir()
        content, original = author_demo(authoring)
        saved = AuthoringSession.open(content)
        if saved.snapshot().to_dict()["content"] != original["content"]:
            raise AssertionError("Studio authoring roundtrip diverged")
        checks["studio_authoring"] = "passed"
        if not content.with_suffix(".game.json").is_file():
            raise AssertionError("Studio GameProject companion was not saved")
        checks["content_gameproject_roundtrip"] = "passed"

        runtime = root / "synthetic-pyinstaller-runtime"
        runtime.mkdir()
        executable = runtime / ("DrawTempPlayer.exe" if os.name == "nt"
                                else "DrawTempPlayer")
        executable.write_bytes(b"R23F FIXTURE — not a native executable")
        executable.chmod(0o755)
        export = export_game(content, runtime, root / "out" / "Jeanne")
        manifest = verify_bundle(export)
        if manifest["content"] != "game/jeanne-gate.json":
            raise AssertionError("Wrong authored content in export")
        checks["export_integrity"] = "passed"

        relocated = root / "independent" / "Jeanne"
        relocated.parent.mkdir()
        shutil.copytree(export, relocated)
        # Original creator documents are unavailable to the relocated Player.
        shutil.rmtree(authoring)
        manifest = verify_bundle(relocated)
        checks["export_relocated"] = "passed"
        manifest_sha = sha256((relocated / "manifest.json").read_bytes()).hexdigest()
        if manifest_sha != sha256((export / "manifest.json").read_bytes()).hexdigest():
            raise AssertionError("Relocation altered game provenance")
        player_content = relocated / manifest["content"]
        player = build_controller(
            content_path=player_content, campaign_id="main",
            save_dir=root / "independent" / "user-saves")
        if player.new_game()["screen"] != "dialogue":
            raise AssertionError("Authored entry story missing")
        player.choose("enter")
        player.start_mission(MISSION)
        player.interact_object("lever")
        current = player.state()
        if current["screen"] != "dialogue" or current["scene"]["id"] != STORY:
            raise AssertionError("Authored lever/dialogue did not trigger")
        if not any(x["id"] == "gate" and x.get("open", False)
                   for x in current["battle"]["objects"]):
            raise AssertionError("Authored gate event did not open the door")
        checks["player_story_to_battle"] = "passed"
        player.save(1)
        old_bytes = (root / "independent" / "user-saves" / "slot_1.json").read_bytes()
        resumed = build_controller(content_path=player_content, campaign_id="main",
                                   save_dir=root / "independent" / "user-saves")
        if resumed.load(1)["screen"] != "dialogue":
            raise AssertionError("Relocated Player checkpoint did not load")
        checks["save_and_reopen"] = "passed"
        if resumed.state()["battle"] != current["battle"]:
            raise AssertionError("Relocated Player replay state diverged")
        if ((root / "independent" / "user-saves" / "slot_1.json").read_bytes()
                != old_bytes):
            raise AssertionError("Loading unexpectedly rewrote the save")
        checks["replay_state_equal"] = "passed"
        player_content.write_bytes(player_content.read_bytes() + b"\nR23F-NEGATIVE\n")
        try:
            verify_bundle(relocated)
        except ExportError:
            checks["tamper_rejected"] = "passed"
        else:
            raise AssertionError("R15 export accepted tampered content")
    return {
        "schema": 1, "kind": "drawtemp-r23f-authoring-player",
        "revision": revision, "platform": platform,
        "journey": "real-api-headless-acceptance",
        "manifest_sha256": manifest_sha,
        "checks": checks, "runtime": "synthetic-native-stub",
        "native_gui_qa": "not-asserted", "signed": False,
        "elapsed_seconds": round(max(perf_counter() - start, .000001), 6),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--platform", choices=("Linux", "Windows", "macOS"),
                        required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_journey(revision=args.revision, platform=args.platform)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True,
                                          ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"journey": "passed", "platform": args.platform,
                          "runtime": report["runtime"]}))
        return 0
    except (OSError, ValueError, AssertionError, KeyError, TypeError) as exc:
        print("R23.F authoring-player rehearsal blocked: " + str(exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
