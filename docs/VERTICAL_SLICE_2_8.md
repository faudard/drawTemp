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
