"""R51.A headless adapter: UI edits use the R1 AuthoringSession transaction.

The visual WYSIWYG editor belongs to R51.B. This adapter never writes a
sidecar file or edits Content, GameSession, Qt/QML, or runtime save state.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.ui_layout_r51 import NAMESPACE, VERSION, validate_ui_catalog


class LayoutAuthoringError(ValueError):
    pass


class LayoutAuthoring:
    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected canonical AuthoringSession")
        self.session = session

    def inspect(self):
        """Detach UI catalog and revision for a future Qt inspector."""
        snap = self.session.snapshot()
        spec = snap.to_dict()["project"].get("extensions", {}).get(NAMESPACE)
        catalog = (spec["data"] if spec is not None
                   else {"version": VERSION, "layouts": {}})
        return {"revision": snap.revision,
                "catalog": validate_ui_catalog(catalog)}

    def _revision(self, expected_revision):
        if expected_revision is not None and expected_revision != self.session.revision:
            raise LayoutAuthoringError("Stale R51 UI editor revision")

    def preview_replace(self, layout_id, layout, *, expected_revision=None):
        """Return a preview; caller explicitly applies it or discards it."""
        self._revision(expected_revision)
        # Validate before preview as well as through canonical GameProject.
        catalog = self.inspect()["catalog"]
        catalog["layouts"][layout_id] = deepcopy(layout)
        validate_ui_catalog(catalog)

        def change(project):
            extensions = project.setdefault("extensions", {})
            envelope = deepcopy(extensions.get(NAMESPACE, {
                "schema_version": VERSION, "data": {"version": VERSION, "layouts": {}},
            }))
            envelope["data"]["layouts"][layout_id] = deepcopy(layout)
            extensions[NAMESPACE] = envelope
            return project

        return self.session.preview_project(change, kind="r51.ui.replace")

    def preview_remove(self, layout_id, *, expected_revision=None):
        self._revision(expected_revision)
        catalog = self.inspect()["catalog"]
        if layout_id not in catalog["layouts"]:
            raise LayoutAuthoringError("Unknown R51 layout")

        def change(project):
            envelope = project["extensions"][NAMESPACE]
            del envelope["data"]["layouts"][layout_id]
            if not envelope["data"]["layouts"]:
                # Removing the last authored screen restores legacy project
                # identity; no empty opt-in extension is persisted.
                del project["extensions"][NAMESPACE]
                if not project["extensions"]:
                    del project["extensions"]
            return project

        return self.session.preview_project(change, kind="r51.ui.remove")

    def apply(self, preview):
        """Preserve R1 stale-revision, validation, undo/redo semantics."""
        return self.session.apply(preview)
