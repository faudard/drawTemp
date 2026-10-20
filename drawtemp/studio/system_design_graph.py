"""R55.B typed graph-link edits; no Qt, scripts, or parallel project schema.

A connector is a directed resource -> consumer or producer -> resource
edge. All edits are detached, checked by the canonical SystemEconomy schema
(including graph cycles), and must be committed through AuthoringSession.
"""
from __future__ import annotations

from copy import deepcopy
from sporebound.model import RuleError
from sporebound.system_design import validate_systems

CATEGORIES = ("resources", "producers", "merchants", "quests")


def _node(document, address):
    if (not isinstance(address, tuple) or len(address) != 2
            or address[0] not in CATEGORIES or type(address[1]) is not str):
        raise RuleError("R55 graph node address must be (category, id)")
    category, name = address
    return next((row for row in document[category] if row["id"] == name), None)


def edit_link(document, source, target, *, quantity=1, scenes=(), remove=False):
    """Return a validated *copy* with one typed port link changed.

    Resource->producer: input; producer->resource: output;
    resource->merchant/quest: single resource binding.
    Removing the final required recipe port fails schema validation.
    """
    if type(quantity) is not int or not 1 <= quantity <= 1000:
        raise RuleError("R55 connection quantity must be 1..1000")
    candidate = deepcopy(document)
    start = _node(candidate, source)
    end = _node(candidate, target)
    if start is None or end is None:
        raise RuleError("R55 graph connection refers to an unknown node")
    a, b = source[0], target[0]
    if a == "resources" and b == "producers":
        key, resource, producer = "inputs", source[1], end
    elif a == "producers" and b == "resources":
        key, resource, producer = "outputs", target[1], start
    elif a == "resources" and b in ("merchants", "quests"):
        if remove:
            raise RuleError("A merchant/quest must be bound to one resource")
        end["resource"] = source[1]
        validate_systems(candidate, scenes)
        return candidate
    else:
        raise RuleError("Incompatible R55 graph port types")
    if remove:
        if resource not in producer[key]:
            raise RuleError("R55 graph link does not exist")
        del producer[key][resource]
    else:
        producer[key][resource] = quantity
    validate_systems(candidate, scenes)
    return candidate


def links(document):
    """Stable directed graph edges for Qt and headless audit tools."""
    result = []
    for producer in sorted(document["producers"], key=lambda row: row["id"]):
        for resource, amount in sorted(producer["inputs"].items()):
            result.append((("resources", resource), ("producers", producer["id"]), amount))
        for resource, amount in sorted(producer["outputs"].items()):
            result.append((("producers", producer["id"]), ("resources", resource), amount))
    for category in ("merchants", "quests"):
        for consumer in sorted(document[category], key=lambda row: row["id"]):
            result.append((("resources", consumer["resource"]),
                           (category, consumer["id"]), None))
    return tuple(result)
