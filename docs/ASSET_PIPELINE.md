# 2.4.3 — Portable asset pipeline

`GameProject.assets` is an optional versioned registry, independent of tactical
content and of any renderer. Old projects omit the field on serialization, so
existing project digests and session saves remain compatible. Like other project
configuration, changing a nonempty registry changes the project digest; an old
save then reports `Project mismatch`. File bytes are not embedded or hashed in
saves. Missing art never blocks headless gameplay or replay.

## Contract

```json
{
  "version": 1,
  "entries": [
    {"id": "hero", "kind": "sprite", "path": "art/hero.png"},
    {"id": "face", "kind": "portrait", "path": "art/face.png"},
    {"id": "music", "kind": "sound", "path": "audio/music.ogg"},
    {"id": "idle", "kind": "animation", "loop": true,
     "frames": [{"sprite": "hero", "duration_ms": 120}]}
  ],
  "bindings": {
    "sprite": {"hero": "hero"},
    "portrait": {"hero": "face"},
    "sound": {"title": "music"},
    "animation": {"hero_idle": "idle"}
  }
}
```

Put this object in the `assets` field of a game manifest. IDs and binding slots
use 1–128 ASCII letters/digits, underscores, dashes or dots (no leading dot).
Asset IDs are unique, including case-insensitive collisions. Slots are names
owned by presentation code, not implicit references to tactical unit IDs; a
renderer can bind a shared portrait to several slots. All binding values and
animation frames must refer to an existing asset of the correct kind. Forward
references are allowed. Frames reference whole PNG sprites with positive integer
durations in milliseconds; animation-to-animation references are forbidden.

PNG sprites/portraits and WAV/OGG sounds use forward-slash paths relative to the
**game manifest directory**, not the working directory or tactical content file.
Absolute paths, parent traversal, Windows drives, reserved Windows filenames,
and other nonportable spellings are rejected. Files must remain under the root,
including through symlinks. Exact case is checked on all platforms.

## Validation and consumption

```python
project = GameProject.load(project_path, content)
registry = project.asset_registry()  # structural/reference checks only
issues = registry.diagnostics(project_path.parent)  # all file errors, sorted by ID
portrait = registry.binding("portrait", "hero")  # descriptor or None
if portrait is not None:
    image_path = registry.resolve(portrait["id"], project_path.parent)
```

`resolve()` checks existence and confinement; `diagnostics()` also checks PNG,
RIFF/WAVE and Ogg signatures. Signature checks are **not full media decoding**:
truncation after a valid header, codec support, dimensions and frame atlases must
be checked by future renderer/import tools. No image/audio library is imported
and no game rule is evaluated here. Descriptors and serialization are defensive
copies; mutate project data then validate to author a new registry.

```sh
python -m sporebound validate --project /path/to/game.json
```

Without `--project`, existing tactical-content validation is unchanged. Invalid
files produce a JSON report with `valid: false`, asset IDs and messages, and exit
status 1. Invalid structures/references fail project loading with `RuleError`.
Empty or absent registries remain valid. There is no silent fallback for a
referenced but missing file; presentation code owns its optional fallback policy.

## Reproducible sample

From the checkout, create a **new** destination directory:

```sh
python examples/asset_pipeline.py --output /tmp/sporebound-assets-demo
python -m sporebound validate --project /tmp/sporebound-assets-demo/game.json
```

The sample copies retained Momo artwork and creates a silent WAV placeholder.
It demonstrates all four asset kinds, including a one-frame idle animation.
Move the entire generated directory and validate again: no absolute path is
stored. This is an asset contract example, not a renderer or finished animation.

## Next integration steps

2.5.5 Project Workspace should own project-relative import/copy/rename and
reference-aware deletion. Studio panels and the 2.6 renderer should consume the
same registry. Atlas slicing, decode validation, caches, thumbnail UI, hot reload,
and packaging artwork inside distributable games remain future work. Existing
repository artwork is retained; no automatic mass migration is performed.
