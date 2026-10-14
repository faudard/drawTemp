"""Reversible Tk Studio dock visibility and map focus.

This module owns only existing Panedwindow geometry. It never re-parents
widgets, rebuilds an editor, or mutates gameplay documents.
"""
from __future__ import annotations


DOCKS = ("explorer", "inspector", "bottom")


class StudioDocks:
    """Manage three optional panes while keeping the map canvas mounted."""

    def __init__(self, root, work, canvas_region, explorer, inspector, bottom, tk):
        self.root = root
        self.tk = tk
        self.work = work
        self.canvas_region = canvas_region
        self.panes = {
            "explorer": (work, explorer, 0, 1),
            "inspector": (work, inspector, -1, 2),
            "bottom": (canvas_region, bottom, -1, 1),
        }
        self.visible_vars = {
            name: tk.BooleanVar(value=True) for name in DOCKS
        }
        self.focus_var = tk.BooleanVar(value=False)
        self._before_focus = None
        self._last_size = {}
        self._change = lambda: None

    def on_change(self, callback):
        self._change = callback

    def visible(self, name):
        parent, child, _, _ = self.panes[name]
        return str(child) in parent.panes()

    def set_visible(self, name, show):
        if name not in self.panes:
            raise ValueError("Unknown Studio dock: " + str(name))
        parent, child, index, weight = self.panes[name]
        show = bool(show)
        if self.visible(name) != show:
            if show:
                if index == 0:
                    parent.insert(0, child, weight=weight)
                else:
                    parent.add(child, weight=weight)
                self.root.after_idle(
                    lambda dock=name: self._restore_size(dock))
            else:
                self._last_size[name] = (
                    child.winfo_width() if name != "bottom"
                    else child.winfo_height())
                parent.forget(child)
        self.visible_vars[name].set(show)
        self._change()

    def _restore_size(self, name):
        if not self.visible(name):
            return
        parent, _, _, _ = self.panes[name]
        size = self._last_size.get(name, {
            "explorer": 230, "inspector": 315, "bottom": 155,
        }[name])
        try:
            if name == "explorer":
                width = parent.winfo_width()
                if len(parent.panes()) > 1 and width > 440:
                    parent.sashpos(0, max(170, min(size, width - 250)))
            elif name == "inspector":
                width = parent.winfo_width()
                if len(parent.panes()) > 1 and width > 440:
                    parent.sashpos(
                        len(parent.panes()) - 2,
                        max(200, min(width - size, width - 170)))
            elif len(parent.panes()) > 1:
                height = parent.winfo_height()
                if height > 260:
                    parent.sashpos(0, max(140, min(height - size, height - 100)))
        except self.tk.TclError:
            # Geometry restoration is best-effort, never block map editing.
            pass

    def toggle(self, name):
        if self.focus_var.get():
            self.set_focus(False)
        self.set_visible(name, not self.visible(name))

    def set_focus(self, enabled):
        """F11: keep only viewport, restore each pane exactly on exit."""
        enabled = bool(enabled)
        if enabled == self.focus_var.get():
            return
        if enabled:
            self._before_focus = {
                name: self.visible(name) for name in DOCKS
            }
            for name in DOCKS:
                self.set_visible(name, False)
        else:
            restore = self._before_focus or {name: True for name in DOCKS}
            for name in DOCKS:
                self.set_visible(name, restore[name])
            self._before_focus = None
        self.focus_var.set(enabled)
        self._change()

    def toggle_focus(self):
        self.set_focus(not self.focus_var.get())

    def persistence(self):
        # Focus is transient: never accidentally persist a fully blank shell.
        if self.focus_var.get() and self._before_focus is not None:
            return dict(self._before_focus)
        return {name: self.visible(name) for name in DOCKS}

    def restore(self, prefs):
        for name in DOCKS:
            if name in prefs and type(prefs[name]) is bool:
                self.set_visible(name, prefs[name])


class DockPreferences:
    """Atomic, UI-only sidecar for dock visibility, independent from Content."""

    def __init__(self, path):
        from pathlib import Path
        self.path = Path(path)

    def load(self):
        import json
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return {
            key: raw[key] for key in DOCKS
            if key in raw and type(raw[key]) is bool
        }

    def save(self, state):
        import json
        clean = {
            key: state[key] for key in DOCKS
            if key in state and type(state[key]) is bool
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(clean, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)
