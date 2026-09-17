@tool
class_name SporeBattleTriggerDefinition
extends Resource

## Runtime battle event: condition -> ordered action sequence.
## Legacy V1.4 single-action fields remain for backwards compatibility.

@export_group("Identity")
@export var id: String = "trigger"
@export var enabled: bool = true
@export var once: bool = true

@export_group("Condition")
@export_enum(
	"round_start",
	"round_end",
	"enemy_count_at_most",
	"player_count_at_most",
	"unit_hp_at_most",
	"unit_defeated",
	"player_enters_cell",
	"enemy_enters_cell",
	"player_enters_zone",
	"enemy_enters_zone"
) var condition_type: String = "round_start"
@export_range(0, 99, 1) var condition_value: int = 1
@export var condition_unit_id: String = ""
@export var condition_cell: Vector2i = Vector2i(-1, -1)
@export var condition_zone_id: String = ""

@export_group("V1.5 Sequence")
@export var actions: Array[Resource] = []

@export_group("Legacy V1.4 Action")
@export_enum(
	"message",
	"spawn_enemy",
	"apply_status_to_unit",
	"add_hazard",
	"remove_hazard",
	"heal_team",
	"damage_team",
	"grant_focus_team"
) var action_type: String = "message"
@export_multiline var message: String = ""
@export var action_unit_id: String = ""
@export var action_status_id: String = ""
@export var action_cell: Vector2i = Vector2i(-1, -1)
@export_range(-99, 99, 1) var action_value: int = 1
@export_enum("player", "enemy") var action_team: String = "enemy"


func summary() -> String:
	if not actions.is_empty():
		return "%s → %d action(s)" % [condition_type, actions.size()]
	return "%s → %s [legacy]" % [condition_type, action_type]
