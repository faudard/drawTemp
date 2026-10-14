# Human Playtest Telemetry 3.8.4

## Why

Battle Lab 3.8 measures **AI-versus-AI** simulations with CT ticks and
command counts. Neither measures how long a human needs to understand or
finish an encounter. The Player can now capture **opt-in human playtest
sessions** and Studio can inspect them without modifying combat mechanics,
savegames or replay journals.

## Consent, privacy and ownership

Collection is **OFF at every Player launch**. In the Player, choose
**Options → Enregistrer les playtests (activation volontaire)**. Uncheck
to stop; capture since activation is saved only in memory until the tester
selects **Exporter rapport playtest JSON** (also in a battle's toolbar).
The tool never uploads any report, stores playtest data in the canonical
GameSession/save slot, or captures names of the tester, device identity,
player filesystem paths, free-text dialogue or account credentials.

It records authored mission and unit IDs, accepted action kind (and a
whitelist of game command fields), remaining HP/objective progress signals,
and a monotonic elapsed time **including time spent idle in menus/dialogues**.
Exporting a JSON is an explicit action selecting a local destination.
Close with an unexported in-memory report prompts the player to export.

The report includes the authored-content SHA-256 and the rules manifest
for reproducibility. One application launch does not resume an earlier
telemetry clock after a saved-game load; late activation is marked
`partial_capture` and excluded from complete-duration percentiles.
Closing a running encounter is marked `interrupted`, not `abandoned`.
The dedicated **Abandonner** action marks an `abandoned` playtest.

## Correct temporal and tactical semantics

- **Human duration:** monotonic wall elapsed seconds, including idle,
  menus, tactical dialogue, cinematic viewing and think-time while capture
  remains active. It is **not** active-input time, CPU time or CT.
- **Accepted command:** recorded only **after** `PlayerController._apply`
  successfully modifies and saves the canonical `GameSession`. Rejected
  actions and failed persistence are not counted. The optional observer
  does not change engine command selection, replay, RNG, damage or rules.
- **Enemy decisions:** `PlayerController.ai_turn` executes canonical
  commands through `PlayerController.execute`; event records contain
  the actor team so the Studio can separate player and enemy action kinds.
- **Result:** victory/defeat/draw are based on the actual Battle result;
  explicit abandonment is distinct from app closure, stop-recording or
  in-progress exports. `partial_capture` and unfinished observations are
  excluded from full-encounter duration distributions.
- **Objectives:** actual hold ticks and goal occupancy are reported as
  factual signals, not a fabricated universal completion percentage.
  Damage/heal events are actual engine events; a UI click alone does not
  invent a hit.
- **Multi-fronts:** recorder follows the focused battle only; each battle
  identity starts a new observation when focus changes. It does not
  reconstruct off-focus tactical events.

The in-memory event list is capped at **10,000 accepted actions per
encounter**, with an explicit truncation count. A filtered whitelist of
fields avoids arbitrary strings or document payloads ending up in exports.

## Studio workflow

1. Play with the option activated and export a report JSON locally.
2. Open the **Playtest Lab** Studio tab, available from **Espace projet**.
3. Click **Importer playtests JSON** and filter by mission. Inspect
   outcomes, abandonment frequency, player/enemy command kinds, real
   durations p50/p95, damage/heals and objective progression.
4. Optionally **Importer référence Battle Lab**. For a matching mission,
   Studio shows AI victory/CT/command metrics **separately**. It **never
   converts ticks CT to human minutes** or infers human victory rates
   from automated outcomes.
5. The Combat Design 1.0 guideline of 15–30 minutes for standard human
   battles remains **advisory** until enough complete human samples exist.
   No arbitrary CI gate treats a tiny sample as statistically reliable.

## Tests

```sh
python -m unittest tests_standalone.test_playtest_384 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_playtest_384_gui -v
```

Gates: opt-in default disabled, verified save before observation, rollback
safety, no user identifiers, JSON round-trip, separation of real time vs CT,
incomplete/partial/abandoned lifecycle, Player opt-in controls and Studio
local import UI. Existing simulation and determinism baselines remain
unchanged.
