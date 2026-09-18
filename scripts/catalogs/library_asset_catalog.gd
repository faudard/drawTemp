@tool
class_name SporeLibraryAssetCatalog
extends RefCounted

const CATALOG_PATH: String = "res://data/library_assets/catalog.json"

static func load_catalog() -> Dictionary:
	if not FileAccess.file_exists(CATALOG_PATH):
		return {}
	var file: FileAccess = FileAccess.open(CATALOG_PATH, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		return parsed as Dictionary
	return {}

static func character_portraits() -> Array:
	var catalog: Dictionary = load_catalog()
	var value: Variant = catalog.get("character_portraits", [])
	if not value is Array:
		return []
	return value as Array

static func portrait_path(asset_id: String) -> String:
	var entries: Array = character_portraits()
	for entry_variant: Variant in entries:
		if not entry_variant is Dictionary:
			continue
		var entry: Dictionary = entry_variant as Dictionary
		if String(entry.get("id", "")) == asset_id:
			return String(entry.get("runtime_path", ""))
	return ""

static func status_icon_path(status_id: String) -> String:
	var catalog: Dictionary = load_catalog()
	var value: Variant = catalog.get("status_icons", [])
	if not value is Array:
		return ""
	var entries: Array = value as Array
	for entry_variant: Variant in entries:
		if not entry_variant is Dictionary:
			continue
		var entry: Dictionary = entry_variant as Dictionary
		if String(entry.get("id", "")) == status_id:
			return String(entry.get("runtime_path", ""))
	return ""


static func character_entry(asset_id: String) -> Dictionary:
	for entry_variant: Variant in character_portraits():
		if entry_variant is Dictionary:
			var entry: Dictionary = entry_variant as Dictionary
			if String(entry.get("id", "")) == asset_id:
				return entry
	return {}


static func character_ids() -> PackedStringArray:
	var result: PackedStringArray = PackedStringArray()
	for entry_variant: Variant in character_portraits():
		if entry_variant is Dictionary:
			var asset_id: String = String((entry_variant as Dictionary).get("id", ""))
			if not asset_id.is_empty():
				result.append(asset_id)
	result.sort()
	return result


static func unit_binding(unit_id: String) -> Dictionary:
	var catalog: Dictionary = load_catalog()
	var value: Variant = catalog.get("unit_bindings", [])
	if not value is Array:
		return {}
	var entries: Array = value as Array
	for entry_variant: Variant in entries:
		if entry_variant is Dictionary:
			var entry: Dictionary = entry_variant as Dictionary
			if String(entry.get("unit_id", "")) == unit_id:
				return entry
	return {}


static func portrait_path_for_unit(unit_id: String) -> String:
	var binding: Dictionary = unit_binding(unit_id)
	if binding.is_empty():
		return ""
	return String(binding.get("runtime_path", ""))
