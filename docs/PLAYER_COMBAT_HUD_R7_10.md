# R7.10 — Combat HUD Layout 4.0

## Goal

Turn the previous stack of portraits, options, preview panels and the all-in-one
combat log into a game-first desktop layout where the battlefield has priority.

## Layout

```
┌─ Mission / tick / current activation ────────────────────────────────┐
│ Objective · feedback     Campaign/Results · Save · Playtest · Panel │
├─ CT timeline (engine-estimated, limited and overflow-labelled) ─────┤
│                                                  ┌─ 2.5D · Aide ───┐│
│                                                  │ Aperçu·Journal  ││
│                                                  ├─ Active hero ───┤│
│                 TACTICAL MAP                     │ Objective       ││
│                 2D / isometric                   ├─────────────────┤│
│                 pan / zoom / mouse / keyboard     │ Tactique        ││
│                                                  │ Journal (opt-in)││
│                                                  │ Équipe          ││
│                                                  │ Assistance      ││
│                                                  │  R7.8 / R7.9    ││
├──────────────────────────────────────────────────┴─────────────────┤
│ ACTIONS: hero / selected action / target floor                      │
│          facing / execute / end activation                          │
└────────────────────────────────────────────────────────────────────┘
```

The map and the sidebar are siblings in a horizontal `ttk.Panedwindow`;
the sidebar can be removed/reinserted without changing selection or battle
data. A two-row action strip stays pinned to the bottom even at 800×580.
The long log is in a hidden-by-default notebook tab, revealed on demand,
and no longer repeated in the tactics panel.

The previous Player projection/rules contract remains unchanged:
- `combat_hud_sections(BattleFrame)` is pure and uses `combat_hud` for
  canonical CT/HP/MP/selection text.
- CT estimates are identified as estimates, not guaranteed future order.
- The complete journal is sourced from `frame.events` and bounded to the
  most recent 30 events. UI navigation never commits a game command.
- The R7.8 tactical guide and R7.9 action preview are moved to an
  **Assistance** tab. Their toggles reveal that tab; they retain their
  existing Engine/Battle semantics and callback cancellation.
- The Player retains original action comboboxes, keyboard remapping, Save,
  Playtest, 2D/ISO at 24/54/96, multilevel targeting, and Results flow.
- Compact UI truncates team summary to four; it does not change combat.
- Text sizing and high-contrast palette apply to the sidebar Text areas.

## Validation

```sh
python -m unittest tests_standalone.test_player_hud_layout_r710 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a -s "-screen 0 1920x1080x24" \
  python3 -m unittest tests_standalone.test_player_hud_layout_r710_gui -v
```

The headless test is included in normal cross-platform discovery;
the real Tk smoke is a dedicated, mandatory `standalone.yml` CI step.

### Manual acceptance gate

At **800×580, 1160×820 and 1920×1080**, without opening the Studio:
1. Start the default campaign, deploy and enter combat.
2. Read the selected hero's HP/MP and the CT timeline while keeping the map
   large enough to identify a tile and a multicell actor.
3. Open/close Journal and the entire sidebar, confirm map selection remains.
4. Toggle contextual help and action preview, including in ISO at all
   24/54/96 px zoom presets and with an active upper floor.
5. Remap action shortcuts in Options, try high contrast + 125% and 150% text.
6. Execute, save/reload, conclude, inspect Results and return to campaign.

No new persisted UI fields or `Content/GameProject/GameSession` schema,
no extra Player engine, no Tk references in headless rules.
