# UI language foundation (English first)

**Default language: English (`en`)** for a newly created GameProject and a
fresh Qt Studio installation. French (`fr`) can be selected explicitly.
Studio: **Tools → Language → English / Français**. Player:
**Options (F10) → Language**. Each application retains its language choice
in its existing presentation preferences: Studio QSettings `language`, and
Player `r57-accessibility.json` per save directory.

`drawtemp.localization.ui.ui_text(key, language, **params)` is the common
presentation-only UI vocabulary. Add new keys in both `UI_STRINGS` mappings.
Use the stable key in Qt Widgets or `root.ui(key)` in Qt Quick. Unsupported
language codes and missing translations fall back to English, with no
dependency on system locale. A missing key itself is returned, making gaps
visible during development. Do not use translated text for action IDs,
serialization, event routing, game logic, or replay state.

**Two concepts stay separate:** `GameProject.options.language` is the
authored content's source language, while the editor's language selection and
the Player accessibility setting control the displayed interface. Existing
French-language project manifests are loaded unchanged; they are *not*
silently rewritten as English sources. Player story/dialogue translations
continue to use R57 `game.l10n.json`, including source drift checks.
New GameProject instances start with an English source language.

Initial UI conversion covers Studio's top-level menus, core file/edit/playtest
actions, workspace navigation, and the Player's main Options/Pause controls
and a few primary game labels. Legacy Studio workspaces, Tk windows, and
other fixed French strings remain to be migrated incrementally. This is **not**
a claim of full French/English coverage.

Validate with:
```
python -m unittest tests_standalone.test_ui_locale_defaults -v
python -m compileall -q drawtemp/localization drawtemp/studio/qt_shell.py drawtemp/player/qt_app.py
```
Qt integration smoke and manual visual overflow review are needed before
full multilingual UI signoff.
