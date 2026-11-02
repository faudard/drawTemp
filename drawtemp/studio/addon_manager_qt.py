"""Host-owned Qt Add-on Manager; manifest data never builds arbitrary widgets."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from drawtemp.addons import AddonError


class AddonManagerDialog(QDialog):
    """Opt-in session-only permissions and explicit local manifest inventory."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setObjectName("studio-addon-manager")
        self.setWindowTitle("Add-on Manager")
        self.resize(740, 490)
        layout = QVBoxLayout(self)

        heading = QLabel(
            "Local JSON add-ons. Contributions use native Studio UI only; "
            "no third-party Python or QML is executed."
        )
        heading.setWordWrap(True)
        heading.setTextFormat(Qt.PlainText)
        layout.addWidget(heading)

        self.items = QListWidget(self)
        self.items.setObjectName("studio-addon-list")
        self.items.setAccessibleName("Registered add-ons")
        layout.addWidget(self.items)

        self.details = QPlainTextEdit(self)
        self.details.setObjectName("studio-addon-details")
        self.details.setReadOnly(True)
        layout.addWidget(self.details)

        row = QHBoxLayout()
        self.import_button = QPushButton("Import JSON…", self)
        self.enable_button = QPushButton("Enable…", self)
        self.disable_button = QPushButton("Disable", self)
        self.remove_button = QPushButton("Remove", self)
        for button in (self.import_button, self.enable_button,
                       self.disable_button, self.remove_button):
            row.addWidget(button)
        layout.addLayout(row)

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        self.import_button.clicked.connect(self._import)
        self.enable_button.clicked.connect(self._enable)
        self.disable_button.clicked.connect(self._disable)
        self.remove_button.clicked.connect(self._remove)
        self.items.currentRowChanged.connect(self._update_details)
        self.refresh()

    def _selected(self):
        item = self.items.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def refresh(self, preferred=None):
        selected = preferred if preferred is not None else self._selected()
        self.items.blockSignals(True)
        self.items.clear()
        found = -1
        for status in self.owner.addons.statuses():
            state = "Enabled" if status["enabled"] else "Disabled"
            if status["legacy_read_only"]:
                state = "Legacy (read-only)"
            self.items.addItem("{}  •  {}  •  {}".format(
                status["name"], status["format"], state))
            row = self.items.count() - 1
            self.items.item(row).setData(Qt.UserRole, status["id"])
            if status["id"] == selected:
                found = row
        self.items.blockSignals(False)
        if self.items.count():
            self.items.setCurrentRow(max(found, 0))
        self._update_details()

    def _update_details(self, _index=None):
        addon_id = self._selected()
        if addon_id is None:
            self.details.setPlainText("No add-ons registered.")
            for button in (self.enable_button, self.disable_button, self.remove_button):
                button.setEnabled(False)
            return
        state = self.owner.addons.status(addon_id)
        self.enable_button.setEnabled(not state["legacy_read_only"] and not state["enabled"])
        self.disable_button.setEnabled(state["enabled"])
        self.remove_button.setEnabled(True)
        self.details.setPlainText(json.dumps({
            "id": state["id"],
            "version": state["version"],
            "format": state["format"],
            "namespace": state["namespace"],
            "manifest_sha256": state["manifest_sha256"],
            "capabilities": state["capabilities"],
            "requested_permissions": state["required_permissions"],
            "granted_permissions": state["grants"],
            "enabled": state["enabled"],
            "code_executed": False,
        }, indent=2, ensure_ascii=False))

    def _report(self, error):
        QMessageBox.warning(self, "Add-on Manager", str(error))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import a local add-on manifest", "", "JSON files (*.json)")
        if not path:
            return
        try:
            state = self.owner.install_addon_manifest(path)
            self.refresh(state["id"])
        except (AddonError, ValueError, OSError) as exc:
            self._report(exc)

    def _enable(self):
        addon_id = self._selected()
        if not addon_id:
            return
        state = self.owner.addons.status(addon_id)
        permissions = state["required_permissions"]
        prompt = (
            "Enable {} for this Studio session only?\n\n"
            "Requested permissions:\n{}\n\n"
            "No external code will run. No project file will be changed."
        ).format(addon_id, "\n".join("• " + p for p in permissions) or "(none)")
        approved = QMessageBox.question(
            self, "Enable add-on", prompt,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if approved != QMessageBox.Yes:
            return
        try:
            self.owner.enable_addon(addon_id, permissions)
            self.refresh(addon_id)
        except (AddonError, ValueError, OSError) as exc:
            self._report(exc)

    def _disable(self):
        addon_id = self._selected()
        if addon_id is None:
            return
        try:
            self.owner.disable_addon(addon_id)
            self.refresh(addon_id)
        except (AddonError, ValueError) as exc:
            self._report(exc)

    def _remove(self):
        addon_id = self._selected()
        if addon_id is None:
            return
        approved = QMessageBox.question(
            self, "Remove add-on",
            "Remove {} from this session? No project or asset files will be deleted."
            .format(addon_id),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if approved != QMessageBox.Yes:
            return
        try:
            if self.owner.addons.status(addon_id)["enabled"]:
                self.owner.disable_addon(addon_id)
            self.owner.addons.unregister(addon_id)
            self.refresh()
        except (AddonError, ValueError) as exc:
            self._report(exc)
