"""Transactional visual-layer authoring on the one canonical R1 session."""
from __future__ import annotations

from copy import deepcopy

from drawtemp.core import RuleError
from sporebound.visual_layers import (MATERIALS, PLANES, VISUAL_NS,
                                     from_extensions)


class VisualLayerStudio:
    """Per-map graphics are project-owned; no mutable sidecar or second undo."""

    def __init__(self, map_studio):
        self.studio = map_studio

    @property
    def mission_id(self):
        return self.studio.mission_id

    def layers(self):
        return deepcopy(from_extensions(
            self.studio.authoring.snapshot().project)["missions"].get(
                self.mission_id, []))

    def _edit(self, kind, transform):
        mid = self.mission_id

        def apply(content, project):
            result = deepcopy(project)
            catalog = from_extensions(result.get("extensions", {}))
            layers = catalog["missions"].setdefault(mid, [])
            transform(layers, content)
            if any(catalog["missions"].values()):
                result.setdefault("extensions", {})[VISUAL_NS] = {
                    "schema_version": 1, "data": catalog,
                    "references": [{"kind": "mission", "id": mission_id}
                                   for mission_id in sorted(catalog["missions"])
                                   if catalog["missions"][mission_id]],
                }
            else:
                result.get("extensions", {}).pop(VISUAL_NS, None)
            return content, result

        return self.studio.authoring.apply(self.studio.authoring.preview_pair(
            apply, kind="visual-layers." + kind,
            mission_id=mid, views=("renderer", "workspace", "inspector")))

    @staticmethod
    def _find(layers, layer_id):
        for layer in layers:
            if layer["id"] == layer_id:
                return layer
        raise RuleError("Unknown visual layer: " + str(layer_id))

    def create(self, identifier, name, *, plane="below"):
        def transform(layers, _content):
            if any(row["id"] == identifier for row in layers):
                raise RuleError("Visual layer ID already exists")
            layers.append({"id": identifier, "name": name,
                           "visible": True, "locked": False,
                           "opacity": 100, "plane": plane, "cells": []})
        return self._edit("create", transform)

    def remove(self, identifier):
        def transform(layers, _content):
            row = self._find(layers, identifier)
            if row["locked"]:
                raise RuleError("Unlock the visual layer before deleting")
            layers.remove(row)
        return self._edit("remove", transform)

    def reorder(self, identifier, direction):
        if direction not in (-1, 1):
            raise RuleError("Layer direction must be -1 or +1")

        def transform(layers, _content):
            layer = self._find(layers, identifier)
            at = layers.index(layer)
            target = at + direction
            if not 0 <= target < len(layers):
                raise RuleError("Layer is already at the stack boundary")
            layers[at], layers[target] = layers[target], layers[at]
        return self._edit("reorder", transform)

    def configure(self, identifier, *, name=None, visible=None, locked=None,
                  opacity=None, plane=None):
        def transform(layers, _content):
            row = self._find(layers, identifier)
            if name is not None:
                row["name"] = name
            if visible is not None:
                row["visible"] = visible
            if locked is not None:
                row["locked"] = locked
            if opacity is not None:
                row["opacity"] = opacity
            if plane is not None:
                row["plane"] = plane
        return self._edit("configure", transform)

    def paint(self, identifier, cells, *, material="grass", mask=None,
              operation="paint"):
        """Commit a whole stroke, paint alpha mask, or erase in one Undo step.

        The alpha mask has four values [NW, NE, SW, SE], 0=transparent,
        255=opaque. A mask edit never creates missing sprite cells.
        """
        if operation not in ("paint", "mask", "erase"):
            raise RuleError("Unknown visual stroke tool")
        if operation == "paint" and material not in MATERIALS:
            raise RuleError("Unknown visual material")
        mask = [255] * 4 if mask is None else list(mask)
        if len(mask) != 4 or any(type(v) is not int or not 0 <= v <= 255
                                 for v in mask):
            raise RuleError("Mask needs four integer alpha values")
        points = list(dict.fromkeys(tuple(cell) for cell in cells))
        if not points:
            raise RuleError("A visual stroke needs at least one cell")

        def transform(layers, content):
            layer = self._find(layers, identifier)
            if layer["locked"]:
                raise RuleError("Unlock the visual layer before painting")
            mission = next(m for m in content["missions"] if m["id"] == self.mission_id)
            width, height = mission["board"]["width"], mission["board"]["height"]
            if any(len(p) != 2 or any(type(n) is not int for n in p) or
                   not 0 <= p[0] < width or not 0 <= p[1] < height
                   for p in points):
                raise RuleError("Visual stroke is outside this map")
            material_cells = {tuple(cell["pos"]): cell for cell in layer["cells"]}
            for point in points:
                if operation == "erase":
                    material_cells.pop(point, None)
                elif operation == "mask":
                    if point not in material_cells:
                        continue
                    material_cells[point]["mask"] = list(mask)
                elif point not in material_cells:
                    material_cells[point] = {
                        "pos": list(point), "material": material, "mask": list(mask)}
                else:
                    material_cells[point]["material"] = material
            layer["cells"] = [material_cells[p] for p in
                              sorted(material_cells, key=lambda t: (t[1], t[0]))]
        return self._edit(operation, transform)


__all__ = ["VisualLayerStudio"]
