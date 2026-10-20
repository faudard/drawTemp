# R57.A / R57.B — Localization & Translation Studio (incremental)

## Scope in this PR

This is a **first functional increment**, not certification of R57. The
historical Content, GameProject v1 and GameSession save/replay schemas remain
unchanged. An authored game can optionally carry "game.l10n.json" alongside
"game.json" and "game.game.json". Existing games without this file play unchanged.

The drawtemp.localization headless module validates a strict, versioned
catalogue with stable keys, a documented source language (French or English),
"one" / "other" plural forms, simple "{name}" interpolation (no attribute or
index access), source drift detection, explicit source fallback, translation
length audits and deterministic "qps-ploc" / "qps-plocm" pseudo-languages.
The mirrored pseudo-language is an RTL inspection aid, **not proof of correct
RTL shaping**. An atomic UTF-8 write with file-revision checking rejects
concurrent sidecar changes rather than overwriting them.

## What is localized

Stable keys are initially seeded from the canonical project snapshot:

- project.title / project.subtitle;
- campaign.<id>.name and .description;
- story.<scene_id>.title, .speaker and .text;
- story.<scene_id>.choice.<choice_id>.label.

Existing project text is never replaced or automatically migrated in-place;
new keys are seeded only if missing, and source drift blocks Translation
Studio saves until reconciled. Other authoring surfaces, including unrelated
legacy Qt/Tk widgets, are **not yet fully translated**.

Studio: **Outils → Translation Studio R57**; search keys and sources, inspect
context, edit the target translation, preview pseudo-localization, then save.
The sidecar is independent from the R1 Undo/Redo history and the canonical
project save. A project must be saved before sidecar editing.

Player: the presentation-only Qt bridge loads the sidecar for authored content,
projects title/subtitle and scene/choice labels, and provides a language picker
under **Options** (FR/EN and two pseudo-locales). Language switching does not
touch the deterministic gameplay simulation. An invalid sidecar is rejected
rather than silently executed. Changes to language are **session-local** in
this increment; persistent settings belong to R57.C.

## Manual validation

    python -m unittest tests_standalone.test_drawtemp5_r57.R57CatalogTests -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp5_r57 -v

GitHub Actions adds headless and Qt-offscreen jobs on Ubuntu, Windows and
macOS. Offscreen jobs cannot certify real GPU rendering, voice navigation,
screen readers or gamepads.

## Remaining gates (NO-GO)

R57.A still needs broad string-extraction coverage and migrations for all
legacy editors. R57.B still needs visual context linked to all asset types,
actual subtitle sizing and keyboard test sessions. R57.C still needs
persistent Player language/preferences, focus/contrast audits, flash/shake
reduction, controller-only walkthroughs, assistive technology and real
hardware evidence. **VS-57 / full R57 remains NO-GO** until one complete
narrative act is available in two human-checked languages plus pseudo-locale,
with a verified no-mouse Player/Studio walkthrough.
