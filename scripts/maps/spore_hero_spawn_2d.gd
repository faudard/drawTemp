@tool
class_name SporeHeroSpawn2D
extends Polygon2D

@export_range(0, 20, 1) var order: int = 0:
	set(value):
		order = maxi(0, value)
		_refresh_visual()
@export_range(8.0, 32.0, 1.0) var marker_radius: float = 18.0:
	set(value):
		marker_radius = maxf(8.0, value)
		_refresh_visual()


func _ready() -> void:
	_refresh_visual()


func _refresh_visual() -> void:
	var points: PackedVector2Array = PackedVector2Array()
	for index: int in range(16):
		var angle: float = TAU * float(index) / 16.0
		points.append(Vector2(cos(angle), sin(angle)) * marker_radius)
	polygon = points
	color = Color("#67c8ff")
	z_index = 30
	queue_redraw()


func _draw() -> void:
	var label: String = "H%d" % (order + 1)
	draw_circle(Vector2.ZERO, marker_radius, Color("#d8f3ff"), false, 2.5)
	draw_string(ThemeDB.fallback_font, Vector2(-10.0, 5.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1.0, 12, Color("#102033"))
	draw_string(ThemeDB.fallback_font, Vector2(-28.0, marker_radius + 16.0), "HÉROS %d" % (order + 1), HORIZONTAL_ALIGNMENT_LEFT, -1.0, 10, Color("#d8f3ff"))
