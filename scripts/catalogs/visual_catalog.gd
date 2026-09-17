class_name SporeVisualCatalog
extends RefCounted

const VISUAL_DIR := "res://data/visuals/units/"

static var _cache: Dictionary = {}


static func definition(visual_id: String) -> Resource:
	if visual_id.is_empty():
		return null
	if _cache.has(visual_id):
		return _cache[visual_id]
	var path := VISUAL_DIR + visual_id + ".tres"
	var data = load(path) if ResourceLoader.exists(path) else null
	if data != null:
		_cache[visual_id] = data
	return data


static func definition_for_unit(unit: Dictionary) -> Resource:
	var visual_id := String(unit.get("visual_id", ""))
	if visual_id.is_empty():
		visual_id = String(unit.get("template_id", unit.get("id", "")))
	return definition(visual_id)


static func all_visual_ids() -> PackedStringArray:
	var result := PackedStringArray()
	var dir := DirAccess.open(VISUAL_DIR)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(file_name.get_basename())
	result.sort()
	return result


static func clear_cache() -> void:
	_cache.clear()
