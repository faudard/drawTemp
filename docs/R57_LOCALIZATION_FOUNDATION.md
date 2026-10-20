# R57.A / R57.B / R57.C — Localization, Translation Studio & Accessibility (incremental)

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
new keys are seeded only if missing. Source drift blocks Translation
Studio saves until the user explicitly confirms reconciliation of stale keys;
that operation clears only translations for changed sources. Other authoring surfaces, including unrelated
legacy Qt/Tk widgets, are **not yet fully translated**.

Studio: **Outils → Translation Studio R57**; search keys and sources, inspect
context, edit the target translation, preview pseudo-localization, then save.
The sidecar is independent from the R1 Undo/Redo history and the canonical
project save. A project must be saved before sidecar editing.

Player: the presentation-only Qt bridge loads the sidecar for authored content,
projects title/subtitle and scene/choice labels, and provides a language picker
under **Options** (FR/EN and two pseudo-locales). Language switching does not
touch the deterministic gameplay simulation. An invalid sidecar is rejected
rather than silently executed. The selected language now persists through the R57.C presentation-only
accessibility file. Pseudo-languages are development/QA aids, not human
translations.

## R57.C — persisted accessible Player presentation

R57.C extends the Qt Player with an independent "r57-accessibility.json"
beside (but never inside) player-preferences.json and the campaign checkpoint
slots. It saves language, 100–200 % subtitle scale, reduce_motion and
reduce_flashes using a strict v1 document with validation, atomic replacement,
and retained .invalid evidence before replacing corrupt input.

- Player Options offers the FR/EN/pseudo-language selector, caption slider,
  reduced battle animation and reduced cinematic flashes. Existing R12 text
  scaling/high-contrast preferences remain supported with their **unchanged**
  v1 schema.
- Dialogue and cinematics scale their caption text, with exposed Accessible
  names; the Options popup explicitly focuses the language control on open,
  using native Qt Quick Tab / Shift+Tab traversal.
- Canonical R12 animation events and cinematic clocks are unchanged. The
  view-only projection removes clips when reduce_motion is enabled; strips
  "camera_shake" and "light" metadata and suppresses fade overlays when the
  appropriate toggle is enabled. This reduces the effects explicitly handled
  here, **not every effect produced by future renderers**.
- The deterministic contrast audit in drawtemp.quality.r57_a11y checks six
  fixed text/background palette pairs with WCAG 2.x luminance/contrast maths.
  It deliberately cannot assess changing images, translucency, actual font
  sizes or dynamic/third-party visual widgets.
- A Qt QTest keyboard smoke exercises Translation Studio search and selection;
  a Player Qt bridge test checks persistence without any gameplay revision
  change. The GitHub CI matrix runs these and legacy R12 preference checks.

A physical gamepad driver, complete controller-only traversal, native assistive
technologies (NVDA/Orca/VoiceOver), actual visual contrast/focus review and
photosensitivity testing with real hardware are **not certified** here. The
Qt 6.8 packaged dependency does not guarantee a cross-platform Gamepad API;
do not report controller support without a tested input backend. The global
R57 gate remains NO-GO.

## Manual validation

    python -m unittest tests_standalone.test_drawtemp5_r57.R57CatalogTests tests_standalone.test_drawtemp5_r57c.R57CAccessibilityTests tests_standalone.test_drawtemp5_r12_preferences -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp5_r57 tests_standalone.test_drawtemp5_r57c -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.player.qt_app --smoke --reference

GitHub Actions adds headless and Qt-offscreen jobs on Ubuntu, Windows and
macOS. Offscreen jobs cannot certify real GPU rendering, voice navigation,
screen readers or gamepads.

## Remaining gates (NO-GO)

R57.A still needs broad string-extraction coverage and migrations for all
legacy editors. R57.B still needs visual context linked to all asset types
and full Studio keyboard test sessions. R57.C now has partial automated
preferences, subtitle sizing, focus and contrast proof, and targeted visual
effect reductions; it still needs a complete controller input backend,
native focus/contrast auditing, photosensitivity review, assistive
technologies and real hardware evidence. **VS-57 / full R57 remains NO-GO** until one complete
narrative act is available in two human-checked languages plus pseudo-locale,
with a verified no-mouse Player/Studio walkthrough.
