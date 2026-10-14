# R5.15 — Campaign Path Certification

R5.14 explores **hypothetical** campaign routes. R5.15 attempts to **certify**
an explicit route by executing real `GameSession` missions, applying real
`StoryBook` choices, and verifying the resulting tactical journals and
campaign checkpoints. It never upgrades a symbolic node to "certified" without
executing the tactical battles.

## The new Studio workflow

In **Campaign Simulation**:

1. Create a new simulation (not from an existing loaded save).
2. Follow mission/choice candidates in the R5.14 tree.
3. Select the terminal node and choose a fixed integer seed. Click
   **Exporter plan R5.15** to save a reusable candidate suite for CI, or
   **Certifier ce parcours R5.15** to run the proof directly in Studio.
4. A worker executes the route twice: uninterrupted and with authentic
   `SessionStore` writes/reads in a private temporary directory. The Tk
   interface remains responsive.
5. The **Certification R5.15** panel shows **CERTIFIÉ** only if every mission
   really reaches the planned result, every intended story choice is available,
   the ending matches, every intermediate checkpoint replays, and the final
   uninterrupted and restored traces agree.
6. Any unsupported interaction, changed project, obsolete branch, invalid
   gate, world-travel requirement, unachievable result, replay mismatch or
   exhausted command budget yields **NON CERTIFIÉ** or **REJETÉ**. A failed run
   never publishes a certificate.

This first implementation uses the deterministic AI command policy
`choose_command` to drive a single-front battle. Multi-front, tactical
dialogues, manual tactics, human playtests and travel events require their own
recorded, explicit action plans; the certificate will not pretend to support
them. The Studio action uses a command budget of 800, so very long battles may
rightly fail to certify.

A route simulated from a pre-existing loaded save is deliberately **not
exportable for fresh-game certification**: to certify it, an authenticated
replay from the original start/checkpoint needs an explicit separate plan.

## Headless certification

Route cases are ordinary request data. They are not save files, nor proof by
themselves. Example `paths.json`:

```json
{
  "version": 1,
  "cases": [
    {
      "id": "castle_mercy",
      "campaign": "main",
      "seed": 7,
      "steps": [
        {"kind": "choice", "id": "assault"},
        {"kind": "mission", "id": "gate", "outcome": "victory"},
        {"kind": "mission", "id": "walls", "outcome": "victory"},
        {"kind": "mission", "id": "throne", "outcome": "victory"},
        {"kind": "choice", "id": "spare"}
      ],
      "expect": {
        "completed": ["gate", "walls", "throne"],
        "endings": ["mercy"]
      }
    }
  ]
}
```

Run against content/project that actually define these IDs:

```bash
python scripts/certify_campaign_paths.py \
  --content path/to/content.json \
  --project path/to/content.game.json \
  --plans paths.json \
  --report campaign_certificate.json \
  --max-commands 1600 \
  --checkpoint-every 7 \
  --require-all-endings
```

The command returns nonzero if a case fails, a specified result does not
match, a required case lacks a certificate, or `--require-all-endings`
requires a declared ending that no successfully replayed case has reached.
The JSON report is written even for per-case failures and distinguishes
`CERTIFIED` from `FAILED` with an explicit error and coverage summary.
Duplicate IDs and invalid suite formats are rejected before execution.

Use `--require-all-endings` only with suites intended to exercise all
endings declared by the selected project. All-endings coverage means all
declared endings **have an observed route witness**, not that every possible
branch, seed or player action has been explored.

## Certificate evidence

For every passing case R5.15 reports:

- Real battle count and executed tactical command count.
- A verified, deterministic Battle command-journal digest at every mission.
- Exact StoryBook choice IDs and resulting committed mission progression.
- Replayed `SessionStore` checkpoint count (never a fake in-memory deepcopy).
- A normalized proof hash over the final GameSession recording and every
  tactical state digest. Only randomly assigned battle IDs are normalized.
- Equality of uninterrupted and disk-restored runs and checked endings,
  resources and persistent consequences.
- Content, gameplay project and rules fingerprints.

No user save slot is created, overwritten or migrated by the certificate
runner. Only a temporary checkpoint is used, and Studio reads its source
campaign without editing it.

## Reproducible CI gates

```bash
python -m unittest tests_standalone.test_campaign_path_certification_r515 -v
python -m examples.campaign_certification_r515 --report campaign_paths_r515.json
```

These run in the dedicated `campaign-path-certification` job of the
standalone workflow; the machine-readable JSON report is uploaded as an
artifact. The example is a deliberately small three-mission castle fixture
that exercises real Battle commands, wounds, gates, fixed rewards, and the
two ending choices (`mercy` and `occupation`). It is **not** evidence that
all authored Jeanne d'Arc battles or missions have been certified.

## Relationship to other QA gates

- **R5.11**: bounded symbolic reachability, useful for authoring errors.
- **R5.14**: interactive speculative route comparison, no tactical proof.
- **R5.15**: real planned seed/route and battle replay parity, **not**
  exhaustive correctness of every possible campaign path.
- **R5.12**: separately verifies portable game packaging and export safety.
- **Real human playtesting** remains necessary for balance, enjoyment,
  mission length, action clarity and accessibility.

R5.15 retains the existing Content, GameProject, Campaign and GameSession
formats; no alternate narrative engine or save schema is introduced.
