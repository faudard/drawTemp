"""R26.B / R25 bridge: opt-in action encounter in a canonical campaign.

This adapter is temporary until R25 SceneRouter owns action scenes. It relies
on the R25 scene_profile contract; no tactical GameSession save schemas change.
It does not fabricate an unversioned second inventory or grant rewards twice.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from sporebound.action_runtime import ActionRuntime, validate_scene
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError, require
from sporebound.storage import write_json


class ActionEncounter:
    VERSION = 1

    def __init__(self, session, scene):
        require(isinstance(session, GameSession), "Expected canonical GameSession owner")
        authored = validate_scene(scene)
        require(session.mode == "campaign"
                and not session.progress.story_pending
                and not session.tactical_story_pending,
                "Finish tactical combat and pending dialogue before action encounter")
        known = set(session.project.exploration)
        known.update(row["id"] for row in session.project.story.get("scenes", []))
        require(authored["id"] in known, "Action scene needs a canonical authored identity")
        require(callable(getattr(session, "scene_profile", None)),
                "R25 scene profiles must be installed before enabling action encounters")
        profile = session.scene_profile(authored["id"])
        require(profile["movement"] == "FREE_REALTIME"
                and profile["combat"] == "ACTION_REALTIME",
                "Action encounter requires an explicit R25 action scene profile")
        self.session = session
        self.scene = authored
        self.ledger_key = "r26:" + authored["id"]
        require(not session.progress.story_flags.get(self.ledger_key, False),
                "Action encounter was already settled")
        self.base_digest = session.recording()["digest"]
        self.runtime = ActionRuntime(
            authored, initial_inventory=session.progress.inventory)
        self.finished = False

    def _unchanged(self):
        require(self.session.recording()["digest"] == self.base_digest,
                "The canonical campaign changed during the action encounter")

    def step(self, command):
        require(not self.finished, "Action encounter was already committed")
        self._unchanged()
        return self.runtime.step(command)

    def can_complete(self):
        return (self.runtime.hero["alive"] and
                all(row["hp"] == 0 for row in self.runtime.enemies.values()) and
                all(self.runtime.objects[obj["id"]]["opened"]
                    for obj in self.scene["objects"] if obj["kind"] == "door"))

    def commit(self):
        """One atomic campaign progress transaction; a successful save is v1.

        Reject simultaneous modifications and duplicate rewards; never replace
        GameSession while an action episode is unfinished.
        """
        require(not self.finished, "Action encounter already committed")
        self._unchanged()
        require(self.can_complete(), "Defeat enemies and open all doors to finish")
        previous = self.session.progress
        candidate = deepcopy(previous)
        candidate.inventory = deepcopy(self.runtime.inventory)
        candidate.story_flags[self.ledger_key] = True
        try:
            self.session.progress = candidate
            # Verify that canonical v1 recording can represent these changes.
            verified = self.session.recording()
            GameSession.from_recording(
                verified, self.session.content, self.session.project, rules=self.session.rules)
        except Exception:
            self.session.progress = previous
            raise
        self.finished = True
        return verified

    def recording(self):
        require(not self.finished, "Commit first, then use canonical GameSession save")
        self._unchanged()
        body = {
            "version": self.VERSION,
            "kind": "r26_action_encounter_preview",
            "campaign": self.session.recording(),
            "action": self.runtime.recording(),
        }
        return {**body, "digest": digest(body)}

    def save(self, path):
        write_json(path, self.recording())
        return Path(path)

    @classmethod
    def from_recording(cls, data, content, project, scene, *, rules=None):
        require(type(data) is dict and set(data) == {
            "version", "kind", "campaign", "action", "digest"
        } and type(data["version"]) is int and data["version"] == cls.VERSION
                and data["kind"] == "r26_action_encounter_preview",
                "Unsupported compound action checkpoint")
        require(data["digest"] == digest({k: v for k, v in data.items()
                                          if k != "digest"}),
                "Action checkpoint checksum mismatch")
        session = GameSession.from_recording(
            data["campaign"], content, project, rules=rules)
        instance = cls(session, scene)
        action = ActionRuntime.from_recording(data["action"], expected_scene=scene)
        require(action.initial_inventory == session.progress.inventory,
                "Action replay cannot change the original campaign inventory")
        instance.runtime = action
        return instance

    @classmethod
    def load(cls, path, content, project, scene, *, rules=None):
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuleError("Invalid action checkpoint file") from exc
        return cls.from_recording(raw, content, project, scene, rules=rules)


__all__ = ["ActionEncounter"]
