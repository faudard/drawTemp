# Studio 5 — Editor-first docking (Qt ADS)

The **Qt 6 Studio** and the **R5 MapWindow** can use [Qt Advanced Docking
System](https://github.com/githubuser0xFFFF/Qt-Advanced-Docking-System) via
its [PySide6 binding](https://github.com/mborgerson/pyside6_qtads).
The old Tk UI is not modified. This is a *presentation-only* change: the
canonical `AuthoringSession`, R3 QML viewport, R1 Content, GameProject,
undo/redo and Player are unchanged.

## Installation (Windows, Python 3.12)

```powershell
py -3.12 -m pip install -e ".[qt6-docking]"
py -3.12 -m drawtemp studio --smoke
py -3.12 -m unittest tests_standalone.test_studio_qtads -v
```

The existing `qt6` extra remains unchanged. `qt6-docking` pins
`PySide6-QtAds==5.1.1.1` and PySide6 6.8.3 on Python 3.12. Verify this
combination on Windows and the actual CI runners before enabling ADS by
default in an installed distribution: prebuilt bindings may be built
against a newer Qt binary. **If ADS is absent**, the Studio continues with
its original native QDockWidgets. An incompatible installed binary should
be investigated rather than ignored.

## Layout and UX

- Studio: central workspace never floats or closes. Project Explorer sits
  on the left, Inspector starts in the **right auto-hide sidebar**, and
  Problems/Diagnostics stays closed by default, accessible from Display.
- MapWindow: exactly the same QQuickWidget/renderer occupies the center.
  Maps/Missions is docked left. Inspector, Layers, assets, prefab tools,
  generator and other contextual tool panels are dockable on the right and
  default to right auto-hide. The pre-existing R6 Construction and R27
  Dungeon Qt native docks remain context-dependent.
- Click a right sidebar tab to expand it; click elsewhere to collapse.
  The dock pin control changes auto-hide/docked state. Drag tabs to dock
  left/right/top/bottom, group in tabs, or float to another monitor.
- The shell's **Display → Focus Editor (F11)** hides Explorer, Inspector,
  and Problems temporarily; pressing F11 again restores their layout.
- Layout is UI-only, stored in QSettings under `window/ads_v1` for each
  Qt Studio/MapEditor5 app. Native fallback layouts remain under the
  previous `window/docks` and `window/native_v1` keys. `--reset-layout`
  on the Studio entrypoint clears saved window settings.

## Verification / merge gate

1. On Windows 10/11 with Python 3.12, run both GUI smoke entrypoints and
   `tests_standalone.test_studio_qtads` with and without ADS.
2. In the Studio select Map, then switch Map/Construction/Events. Verify
   there is still one R3 renderer and no lost map selections.
3. Collapse/expand Inspector and Layers, drag between sides, float/re-dock
   on another monitor, close/reopen. Restore the dock layout.
4. Test F11 twice, then save, undo/redo, workspaces, playtest and project
   switching. In Focus Mode close/reopen and verify the previous layout.
5. Repeat at 1280×800 and 1650×900, with 100% and 150% DPI.
6. Test the native QDockWidget fallback (remove PySide6-QtAds) and ensure
   core map editing, rendering, save, and project navigation still work.

**Status:** Implementation in PR. Qt ADS native-binary / QML integration
qualification on the real Windows environment is required before merge.
