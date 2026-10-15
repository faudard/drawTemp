"""R4.B — single headless sprite/animation binding for the R3 Qt renderer.

The GameProject v1 AssetRegistry remains canonical. The visual clock is wholly
independent of Tactical Core CT, RNG, saves and replays. Studio and Player call
the *same* decorator with the *same* project path.
"""
from __future__ import annotations

from pathlib import Path

from sporebound.assets import AssetRegistry
from sporebound.model import RuleError

from .atlas import load_annotations
from .resolver import AssetResolver


class PresentationAssets:
    """Resolve the canonical v1 animation slot into an atlas rectangle.

    Naming contract for imported directional animations:
    animation slot = `<actor_id>_<direction>_<pose>`.
    An explicit `sprite` slot equal to actor ID remains a static fallback.
    Unbound actors use their existing Qt placeholder, not guessed artwork.
    """

    def __init__(self, registry: AssetRegistry, root: Path, annotations=None):
        self.registry = registry
        self.root = Path(root).resolve()
        self.resolver = AssetResolver(registry, self.root, annotations)
        data = registry.to_dict()
        self._animations = dict(data["bindings"].get("animation", {}))
        self._sprites = dict(data["bindings"].get("sprite", {}))
        self.has_animations = any(
            len(registry.require_reference(asset_id, "animation")["frames"]) > 1
            for asset_id in self._animations.values()
        )

    @classmethod
    def for_project(cls, project, project_path):
        """Resolve against the *manifest directory*, never the process cwd."""
        path = Path(project_path)
        registry = project.asset_registry()
        annotations = load_annotations(path.parent / ".drawtemp" / "r4-annotations.json",
                                       registry)
        return cls(registry, path.parent, annotations)

    def _asset_id(self, actor_id, direction, pose):
        if not isinstance(actor_id, str) or not actor_id:
            return None
        # Exact binding first. Only idle/south fallback for a missing optional
        # cosmetic pose; no reinterpretation of tactical state.
        # Imported R4 strips use actor_direction_pose. The packaged Jeanne
        # campaign predates R4 and uses actor_pose_direction. Both are
        # authoritative bindings in the unchanged GameProject asset registry.
        for slot in (f"{actor_id}_{direction}_{pose}",
                     f"{actor_id}_{pose}_{direction}",
                     f"{actor_id}_{direction}_idle",
                     f"{actor_id}_idle_{direction}",
                     f"{actor_id}_south_idle",
                     f"{actor_id}_idle_south"):
            if slot in self._animations:
                return self._animations[slot]
        return self._sprites.get(actor_id)

    def actor_frame(self, actor_id, *, direction="south", pose="idle", elapsed_ms=0):
        if direction not in ("south", "north", "east", "west"):
            raise ValueError("Unknown facing")
        if not isinstance(pose, str) or not pose:
            raise ValueError("Unknown pose")
        asset_id = self._asset_id(actor_id, direction, pose)
        if asset_id is None:
            return None
        frame = self.resolver.resolve(asset_id, elapsed_ms=elapsed_ms)
        return {
            "imageUrl": frame.filename.as_uri(),
            "assetId": frame.asset_id,
            "atlasX": frame.region[0],
            "atlasY": frame.region[1],
            "frameWidth": frame.region[2],
            "frameHeight": frame.region[3],
            "pivotX": frame.pivot[0],
            "pivotY": frame.pivot[1],
            "footprint": list(frame.footprint),
            "imageRevision": list(frame.revision),
        }

    def decorate(self, render_rows, *, elapsed_ms=0):
        """Detached R3 rows: stable ordering and no mutation of input scenes."""
        if type(elapsed_ms) is not int or elapsed_ms < 0:
            raise ValueError("Invalid presentation time")
        result = []
        for row in render_rows:
            if row["kind"] != "actor":
                result.append(dict(row))
                continue
            actor = dict(row)
            try:
                frame = self.actor_frame(
                    actor["id"], direction=actor.get("direction", "south"),
                    pose=actor.get("pose", "idle"), elapsed_ms=elapsed_ms)
                if frame is not None:
                    actor.update(frame)
            except (OSError, RuntimeError, ValueError, RuleError) as exc:
                # Broken explicit binding is visible in scene diagnostics;
                # an unbound actor has no error and retains the placeholder.
                actor["assetError"] = str(exc)
            result.append(actor)
        return result
