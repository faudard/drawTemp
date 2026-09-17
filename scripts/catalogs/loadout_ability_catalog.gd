class_name SporeLoadoutAbilityCatalog
extends RefCounted

const ABILITY_DIR := "res://data/loadout_abilities/"
const JobCatalog = preload("res://scripts/catalogs/job_catalog.gd")


static func definition(id: String) -> SporeLoadoutAbilityDefinition:
	if id.is_empty() or id == "none":
		return null
	var path: String = ABILITY_DIR + id + ".tres"
	return (load(path) as SporeLoadoutAbilityDefinition) if ResourceLoader.exists(path) else null


static func all_ids() -> PackedStringArray:
	var ids := PackedStringArray()
	var dir := DirAccess.open(ABILITY_DIR)
	if dir == null:
		return ids
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			ids.append(file_name.get_basename())
	ids.sort()
	return ids


static func is_unlocked(id: String, job_xp: Dictionary) -> bool:
	var data := definition(id)
	if data == null:
		return false
	if String(data.unlock_job_id).is_empty():
		return true
	var xp: int = int(job_xp.get(String(data.unlock_job_id), 0))
	return JobCatalog.level_for_xp(String(data.unlock_job_id), xp) >= int(data.required_job_level)


static func unlocked_ids_for_slot(slot: String, job_xp: Dictionary) -> PackedStringArray:
	var result := PackedStringArray()
	for id in all_ids():
		var data := definition(id)
		if data != null and String(data.slot) == slot and is_unlocked(id, job_xp):
			result.append(id)
	return result


static func apply_to_unit(unit: Dictionary, id: String, job_xp: Dictionary) -> bool:
	var data := definition(id)
	if data == null or not is_unlocked(id, job_xp):
		return false
	match String(data.slot):
		"reaction":
			unit["reaction_type"] = String(data.reaction_type)
			unit["reaction_range"] = int(data.reaction_range)
			unit["reaction_damage_bonus"] = int(data.reaction_damage_bonus)
		"support":
			unit["hp"] = maxi(1, int(unit.get("hp", 1)) + int(data.hp_bonus))
			unit["max_hp"] = maxi(1, int(unit.get("max_hp", 1)) + int(data.hp_bonus))
			var physical_base: int = int(unit.get("physical_power", unit.get("attack", 0)))
			unit["attack"] = maxi(0, int(unit.get("attack", 0)) + int(data.attack_bonus))
			unit["physical_power"] = maxi(0, physical_base + int(data.attack_bonus))
			unit["initiative"] = maxi(1, int(unit.get("initiative", 1)) + int(data.initiative_bonus))
			unit["accuracy"] = int(unit.get("accuracy", 0)) + int(data.accuracy_bonus)
			unit["evasion"] = int(unit.get("evasion", 0)) + int(data.evasion_bonus)
			unit["max_focus"] = maxi(0, int(unit.get("max_focus", 0)) + int(data.focus_bonus))
			unit["focus_regen_bonus"] = int(unit.get("focus_regen_bonus", 0)) + int(data.focus_regen_bonus)
			unit["end_ct_bonus"] = int(unit.get("end_ct_bonus", 0)) + int(data.end_ct_bonus)
			unit["revive_hp_bonus"] = int(unit.get("revive_hp_bonus", 0)) + int(data.revive_hp_bonus)
		"movement":
			unit["move"] = maxi(1, int(unit.get("move", 1)) + int(data.movement_bonus))
			unit["jump_up_bonus"] = int(unit.get("jump_up_bonus", 0)) + int(data.jump_up_bonus)
			unit["jump_down_bonus"] = int(unit.get("jump_down_bonus", 0)) + int(data.jump_down_bonus)
			unit["ignore_opportunity"] = bool(unit.get("ignore_opportunity", false)) or bool(data.ignore_opportunity)
	unit["loadout_%s" % String(data.slot)] = id
	unit["focus"] = int(unit.get("max_focus", 0))
	return true
