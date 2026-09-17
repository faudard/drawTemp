class_name SporeSkillCatalog
extends RefCounted

## V1.2 data-driven skill catalog.
## Metadata and composable effect blocks live in .tres files and are executed by BattleController.

const SKILL_DIR := "res://data/skills/"

static func definition(skill_id: String) -> Resource:
	var path := SKILL_DIR + skill_id + ".tres"
	if ResourceLoader.exists(path):
		return load(path)
	return null


static func secondary_for_unit(id: String) -> String:
	var path := "res://data/units/" + id + ".tres"
	if ResourceLoader.exists(path):
		var unit_def := load(path)
		return String(unit_def.secondary_skill)
	return ""


static func display_name(skill_id: String) -> String:
	var data := definition(skill_id)
	return String(data.display_name) if data != null else "Action"


static func focus_cost(skill_id: String) -> int:
	var data := definition(skill_id)
	return int(data.focus_cost) if data != null else 1


static func cooldown_rounds(skill_id: String) -> int:
	var data := definition(skill_id)
	return int(data.cooldown_rounds) if data != null else 2


static func skill_range(skill_id: String) -> int:
	var data := definition(skill_id)
	return int(data.range) if data != null else 1


static func target_mode(skill_id: String) -> String:
	var data := definition(skill_id)
	return String(data.target_mode) if data != null else "enemy"


static func vfx_id(skill_id: String) -> String:
	var data := definition(skill_id)
	return String(data.vfx_id) if data != null else "default_hit"


static func effects(skill_id: String) -> Array:
	var data := definition(skill_id)
	if data == null:
		return []
	return data.effects


static func has_effects(skill_id: String) -> bool:
	return not effects(skill_id).is_empty()


static func cooldown_left(unit: Dictionary, skill_id: String) -> int:
	var cooldowns: Dictionary = unit.get("cooldowns", {})
	return int(cooldowns.get(skill_id, 0))


static func can_use(unit: Dictionary, skill_id: String) -> bool:
	return (
		not skill_id.is_empty()
		and int(unit.get("focus", 0)) >= focus_cost(skill_id)
		and cooldown_left(unit, skill_id) <= 0
		and not bool(unit["has_acted"])
	)


static func spend(unit: Dictionary, skill_id: String) -> void:
	unit["focus"] = max(0, int(unit.get("focus", 0)) - focus_cost(skill_id))
	var cooldowns: Dictionary = unit.get("cooldowns", {})
	cooldowns[skill_id] = cooldown_rounds(skill_id)
	unit["cooldowns"] = cooldowns
	unit["has_acted"] = true


static func tick_round(unit: Dictionary) -> void:
	unit["focus"] = min(int(unit.get("max_focus", 2)), int(unit.get("focus", 0)) + 1 + int(unit.get("focus_regen_bonus", 0)))
	var cooldowns: Dictionary = unit.get("cooldowns", {})
	for key in cooldowns.keys():
		cooldowns[key] = max(0, int(cooldowns[key]) - 1)
	unit["cooldowns"] = cooldowns
