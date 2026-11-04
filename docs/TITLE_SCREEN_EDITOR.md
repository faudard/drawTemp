# Title Screen Editor — WYSIWYG authoring

The Studio **Title Screen** tab edits the real standalone Tk Player title
screen. The preview is deliberately non-interactive with respect to game
commands; the Player uses the saved project settings. Existing projects
without an opt-in extension retain their original appearance and controls.

## Editing workflow

1. Open **Title Screen**. Choose the editing language (**en** / **fr**) at the
   top of the global settings pane. The selected language is also stored as the
   project's initial Player language when you apply changes.
2. The always-visible **Elements / Inspector** hierarchy on the right lists
   built-in objects and user-created overlays. Click a row or click directly
   on the canvas to select it. Drag objects to position them; use **X % / Y %**
   for precision. The blue dashed outline marks the selected item.
3. Use **+ Text** to create a custom text block, or **+ Image / logo** to import
   a PNG/JPEG into the project's `art/title_screen/` directory. Each asset
   gets a stable `extra:<id>` identifier. Modify its content, text color,
   font size, width and height in the inspector and choose
   **Apply selected properties**. Imported images are decorative and never
   execute game commands. PNG remains supported without Pillow (resized with
   native Tk approximation); JPEG and exact image scaling need Pillow.
4. Edit built-in action labels in the left pane or select a button and edit its
   **Text / label** and **Description / subtitle** in the inspector. The
   ornamental logo, campaign card caption and footer labels are also editable.
   Set global accent, panel and text colors in the left pane, or pick a color
   for an individual custom text overlay in the inspector.
5. **Delete / Hide** removes user-created overlays, or hides built-in elements
   while keeping their internal gameplay handlers intact. **Show** restores
   hidden built-in elements. Overlay layering can be changed with
   **Bring forward / Send backward**. The relative position of all elements
   is saved and reapplied at different Player window sizes.
6. Switch languages to author text variants. Built-in English fallback labels
   and captions are supplied; other content falls back to the source language.
   Translations are saved with the project, under the title-screen extension,
   and do not change tactical gameplay or its separate R57 localization files.
7. Select **Apply changes** and **Save project…**. The regular Studio project
   save and recovery mechanisms also work. The canvas has move Undo/Redo via
   Ctrl+Z/Ctrl+Y (when focused), and a position reset for selected items.

## Persistence

All changes live in the existing optional GameProject extension
`org.drawtemp.titlescreen`, schema version 1. Existing fields
(`background`, `image`, `accent`, `panel`, `text`,
`show_campaign`, `labels`, `positions`) remain compatible.
Additional optional fields:

- `source_language`: `fr` or `en`, remembered when variants are authored.
- `hidden`: list of built-in semantic IDs; hidden cards are removed from
  pointer and arrow-key navigation, but their underlying handlers remain wired.
- `captions`: source-language secondary button text.
- `strings`: source-language logo/campaign/footer text.
- `translations`: language maps (`en` and `fr`) for `title`,
  `subtitle`, `labels`, `captions`, `strings` and extra element text.
- `extras`: at most 64 text/image overlays with stable IDs, type, text,
  project-relative asset path, normalized position/size, font size and color.

Assets must be under the project's `art/` directory. Absolute paths and
path traversal are rejected by the shared validator. Overlay geometry uses
normalized fractions and clamps to the visible viewport. Custom text and images
do not have actions; standard game buttons retain their existing click and
keyboard handlers. The canvas preview is not a Playtest.

## Tests

```sh
python -m unittest tests_standalone.test_title_screen_settings -v
python -m unittest tests_standalone.test_title_screen_wysiwyg -v
python -m unittest tests_standalone.test_title_menu_cinematic -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_title_screen_studio -v
```

Manual verification: open an old Jeanne project and confirm unchanged
appearance; create a new text and PNG logo, hide the original logo, drag both,
change their colors and dimensions, save and reopen; switch English/French,
edit a button label and caption in each language, save and verify in Player.
Test missing image fallback, both backgrounds, high contrast, keyboard
navigation after hiding action cards and layout at 800×580, 1160×820 and
1920×1080. The preview approximates font rasterization, so exact typography
needs a Player visual check.

### Current boundaries

- Built-in menu actions cannot be redefined or detached from their gameplay
  logic; hiding them does not delete that logic.
- User-created overlays are **text or image**, not new clickable menu actions.
- Animations, rotation, per-element opacity, external hyperlinks, and
  pixel-identical Player/Studio rendering are not included.
