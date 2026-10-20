# R56.A — Automated Gameplay QA, headless foundation

Scope: partial implementation of the P0 R56.A contract from the R51–R80
roadmap. This is **not** the R56.B visual QA Lab or the R56.C automated
softlock/collision/reward analyzer. No release is certified.

## Versioned scenario

The public Python entry points in drawtemp.quality.r56_scenarios are
build_scenario, validate_scenario and run_scenario. They consume an authentic
Content + GameProject and the authoritative GameSession; no substitute engine,
mock runtime, or arbitrary scenario-specified Python imports are used.

A scenario is a JSON object with exact fields kind, schema (=1), id, starter,
revision (full Git SHA), campaign, seed, content_digest, project_digest and
steps. Each step has operation, args and expect. Operations are an explicit
method allowlist (story, CT, fixed-tick exploration, canonical transitions and
R55 systems); arguments are positional JSON values. An expectation has a path
(array of string keys in GameSession.recording()) and an equals JSON value.

Contracts enforce a maximum of 256 steps, 256 KiB, 16 checks per step, bounded
seed, no unexpected fields, and no nonfinite JSON. CLI input rejects symlinks
and duplicate JSON keys.

## Generate and run a test case

    from drawtemp.sdk.r40_starters import create_starter_pair
    from drawtemp.quality.r56_scenarios import build_scenario, run_scenario

    content, project = create_starter_pair("r40-adventure")
    revision = "a" * 40  # EXAMPLE ONLY: use actual git rev-parse HEAD
    case = build_scenario(
        content, project, identifier="one-move",
        starter="r40-adventure", revision=revision,
        steps=[{"operation": "route_realtime_step", "args": [1, 0],
                "expect": [{"path": ["mode"], "equals": "campaign"}]}],
    )
    result = run_scenario(case, content, project, revision=revision)
    assert result["status"] == "passed"

After reviewing and writing the case to scenario.json:

    python -m drawtemp.quality.r56_scenarios \
        --scenario scenario.json --revision "$(git rev-parse HEAD)" \
        --output r56-qa-report.json

The CLI supports the four canonical R40 starters. Python callers can test
other validated projects, including R55, by passing Content/GameProject
explicitly; the JSON cannot name a Python module to import.

## Evidence and limitations

Every step records the canonical digest and mode. The run is repeated from an
independent initial GameSession, with digest parity and checkpoint
roundtrips. A failing invariant yields the **first failing prefix** of actions.
This is not a minimized subsequence; fault injection and minimization belong
to R56.C.

Statuses are passed, failed or blocked. Stale revision/source hashes block
the run. CLI status is nonzero for failed/blocked cases. The revision field is
**declared**, not independently attested to the GitHub runner SHA. All reports
explicitly set revision_independently_attested=false and
release_certified=false. Green headless tests do not replace human playtests,
Studio UX/GPU validation or the R50/R56 release gates.

## Follow-up

R56.B: capture and batch cases in a Studio QA Lab; visual tick inspector and
failed graph/quest node links. R56.C: softlocks, duplicate rewards, invalid
transitions, physical collisions, minimization, cross-platform CI and
independent SHA provenance, ending with a verified GO/NO-GO report.
