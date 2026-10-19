# R40.A — Four creator starters (8.0 preparation)

**Status: code in a feature PR; NOT a DrawTemp 8.0 certification.** The
[R31–R40 roadmap](../DRAWTEMP_7_1_TO_8_0_DETAILED_ROADMAP.md) requires four
complete games, created, playtested, saved and exported to independently
verified clean machines. These starters are an initial source/content slice.

## Implementation

The existing Studio project wizard now exposes four new template IDs. Each
generates the same canonical game.json + game.game.json pair as the old
templates, and can be opened in the existing AuthoringSession.

| Template ID | Genre | Validated source feature | Missing for 8.0 release |
|---|---|---|---|
| r40-srpg | Jeanne / SRPG | CT mission, lever and narrative | Full siege path, historical saves, certified Player |
| r40-adventure | Original action-adventure | Three routed scenes, persistent waystone gates and real fixed-tick movement | Full puzzles/boss action combat, packaged Player/export |
| r40-metroidvania | Original metroidvania | Three routed scenes, static double-jump preflight; jump runtime not connected | Physics/jump ability integration, boss and Player/export |
| r40-roguelite | Original roguelite | R34 seeded layout, GameSession run/meta/replay | Physical rooms, visual debugger and standalone Player |

No competing engine, GameProject schema, quest registry, save owner or art
library is introduced. The reference tactical Content remains CT for all four
starters. Action profiles are explicitly scoped to exploration scenes. R34
roguelite state and meta rewards use the existing GameSession implementation.

The adventure/metroidvania starters are NOT complete playable games. The
metroidvania BFS proves only abstract reachability. SRPG uses the existing
Jeanne Content: it is not four independently completed, original games.
No copyright-protected third-party artwork was added by this PR.

## Usage and tests

Use Studio > New project > choose a starter > Preview > Create in a new folder,
then open the resulting game.json. Existing target folders cannot be replaced.

Run these headless/optional Qt contract tests:

    python -m unittest tests_standalone.test_r40_reference_starters -v
    python -m unittest tests_standalone.test_drawtemp5_r22_project_wizard -v

The tests cover detachment, legacy CT isolation, canonical serialization,
authoring round-trip, preflight, unknown inputs, non-overwrite behavior,
metroidvania reachability and a real roguelite win/replay. Qt import is
conditional; offscreen Qt is not human onscreen or real-GPU evidence.

## R40.A.2 — Routed, saveable example journeys

Both adventure and metroidvania prototypes now have real R25
GameSession.scene_routes linking village, ruins and citadel. The routes use
versioned project data, and their waystone prerequisites are the actual
Exploration.interact() flags already persisted in Campaign.story_flags. There
is no independent quest engine, runtime cursor or save format. The narrative
starter clears Jeanne's entry dialogue rather than silently reusing her
dialogue as an original character.

The adventure source smoke walks the original village, activates the stone,
saves, loads, travels to the ruins, activates the second stone, saves, enters
the citadel, reaches a real exit and restores the checkpoint. Locomotion uses
the R25 integer fixed-tick runtime (60 Hz); this is not a boss or an action
combat demonstration.

The metroidvania source smoke tests two **different** contracts: a bounded R33
ability-graph proof and the R25 narrative waypoint routes. The ability pickup
has **not** been wired into R32 side-view jump physics or the route conditions.
Consequently the source journey is not a physical metroidvania and cannot
close the R40.4 gate.

## R40.B.1 — Evidence-producing headless source audit

    python -m unittest tests_standalone.test_r40_headless -v
    python -m drawtemp.quality.r40_headless --report out/r40-source.json
    python -m drawtemp.quality.r40_headless --report out/r40-source.json --require-release

The new tool runs the genuine canonical GameSession for four source probes:
CT lever/recovery; action fixed-step exploration/route gates/disk checkpoints;
R33 abstract witness + routed progress; R34 seeded win/meta/restart. The
tool does not generate dummy proofs for unavailable rendering/export checks.

Return codes: **0** = source-only probes successful (not 8.0 certified);
**1** = at least one probe failed; **2** = release requested but NO-GO. The
JSON report lists failed scenarios, and always lists the missing R40 P0 gates.
Tests are included in the cross-platform CI matrix; their result must be
confirmed on the final GitHub SHA, never inferred from their presence.

## Remaining R40.B and R40.C gates

1. Deliver four complete independent authored games with actual game loops,
   scene transitions, boss/end conditions, save/restore and player walkthroughs.
2. Run four Studio->Player->save/replay E2E scenarios on the final integration SHA.
3. Produce native, independent Windows/Linux/macOS bundles and clean-machine
   install/launch/restore evidence, with asset rights and checksums.
4. Record hardware GPU frame-times, memory, accessibility, FR/EN, usability,
   artistic approvals and reproducible build/CI evidence.
5. Sign off the GO/NO-GO 8.0 decision using the R40.1–R40.12 checklist.

**R40.12 remains NO-GO.** No successful source smoke test is a substitute
for the complete 8.0 certification dossier.
