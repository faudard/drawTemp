"""R54.A: deterministic region traversal, corrupted saves and async cancellation."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest

from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.world_streaming import (
    EXTENSION, WorldCellCache, WorldStreamState, validate_world_streaming)
from tests_standalone.test_r25_scene_router import scene_fixture


def fixture():
    content, project = scene_fixture()
    for scene in ("forest", "pass"):
        project.exploration[scene] = deepcopy(project.exploration["arrival"])
        project.exploration[scene]["title"] = scene
    project.scene_routes["links"].extend([
        {"id": "to_forest", "source": "arrival",
         "destination": "forest", "spawn": [0, 1]},
        {"id": "to_pass", "source": "forest",
         "destination": "pass", "spawn": [0, 1]},
        {"id": "back_forest", "source": "pass",
         "destination": "forest", "spawn": [0, 1]},
        {"id": "back_village", "source": "forest",
         "destination": "arrival", "spawn": [0, 1]},
    ])
    spec = {"version": 1, "start": "village",
            "max_cache_bytes": 1024, "cells": [
                {"id": "village", "region": "plain", "scene": "arrival",
                 "neighbors": ["woods"],
                 "entities": [{"id": "chest", "initial": "closed"}]},
                {"id": "woods", "region": "forest", "scene": "forest",
                 "neighbors": ["village", "pass"], "entities": []},
                {"id": "pass", "region": "mountain", "scene": "pass",
                 "neighbors": ["woods"], "entities": []},
            ]}
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": spec, "references": []}
    project.validate(content)
    return content, project


class WorldStreamingTests(unittest.TestCase):
    def test_multiple_regions_backtrack_save_resume_once_only(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=54)
        self.assertTrue(session.world_stream_event(
            "pickup_1", "chest", "closed", "collected"))
        self.assertFalse(session.world_stream_event(
            "pickup_1", "chest", "closed", "collected"))
        for link in ("to_forest", "to_pass", "back_forest", "back_village"):
            session.route_transition(link)
        self.assertEqual(session.world_stream_state()["history"],
                         ["village", "woods", "pass", "woods", "village"])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            session.save(path)
            loaded = GameSession.load(path, content, project)
        self.assertEqual(session.recording(), loaded.recording())
        self.assertEqual(loaded.world_stream_state()["entities"]["chest"],
                         "collected")
        with self.assertRaises(RuleError):
            loaded.world_stream_event("pickup_2", "chest", "closed", "collected")

    def test_legacy_checkpoint_unchanged_and_forged_world_rejected(self):
        content, project = fixture()
        legacy_content, legacy_project = scene_fixture()
        legacy = GameSession.new(legacy_content, legacy_project, "main")
        self.assertNotIn("world_stream", legacy.recording())
        baseline = GameSession.new(content, project, "main").recording()
        self.assertIn("world_stream", baseline)
        invalid = [
            lambda record: record.pop("world_stream"),
            lambda record: record["world_stream"]["history"].append("pass"),
            lambda record: record["world_stream"]["events"].append({
                "id": "forged", "entity": "missing",
                "before": "closed", "after": "opened"}),
        ]
        for mutate in invalid:
            data = deepcopy(baseline)
            mutate(data)
            data["digest"] = digest({k: v for k, v in data.items()
                                     if k != "digest"})
            with self.subTest(data=data), self.assertRaises(RuleError):
                GameSession.from_recording(data, content, project)
        world = WorldStreamState(project.extensions[EXTENSION]["data"], project)
        with self.assertRaises(RuleError):
            world.restore({"version": 1, "history": ["village", "pass"],
                           "events": []})
        self.assertEqual(world.recording(),
                         {"version": 1, "history": ["village"], "events": []})

    def test_manifest_broken_edges_repeated_ids_and_limits(self):
        content, project = fixture()
        original = project.extensions[EXTENSION]["data"]
        modifications = [
            lambda x: x["cells"][1]["neighbors"].remove("village"),
            lambda x: x["cells"][2].update(scene="arrival"),
            lambda x: x["cells"][0]["entities"].append(
                {"id": "chest", "initial": "closed"}),
            lambda x: x.update(max_cache_bytes=True),
            lambda x: x["cells"][1].update(region="../../tmp"),
        ]
        for mutate in modifications:
            spec = deepcopy(original)
            mutate(spec)
            with self.subTest(spec=spec), self.assertRaises(RuleError):
                validate_world_streaming(spec, project)
        self.assertEqual(GameProject.from_dict(
            project.to_dict(), content).to_dict(), project.to_dict())

    def test_bounded_lru_does_not_alias_loaded_payload(self):
        _, project = fixture()
        spec = project.extensions[EXTENSION]["data"]
        cache = WorldCellCache(
            spec, lambda cell: {"id": cell["id"], "payload": "x" * 650})
        try:
            for cell in ("village", "woods", "pass"):
                token = cache.request(cell)
                self.assertEqual(cache.resolve(token, timeout=5)["id"], cell)
                self.assertLessEqual(cache.stats()["resident_bytes"], 1024)
            self.assertEqual(cache.stats()["loaded"], ["pass"])
            result = cache.get("pass")
            result["payload"] = "changed"
            self.assertNotEqual(cache.get("pass")["payload"], "changed")
        finally:
            cache.close()

    def test_cancel_inflight_and_retry_discards_late_result(self):
        _, project = fixture()
        entered, release = Event(), Event()
        def loader(cell):
            entered.set()
            release.wait(5)
            return {"id": cell["id"]}
        cache = WorldCellCache(project.extensions[EXTENSION]["data"],
                               loader, workers=1)
        try:
            ticket = cache.request("village")
            self.assertTrue(entered.wait(2))
            self.assertTrue(cache.cancel(ticket))
            with self.assertRaises(RuleError):
                cache.resolve(ticket, timeout=0)
            release.set()
            self.assertEqual(cache.stats()["loaded"], [])
            retry = cache.request("village")
            self.assertEqual(cache.resolve(retry, timeout=5)["id"], "village")
        finally:
            release.set()
            cache.close()

    def test_failed_and_oversized_loads_leave_cache_empty(self):
        _, project = fixture()
        for loader in (lambda cell: {"bad": float("nan")},
                       lambda cell: {"blob": "x" * 3000},
                       lambda cell: 1 / 0):
            cache = WorldCellCache(project.extensions[EXTENSION]["data"], loader)
            try:
                with self.assertRaises(RuleError):
                    cache.resolve(cache.request("woods"), timeout=5)
                self.assertEqual(cache.stats()["resident_bytes"], 0)
                self.assertEqual(cache.stats()["pending"], 0)
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()
