@tool
class_name SporeMapZone2D
extends Polygon2D

## Polygonal gameplay zone authored directly in Godot's native 2D editor.
## Move the node with the normal transform tool and edit Polygon2D points with
## Godot's polygon editor. Runtime consumers use the occupied grid cells.

@export_group("Identity")
@export var zone_id: String = "zone":
	set(value):
		zone_id = value.strip_edges()
		queue_redraw()
@export var display_name: String = "Zone":
	set(value):
		display_name = value
		queue_redraw()
@export_enum("deployment", "objective", "trigger", "danger", "camera") var zone_type: String = "trigger":
	set(value):
		zone_type = value
		_refresh_visual()
@export_enum("any", "player", "enemy") var team: String = "any":
	set(value):
		team = value
		queue_redraw()
@export var enabled: bool = true:
	set(value):
		enabled = value
		_refresh_visual()

@export_group("Editor")
@export_range(0.05, 0.8, 0.01) var fill_alpha: float = 0.18:
	set(value):
		fill_alpha = clampf(value, 0.05, 0.8)
		_refresh_visual()


func _ready() -> void:
	if polygon.size() < 3:
		polygon = PackedVector2Array([
			Vector2(-32.0, -32.0),
			Vector2(32.0, -32.0),
			Vector2(32.0, 32.0),
			Vector2(-32.0, 32.0),
		])
	_refresh_visual()


func _refresh_visual() -> void:
	var base_color: Color = _zone_color()
	base_color.a = fill_alpha if enabled else 0.06
	color = base_color
	z_index = 24
	queue_redraw()


func _zone_color() -> Color:
	match zone_type:
		"deployment":
			return Color("#5aa9ff")
		"objective":
			return Color("#62e6a5")
		"danger":
			return Color("#ff6b6b")
		"camera":
			return Color("#d68cff")
		_:
			return Color("#ffd166")


func occupied_cells(map: SporeMap2D) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	if map == null or polygon.size() < 3:
		return result
	for y: int in range(map.grid_height):
		for x: int in range(map.grid_width):
			var cell: Vector2i = Vector2i(x, y)
			var map_local: Vector2 = map.cell_to_local(cell, true)
			var global_point: Vector2 = map.to_global(map_local)
			var zone_local: Vector2 = to_local(global_point)
			if Geometry2D.is_point_in_polygon(zone_local, polygon):
				result.append(cell)
	return result


func to_runtime_dict(map: SporeMap2D) -> Dictionary:
	return {
		"id": zone_id,
		"name": display_name,
		"type": zone_type,
		"team": team,
		"enabled": enabled,
		"cells": occupied_cells(map),
	}


func _draw() -> void:
	var outline: Color = _zone_color()
	outline.a = 0.95 if enabled else 0.35
	if polygon.size() >= 2:
		for index: int in range(polygon.size()):
			var next_index: int = (index + 1) % polygon.size()
			draw_line(polygon[index], polygon[next_index], outline, 2.0, true)
	var label: String = display_name if not display_name.is_empty() else zone_id
	if team != "any":
		label += " · " + team
	draw_string(ThemeDB.fallback_font, Vector2(-28.0, -40.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1.0, 11, outline)
