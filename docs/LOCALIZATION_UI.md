# Localization / internationalization

Two distinct domains share the **drawtemp.localization** package:

1. **Application UI:** Studio + Qt Player labels in `locales/en.json` and `locales/fr.json`, indexed by `locales/manifest.json`. All new UI labels use stable semantic keys. English (`en`) is the default regardless of the operating system's locale.
2. **Game content:** The existing R57 `game.l10n.json` translation sidecar contains dialogue, campaign names, titles, etc., with a per-project *source language*. Changing UI language must never rewrite source text or change game rules, saves, checkpoints, or replay hashes.

## Adding a language

- Copy `drawtemp/localization/locales/en.json` to `<code>.json`, set `locale` to the BCP47-style code, translate values (never change IDs like `menu.file` or placeholders like `{name}`).
- Register the locale once in `locales/manifest.json` with `{"code": "es", "name": "Español"}`.
- Run `python -m unittest tests_standalone.test_ui_locale_defaults -v`. CI also runs this audit on Windows, Linux and macOS through the existing R57 workflow. `audit_catalogs()` reports missing keys and the loader rejects invalid JSON, duplicate keys, unknown keys and mismatched placeholders. A missing translation safely falls back to English.
- Call `ui_text("menu.file", ui_language)` in Python/Qt Widgets or `root.ui("player.options")` in QML. Add the keys to `en.json`, then translate in each locale. Never use a translated label as a programmatic ID or persistence value.

UI files are embedded in the installed Python package via `pyproject.toml` package data; no absolute source-tree paths or network access required. Files are UTF-8 and read via `importlib.resources` with cached, validated catalogs. No extra dependency is needed.

## User choice

- Studio: **Tools → Language → English / Français**; the selection is stored in `QSettings("DrawTemp", "Studio5")` and can change without restarting.
- Player: **Options (F10) → Language**; available languages are generated from the JSON manifest, with QA pseudo-locales added separately. Choice is stored in `r57-accessibility.json` independently from game saves. A fresh UI starts in English, even when its historical project content was authored in French.
- Newly created `GameProject` manifests also default to English source text, but pre-existing French projects remain French-authored and are not silently rewritten.

## Status

The catalog migration includes top-level Studio navigation and frequently used Player screens. Specialized Studio workspaces, old Tk windows, and some complex Player HUD/gameplay strings remain to be converted. The R57 per-project Translation Studio is still the correct place for *authored dialogue*; UI JSON is only for application chrome.

Testing: `python -m unittest tests_standalone.test_ui_locale_defaults tests_standalone.test_drawtemp5_r57c -v`, `python -m compileall -q drawtemp/localization drawtemp/studio/qt_shell.py drawtemp/player/qt_app.py`, and offscreen Qt smoke + visual review on Windows/macOS/Linux.

## In-game language for the legacy Tk Player

The legacy Tk game now has **Options → Language** with the locales enumerated
by `locales/manifest.json`. The default is English; choose Français, then
**Apply** to persist the selection to `<profile>.ui-language.json` (atomic,
versioned and independent of savegames and `<profile>.player-ux.json`).
**Back without saving** does not change the language. Title, Pause and Options
are localized with the shared JSON catalogs. The underlying authored project
language is unchanged. Some specialist gameplay windows are not yet translated.
