# PR 3 — Runtime & Event Addons (native, declarative)

## Architectural boundary

`game.event` is a **v3 declarative native effect compiler**, not a Python
plugin runtime, scripting VM, network-capable mod, dynamic code import or a new
Battle event scheduler. It reuses the already qualified R24.E controlled
`story.choice` hook compiler and the real `StoryBook` /
`GameSession` effects interpreter.

This ensures the event runs in the **exported Player** from canonical
GameProject data. The Player needs no installed addon package, enabled
Add-on Manager or Python code from a creator. Existing saves and replays
retain the canonical project digest and change compatibility explicitly
when an authored hook is added.

## Supported v3 event contribution

See [asterion-event-addon.json](../examples/addons/asterion-event-addon.json).

```json
{
  "id": "scan-reward",
  "point": "game.event",
  "config": {
    "trigger": "story.choice",
    "scene": "briefing",
    "choice": "launch",
    "effects": [
      {"kind": "set_flag", "flag": "addon_scan_ready", "value": true},
      {"kind": "gold", "amount": 5}
    ]
  }
}
```

This contribution must belong to a v3 `kind: "game"` or `"hybrid"`
manifest, declare `event-addons.v1` and `addons-foundation.v1` as
SDK features, and request exactly `events.write` (plus other point
permissions only when such points exist).

**Allowed effects:** `set_flag`, `add_flag`, `unlock_mission`, and
`gold`, as validated by R24.E and canonical GameProject/StoryBook.
Other effects or trigger types (such as per-tick, arbitrary combat rules,
Python scripts, custom QML, subprocess, filesystem or network calls)
are not supported. Max 16 hooks per addon, max 8 effects per hook.
A scene/choice target may only be owned by one compiled hook receipt.
Permissions for the native effects are derived by R24.E; no additional
third-party execution grant exists.

## Authoring UX

1. Open **Tools → Add-on Manager…** (PR 2).
2. Import `examples/addons/asterion-event-addon.json` while editing
   the Asterion example project. The manifest is validated in both
   v3 and R24.E shape before registration, and starts disabled.
3. **Enable…** with explicit `events.write` consent, denied by default.
   No GameProject modification occurs at this stage.
4. **Preview / Compile Events…** shows exact choice targets and native
   effect kinds. Confirm again (default No) to apply one revision-bound
   `AuthoringSession.apply` transaction. Rejected/missing targets,
   duplicate receipts, invalid effects or stale revisions do not mutate.
5. **Save Project** separately. The resulting GameProject includes native
   StoryBook effects and an inert R24.E receipt with content hashes.
6. Disable/remove the addon UI without affecting compiled project data.
   To revert unsaved compilation, use **Edit → Undo**. For persisted
   changes, perform an explicit migration or restore a prior version.
   Disabling an addon never silently removes compiled quest content.

`drawtemp.studio.events.EventStudio` exposes a headless catalogue and
the same preview/install helpers for future visual event workflow integration.
The current Visual Event Graph is not extended with a new native node type:
this is deliberate until such a node has an explicit validated schema.

## Runtime, integrity, migration and compatibility

`drawtemp.player.qt_app.build_controller` checks existing compiled
R24.E receipts before creating a Player controller. Mismatched, deleted,
or tampered compiled effect ranges are refused: no fallback silently
skips a required effect.

This applies to both new v3 compiled hooks and historical R24.E hooks.
Runtime **does not** execute a JSON manifest or ask for add-on permissions.
Permissions are a one-time Studio compilation authorization; the Player
reads only the resulting canonical native StoryBook data.

A receipt stores the SHA-256 of the **compiled R24.E source** and effect
ranges, not a trusted creator signature. V3 manifest version and publisher
identity are not authenticated by this receipt; these require the future
packaging/signature contract. A previously compiled project may be
migrated only by explicit authoring actions. No auto-updates are performed.

## Python SDK

```python
from drawtemp.addons import AddonManager
from drawtemp.sdk import preview_event_addon
from drawtemp.sdk.event_addons import install_event_addon

manager = AddonManager()
manifest = manager.register_file("examples/addons/asterion-event-addon.json")
manager.enable(manifest["id"], grants=["events.write"])
# session is the *existing* canonical AuthoringSession for a game with the
# "briefing" scene and "launch" choice.
plan = preview_event_addon(manager, session, manifest["id"],
                           expected_revision=session.revision)
# Present a diff and obtain explicit confirmation before committing.
session.apply(plan)
```

## Tests

```sh
python -m unittest tests_standalone.test_event_addons.ContractTests tests_standalone.test_event_addons.CompilationTests -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_event_addons.QtStudioPlayerTests -v
python -m unittest tests_standalone.test_drawtemp5_r24e -v
```

CI is required on the final branch SHA (Python 3.10/3.12, Windows,
Linux, macOS headless; Python 3.12 Linux Qt offscreen). Additional
manual Windows/macOS Player, QML, GPU, DPI and export clean-machine
tests remain gates before certifying a public runtime addon ecosystem.
