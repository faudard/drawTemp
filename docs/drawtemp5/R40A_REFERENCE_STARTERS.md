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
| r40-metroidvania | Original metroidvania | R25/R32 high portal, earned double jump, original two-phase guardian and canonical victory flag | Final gameplay/Player/export certification |
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

The initial metroidvania source smoke checks the bounded R33 ability graph
and the R25 narrative routes. **R40.B.3 adds a separate opt-in physical
R32 pickup/double-jump path** using the same GameSession and save schema.
The R40.B.4 physical boss and shortcut removal are source-level prototypes; the final Player remains uncertified,
so this still cannot close the R40.4 release gate.

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
Player bundles. R40.B.4 now removes the direct metroidvania shortcut and
adds a deterministic two-phase guardian in the R32 preview; final production
Player, polish and human playtesting remain uncertified.
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

**Status update (R40.B.4):** the old `to_citadel` shortcut was **removed
from the metroidvania starter only**. The authored physical `high_gate` is
now the sole way into the guardian chamber; the adventure starter's
narrative journey remains unchanged. A deterministic two-phase guardian
has been added to the R32 physical preview. Full-game softlock coverage,
a final art/character pipeline and installed three-OS Qt Player are still
missing; **R40.12 remains NO-GO**.

## R40.B.4 — Real deterministic two-phase guardian (source prototype)

The metroidvania starter no longer contains the R25
`r40_ruins → r40_citadel` shortcut. Reaching the boss now requires the
R33 feather, real R32 double-jump and contact with the physical high portal
in the village. The normal top-down adventure's narrative route is unchanged.

The optional `boss` field in an R32 authored platform scene is strictly
bounded: boss and strike rectangles, max health, two phases, phase threshold,
telegraph/strike/recovery durations and player HP. `PlatformBoss` advances
*only* from the R32 fixed-step `attack` command; incoming strikes are
telegraphed, hit the hero only on real AABB overlap, and leave deliberate
recovery windows for player counterattacks. The phase changes at the authored
HP threshold. No random effects, QML mutation or second save system.

The R32 preview displays the strike zone, vulnerability color, boss HP,
player HP and phase. **F** attacks while in range during recovery; other
controls remain unchanged. `GameSession.route_platform_step(attack=True)`
converts a genuine boss-defeat event into a Campaign.story_flags victory.
The existing R32 `scene_platform` replay validates physics and boss actions
from input commands; the load path compares the reconstructed boss outcome
with the canonical Campaign victory flag. Rewritten attacks or fabricated
victory flags are rejected even with recomputed outer checksums.

Old non-boss R32 project snapshots, commands and recording format are
unchanged. Boss authoring uses the pre-existing `drawtemp.physics` catalog
and `GameSession` alone; this does **not** change tactical CT.

Headless checks:

    python -m unittest tests_standalone.test_r40_platform_boss -v
    python -m unittest tests_standalone.test_r40_platform_ability tests_standalone.test_platform_physics_r32 tests_standalone.test_platform_journey_r32 -v
    python -m drawtemp.quality.r40_headless --report r40-source-audit.json

The four-genre source audit now requires actual feather pickup, physical
double jump, high-gate traversal, two boss phases, victory and disk
checkpoint restore, rather than passing metroidvania on abstract R33 BFS
alone. **These tests are authored but have NOT been confirmed passing
on GitHub Actions**, which currently fails before scheduling any jobs.

Outstanding: gameplay tuning and accessibility, enemy varieties,
production Player polish and verified installed-bundle integration, full human-playtested original game,
native packaged clean-machine exports, 3-OS GPU performance and signatures.
The boss is an original minimal encounter, **not** an 8.0-complete boss/game.

## R40.B.5 — Main Qt Quick Player platform integration

The **actual** `drawtemp.player.qt_app` now recognizes canonical R32 scenes
and presents them as a `platform` screen instead of trying to use the
top-down tactical/exploration grid. No alternate engine is added:

- `Simulation.platform_state()` produces an immutable authored-geometry +
  R32 actor/boss projection **without materializing the physics journal**
  on a read-only view. `platform_step()` and `platform_travel()` remain
  revision-checked, atomic real `GameSession` calls.
- `PlayerController` exclusively routes physical scenes through R32 inputs.
  Old `explore_move`, `explore_interact` and `explore_actor` entry points
  reject physical scenes. Every authored R32 portal (not just R33 high gate)
  requires real trigger contact; `Simulation.route_options()` also marks it
  unavailable until contact.
- The **main** `Main.qml` includes `PlatformViewport.qml`, a Qt Quick
  side-view read-only Canvas showing R32 colliders, physical actor position,
  current portal contacts and the deterministic R40 boss hit/telegraph zones.
  The original tactical `TacticalBoard` remains unchanged and visible only
  outside physical scenes. The viewport is not a second gameplay simulation.
- The existing Qt `PlayerBridge` uses `ActionStepClock` and monotonic
  nanoseconds to advance exactly the due **integer 60 Hz engine ticks**,
  independent of the QML paint/event timer. Jump and attack buttons generate
  buffered input **edges**, not held-frame double-jumps.
- Existing Player slots save immediately when manually requested, after
  authenticated transitions and boss terminal outcomes, and periodically
  during physical traversal (every 60 committed revisions), avoiding
  60 full disk writes per second. The Player can load a **manual pre-fight**
  slot after death; there is not yet a dedicated checkpoint-respawn contract.

Create an authored `r40-metroidvania` project using the existing Studio
Project Wizard, then launch the **main Player**:

    python -m drawtemp.player.qt_app --content /PATH/TO/game.json --project /PATH/TO/game.game.json --campaign main

The project must be a canonical matching Content and GameProject pair.
A smoke run instantiates the real root QML with a physical scene but
does not validate human-visible graphics:

    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.player.qt_app --smoke --smoke-scene platform --content /PATH/TO/game.json

Controls: **A/D or ←/→** move, **Space** jump/double-jump, **F** attack
during recovery, **Enter** use a contacted portal. Accessible on-screen
hold buttons offer an alternative; the existing save/load/pause menu remains.
Pause, unload and scene changes reset the presentation clock. Rendering,
including telegraph colors, is derived from the same fixed-tick replay.

Headless and actual Main.qml offscreen smoke tests:

    python -m unittest tests_standalone.test_r40_player_platform -v
    python -m unittest tests_standalone.test_r40_player_routes tests_standalone.test_r40_platform_ability tests_standalone.test_r40_platform_boss -v

The tests cover wizard→Player physical path→feather→double jump→guardian
→boss win→slot replay; boss defeat→manual pre-fight restore; read-only view
purity, old top-down command refusal, physical route validity and stale
revision refusal, render-frequency independence, and optional actual QML
widgets/bridge. **Tests are authored, not confirmed PASS:** the current
GitHub Actions repository workflow starts then fails with *zero jobs*.

**Not done:** human playtests, optimized million-tick/memory performance,
controller/gamepad polish, character animation and sound, death-respawn UI,
the complete top-down and roguelite original game slices, verified full
native export, 3-OS GPU/device validation, localization/accessibility
acceptance and release sign-off. R40.B.5 is a **development integration**,
not an 8.0-certified Player. **R40.12 remains NO-GO.**

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
