@tool
class_name SporeMapInteractable2D
extends Polygon2D

const MapInteractableDefinition = preload("res://scripts/data/map_interactable_definition.gd")

@export_group("Identity")
@export var object_id: String = "object"
@export var display_name: String = "Objet":
	set(value):
		display_name = value
		queue_redraw()
@export_enum("door", "switch", "chest") var object_type: String = "door":
	set(value):
		object_type = value
		_refresh_visual()
@export var linked_object_id: String = ""

@export_group("State")
@export var starts_active: bool = false
@export var one_shot: bool = true

@export_group("Reward")
@export_enum("none", "heal_team", "focus_team") var reward_type: String = "none"
@export_range(0, 20, 1) var reward_value: int = 0
@export_enum("player", "enemy") var reward_team: String = "player"


func _ready() -> void:
	_refresh_visual()


func _refresh_visual() -> void:
	match object_type:
		"switch":
			polygon = PackedVector2Array([Vector2(0.0, -17.0), Vector2(17.0, 0.0), Vector2(0.0, 17.0), Vector2(-17.0, 0.0)])
			color = Color("#67c8ff")
		"chest":
			polygon = PackedVector2Array([Vector2(-20.0, -13.0), Vector2(20.0, -13.0), Vector2(20.0, 13.0), Vector2(-20.0, 13.0)])
			color = Color("#c99245")
		_:
			polygon = PackedVector2Array([Vector2(-18.0, -26.0), Vector2(18.0, -26.0), Vector2(18.0, 26.0), Vector2(-18.0, 26.0)])
			color = Color(1.0, 0.82, 0.35, 0.35)
	z_index = 32
	queue_redraw()


func to_definition(cell: Vector2i) -> Resource:
	var definition: Resource = MapInteractableDefinition.new()
	definition.id = object_id
	definition.display_name = display_name
	definition.object_type = object_type
	definition.cell = cell
	definition.linked_object_id = linked_object_id
	definition.starts_active = starts_active
	definition.one_shot = one_shot
	definition.reward_type = reward_type
	definition.reward_value = reward_value
	definition.reward_team = reward_team
	return definition


func _draw() -> void:
	match object_type:
		"door":
			draw_rect(Rect2(Vector2(-18.0, -26.0), Vector2(36.0, 52.0)), Color("#ffd166"), false, 3.0)
			draw_string(ThemeDB.fallback_font, Vector2(-5.0, 5.0), "D", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 13, Color("#ffd166"))
		"switch":
			draw_string(ThemeDB.fallback_font, Vector2(-4.0, 5.0), "I", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 11, Color("#102033"))
		"chest":
			draw_string(ThemeDB.fallback_font, Vector2(-6.0, 5.0), "◆", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 12, Color("#fff0b3"))
	var label: String = display_name if not display_name.is_empty() else object_id
	draw_string(ThemeDB.fallback_font, Vector2(-38.0, 42.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1.0, 10, Color("#fff0c8"))
