class_name SporeDialogueSpeakerCatalog
extends RefCounted

const PROFILE_DIR: String = "res://data/dialogue_speakers/"

static var _definitions: Dictionary = {}
static var _loaded: bool = false


static func _ensure_loaded() -> void:
	if _loaded:
		return
	_definitions.clear()
	var directory: DirAccess = DirAccess.open(PROFILE_DIR)
	if directory != null:
		for filename: String in directory.get_files():
			if not filename.ends_with(".tres"):
				continue
			var resource: Resource = load(PROFILE_DIR + filename) as Resource
			if resource == null:
				continue
			var profile_id: String = String(resource.get("id"))
			if not profile_id.is_empty():
				_definitions[profile_id] = resource
	_loaded = true


static func reload() -> void:
	_loaded = false
	_ensure_loaded()


static func definition(profile_id: String) -> Resource:
	_ensure_loaded()
	return _definitions.get(profile_id, null) as Resource


static func ids() -> Array[String]:
	_ensure_loaded()
	var result: Array[String] = []
	for key: Variant in _definitions.keys():
		result.append(String(key))
	result.sort()
	return result


static func resolve(profile_id: String, unit_id: String, speaker: String) -> Resource:
	_ensure_loaded()

	if not profile_id.is_empty():
		var explicit: Resource = definition(profile_id)
		if explicit != null:
			return explicit

	if not unit_id.is_empty():
		var by_unit_id: Resource = definition(unit_id)
		if by_unit_id != null:
			return by_unit_id
		for candidate_var: Variant in _definitions.values():
			var candidate: Resource = candidate_var as Resource
			if candidate != null and String(candidate.get("unit_id")) == unit_id:
				return candidate

	var wanted: String = speaker.strip_edges().to_lower()
	if wanted in ["narrateur", "narrator"]:
		return definition("narrator")

	for candidate_var: Variant in _definitions.values():
		var candidate: Resource = candidate_var as Resource
		if candidate == null:
			continue
		if String(candidate.get("display_name")).strip_edges().to_lower() == wanted:
			return candidate

	return null
