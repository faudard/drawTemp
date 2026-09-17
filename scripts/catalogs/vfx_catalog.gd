class_name SporeVfxCatalog
extends RefCounted

const VFX_DIR := "res://data/vfx/"
static var _cache: Dictionary = {}


static func definition(vfx_id: String) -> Resource:
	if vfx_id.is_empty():
		return null
	if _cache.has(vfx_id):
		return _cache[vfx_id]
	var path := VFX_DIR + vfx_id + ".tres"
	var data = load(path) if ResourceLoader.exists(path) else null
	if data != null:
		_cache[vfx_id] = data
	return data


static func all_vfx_ids() -> PackedStringArray:
	var result := PackedStringArray()
	var dir := DirAccess.open(VFX_DIR)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(file_name.get_basename())
	result.sort()
	return result


static func clear_cache() -> void:
	_cache.clear()
