@tool
class_name SporeProgressionNodeDefinition
extends Resource

## One node in a job progression tree. Nodes are embedded in JobDefinition Resources.

@export_group("Identity")
@export var id: String = "node"
@export var display_name: String = "Progression node"
@export_multiline var description: String = ""
@export_enum("skill", "stat", "passive") var node_type: String = "stat"
@export var editor_position: Vector2 = Vector2(80.0, 120.0)

@export_group("Unlock")
@export_range(0, 9, 1) var cost: int = 1
@export_range(1, 20, 1) var required_level: int = 1
@export var auto_unlock: bool = false
@export var required_node_ids: PackedStringArray = PackedStringArray()
@export var exclusive_group: String = ""

@export_group("Skill node")
@export var skill_id: String = ""

@export_group("Stat node")
@export_enum("hp", "attack", "movement", "range", "initiative", "focus") var stat_type: String = "hp"
@export_range(-20, 20, 1) var stat_value: int = 1

@export_group("Passive node")
@export_enum("skill_power", "resistance", "guard_after_skill", "focus_regen") var passive_type: String = "skill_power"
@export var passive_target: String = ""
@export_range(-100, 100, 1) var passive_value: int = 1


func summary() -> String:
	var detail := ""
	match node_type:
		"skill":
			detail = "Skill %s" % skill_id
		"stat":
			detail = "%s %+d" % [stat_type, stat_value]
		"passive":
			detail = "%s %s %+d" % [passive_type, passive_target, passive_value]
	return "%s • %s • coût %d" % [display_name, detail, cost]
