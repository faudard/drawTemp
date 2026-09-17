class_name SporeCampaignState
extends RefCounted

## Persistent meta-progression state. V1.9 adds purchased progression-tree nodes per hero/job.

var mode := "prep"
var mission_index := 0
var max_unlocked := 0
var loop := 0
var spores := 0
var wins := 0
var completed := false
var difficulty_index := 1
var next_mission_buff := ""
var hero_selected := {"momo": true, "pipo": true, "ziggy": true, "luma": false}
# Legacy V1.7 module values are kept only for save migration.
var hero_modules := {"momo": 0, "pipo": 0, "ziggy": 0, "luma": 0}
# Legacy single-equipment field is mirrored to accessory on migration.
var hero_equipment := {"momo": "none", "pipo": "none", "ziggy": "none", "luma": "none"}
var hero_jobs := {
	"momo": "brave",
	"pipo": "field_medic",
	"ziggy": "spore_maestro",
	"luma": "prism_ranger",
}
var hero_job_xp := {
	"momo": {"brave": 0, "bulwark": 0},
	"pipo": {"field_medic": 0, "moss_warden": 0},
	"ziggy": {"spore_maestro": 0, "groove_runner": 0},
	"luma": {"prism_ranger": 0, "flare_gunner": 0},
}
var hero_job_nodes := {
	"momo": {"brave": [], "bulwark": []},
	"pipo": {"field_medic": [], "moss_warden": []},
	"ziggy": {"spore_maestro": [], "groove_runner": []},
	"luma": {"prism_ranger": [], "flare_gunner": []},
}
var hero_equipment_slots := {
	"momo": {"weapon": "none", "armor": "none", "accessory": "none"},
	"pipo": {"weapon": "none", "armor": "none", "accessory": "none"},
	"ziggy": {"weapon": "none", "armor": "none", "accessory": "none"},
	"luma": {"weapon": "none", "armor": "none", "accessory": "none"},
}
var unlocked_equipment: Array = []
var campaign_node_id := "mission_crown"


func reset_progress() -> void:
	mode = "prep"
	mission_index = 0
	max_unlocked = 0
	loop = 0
	spores = 0
	wins = 0
	completed = false
	difficulty_index = 1
	next_mission_buff = ""
	hero_selected = {"momo": true, "pipo": true, "ziggy": true, "luma": false}
	hero_modules = {"momo": 0, "pipo": 0, "ziggy": 0, "luma": 0}
	hero_equipment = {"momo": "none", "pipo": "none", "ziggy": "none", "luma": "none"}
	hero_jobs = {"momo": "brave", "pipo": "field_medic", "ziggy": "spore_maestro", "luma": "prism_ranger"}
	hero_job_xp = {
		"momo": {"brave": 0, "bulwark": 0},
		"pipo": {"field_medic": 0, "moss_warden": 0},
		"ziggy": {"spore_maestro": 0, "groove_runner": 0},
		"luma": {"prism_ranger": 0, "flare_gunner": 0},
	}
	hero_job_nodes = {
		"momo": {"brave": [], "bulwark": []},
		"pipo": {"field_medic": [], "moss_warden": []},
		"ziggy": {"spore_maestro": [], "groove_runner": []},
		"luma": {"prism_ranger": [], "flare_gunner": []},
	}
	hero_equipment_slots = {
		"momo": {"weapon": "none", "armor": "none", "accessory": "none"},
		"pipo": {"weapon": "none", "armor": "none", "accessory": "none"},
		"ziggy": {"weapon": "none", "armor": "none", "accessory": "none"},
		"luma": {"weapon": "none", "armor": "none", "accessory": "none"},
	}
	unlocked_equipment.clear()
	campaign_node_id = "mission_crown"


func selected_hero_count() -> int:
	var count := 0
	for value in hero_selected.values():
		if bool(value):
			count += 1
	return count


func rank() -> int:
	return 1 + int(spores / 6)


func job_xp(hero_id: String, job_id: String) -> int:
	var jobs: Dictionary = hero_job_xp.get(hero_id, {})
	return max(0, int(jobs.get(job_id, 0)))


func add_job_xp(hero_id: String, job_id: String, amount: int) -> void:
	if amount <= 0 or job_id.is_empty():
		return
	if not hero_job_xp.has(hero_id):
		hero_job_xp[hero_id] = {}
	var jobs: Dictionary = hero_job_xp[hero_id]
	jobs[job_id] = max(0, int(jobs.get(job_id, 0)) + amount)
	hero_job_xp[hero_id] = jobs


func job_nodes(hero_id: String, job_id: String) -> PackedStringArray:
	var hero_nodes: Dictionary = hero_job_nodes.get(hero_id, {})
	var stored: Variant = hero_nodes.get(job_id, [])
	var result := PackedStringArray()
	if typeof(stored) == TYPE_ARRAY or typeof(stored) == TYPE_PACKED_STRING_ARRAY:
		for node_id in stored:
			var id := String(node_id)
			if not id.is_empty() and not result.has(id):
				result.append(id)
	return result


func purchase_job_node(hero_id: String, job_id: String, node_id: String) -> bool:
	if hero_id.is_empty() or job_id.is_empty() or node_id.is_empty():
		return false
	if not hero_job_nodes.has(hero_id):
		hero_job_nodes[hero_id] = {}
	var jobs: Dictionary = hero_job_nodes[hero_id]
	var nodes: Array = []
	var stored: Variant = jobs.get(job_id, [])
	if typeof(stored) == TYPE_ARRAY or typeof(stored) == TYPE_PACKED_STRING_ARRAY:
		for existing_id in stored:
			nodes.append(String(existing_id))
	if nodes.has(node_id):
		return false
	nodes.append(node_id)
	jobs[job_id] = nodes
	hero_job_nodes[hero_id] = jobs
	return true


func reset_job_nodes(hero_id: String, job_id: String) -> void:
	if not hero_job_nodes.has(hero_id):
		hero_job_nodes[hero_id] = {}
	var jobs: Dictionary = hero_job_nodes[hero_id]
	jobs[job_id] = []
	hero_job_nodes[hero_id] = jobs


func equipment_for(hero_id: String, slot: String) -> String:
	var slots: Dictionary = hero_equipment_slots.get(hero_id, {})
	return String(slots.get(slot, "none"))


func set_equipment(hero_id: String, slot: String, equipment_id: String) -> void:
	if not hero_equipment_slots.has(hero_id):
		hero_equipment_slots[hero_id] = {"weapon": "none", "armor": "none", "accessory": "none"}
	var slots: Dictionary = hero_equipment_slots[hero_id]
	slots[slot] = equipment_id
	hero_equipment_slots[hero_id] = slots
	if slot == "accessory":
		hero_equipment[hero_id] = equipment_id


func to_save_dict(version: int) -> Dictionary:
	return {
		"version": version,
		"campaign_mode": mode,
		"campaign_mission_index": mission_index,
		"campaign_max_unlocked": max_unlocked,
		"campaign_loop": loop,
		"campaign_spores": spores,
		"campaign_wins": wins,
		"campaign_completed": completed,
		"difficulty_index": difficulty_index,
		"next_mission_buff": next_mission_buff,
		"hero_selected": hero_selected,
		"hero_modules": hero_modules,
		"hero_equipment": hero_equipment,
		"hero_jobs": hero_jobs,
		"hero_job_xp": hero_job_xp,
		"hero_job_nodes": hero_job_nodes,
		"hero_equipment_slots": hero_equipment_slots,
		"unlocked_equipment": unlocked_equipment,
		"campaign_node_id": campaign_node_id,
	}


func apply_save_dict(data: Dictionary) -> void:
	mode = str(data.get("campaign_mode", "prep"))
	if mode not in ["prep", "battle", "debrief", "event"]:
		mode = "prep"
	if mode in ["battle", "debrief"]:
		mode = "prep"
	mission_index = max(0, int(data.get("campaign_mission_index", 0)))
	max_unlocked = max(0, int(data.get("campaign_max_unlocked", mission_index)))
	loop = max(0, int(data.get("campaign_loop", 0)))
	spores = max(0, int(data.get("campaign_spores", 0)))
	wins = max(0, int(data.get("campaign_wins", 0)))
	completed = bool(data.get("campaign_completed", false))
	difficulty_index = clamp(int(data.get("difficulty_index", 1)), 0, 2)
	next_mission_buff = str(data.get("next_mission_buff", ""))
	campaign_node_id = str(data.get("campaign_node_id", "mission_crown"))

	var saved_selected: Variant = data.get("hero_selected", {})
	if typeof(saved_selected) == TYPE_DICTIONARY:
		for hero_id in hero_selected.keys():
			if saved_selected.has(hero_id):
				hero_selected[hero_id] = bool(saved_selected[hero_id])

	var saved_modules: Variant = data.get("hero_modules", {})
	if typeof(saved_modules) == TYPE_DICTIONARY:
		for hero_id in hero_modules.keys():
			if saved_modules.has(hero_id):
				hero_modules[hero_id] = clamp(int(saved_modules[hero_id]), 0, 1)

	var saved_gear: Variant = data.get("hero_equipment", {})
	if typeof(saved_gear) == TYPE_DICTIONARY:
		for hero_id in hero_equipment.keys():
			if saved_gear.has(hero_id):
				hero_equipment[hero_id] = str(saved_gear[hero_id])

	var saved_jobs: Variant = data.get("hero_jobs", {})
	if data.has("hero_jobs") and typeof(saved_jobs) == TYPE_DICTIONARY:
		for hero_id in hero_jobs.keys():
			if saved_jobs.has(hero_id) and not String(saved_jobs[hero_id]).is_empty():
				hero_jobs[hero_id] = String(saved_jobs[hero_id])
	else:
		_migrate_modules_to_jobs()

	var saved_job_xp: Variant = data.get("hero_job_xp", {})
	if typeof(saved_job_xp) == TYPE_DICTIONARY:
		for hero_id in hero_job_xp.keys():
			if saved_job_xp.has(hero_id) and typeof(saved_job_xp[hero_id]) == TYPE_DICTIONARY:
				var merged: Dictionary = hero_job_xp[hero_id]
				for job_id in saved_job_xp[hero_id].keys():
					merged[String(job_id)] = max(0, int(saved_job_xp[hero_id][job_id]))
				hero_job_xp[hero_id] = merged

	var saved_job_nodes: Variant = data.get("hero_job_nodes", {})
	if typeof(saved_job_nodes) == TYPE_DICTIONARY:
		for hero_id in saved_job_nodes.keys():
			if typeof(saved_job_nodes[hero_id]) != TYPE_DICTIONARY:
				continue
			if not hero_job_nodes.has(String(hero_id)):
				hero_job_nodes[String(hero_id)] = {}
			var jobs: Dictionary = hero_job_nodes[String(hero_id)]
			for job_id in saved_job_nodes[hero_id].keys():
				var clean: Array = []
				var raw_nodes: Variant = saved_job_nodes[hero_id][job_id]
				if typeof(raw_nodes) == TYPE_ARRAY or typeof(raw_nodes) == TYPE_PACKED_STRING_ARRAY:
					for node_id in raw_nodes:
						var id := String(node_id)
						if not id.is_empty() and not clean.has(id):
							clean.append(id)
				jobs[String(job_id)] = clean
			hero_job_nodes[String(hero_id)] = jobs

	var saved_slots: Variant = data.get("hero_equipment_slots", {})
	if data.has("hero_equipment_slots") and typeof(saved_slots) == TYPE_DICTIONARY:
		for hero_id in hero_equipment_slots.keys():
			if saved_slots.has(hero_id) and typeof(saved_slots[hero_id]) == TYPE_DICTIONARY:
				var slots: Dictionary = hero_equipment_slots[hero_id]
				for slot in ["weapon", "armor", "accessory"]:
					if saved_slots[hero_id].has(slot):
						slots[slot] = String(saved_slots[hero_id][slot])
				hero_equipment_slots[hero_id] = slots
	else:
		for hero_id in hero_equipment.keys():
			var old_id := String(hero_equipment[hero_id])
			if old_id != "none":
				hero_equipment_slots[hero_id]["accessory"] = old_id

	var saved_unlocks: Variant = data.get("unlocked_equipment", [])
	if typeof(saved_unlocks) == TYPE_ARRAY:
		unlocked_equipment.clear()
		for equipment_id in saved_unlocks:
			var id := str(equipment_id)
			if not unlocked_equipment.has(id):
				unlocked_equipment.append(id)

	for hero_id in hero_equipment_slots.keys():
		var slots: Dictionary = hero_equipment_slots[hero_id]
		for slot in ["weapon", "armor", "accessory"]:
			var equipped := String(slots.get(slot, "none"))
			if equipped != "none" and not unlocked_equipment.has(equipped):
				slots[slot] = "none"
		hero_equipment_slots[hero_id] = slots
		hero_equipment[hero_id] = String(slots.get("accessory", "none"))
	max_unlocked = max(max_unlocked, mission_index)


func _migrate_modules_to_jobs() -> void:
	var primary := {"momo": "brave", "pipo": "field_medic", "ziggy": "spore_maestro", "luma": "prism_ranger"}
	var secondary := {"momo": "bulwark", "pipo": "moss_warden", "ziggy": "groove_runner", "luma": "flare_gunner"}
	for hero_id in hero_jobs.keys():
		var old_secondary := int(hero_modules.get(hero_id, 0)) == 1
		hero_jobs[hero_id] = secondary[hero_id] if old_secondary else primary[hero_id]
		if old_secondary:
			var jobs: Dictionary = hero_job_xp[hero_id]
			jobs[primary[hero_id]] = max(int(jobs.get(primary[hero_id], 0)), 7)
			hero_job_xp[hero_id] = jobs
