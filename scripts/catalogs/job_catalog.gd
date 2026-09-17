class_name SporeJobCatalog
extends RefCounted

const JOB_DIR := "res://data/jobs/"


static func definition(id: String) -> SporeJobDefinition:
	if id.is_empty():
		return null
	var path: String = JOB_DIR + id + ".tres"
	return (load(path) as SporeJobDefinition) if ResourceLoader.exists(path) else null


static func all_job_ids() -> PackedStringArray:
	var ids: PackedStringArray = PackedStringArray()
	var dir: DirAccess = DirAccess.open(JOB_DIR)
	if dir == null:
		return ids
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			ids.append(file_name.get_basename())
	ids.sort()
	return ids


static func level_for_xp(job_id: String, xp: int) -> int:
	var data: SporeJobDefinition = definition(job_id)
	return int(data.level_from_xp(maxi(0, xp))) if data != null else 1


static func xp_for_next(job_id: String, xp: int) -> int:
	var data: SporeJobDefinition = definition(job_id)
	if data == null:
		return 0
	var level: int = int(data.level_from_xp(maxi(0, xp)))
	if level >= int(data.max_level):
		return 0
	return maxi(0, int(data.xp_for_level(level + 1)) - xp)


static func progression_nodes(job_id: String) -> Array[SporeProgressionNodeDefinition]:
	var data: SporeJobDefinition = definition(job_id)
	return data.progression_nodes if data != null else []


static func progression_node(job_id: String, node_id: String) -> SporeProgressionNodeDefinition:
	var data: SporeJobDefinition = definition(job_id)
	return data.progression_node_by_id(node_id) if data != null else null


static func tree_point_budget(job_id: String, level: int) -> int:
	var data: SporeJobDefinition = definition(job_id)
	if data == null:
		return 0
	return maxi(0, int(data.starting_tree_points) + maxi(0, level - 1) * int(data.tree_points_per_level))


static func tree_points_spent(job_id: String, purchased_nodes: PackedStringArray) -> int:
	var data: SporeJobDefinition = definition(job_id)
	if data == null:
		return 0
	var total: int = 0
	for node_id in purchased_nodes:
		var node: SporeProgressionNodeDefinition = data.progression_node_by_id(String(node_id))
		if node != null and not bool(node.auto_unlock):
			total += maxi(0, int(node.cost))
	return total


static func tree_points_available(job_id: String, level: int, purchased_nodes: PackedStringArray) -> int:
	return maxi(0, tree_point_budget(job_id, level) - tree_points_spent(job_id, purchased_nodes))


static func effective_node_ids(job_id: String, level: int, purchased_nodes: PackedStringArray) -> PackedStringArray:
	var data: SporeJobDefinition = definition(job_id)
	var result: PackedStringArray = PackedStringArray()
	if data == null:
		return result
	for node: SporeProgressionNodeDefinition in data.progression_nodes:
		if node != null and bool(node.auto_unlock) and int(node.required_level) <= level:
			result.append(String(node.id))
	for node_id in purchased_nodes:
		var node: SporeProgressionNodeDefinition = data.progression_node_by_id(String(node_id))
		if node != null and int(node.required_level) <= level and not result.has(String(node.id)):
			result.append(String(node.id))
	return result


static func can_purchase_node(job_id: String, node_id: String, level: int, purchased_nodes: PackedStringArray) -> Dictionary:
	var data: SporeJobDefinition = definition(job_id)
	if data == null:
		return {"ok": false, "reason": "Job introuvable."}
	var node: SporeProgressionNodeDefinition = data.progression_node_by_id(node_id)
	if node == null:
		return {"ok": false, "reason": "Nœud introuvable."}
	if bool(node.auto_unlock):
		return {"ok": false, "reason": "Ce nœud est automatique."}
	if purchased_nodes.has(node_id):
		return {"ok": false, "reason": "Déjà acquis."}
	if level < int(node.required_level):
		return {"ok": false, "reason": "Niveau %d requis." % int(node.required_level)}
	var effective: PackedStringArray = effective_node_ids(job_id, level, purchased_nodes)
	for required_id in node.required_node_ids:
		if not effective.has(String(required_id)):
			var required: SporeProgressionNodeDefinition = data.progression_node_by_id(String(required_id))
			var label: String = String(required.display_name) if required != null else String(required_id)
			return {"ok": false, "reason": "Prérequis : %s." % label}
	var group: String = String(node.exclusive_group)
	if not group.is_empty():
		for other_id in effective:
			var other: SporeProgressionNodeDefinition = data.progression_node_by_id(String(other_id))
			if other != null and String(other.id) != node_id and String(other.exclusive_group) == group:
				return {"ok": false, "reason": "Branche exclusive déjà choisie : %s." % String(other.display_name)}
	var available: int = tree_points_available(job_id, level, purchased_nodes)
	if available < int(node.cost):
		return {"ok": false, "reason": "%d point(s) requis, %d disponible(s)." % [int(node.cost), available]}
	return {"ok": true, "reason": "Disponible."}


static func unlocked_skills(job_id: String, level: int, purchased_nodes: PackedStringArray = PackedStringArray()) -> PackedStringArray:
	var data: SporeJobDefinition = definition(job_id)
	if data == null:
		return PackedStringArray()
	if data.progression_nodes.is_empty():
		return data.unlocked_skills(level)
	var effective: PackedStringArray = effective_node_ids(job_id, level, purchased_nodes)
	var result: PackedStringArray = PackedStringArray()
	for node: SporeProgressionNodeDefinition in data.progression_nodes:
		if node == null or not effective.has(String(node.id)) or String(node.node_type) != "skill":
			continue
		var skill_id: String = String(node.skill_id)
		if not skill_id.is_empty() and not result.has(skill_id):
			result.append(skill_id)
	return result


static func apply_to_unit(unit: Dictionary, job_id: String, level: int, purchased_nodes: PackedStringArray = PackedStringArray()) -> void:
	var data: SporeJobDefinition = definition(job_id)
	if data == null:
		return
	var levels: int = maxi(0, level - 1)
	var hp_delta := int(data.hp_bonus) + int(floor(float(data.hp_growth) * levels))
	unit["hp"] = maxi(1, int(unit.get("hp", 1)) + hp_delta)
	unit["max_hp"] = maxi(1, int(unit.get("max_hp", 1)) + hp_delta)
	var physical_delta: int = int(data.attack_bonus) + int(floor(float(data.attack_growth) * levels))
	unit["attack"] = maxi(0, int(unit.get("attack", 0)) + physical_delta)
	unit["physical_power"] = maxi(0, int(unit.get("physical_power", unit.get("attack", 0) - physical_delta)) + physical_delta)
	unit["magic_power"] = maxi(0, int(unit.get("magic_power", 0)) + int(data.magic_power_bonus) + int(floor(float(data.magic_power_growth) * levels)))
	unit["physical_defense"] = maxi(0, int(unit.get("physical_defense", 0)) + int(data.physical_defense_bonus) + int(floor(float(data.physical_defense_growth) * levels)))
	unit["magic_defense"] = maxi(0, int(unit.get("magic_defense", 0)) + int(data.magic_defense_bonus) + int(floor(float(data.magic_defense_growth) * levels)))
	unit["move"] = maxi(1, int(unit.get("move", 1)) + int(data.movement_bonus) + int(floor(float(data.movement_growth) * levels)))
	var range_delta: int = int(data.range_bonus) + int(floor(float(data.range_growth) * levels))
	unit["range"] = maxi(1, int(unit.get("range", 1)) + range_delta)
	unit["attack_max_range"] = maxi(int(unit.get("attack_min_range", 1)), int(unit.get("attack_max_range", unit["range"] - range_delta)) + range_delta)
	unit["initiative"] = maxi(0, int(unit.get("initiative", 0)) + int(data.initiative_bonus) + int(floor(float(data.initiative_growth) * levels)))
	unit["accuracy"] = int(unit.get("accuracy", 0)) + int(data.accuracy_bonus) + int(floor(float(data.accuracy_growth) * levels))
	unit["evasion"] = int(unit.get("evasion", 0)) + int(data.evasion_bonus) + int(floor(float(data.evasion_growth) * levels))
	unit["max_focus"] = maxi(0, int(unit.get("max_focus", 0)) + int(data.focus_bonus) + int(floor(float(data.focus_growth) * levels)))
	unit["focus"] = int(unit["max_focus"])
	unit["job_id"] = job_id
	unit["job_level"] = level
	var runtime_tree_nodes: Array = []
	for runtime_node_id in effective_node_ids(job_id, level, purchased_nodes):
		runtime_tree_nodes.append(String(runtime_node_id))
	unit["tree_nodes"] = runtime_tree_nodes
	unit["skill_power_skill_id"] = String(data.skill_power_skill_id)
	unit["skill_power_bonus"] = int(data.skill_power_bonus)
	unit["skill_power_bonuses"] = {}
	if not String(data.skill_power_skill_id).is_empty() and int(data.skill_power_bonus) != 0:
		unit["skill_power_bonuses"][String(data.skill_power_skill_id)] = int(data.skill_power_bonus)
	unit["guard_after_skill_id"] = String(data.guard_after_skill_id)
	unit["guard_after_skill_ids"] = []
	if not String(data.guard_after_skill_id).is_empty():
		unit["guard_after_skill_ids"].append(String(data.guard_after_skill_id))
	unit["focus_regen_bonus"] = 0
	unit["resistances"] = unit.get("resistances", {}).duplicate(true)
	for entry in data.resistances:
		if entry != null and not String(entry.damage_type).is_empty():
			unit["resistances"][String(entry.damage_type)] = int(entry.percent)

	var effective: PackedStringArray = effective_node_ids(job_id, level, purchased_nodes)
	for node: SporeProgressionNodeDefinition in data.progression_nodes:
		if node == null or not effective.has(String(node.id)):
			continue
		if String(node.node_type) == "stat":
			_apply_stat_node(unit, node)
		elif String(node.node_type) == "passive":
			_apply_passive_node(unit, node)

	unit["special"] = ""
	unit["secondary"] = ""
	var skills: PackedStringArray = unlocked_skills(job_id, level, purchased_nodes)
	if skills.size() > 0:
		unit["special"] = String(skills[0])
	if skills.size() > 1:
		unit["secondary"] = String(skills[1])
	unit["focus"] = int(unit["max_focus"])


static func _apply_stat_node(unit: Dictionary, node: SporeProgressionNodeDefinition) -> void:
	var value: int = int(node.stat_value)
	match String(node.stat_type):
		"hp":
			unit["hp"] = maxi(1, int(unit.get("hp", 1)) + value)
			unit["max_hp"] = maxi(1, int(unit.get("max_hp", 1)) + value)
		"attack":
			unit["attack"] = maxi(0, int(unit.get("attack", 0)) + value)
			unit["physical_power"] = maxi(0, int(unit.get("physical_power", unit.get("attack", 0) - value)) + value)
		"movement":
			unit["move"] = maxi(1, int(unit.get("move", 1)) + value)
		"range":
			unit["range"] = maxi(1, int(unit.get("range", 1)) + value)
			unit["attack_max_range"] = maxi(int(unit.get("attack_min_range", 1)), int(unit.get("attack_max_range", unit["range"] - value)) + value)
		"initiative":
			unit["initiative"] = maxi(0, int(unit.get("initiative", 0)) + value)
		"accuracy":
			unit["accuracy"] = int(unit.get("accuracy", 0)) + value
		"evasion":
			unit["evasion"] = int(unit.get("evasion", 0)) + value
		"focus":
			unit["max_focus"] = maxi(0, int(unit.get("max_focus", 0)) + value)
			unit["focus"] = int(unit["max_focus"])


static func _apply_passive_node(unit: Dictionary, node: SporeProgressionNodeDefinition) -> void:
	var target: String = String(node.passive_target)
	var value: int = int(node.passive_value)
	match String(node.passive_type):
		"skill_power":
			if target.is_empty():
				return
			var bonuses: Dictionary = unit.get("skill_power_bonuses", {})
			bonuses[target] = int(bonuses.get(target, 0)) + value
			unit["skill_power_bonuses"] = bonuses
			# Legacy mirrors keep older code/content compatible.
			unit["skill_power_skill_id"] = target
			unit["skill_power_bonus"] = int(bonuses[target])
		"resistance":
			if target.is_empty():
				return
			var resistances: Dictionary = unit.get("resistances", {})
			resistances[target] = clampi(int(resistances.get(target, 0)) + value, -100, 100)
			unit["resistances"] = resistances
		"guard_after_skill":
			if target.is_empty():
				return
			var guards: Array = unit.get("guard_after_skill_ids", [])
			if not guards.has(target):
				guards.append(target)
			unit["guard_after_skill_ids"] = guards
			unit["guard_after_skill_id"] = target
		"focus_regen":
			unit["focus_regen_bonus"] = int(unit.get("focus_regen_bonus", 0)) + value


static func allowed_slots(job_id: String) -> PackedStringArray:
	var data: SporeJobDefinition = definition(job_id)
	return data.allowed_slots if data != null else PackedStringArray(["weapon", "armor", "accessory"])


static func is_job_unlocked(candidate_id: String, hero_job_xp: Dictionary) -> bool:
	var candidate := definition(candidate_id)
	if candidate == null:
		return false
	var parent_id: String = String(candidate.unlock_from_job_id)
	if parent_id.is_empty():
		return true
	var parent_xp: int = int(hero_job_xp.get(parent_id, 0))
	return level_for_xp(parent_id, parent_xp) >= int(candidate.unlock_level)
