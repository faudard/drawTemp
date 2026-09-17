class_name SporeMissionCatalog
extends RefCounted

const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")

## Mission metadata stays in .tres Resources.
## Map geometry/deployment can live in a native Godot scene assigned by map_scene_path.
## Native map scenes are preferred; legacy arrays remain as a compatibility fallback.

const MISSION_DIR := "res://data/missions/"


static func mission_paths() -> Array[String]:
	var numbered_by_index: Dictionary = {}
	var extra: Array[String] = []
	var dir: DirAccess = DirAccess.open(MISSION_DIR)
	if dir == null:
		return []
	for file_name: String in dir.get_files():
		if not file_name.ends_with(".tres"):
			continue
		var stem: String = file_name.get_basename()
		var suffix: String = stem.trim_prefix("mission_")
		if stem.begins_with("mission_") and suffix.is_valid_int():
			numbered_by_index[suffix.to_int()] = MISSION_DIR + file_name
		else:
			extra.append(MISSION_DIR + file_name)
	var numbered_keys: Array = numbered_by_index.keys()
	numbered_keys.sort()
	var result: Array[String] = []
	for key: Variant in numbered_keys:
		result.append(String(numbered_by_index[key]))
	extra.sort()
	result.append_array(extra)
	return result


static func count() -> int:
	return mission_paths().size()


static func definition(index: int) -> Resource:
	var paths: Array[String] = mission_paths()
	if index < 0 or index >= paths.size():
		return null
	var path: String = paths[index]
	return load(path) if ResourceLoader.exists(path) else null


static func index_for_path(path: String) -> int:
	return mission_paths().find(path)


static func index_for_id(mission_id: String) -> int:
	var paths: Array[String] = mission_paths()
	for index: int in range(paths.size()):
		var data: Resource = load(paths[index])
		if data != null and String(data.id) == mission_id:
			return index
	return -1


static func meta(index: int) -> Dictionary:
	var data: Resource = definition(index)
	if data == null:
		return {"name": "Mission", "brief": "Mission introuvable."}
	return {
		"name": String(data.display_name),
		"brief": String(data.brief),
	}


static func mission_id(index: int) -> String:
	var data: Resource = definition(index)
	return String(data.id) if data != null else ""


static func secondary_objective_text(index: int) -> String:
	var data: Resource = definition(index)
	return String(data.secondary_objective) if data != null else ""


static func map_scene_path(index: int) -> String:
	var data: Resource = definition(index)
	if data == null:
		return ""
	return String(data.get("map_scene_path"))


static func _map_instance(data: Resource) -> Node:
	if data == null:
		return null
	var path: String = String(data.get("map_scene_path"))
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	var packed: PackedScene = load(path) as PackedScene
	if packed == null:
		return null
	return packed.instantiate()


static func hero_starts(index: int) -> Array:
	var data: Resource = definition(index)
	if data == null:
		return []
	var map_root: Node = _map_instance(data)
	if map_root != null and map_root.has_method("hero_start_cells"):
		var result: Array = map_root.call("hero_start_cells")
		map_root.free()
		return result
	if map_root != null:
		map_root.free()
	return data.hero_starts.duplicate()


static func environment(index: int) -> Dictionary:
	var data: Resource = definition(index)
	if data == null:
		return {
			"objective": "eliminate",
			"survival_rounds": 0,
			"obstacles": [],
			"cover": [],
			"hazards": [],
			"extraction": [],
			"bonus": [],
			"crown": Vector2i(-9, -9),
			"heights": {},
			"grid_width": 10,
			"grid_height": 8,
			"zones": [],
		}
	var result: Dictionary = {
		"objective": String(data.objective),
		"survival_rounds": int(data.survival_rounds),
	}
	var map_root: Node = _map_instance(data)
	if map_root != null and map_root.has_method("to_environment"):
		var map_data: Dictionary = map_root.call("to_environment")
		map_root.free()
		result.merge(map_data, true)
		return result
	if map_root != null:
		map_root.free()
	result.merge({
		"obstacles": data.obstacles.duplicate(),
		"cover": data.cover.duplicate(),
		"hazards": data.hazards.duplicate(),
		"extraction": data.extraction.duplicate(),
		"bonus": data.bonus.duplicate(),
		"crown": data.crown,
		"heights": data.terrain_heights(),
		"grid_width": int(data.grid_width),
		"grid_height": int(data.grid_height),
		"zones": [],
	}, true)
	return result


static func interactables(index: int) -> Array[Resource]:
	var data: Resource = definition(index)
	var result: Array[Resource] = []
	if data == null:
		return result
	var map_root: Node = _map_instance(data)
	if map_root != null and map_root.has_method("interactable_definitions"):
		var from_scene: Array = map_root.call("interactable_definitions")
		for item: Variant in from_scene:
			if item is Resource:
				result.append(item as Resource)
		map_root.free()
		return result
	if map_root != null:
		map_root.free()
	for item: Variant in data.interactables:
		if item is Resource:
			result.append(item as Resource)
	return result


static func enemy_specs(index: int) -> Array:
	var mission: Resource = definition(index)
	var specs: Array = []
	if mission == null:
		return specs
	var map_root: Node = _map_instance(mission)
	if map_root != null and map_root.has_method("enemy_spawn_data"):
		var spawn_data: Array = map_root.call("enemy_spawn_data")
		map_root.free()
		for raw_entry: Variant in spawn_data:
			if not (raw_entry is Dictionary):
				continue
			var entry: Dictionary = raw_entry as Dictionary
			var unit_id: String = String(entry.get("unit_id", ""))
			var unit_def: Resource = UnitCatalog.definition(unit_id)
			if unit_def == null:
				continue
			var role: String = String(entry.get("role", ""))
			if role.is_empty():
				role = String(unit_def.role)
			var hp: int = int(unit_def.max_hp)
			var attack: int = int(unit_def.attack)
			var move_range: int = int(unit_def.movement)
			var attack_range: int = int(unit_def.attack_range)
			if int(entry.get("hp", -1)) >= 0:
				hp = int(entry["hp"])
			if int(entry.get("attack", -1)) >= 0:
				attack = int(entry["attack"])
			if int(entry.get("move", -1)) >= 0:
				move_range = int(entry["move"])
			if int(entry.get("range", -1)) >= 0:
				attack_range = int(entry["range"])
			specs.append({
				"id": unit_id,
				"name": String(unit_def.display_name),
				"role": role,
				"position": entry.get("cell", Vector2i.ZERO),
				"hp": hp,
				"attack": attack,
				"move": move_range,
				"range": attack_range,
				"color": unit_def.color,
				"special": String(unit_def.primary_skill),
			})
		return specs
	if map_root != null:
		map_root.free()

	var count_value: int = mini(mission.enemy_ids.size(), mission.enemy_positions.size())
	for spawn_index: int in range(count_value):
		var unit_id: String = String(mission.enemy_ids[spawn_index])
		var unit_def: Resource = UnitCatalog.definition(unit_id)
		if unit_def == null:
			continue
		var role: String = String(unit_def.role)
		if spawn_index < mission.enemy_roles.size() and not String(mission.enemy_roles[spawn_index]).is_empty():
			role = String(mission.enemy_roles[spawn_index])
		var hp: int = int(unit_def.max_hp)
		var attack: int = int(unit_def.attack)
		var move_range: int = int(unit_def.movement)
		var attack_range: int = int(unit_def.attack_range)
		if spawn_index < mission.enemy_hp_overrides.size() and int(mission.enemy_hp_overrides[spawn_index]) >= 0:
			hp = int(mission.enemy_hp_overrides[spawn_index])
		if spawn_index < mission.enemy_attack_overrides.size() and int(mission.enemy_attack_overrides[spawn_index]) >= 0:
			attack = int(mission.enemy_attack_overrides[spawn_index])
		if spawn_index < mission.enemy_move_overrides.size() and int(mission.enemy_move_overrides[spawn_index]) >= 0:
			move_range = int(mission.enemy_move_overrides[spawn_index])
		if spawn_index < mission.enemy_range_overrides.size() and int(mission.enemy_range_overrides[spawn_index]) >= 0:
			attack_range = int(mission.enemy_range_overrides[spawn_index])
		specs.append({
			"id": unit_id,
			"name": String(unit_def.display_name),
			"role": role,
			"position": mission.enemy_positions[spawn_index],
			"hp": hp,
			"attack": attack,
			"move": move_range,
			"range": attack_range,
			"color": unit_def.color,
			"special": String(unit_def.primary_skill),
		})
	return specs
