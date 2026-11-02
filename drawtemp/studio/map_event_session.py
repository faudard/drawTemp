"""Map-local Events selection and simple authoring over the canonical R9 EventStudio.

This class owns only transient UI context (selected event and focused cell).
The R1 AuthoringSession remains the sole document/history owner; neither
changing modes nor selecting a marker writes project content.
"""
from __future__ import annotations

from drawtemp.studio.events import EventStudio
from sporebound.event_composer import action, condition


class MapEventSession:
    """Bridge the R5 MapStudio mission to the existing R9 event authoring API."""

    def __init__(self, map_studio):
        self.map_studio = map_studio
        self.events_studio = EventStudio(map_studio.authoring)
        self._mission_id = map_studio.mission_id
        self.selected_id = ""
        self.focus_cell = None

    @property
    def mission_id(self):
        if self._mission_id != self.map_studio.mission_id:
            self._mission_id = self.map_studio.mission_id
            self.selected_id = ""
            self.focus_cell = None
        return self._mission_id

    def events(self):
        mid = self.mission_id
        result = self.events_studio.events(mid)
        if self.selected_id and not any(event["id"] == self.selected_id for event in result):
            self.selected_id = ""
        return result

    def markers(self):
        return self.events_studio.map_markers(self.mission_id)

    def select_event(self, event_id):
        if event_id and not any(event["id"] == event_id for event in self.events()):
            raise ValueError("Unknown event: " + event_id)
        self.selected_id = event_id
        self.focus_cell = None
        markers = [marker for marker in self.markers()
                   if marker["event_id"] == event_id]
        markers.sort(key=lambda marker: marker["kind"] != "trigger")
        if markers:
            self.focus_cell = tuple(markers[0]["pos"])
        return self.selected_id

    def select_cell(self, x, y):
        mission = self.map_studio.mission()
        if not (type(x) is int and type(y) is int and
                0 <= x < mission["board"]["width"] and
                0 <= y < mission["board"]["height"]):
            raise ValueError("Cell is outside the current map")
        self.focus_cell = (x, y)
        matches = [marker for marker in self.markers()
                   if tuple(marker["pos"]) == self.focus_cell]
        # Prefer the authored trigger to an effect sprite at the same position.
        matches.sort(key=lambda marker: marker["kind"] != "trigger")
        self.selected_id = matches[0]["event_id"] if matches else ""
        return self.selected_id

    def create_at_focus(self, event_id, message):
        self.events()
        if self.focus_cell is None:
            raise ValueError("Select a map cell before creating an event")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("An event message is required")
        self.events_studio.create(
            self.mission_id, event_id,
            condition("enter", pos=self.focus_cell),
            [action("message", text=message.strip())])
        self.selected_id = event_id
        return event_id

    def replace_first_message(self, message):
        selected = self.selected_id
        if not selected:
            raise ValueError("Select an event before editing it")
        event = self.events_studio.event(self.mission_id, selected)
        if not event["actions"] or event["actions"][0]["kind"] != "message":
            raise ValueError("This event has no editable first message")
        if not message.strip():
            raise ValueError("An event message is required")
        self.events_studio.replace_action(
            self.mission_id, selected, 0, action("message", text=message.strip()))

    def delete_selected(self):
        selected = self.selected_id
        if not selected:
            raise ValueError("Select an event before deleting it")
        self.events_studio.delete(self.mission_id, selected)
        self.selected_id = ""
        return selected
