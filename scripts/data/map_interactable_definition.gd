@tool
class_name SporeMapInteractableDefinition
extends Resource

## Data-driven battlefield object used by doors, floor switches and chests.

@export var id: String = "object"
@export var display_name: String = "Objet"
@export_enum("door", "switch", "chest") var object_type: String = "door"
@export var cell: Vector2i = Vector2i.ZERO
@export var linked_object_id: String = ""
@export var starts_active: bool = false
@export var one_shot: bool = true

@export_group("Chest reward")
@export_enum("none", "heal_team", "focus_team") var reward_type: String = "none"
@export_range(0, 99, 1) var reward_value: int = 1
@export_enum("player", "enemy") var reward_team: String = "player"


func summary() -> String:
	var state := "actif" if starts_active else "inactif"
	return "%s • %s • (%d,%d) • %s" % [display_name, object_type, cell.x, cell.y, state]
