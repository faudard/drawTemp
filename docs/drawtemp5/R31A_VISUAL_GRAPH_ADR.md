# R31.A — ADR: Visual Graph → R9 Event Graph

**Date:** 2026-10-19. **Status:** R31.A implementation candidate, not certified R31 or release 7.1. **Target:** consolidated PR #339. The final integrated master SHA still needs gate validation.

## Decision

R31 visual logic is **authoring data**, not a second event engine. It is compiled into the existing native Content Mission.triggers contract through sporebound.event_composer.save_event and the canonical Content validator. Battle / GameSession continue to dispatch R9 events with their established timing, replay and save rules. No Python callbacks, eval/exec, arbitrary scripts, new quest truth database, runtime graph scheduler or extra save file.

Authored graph definitions live in the existing versioned GameProject.extensions envelope **org.drawtemp.logic**, alongside validated mission references. An AuthoringSession.preview_pair transaction atomically stages the native trigger in Content and the authoring graph in GameProject. Undo/Redo and two-document recovery remain canonical. Legacy projects do not get migrated by merely loading them.

## Contract v1 (restricted R31.A subset)

- Exact graph keys: schema_version=1, id, mission_id, entry, nodes, edges. Identifiers are stable, lowercase ASCII, with a length bound. The compiled R9 event is named r31_ + graph ID.
- Exactly one entry event of kind tick or interact, followed by 1–63 actions of kind message, hazard or despawn. Future node kinds fail with a diagnosed error, not a fallback.
- Directed typed flow ports only: next → flow. All actions have one incoming edge, at most one outgoing; forks, joins, cycles, unreachable nodes, unknown IDs and extra fields are rejected before compilation.
- Compilation follows directed edges, **not display/JSON node ordering**. Parameter validation is strict about text bounds, integer ranges, coordinate length, unsupported keys and bool/int distinctions.
- Maximum 64 nodes and 16 graphs per project, subject also to the existing GameProject extension maximum (64 KiB per namespace). Graph execution has no new CPU or tick loop: native R9 remains the sole runtime.

### Example input (visual authoring document)

\`\`\`json
{
  "schema_version": 1,
  "id": "lever",
  "mission_id": "r0_village_forest",
  "entry": "interact",
  "nodes": [
    {"id": "interact", "kind": "event", "params": {"kind": "interact", "object_id": "lever"}},
    {"id": "feedback", "kind": "action", "params": {"kind": "message", "text": "Porte ouverte"}}
  ],
  "edges": [{"from": "interact", "out": "next", "to": "feedback", "in": "flow"}]
}
\`\`\`

Native R9 representation: an event with id r31_lever, condition interact, object lever and actions consisting of one native message with text Porte ouverte.

## Conflict and migration policy

- A graph cannot silently overwrite a pre-existing native R9 event sharing its generated ID.
- Before updating a previously stored graph, compile its old version and compare it with the current native trigger. If an R9 editor has independently modified the trigger, refuse with native_event_conflict. Future UI must offer explicit reconciliation.
- Graph schema upgrades are **opt-in and transactional**; no automatic destructive downgrade from unknown schema versions.
- Missing mission, invalid graph, malicious payload, invalid rule fields, stale authoring preview and Content/GameProject validation failures all leave the session unchanged.
- Graphs are inert data: importing one does not execute network requests, filesystem operations, arbitrary Python, extensions or hidden game commands.

## Interfaces and tests

Headless internal API in drawtemp.sdk.logic_graph: validate_graph, compile_r9_trigger, graphs_from_project, preview_graph, apply_graph. This API is not yet advertised as stable in SDK_FEATURES.

Test command:

\`\`\`sh
python -m unittest tests_standalone.test_drawtemp_r31_logic_graph -v
\`\`\`

The tests cover static rejection, adversarial graphs, compile ordering, graph storage, atomic preview/Undo/Redo, legacy isolation, save/load, native R9 event collision, stale preview and native EventStudio preview. The CI on the **final merged SHA** must still prove regression-free play, replay, packaging and actual Qt behavior.

## Next increments

R31.B: Qt editor using AuthoringSession, typed action palette and visual connections, search/copy/group, Qt keyboard/mouse tests. R31.C: pure expressions and guarded branch/wait nodes with a versioned deterministic execution budget integrated into canonical events. R31.D: breakpoint/step tracing and causality diagnostics, then reference scenario NPC → locked door → fight → chest → quest plus Qt Player E2E.

R31.3–R31.12 **are not implemented or certified** by R31.A. No real-GPU certification, public release, full action mode node palette or all-genre no-code acceptance is claimed.