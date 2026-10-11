"""Smoke test a built drawTemp wheel in an isolated interpreter.

Run from repository root: python scripts/verify_distribution.py dist
The test actually imports packaged content outside the checkout.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def run(args, *, cwd=None):
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_distribution.py dist/")
    dist = Path(sys.argv[1]).resolve()
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected one wheel in {dist}, found {len(wheels)}")
    with TemporaryDirectory(prefix="drawtemp-wheel-") as folder:
        root = Path(folder).resolve()
        venv = root / "venv"
        run([sys.executable, "-m", "venv", venv])
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run([python, "-m", "pip", "install", "--no-index", "--no-deps", wheels[0]])
        # All commands are executed away from the working tree.
        run([python, "-c", "import sporebound; print(sporebound.__file__)"],
            cwd=root)
        run([python, "-m", "sporebound", "validate"], cwd=root)
        save = root / "battle.json"
        run([python, "-m", "sporebound", "simulate", "--mission", "garden",
             "--seed", "42", "--save", save], cwd=root)
        run([python, "-m", "sporebound", "replay", "--load", save], cwd=root)
        if not save.is_file():
            raise SystemExit("Installed application did not create battle save")
        print(f"Wheel smoke OK: {wheels[0].name} ({sys.platform})")


if __name__ == "__main__":
    main()
