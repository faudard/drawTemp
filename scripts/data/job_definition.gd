@tool
class_name SporeJobDefinition
extends Resource

## Data-driven class/job edited by Sporebound Studio.
## UnitDefinition keeps base stats; jobs add modifiers and growth at runtime.

@export_group("Identity")
@export var id: String = "job"
@export var display_name: String = "Job"
@export_multiline var description: String = ""
@export var icon_path: String = ""
@export_range(1, 20, 1) var max_level: int = 10

@export_group("Job tree")
@export var unlock_from_job_id: String = ""
@export_range(1, 20, 1) var unlock_level: int = 1
@export var next_job_ids: PackedStringArray = PackedStringArray()

@export_group("Base modifiers")
@export_range(-30, 30, 1) var hp_bonus: int = 0
@export_range(-20, 20, 1) var attack_bonus: int = 0
@export_range(-20, 20, 1) var magic_power_bonus: int = 0
@export_range(-20, 20, 1) var physical_defense_bonus: int = 0
@export_range(-20, 20, 1) var magic_defense_bonus: int = 0
@export_range(-8, 8, 1) var movement_bonus: int = 0
@export_range(-8, 8, 1) var range_bonus: int = 0
@export_range(-20, 20, 1) var initiative_bonus: int = 0
@export_range(-30, 30, 1) var accuracy_bonus: int = 0
@export_range(-30, 30, 1) var evasion_bonus: int = 0
@export_range(-10, 10, 1) var focus_bonus: int = 0

@export_group("Growth per level")
@export_range(0.0, 5.0, 0.05) var hp_growth: float = 0.5
@export_range(0.0, 2.0, 0.05) var attack_growth: float = 0.15
@export_range(0.0, 2.0, 0.05) var magic_power_growth: float = 0.10
@export_range(0.0, 2.0, 0.05) var physical_defense_growth: float = 0.0
@export_range(0.0, 2.0, 0.05) var magic_defense_growth: float = 0.0
@export_range(0.0, 1.0, 0.05) var movement_growth: float = 0.0
@export_range(0.0, 1.0, 0.05) var range_growth: float = 0.0
@export_range(0.0, 2.0, 0.05) var initiative_growth: float = 0.1
@export_range(0.0, 2.0, 0.05) var accuracy_growth: float = 0.0
@export_range(0.0, 2.0, 0.05) var evasion_growth: float = 0.0
@export_range(0.0, 1.0, 0.05) var focus_growth: float = 0.0

@export_group("Mastery curve")
@export_range(1, 99, 1) var xp_base: int = 3
@export_range(0, 99, 1) var xp_step: int = 1


@export_group("Progression tree")
@export_range(0, 9, 1) var starting_tree_points: int = 1
@export_range(0, 9, 1) var tree_points_per_level: int = 1
@export var progression_nodes: Array[SporeProgressionNodeDefinition] = []

@export_group("Loadout")
@export var allowed_slots: PackedStringArray = PackedStringArray(["weapon", "armor", "accessory"])
@export var skill_unlocks: Array[Resource] = []
@export var resistances: Array[Resource] = []

@export_group("Job passives")
@export var skill_power_skill_id: String = ""
@export_range(-10, 10, 1) var skill_power_bonus: int = 0
@export var guard_after_skill_id: String = ""


func xp_for_level(level: int) -> int:
	var clamped: int = clampi(level, 1, max_level)
	var total: int = 0
	for current in range(1, clamped):
		total += xp_base + (current - 1) * xp_step
	return total


func level_from_xp(xp: int) -> int:
	var result: int = 1
	for candidate in range(2, max_level + 1):
		if xp < xp_for_level(candidate):
			break
		result = candidate
	return result


func unlocked_skills(level: int) -> PackedStringArray:
	var result := PackedStringArray()
	for unlock in skill_unlocks:
		if unlock != null and int(unlock.required_level) <= level and not String(unlock.skill_id).is_empty():
			result.append(String(unlock.skill_id))
	return result

func progression_node_by_id(node_id: String) -> SporeProgressionNodeDefinition:
	for node: SporeProgressionNodeDefinition in progression_nodes:
		if node != null and String(node.id) == node_id:
			return node
	return null


func progression_node_ids() -> PackedStringArray:
	var result := PackedStringArray()
	for node: SporeProgressionNodeDefinition in progression_nodes:
		if node != null and not String(node.id).is_empty():
			result.append(String(node.id))
	return result

