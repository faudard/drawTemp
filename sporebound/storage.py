"""Versioned JSON persistence. Atomic replace; no pickle or executable content."""
import json
import os
from pathlib import Path
import tempfile

from .engine import Battle
from .model import RuleError


def json_text(data):
    """Exact on-disk representation, including the terminal newline."""
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as out:
            name = out.name
            out.write(json_text(data))
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def load_battle(path, *, rules=None):
    try:
        return Battle.replay(json.loads(Path(path).read_text(encoding="utf-8")), rules=rules)
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        raise RuleError(f"Invalid battle save: {exc}") from exc


def save_battle(path, battle):
    write_json(path, battle.recording())


def save_scenario(path, session):
    write_json(path, session.recording())


def load_scenario(path, *, rules=None):
    from .scenarios import ScenarioSession
    try:
        return ScenarioSession.replay(json.loads(Path(path).read_text(encoding='utf-8')), rules=rules)
    except (KeyError, TypeError, ValueError, StopIteration, AttributeError) as exc:
        raise RuleError(f'Invalid scenario save: {exc}') from exc
