extends SceneTree

const CampaignState = preload("res://scripts/campaign/campaign_state.gd")
const JobCatalog = preload("res://scripts/catalogs/job_catalog.gd")
const EquipmentCatalog = preload("res://scripts/catalogs/equipment_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")

var failures: Array[String] = []


func _init() -> void:
	test_job_library()
	test_job_unlocks()
	test_equipment_library()
	test_runtime_application()
	test_save_round_trip()
	if failures.is_empty():
		print("Sporebound V1.9 progression smoke test: OK")
		quit(0)
		return
	for message in failures:
		push_error(message)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_job_library() -> void:
	expect(JobCatalog.all_job_ids().size() >= 8, "8 starter jobs expected")
	var brave := JobCatalog.definition("brave")
	expect(brave != null, "Brave job exists")
	if brave != null:
		expect(brave.unlocked_skills(1).has("hat"), "Brave unlocks Hat at level 1")
		expect(brave.unlocked_skills(2).has("taunt"), "Brave unlocks Taunt at level 2")
		expect(JobCatalog.level_for_xp("brave", 7) >= 3, "Brave reaches level 3 at starter curve")


func test_job_unlocks() -> void:
	var xp := {"brave": 0, "bulwark": 0}
	expect(not JobCatalog.is_job_unlocked("bulwark", xp), "Bulwark locked at Brave level 1")
	xp["brave"] = 7
	expect(JobCatalog.is_job_unlocked("bulwark", xp), "Bulwark unlocks at Brave level 3")


func test_equipment_library() -> void:
	expect(EquipmentCatalog.all_equipment_ids().size() >= 9, "9 equipment resources expected")
	expect(EquipmentCatalog.slot("mycelium_plate") == "armor", "Mycelium Plate is armor")
	expect(EquipmentCatalog.slot("thorn_ring") == "weapon", "Thorn Ring is weapon")


func test_runtime_application() -> void:
	var xp := {"brave": 7, "bulwark": 0}
	var slots := {"weapon": "thorn_ring", "armor": "mycelium_plate", "accessory": "none"}
	var unit := UnitCatalog.make_hero("momo", Vector2i(0, 0), 1, "brave", xp, slots)
	expect(String(unit.get("job_id", "")) == "brave", "runtime hero job id")
	expect(int(unit.get("job_level", 0)) >= 3, "runtime hero job level")
	expect(int(unit.get("attack", 0)) >= 5, "job + equipment attack applied")
	expect(int(unit.get("max_hp", 0)) >= 16, "job + armor HP applied")
	expect(unit.has("resistances"), "runtime resistances dictionary")


func test_save_round_trip() -> void:
	var state := CampaignState.new()
	state.unlocked_equipment = ["thorn_ring", "mycelium_plate"]
	state.hero_jobs["momo"] = "brave"
	state.hero_job_xp["momo"]["brave"] = 11
	state.set_equipment("momo", "weapon", "thorn_ring")
	state.set_equipment("momo", "armor", "mycelium_plate")
	state.purchase_job_node("momo", "brave", "heavy_fists")
	var copy := CampaignState.new()
	copy.apply_save_dict(state.to_save_dict(5))
	expect(int(copy.hero_job_xp["momo"]["brave"]) == 11, "job XP saved")
	expect(copy.equipment_for("momo", "weapon") == "thorn_ring", "weapon slot saved")
	expect(copy.equipment_for("momo", "armor") == "mycelium_plate", "armor slot saved")
	expect(copy.job_nodes("momo", "brave").has("heavy_fists"), "tree node purchase saved")
