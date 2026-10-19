"""R36.B2 deterministic visual timeline: schema, R1 history and tick semantics."""
from __future__ import annotations

from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring
from drawtemp.studio.animation_timeline_authoring import AnimationTimelineAuthoring
from sporebound.animation_graph import AnimationGraphError
from sporebound.animation_timeline import (
    NAMESPACE, cues_crossed, timelines_from_project, validate_timeline,
)
from sporebound.game_project import GameProject
from tests_standalone.test_r36_animation_graph import authored, graph, registry


def timeline():
    return {
        "schema_version": 1, "id": "hero_cues",
        "controller_id": "hero_animation",
        "tracks": [
            {"state": "attack", "markers": [
                {"id": "windup", "at_ms": 40, "cue": "glow"},
                {"id": "swish", "at_ms": 90, "cue": "spark"}]},
            {"state": "idle", "markers": [
                {"id": "breath", "at_ms": 0, "cue": "dust"}]},
        ],
    }


class AnimationTimelineTests(unittest.TestCase):
    def test_validation_and_invalid_marker_fail_closed(self):
        value = validate_timeline(timeline(), graph(), registry())
        value["tracks"][0]["markers"][0]["cue"] = "changed"
        self.assertEqual(timeline()["tracks"][0]["markers"][0]["cue"], "glow")
        for mutate in (
            lambda d: d.update(schema_version=True),
            lambda d: d.update(controller_id="missing"),
            lambda d: d["tracks"][0]["markers"][0].update(at_ms=180),
            lambda d: d["tracks"][0]["markers"][0].update(at_ms=True),
            lambda d: d["tracks"][0]["markers"][0].update(cue="hitbox"),
            lambda d: d["tracks"][0]["markers"][0].update(cue="damage"),
            lambda d: d["tracks"][0]["markers"].append(
                deepcopy(d["tracks"][0]["markers"][0])),
            lambda d: d["tracks"].append(deepcopy(d["tracks"][0])),
        ):
            bad = timeline()
            mutate(bad)
            with self.subTest(bad=bad), self.assertRaises(AnimationGraphError):
                validate_timeline(bad, graph(), registry())

    def test_committed_tick_crossings_are_repeatable_and_frame_independent(self):
        markers = cues_crossed(timeline(), graph(), registry(),
                               state="attack", entered_tick=1,
                               from_tick=1, to_tick=12)
        self.assertEqual([(m["tick"], m["cue"]) for m in markers],
                         [(4, "glow"), (7, "spark")])
        sections = []
        for start, end in ((1, 4), (4, 8), (8, 12)):
            sections.extend(cues_crossed(timeline(), graph(), registry(),
                            state="attack", entered_tick=1,
                            from_tick=start, to_tick=end))
        self.assertEqual(sections, markers)
        self.assertEqual(cues_crossed(timeline(), graph(), registry(),
                         state="attack", entered_tick=1, from_tick=12,
                         to_tick=15), [])
        # Looping presentation state marks the beginning of each cycle,
        # including the exact start at entered_tick.
        loops = cues_crossed(timeline(), graph(), registry(), state="idle",
                             entered_tick=0, from_tick=-1, to_tick=16)
        self.assertEqual([m["tick"] for m in loops], [0, 8, 15])
        self.assertEqual([m["cycle"] for m in loops], [0, 1, 2])

    def test_time_budget_and_non_authoritative_marker_types(self):
        for bounds in ((0, 999), (5, 4), (0, True), (-5, 2)):
            with self.subTest(bounds=bounds), self.assertRaises(AnimationGraphError):
                cues_crossed(timeline(), graph(), registry(),
                             state="idle", entered_tick=0,
                             from_tick=bounds[0], to_tick=bounds[1])
        # UI-only cues are not attacks; no access to GameSession/Battle here.
        self.assertNotIn("damage", {m["cue"] for t in timeline()["tracks"]
                                   for m in t["markers"]})

    def test_canonical_transaction_undo_redo_load_and_delete_guard(self):
        session = authored()
        controller = AnimationControllerAuthoring(session)
        controller.apply(controller.preview(graph()))
        editor = AnimationTimelineAuthoring(session)
        baseline = session.snapshot().to_dict()
        plan = editor.preview(timeline(), expected_revision=session.revision)
        self.assertEqual(baseline, session.snapshot().to_dict())
        editor.apply(plan)
        self.assertEqual(editor.timelines(), [timeline()])
        with self.assertRaises(AnimationGraphError):
            editor.preview(timeline(), expected_revision=0)
        with self.assertRaises(ValueError):
            controller.preview_remove("hero_animation")
            # An orphaned timeline must not survive an R1 transaction.
        session.undo()
        self.assertEqual(editor.timelines(), [])
        session.redo()
        self.assertEqual(editor.timelines(), [timeline()])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "timeline.json"
            session.save_as(path)
            loaded = AuthoringSession.open(path)
            self.assertEqual(AnimationTimelineAuthoring(loaded).timelines(), [timeline()])
        editor.apply(editor.preview_remove("hero_cues"))
        self.assertEqual(editor.timelines(), [])
        session.undo()
        self.assertEqual(editor.timelines(), [timeline()])

    def test_gameproject_rejects_dangling_and_unsupported_extension(self):
        session = authored()
        AnimationControllerAuthoring(session).apply(
            AnimationControllerAuthoring(session).preview(graph()))
        editor = AnimationTimelineAuthoring(session)
        editor.apply(editor.preview(timeline()))
        contents, _ = reference_project()
        project = session.snapshot().to_dict()["project"]
        self.assertEqual(timelines_from_project(project), [timeline()])
        GameProject.from_dict(project, contents)
        bad = deepcopy(project)
        bad["extensions"][NAMESPACE]["data"]["timelines"][0]["tracks"][0][
            "markers"][0]["cue"] = "grant_hp"
        with self.assertRaises(AnimationGraphError):
            GameProject.from_dict(bad, contents)
        bad = deepcopy(project)
        bad["extensions"][NAMESPACE]["data"]["timelines"][0]["controller_id"] = "deleted"
        with self.assertRaises(AnimationGraphError):
            GameProject.from_dict(bad, contents)


if __name__ == "__main__":
    unittest.main()
