"""R74.A: bounded, offline assisted dungeon proposals over the canonical R34 model.

This is a logical topology/route proof, *not* physical collision, puzzle/quest,
GameSession, GPU or clean-machine certification. Nothing mutates Content or
GameProject until the caller explicitly applies a selected R34 recipe using
the owning AuthoringSession. Bound external prefabs are rejected fail-closed
until a separate rights/provenance verifier is integrated.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.procgen import ProcGenError, ProcGenRecipe
from drawtemp.sdk.procgen_prefabs import (
    demo_library, generate_with_prefabs, validate_library, verify_with_prefabs,
)
from drawtemp.sdk.roguelite_authoring import preview_roguelite_project
from drawtemp.sdk.simulation import thaw
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.roguelite import MAX_RUNS


MAX_VARIANTS = 5
MAX_ATTEMPTS = 48
MAX_ASSISTED_ROOMS = 32
MAX_ASSISTED_BUDGET = 64
GENERATOR = "r74-assisted-dungeon-v1"


class DungeonAssistError(ValueError):
    """Stable failure reason for UI and automation."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _integer(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise DungeonAssistError(
            "invalid_constraints", f"{name} must be an integer in [{lower}, {upper}]"
        )
    return value


def _topology(layout):
    """Ignore seed/digest and prefab cosmetics when comparing actual variants."""
    rooms = tuple(
        (row["id"], row["role"], tuple(row["neighbors"]), tuple(row["keys"]))
        for row in layout["rooms"]
    )
    locks = tuple((row["a"], row["b"], row["key"]) for row in layout["locks"])
    return (rooms, locks)


def _topology_digest(layout):
    return sha256(
        json.dumps(_topology(layout), separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _proposal_digest(suggestion):
    return sha256(json.dumps(
        suggestion.to_dict(), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DungeonSuggestion:
    revision: int
    seed: int
    biome: str
    recipe: dict
    layout: dict
    topology_digest: str
    provenance: dict

    def to_dict(self):
        """Detached report; never expose a mutable handle to editor history."""
        return {
            "schema_version": 1,
            "revision": self.revision,
            "seed": self.seed,
            "biome": self.biome,
            "recipe": deepcopy(self.recipe),
            "layout": deepcopy(self.layout),
            "topology_digest": self.topology_digest,
            "provenance": deepcopy(self.provenance),
            "logical_route_verified": True,
            "physical_route_verified": False,
            "player_export_certified": False,
            "applied": False,
        }


class AssistedDungeonController:
    """Explicit preview -> select/apply or reject, with no parallel content store."""

    def __init__(self, session: AuthoringSession, library=None):
        if not isinstance(session, AuthoringSession):
            raise DungeonAssistError("invalid_session", "Use the active editor session")
        self.session = session
        self.library = deepcopy(demo_library() if library is None else library)
        self._suggestions = ()
        self._signatures = ()

    def invalidate(self):
        self._suggestions = ()
        self._signatures = ()

    def reject(self):
        """Discard all proposals; never change canonical documents/history."""
        self.invalidate()

    def _library_models(self):
        snapshot = self.session.snapshot()
        content = Content.from_dict(thaw(snapshot.content))
        project = GameProject.from_dict(thaw(snapshot.project), content)
        library = validate_library(self.library, content=content, project=project)
        # R74 never guesses the licensing/attribution of externally bound files.
        # A symbolic reference is not itself permission to redistribute it.
        if any("asset_id" in item or "mission_id" in item
               for item in library["prefabs"]):
            raise DungeonAssistError(
                "rights_unverified",
                "Referenced assets/missions need a verified rights manifest; "
                "R74.A currently permits only unbound procedural prefabs",
            )
        return snapshot, content, project, library

    def preview_variants(
        self, *, seed: int, biome: str = "ruins", count: int = 3,
        rooms: int = 8, branches: int = 2, locked_goal: bool = True,
        encounter_budget: int = 2, loot_budget: int = 2,
        meta_reward: int = 1,
    ) -> tuple[DungeonSuggestion, ...]:
        """Return genuinely distinct, solved logical room topologies.

        Never run external generation services, touch files or mutate session.
        If constraints cannot yield count distinct layouts in a bounded search,
        reject the *whole* request rather than returning duplicates/partial data.
        """
        self.invalidate()
        _integer(seed, "seed", 0, (1 << 63) - 1 - MAX_RUNS - MAX_ATTEMPTS)
        _integer(count, "count", 1, MAX_VARIANTS)
        _integer(rooms, "rooms", 3, MAX_ASSISTED_ROOMS)
        _integer(branches, "branches", 0, rooms - 3)
        _integer(encounter_budget, "encounter_budget", 0, MAX_ASSISTED_BUDGET)
        _integer(loot_budget, "loot_budget", 0, MAX_ASSISTED_BUDGET)
        _integer(meta_reward, "meta_reward", 0, 1000)
        if type(locked_goal) is not bool:
            raise DungeonAssistError("invalid_constraints", "locked_goal must be boolean")
        if not isinstance(biome, str) or not biome or len(biome) > 64:
            raise DungeonAssistError("invalid_constraints", "Invalid biome name")

        snapshot, content, project, library = self._library_models()
        results, seen = [], set()
        for step in range(MAX_ATTEMPTS):
            recipe = ProcGenRecipe(
                seed=seed + step, rooms=rooms, branches=branches,
                locked_goal=locked_goal, encounter_budget=encounter_budget,
                loot_budget=loot_budget,
            )
            # Explicitly reject invalid/unsatisfiable recipes (no silent fallback).
            recipe.validate()
            layout = generate_with_prefabs(
                recipe, library, biome=biome, content=content, project=project,
            )
            verify_with_prefabs(
                recipe, library, layout, biome=biome, content=content, project=project,
            )
            # R34's bounded state-space solver certified entry -> goal -> exit.
            if not layout["route"]:
                raise DungeonAssistError("route_unproven", "Logical route could not be proved")
            fingerprint = _topology_digest(layout)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            results.append(DungeonSuggestion(
                revision=snapshot.revision, seed=recipe.seed, biome=biome,
                recipe=recipe.to_dict(), layout=deepcopy(layout),
                topology_digest=fingerprint,
                provenance={
                    "generator": GENERATOR,
                    "algorithm": recipe.algorithm,
                    "recipe_version": recipe.schema_version,
                    "seed": recipe.seed,
                    "library_digest": layout["library_digest"],
                    "layout_digest": layout["digest"],
                    "origin": "local_unbound_templates",
                    "uses_external_assets": False,
                    "rights_status": "no_external_assets",
                    "meta_reward": meta_reward,
                },
            ))
            if len(results) == count:
                self._suggestions = tuple(results)
                self._signatures = tuple(_proposal_digest(item) for item in results)
                return self._suggestions
        raise DungeonAssistError(
            "insufficient_variants",
            f"Only {len(results)} distinct topologies within {MAX_ATTEMPTS} seeds; "
            "change room/branch constraints",
        )

    def prepare_selection(self, suggestion: DungeonSuggestion):
        """Produce an unapplied canonical R34 plan; caller chooses whether to apply."""
        index = next((i for i, row in enumerate(self._suggestions)
                      if row is suggestion), None)
        if index is None:
            raise DungeonAssistError("stale_suggestion", "Preview again before selecting")
        if _proposal_digest(suggestion) != self._signatures[index]:
            raise DungeonAssistError("modified_suggestion", "Proposal was modified")
        if self.session.revision != suggestion.revision:
            self.invalidate()
            raise AuthoringError(
                "stale_revision", "r74-select", "Project changed since assisted preview",
            )
        if _topology_digest(suggestion.layout) != suggestion.topology_digest:
            raise DungeonAssistError("modified_suggestion", "Proposal was modified")
        _, content, project, library = self._library_models()
        recipe = ProcGenRecipe.from_dict(suggestion.recipe)
        verify_with_prefabs(
            recipe, library, suggestion.layout, biome=suggestion.biome,
            content=content, project=project,
        )
        return preview_roguelite_project(
            self.session, recipe, library, biome=suggestion.biome,
            meta_reward=suggestion.provenance["meta_reward"],
        )

    def apply(self, suggestion: DungeonSuggestion):
        """Explicit opt-in: one validated GameProject edit, one Undo step."""
        plan = self.prepare_selection(suggestion)
        transition = self.session.apply(plan)
        self.invalidate()
        return transition
