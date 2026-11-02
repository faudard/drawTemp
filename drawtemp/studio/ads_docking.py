"""Optional Qt Advanced Docking System integration for the Qt 6 Studio.

Only QWidget ownership and *UI* state live here. AuthoringSession, Qt Quick
renderers, editing history and gameplay data are never reconstructed.
Native QDockWidget is kept as a working fallback when QtAds is not installed.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QDockWidget

log = logging.getLogger(__name__)
_ADS_CONFIGURED = False


class DockHost:
    """A central viewport with movable, floatable and auto-hide tool panes."""

    def __init__(self, window, central, *, central_name="Editor"):
        self.window = window
        self.ads = None
        self.manager = None
        self.panels = {}
        try:
            import PySide6QtAds as ads
        except (ImportError, OSError) as exc:
            log.info("Qt ADS unavailable; using native Qt docks: %s", exc)
            window.setCentralWidget(central)
            return

        # ADS configuration is process-wide. Set it exactly once, before
        # the first manager (the MapWindow may be nested inside the Studio).
        global _ADS_CONFIGURED
        if not _ADS_CONFIGURED:
            ads.CDockManager.setAutoHideConfigFlags(
                ads.CDockManager.DefaultAutoHideConfig)
            _ADS_CONFIGURED = True
        self.ads = ads
        self.manager = ads.CDockManager(window)
        window.setCentralWidget(self.manager)
        dock = ads.CDockWidget(central_name)
        dock.setObjectName("drawtemp-ads-central")
        dock.setWidget(central)
        self.manager.setCentralWidget(dock)
        self.central_dock = dock

    @property
    def enabled(self):
        return self.manager is not None

    def add(self, title, name, widget, area, *, auto_hide=False):
        if self.manager is None:
            dock = QDockWidget(title, self.window)
            dock.setObjectName(name)
            dock.setFeatures(QDockWidget.DockWidgetMovable |
                             QDockWidget.DockWidgetFloatable |
                             QDockWidget.DockWidgetClosable)
            dock.setWidget(widget)
            self.window.addDockWidget(area, dock)
        else:
            ads = self.ads
            dock = ads.CDockWidget(title)
            dock.setObjectName(name)
            dock.setWidget(widget)
            if auto_hide:
                side = (ads.SideBarLeft if area == Qt.LeftDockWidgetArea
                        else ads.SideBarBottom if area == Qt.BottomDockWidgetArea
                        else ads.SideBarTop if area == Qt.TopDockWidgetArea
                        else ads.SideBarRight)
                self.manager.addAutoHideDockWidget(side, dock)
            else:
                location = {
                    Qt.LeftDockWidgetArea: ads.DockWidgetArea.LeftDockWidgetArea,
                    Qt.RightDockWidgetArea: ads.DockWidgetArea.RightDockWidgetArea,
                    Qt.BottomDockWidgetArea: ads.DockWidgetArea.BottomDockWidgetArea,
                    Qt.TopDockWidgetArea: ads.DockWidgetArea.TopDockWidgetArea,
                }[area]
                self.manager.addDockWidget(location, dock)
        self.panels[name] = dock
        return dock

    def remove(self, dock):
        if self.manager is None:
            self.window.removeDockWidget(dock)
        else:
            self.manager.removeDockWidget(dock)
        self.panels.pop(dock.objectName(), None)

    def save_state(self):
        if self.manager is None:
            return self.window.saveState(1)
        return self.manager.saveState()

    def restore_state(self, state):
        if not isinstance(state, QByteArray) or state.isEmpty():
            return False
        if state.size() > 1024 * 1024:
            log.warning("Ignoring oversized dock layout")
            return False
        if self.manager is None:
            return self.window.restoreState(state, 1)
        return bool(self.manager.restoreState(state))

    def show_preset(self, preset, *, resource=None, inspector=None, problems=None):
        """Keep the editor central and favor collapsed inspector in ADS mode."""
        if self.manager is not None:
            if resource is not None:
                resource.toggleView(True)
            if inspector is not None and preset == "compact":
                inspector.toggleView(False)
            elif inspector is not None:
                inspector.toggleView(True)
            if problems is not None:
                problems.toggleView(preset == "analysis")
            return
        for dock in (resource, inspector, problems):
            if dock is not None:
                dock.setFloating(False)
        if resource is not None:
            resource.show()
        if inspector is not None:
            inspector.setVisible(preset != "compact")
        if problems is not None:
            problems.setVisible(preset == "analysis")
        if resource is not None:
            self.window.addDockWidget(Qt.LeftDockWidgetArea, resource)
        if inspector is not None:
            self.window.addDockWidget(Qt.RightDockWidgetArea, inspector)
        if problems is not None:
            self.window.addDockWidget(Qt.BottomDockWidgetArea, problems)
