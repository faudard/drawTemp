@tool
class_name SporeEnemySpawn2D
extends Polygon2D

@export_group("Unit")
@export var unit_id: String = "baveux":
	set(value):
		unit_id = value.strip_edges()
		_refresh_visual()
@export var role_override: String = "":
	set(value):
		role_override = value
		queue_redraw()

@export_group("Mission overrides (-1 = global)")
@export_range(-1, 99, 1) var hp_override: int = -1
@export_range(-1, 30, 1) var attack_override: int = -1
@export_range(-1, 20, 1) var move_override: int = -1
@export_range(-1, 20, 1) var range_override: int = -1


func _ready() -> void:
	_refresh_visual()


func _refresh_visual() -> void:
	var radius: float = 19.0
	var points: PackedVector2Array = PackedVector2Array()
	for index: int in range(12):
		var angle: float = TAU * float(index) / 12.0
		points.append(Vector2(cos(angle), sin(angle)) * radius)
	polygon = points
	color = Color("#ff8a78")
	z_index = 31
	queue_redraw()


func _draw() -> void:
	var short_name: String = unit_id.substr(0, mini(3, unit_id.length())).to_upper()
	draw_circle(Vector2.ZERO, 19.0, Color("#ffd1c9"), false, 2.5)
	draw_string(ThemeDB.fallback_font, Vector2(-12.0, 5.0), short_name, HORIZONTAL_ALIGNMENT_LEFT, -1.0, 10, Color("#311511"))
	var title: String = unit_id.replace("_", " ").capitalize()
	if not role_override.is_empty():
		title += " · " + role_override
	draw_string(ThemeDB.fallback_font, Vector2(-34.0, 37.0), title, HORIZONTAL_ALIGNMENT_LEFT, -1.0, 10, Color("#ffe0da"))
