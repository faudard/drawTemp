extends SceneTree

const CampaignState = preload("res://scripts/campaign/campaign_state.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const MissionCatalog = preload("res://scripts/catalogs/mission_catalog.gd")
const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")
const CampaignCatalog = preload("res://scripts/catalogs/campaign_catalog.gd")
const AiCatalog = preload("res://scripts/catalogs/ai_catalog.gd")
const CinematicCatalog = preload("res://scripts/catalogs/cinematic_catalog.gd")
const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")
const VfxCatalog = preload("res://scripts/catalogs/vfx_catalog.gd")
const BattleRules = preload("res://scripts/core/battle_rules.gd")
const JobCatalog = preload("res://scripts/catalogs/job_catalog.gd")
const EquipmentCatalog = preload("res://scripts/catalogs/equipment_catalog.gd")

var failures: Array = []


func _init() -> void:
	test_campaign_round_trip()
	test_content_resources()
	test_catalogs()
	test_status_runtime()
	test_campaign_graph()
	test_ai_profiles()
	test_mission_logic()
	test_cinematics()
	test_visual_assets()
	test_progression()
	test_unit_schema()
	test_battle_rules()
	if failures.is_empty():
		print("Sporebound V1.9 architecture/content smoke test: OK")
		quit(0)
		return
	for message in failures:
		push_error(str(message))
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_campaign_round_trip() -> void:
	var source := CampaignState.new()
	source.spores = 17
	source.loop = 2
	source.max_unlocked = 2
	source.difficulty_index = 2
	source.campaign_node_id = "event_moss"
	source.mode = "event"
	source.hero_selected["luma"] = true
	source.hero_selected["ziggy"] = false
	source.unlocked_equipment.append("thorn_ring")
	source.hero_jobs["momo"] = "brave"
	source.hero_job_xp["momo"]["brave"] = 9
	source.hero_equipment_slots["momo"]["weapon"] = "thorn_ring"
	source.purchase_job_node("momo", "brave", "heavy_fists")
	var copy := CampaignState.new()
	copy.apply_save_dict(source.to_save_dict(5))
	expect(copy.spores == 17, "campaign spores round-trip")
	expect(copy.loop == 2, "campaign loop round-trip")
	expect(copy.max_unlocked == 2, "mission unlock round-trip")
	expect(copy.difficulty_index == 2, "difficulty round-trip")
	expect(copy.campaign_node_id == "event_moss", "campaign node round-trip")
	expect(copy.mode == "event", "campaign event mode round-trip")
	expect(bool(copy.hero_selected["luma"]), "hero selection round-trip")
	expect(copy.unlocked_equipment.has("thorn_ring"), "equipment unlock round-trip")
	expect(String(copy.hero_jobs["momo"]) == "brave", "job selection round-trip")
	expect(int(copy.hero_job_xp["momo"]["brave"]) == 9, "job mastery round-trip")
	expect(String(copy.hero_equipment_slots["momo"]["weapon"]) == "thorn_ring", "equipment slot round-trip")
	expect(copy.job_nodes("momo", "brave").has("heavy_fists"), "progression-tree round-trip")


func test_content_resources() -> void:
	var momo := UnitCatalog.definition("momo")
	expect(momo != null, "Momo UnitDefinition exists")
	if momo != null:
		expect(String(momo.display_name) == "Momo", "Momo resource name")
		expect(int(momo.max_hp) == 13, "Momo resource HP")
	var mission := MissionCatalog.definition(0)
	expect(mission != null, "MissionDefinition exists")
	if mission != null:
		expect(mission.obstacles.size() == 6, "mission resource obstacle count")
		expect(mission.enemy_positions.size() == 4, "mission resource enemy count")
	var funk := SkillCatalog.definition("funk")
	expect(funk != null, "SkillDefinition exists")
	if funk != null:
		expect(int(funk.cooldown_rounds) == 3, "skill resource cooldown")
		expect(not funk.effects.is_empty(), "skill resource executable effects")
	expect(StatusCatalog.definition("poisoned") != null, "Poison status exists")
	expect(CampaignCatalog.definition() != null, "CampaignDefinition exists")


func test_catalogs() -> void:
	expect(str(MissionCatalog.meta(0)["name"]) == "La Couronne Beatbox", "mission 1 metadata")
	expect(MissionCatalog.enemy_specs(2).size() == 5, "mission 3 enemy roster")
	expect(MissionCatalog.hero_starts(1).size() == 3, "mission deployment count")
	expect(SkillCatalog.focus_cost("mist") == 2, "mist focus cost")
	expect(SkillCatalog.cooldown_rounds("funk") == 3, "Spore Funk cooldown")
	expect(UnitCatalog.initiative_for("ziggy") == 8, "Ziggy initiative")
	expect(UnitCatalog.reward_pool(0).size() == 3, "reward pool size")


func test_status_runtime() -> void:
	var unit := {"statuses": {}}
	StatusCatalog.apply(unit, "poisoned")
	expect(StatusCatalog.has(unit, "poisoned"), "status apply")
	expect(StatusCatalog.remaining(unit, "poisoned") == 3, "status duration")
	expect(StatusCatalog.phase_events(unit, "activation_end").size() == 1, "poison tick event")
	StatusCatalog.finish_activation(unit)
	expect(StatusCatalog.remaining(unit, "poisoned") == 2, "status duration tick")
	StatusCatalog.apply(unit, "stunned")
	expect(StatusCatalog.prevents_action(unit), "stun blocks action")
	expect(StatusCatalog.prevents_movement(unit), "stun blocks movement")


func test_campaign_graph() -> void:
	var campaign := CampaignCatalog.definition()
	expect(campaign != null, "campaign graph loaded")
	if campaign == null:
		return
	expect(String(campaign.start_node_id) == "mission_crown", "campaign start node")
	expect(CampaignCatalog.mission_index_for_node("mission_stage") == 1, "campaign mission lookup")
	expect(CampaignCatalog.next_after_mission("crown", 0, 0, []) == "event_jam", "campaign transition")


func test_visual_assets() -> void:
	expect(VisualCatalog.all_visual_ids().size() >= 10, "starter visual library")
	expect(VfxCatalog.all_vfx_ids().size() >= 10, "starter VFX library")
	var momo := UnitCatalog.definition("momo")
	expect(momo != null and String(momo.visual_id) == "momo", "Momo visual binding")
	expect(VisualCatalog.definition("momo") != null, "Momo visual resource")
	expect(VfxCatalog.definition(SkillCatalog.vfx_id("funk")) != null, "Spore Funk VFX binding")


func test_progression() -> void:
	expect(JobCatalog.all_job_ids().size() >= 8, "starter job library")
	expect(EquipmentCatalog.all_equipment_ids().size() >= 9, "data-driven equipment library")
	expect(JobCatalog.level_for_xp("brave", 0) == 1, "job starts at level 1")
	expect(JobCatalog.level_for_xp("brave", 7) >= 3, "job mastery curve reaches level 3")
	expect(JobCatalog.progression_nodes("brave").size() >= 6, "Brave visual progression tree")
	expect(JobCatalog.tree_point_budget("brave", 2) == 2, "tree point budget follows job level")
	var momo := UnitCatalog.definition("momo")
	expect(momo != null and String(momo.default_job_id) == "brave", "Momo default job binding")
	expect(momo != null and momo.available_job_ids.has("bulwark"), "Momo advanced job binding")


func test_unit_schema() -> void:
	var equipment := {"weapon": "none", "armor": "none", "accessory": "sprout_badge"}
	var job_xp := {"brave": 0, "bulwark": 0}
	var hero := UnitCatalog.make_hero("momo", Vector2i(1, 2), 2, "brave", job_xp, equipment)
	for key in ["id", "name", "team", "pos", "hp", "max_hp", "attack", "move", "range", "initiative", "statuses", "focus", "max_focus", "cooldowns", "secondary", "job_id", "job_level", "resistances"]:
		expect(hero.has(key), "unit schema missing %s" % key)
	expect(int(hero["max_hp"]) == 17, "Momo rank + job + equipment HP")
	expect(int(hero["attack"]) == 4, "Momo Brave attack bonus")
	expect(int(hero["job_level"]) == 1, "Momo job level")


func test_battle_rules() -> void:
	expect(BattleRules.manhattan(Vector2i(0, 0), Vector2i(3, 2)) == 5, "Manhattan distance")
	expect(BattleRules.neighbours(Vector2i(2, 2)).size() == 4, "orthogonal neighbours")
	var target := {"pos": Vector2i(2, 2), "facing": Vector2i(0, 1)}
	var attacker := {"pos": Vector2i(2, 1)}
	expect(BattleRules.is_back_attack(attacker, target), "back attack detection")
	BattleRules.add_status(target, "guarded")
	expect(BattleRules.has_status(target, "guarded"), "status add/read")
	BattleRules.remove_status(target, "guarded")
	expect(not BattleRules.has_status(target, "guarded"), "status removal")


func test_ai_profiles() -> void:
	expect(AiCatalog.all_ids().size() >= 6, "starter AI profile library")
	var aggressive := AiCatalog.definition("aggressive")
	expect(aggressive != null, "aggressive AI profile")
	if aggressive != null:
		expect(float(aggressive.attack_position_bonus) > 100.0, "aggressive attack-position bias")
	var baveux := UnitCatalog.definition("baveux")
	expect(baveux != null and String(baveux.ai_profile) == "aggressive", "Baveux AI profile binding")


func test_mission_logic() -> void:
	var crown := MissionCatalog.definition(0)
	expect(crown != null and crown.victory_rules.size() == 1, "crown mission victory rule")
	expect(crown != null and crown.defeat_rules.size() == 1, "crown mission defeat rule")
	if crown != null:
		expect(crown.interactables.size() == 3, "crown mission V1.5 interactables")
	var stage := MissionCatalog.definition(1)
	expect(stage != null and stage.victory_rules.size() == 2, "survival mission OR victory rules")
	expect(stage != null and stage.battle_triggers.size() >= 1, "survival mission sequencer trigger")
	if stage != null and not stage.battle_triggers.is_empty():
		expect(String(stage.battle_triggers[0].condition_type) == "round_start", "trigger condition resource")
		expect(stage.battle_triggers[0].actions.size() >= 3, "trigger ordered V1.5 actions")
		expect(String(stage.battle_triggers[0].actions[1].action_type) == "wait", "sequencer delay action")


func test_cinematics() -> void:
	expect(CinematicCatalog.ids().size() >= 6, "starter cinematic library")
	var intro := CinematicCatalog.definition("intro_crown")
	expect(intro != null, "crown intro cinematic")
	if intro != null:
		expect(intro.actions.size() >= 4, "crown intro timeline actions")
	var finale := MissionCatalog.definition(2)
	expect(finale != null and String(finale.intro_cinematic_id) == "intro_finale", "finale cinematic binding")
	if finale != null and finale.battle_triggers.size() >= 2:
		expect(String(finale.battle_triggers[0].actions[0].action_type) == "play_cinematic", "boss phase II cinematic trigger")
