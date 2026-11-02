# Unified Add-on Foundation — PR 1

This PR adds the **headless metadata contract**, not the Qt Add-on Manager UI
(PR 2), runtime event hooks (PR 3) or executable third-party Python plugins.
Nothing in an add-on descriptor is executed, mounted, imported, or written to
a GameProject by this registry.

## Unified API

`drawtemp.addons.AddonManager` exposes `register`, `register_file`,
`status`, `statuses`, `manifest`, `enable`, `disable`,
`unregister`, `lock`, and `verify_lock`.

- Version 3 manifests are strict JSON, size-limited to 64 KiB.
- Unique ids and reverse-domain namespaces; exact schema, finite JSON,
  no duplicate keys, executable fields or symlink loading.
- SemVer validation and SDK feature negotiation: `addons-foundation.v1`.
- Dependencies by id and half-open version interval. Missing/out-of-range
  requirements fail registration; enabled dependents block disabling/removal.
- Permissions are precisely derived from declared contribution points.
  Registration is disabled by default; `enable` requires explicit exact
  grants and enabled dependencies. Grants are **ephemeral registry metadata**.
- A deterministic SHA-256 lock snapshot detects manifest changes. It is not
  a signature, authenticated publisher identity, export approval or saved
  permission grant.

## Backwards-compatible inventory

Existing readers, SDKs and Studio workflows remain untouched:

| Existing contract | Validator | New registry |
| --- | --- | --- |
| R15 `api_version=1` | `drawtemp.export.extensions` | Read-only inventory |
| R24.B `api_version=2` | `drawtemp.studio.plugins` | Read-only inventory |
| R47.A `schema=1` | `drawtemp.sdk.modding` | Read-only inventory |

Legacy manifests **cannot** be enabled through the new registry, and existing
permission states are not copied into it. Nothing silently migrates old
GameProject extension data. PR 2 can build the Qt façade using these statuses
while keeping legacy workflows authoritative.

## v3 contribution points

`studio.dock`, `studio.tool`, `studio.menu`, `game.event`,
`assets.pack` and `project.template`, all containing inert
`{id, point, config}` declarations. These are **reserved contracts** only.
Host-side point-specific config validation, safe UI construction, transactions,
export-time enforcement and support for these actions must be implemented
before contributions can function. In particular, `enabled` does not
mean an editor brush or runtime command is operational.

The `rights` fields are self-reported author metadata, not proof of legal
rights to redistribute.

## Example

See [terrain-brush.json](../examples/addons/terrain-brush.json).

```python
from drawtemp.sdk import AddonManager

manager = AddonManager()
manager.register_file("examples/addons/terrain-brush.json")
assert manager.status("terrain-brush")["enabled"] is False

manager.enable("terrain-brush", grants=["project.read", "map.tiles.write"])
assert manager.verify_lock(manager.lock())
manager.disable("terrain-brush")
```

## Validation

```sh
python -m unittest tests_standalone.test_drawtemp_addons_foundation -v
python -m unittest tests_standalone.test_drawtemp5_r24b tests_standalone.test_drawtemp_r47a_modding -v
```

The dedicated CI workflow covers Python 3.10 and 3.12 on Linux and Python
3.12 on Windows/macOS. CI is not a substitute for future Qt/Player qualification.
