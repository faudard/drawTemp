"""R5.15 — Verified GameSession campaign routes, separate from symbolic R5.14.

Every certified battle is actually played through Battle.execute using the
deterministic AI command policy; every checkpoint is verified by SessionStore
and GameSession replay. A symbolic simulator node is only an input plan, never
evidence. No production save/slot is read or written by this module.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from .ai import choose_command
from .campaign_flow import inspect_campaign
from .game_session import GameSession, digest, gameplay_project_digest
from .model import RuleError, require
from .persistence import SessionStore


def validate_plan(plan, content, project):
    """Strict v1 request; expected results must be chosen before executing."""
    require(isinstance(plan, dict) and set(plan) ==
            {"id", "campaign", "seed", "steps", "expect"},
            "Invalid campaign certification plan")
    require(isinstance(plan["id"], str) and
            0 < len(plan["id"]) <= 80 and
            all(c.isalnum() or c in "-_" for c in plan["id"]),
            "Invalid certification case id")
    require(isinstance(plan["campaign"], str) and
            project.campaign(plan["campaign"]) is not None,
            "Unknown certification campaign")
    require(type(plan["seed"]) is int and 0 <= plan["seed"] <= 2147483647,
            "Invalid certification seed")
    steps = plan["steps"]
    require(isinstance(steps, list) and 1 <= len(steps) <= 96,
            "Certification needs 1–96 explicit actions")
    require(any(isinstance(step, dict) and step.get("kind") == "mission"
                for step in steps), "Certification must execute a real battle")
    for step in steps:
        require(isinstance(step, dict) and step.get("kind") in
                {"choice", "mission"}, "Unknown certification step")
        if step["kind"] == "choice":
            require(set(step) == {"kind", "id"} and
                    isinstance(step["id"], str) and bool(step["id"]),
                    "Invalid dialogue step")
        else:
            require(set(step) == {"kind", "id", "outcome"} and
                    step["id"] in content.missions and
                    step["outcome"] in {"victory", "defeat"},
                    "Invalid tactical step")
    expected = plan["expect"]
    require(isinstance(expected, dict) and set(expected) ==
            {"completed", "endings"}, "Explicit completed/endings expectations required")
    require(isinstance(expected["completed"], list) and
            all(isinstance(mid, str) and mid in content.missions
                for mid in expected["completed"]) and
            len(set(expected["completed"])) == len(expected["completed"]),
            "Invalid expected completed missions")
    require(isinstance(expected["endings"], list) and
            all(isinstance(e, str) and e in project.campaign_flow.get("endings", {})
                for e in expected["endings"]) and
            len(set(expected["endings"])) == len(expected["endings"]),
            "Invalid expected campaign endings")
    require(expected["completed"] or expected["endings"],
            "Certification must assert at least one observable result")
    return deepcopy(plan)


def _normalized_record(record):
    """Ignore *only* intentionally random battle UUIDs, not gameplay state."""
    copy = deepcopy(record)
    battle_ids = copy["progress"]["tracked_battles"]
    require(len(set(battle_ids)) == len(battle_ids),
            "Duplicate battle identities in the certified route")
    copy["progress"]["tracked_battles"] = [
        "battle-" + str(i) for i in range(len(battle_ids))]
    copy.pop("digest", None)
    return copy


def _run(content, project, plan, *, rules, checkpoint_every, max_commands,
         checkpoints_enabled):
    session = GameSession.new(content, project, plan["campaign"],
                              seed=plan["seed"], rules=rules)
    trace = []
    timeline = []
    checkpoint_count = 0
    completed_battles = 0
    commands = 0
    # TemporaryDirectory is private evidence scratch, never a user profile.
    with TemporaryDirectory(prefix="campaign-cert-r515-") as temp:
        store = SessionStore(Path(temp) / "checkpoint.json")

        def checkpoint():
            nonlocal session, checkpoint_count
            if not checkpoints_enabled:
                return
            expected = session.recording()
            store.save(session)
            loaded = store.load(content, project, rules=rules)
            require(loaded.recording() == expected,
                    "SessionStore checkpoint / replay diverged")
            session = loaded
            checkpoint_count += 1

        checkpoint()
        for index, step in enumerate(plan["steps"]):
            if step["kind"] == "choice":
                choices = {c["id"] for c in session.available_choices()}
                require(step["id"] in choices,
                        f"Step {index}: narrative choice unavailable: {step['id']}")
                before = session.progress.story_pending
                session.choose_story_option(step["id"])
                timeline.append({"step": index, "kind": "choice",
                                 "scene": before, "choice": step["id"],
                                 "current_scene": session.progress.story_pending})
                checkpoint()
                continue

            mid = step["id"]
            require(mid in session.available_missions(),
                    f"Step {index}: mission locked or narrative pending: {mid}")
            session.start_mission(mid)
            require(session.active_battle is not None,
                    "Mission did not construct a tactical Battle")
            checkpoint()
            executed = 0
            while session.active_battle.result is None:
                require(not session.tactical_story_pending,
                        "Pending tactical narrative choice: path not certifiable by AI-only policy")
                require(commands < max_commands,
                        f"Campaign command budget reached at mission {mid}")
                command = choose_command(session.active_battle)
                session.execute(command)
                commands += 1
                executed += 1
                trace.append(session.active_battle.digest())
                if commands % checkpoint_every == 0:
                    checkpoint()
            require(session.active_battle.result == step["outcome"],
                    f"Step {index}: actual outcome {session.active_battle.result} "
                    f"differs from planned {step['outcome']}")
            completed_battles += 1
            checkpoint()
            record = session.active_battle.recording()
            # Must be a real journal with commands, never a manually set result.
            require(bool(record.get("commands")), "No actual tactical commands recorded")
            battle_digest = record["digest"]
            session.return_to_campaign()
            checkpoint()
            timeline.append({"step": index, "kind": "battle",
                             "mission": mid, "outcome": step["outcome"],
                             "commands": executed, "replay_digest": battle_digest,
                             "completed": list(session.progress.completed),
                             "consequences": list(session.progress.flow_ledger)})

        inspector = inspect_campaign(session.progress, project.campaign_flow)
        require(session.mode == "campaign",
                "Certification must end outside tactical combat")
        require(list(session.progress.completed) == plan["expect"]["completed"],
                "Actual completed mission sequence differs from expectation")
        require(sorted(inspector["endings"]) == sorted(plan["expect"]["endings"]),
                "Actual campaign endings differ from expectation")
        require(completed_battles == sum(s["kind"] == "mission"
                                        for s in plan["steps"]),
                "An expected tactical encounter was not executed")
        checkpoint()
        record = session.recording()
        require(record["mode"] == "campaign" and record["tactical"] is None,
                "Unfinished tactical journal")
        canonical = _normalized_record(record)
        fingerprint = digest({"final": canonical, "trace": trace})
        return {"proof_digest": fingerprint,
                "normalized_final": canonical,
                "trace": trace,
                "timeline": timeline,
                "commands": commands, "battles": completed_battles,
                "checkpoints": checkpoint_count,
                "inspector": inspector}


def certify_path(content, project, plan, *, rules=None, max_commands=1600,
                 checkpoint_every=7):
    """Certify by comparing real uninterrupted and disk-reloaded playthroughs.

    Raises RuleError on ANY discrepancy: the caller must never turn this into
    a passing certificate or silently fall back to a symbolic state.
    """
    from .rules import default_rules
    rules = default_rules() if rules is None else rules
    require(type(max_commands) is int and 1 <= max_commands <= 100000,
            "Invalid certification command budget")
    require(type(checkpoint_every) is int and 1 <= checkpoint_every <= 1000,
            "Invalid checkpoint cadence")
    project.validate(content)
    plan = validate_plan(plan, content, project)
    uninterrupted = _run(content, project, plan, rules=rules,
                         checkpoint_every=checkpoint_every,
                         max_commands=max_commands, checkpoints_enabled=False)
    resumed = _run(content, project, plan, rules=rules,
                   checkpoint_every=checkpoint_every,
                   max_commands=max_commands, checkpoints_enabled=True)
    require(uninterrupted["proof_digest"] == resumed["proof_digest"] and
            uninterrupted["trace"] == resumed["trace"] and
            uninterrupted["inspector"] == resumed["inspector"],
            "Uninterrupted and checkpoint-restored campaigns diverged")
    require(resumed["checkpoints"] >= resumed["battles"] + 1,
            "Missing mandatory disk checkpoint evidence")
    return {
        "format": "campaign-path-certification-r515",
        "version": 1, "status": "CERTIFIED",
        "id": plan["id"], "campaign": plan["campaign"], "seed": plan["seed"],
        "project_digest": gameplay_project_digest(project),
        "content_digest": digest(content.to_dict()),
        "rules_digest": digest(rules.manifest()),
        "path": deepcopy(plan["steps"]),
        "expected": deepcopy(plan["expect"]),
        "observed": {"completed": resumed["inspector"]["missions"]["completed"],
                     "endings": resumed["inspector"]["endings"],
                     "consequences": resumed["inspector"]["consequences"],
                     "variables": resumed["inspector"]["variables"],
                     "gold": resumed["inspector"]["resources"]["gold"]},
        "evidence": {"proof_digest": resumed["proof_digest"],
                     "tactical_battles": resumed["battles"],
                     "commands": resumed["commands"],
                     "checkpoints": resumed["checkpoints"],
                     "checkpoints_replayed": True,
                     "uninterrupted_equal_resumed": True,
                     "timeline": resumed["timeline"]},
        "scope": ("Real deterministic Battle commands and verified GameSession "
                  "checkpoints; only this planned seed/path and its asserted endings"),
    }


def certificate_coverage(project, reports, *, required_ids=()):
    """Coverage is exactly the set of PASS certificates (never symbolic QA)."""
    ids = [row["id"] for row in reports if row.get("status") == "CERTIFIED"]
    require(len(set(ids)) == len(ids), "Duplicate path certification IDs")
    endings = sorted({ending for row in reports
                      if row.get("status") == "CERTIFIED"
                      for ending in row["observed"]["endings"]})
    missing_ids = sorted(set(required_ids) - set(ids))
    expected_endings = sorted(project.campaign_flow.get("endings", {}))
    return {
        "certified_paths": sorted(ids),
        "required_paths_missing": missing_ids,
        "certified_endings": endings,
        "uncertified_endings": sorted(set(expected_endings) - set(endings)),
        "complete_for_required_cases": not missing_ids,
        "complete_for_declared_endings": not (set(expected_endings) - set(endings)),
        "scope": "Observed on actual selected seeds and routes, not exhaustive gameplay",
    }
