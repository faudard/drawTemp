# PR 2 — Studio Extension Points (declarative, Qt-hosted)

The R24 Studio plugins, R47 mods and R58 resource packs remain supported by
their existing managers. The unified v3 `AddonManager` from PR 1 now has
**three concrete, bounded Studio extension points**.

## Installation and session lifecycle

1. In the native Studio menu choose **Tools → Add-on Manager…**.
2. Choose **Import JSON…** and select an explicit local v3 manifest.
3. Inspect the id, version, SHA-256, capabilities and required permissions.
4. Choose **Enable…** and explicitly approve the *exact* permissions.
   The default response is **No**.
5. Use **Tools → Add-on Actions**, the right-side dock, or the Map Editor's
   new **Add-on brushes** combo (only shown when presets exist).
6. **Disable** removes all mounted UI and map presets; **Remove** forgets the
   descriptor in this session. Neither operation deletes user files.
7. Opening, closing or replacing a project clears all v3 grants and
   descriptors. Addons are never auto-loaded from the project or QSettings.

This work adds no second authoring state, project/schema migration, local
settings permission persistence, background scripts, third-party QWidget,
QML, Python module, executable entry point or arbitrary external actions.

## Implemented v3 points

| Point | Strict `config` | Host implementation |
| --- | --- | --- |
| `studio.dock` | `{"title":"Overview","fields":["project.title","project.campaign_count","content.mission_count"]}` | DrawTemp creates read-only Qt labels in a dock. Refreshes from current AuthoringSession snapshot. |
| `studio.menu` | `{"label":"Open Events","command":"go_events"}` | Native QAction in Tools → Add-on Actions. Only existing host commands `go_maps`, `go_actors`, `go_events`, `global_search`, `focus_inspector` are permitted. |
| `studio.tool` | `{"label":"Grass Brush","material":"grass","radius":1,"shape":"diamond"}` | Registers a user-selectable preset on the existing R5 MapWindow brush (no new painter, renderer or map schema). Supported surfaces come from `MapStudio.SURFACE_PALETTE`. |

An addon may declare several points, provided that its v3 manifest already
requests precisely the required permissions. A host-specific validator rejects
unknown config keys, unsafe command references, bad terrain types, duplicate/
unknown inspector fields, or invalid brush radius/shape.

**Important:** `studio.tool` does not install a new painting algorithm;
it configures the existing native R5 brush. A fully custom brush, event node,
character editor part, native game runtime or Player-side behavior requires
explicit, separately reviewed host contracts in later PRs.

## Examples

- `examples/addons/terrain-brush.json` (single map brush preset).
- `examples/addons/studio-inspector-demo.json` (read-only dock and Events menu).

An addon must be enabled before its points are visible. Example in code:

```python
from drawtemp.addons import AddonManager
from drawtemp.studio.addon_points import studio_contributions

registry = AddonManager()
registry.register_file("examples/addons/terrain-brush.json")
assert studio_contributions(registry) == ()
registry.enable("terrain-brush", grants=["project.read", "map.tiles.write"])
assert studio_contributions(registry)[0]["point"] == "studio.tool"
```

## Security and compatibility boundaries

- All Qt widgets, actions and map edits are owned by DrawTemp.
- A v3 descriptor is never treated as callable code. No dynamic import,
  QML path, shell command, web/network access, untrusted filesystem path or
  arbitrary callback is created.
- Legacy R15/R24/R47 formats remain **inventory only** in the unified registry;
  their current dedicated Studio dialogs remain operational.
- A failed local manifest is rejected before any Qt UI is mounted.
- The Studio uses the original AuthoringSession; selecting a brush merely
  changes native UI controls. Subsequent user painting still follows
  existing MapStudio validation and undo/redo.
- Pack/code signing, publisher provenance verification, package
  installation and automatic update remain outside PR 2.

## Tests

```sh
python -m unittest tests_standalone.test_studio_addon_points.StudioPointsTests -v
python -m unittest tests_standalone.test_studio_addon_points.QtStudioAddonTests -v
python -m unittest tests_standalone.test_drawtemp_addons_foundation -v
```

Qt smoke requires Python 3.12 with `PySide6==6.8.3` and a software Qt Quick
backend. CI runs headless tests on Windows/Linux/macOS and a Linux Qt offscreen
smoke; full interactive/high-DPI testing and ADS-specific QA are still needed.
