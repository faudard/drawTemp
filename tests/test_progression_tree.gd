extends SceneTree

const CampaignState = preload("res://scripts/campaign/campaign_state.gd")
const JobCatalog = preload("res://scripts/catalogs/job_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")

var failures: Array[String] = []


func _init() -> void:
	test_starter_trees()
	test_points_and_exclusive_branch()
	test_runtime_node_effects()
	test_save_round_trip()
	if failures.is_empty():
		print("Sporebound V1.9 progression-tree smoke test: OK")
		quit(0)
		return
	for message in failures:
		push_error(message)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_starter_trees() -> void:
	for job_id in JobCatalog.all_job_ids():
		var job := JobCatalog.definition(String(job_id))
		expect(job != null, "job exists: %s" % job_id)
		if job != null:
			expect(job.progression_nodes.size() >= 6, "%s has starter visual tree" % job_id)
	var brave := JobCatalog.definition("brave")
	expect(brave.progression_node_by_id("skill_hat") != null, "Brave Hat node exists")
	expect(brave.progression_node_by_id("heavy_fists") != null, "Brave branch node exists")


func test_points_and_exclusive_branch() -> void:
	var level := 2
	var purchased := PackedStringArray()
	expect(JobCatalog.tree_point_budget("brave", level) == 2, "level 2 grants two tree points")
	var heavy := JobCatalog.can_purchase_node("brave", "heavy_fists", level, purchased)
	expect(bool(heavy.get("ok", false)), "heavy_fists purchasable at level 2")
	purchased.append("heavy_fists")
	expect(JobCatalog.tree_points_available("brave", level, purchased) == 1, "one point remains after branch purchase")
	var spring := JobCatalog.can_purchase_node("brave", "spring_step", level, purchased)
	expect(not bool(spring.get("ok", true)), "exclusive alternative branch is blocked")


func test_runtime_node_effects() -> void:
	var xp := {"brave": 12, "bulwark": 0}
	var gear := {"weapon": "none", "armor": "none", "accessory": "none"}
	var base := UnitCatalog.make_hero("momo", Vector2i.ZERO, 1, "brave", xp, gear, PackedStringArray())
	var purchased := PackedStringArray(["heavy_fists", "royal_impact"])
	var branched := UnitCatalog.make_hero("momo", Vector2i.ZERO, 1, "brave", xp, gear, purchased)
	expect(int(branched.get("attack", 0)) == int(base.get("attack", 0)) + 1, "stat node affects runtime attack")
	var bonuses: Dictionary = branched.get("skill_power_bonuses", {})
	expect(int(bonuses.get("hat", 0)) >= 1, "passive node affects skill power")
	expect(String(branched.get("special", "")) == "hat", "auto skill node keeps primary skill")
	expect(String(branched.get("secondary", "")) == "taunt", "auto skill node keeps secondary skill")


func test_save_round_trip() -> void:
	var state := CampaignState.new()
	state.purchase_job_node("momo", "brave", "heavy_fists")
	var copy := CampaignState.new()
	copy.apply_save_dict(state.to_save_dict(5))
	expect(copy.job_nodes("momo", "brave").has("heavy_fists"), "purchased tree nodes persist")
