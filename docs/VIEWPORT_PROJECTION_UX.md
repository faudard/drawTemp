# Viewport Projection UX — 2D / Iso 2.5D

## Where to find it

Open **Carte et combat**. The **VUE DE LA CARTE** strip immediately above the
map canvas contains two radio choices: **2D** and **Iso 2.5D**. Projection
is independent of the tool notebook (Carte & combat / Terrain & couches /
Architecture / Sélection & modèles). You can switch while editing or testing,
without losing the current zoom or selected tiles.

The old isometric checkbox was removed from the **Terrain & couches** tool
pane to avoid two competing projection controls. The new selector and palette
actions all drive the existing `iso_var` and `EditorRenderCache` pipeline:
there is no second renderer and no change to gameplay data.

## Persistence and compatibility

Projection is a **per-mission workspace preference** stored alongside layer
visibility, locks, active floor and interior visibility in
`<content>.mapbuilder-view.json`. The `Content` and `GameProject` files,
saves and replay schema are unchanged.

- Old version-1 mapbuilder sidecars without `projection` still load. Missing
  values default to `2d` and normalize on the next preference save.
- New rows use `projection: '2d'` or `projection: 'iso'`; malformed modes are
  rejected rather than silently replaced.
- Switching missions restores each mission's choice independently. When
  selecting an elevated floor or an asset for isometric placement, the
  existing automatic ISO switch is also remembered.

## Regression gates

```sh
python -m unittest tests_standalone.test_map_layer_workspace_3732c -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_viewport_projection_ux_gui \
  tests_standalone.test_map_editor_gui \
  tests_standalone.test_iso_battle_view_3718_gui -v
```

GUI gate: select a cell, zoom, switch 2D → ISO → 2D, return to the original
projection and verify the selected cell and zoom are unchanged. Switch
missions, reopen the editor and verify their independent projection choices.
Confirm that the content file is untouched by presentation-only actions.
