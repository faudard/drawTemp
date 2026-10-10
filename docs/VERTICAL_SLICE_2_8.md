# 2.8 — Castle Vertical Slice

This is a **playable integration scenario**, not another combat or narrative
engine. `sporebound.vertical_slice.CastleVerticalSlice` wires up the existing
`Campaign` roster and builds, `MultiFrontSession` strategic timeline,
authored siege routes, linked tactical objectives, finite supplies,
diplomacy, the 2.7 phased boss and replay verification.

## Launch

From the repository root:

```bash
python -m examples.castle_vertical_slice --seed 7 --save saves/castle-2.8.json
python -m examples.castle_vertical_slice --load saves/castle-2.8.json
```

The command prompt exposes the game state and valid actors/objects after every
accepted action. It autosaves after each successful command and supports an
explicit `save` command. It requires Python 3.10+ with no third-party
runtime dependencies. The GUI has **not** been integrated into this vertical
slice; the current delivery is headless + terminal player, usable for
deterministic acceptance testing.

## Player flow

| Chapter | Choices / real mechanics |
| --- | --- |
| Preparation | Choose 1–2 heroes (captain / engineer), class, buy/equip starter gear using a fixed budget |
| Approach | `ram` opens the gate battle; `infiltration` opens walls; `tunnels` commits the costly sewer route; `negotiation` opens supplies; `direct` pays provisions and troops for a costly assault |
| Multi-front | Switch to gate, walls, courtyard, supplies, tunnels; set doctrine and advance global time; outcomes on unfocused fronts are resolved by the existing timeline |
| Tactical objectives | Ram targets the door; wall lever opens the gate and weakens courtyard opposition; sabotaging oil neutralizes courtyard defense; genuine cache interaction interdits later royal reinforcement; supplies intelligence allows gate negotiation |
| Throne | Requires an **eligible verified route**; royal guard honors authenticated treaties; boss has a half-health transition to phase 2 and reinforcements |
| Epilogue | **Victoire** only after a real throne victory; **Accord** after authenticated gate negotiation and actual throne victory; **Défaite** after final defeat or explicit concession |

### Quick examples of the terminal commands

```text
job captain vanguard
buy sturdy_armor
equip captain sturdy_armor
approach negotiation
begin
interact supply_cache
end
switch gate
begin
negotiate
switch courtyard
begin
interact stone_drop
end
partial
switch throne
begin
# Tactical commands until the castellan is defeated...
status
save
```

The full castle uses normal enemy HP, deployment, movement, boss AI and phase
reinforcements. The test suite's specially weakened variant is only used to
make replay and ending checks fast; it is never used by the playable demo.

The `tunnels` branch has a real win requirement; `switch throne` remains
locked until the sewer encounter was *played* and won. `direct` has a
provision and troop cost rather than silently awarding a win. There is no
automatic castle victory or success override in the slice.

## Authoring and architecture

The thin orchestrator receives `content`, `blueprint`, `seed` and
`rules`. A blueprint forwards `missions`, `specs`, `links`, `logistics`
and `campaign` to the existing `MultiFrontSession`. The authored castle
comes from `examples.siege_fronts`, `examples.siege_scenarios`, and
`examples.tactical_rpg3_castle`, with demo jobs and starter gear layered on
top. Existing historical siege scenarios, saves and replays are untouched.

The wrapper records **preparation commands** and the selected approach, plus
a complete multi-front operations journal. Loading validates:

1. Exact schema, wrapper checksum and current ruleset manifest.
2. Exact authored content and blueprint identities (no silent migration).
3. Reapplication of each squad, class, purchase and equip action through
   existing validation.
4. Reconstitution of exactly the same prepared content and initial
   multi-front configuration.
5. Complete tactical/strategic replay and its verified state digest.
6. The final reconstructed checkpoint matches the original exactly.

This detects accidental corruption, content changes, fabricated battle
results and changes to the command journal. The checksum is **not a signed
anti-cheat mechanism**: someone with write access to both game content and
save file can create a new compatible checkpoint.

## 2.8 acceptance and known limits

- [x] Start with squad, class and gear.
- [x] Choose each of five strategic approaches.
- [x] Play real siege mechanics across fronts, tactical links and supplies.
- [x] Resolve diplomacy only after the authenticated tactical prerequisite.
- [x] Reach the throne only through a checked route; fight the existing boss.
- [x] Obtain and resume three distinct endings.
- [x] Verify an in-progress checkpoint and reject corrupt or incompatible saves.
- [x] Run tests in the existing 3 OS × 3 Python CI matrix.
- [ ] Expose this workflow in the graphical Player / Game Studio workspace.
- [ ] Add cinematic/transitional portraits, dialogue UI and audio to the player.
- [ ] Expand diplomacy into a peaceful throne resolution *without* boss combat,
      which needs an explicitly authored and independently verified objective.
- [ ] Full-length balance sessions and UI usability review.

```bash
python -m unittest discover -s tests_standalone -p test_vertical_slice.py -v
```

## 2.8.1 — Graphical Castle Player (follow-up)

Launch from the **repository root** (the authored example is in `examples/`):

```bash
python -m examples.castle_player
python -m examples.castle_player --save saves/castle-gui.json
```

Alternatively, launch the ordinary graphical Player from a repository checkout,
then choose **Campagne Château (2.8)** on the main menu:

```bash
python -m sporebound player
```

This entry is intentionally hidden in wheel-only installs because the historical
castle authors in `examples/` are not bundled in the installed package. It
opens a separate graphical campaign, with an independent, explicitly named
save, without changing regular Player slots.

The Tk client uses the *same* CanvasRenderer, `battle_frame`, camera, tactical
action API and `strategy_frame` as the ordinary Player. It offers:

- New game / continue, explicit overwrite confirmation and save button.
- Squad selection, job selection, shop and equipment before deployment.
- Five approaches, and all standard tactical commands on the 2D board
  (click or arrow keys to select; mouse wheel zoom; Enter to execute).
- Global strategic timeline, focus switching, doctrine, alternative paid routes,
  negotiation, partial courtyard victory and retreat.
- Three authentic epilogues: victory, treaty-backed agreement or defeat.
- Every accepted operation writes an atomic, replay-verifiable checkpoint;
  a rejected command or persistence error restores the previous in-memory state.

The Player does **not** generate synthetic victories or invent resources.
For infiltration and diplomacy, players still need to carry out the real
in-map objective, e.g. supplies cache interaction or door mechanism.
The campaign gate and phased throne encounter are enforced by the engine.

Tests:

```bash
python -m unittest discover -s tests_standalone -p test_castle_player_controller.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_castle_player_gui.py -v
```

Remaining 2.8 integration is tracked by 2.8.2 Studio → Player below.

## 2.8.2 — Custom Campaign & Siege Studio → graphical Player

A Studio siege does **not** need the six castle-demo fronts. The launcher uses
the authored GameProject `sieges[]` schema, existing mission content, the
original `MultiFrontSession` journal and the existing `siege_authoring`
slot format. Existing 2.5.4 game manifests (without logistics) remain valid.

**In the Studio:** open **Campagne & siège**, create fronts/finale/links/waves,
choose slot 1–9 and click **Jouer dans Player 2.8**. You may still use the
Command Center. The in-memory Studio session can be passed to Player, but
overwriting a previously saved slot requires explicit confirmation.

**In the standalone Player:** launch with a project containing saved sieges:

```bash
python -m sporebound player --content my-missions.json --project my-game.game.json
```

Select **Sièges créés dans le Studio** in the title screen, choose siege ID
and slot, then **Nouvelle partie** or **Reprendre sauvegarde**. The Player
uses the same tactical Canvas, zoom/cell-selection, orders, enemy AI and global
timeline. Saves are located beside the game manifest at
`<project-stem>_saves/siege_<siege-id>/slot_<n>.json`. Every accepted command
is checkpointed, resumed by replay and rejected if mission, rules, logistics
or siege definition changed.

**New optional visual authoring:** the **Logistique & convois** Studio tab
can create reserves, provision/escort pools, convoy routes, ambushes, tactical
rescue and pursuit mission references. These become an optional `logistics`
field on the siege blueprint; legacy blueprints are unchanged. The player
includes actual fighter transfers, escort, rescue, pursuit and recovery actions;
side missions use the same tactical board and journal as main fronts.

**Narrative transition:** introductory campaign scene and final-mission
epilogue scene authored in **Scénario & dialogues** are displayed in the
siege GUI if configured. In 2.8.2 these are explicitly **read-only scene
previews**: the interactive dialogue choices, side effects and flags still
belong to the existing main campaign mode, not this siege. Those interactive
narrative integrations plus dynamic portraits are deferred to 2.8.3.

To verify:

```bash
python -m unittest discover -s tests_standalone -p test_authored_siege_player.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_authored_siege_gui.py -v
```

## 2.8.3 — Authenticated siege narrative and presentation

The standalone **Studio-authored siege Player** now uses the existing
`StoryBook` engine, not read-only text scenes. Studio **Scénario & dialogues**
choices are interactive, including validated `when` conditions, `set_flag`,
`add_flag`, `gold` and `unlock_mission` effects, and directed `next_scene`
branches. These effects update **narrative campaign progression** and gate
later dialogue. They do **not** directly grant battle units or supplies, nor
override the tactical front/finale prerequisites.

Entry scenes block combat commands until their choices are resolved. When a
front's Battle really resolves to victory, its authored
`story.after_mission[mission_id]` is queued as an interactive dialogue; the
engine never invents victory. Multiple simultaneous front victories queue
their distinct scenes. Combat resumes once the dialogue graph is resolved.

### Replay and compatibility

The original siege slot (`version: 1`) now optionally includes a `narrative`
chronicle: scene choice IDs and victorious front IDs at exact tactical journal
indices; checksum, project digest and replay-derived progress digest. The
loader first **fully replays and verifies** the tactical journal and then
replays each narrative event against verified tactical prefixes, including
battle-result prerequisites, unlocks, available choices and chronological
dialogue gates. Invalid or tampered narrative choices are rejected.

Existing slots without this optional field still load via the original API.
Loading an already-started legacy siege suppresses a belated introduction;
the next save upgrades the slot to include the narrative chronicle. The
regular Campaign/GameSession and Castle Vertical Slice save formats remain
unchanged.

### Presentation

The scene viewer includes a skippable typewriter effect, accessible visible
choice buttons, a portrait binding for the scene speaker with text fallback,
and optional scene/voice/music cues. The tactical canvas picks up portable
sprite bindings from the same `GameProject.assets` manifest. PNG files
and WAV/OGG remain project-relative and validated by `AssetRegistry`.

Audio is optional: missing bindings or a missing mixer do not block play.
This step is interactive **dialogue staging**, not a full authorable camera
timeline/cinematic sequencer. Full storyboards and timed cinematic editing
remain milestone 2.8.4.

```bash
python -m unittest discover -s tests_standalone -p test_siege_story.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_authored_siege_gui.py -v
```
