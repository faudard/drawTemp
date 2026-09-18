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
	# Legacy serialized name. In the FFT ruleset this value is treated as MP.
	var data := definition(skill_id)
	return int(data.focus_cost) if data != null else 1


static func mp_cost(skill_id: String) -> int:
	return focus_cost(skill_id)


static func cooldown_rounds(_skill_id: String) -> int:
	# Compatibility API only. Cooldowns are deliberately disabled in the FFT loop.
	return 0


static func skill_range(skill_id: String) -> int:
	var data := definition(skill_id)
	return int(data.range) if data != null else 1


static func target_mode(skill_id: String) -> String:
	var data := definition(skill_id)
	return String(data.target_mode) if data != null else "enemy"


static func uses_accuracy(skill_id: String) -> bool:
	var data := definition(skill_id)
	return bool(data.uses_accuracy) if data != null else false


static func accuracy(skill_id: String) -> int:
	var data := definition(skill_id)
	return int(data.accuracy) if data != null else 90


static func cast_time_ticks(skill_id: String) -> int:
	var data := definition(skill_id)
	return int(data.cast_time_ticks) if data != null else 0


static func interrupt_on_damage(skill_id: String) -> bool:
	var data := definition(skill_id)
	return bool(data.interrupt_on_damage) if data != null else false


static func vfx_id(skill_id: String) -> String:
	var data := definition(skill_id)
	return String(data.vfx_id) if data != null else "default_hit"


static func effects(skill_id: String) -> Array:
	var data := definition(skill_id)
	if data == null:
		return []
	return data.effects


static func has_tag(skill_id: String, tag: String) -> bool:
	var data := definition(skill_id)
	return data != null and data.effect_tags.has(tag)


static func has_effects(skill_id: String) -> bool:
	return not effects(skill_id).is_empty()


static func cooldown_left(_unit: Dictionary, _skill_id: String) -> int:
	return 0


static func can_use(unit: Dictionary, skill_id: String) -> bool:
	if skill_id.is_empty() or bool(unit["has_acted"]):
		return false
	if silence_affected(skill_id):
		var statuses: Dictionary = unit.get("statuses", {})
		if statuses.has("silence"):
			return false
	if cast_time_ticks(skill_id) > 0:
		return true
	return int(unit.get("focus", 0)) >= focus_cost(skill_id)


static func spend(unit: Dictionary, skill_id: String) -> void:
	unit["focus"] = max(0, int(unit.get("focus", 0)) - focus_cost(skill_id))
	# One Act per Active Turn is the only per-turn skill gate, like FFT.
	unit["has_acted"] = true
	# Purge stale cooldown state from older saves/runtime dictionaries.
	if unit.has("cooldowns"):
		unit["cooldowns"] = {}


static func tick_round(unit: Dictionary) -> void:
	# FFT MP does not regenerate for free each round. Explicit equipment/passive
	# regeneration remains supported through focus_regen_bonus for Sporebound content.
	var regen: int = maxi(0, int(unit.get("focus_regen_bonus", 0)))
	if regen > 0:
		unit["focus"] = min(int(unit.get("max_focus", 2)), int(unit.get("focus", 0)) + regen)
	if unit.has("cooldowns"):
		unit["cooldowns"] = {}

static func silence_affected(skill_id: String) -> bool:
	var data := definition(skill_id)
	return bool(data.silence_affected) if data != null else false


static func fft_status_modifier(skill_id: String) -> int:
	var data := definition(skill_id)
	return int(data.fft_status_modifier) if data != null else 0
