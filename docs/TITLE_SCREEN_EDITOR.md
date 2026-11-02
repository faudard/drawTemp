# Title Screen Editor

The standalone Player uses `CinematicTitleMenu` for the game entry screen.
Its background, colors and action labels are now editable in Studio without
modifying code. The project/mission map editor remains unchanged.

## Authoring

1. Open Studio and select the **Title Screen** tab, or open **Jeu, campagnes
   et sauvegardes → Edit Title Screen**.
2. Edit the game title/subtitle, background mode (`auto`, `solid`, `image`),
   accent, card/text colors, optional campaign card and the six action labels.
3. Choose **Import background image…** to copy a PNG or JPEG into
   `art/title_screen/` beside the project's `.game.json`. JPEG requires
   Pillow; PNG can fall back to native Tk if Pillow is absent.
4. The right-hand canvas provides a **live visual approximation**, not a
   playable Player session. It does not create saves or invoke actions.
5. Choose **Apply changes** and then **Save project…**. The normal global
   Save Project workflow also saves the settings. Undo/Redo, dirty detection
   and interrupted-session recovery use the existing Studio transaction model.

A project that has never been edited keeps the original cinematic menu,
including the Jeanne artwork. Existing project manifests are unchanged until
the Title Screen settings are applied.

## Data contract

Optional extension of `GameProject`:

```json
{
  "extensions": {
    "org.drawtemp.titlescreen": {
      "schema_version": 1,
      "data": {
        "background": "image",
        "image": "art/title_screen/example.png",
        "accent": "#e3b970",
        "panel": "#111a27",
        "text": "#f4ead7",
        "show_campaign": true,
        "labels": {"new": "Commencer"}
      }
    }
  }
}
```

Only project-relative `art/...` image paths are permitted. The extension
contains presentation data only: New Game, Continue, Load, Campaigns, Options,
Quit and their keyboard activation remain wired to their original handlers.
Hidden campaign card does not disable the Campaigns menu entry. Contrast mode
overrides the authored accent and text for accessibility. If image loading
fails, the Player retains a graphical fallback.

## Tests

```sh
python -m unittest tests_standalone.test_title_screen_settings -v
python -m unittest tests_standalone.test_title_menu_cinematic -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_title_menu_cinematic -v
```

Manual gate: import a PNG, apply, save, reopen Studio and the Player,
verify image and labels, then Undo/Redo, save and reopen; check high contrast,
a custom game without Jeanne and a missing-file fallback. Resizing 800×580,
1160×820 and full-screen must preserve action hit boxes and keyboard focus.

### Current boundaries

The first version edits presentation properties and previews the overall
layout. Drag/drop card positioning, individual action visibility, scene
animation timelines and exact pixel-parity preview are future enhancements,
not silently exposed as incomplete controls.
