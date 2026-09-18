class_name SporeCinematicShotCatalog
extends RefCounted

const SHOT_DIR: String = "res://data/cinematic_shots/"

static var _cache: Dictionary = {}


static func definition(shot_id: String) -> Resource:
	if shot_id.is_empty() or shot_id in ["auto", "none"]:
		return null
	if _cache.has(shot_id):
		return _cache[shot_id]
	var path: String = SHOT_DIR + shot_id + ".tres"
	if not ResourceLoader.exists(path):
		return null
	var data: Resource = load(path) as Resource
	if data != null:
		_cache[shot_id] = data
	return data


static func ids() -> Array[String]:
	var result: Array[String] = []
	var directory: DirAccess = DirAccess.open(SHOT_DIR)
	if directory == null:
		return result
	for file_name: String in directory.get_files():
		if not file_name.ends_with(".tres"):
			continue
		if file_name == "dialogue_default_set.tres":
			continue
		var path: String = SHOT_DIR + file_name
		var data: Resource = load(path) as Resource
		if data == null:
			continue
		var shot_id: String = String(data.get("id"))
		if not shot_id.is_empty():
			result.append(shot_id)
	result.sort()
	return result


static func clear_cache() -> void:
	_cache.clear()
