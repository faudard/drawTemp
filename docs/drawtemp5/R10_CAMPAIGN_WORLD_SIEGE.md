# DrawTemp 5.0 — R10 : Campaign, World & Siege Studio

## Intent and migration boundary

This delivery connects the **existing** campaign, narrative, world, siege,
simulation, QA, persistence and source-export engines to a new optional
**Qt 6 Widgets authoring window**. No Content/GameProject/Campaign schema,
replay format, save slot or Tk launcher is replaced. The legacy Studio remains
usable until the equivalent player/editor workflows are certified.

It is not a new campaign engine. Changes are authored through
`AuthoringSession.preview_pair → apply` and validated with the canonical
`Content`, `GameProject` and `StudioHistory` implementations. World positions
are presentation coordinates, not movement geometry; graph edges remain
`Mission.next_missions`. Undo/redo covers both documents atomically.

## Launch

Python 3.12 is the qualified Qt 6 target:

```sh
python -m pip install ".[qt6]"
drawtemp-campaigns --content sporebound/content/jeanne.json
# equivalent
python -m drawtemp.studio.campaign_window --content sporebound/content/jeanne.json
```

The content file may belong to an existing paired project
(`content.json` + `content.game.json`). If no paired document exists,
the window opens the tactical content with a new canonical default
`GameProject` **in memory**; save under a new filename using
**Enregistrer sous…**. A half-present pair or pending recovery journal fails
closed: run explicit recovery rather than overwrite the other document.

The Qt command is separate from `drawtemp-qt6` (R0 composition probe),
`drawtemp` and `sporebound`. No Qt import is needed to use the headless SDK.

## Editor workflows

| Roadmap | Delivered integration | Qualification boundary |
| --- | --- | --- |
| R10.1 Explorer | Campaign selector, mission groups by graph depth, narrative events and endings | Act/chapter hierarchy is *visual only*, not new persisted authoring metadata |
| R10.2 Mission Graph | Canonical mission links, start mission, reachable/isolated nodes and Undo/Redo | Gate predicates and narrative branching use existing Campaign Flow/StoryBook |
| R10.3 World Map | Create world layout, assign mission coordinates/regions, display actual route edges | Advanced encounter/POI authoring remains in the existing world event tools |
| R10.4 Persistent State | Campaign inspector exposes flags, companions, wounds, supplies, resources and consequence ledger | Simulation is not a real player save |
| R10.5 Transitions | Link missions, edit typed gating, attach validated mission-end consequences | Explicit tactical spawns, cinematic transitions and R9 scenes still use their authoring editors |
| R10.6 Siege | Add front doctrine/forces, define finale prerequisites using real missions | Advanced routes, diplomacy, and logistics remain in the existing Siege Studio |
| R10.7 Timeline | Existing deterministic `timeline_preview`, without playing unobserved battle victories | Strategic turns are not tactical combat or offscreen play proof |
| R10.8 Simulation | Branch narrative choices and hypothetical victory/defeat, compare persistent state and endings | No battle, loot, tactical XP or saves are fabricated |
| R10.9 Path Certification | Symbolic `audit_campaign` plus asynchronous real `certify_path` with `GameSession` replay/checkpoints | Each seed and path requires observed `CERTIFIED` evidence; an exploratory route alone cannot pass |
| R10.10 Export | Existing validated deterministic source ZIP with manifest hashes and bundled assets | Requires Python/Tk; **not** standalone native Qt Player; R15 owns portable Qt packaging |

## Example three-mission route

1. Build a campaign with a starting village mission, a forest mission and a
   castle mission in the existing content editor (or use existing missions).
2. Open the **Graphe** workspace; select origin/destination and click
   **Relier** twice. Choose a start mission if needed.
3. Use **Conditions & conséquences** to add mission gates, persistent flags,
   resources, and two alternative ending conditions. R9 StoryBook provides
   the actual player-facing dialogue/decisions.
4. Initialize the **Carte du monde**, position the three locations and
   assign region labels; the connector lines derive from the mission graph.
5. Create a siege on a forest mission, add a distinct castle front, select a
   different final sector and require victory at the approach.
6. Explore both narrative branches in **Simulation**. The inspector reflects
   persistent campaign consequences; these are hypothetical results.
7. Run **Audit** to find unreachable nodes/ends or duplicate effects. Run
   **Certifier la branche** for a chosen planned route: only the real battle
   runner with deterministic checkpoints can return `CERTIFIED`.
8. Use **Enregistrer** or **Enregistrer sous…** for the journal-protected
   Content/GameProject pair. ZIP source export is an optional separate step.

## Deterministic safety contracts

- No alternate save format, simulation engine, world travel graph or project
  manifest. No UI dependencies transitively imported into core/sdk.
- Each editor mutation first validates both canonical documents; failure and
  stale preview leave the revision/history untouched.
- Undo and Redo also invalidate the simulation sandbox, so a route from an old
  document revision cannot masquerade as current proof.
- Source export runs the existing diagnostics and symbolic campaign audit;
  missing assets or invalid references abort before replacing the ZIP.
- Real certification operates on detached models on a Qt worker. A report
  completed after an editor revision change is visibly marked obsolete.
- GUI smoke checks creation of a real Qt Widgets surface with software
  rendering, **not** visual design approval or GPU certification.

## Test and CI commands

```sh
python -m unittest tests_standalone.test_drawtemp5_r10 -v
python -m unittest tests_standalone.test_campaign_flow_simulation_r514 -v
python -m unittest tests_standalone.test_campaign_path_certification_r515 -v
python scripts/audit_drawtemp5.py --check --strict

# Python 3.12 + .[qt6], without visible display
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.campaign_window --smoke
```

Dedicated GitHub Actions checks run the headless suite on Python 3.10, 3.12
and 3.14 and the Qt window smoke on Linux, macOS and Windows.

## Explicit remaining R10 exit criteria

The roadmap's full **gate R10** is broader than this first integration.
Closure still requires a GUI-authored, saved-and-reloaded end-to-end
three-mission sample **without manual JSON**, two dialogue decisions,
actual player-controlled combat and persistent consequences, and **two
distinct endings evidenced by real tactical replay**. The Qt Player
hand-off (R12), full R9 graph authoring and native deployment (R15)
are prerequisites; until those are integrated and exercised, do **not**
mark the complete R10 product gate as passed. This PR provides the concrete
authoring foundation, testable contracts and certification entry points,
not a fictional gate pass.
