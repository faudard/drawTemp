"""R44 player Qt gate: drive production QML on a generated five-valley pair.

Creates isolated temporary directories, checks the preflight, then launches the
same Qt app/bridge/QML used by the real Player. No fake renderer or fake state.
This is software/offscreen validation, not real-GPU or clean-machine evidence.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from drawtemp.export.r15 import preflight
from examples.r44_five_valleys import write_five_valleys


def main():
    with TemporaryDirectory(prefix="drawtemp-r44-gui-") as root:
        base = Path(root)
        source, _manifest = write_five_valleys(base / "project")
        report = preflight(source, require_licenses=True)
        if not report["passed"]:
            print("R44 GUI preflight rejected: " + repr(report["errors"]), file=sys.stderr)
            return 1
        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        env.setdefault("QT_QUICK_BACKEND", "software")
        command = [
            sys.executable, "-m", "drawtemp.player.qt_app",
            "--gui-world-journey", "--content", str(source),
            "--save-dir", str(base / "slots"),
        ]
        try:
            result = subprocess.run(
                command, cwd=Path.cwd(), env=env,
                capture_output=True, text=True, timeout=150,
                check=False)
        except subprocess.TimeoutExpired:
            print("R44 GUI journey exceeded 150 seconds", file=sys.stderr)
            return 1
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
