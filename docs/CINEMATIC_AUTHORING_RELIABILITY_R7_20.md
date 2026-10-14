# R7.20 — Cinematic Authoring Reliability

**Branch:** `feat/r7-20-cinematic-authoring-reliability`, based on the
integrated R7.19 Cinematic Studio and destined for `master`.
R7.20 adds no new GameProject fields or alternate gameplay data model.

## Workflow

1. Select multiple events in the list with **Ctrl+click** or **Shift+click**
   (normal Tk extended selection). The timeline also accepts **Ctrl+click**
   to add/remove an event from the selection. The coloured blocks are
   outlined to show the group.
2. Use **Copier sélection** (Ctrl+C / Cmd+C) or **Couper sélection**.
   Clipboard data is an in-memory deep copy, independent from project files,
   operating-system clipboard and project save states.
3. Switch cinematic sequence, place the playhead, click **Coller au curseur**
   (Ctrl+V / Cmd+V). The relative time offsets, order, keyframe data, dialogue
   presentation and audio mixer automation are preserved.
4. Use **Décaler sélection** and a millisecond delta to retime tracks together.
   Alternatively drag any selected timeline block; the preview moves all
   selected blocks and commits **one** transaction on release.
5. **Supprimer groupe** / Delete removes all selected events as one action.
   Ctrl+A / Cmd+A selects all events; Escape clears the selection in the list.
   Undo/Redo restores the entire validated state.

| Shortcut, in event list or timeline | Operation |
| --- | --- |
| Ctrl+C / Cmd+C | Copy selected events |
| Ctrl+X / Cmd+X | Cut selected events |
| Ctrl+V / Cmd+V | Paste at playhead |
| Delete | Remove selected events |
| Ctrl+Z / Cmd+Z | Undo |
| Ctrl+Y / Cmd+Y | Redo |
| Ctrl+A / Cmd+A | Select all cinematic events |
| Escape (event list) | Clear selection |

Shortcuts are deliberately bound **only** to the event Listbox and timeline,
not global widget/key bindings. Ordinary text Entry keyboard copy/paste works
normally. Focus must be in the cinematic editor selection/timeline; no
keyboard shortcut consumes the Editor's global hotkeys while working in
unrelated panels.

## Safety and identity

The pure `cinematic_batch.py` commands always return **deep copies**.
Invalid selections, duplicate IDs, attempted overflow of the target
cinematic, negative times or bad clipboard structure fail without
partially changing a project. A pasted group receives deterministic
new event IDs, kept inside the existing 64-character event-ID budget.

Paste anchors the **earliest selected event** at the target playhead;
subsequent events preserve the exact relative start offset. An event's
interior keyframe timestamps remain relative to its original event start,
which makes group moves and cross-cinematic paste lossless. No absolute
story-event references or gameplay conditions are rewritten.

The UI commits a complete candidate with the existing
`GameProject.from_dict(..., Content)` gate and one `_apply` call per
gesture. Invalid candidates do not consume undo slots, emit a save status,
or corrupt the in-memory clipboard. No-op edits do not consume a history
entry.

## Shared Studio History

The prior cinematic-specific undo implementation could restore
`GameProject` locally while `StudioHistory` still pointed at a newer
Content+Project snapshot. When a full Studio owner provides
`undo_global`/`redo_global`, Cinematic Studio now delegates to it.
The owner restores **both Content and GameProject** and resets dependent
panels. Minimal stand-alone/headless Studio harnesses without a global
history continue using validated local snapshots as a fallback.

## Tests and gates

Headless model, included in the normal 3-OS Python unittest matrix:

```sh
python -m unittest tests_standalone.test_r7_cinematic_batch -v
```

Explicit Tk smoke in Editor CI:

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_r7_cinematic_batch_gui -v
```

The gates cover multi-selection, clipboard deep copy, copy to another clip,
keyframe fidelity, repeat-paste IDs, retiming, non-truncating validation,
save/reload, local undo/redo, global history delegation and rejection of
out-of-range paste without mutations.

## Known limits

- Clipboard is **in-session**, not serialized or shared with another process.
- Group editing moves whole timeline events; it does not stretch all
  durations/keys proportionally or rewrite external story dependencies.
- The Studio inspector edits the **lead selected event**; bulk property
  editing beyond group position/delete/copy/paste is not part of R7.20.
- UI focus/shortcuts and DPI behavior need a real-device Windows/macOS
  smoke in addition to Xvfb.

**Release gate:** all matrix checks green, Editor Tk smoke passes,
manual cross-OS clipboard/keyboard smoke, unchanged schema and successful
campaign/siege replay. Only then merge to `master`.
