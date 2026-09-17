class_name SporeSaveManager
extends RefCounted

## Single persistence boundary for the campaign. V1.3 keeps the V0.9 path for seamless migration.

const SAVE_PATH := "user://sporebound_tactics_v09_save.json"
const SAVE_VERSION := 5


static func save_campaign(state) -> bool:
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(state.to_save_dict(SAVE_VERSION), "\t"))
	return true


static func load_campaign(state) -> bool:
	if not FileAccess.file_exists(SAVE_PATH):
		return false
	var file := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if file == null:
		return false
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return false
	state.apply_save_dict(parsed)
	return true
