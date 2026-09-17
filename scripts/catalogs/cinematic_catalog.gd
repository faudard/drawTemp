class_name SporeCinematicCatalog
extends RefCounted

const CINEMATIC_DIR := "res://data/cinematics/"

static var _definitions: Dictionary = {}
static var _loaded := false


static func _ensure_loaded() -> void:
	if _loaded:
		return
	_definitions.clear()
	var directory := DirAccess.open(CINEMATIC_DIR)
	if directory != null:
		for filename in directory.get_files():
			if not filename.ends_with(".tres"):
				continue
			var resource := load(CINEMATIC_DIR + filename)
			if resource != null and String(resource.get("id")) != "":
				_definitions[String(resource.id)] = resource
	_loaded = true


static func reload() -> void:
	_loaded = false
	_ensure_loaded()


static func definition(cinematic_id: String) -> Resource:
	_ensure_loaded()
	return _definitions.get(cinematic_id)


static func ids() -> Array[String]:
	_ensure_loaded()
	var result: Array[String] = []
	for key in _definitions.keys():
		result.append(String(key))
	result.sort()
	return result


static func all() -> Array:
	_ensure_loaded()
	var result: Array = []
	for cinematic_id in ids():
		result.append(_definitions[cinematic_id])
	return result
