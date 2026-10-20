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
- story.<scene_id>.line.<line_id>.speaker and .text (R42 Narrative v2);
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
- A Qt QTest keyboard smoke exercises Translation Studio search and selection.
  Ctrl+F, Ctrl+L, Ctrl+E target the search, key list and translation editor,
  with Ctrl+S for saving. Translation Studio takes an immutable snapshot of
  the saved AuthoringSession, rejecting later edits instead of overwriting
  translations. The Player now exposes F10 for Options, initial focus on
  language and focus restoration on close; Tab/Shift+Tab use native controls.
- Canonical R42 Narrative v2 line IDs now own distinct stable keys. The
  currently saved line id selects the matching localized subtitle (speaker
  and text), preserving the actual dialogue cursor/choice eligibility,
  both before and after a genuine Player checkpoint/reload.
- A Player Qt bridge test checks persistence without any gameplay revision
  change. The GitHub CI matrix includes R12 preferences, R42 checkpoint
  progression and Python syntax preflights alongside R57.

A physical gamepad driver, complete controller-only traversal, native assistive
technologies (NVDA/Orca/VoiceOver), actual visual contrast/focus review and
photosensitivity testing with real hardware are **not certified** here. The
Qt 6.8 packaged dependency does not guarantee a cross-platform Gamepad API;
do not report controller support without a tested input backend. The global
R57 gate remains NO-GO.

## Auditable automated language readiness (still not certification)

The headless `drawtemp.localization.qa` reader consumes the actual saved
GameProject manifest plus its optional sidecar, without changing either
source or the tactical simulation. Its JSON evidence lists every missing or
overlong target-language key, stale source key, pseudo-RTL isolate failure
and totals for authored FR/EN coverage. Automated passage explicitly
**does not** certify translated prose or end-to-end accessibility.

    python -m drawtemp.localization.qa path/to/game.game.json path/to/game.l10n.json --json-out /tmp/r57-evidence.json

Return codes: `0` = **automated** checks pass; `1` = incomplete/failed
coverage; `2` = bad input or unreadable sidecar. The report always lists the
outstanding human QA gates: FR/EN narrative review, screenshot overflow and
bidi shaping, native assistive technology, controller-only hardware gameplay
and photosensitivity/device inspections. It is safe to run against external
published Content/GameProject projects as a separate, read-only preflight.

## Manual validation

    python -m compileall -q drawtemp/localization drawtemp/player/r57_accessibility.py drawtemp/quality/r57_a11y.py drawtemp/studio/r57_translation_qt.py
    python -m unittest tests_standalone.test_drawtemp5_r57.R57CatalogTests tests_standalone.test_drawtemp5_r57c.R57CAccessibilityTests tests_standalone.test_drawtemp5_r12_preferences tests_standalone.test_r42_narrative_player tests_standalone.test_drawtemp5_r57_qa -v
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
