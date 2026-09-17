@tool
class_name SporeCampaignNodeDefinition
extends Resource

## One node in a data-driven campaign flow graph.

@export_group("Identity")
@export var id: String = "node"
@export_enum("mission", "event", "end") var node_type: String = "mission"
@export var title: String = "Node"
@export_multiline var body: String = ""
@export var editor_position: Vector2 = Vector2.ZERO

@export_group("Conditions")
@export_range(0, 999, 1) var minimum_spores: int = 0
@export_range(0, 99, 1) var minimum_loop: int = 0
@export var required_equipment: String = ""
@export var fallback_node_id: String = ""

@export_group("Mission")
@export var mission_id: String = ""
@export var next_node_id: String = ""
@export_range(0, 20, 1) var victory_spores_bonus: int = 0
@export var reward_pool_override: PackedStringArray = PackedStringArray()

@export_group("Event choice A")
@export var choice_a_label: String = "Continuer"
@export var choice_a_next_node_id: String = ""
@export_enum("none", "xp", "focus_buff", "guard_buff") var choice_a_reward_type: String = "none"
@export_range(0, 20, 1) var choice_a_reward_value: int = 0

@export_group("Event choice B")
@export var choice_b_label: String = ""
@export var choice_b_next_node_id: String = ""
@export_enum("none", "xp", "focus_buff", "guard_buff") var choice_b_reward_type: String = "none"
@export_range(0, 20, 1) var choice_b_reward_value: int = 0


func outgoing_node_ids() -> PackedStringArray:
	var result := PackedStringArray()
	if node_type == "mission" and not next_node_id.is_empty():
		result.append(next_node_id)
	elif node_type == "event":
		if not choice_a_next_node_id.is_empty():
			result.append(choice_a_next_node_id)
		if not choice_b_next_node_id.is_empty() and choice_b_next_node_id != choice_a_next_node_id:
			result.append(choice_b_next_node_id)
	return result
