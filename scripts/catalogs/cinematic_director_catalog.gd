class_name SporeCinematicDirectorCatalog
extends RefCounted

const DIRECTOR_DIR: String = "res://data/cinematic_directors/"

static var _cache: Dictionary = {}


static func definition(profile_id: String) -> Resource:
	if profile_id.is_empty():
		return null
	if _cache.has(profile_id):
		return _cache[profile_id]
	var path: String = DIRECTOR_DIR + profile_id + ".tres"
	if not ResourceLoader.exists(path):
		return null
	var data: Resource = load(path) as Resource
	if data != null:
		_cache[profile_id] = data
	return data


static func ids() -> Array[String]:
	var result: Array[String] = []
	var directory: DirAccess = DirAccess.open(DIRECTOR_DIR)
	if directory == null:
		return result
	for file_name: String in directory.get_files():
		if not file_name.ends_with(".tres"):
			continue
		var data: Resource = load(DIRECTOR_DIR + file_name) as Resource
		if data == null:
			continue
		var profile_id: String = String(data.get("id"))
		if not profile_id.is_empty():
			result.append(profile_id)
	result.sort()
	return result


static func clear_cache() -> void:
	_cache.clear()
