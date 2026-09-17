class_name SporeCampaignCatalog
extends RefCounted

const MissionCatalog = preload("res://scripts/catalogs/mission_catalog.gd")
const CAMPAIGN_PATH := "res://data/campaigns/main_campaign.tres"


static func definition() -> Resource:
	return load(CAMPAIGN_PATH) if ResourceLoader.exists(CAMPAIGN_PATH) else null


static func node(node_id: String) -> Resource:
	var campaign := definition()
	return campaign.node_by_id(node_id) if campaign != null else null


static func start_node_id() -> String:
	var campaign := definition()
	return String(campaign.start_node_id) if campaign != null else ""


static func node_for_mission_id(mission_id: String) -> Resource:
	var campaign := definition()
	if campaign == null:
		return null
	for item in campaign.nodes:
		if item != null and String(item.node_type) == "mission" and String(item.mission_id) == mission_id:
			return item
	return null


static func mission_id_for_node(node_id: String) -> String:
	var item := node(node_id)
	return String(item.mission_id) if item != null and String(item.node_type) == "mission" else ""


static func mission_index_for_node(node_id: String) -> int:
	var mission_id := mission_id_for_node(node_id)
	return MissionCatalog.index_for_id(mission_id) if not mission_id.is_empty() else -1


static func is_eligible(item: Resource, spores: int, loop: int, unlocked_equipment: Array) -> bool:
	if item == null:
		return false
	if spores < int(item.minimum_spores) or loop < int(item.minimum_loop):
		return false
	var requirement := String(item.required_equipment)
	return requirement.is_empty() or unlocked_equipment.has(requirement)


static func resolve_node_id(node_id: String, spores: int, loop: int, unlocked_equipment: Array) -> String:
	var current := node_id
	var guard := 0
	while not current.is_empty() and guard < 20:
		guard += 1
		var item := node(current)
		if item == null:
			return ""
		if is_eligible(item, spores, loop, unlocked_equipment):
			return current
		current = String(item.fallback_node_id)
	return ""


static func next_after_mission(mission_id: String, spores: int, loop: int, unlocked_equipment: Array) -> String:
	var mission_node := node_for_mission_id(mission_id)
	if mission_node == null:
		return ""
	return resolve_node_id(String(mission_node.next_node_id), spores, loop, unlocked_equipment)


static func victory_spores_bonus(mission_id: String) -> int:
	var item := node_for_mission_id(mission_id)
	return int(item.victory_spores_bonus) if item != null else 0


static func reward_pool_override(mission_id: String) -> PackedStringArray:
	var item := node_for_mission_id(mission_id)
	return item.reward_pool_override if item != null else PackedStringArray()
