extends SceneTree

const MissionCatalog = preload("res://scripts/catalogs/mission_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")
const CampaignCatalog = preload("res://scripts/catalogs/campaign_catalog.gd")
const AiCatalog = preload("res://scripts/catalogs/ai_catalog.gd")
const CinematicCatalog = preload("res://scripts/catalogs/cinematic_catalog.gd")

const EFFECT_TYPES := ["damage", "heal", "status", "push", "pull", "focus", "guard", "reaction"]
const EFFECT_SCOPES := ["target", "self", "allies", "enemies"]
const EFFECT_SHAPES := ["single", "cross", "diamond"]


func _init() -> void:
	var failures: Array[String] = []
	_test_missions(failures)
	_test_units(failures)
	_test_ai_profiles(failures)
	_test_statuses(failures)
	_test_skills(failures)
	_test_campaign(failures)
	_test_cinematics(failures)
	if failures.is_empty():
		print("Sporebound Studio V1.9 content smoke test: OK")
		quit(0)
		return
	for failure in failures:
		push_error(failure)
	quit(1)


func _test_missions(failures: Array[String]) -> void:
	if MissionCatalog.count() < 3:
		failures.append("Expected at least 3 missions.")
	for mission_index in range(MissionCatalog.count()):
		var mission := MissionCatalog.definition(mission_index)
		if mission == null:
			failures.append("Mission %d failed to load." % mission_index)
			continue
		if mission.hero_starts.size() < 3:
			failures.append("Mission %s has fewer than 3 hero starts." % mission.id)
		for unit_id in mission.enemy_ids:
			if UnitCatalog.definition(String(unit_id)) == null:
				failures.append("Mission %s references unknown unit %s." % [mission.id, unit_id])
		if mission.victory_rules.is_empty():
			failures.append("Mission %s has no victory rules." % mission.id)
		if mission.defeat_rules.is_empty():
			failures.append("Mission %s has no defeat rules." % mission.id)
		var object_ids: Dictionary = {}
		for object_def in mission.interactables:
			if object_def == null:
				failures.append("Mission %s contains a null interactable." % mission.id)
				continue
			if object_ids.has(String(object_def.id)):
				failures.append("Mission %s duplicate interactable id %s." % [mission.id, object_def.id])
			object_ids[String(object_def.id)] = true
		for object_def in mission.interactables:
			if object_def != null and not String(object_def.linked_object_id).is_empty() and not object_ids.has(String(object_def.linked_object_id)):
				failures.append("Mission %s object %s links unknown object %s." % [mission.id, object_def.id, object_def.linked_object_id])
		var trigger_ids: Dictionary = {}
		for trigger in mission.battle_triggers:
			if trigger == null:
				failures.append("Mission %s contains a null trigger." % mission.id)
				continue
			if trigger_ids.has(String(trigger.id)):
				failures.append("Mission %s duplicate trigger id %s." % [mission.id, trigger.id])
			trigger_ids[String(trigger.id)] = true
			if trigger.actions.is_empty():
				failures.append("Mission %s trigger %s still uses a V1.4 legacy action." % [mission.id, trigger.id])
			for action in trigger.actions:
				if action == null:
					failures.append("Mission %s trigger %s contains a null action." % [mission.id, trigger.id])
					continue
				if String(action.action_type) in ["open_door", "close_door", "toggle_switch", "open_chest"] and not object_ids.has(String(action.object_id)):
					failures.append("Mission %s trigger %s references unknown object %s." % [mission.id, trigger.id, action.object_id])


func _test_units(failures: Array[String]) -> void:
	for unit_id in UnitCatalog.all_unit_ids():
		var unit := UnitCatalog.definition(String(unit_id))
		if unit == null:
			failures.append("Unit %s failed to load." % unit_id)
			continue
		for skill_id in [String(unit.primary_skill), String(unit.secondary_skill)]:
			if not skill_id.is_empty() and SkillCatalog.definition(skill_id) == null:
				failures.append("Unit %s references unknown skill %s." % [unit_id, skill_id])
		if String(unit.ai_profile) not in AiCatalog.all_ids():
			failures.append("Unit %s references unknown AI profile %s." % [unit_id, unit.ai_profile])


func _test_ai_profiles(failures: Array[String]) -> void:
	if AiCatalog.all_ids().size() < 6:
		failures.append("Expected the starter AI profile library.")
	for profile_id in AiCatalog.all_ids():
		var profile := AiCatalog.definition(String(profile_id))
		if profile == null:
			failures.append("AI profile %s failed to load." % profile_id)
		elif String(profile.id) != String(profile_id):
			failures.append("AI profile filename/id mismatch for %s." % profile_id)


func _test_statuses(failures: Array[String]) -> void:
	if StatusCatalog.all_status_ids().size() < 8:
		failures.append("Expected the V1.3 starter status library.")
	for status_id in StatusCatalog.all_status_ids():
		var status := StatusCatalog.definition(String(status_id))
		if status == null:
			failures.append("Status %s failed to load." % status_id)
			continue
		if String(status.id) != String(status_id):
			failures.append("Status filename/id mismatch for %s." % status_id)


func _test_skills(failures: Array[String]) -> void:
	var dir := DirAccess.open("res://data/skills/")
	if dir == null:
		failures.append("Cannot open data/skills.")
		return
	for file_name in dir.get_files():
		if not file_name.ends_with(".tres"):
			continue
		var skill_id := file_name.get_basename()
		var skill := SkillCatalog.definition(skill_id)
		if skill == null:
			failures.append("Skill %s failed to load." % skill_id)
			continue
		if skill.effects.is_empty():
			failures.append("Skill %s has no executable effects." % skill_id)
		for effect in skill.effects:
			if effect == null:
				failures.append("Skill %s contains a null effect." % skill_id)
				continue
			if String(effect.effect_type) not in EFFECT_TYPES:
				failures.append("Skill %s uses invalid effect type %s." % [skill_id, effect.effect_type])
			if String(effect.target_scope) not in EFFECT_SCOPES:
				failures.append("Skill %s uses invalid target scope %s." % [skill_id, effect.target_scope])
			if String(effect.area_shape) not in EFFECT_SHAPES:
				failures.append("Skill %s uses invalid area shape %s." % [skill_id, effect.area_shape])
			if String(effect.effect_type) == "status":
				if String(effect.status_id).is_empty():
					failures.append("Skill %s has a status effect without status_id." % skill_id)
				elif StatusCatalog.definition(String(effect.status_id)) == null:
					failures.append("Skill %s references unknown status %s." % [skill_id, effect.status_id])


func _test_campaign(failures: Array[String]) -> void:
	var campaign := CampaignCatalog.definition()
	if campaign == null:
		failures.append("Main campaign failed to load.")
		return
	if campaign.node_by_id(String(campaign.start_node_id)) == null:
		failures.append("Campaign start node is invalid.")
	var ids: Dictionary = {}
	for node in campaign.nodes:
		if node == null:
			failures.append("Campaign contains a null node.")
			continue
		if ids.has(String(node.id)):
			failures.append("Campaign duplicate node id %s." % node.id)
		ids[String(node.id)] = true
		if String(node.node_type) == "mission" and MissionCatalog.index_for_id(String(node.mission_id)) < 0:
			failures.append("Campaign node %s references unknown mission %s." % [node.id, node.mission_id])
	for node in campaign.nodes:
		if node == null:
			continue
		for target_id in node.outgoing_node_ids():
			if not ids.has(String(target_id)):
				failures.append("Campaign edge %s -> %s is broken." % [node.id, target_id])


func _test_cinematics(failures: Array[String]) -> void:
	if CinematicCatalog.ids().size() < 6:
		failures.append("Expected starter cinematic timeline library.")
	for cinematic_id in CinematicCatalog.ids():
		var cinematic := CinematicCatalog.definition(cinematic_id)
		if cinematic == null:
			failures.append("Cinematic %s failed to load." % cinematic_id)
			continue
		if cinematic.actions.is_empty():
			failures.append("Cinematic %s has no actions." % cinematic_id)
		for action in cinematic.actions:
			if action == null:
				failures.append("Cinematic %s contains a null action." % cinematic_id)
				continue
			if String(action.action_type) == "play_cinematic" and CinematicCatalog.definition(String(action.cinematic_id)) == null:
				failures.append("Cinematic %s references unknown nested cinematic %s." % [cinematic_id, action.cinematic_id])
	for mission_index in range(MissionCatalog.count()):
		var mission := MissionCatalog.definition(mission_index)
		if mission == null:
			continue
		for cinematic_id in [String(mission.intro_cinematic_id), String(mission.victory_cinematic_id), String(mission.defeat_cinematic_id)]:
			if not cinematic_id.is_empty() and CinematicCatalog.definition(cinematic_id) == null:
				failures.append("Mission %s references unknown cinematic %s." % [mission.id, cinematic_id])
		for trigger in mission.battle_triggers:
			if trigger == null:
				continue
			for action in trigger.actions:
				if action != null and String(action.action_type) == "play_cinematic" and CinematicCatalog.definition(String(action.cinematic_id)) == null:
					failures.append("Mission %s trigger %s references unknown cinematic %s." % [mission.id, trigger.id, action.cinematic_id])
