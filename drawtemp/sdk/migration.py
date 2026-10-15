"""Executable parity gate: legacy session vs candidate adapter, then disk and replay."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from sporebound.ai import choose_command
from drawtemp.core import GameSession
from .reference import MISSION, reference_project
from .session import SessionAdapter


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def comparable(recording):
    """Ignore only per-instance UUID and the envelope hash that includes it.

    GameSession.recording/load verify the actual envelope independently.
    Tactical state, RNG, commands and event digests remain compared.
    """
    value = deepcopy(recording)
    value.pop("digest", None)
    if isinstance(value.get("tactical"), dict):
        battle_id = value["tactical"].pop("battle_id", None)
        progress = value.get("progress", {})
        if "tracked_battles" in progress and battle_id is not None:
            progress["tracked_battles"] = [
                "<current-battle>" if item == battle_id else item
                for item in progress["tracked_battles"]]
    return value


def run_gate(adapter_type=SessionAdapter, seed=17):
    content, project = reference_project()
    legacy = GameSession.new(content, project, "main", seed=seed)
    candidate = adapter_type.new(content, project, "main", seed=seed)
    trace = []

    def check(stage):
        expected, actual = comparable(legacy.recording()), comparable(candidate.snapshot())
        if actual != expected:
            raise AssertionError("Migration divergence at " + stage)
        trace.append({"stage": stage, "sha256": fingerprint(expected)})

    check("new")
    legacy.choose_story_option("enter")
    candidate.choose_story_option("enter")
    check("dialogue")
    legacy.start_mission(MISSION)
    candidate.start_mission(MISSION)
    check("mission")
    if not legacy.active_battle.board.tile((3, 4)).blocked:
        raise AssertionError("Reference gate must initially block movement")
    command = {"kind": "interact", "unit": "jeanne", "object": "lever"}
    legacy.execute(command)
    candidate.execute(command)
    check("lever")
    if legacy.active_battle.board.tile((3, 4)).blocked:
        raise AssertionError("Lever did not open the canonical door")
    with TemporaryDirectory() as folder:
        # Persist both implementations independently. Reload EACH file through
        # BOTH readers: loading only the candidate's save misses legacy regressions.
        sources = {}
        for name, session in (("legacy", legacy), ("candidate", candidate)):
            path = Path(folder) / (name + ".json")
            session.save(path)
            sources[name] = (path, path.read_bytes())
        expected = comparable(legacy.recording())
        loaded = {}
        for name, (path, original_bytes) in sources.items():
            try:
                from_legacy = GameSession.load(path, content, project)
                from_adapter = adapter_type.load(path, content, project)
            except Exception as exc:
                raise AssertionError(
                    "Migration " + name + " save cannot be loaded by both runtimes"
                ) from exc
            if (comparable(from_legacy.recording()) != expected or
                    comparable(from_adapter.snapshot()) != expected):
                raise AssertionError("Migration " + name + " save differs from pre-save state")
            if path.read_bytes() != original_bytes:
                raise AssertionError("Loading mutated the " + name + " source save")
            loaded[name] = (from_legacy, from_adapter)
        # Resume each implementation from its OWN saved output for the remainder
        # of the command-by-command parity check and the final replay.
        legacy = loaded["legacy"][0]
        candidate = loaded["candidate"][1]
        check("resume")
        for step in range(700):
            if legacy.active_battle.result:
                break
            command = choose_command(legacy.active_battle)
            legacy.execute(command)
            candidate.execute(command)
            check("command-" + str(step))
        if legacy.active_battle.result != "victory":
            raise AssertionError("Reference combat failed to reach victory")
        replayed = GameSession.from_recording(candidate.snapshot(), content, project)
        if replayed.recording() != legacy.recording():
            raise AssertionError("Replay divergence")
    return {"schema": 1, "seed": seed, "result": "victory", "trace": trace,
            "content_sha256": fingerprint(content.to_dict()),
            "project_sha256": fingerprint(project.to_dict())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-baseline", type=Path,
                        help="Fail if the current parity trace differs from the frozen R0 reference")
    args = parser.parse_args()
    report = run_gate()
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if args.verify_baseline:
        expected = json.loads(args.verify_baseline.read_text(encoding="utf-8"))
        if report != expected:
            parser.exit(1, "R0 frozen baseline mismatch; investigate before updating the reference\n")


if __name__ == "__main__":
    main()
