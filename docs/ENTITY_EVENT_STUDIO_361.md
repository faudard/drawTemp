# Entity & Event Studio 3.6.1 — Visual Branch Graph Scale & Compare

**Base:** Visual Branch Graph 3.6 (#145). This is a follow-up stacked
change. Integrate 3.4/3.5/3.6 before this PR.

## User-visible experience

In the existing **Arbre narratif** tab, the existing scene/event canvas,
ports, contextual inspector and authoring commands are retained:

1. **Disposition: Normal / Compact** changes the computed geometry, not
   the scene definitions. Normal spacing remains byte-for-byte equivalent to
   the previous layout; Compact uses 260px horizontally and 94px vertically
   (at 100% zoom) instead of 320px and 125px.
2. **Regrouper** hides descendants *after* each first-level scene with
   further links, reducing a complex campaign to its primary branches.
   The existing occurrence-based **Replier / déplier** remains available
   for drilling down. **Déployer tout** restores the whole tree, subject
   to the existing display cap.
3. The new inspector displays summaries of each first-level branch:
   number of distinct scenes, endings and choice-guarded tactical events.
   Counting is bounded; explicit `LIMITÉ` appears if budgets are hit.
4. Select any occurrence and click **Marquer A**, then select another
   occurrence and click **Marquer B**. Click **Comparer A / B** to inspect:
   - shared decisions / shared prefix;
   - exclusive choice IDs and labels on each path;
   - narrative and tactical effects on each choice;
   - choice-gated tactical events unique to A, unique to B, or common.
   The canvas colors selected paths blue (A), orange (B), and violet
   (shared prefix). **Effacer A / B** clears the overlays.
5. All comparisons resolve canonical `scene_id` and choice IDs using
   **StoryBook occurrence paths**. Shared scenes can have several
   occurrences without copying their authoring data. Changing roots
   invalidates obsolete selections.

## No alternate game model

`sporebound/story_graph_scale.py` is a bounded, read-only projection
of `GameProject.story.scenes` and canonical
`Mission.triggers[*].after_choice`. The pure helpers are:

- `trace_occurrence(story, root, occurrence_tuple)`;
- `compare_occurrences(story, content_data, mission_id, root, path_a, path_b)`;
- `grouped_branches(story, root, content_data, mission_id)`;
- `grouped_collapse_paths(story, root)`;
- `format_path_comparison(report)`.

`StoryGraphScaleControls` adds controls to `StoryGraphEditor` rather
than a new tab or renderer. `build_story_tree(density='normal')` remains
the default API. Existing graph budgets, scene authoring, canvas ports,
undo/redo, saves and Player replay are unchanged by these presentation
features.

**Scope limitation:** path comparison is a **static authoring analysis**.
It reports declared effects and event guards, not the actual runtime value
of flags, AI decisions, turn order or Player replay results. A simulated
battle still belongs to Event Studio's real-engine preview and game tests.

## Stabilization included

The 3.5 wizard and 3.6 cross-document link authoring now install both
validated content/project versions *before* `design_change` triggers
global Studio refresh/history. Previously, a temporary state containing
`after_choice` but not yet its `GameProject.story` could cause a
GUI validation failure. Failed or declined Content publication reverts
the provisional project pointer. This does not add a schema.

## Tests

```bash
python -m unittest tests_standalone.test_story_graph_scale_361 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest discover \
  -s tests_standalone -p test_story_graph_scale_361_gui.py -v
python -m unittest tests_standalone.test_visual_branch_graph_36 \
  tests_standalone.test_event_branch_builder_35 \
  tests_standalone.test_event_choice_branches_34 -v
```

The CI editor job runs the real Tk test automatically.
Gate: at least two selected routes on the same root show different
effects and guarded events, grouping/compact spacing reduce the
display footprint, and no edit to `Content`, `GameProject` or replay
occurs as a side effect of comparison.
