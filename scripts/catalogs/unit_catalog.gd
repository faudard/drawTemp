class_name SporeUnitCatalog
extends RefCounted

const UnitData = preload("res://scripts/models/unit_data.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const BattleRules = preload("res://scripts/core/battle_rules.gd")
const JobCatalog = preload("res://scripts/catalogs/job_catalog.gd")
const EquipmentCatalog = preload("res://scripts/catalogs/equipment_catalog.gd")

## V1.4 data-driven unit catalog with editable AI profile references.
## Sporebound Studio edits res://data/units/*.tres and the runtime reads those same resources.

const UNIT_DIR := "res://data/units/"


static func definition(id: String) -> Resource:
	var path := UNIT_DIR + id + ".tres"
	if ResourceLoader.exists(path):
		return load(path)
	return null


static func all_unit_ids() -> PackedStringArray:
	var ids := PackedStringArray()
	var dir := DirAccess.open(UNIT_DIR)
	if dir == null:
		return ids
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			ids.append(file_name.get_basename())
	ids.sort()
	return ids


static func initiative_for(id: String) -> int:
	var data := definition(id)
	if data != null:
		return int(data.initiative)
	return 5


static func make_unit(
	id: String,
	unit_name: String,
	role: String,
	team: String,
	position: Vector2i,
	hp: int,
	attack: int,
	move_range: int,
	attack_range: int,
	color: Color,
	special: String
) -> Dictionary:
	var data := definition(id)
	var secondary := SkillCatalog.secondary_for_unit(id)
	var max_focus := 2
	var ai_profile := "default"
	if data != null:
		secondary = String(data.secondary_skill)
		max_focus = int(data.max_focus)
		ai_profile = String(data.ai_profile)
	var unit := UnitData.create(
		id,
		unit_name,
		role,
		team,
		position,
		hp,
		attack,
		move_range,
		attack_range,
		color,
		special,
		initiative_for(id),
		secondary
	)
	unit["max_focus"] = max_focus
	unit["focus"] = max_focus
	unit["ai_profile"] = ai_profile
	unit["visual_id"] = String(data.visual_id) if data != null and not String(data.visual_id).is_empty() else id
	unit["template_id"] = id
	return unit


static func make_hero(
	hero_id: String,
	position: Vector2i,
	rank: int,
	job_id: String,
	job_xp: Dictionary,
	equipment_slots: Dictionary,
	purchased_nodes: PackedStringArray = PackedStringArray()
) -> Dictionary:
	var data := definition(hero_id)
	var unit: Dictionary
	if data != null:
		unit = data.to_runtime_dict(position, "player")
	else:
		unit = make_unit(hero_id, hero_id.capitalize(), "Héros", "player", position, 9, 2, 4, 1, Color.WHITE, "")

	# Global campaign rank remains a small meta-progression bonus.
	var rank_bonus: int = maxi(0, rank - 1)
	unit["hp"] = int(unit["hp"]) + rank_bonus
	unit["max_hp"] = int(unit["max_hp"]) + rank_bonus

	var chosen_job := job_id
	if chosen_job.is_empty() and data != null:
		chosen_job = String(data.default_job_id)
	var xp := int(job_xp.get(chosen_job, 0))
	var level := JobCatalog.level_for_xp(chosen_job, xp)
	if data != null:
		level = max(level, int(data.starting_level))
	JobCatalog.apply_to_unit(unit, chosen_job, level, purchased_nodes)

	var allowed_slots := JobCatalog.allowed_slots(chosen_job)
	for slot in ["weapon", "armor", "accessory"]:
		if not allowed_slots.has(slot):
			continue
		var equipment_id := String(equipment_slots.get(slot, "none"))
		if equipment_id != "none":
			EquipmentCatalog.apply_to_unit(unit, equipment_id)
	unit["focus"] = int(unit["max_focus"])
	return unit


static func apply_equipment(unit: Dictionary, equipment_id: String) -> void:
	EquipmentCatalog.apply_to_unit(unit, equipment_id)


static func default_job(hero_id: String) -> String:
	var data := definition(hero_id)
	return String(data.default_job_id) if data != null else ""


static func available_jobs(hero_id: String) -> PackedStringArray:
	var data := definition(hero_id)
	if data == null:
		return PackedStringArray()
	return data.available_job_ids


static func unlocked_jobs(hero_id: String, job_xp: Dictionary) -> PackedStringArray:
	var result := PackedStringArray()
	for job_id in available_jobs(hero_id):
		if JobCatalog.is_job_unlocked(String(job_id), job_xp):
			result.append(String(job_id))
	return result


static func job_name(job_id: String) -> String:
	var data := JobCatalog.definition(job_id)
	return String(data.display_name) if data != null else job_id


static func job_description(job_id: String) -> String:
	var data := JobCatalog.definition(job_id)
	return String(data.description) if data != null else ""


static func job_level(job_id: String, job_xp: Dictionary) -> int:
	return JobCatalog.level_for_xp(job_id, int(job_xp.get(job_id, 0)))


static func job_xp_to_next(job_id: String, job_xp: Dictionary) -> int:
	return JobCatalog.xp_for_next(job_id, int(job_xp.get(job_id, 0)))




static func job_tree_points(job_id: String, job_xp: Dictionary, purchased_nodes: PackedStringArray) -> Dictionary:
	var level := job_level(job_id, job_xp)
	return {
		"level": level,
		"budget": JobCatalog.tree_point_budget(job_id, level),
		"spent": JobCatalog.tree_points_spent(job_id, purchased_nodes),
		"available": JobCatalog.tree_points_available(job_id, level, purchased_nodes),
	}


static func can_purchase_job_node(job_id: String, job_xp: Dictionary, purchased_nodes: PackedStringArray, node_id: String) -> Dictionary:
	return JobCatalog.can_purchase_node(job_id, node_id, job_level(job_id, job_xp), purchased_nodes)

static func equipment_name(equipment_id: String) -> String:
	return EquipmentCatalog.display_name(equipment_id)


static func equipment_description(equipment_id: String) -> String:
	return EquipmentCatalog.description(equipment_id)


static func equipment_slot(equipment_id: String) -> String:
	return EquipmentCatalog.slot(equipment_id)


static func equipment_ids_for_slot(slot: String) -> PackedStringArray:
	return EquipmentCatalog.ids_for_slot(slot)


static func reward_pool(mission_index: int) -> Array:
	if mission_index == 0:
		return ["sprout_badge", "rhythm_boots", "echo_lens"]
	if mission_index == 1:
		return ["thorn_ring", "hot_capacitor", "moss_charm"]
	return ["crown_core", "mycelium_plate", "phase_compass"]


static func hero_name(hero_id: String) -> String:
	var data := definition(hero_id)
	return String(data.display_name) if data != null else hero_id


static func hero_role(hero_id: String) -> String:
	var data := definition(hero_id)
	return String(data.role) if data != null else "Héros"


static func module_name(hero_id: String, index: int) -> String:
	match hero_id:
		"momo":
			return "Gants lourds" if index == 0 else "Bottes ressort"
		"pipo":
			return "Trousse XL" if index == 0 else "Bouclier mousse"
		"ziggy":
			return "Ampli spores" if index == 0 else "Semelles funk"
		"luma":
			return "Lentille longue" if index == 0 else "Batterie chaude"
		_:
			return "Standard"


static func module_description(hero_id: String, index: int) -> String:
	match hero_id:
		"momo":
			return "+1 ATQ" if index == 0 else "+1 MVT"
		"pipo":
			return "Soin spécial +1 PV" if index == 0 else "Pipo reçoit GARDE après son soin"
		"ziggy":
			return "Spore Funk inflige 3 dégâts" if index == 0 else "+1 MVT"
		"luma":
			return "+1 portée" if index == 0 else "+1 ATQ"
		_:
			return "Aucun bonus"
