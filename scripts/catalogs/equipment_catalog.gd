class_name SporeEquipmentCatalog
extends RefCounted

const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")
const EQUIPMENT_DIR := "res://data/equipment/"


static func definition(id: String) -> Resource:
	if id.is_empty() or id == "none":
		return null
	var path := EQUIPMENT_DIR + id + ".tres"
	return load(path) if ResourceLoader.exists(path) else null


static func all_equipment_ids() -> PackedStringArray:
	var ids := PackedStringArray()
	var dir := DirAccess.open(EQUIPMENT_DIR)
	if dir == null:
		return ids
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			ids.append(file_name.get_basename())
	ids.sort()
	return ids


static func ids_for_slot(slot: String) -> PackedStringArray:
	var result := PackedStringArray()
	for id in all_equipment_ids():
		var data := definition(id)
		if data != null and String(data.slot) == slot:
			result.append(id)
	return result


static func display_name(id: String) -> String:
	var data := definition(id)
	return String(data.display_name) if data != null else ("Aucun" if id == "none" else id)


static func description(id: String) -> String:
	var data := definition(id)
	return String(data.short_description()) if data != null else "Pas de bonus"


static func slot(id: String) -> String:
	var data := definition(id)
	return String(data.slot) if data != null else "accessory"


static func apply_to_unit(unit: Dictionary, equipment_id: String) -> void:
	var data := definition(equipment_id)
	if data == null:
		return
	var hp_delta := int(data.hp_bonus)
	unit["hp"] = max(1, int(unit.get("hp", 1)) + hp_delta)
	unit["max_hp"] = max(1, int(unit.get("max_hp", 1)) + hp_delta)
	var physical_base: int = int(unit.get("physical_power", unit.get("attack", 0)))
	unit["attack"] = max(0, int(unit.get("attack", 0)) + int(data.attack_bonus))
	unit["physical_power"] = max(0, physical_base + int(data.attack_bonus))
	unit["magic_power"] = max(0, int(unit.get("magic_power", 0)) + int(data.magic_power_bonus))
	unit["physical_defense"] = max(0, int(unit.get("physical_defense", 0)) + int(data.physical_defense_bonus))
	unit["magic_defense"] = max(0, int(unit.get("magic_defense", 0)) + int(data.magic_defense_bonus))
	unit["move"] = max(1, int(unit.get("move", 1)) + int(data.movement_bonus))
	if int(unit.get("range", 1)) > 1 or int(data.range_bonus) <= 0:
		unit["range"] = max(1, int(unit.get("range", 1)) + int(data.range_bonus))
		unit["attack_max_range"] = maxi(int(unit.get("attack_min_range", 1)), int(unit.get("attack_max_range", unit["range"] - int(data.range_bonus))) + int(data.range_bonus))
	unit["initiative"] = max(0, int(unit.get("initiative", 0)) + int(data.initiative_bonus))
	unit["accuracy"] = int(unit.get("accuracy", 0)) + int(data.accuracy_bonus)
	unit["evasion"] = int(unit.get("evasion", 0)) + int(data.evasion_bonus)
	unit["max_focus"] = max(0, int(unit.get("max_focus", 0)) + int(data.focus_bonus))
	unit["focus"] = int(unit["max_focus"])
	unit["basic_attack_damage_bonus"] = int(unit.get("basic_attack_damage_bonus", 0)) + int(data.basic_attack_damage_bonus)
	unit["basic_attack_accuracy_bonus"] = int(unit.get("basic_attack_accuracy_bonus", 0)) + int(data.basic_attack_accuracy_bonus)
	unit["flat_damage_reduction"] = maxi(0, int(unit.get("flat_damage_reduction", 0)) + int(data.flat_damage_reduction))
	unit["focus_regen_bonus"] = int(unit.get("focus_regen_bonus", 0)) + int(data.focus_regen_bonus)
	unit["end_ct_bonus"] = int(unit.get("end_ct_bonus", 0)) + int(data.end_ct_bonus)
	unit["revive_hp_bonus"] = int(unit.get("revive_hp_bonus", 0)) + int(data.revive_hp_bonus)
	if String(data.weapon_family) != "none":
		unit["weapon_family"] = String(data.weapon_family)
		var default_max: int = maxi(1, int(unit.get("range", 1)))
		unit["attack_min_range"] = maxi(1, int(data.attack_min_range) if int(data.attack_min_range) > 0 else 1)
		unit["attack_max_range"] = maxi(int(unit["attack_min_range"]), int(data.attack_max_range) if int(data.attack_max_range) > 0 else default_max)
		unit["range"] = int(unit["attack_max_range"])
		unit["threat_min_range"] = maxi(1, int(data.threat_min_range) if int(data.threat_min_range) > 0 else 1)
		unit["threat_max_range"] = maxi(int(unit["threat_min_range"]), int(data.threat_max_range) if int(data.threat_max_range) > 0 else 1)
		unit["can_opportunity_attack"] = bool(data.can_opportunity_attack)
		unit["basic_attack_damage_type"] = String(data.basic_attack_damage_type)
	unit["shield_block_chance"] = clampi(int(unit.get("shield_block_chance", 0)) + int(data.shield_block_chance), 0, 100)
	unit["shield_block_reduction"] = maxi(0, int(unit.get("shield_block_reduction", 0)) + int(data.shield_block_reduction))
	unit["resistances"] = unit.get("resistances", {}).duplicate(true)
	for entry in data.resistances:
		if entry != null and not String(entry.damage_type).is_empty():
			var type := String(entry.damage_type)
			unit["resistances"][type] = int(unit["resistances"].get(type, 0)) + int(entry.percent)
	if not String(data.granted_skill_id).is_empty():
		unit["equipment_skill"] = String(data.granted_skill_id)
		if String(unit.get("special", "")).is_empty():
			unit["special"] = String(data.granted_skill_id)
		elif String(unit.get("secondary", "")).is_empty():
			unit["secondary"] = String(data.granted_skill_id)
	if not String(data.start_status_id).is_empty():
		StatusCatalog.apply(unit, String(data.start_status_id))
