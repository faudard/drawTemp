"""Renderer-neutral resolved sprite frames for Qt Studio and Qt Player (R4/R3).

This adapter is the sole path from a GameProject v1 asset binding to a file
and atlas rect. QML/Qt Quick may consume it without touching tactical rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sporebound.assets import AssetRegistry

from .atlas import validate_annotations, png_dimensions


@dataclass(frozen=True)
class FrameResource:
    asset_id: str
    filename: Path
    region: tuple[int, int, int, int]
    pivot: tuple[int, int]
    footprint: tuple[int, int]
    revision: tuple[int, int]


class AssetResolver:
    def __init__(self, registry: AssetRegistry, project_root: Path, annotations=None):
        self.registry = registry
        self.root = Path(project_root).resolve()
        self.annotations = validate_annotations(registry, annotations or {
            "version": 1, "sprites": {},
        })

    def entry(self, kind: str, slot: str):
        """Existing typed presentation binding, without changing IDs."""
        return self.registry.binding(kind, slot)

    def frames(self, asset_id):
        source = self.registry.require_reference(asset_id)
        if source["kind"] == "animation":
            return tuple((frame["sprite"], frame["duration_ms"])
                         for frame in source["frames"])
        if source["kind"] in ("sprite", "portrait"):
            return ((asset_id, 0),)
        raise ValueError("Audio is not a visual frame")

    def resolve(self, asset_id: str, *, elapsed_ms: int = 0) -> FrameResource:
        """Pick a presentation frame deterministically from elapsed visual time."""
        if type(elapsed_ms) is not int or elapsed_ms < 0:
            raise ValueError("Invalid animation elapsed time")
        descriptor = self.registry.require_reference(asset_id)
        if descriptor["kind"] == "animation":
            frames = descriptor["frames"]
            total = sum(frame["duration_ms"] for frame in frames)
            position = elapsed_ms % total if descriptor["loop"] else min(elapsed_ms, total - 1)
            for frame in frames:
                if position < frame["duration_ms"]:
                    descriptor = self.registry.require_reference(frame["sprite"], "sprite")
                    break
                position -= frame["duration_ms"]
        if descriptor["kind"] not in ("sprite", "portrait"):
            raise ValueError("Audio cannot be resolved as an image")
        path = self.registry.resolve(descriptor["id"], self.root)
        if "region" in descriptor:
            region = tuple(descriptor["region"])
        else:
            region = (0, 0, *png_dimensions(path.read_bytes()))
        info = self.annotations["sprites"].get(descriptor["id"])
        pivot = tuple(info["pivot"]) if info else (region[2] // 2, region[3])
        footprint = tuple(info["footprint"]) if info else (1, 1)
        stat = path.stat()
        return FrameResource(
            asset_id=descriptor["id"], filename=path,
            region=region, pivot=pivot, footprint=footprint,
            revision=(stat.st_mtime_ns, stat.st_size),
        )
