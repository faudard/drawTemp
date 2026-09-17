@tool
class_name SporeMapCanvas
extends Control

signal cell_pressed(cell: Vector2i, mouse_button: int)
signal cell_dragged(cell: Vector2i, mouse_button: int)
signal cell_released(cell: Vector2i, mouse_button: int)

var mission: Resource
var hover_cell := Vector2i(-1, -1)
var active_tool := "obstacle"
var cell_size := 52.0
var board_origin := Vector2(12.0, 12.0)
var overlay_cells: Array[Vector2i] = []
var overlay_color := Color(1.0, 0.86, 0.36, 0.23)
var selected_spawn_cell := Vector2i(-999, -999)
var _drag_button := 0
var _last_drag_cell := Vector2i(-999, -999)

const GROUND_A := Color("#263950")
const GROUND_B := Color("#2b4259")
const GRID := Color("#52708a")


func _ready() -> void:
	custom_minimum_size = Vector2(560.0, 470.0)
	mouse_default_cursor_shape = Control.CURSOR_CROSS
	set_process(false)


func set_mission(value: Resource) -> void:
	mission = value
	overlay_cells.clear()
	selected_spawn_cell = Vector2i(-999, -999)
	queue_redraw()


func set_tool(value: String) -> void:
	active_tool = value
	queue_redraw()


func set_overlay(cells: Array[Vector2i], color: Color = Color(1.0, 0.86, 0.36, 0.23)) -> void:
	overlay_cells = cells.duplicate()
	overlay_color = color
	queue_redraw()


func clear_overlay() -> void:
	overlay_cells.clear()
	queue_redraw()


func set_selected_spawn(cell: Vector2i) -> void:
	selected_spawn_cell = cell
	queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if mission == null:
		return
	if event is InputEventMouseMotion:
		var cell := point_to_cell(event.position)
		if cell != hover_cell:
			hover_cell = cell
			queue_redraw()
		if _drag_button != 0 and is_cell_valid(cell) and cell != _last_drag_cell:
			_last_drag_cell = cell
			cell_dragged.emit(cell, _drag_button)
			accept_event()
	elif event is InputEventMouseButton:
		if event.button_index not in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT]:
			return
		var cell := point_to_cell(event.position)
		if not is_cell_valid(cell):
			return
		if event.pressed:
			_drag_button = event.button_index
			_last_drag_cell = cell
			cell_pressed.emit(cell, event.button_index)
		else:
			cell_released.emit(cell, event.button_index)
			_drag_button = 0
		accept_event()


func point_to_cell(point: Vector2) -> Vector2i:
	var local := point - board_origin
	return Vector2i(floor(local.x / cell_size), floor(local.y / cell_size))


func is_cell_valid(cell: Vector2i) -> bool:
	return (
		mission != null
		and cell.x >= 0
		and cell.y >= 0
		and cell.x < int(mission.grid_width)
		and cell.y < int(mission.grid_height)
	)


func _draw() -> void:
	if mission == null:
		draw_string(ThemeDB.fallback_font, Vector2(20, 34), "Aucune mission sélectionnée", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color.WHITE)
		return
	var width: int = maxi(1, int(mission.grid_width))
	var height: int = maxi(1, int(mission.grid_height))
	cell_size = min((size.x - 24.0) / float(width), (size.y - 24.0) / float(height))
	cell_size = clamp(cell_size, 28.0, 62.0)
	var board_size := Vector2(width * cell_size, height * cell_size)
	board_origin = Vector2((size.x - board_size.x) * 0.5, (size.y - board_size.y) * 0.5)

	for y in range(height):
		for x in range(width):
			var cell := Vector2i(x, y)
			var rect := Rect2(board_origin + Vector2(x, y) * cell_size, Vector2(cell_size, cell_size))
			var fill := GROUND_A if (x + y) % 2 == 0 else GROUND_B
			draw_rect(rect, fill, true)
			_draw_tile_layers(cell, rect)
			draw_rect(rect, GRID, false, 1.0)

	_draw_spawns()
	_draw_interactables()
	for cell in overlay_cells:
		if is_cell_valid(cell):
			var overlay_rect := Rect2(board_origin + Vector2(cell) * cell_size, Vector2(cell_size, cell_size))
			draw_rect(overlay_rect.grow(-2.0), overlay_color, true)
			var overlay_edge := overlay_color
		overlay_edge.a = 0.92
		draw_rect(overlay_rect.grow(-2.0), overlay_edge, false, 2.0)
	if is_cell_valid(selected_spawn_cell):
		var selected_rect := Rect2(board_origin + Vector2(selected_spawn_cell) * cell_size, Vector2(cell_size, cell_size))
		draw_rect(selected_rect.grow(-2.0), Color("#fff3a4"), false, 4.0)
	if is_cell_valid(hover_cell):
		var hover_rect := Rect2(board_origin + Vector2(hover_cell) * cell_size, Vector2(cell_size, cell_size))
		draw_rect(hover_rect.grow(-2.0), Color(1.0, 0.93, 0.5, 0.16), true)
		draw_rect(hover_rect.grow(-2.0), Color("#ffe28a"), false, 2.0)


func _draw_tile_layers(cell: Vector2i, rect: Rect2) -> void:
	if mission.height_level_2.has(cell):
		draw_rect(rect.grow(-4.0), Color(0.36, 0.54, 0.72, 0.50), true)
		_draw_center_text(rect, "H2", Color.WHITE)
	elif mission.height_level_1.has(cell):
		draw_rect(rect.grow(-4.0), Color(0.28, 0.46, 0.62, 0.38), true)
		_draw_center_text(rect, "H1", Color("#d8ebff"))
	if mission.obstacles.has(cell):
		draw_rect(rect.grow(-8.0), Color("#202938"), true)
		_draw_center_text(rect, "■", Color("#c8d4df"), 20)
	elif mission.cover.has(cell):
		draw_rect(rect.grow(-8.0), Color(0.35, 0.72, 0.54, 0.58), true)
		_draw_center_text(rect, "C", Color.WHITE)
	elif mission.hazards.has(cell):
		draw_rect(rect.grow(-8.0), Color(0.72, 0.36, 0.84, 0.62), true)
		_draw_center_text(rect, "S", Color.WHITE)
	if mission.extraction.has(cell):
		draw_rect(rect.grow(-5.0), Color(0.32, 0.86, 0.65, 0.30), true)
		draw_rect(rect.grow(-6.0), Color("#67e0ad"), false, 3.0)
	if mission.bonus.has(cell):
		_draw_corner_text(rect, "♪", Color("#7fd7ff"))
	if mission.crown == cell:
		_draw_corner_text(rect, "♛", Color("#ffd166"), true)


func _draw_spawns() -> void:
	for i in range(mission.hero_starts.size()):
		var cell: Vector2i = mission.hero_starts[i]
		if not is_cell_valid(cell):
			continue
		var rect := Rect2(board_origin + Vector2(cell) * cell_size, Vector2(cell_size, cell_size))
		draw_circle(rect.get_center(), cell_size * 0.21, Color("#67c8ff"))
		_draw_center_text(rect, "H%d" % (i + 1), Color("#102033"), 12)
	var count: int = min(mission.enemy_ids.size(), mission.enemy_positions.size())
	for i in range(count):
		var cell: Vector2i = mission.enemy_positions[i]
		if not is_cell_valid(cell):
			continue
		var rect := Rect2(board_origin + Vector2(cell) * cell_size, Vector2(cell_size, cell_size))
		draw_circle(rect.get_center(), cell_size * 0.22, Color("#ff8a78"))
		var unit_id := String(mission.enemy_ids[i])
		var label: String = unit_id.substr(0, mini(2, unit_id.length())).to_upper()
		_draw_center_text(rect, label, Color("#311511"), 12)


func _draw_interactables() -> void:
	if mission == null:
		return
	for object_def in mission.interactables:
		if object_def == null or not is_cell_valid(object_def.cell):
			continue
		var rect := Rect2(board_origin + Vector2(object_def.cell) * cell_size, Vector2(cell_size, cell_size))
		match String(object_def.object_type):
			"door":
				draw_rect(rect.grow(-10.0), Color(1.0, 0.82, 0.35, 0.22), true)
				draw_rect(rect.grow(-11.0), Color("#ffd166"), false, 3.0)
				_draw_center_text(rect, "D", Color("#ffd166"), 13)
			"switch":
				draw_circle(rect.get_center(), cell_size * 0.15, Color("#67c8ff"))
				_draw_center_text(rect, "I", Color("#102033"), 11)
			"chest":
				draw_rect(Rect2(rect.get_center() - Vector2(cell_size * 0.17, cell_size * 0.11), Vector2(cell_size * 0.34, cell_size * 0.22)), Color("#c99245"), true)
				_draw_center_text(rect, "◆", Color("#fff0b3"), 12)


func _draw_center_text(rect: Rect2, text: String, color: Color, font_size: int = 13) -> void:
	var font := ThemeDB.fallback_font
	var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
	var pos := rect.get_center() - Vector2(text_size.x * 0.5, -text_size.y * 0.32)
	draw_string(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


func _draw_corner_text(rect: Rect2, text: String, color: Color, right: bool = false) -> void:
	var x := rect.end.x - 19.0 if right else rect.position.x + 6.0
	draw_string(ThemeDB.fallback_font, Vector2(x, rect.position.y + 18.0), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, color)
