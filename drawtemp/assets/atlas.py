"""DrawTemp 5.0 R4: strict, headless PNG atlas authoring over the v1 asset registry.

No new gameplay schema: plans add sprites (atlas regions) and animations to
GameProject.assets, and keep optional visual annotations in a separate sidecar.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import struct
import zlib

from sporebound.assets import AssetRegistry

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 32 * 1024 * 1024
MAX_DIMENSION = 8192
ASSET_ID = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}\Z")
DIRECTIONS = ("south", "east", "north", "west")


def png_dimensions(source: bytes) -> tuple[int, int]:
    """Validate chunk bounds, CRC and basic pixel limits without importing Qt/Pillow.

    This is a container check, not a full pixel decoder: Qt validates decoding.
    """
    if not isinstance(source, bytes) or not 33 <= len(source) <= MAX_PNG_BYTES:
        raise ValueError("PNG size is invalid or exceeds 32 MiB")
    if not source.startswith(PNG_MAGIC):
        raise ValueError("Invalid PNG signature")
    pos, dimensions, seen_data, ended = 8, None, False, False
    while pos + 12 <= len(source):
        length = struct.unpack_from(">I", source, pos)[0]
        end = pos + 12 + length
        if end > len(source):
            raise ValueError("Truncated PNG chunk")
        tag = source[pos + 4:pos + 8]
        payload = source[pos + 8:pos + 8 + length]
        check = struct.unpack_from(">I", source, pos + 8 + length)[0]
        if zlib.crc32(tag + payload) & 0xffffffff != check:
            raise ValueError("PNG chunk CRC mismatch")
        if dimensions is None:
            if tag != b"IHDR" or length != 13:
                raise ValueError("PNG must begin with IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if (not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION
                    or depth != 8 or color not in (2, 3, 4, 6)
                    or compression or filtering or interlace):
                raise ValueError("Unsupported PNG dimensions, depth, color or interlace")
            dimensions = (width, height)
        elif tag == b"IHDR":
            raise ValueError("Duplicate PNG IHDR")
        if tag == b"IDAT":
            seen_data = True
        if tag == b"IEND":
            if length or not seen_data or end != len(source):
                raise ValueError("Invalid or trailing PNG data")
            ended = True
            break
        pos = end
    if not ended:
        raise ValueError("Missing PNG image data or IEND")
    return dimensions


@dataclass(frozen=True)
class DirectionalLayout:
    """Columns encode directions; one or more rows encode each pose's frames."""
    frame_size: tuple[int, int]
    action_rows: dict[str, tuple[int, ...]]
    directions: tuple[str, ...] = DIRECTIONS
    pivot: tuple[int, int] = (0, 0)
    footprint: tuple[int, int] = (1, 1)
    frame_ms: int = 120

    def validate(self, dimensions):
        w, h = self.frame_size
        if (type(w) is not int or type(h) is not int or
                not 1 <= w <= 2048 or not 1 <= h <= 2048):
            raise ValueError("Invalid atlas frame size")
        if (not self.directions or len(set(self.directions)) != len(self.directions)
                or any(direction not in DIRECTIONS for direction in self.directions)):
            raise ValueError("Unknown or repeated direction")
        if (not isinstance(self.action_rows, dict) or not self.action_rows
                or len(self.action_rows) > 24):
            raise ValueError("Atlas needs at least one action")
        used = set()
        for action, rows in self.action_rows.items():
            if (not isinstance(action, str) or not ASSET_ID.fullmatch(action)
                    or not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= 64):
                raise ValueError("Invalid atlas action/frames")
            for row in rows:
                if type(row) is not int or row < 0 or row in used:
                    raise ValueError("Atlas rows must be unique nonnegative integers")
                used.add(row)
        if (dimensions[0] != w * len(self.directions)
                or dimensions[1] != h * (max(used) + 1)):
            raise ValueError("PNG atlas dimensions differ from layout")
        if (len(self.pivot) != 2 or any(type(v) is not int for v in self.pivot)
                or not (0 <= self.pivot[0] <= w and 0 <= self.pivot[1] <= h)):
            raise ValueError("Pivot must be inside a frame")
        if (len(self.footprint) != 2 or any(type(v) is not int or not 1 <= v <= 32
                                             for v in self.footprint)):
            raise ValueError("Footprint must be 1..32 tiles")
        if type(self.frame_ms) is not int or not 1 <= self.frame_ms <= 60000:
            raise ValueError("Frame duration must be 1..60000 ms")


@dataclass(frozen=True)
class AtlasPlan:
    source: Path
    relative_path: str
    manifest: dict
    annotations: dict
    digest: str

    def copy_into(self, project_root: Path) -> Path:
        """Copy exactly the validated source, exclusively; never replace existing art."""
        root = Path(project_root).resolve()
        destination = root / self.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.parent.resolve().is_relative_to(root):
            raise ValueError("Asset destination escapes project directory")
        contents = self.source.read_bytes()
        png_dimensions(contents)
        if sha256(contents).hexdigest() != self.digest:
            raise ValueError("Atlas source changed since plan was created")
        with destination.open("xb") as target:
            try:
                target.write(contents)
                target.flush()
                os.fsync(target.fileno())
            except BaseException:
                target.close()
                destination.unlink(missing_ok=True)
                raise
        return destination


def plan_directional_import(registry: AssetRegistry, source: Path, asset_id: str,
                            layout: DirectionalLayout, *,
                            license_id: str = "UNVERIFIED",
                            binding_prefix: str | None = None) -> AtlasPlan:
    """Build an import plan without changing a project, or touching its files."""
    if not isinstance(asset_id, str) or not ASSET_ID.fullmatch(asset_id):
        raise ValueError("Invalid stable atlas ID")
    if (not isinstance(license_id, str) or not license_id.strip()
            or len(license_id) > 160):
        raise ValueError("License identifier required")
    source = Path(source).resolve(strict=True)
    if source.stat().st_size > MAX_PNG_BYTES:\n        raise ValueError("PNG exceeds 32 MiB")\n    data = source.read_bytes()
    dimensions = png_dimensions(data)
    layout.validate(dimensions)
    relative_path = "assets/imported/" + asset_id + ".png"
    manifest = registry.to_dict()
    annotations = {}
    for direction_index, direction in enumerate(layout.directions):
        for action, rows in sorted(layout.action_rows.items()):
            frames = []
            for index, row in enumerate(rows):
                frame_id = f"{asset_id}.{direction}.{action}.{index}"
                manifest["entries"].append({
                    "id": frame_id, "kind": "sprite", "path": relative_path,
                    "region": [direction_index * layout.frame_size[0],
                               row * layout.frame_size[1], *layout.frame_size],
                })
                annotations[frame_id] = {
                    "pivot": list(layout.pivot), "footprint": list(layout.footprint),
                    "direction": direction, "pose": action,
                    "license": license_id, "source_sha256": sha256(data).hexdigest(),
                }
                frames.append({"sprite": frame_id, "duration_ms": layout.frame_ms})
            animation_id = f"{asset_id}.{direction}.{action}"
            manifest["entries"].append({
                "id": animation_id, "kind": "animation",
                "loop": action in ("idle", "move", "walk", "run"),
                "frames": frames,
            })
    if binding_prefix is not None:
        if not isinstance(binding_prefix, str) or not ASSET_ID.fullmatch(binding_prefix):
            raise ValueError("Invalid binding prefix")
        slots = manifest["bindings"].setdefault("animation", {})
        for direction in layout.directions:
            for action in sorted(layout.action_rows):
                slot = f"{binding_prefix}_{direction}_{action}"
                if slot in slots:
                    raise ValueError(f"Existing animation binding: {slot}")
                slots[slot] = f"{asset_id}.{direction}.{action}"
    # This canonical validation detects ID collisions, bad paths and references.
    AssetRegistry(manifest)
    return AtlasPlan(source, relative_path, manifest, annotations, sha256(data).hexdigest())


def validate_annotations(registry: AssetRegistry, payload: dict) -> dict:
    """Sidecar is derived presentation data only; never a second asset registry."""
    if (not isinstance(payload, dict) or set(payload) != {"version", "sprites"}
            or type(payload["version"]) is not int or payload["version"] != 1
            or not isinstance(payload["sprites"], dict)):
        raise ValueError("Invalid R4 annotations schema")
    for asset_id, annotation in payload["sprites"].items():
        if registry.require_reference(asset_id, "sprite") is None:
            raise ValueError("Unknown sprite")
        if not isinstance(annotation, dict) or set(annotation) != {
                "pivot", "footprint", "direction", "pose", "license", "source_sha256"}:
            raise ValueError("Invalid sprite annotation")
        if (not isinstance(annotation["pivot"], list) or len(annotation["pivot"]) != 2
                or any(type(v) is not int or v < 0 or v > 8192
                       for v in annotation["pivot"])):
            raise ValueError("Invalid pivot")
        if (not isinstance(annotation["footprint"], list)
                or len(annotation["footprint"]) != 2
                or any(type(v) is not int or not 1 <= v <= 32
                       for v in annotation["footprint"])):
            raise ValueError("Invalid footprint")
        if annotation["direction"] not in DIRECTIONS or not isinstance(annotation["pose"], str):
            raise ValueError("Invalid directional pose")
        if (not isinstance(annotation["license"], str) or not annotation["license"].strip()
                or len(annotation["license"]) > 160):
            raise ValueError("Missing license")
        digest = annotation["source_sha256"]
        if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
            raise ValueError("Invalid source digest")
        region = registry.require_reference(asset_id)["region"]
        if annotation["pivot"][0] > region[2] or annotation["pivot"][1] > region[3]:
            raise ValueError("Pivot outside region")
    return deepcopy(payload)


def load_annotations(path: Path, registry: AssetRegistry) -> dict:
    path = Path(path)
    if not path.exists():
        return {"version": 1, "sprites": {}}
    return validate_annotations(registry, json.loads(path.read_text(encoding="utf-8")))


def save_annotations(path: Path, registry: AssetRegistry, payload: dict) -> None:
    """Atomic replacement of presentation-only metadata, not GameProject."""
    clean = validate_annotations(registry, payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(clean, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def license_issues(registry: AssetRegistry, annotations: dict) -> list[dict]:
    """Report unresolved provenance on imported sprites before game export."""
    payload = validate_annotations(registry, annotations)
    return [
        {"asset_id": key, "message": "Art provenance/license not verified"}
        for key, info in sorted(payload["sprites"].items())
        if info["license"].upper() in ("UNVERIFIED", "UNKNOWN", "TODO")
    ]


def plan_strip_import(registry: AssetRegistry, source: Path, asset_id: str, *,
                      frame_size: tuple[int, int], count: int,
                      pivot: tuple[int, int] = (0, 0),
                      frame_ms: int = 125,
                      license_id: str = "UNVERIFIED") -> AtlasPlan:
    """Import a horizontal environment strip as regions + one looping animation."""
    if not isinstance(asset_id, str) or not ASSET_ID.fullmatch(asset_id):
        raise ValueError("Invalid stable asset ID")
    if type(count) is not int or not 1 <= count <= 128:
        raise ValueError("Invalid strip frame count")
    if (not isinstance(license_id, str) or not license_id.strip()
            or len(license_id) > 160):
        raise ValueError("License identifier required")
    w, h = frame_size
    if (type(w) is not int or type(h) is not int or
            not 1 <= w <= 2048 or not 1 <= h <= 2048):
        raise ValueError("Invalid frame size")
    if (not isinstance(pivot, (tuple, list)) or len(pivot) != 2
            or any(type(v) is not int for v in pivot)
            or not (0 <= pivot[0] <= w and 0 <= pivot[1] <= h)):
        raise ValueError("Invalid strip pivot")
    if type(frame_ms) is not int or not 1 <= frame_ms <= 60000:
        raise ValueError("Invalid frame duration")
    source = Path(source).resolve(strict=True)
    if source.stat().st_size > MAX_PNG_BYTES:
        raise ValueError("PNG exceeds 32 MiB")
    data = source.read_bytes()
    if png_dimensions(data) != (w * count, h):
        raise ValueError("PNG dimensions differ from horizontal strip layout")
    digest = sha256(data).hexdigest()
    relative_path = "assets/imported/" + asset_id + ".png"
    manifest = registry.to_dict()
    annotations = {}
    frames = []
    for index in range(count):
        frame_id = f"{asset_id}.{index}"
        manifest["entries"].append({
            "id": frame_id, "kind": "sprite", "path": relative_path,
            "region": [index * w, 0, w, h],
        })
        annotations[frame_id] = {
            "pivot": list(pivot), "footprint": [1, 1],
            "direction": "south", "pose": "ambient",
            "license": license_id, "source_sha256": digest,
        }
        frames.append({"sprite": frame_id, "duration_ms": frame_ms})
    manifest["entries"].append({
        "id": asset_id, "kind": "animation", "loop": True, "frames": frames,
    })
    AssetRegistry(manifest)
    return AtlasPlan(source, relative_path, manifest, annotations, digest)
