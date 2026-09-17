class_name SporeAICatalog
extends RefCounted

const AI_DIR := "res://data/ai/"

static func definition(id: String) -> Resource:
	var wanted := id.strip_edges()
	if wanted.is_empty():
		wanted = "default"
	var path := AI_DIR + wanted + ".tres"
	if ResourceLoader.exists(path):
		return load(path)
	var fallback := AI_DIR + "default.tres"
	return load(fallback) if ResourceLoader.exists(fallback) else null

static func all_ids() -> PackedStringArray:
	var result := PackedStringArray()
	var dir := DirAccess.open(AI_DIR)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(file_name.get_basename())
	result.sort()
	return result
