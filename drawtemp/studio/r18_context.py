"""R18.B contextual Studio command policy, without a GUI dependency.

This guards *execution* as well as menu enablement. The map viewport is
shared by painting and building authoring; a disabled button alone is not
sufficient to protect keyboard commands or queued renderer signals.
"""
from __future__ import annotations

MAP_OPERATIONS = frozenset({
    "map.create", "map.duplicate", "map.rename", "map.copy", "map.paste",
    "map.stroke", "map.transform", "map.apply_transform", "map.objective",
})
CONSTRUCTION_OPERATIONS = frozenset({
    "construction.select", "construction.edit", "construction.history",
    "construction.level", "construction.view",
})


class ContextCommandError(ValueError):
    """An operation was invoked outside its authoring mode."""


def require_context(mode, operation):
    if operation in MAP_OPERATIONS:
        required = "map"
    elif operation in CONSTRUCTION_OPERATIONS:
        required = "construction"
    else:
        raise ContextCommandError("Commande contextuelle inconnue : " + str(operation))
    if mode != required:
        raise ContextCommandError(
            "Commande " + operation + " indisponible en mode " + str(mode))
    return True
