"""R45.B Qt Widgets Economy Studio: typed shops, recipes and source diagnostics.

This dialog stages authoring data only. Player state, inventories, stock receipts
and NPC clock remain owned by GameSession/LivingWorld; never by widgets.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QTabWidget, QTableWidget, QVBoxLayout, QWidget,
)

from drawtemp.studio.living_economy_authoring import EconomyDraft
from sporebound.living_world import LivingWorld
from sporebound.living_world_diagnostics import timeline
from sporebound.model import RuleError


def _spin(low, high, value=0):
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


def _combo(items):
    widget = QComboBox()
    widget.addItems(list(items))
    return widget


def _select(combo, text):
    if text and combo.findText(text) < 0:
        combo.addItem(text)  # Never silently drop a pre-existing broken ref.
    combo.setCurrentText(text)


class ShopItems(QTableWidget):
    """Typed rows: item identity, player buy/sell prices, daily stock."""

    def __init__(self):
        super().__init__(0, 4)
        self.setHorizontalHeaderLabels(
            ["Objet", "Prix achat", "Prix vente", "Stock / jour"])
        self.setAccessibleName("Catalogue et stock de la boutique")
        self.verticalHeader().setVisible(False)

    def append_item(self, item=None):
        item = item or {}
        index = self.rowCount()
        self.insertRow(index)
        self.setCellWidget(index, 0, QLineEdit(item.get("id", "")))
        for col, low, high, key, default in (
                (1, 0, 1_000_000, "buy_price", 1),
                (2, 0, 1_000_000, "sell_price", 0),
                (3, 1, 1000, "daily_stock", 1)):
            self.setCellWidget(index, col, _spin(
                low, high, item.get(key, default)))
        self.setCurrentCell(index, 0)

    def set_items(self, rows):
        self.setRowCount(0)
        for row in rows:
            self.append_item(row)

    def values(self):
        return [
            {"id": self.cellWidget(i, 0).text().strip(),
             "buy_price": self.cellWidget(i, 1).value(),
             "sell_price": self.cellWidget(i, 2).value(),
             "daily_stock": self.cellWidget(i, 3).value()}
            for i in range(self.rowCount())]


class MaterialItems(QTableWidget):
    """Item IDs are selected from the existing R8/R35 catalogue, not JSON."""

    def __init__(self, label):
        super().__init__(0, 2)
        self.setHorizontalHeaderLabels(["Objet", "Quantité"])
        self.setAccessibleName(label)
        self.verticalHeader().setVisible(False)
        self.catalogue = []

    def set_catalogue(self, ids):
        self.catalogue = list(ids)
        for i in range(self.rowCount()):
            chooser = self.cellWidget(i, 0)
            old = chooser.currentText()
            chooser.blockSignals(True)
            chooser.clear()
            chooser.addItems(self.catalogue)
            _select(chooser, old)
            chooser.blockSignals(False)

    def append_item(self, item=None):
        item = item or {}
        index = self.rowCount()
        self.insertRow(index)
        chooser = _combo(self.catalogue)
        _select(chooser, item.get("item", self.catalogue[0] if self.catalogue else ""))
        self.setCellWidget(index, 0, chooser)
        self.setCellWidget(index, 1, _spin(
            1, 99, item.get("quantity", 1)))
        self.setCurrentCell(index, 0)

    def set_items(self, rows):
        self.setRowCount(0)
        for row in rows:
            self.append_item(row)

    def values(self):
        return [
            {"item": self.cellWidget(i, 0).currentText(),
             "quantity": self.cellWidget(i, 1).value()}
            for i in range(self.rowCount())]


class EconomyHeader(QWidget):
    """Reuse R35 authored schedules, not a second NPC calendar editor."""

    def __init__(self, document, scenes):
        super().__init__()
        self.document = document
        form = QFormLayout(self)
        self.ident = QLineEdit()
        self.ident.setAccessibleName("Identifiant stable de l'activité")
        self.npc = _combo([row["id"] for row in document["npcs"]])
        self.scene = _combo(scenes)
        self.activity = _combo([])
        self.faction = _combo([row["id"] for row in document.get("factions", [])])
        self.reputation = _spin(-100, 100)
        self.npc.currentTextChanged.connect(self._reload_activities)
        form.addRow("ID", self.ident)
        form.addRow("PNJ", self.npc)
        form.addRow("Scène", self.scene)
        form.addRow("Activité de l'agenda R35", self.activity)
        form.addRow("Faction", self.faction)
        form.addRow("Réputation minimale", self.reputation)
        self._reload_activities()

    def _reload_activities(self, *_):
        old = self.activity.currentText()
        npc = next((row for row in self.document["npcs"]
                    if row["id"] == self.npc.currentText()), None)
        activities = sorted({row["activity"] for row in npc["schedule"]}) if npc else []
        self.activity.clear()
        self.activity.addItems(activities)
        if old in activities:
            self.activity.setCurrentText(old)
        if npc and npc["schedule"] and not self.scene.currentText():
            _select(self.scene, npc["schedule"][0]["scene"])

    def load(self, row=None):
        row = row or {}
        self.ident.setText(row.get("id", ""))
        _select(self.npc, row.get("npc", self.npc.currentText()))
        _select(self.scene, row.get("scene", self.scene.currentText()))
        _select(self.activity, row.get("activity", self.activity.currentText()))
        _select(self.faction, row.get("faction", self.faction.currentText()))
        self.reputation.setValue(row.get("min_reputation", 0))

    def value(self):
        return {
            "id": self.ident.text().strip(),
            "npc": self.npc.currentText(),
            "scene": self.scene.currentText(),
            "activity": self.activity.currentText(),
            "faction": self.faction.currentText(),
            "min_reputation": self.reputation.value()}


def _button_row(*buttons):
    holder = QHBoxLayout()
    for title, action in buttons:
        widget = QPushButton(title)
        widget.clicked.connect(action)
        holder.addWidget(widget)
    return holder


class LivingEconomyDialog(QDialog):
    """R45.B visual authoring with explicit preview and a single undo commit."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.draft = EconomyDraft(session)
        self.document = self.draft.document
        self.setWindowTitle("Économie vivante R45 — boutiques et artisanat")
        self.resize(980, 750)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Les horaires PNJ restent dans Monde vivant R35. "
            "Enregistrer une fiche dans le brouillon, puis prévisualiser "
            "et appliquer en une seule transaction Undo/Redo."))
        tabs = QTabWidget()
        layout.addWidget(tabs, 3)

        shops = QWidget()
        shops_layout = QVBoxLayout(shops)
        self.shop_list = QListWidget()
        self.shop_list.setAccessibleName("Boutiques et marchands")
        self.shop_list.currentRowChanged.connect(self._load_shop)
        shops_layout.addWidget(self.shop_list, 1)
        shops_layout.addLayout(_button_row(
            ("Nouvelle boutique", self._new_shop),
            ("Supprimer la boutique", self._delete_shop)))
        self.shop_header = EconomyHeader(self.document, self.draft.scenes)
        shops_layout.addWidget(self.shop_header)
        self.shop_items = ShopItems()
        shops_layout.addWidget(self.shop_items, 2)
        shops_layout.addLayout(_button_row(
            ("Ajouter un article", self.shop_items.append_item),
            ("Retirer l'article sélectionné", lambda: self._remove_row(self.shop_items)),
            ("Conserver la boutique", self._save_shop)))
        tabs.addTab(shops, "Boutiques / stocks")

        recipes = QWidget()
        recipe_layout = QVBoxLayout(recipes)
        self.recipe_list = QListWidget()
        self.recipe_list.setAccessibleName("Recettes d'artisanat")
        self.recipe_list.currentRowChanged.connect(self._load_recipe)
        recipe_layout.addWidget(self.recipe_list, 1)
        recipe_layout.addLayout(_button_row(
            ("Nouvelle recette", self._new_recipe),
            ("Supprimer la recette", self._delete_recipe)))
        self.recipe_header = EconomyHeader(self.document, self.draft.scenes)
        recipe_layout.addWidget(self.recipe_header)
        recipe_cost = QHBoxLayout()
        self.recipe_gold = _spin(0, 1_000_000)
        self.recipe_limit = _spin(1, 1000, 1)
        recipe_cost.addWidget(QLabel("Coût en or / unité"))
        recipe_cost.addWidget(self.recipe_gold)
        recipe_cost.addWidget(QLabel("Fabrications / jour"))
        recipe_cost.addWidget(self.recipe_limit)
        recipe_layout.addLayout(recipe_cost)
        inputs = QHBoxLayout()
        self.recipe_inputs = MaterialItems("Matières consommées")
        self.recipe_outputs = MaterialItems("Objets produits")
        input_col = QVBoxLayout()
        input_col.addWidget(QLabel("Consomme"))
        input_col.addWidget(self.recipe_inputs)
        input_col.addLayout(_button_row(
            ("Ajouter matière", self.recipe_inputs.append_item),
            ("Retirer matière", lambda: self._remove_row(self.recipe_inputs))))
        output_col = QVBoxLayout()
        output_col.addWidget(QLabel("Produit"))
        output_col.addWidget(self.recipe_outputs)
        output_col.addLayout(_button_row(
            ("Ajouter produit", self.recipe_outputs.append_item),
            ("Retirer produit", lambda: self._remove_row(self.recipe_outputs))))
        inputs.addLayout(input_col)
        inputs.addLayout(output_col)
        recipe_layout.addLayout(inputs, 2)
        recipe_layout.addLayout(_button_row(
            ("Conserver la recette", self._save_recipe)))
        tabs.addTab(recipes, "Fabrication")

        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setAccessibleName(
            "Prévisualisation sources des changements et état des commerces")
        self.diagnostics.setMaximumHeight(210)
        layout.addWidget(self.diagnostics, 1)
        layout.addLayout(_button_row(
            ("Prévisualiser les changements", self._preview),
            ("Appliquer au projet", self._apply),
            ("Annuler", self.reject)))
        self._refresh_all()

    @staticmethod
    def _remove_row(table):
        index = table.currentRow()
        if index >= 0:
            table.removeRow(index)

    def _refresh_all(self, shop_id=None, recipe_id=None):
        self.shop_list.blockSignals(True)
        self.shop_list.clear()
        self.shop_list.addItems([row["id"] for row in self.document.get("shops", [])])
        if shop_id is not None:
            found = self.shop_list.findItems(shop_id, 0)
            if found:
                self.shop_list.setCurrentItem(found[0])
        elif self.shop_list.count():
            self.shop_list.setCurrentRow(0)
        self.shop_list.blockSignals(False)
        self._load_shop(self.shop_list.currentRow())

        item_ids = self.draft.item_ids()
        self.recipe_inputs.set_catalogue(item_ids)
        self.recipe_outputs.set_catalogue(item_ids)
        self.recipe_list.blockSignals(True)
        self.recipe_list.clear()
        self.recipe_list.addItems([row["id"] for row in self.document.get("recipes", [])])
        if recipe_id is not None:
            found = self.recipe_list.findItems(recipe_id, 0)
            if found:
                self.recipe_list.setCurrentItem(found[0])
        elif self.recipe_list.count():
            self.recipe_list.setCurrentRow(0)
        self.recipe_list.blockSignals(False)
        self._load_recipe(self.recipe_list.currentRow())

    def _load_shop(self, index):
        entries = self.document.get("shops", [])
        row = entries[index] if 0 <= index < len(entries) else None
        self.shop_header.load(row)
        self.shop_items.set_items(row["items"] if row else [])

    def _load_recipe(self, index):
        entries = self.document.get("recipes", [])
        row = entries[index] if 0 <= index < len(entries) else None
        self.recipe_header.load(row)
        self.recipe_gold.setValue(row["gold_cost"] if row else 0)
        self.recipe_limit.setValue(row["daily_limit"] if row else 1)
        self.recipe_inputs.set_items(row["inputs"] if row else [])
        self.recipe_outputs.set_items(row["outputs"] if row else [])

    def _new_shop(self):
        self.shop_list.setCurrentRow(-1)
        self.shop_header.load()
        self.shop_items.set_items([])
        self.shop_header.ident.setFocus()

    def _new_recipe(self):
        self.recipe_list.setCurrentRow(-1)
        self.recipe_header.load()
        self.recipe_inputs.set_items([])
        self.recipe_outputs.set_items([])
        self.recipe_header.ident.setFocus()

    def _save_shop(self):
        row = {**self.shop_header.value(), "items": self.shop_items.values()}
        index = self.shop_list.currentRow()
        entries = self.document.get("shops", [])
        previous = entries[index]["id"] if 0 <= index < len(entries) else None
        try:
            self.draft.upsert_shop(row, original_id=previous)
        except ValueError as exc:
            QMessageBox.warning(self, "Boutique", str(exc))
            return
        self._refresh_all(shop_id=row["id"])
        self.diagnostics.setPlainText("Boutique conservée en brouillon. Prévisualiser avant d'appliquer.")

    def _save_recipe(self):
        row = {**self.recipe_header.value(),
               "inputs": self.recipe_inputs.values(),
               "outputs": self.recipe_outputs.values(),
               "gold_cost": self.recipe_gold.value(),
               "daily_limit": self.recipe_limit.value()}
        index = self.recipe_list.currentRow()
        entries = self.document.get("recipes", [])
        previous = entries[index]["id"] if 0 <= index < len(entries) else None
        try:
            self.draft.upsert_recipe(row, original_id=previous)
        except ValueError as exc:
            QMessageBox.warning(self, "Artisanat", str(exc))
            return
        self._refresh_all(recipe_id=row["id"])
        self.diagnostics.setPlainText("Recette conservée en brouillon. Prévisualiser avant d'appliquer.")

    def _delete_shop(self):
        item = self.shop_list.currentItem()
        if item is not None:
            self.draft.remove_shop(item.text())
            self._refresh_all()

    def _delete_recipe(self):
        item = self.recipe_list.currentItem()
        if item is not None:
            self.draft.remove_recipe(item.text())
            self._refresh_all()

    def _preview(self):
        try:
            report = self.draft.preview()
            pair = self.draft.session.snapshot().to_dict()
            world = LivingWorld(
                self.document, set(self.draft.scenes),
                exploration=pair["project"].get("exploration", {}),
                item_ids=set(self.draft.equipment_ids))
            state = world.view({})
            schedule = timeline(world, {}, limit=24)
            summary = [
                "Aperçu sans mutation de Campaign, sans tick et avec flags désactivés.",
                f'Révision source : {report.report["source_revision"]}',
                f'PNJ : {len(self.document["npcs"])} | '
                f'Boutiques : {len(self.document.get("shops", []))} | '
                f'Recettes : {len(self.document.get("recipes", []))}',
                "Catalogue R35 :",
            ]
            for shop in state.get("shops", []):
                summary.append(
                    f'  {shop["id"]} — {"ouvert" if shop["open"] else "fermé"} '
                    f'— {len(shop["items"])} références')
            for recipe in state.get("recipes", []):
                summary.append(
                    f'  {recipe["id"]} — quota {recipe["remaining_today"]} '
                    f'— coût {recipe["gold_cost"]}')
            summary.append("Prochains événements de calendrier (projection hors focus) :")
            summary.extend(
                f'  J+{event.get("day", 0)} {event["minute"]//60:02}:'
                f'{event["minute"]%60:02} {event["kind"]} {event["id"]}'
                for event in schedule["entries"][:12])
            self.diagnostics.setPlainText("\n".join(summary))
            return True
        except (RuleError, ValueError, TypeError, KeyError) as exc:
            self.diagnostics.setPlainText("Prévisualisation refusée : " + str(exc))
            return False

    def _apply(self):
        try:
            self.draft.apply()
        except (RuleError, ValueError, TypeError, KeyError) as exc:
            self.diagnostics.setPlainText("Aucune modification appliquée : " + str(exc))
            return
        self.accept()
