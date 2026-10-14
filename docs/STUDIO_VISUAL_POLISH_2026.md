# Game Studio — Visual polish pass (14 October 2026)

## Scope

Visual finishing on the **current master** following the consolidation in
PR #192. This PR is intentionally small and does not replay the older,
now-diverged Studio UX branch #180.

### Shared appearance

- Light and dark palettes are defined in `sporebound/studio_theme.py`.
  Only named, validated modes can be selected. The UI defaults to light.
- Visual hierarchy: neutral window background, elevated navigation areas,
  a readable editor/document surface, muted secondary text, and a single
  cobalt/blue primary action.
- Unified TTK styles for controls, selected workspace navigation, inspector
  headings, tree rows, selection, form inputs and focus colour. Text and
  Canvas widgets are explicitly registered for palette updates.
- Canvas art and tile colours remain owned by the rendering pipeline, not
  this theme layer; no hidden model or renderer is recreated.
- The Playtest timeline uses theme tokens for backdrop, labels and outcomes.
- Prefab cards (including errors and active selection), actor palette and
  asset-library previews use the same surfaces.

### Appearance preference

Choose **Affichage > Thème clair / Thème sombre**. The choice persists
atomically in the UI-only `*.workspace.appearance.json` sidecar.
Malformed files revert safely to light mode. It is never included in
`Content`, `GameProject`, mission exports or savegames.

### Verification

Headless:

    python -m unittest tests_standalone.test_studio_theme_2026 -v

Tk integration gate on Linux:

    SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
        tests_standalone.test_studio_theme_2026 \
        tests_standalone.test_studio_layout_2026 \
        tests_standalone.test_studio_docks_2026 -v

Verify actual Studio at 1280x800 and 1662x896 and at Windows 100/125/150% DPI:
1. No cropped tab text, selectors or labels; focus and hover indicators are
   visible using keyboard navigation.
2. Switch appearance while map, inspector and Playtest chart exist. No lost
   Canvas items, selected resources, analytics or typed edits.
3. Open the asset and actor popups before and after changing theme.
4. Toggle prefabs, groups, focus F11 and explorer; none should turn into a
   second visual system or change the editor document.
5. Verify dark-mode prefabs with alpha images and error states; the
   terrain/actor atlas must not be recoloured.
6. Verify sidecar recovery with corrupt JSON and existing projects that have
   never saved an appearance preference.

The theme token combinations for body text, muted text, action text and
selected rows are tested against a minimum WCAG-style 4.5:1 ratio,
with main body text at least 7:1. This is a static contrast test,
not a substitute for Windows keyboard and accessibility validation.
