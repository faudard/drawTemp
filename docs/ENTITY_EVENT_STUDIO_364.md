# Event Studio 3.6.4 — Gameplay Path Certification

## Goal

Upgrade the prior **Branch QA & Coverage 3.6.3** from structural diagnostics
and isolated previews to a real **GameSession certification gate**: scripted
player actions, checkpointed replay, explicit expected consequences, and
reproducible regression comparisons. Reuse the same Studio Branch QA window
and its JSON export, not a parallel tactical/narrative engine.

## Evidence, not estimates

The new `sporebound/gameplay_certification_364.py` runs these actual
GameSession entrypoints:

- `choose_story_option(id)` — campaign narrative dialogue
- `start_mission(id)` — battle creation with existing tactical events
- `choose_tactical_story_option(id)` — validated tactical StoryBook choice,
  with the real `Battle.execute(story_effects)` consequence and event chain
- `execute(command)`, `ai_turn()`, `return_to_campaign()`,
  `abandon_encounter()` — optional authored step kinds

After **every step** it executes `GameSession.recording()`, restores it
using `GameSession.from_recording()`, and requires the restored recording
to match the original **exactly** before continuing from the restored
session. This mechanism internally replays Battle command journals and
validates the saved Campaign state and narrative history.

A path is **certified only when** every step replays, every explicitly
declared oracle passes, and all required scenario/choice/event thresholds
pass. A missing required choice or event, an unexpected competing branch,
a divergent flag, reward, hazard, or history entry **fails the gate**.

### Honest scope of certification

- The tactical Battle command log is independently replayed by the engine.
- `Campaign` progress is restored and validated from the checkpoint. The
  whole campaign decision sequence is not independently reconstructed from
  an event-sourced campaign journal. Therefore this is **GameSession
  checkpoint replay certification**, not a proof of every possible game path.
- Scripted paths exercise **real** player APIs. This is stronger than the
  3.6.3 synthetic StoryBook probes and 3.4 isolated Battle previews.
- Only specifically scripted paths are certified. Coverage reports list
  exactly which real choices and tactical events were observed.
- Random Battle UUIDs and outer GameSession checkpoint hashes are retained
  as per-run evidence but **excluded from cross-run baselines**. Semantic
  baselines keep a deterministic Battle state digest that includes tiles,
  units, RNG, effects, and fired events. This detects real changes beyond
  explicitly listed output fields.

## Scenario format

Each JSON suite has `version:1`, `cases` (1–20), `min_passed_paths`,
`required_choices`, and `required_events`. Each case has a unique ID,
campaign, seed and at most 80 ordered steps. **Every step must specify at
least one `expect` assertion**.

Example:

```json
{
  "version": 1,
  "min_passed_paths": 1,
  "required_choices": ["gate_dialogue/fight"],
  "required_events": ["gate_attack"],
  "cases": [{
    "id": "attack_gate",
    "campaign": "main",
    "seed": 17,
    "steps": [
      {"kind": "start_mission", "mission": "garden",
       "expect": {"mode": "battle", "pending_tactical": "gate_dialogue"}},
      {"kind": "tactical_choice", "choice": "fight",
       "expect": {
         "fired": ["gate_attack"],
         "not_fired": ["gate_negotiate"],
         "pending_tactical": "",
         "flags": {"strategy": "attack"},
         "hazards": {"5,5": 12}
       }}
    ]
  }]
}
```

Observed oracle fields include `mode`, `pending_campaign`,
`pending_tactical`, `fired`, `fired_exact`, `not_fired`,
`flags`, `history`, `gold`, `inventory`, `unlocked`,
`completed`, `battle_result`, and `hazards`. An authored choice
cannot be spoofed by passing `story_effects` as a generic battle command.

## Run the blocking CI contract

```bash
python3 scripts/certify_gameplay_paths_364.py \
  --content sporebound/content/core.json \
  --project sporebound/content/core.game.json \
  --suite tests_standalone/fixtures/core_gameplay_certification_364.json \
  --report gameplay-certification-364.json
```

Optional regression comparison:

```bash
# After reviewing a successful run, generate an explicitly approved baseline.
python3 scripts/certify_gameplay_paths_364.py \
  --content sporebound/content/core.json \
  --project sporebound/content/core.game.json \
  --suite tests_standalone/fixtures/core_gameplay_certification_364.json \
  --write-baseline approved-baseline.json

# CI can lock a previously approved semantic baseline.
python3 scripts/certify_gameplay_paths_364.py \
  --content sporebound/content/core.json \
  --project sporebound/content/core.game.json \
  --suite tests_standalone/fixtures/core_gameplay_certification_364.json \
  --baseline approved-baseline.json \
  --report current-evidence.json
```

The script exits **nonzero** if any path, required choice/event, oracle,
or locked semantic baseline fails. Reports are persisted even for failed
gates; the CI editor job uploads `gameplay-certification-364.json` as an
artifact using `if: always()`.

The builtin core fixture covers the campaign split
`oath/guard` versus `oath/alone`, the `provisions` reward vs
`proceed`, and an actual `garden` mission start. Separate headless
tests exercise both **exclusive tactical branches and their OR reunion**,
with a deterministic replay checkpoint for each branch.

## Existing Studio workflow

In **Arbre narratif → QA & couverture**, use **Certifier GameSession…**
to select a scenario contract JSON and read per-step results in the existing
Branch QA panel. An author can export the complete JSON and compare it with
the CI evidence. The window does not edit Content or GameProject.

## Gates

```bash
python -m unittest tests_standalone.test_gameplay_certification_364 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover \
  -s tests_standalone -p test_branch_qa_363_gui.py -v
```

- All real scripted `GameSession` checkpoints must roundtrip.
- Exclusive routes, selected flags and OR reunion must match the oracle.
- Semantically meaningful gameplay changes must break an approved baseline.
- All required story choices and tactical events must be truly observed.
- Tk GUI, core content CI and multi-OS game tests must pass.
