"""Versioned JSON persistence. Atomic replace; no pickle or executable content."""
import json
import os
from pathlib import Path
import tempfile

from .engine import Battle
from .model import RuleError


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as out:
            name = out.name
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def load_battle(path):
    try:
        return Battle.replay(json.loads(Path(path).read_text(encoding="utf-8")))
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        raise RuleError(f"Invalid battle save: {exc}") from exc


def save_battle(path, battle):
    write_json(path, battle.recording())
