# R38.1 — Global Search and Typed Usages

**Scope:** first P0 delivery of [Creator Tools Pro R38](DRAWTEMP_7_1_TO_8_0_DETAILED_ROADMAP.md). This is an authoring read-only projection, **not** the whole R38 gate.

## Author workflow

In Qt Studio, open **Outils → R38 • Recherche globale et utilisations…**, or press **Ctrl+Shift+F** (also available from the command palette). Search by display name, stable ID, mission, type or relative registry path. Accents and case are ignored; every token must match. Narrow by family and mission.

The panel includes canonical Content/GameProject resources (project, maps, placed actors/objects/events, campaigns, scenes and cinematics), assets and animation frames, and R31 logic graphs with individual nodes. Results have mission-qualified stable identities; two "gate" objects on separate maps remain distinct. Only the first 200 matches are rendered, in deterministic order.

Select a hit to inspect incoming **Utilisé par** and outgoing **Utilise** typed references with exact field and source path. Existing resources navigate through the R2 explorer; graph hits open the R31 workshop. Assets are discoverable and inspectable, not edited via the generic inspector.

## Contracts

- GlobalSearchIndex accepts an immutable AuthoringSnapshot or detached pair. No extra database, hidden registry, permanent cache, new gameplay schema or disk scan.
- Only known typed fields count as usages. Matching dialogue words are not interpreted as ID references.
- Referenced actors and objects use (family, mission_id, resource_id), preventing cross-map false positives.
- The dialog indexes the current session snapshot; concurrent revision changes trigger a rebuild rather than stale navigation.
- No user edit, RNG call, graph evaluation, save or serializer rewrite. R1 Undo/Redo, R9, R24 and R31 remain authoritative.
- Paths are advisory and cannot authorize deletion, refactor or bypass validation.

## Tests and acceptance

~~~sh
python -m unittest tests_standalone.test_drawtemp_r38_search -v
python -m unittest tests_standalone.test_drawtemp5_r2_cd -v
~~~

Qt smoke uses PySide6 offscreen (QT_QPA_PLATFORM=offscreen). CI includes headless Ubuntu/Windows/macOS and a Qt smoke job. Acceptance requires large projects, duplicate IDs on distinct maps, sprite/animation usages, R31 visual nodes and revision changes while the dialog is open.

## Next slices

R38.2: prefab variants and inherited overrides. R38.3: typed cross-document renames with reviewed diff and single Undo transaction. R38.4–6: preflight validation, project CI and collaborative conflict resolution based on R24.G semantic VCS. R38.8/R38.12: cancelable jobs and real two-author conflict trials.

**Status:** code in PR; do not mark R38 certified before CI, UX and multi-author gates.
