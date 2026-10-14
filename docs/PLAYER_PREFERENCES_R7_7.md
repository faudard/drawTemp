# R7.7 — Persistent Player accessibility and controls

## Scope

`PlayerApplication` now restores the player's chosen keyboard bindings,
high-contrast palette, 100/125/150% text scale and compact HUD on startup.

The user may configure these through **Options → Appliquer**. Applying
validates all shortcuts for duplicates and writes an atomic, versioned JSON
preferences file next to the configured **profile path**:

`<profile filename>.player-ux.json`.

This is a **Player-only sidecar**, not a change to `Content`, `GameProject`,
`GameSession`, replay, campaign, tactical battle or slot save formats. Existing
profile/slot files continue to load without conversion.

## Safety and recovery

- Fresh profiles load defaults and do not create a file until Apply is pressed.
- Invalid values or duplicate shortcuts are rejected without a file write.
- Malformed/unknown-version preferences are left untouched and defaults
  are used; the Options screen shows a diagnostic.
- The sidecar is replaced atomically from a synchronized temporary file.
  Failed replacements leave the old file intact and remove the temp file.
- Each profile has its own preferences; no global account or server storage.
- Fullscreen/audio remain governed by the existing project options, not
  newly introduced persisted sidecars.

## Verification

```sh
python -m unittest tests_standalone.test_player_preferences_r7 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_player_preferences_r7_gui -v
```

The headless test executes on the existing OS/Python CI matrix and the real Tk
Apply → close → relaunch smoke runs explicitly under Xvfb.

Manual acceptance: change contrast, text scale, HUD density and execute
shortcut; Apply; quit; launch without Studio; verify each setting restored.
Load an existing campaign save and confirm the canonical replay digest and
save slot bytes are unaffected. Corrupt the preferences sidecar and confirm
the Player launches using defaults and offers a diagnostic without rewriting
the corrupt file.
