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

## R40.B.2 — Existing Player / Studio round-trip

Implemented in the same feature PR as a **source-level integration**, not a
full 8.0 Player certification:

- `Simulation.route_options()` produces immutable source/destination/eligibility
  projections by querying the existing R25 SceneRouter. The menu never writes
  progress or bypasses the versioned `AuthoringSession` content.
- `Simulation.route_transition()` delegates to canonical
  `GameSession.route_transition()` with R1 revision guards and rollback.
  `PlayerController` now exposes that operation, a read-only route catalogue
  and persistent saves through its existing `SaveManager`.
- The Qt Player bridge forwards route transitions to that controller.
  `Main.qml` displays focusable destinations as locked/available in
  exploration, with a recovery route on completed campaign stages. No
  additional scene manager or QML-owned gameplay clock.
- Roguelite uses the **existing R34 GameSession run/meta** through the
  existing R1 `Simulation.roguelite_*` methods. Its new Player panel shows
  neighboring rooms, key requirements, loot, checkpoints, meta totals,
  loss and restart. This is a **topological text/menu interface**, not
  a physically rendered generated dungeon.
- Tests create real projects via the Studio wizard, open the canonical pair
  through `build_controller`, traverse village→ruins→citadel via the
  Player, perform disk save/load, verify rejection of stale revisions,
  prevent cross-project save reuse, and check R34 meta retention after restart.
  Optional software Qt tests load the real `Main.qml` and exercise bridge
  callbacks for the routed journey and roguelite menu.

Commands:

    python -m unittest tests_standalone.test_r40_player_routes -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_r40_player_routes -v

**Certification exclusions:** direct controller and offscreen QML tests are
not human-visible Studio editing, hardware frame-time measurement, fully
authored original boss encounters, licensed final graphics or installed
Player bundles. The metroidvania static double-jump graph remains separate
from physical side-view control and cannot qualify as completed gameplay.
R40.12 stays **NO-GO** even if all these tests are green.

## R40.B.3 — Authored physical R32/R33 metroidvania preview

The R40 metroidvania starter now contains **three real side-view R32 physics
scenes** in its canonical GameProject extension `drawtemp.physics`. The R33
`feather` pickup is a collidable trigger in the ruins. Entering it records the
ability in canonical Campaign.story_flags, and returning to the village
activates **one optional midair jump** in R32 PlatformPhysics.

The high portal is not an arbitrary menu shortcut: the `high_gate`
R25 route requires both the earned R33 feather and overlap with an
authenticated R32 portal trigger. A destination can be rejected even if
its narrative flag is present, when the player has not physically arrived.
The extra air jump is reset by genuine ground contact, has an explicit
one-jump budget, is simulated at a fixed 60 Hz, and is replay-validated
through the existing R32/GameSession checkpoint. Original R32 records
without the optional ability keep the same snapshot and disk schema.

Original example journey:

1. Start in village; walk right to the physical waystone and ruins portal.
2. Press Enter at the active portal to visit the ruins; walk onto the
   `feather` trigger and acquire double jump.
3. Enter the return portal; the canonical R33 flag now enables one air jump
   in the village platform scene.
4. Jump again while airborne to reach the elevated high portal; Enter takes
   the real R25 route to the citadel.
5. Save/load at any active platform checkpoint using the existing
   GameSession save contract.

Launch the **existing** R32 Qt Widgets side-view diagnostic with the new
starter (software preview, not packaged Player certification):

    python -m drawtemp.player.platform_app --r40-metroidvania

Controls: A/D or left/right = move; Space = jump; Enter = use currently
overlapped portal; Ctrl+S / Ctrl+L = save/load; P = pause.

Automated headless source / replay checks:

    python -m unittest tests_standalone.test_r40_platform_ability -v
    python -m unittest tests_standalone.test_platform_physics_r32 tests_standalone.test_platform_journey_r32 -v

**Important limits:** R40.A's earlier narrative `to_citadel` shortcut from
the ruins remains in the starter for compatibility; it is not an 8.0-certified
metroidvania traversal gate. The new `high_gate` is *physically gated*; the
project as a whole is **not yet softlock-proof in the playable implementation**.
Likewise this slice does not provide authentic enemies, damage, side-view boss
phases, a final character-asset pipeline or an installed three-OS Qt Player.
R40.B.3 physical proof is a partial milestone only; R40.12 remains NO-GO.

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
