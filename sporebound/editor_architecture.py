"""Editor Architecture 2.0: opt-in orchestration around the existing Document.

Headless, Tk-independent, Content-schema-neutral. Operations are projections of
existing authoring functions; Document.replace remains the single undo and
validation authority. Legacy callers can migrate one action at a time.
"""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable, Optional, Protocol, Tuple

from .model import Content, RuleError, require
from .editor_reliability import IncrementalValidator
from .tactical_rpg3 import authored_rules_for_document

RENDERER = 'renderer'
MINIMAP = 'minimap'
INSPECTOR = 'inspector'
WORKSPACE = 'workspace'
ALL_VIEWS = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)


def _fingerprint(data):
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class EditorChange:
    """A notification scoped to consumers, not a gameplay event."""
    kind: str
    mission_id: str
    views: Tuple[str, ...]
    revision: int
    cells: Tuple[Tuple[int, int], ...] = ()


class ChangeNotifications:
    """Synchronous, per-view observer bus; unsubscribe never affects another view."""
    def __init__(self):
        self._listeners = {name: [] for name in ALL_VIEWS}

    def subscribe(self, view, callback):
        require(view in ALL_VIEWS, 'Unknown editor view: ' + str(view))
        require(callable(callback), 'View listener must be callable')
        listeners = self._listeners[view]
        listeners.append(callback)

        def unsubscribe():
            if callback in listeners:
                listeners.remove(callback)
        return unsubscribe

    def publish(self, change):
        for view in change.views:
            require(view in ALL_VIEWS, 'Unknown editor view: ' + str(view))
        # Snapshot lists to allow listeners to unsubscribe while dispatching.
        for view in dict.fromkeys(change.views):
            for callback in tuple(self._listeners[view]):
                callback(change)


@dataclass(frozen=True)
class SelectionState:
    mission_id: str
    cell: Tuple[int, int] = (0, 0)
    cells: Tuple[Tuple[int, int], ...] = ()


class SelectionController:
    """Pure selection state; the selection never enters serialized Content."""
    def __init__(self, notifications, mission_id='', *, cell=(0, 0)):
        self.notifications = notifications
        self.state = SelectionState(mission_id, tuple(cell))

    def set(self, mission_id, cell, cells=(), *, publish=True):
        require(isinstance(mission_id, str) and bool(mission_id),
                'Selection requires a mission')
        require(len(cell) == 2 and all(type(v) is int for v in cell),
                'Invalid selected cell')
        selected = tuple(sorted(set(tuple(c) for c in cells)))
        updated = SelectionState(mission_id, tuple(cell), selected)
        if updated != self.state:
            self.state = updated
            if publish:
                self.notifications.publish(EditorChange(
                    'selection', mission_id, (RENDERER, INSPECTOR), 0,
                    (tuple(cell),) + selected))
        return self.state


class ToolController:
    """Mirror the existing Tk tool variable without replacing its widgets."""
    def __init__(self, notifications, name='Pinceau'):
        self.notifications, self.name = notifications, name

    def set(self, name, mission_id=''):
        require(isinstance(name, str) and bool(name), 'Unknown tool')
        if name != self.name:
            self.name = name
            self.notifications.publish(EditorChange(
                'tool', mission_id, (INSPECTOR,), 0))
        return self.name


class TypedEditCommand(Protocol):
    @property
    def kind(self) -> str:
        ...

    @property
    def views(self) -> Tuple[str, ...]:
        ...

    def transform(self, data, mission_id):
        ...


@dataclass(frozen=True)
class StructureCommand:
    """Bridge/building authoring uses iso_structures, never a new tile schema."""
    cell: Tuple[int, int]
    anchor: Optional[Tuple[int, int]] = None
    duplicate: bool = False
    name: Optional[str] = None
    quarter_turns: Optional[int] = None
    door_slot: Optional[int] = None
    kind: str = 'structure'
    views: Tuple[str, ...] = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)

    def transform(self, data, mission_id):
        from .iso_structures import edit_structure
        return edit_structure(
            data, mission_id, self.cell, anchor=self.anchor,
            duplicate=self.duplicate, name=self.name,
            quarter_turns=self.quarter_turns, door_slot=self.door_slot)


@dataclass(frozen=True)
class StructureGroupCommand:
    """Atomic group relocation with original footprint and underlays intact."""
    cells: Tuple[Tuple[int, int], ...]
    dx: int
    dy: int
    duplicate: bool = False
    kind: str = 'structure-group'
    views: Tuple[str, ...] = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)

    def transform(self, data, mission_id):
        from .structure_groups import transform_structure_group
        return transform_structure_group(
            data, mission_id, self.cells, self.dx, self.dy,
            duplicate=self.duplicate)


@dataclass(frozen=True)
class EditorGroupMoveCommand:
    """Move a persistent hierarchy with the normal validated edit protocol."""
    group_id: str
    dx: int
    dy: int
    kind: str = 'editor-group'
    views: Tuple[str, ...] = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)

    def transform(self, data, mission_id):
        from .editor_groups import move_editor_group
        return move_editor_group(data, mission_id, self.group_id,
                                 self.dx, self.dy)


@dataclass(frozen=True)
class EditorGroupBatchCommand:
    """Preview/apply multi-selected group translation or deep duplication."""
    group_ids: Tuple[str, ...]
    dx: int
    dy: int
    duplicate: bool = False
    kind: str = 'editor-groups'
    views: Tuple[str, ...] = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)

    def transform(self, data, mission_id):
        from .editor_groups import duplicate_editor_groups, move_editor_groups
        if self.duplicate:
            return duplicate_editor_groups(data, mission_id,
                                           self.group_ids, self.dx, self.dy)
        return move_editor_groups(data, mission_id, self.group_ids,
                                  self.dx, self.dy)


@dataclass(frozen=True)
class GroupPrefabPlaceCommand:
    """Preview/apply a validated portable group prefab on an authored mission."""
    prefab: dict
    anchor: Tuple[int, int]
    kind: str = 'editor-prefab'
    views: Tuple[str, ...] = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)

    def transform(self, data, mission_id):
        from .group_prefabs import place_group_prefab
        return place_group_prefab(data, mission_id, self.prefab, self.anchor)


@dataclass(frozen=True)
class EditorGroupTreeDropCommand:
    """Reorganize a mission hierarchy from Treeview without moving the map."""
    source_group_id: str
    item_kind: str
    member: object = None
    target_group_id: Optional[str] = None
    kind: str = 'editor-group-tree'
    views: Tuple[str, ...] = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)

    def transform(self, data, mission_id):
        from .editor_groups import drop_group_tree_item
        return drop_group_tree_item(
            data, mission_id, self.source_group_id, self.item_kind,
            member=self.member, target_group_id=self.target_group_id)


@dataclass(frozen=True)
class EntityCommand:
    """Move, duplicate, edit or delete an existing unit or interactive object."""
    action: str
    entity_kind: str
    identifier: str
    cell: Optional[Tuple[int, int]] = None
    fields: Tuple[Tuple[str, object], ...] = ()
    kind: str = 'entity'
    views: Tuple[str, ...] = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)

    def transform(self, data, mission_id):
        from .entity_editing import (relocate_entity, duplicate_entity,
                                     edit_entity, remove_entity)
        if self.action == 'move':
            return relocate_entity(data, mission_id, self.entity_kind,
                                   self.identifier, self.cell)
        if self.action == 'duplicate':
            return duplicate_entity(data, mission_id, self.entity_kind,
                                    self.identifier, self.cell)
        if self.action == 'edit':
            return edit_entity(data, mission_id, self.entity_kind,
                               self.identifier, **dict(self.fields))
        if self.action == 'remove':
            return remove_entity(data, mission_id, self.entity_kind,
                                 self.identifier)
        raise RuleError('Unknown entity action: ' + str(self.action))


@dataclass(frozen=True)
class TacticalEventCommand:
    """The event DAG and the engine still read Mission.triggers unchanged."""
    event_id: str
    condition: dict
    kind: str = 'event'
    views: Tuple[str, ...] = (INSPECTOR, WORKSPACE)

    def transform(self, data, mission_id):
        from .event_graph import update_condition
        return update_condition(data, mission_id, self.event_id,
                                deepcopy(self.condition))


@dataclass(frozen=True)
class CommandPreview:
    """Validated and version-pinned edit, not yet applied or historized."""
    command: TypedEditCommand
    mission_id: str
    based_on: str
    candidate: dict


class EditingContext:
    """One path: preview -> Content validation -> Document history -> notify."""
    def __init__(self, document, mission, notifications=None):
        self.document = document
        self.mission = mission
        self.notifications = notifications or ChangeNotifications()
        self.selection = SelectionController(self.notifications)
        self.tools = ToolController(self.notifications)
        self.revision = 0
        self.diagnostics = IncrementalValidator()

    def preview(self, command, *, mission_id=None):
        mid = mission_id or self.mission()
        require(mid in {m['id'] for m in self.document.data['missions']},
                'Unknown mission: ' + str(mid))
        before = _fingerprint(self.document.data)
        candidate = command.transform(deepcopy(self.document.data), mid)
        # Run the exact current authored rules, including opt-in features.
        candidate = Content.from_dict(
            candidate, rules=authored_rules_for_document(candidate)).to_dict()
        require(_fingerprint(self.document.data) == before,
                'A preview must never change its source document')
        return CommandPreview(command, mid, before, candidate)

    def apply(self, preview, *, publish=True):
        require(_fingerprint(self.document.data) == preview.based_on,
                'Editor changed since preview; recompute before applying')
        require(preview.mission_id == self.mission(),
                'Active mission changed since preview')
        # One Document.replace: existing validation, one undo entry.
        self.document.replace(preview.candidate)
        self.revision += 1
        # Invalidate even a still-running report before notifying consumers.
        self.diagnostics.cancel()
        notice = EditorChange(
            preview.command.kind, preview.mission_id,
            tuple(preview.command.views), self.revision)
        if publish:
            self.notifications.publish(notice)
        return notice

    def execute(self, command, *, mission_id=None, publish=True):
        return self.apply(self.preview(command, mission_id=mission_id),
                          publish=publish)

    def validate_incremental(self, project=None, *, on_scan=None):
        """Report canonical/cross-resource issues for the current revision."""
        return self.diagnostics.validate(
            self.document.data, project, on_scan=on_scan)

    def notify(self, change):
        self.notifications.publish(change)
