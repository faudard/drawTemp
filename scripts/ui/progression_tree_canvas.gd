@tool
class_name SporeProgressionTreeCanvas
extends Control

signal node_selected(node_id: String)
signal node_moved(node_id: String, position: Vector2)

var job: SporeJobDefinition
var selected_node_id := ""
var hovered_node_id := ""
var dragging_node_id := ""
var drag_offset := Vector2.ZERO
var editable_positions := false
var runtime_level := 1
var runtime_purchased: PackedStringArray = PackedStringArray()
var runtime_points_available := 0
var show_runtime_state := false
var card_size := Vector2(188.0, 86.0)

const BG := Color("#172536")
const GRID := Color(0.32, 0.44, 0.57, 0.16)
const EDGE := Color("#7895aa")
const SELECTED := Color("#ffd166")
const SKILL := Color("#416f92")
const STAT := Color("#40775d")
const PASSIVE := Color("#745b8c")
const LOCKED := Color("#394858")
const AVAILABLE := Color("#3f846e")
const PURCHASED := Color("#94722f")
const AUTO := Color("#476f91")
const EXCLUSIVE := Color("#6f4049")


func _ready() -> void:
	custom_minimum_size = Vector2(1250.0, 520.0)
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


func set_job(value: SporeJobDefinition) -> void:
	job = value
	selected_node_id = ""
	queue_redraw()


func set_selected_node(node_id: String) -> void:
	selected_node_id = node_id
	queue_redraw()


func set_runtime_state(level: int, purchased: PackedStringArray, points_available: int) -> void:
	runtime_level = maxi(1, level)
	runtime_purchased = purchased.duplicate()
	runtime_points_available = maxi(0, points_available)
	show_runtime_state = true
	queue_redraw()


func clear_runtime_state() -> void:
	show_runtime_state = false
	queue_redraw()


func _nodes() -> Array[SporeProgressionNodeDefinition]:
	if job == null:
		return []
	return job.progression_nodes


func _node_position(node: SporeProgressionNodeDefinition, index: int) -> Vector2:
	var pos: Vector2 = node.editor_position
	if pos == Vector2.ZERO:
		pos = Vector2(30.0 + float(index % 5) * 220.0, 60.0 + float(index / 5) * 120.0)
	return pos


func _node_rect(node: SporeProgressionNodeDefinition, index: int) -> Rect2:
	return Rect2(_node_position(node, index), card_size)


func _node_at(point: Vector2) -> String:
	var nodes: Array[SporeProgressionNodeDefinition] = _nodes()
	for index in range(nodes.size() - 1, -1, -1):
		var node: SporeProgressionNodeDefinition = nodes[index]
		if node != null and _node_rect(node, index).has_point(point):
			return String(node.id)
	return ""


func _node_by_id(node_id: String) -> SporeProgressionNodeDefinition:
	if job == null:
		return null
	for node: SporeProgressionNodeDefinition in job.progression_nodes:
		if node != null and String(node.id) == node_id:
			return node
	return null


func _effective_node_ids() -> PackedStringArray:
	var result := PackedStringArray()
	if job == null:
		return result
	for node: SporeProgressionNodeDefinition in job.progression_nodes:
		if node != null and bool(node.auto_unlock) and int(node.required_level) <= runtime_level:
			result.append(String(node.id))
	for node_id in runtime_purchased:
		if not result.has(String(node_id)):
			result.append(String(node_id))
	return result


func _runtime_state_for(node: SporeProgressionNodeDefinition) -> String:
	if not show_runtime_state:
		return "editor"
	var node_id := String(node.id)
	if bool(node.auto_unlock) and int(node.required_level) <= runtime_level:
		return "auto"
	if runtime_purchased.has(node_id):
		return "purchased"
	if int(node.required_level) > runtime_level:
		return "locked"
	var effective := _effective_node_ids()
	for required_id in node.required_node_ids:
		if not effective.has(String(required_id)):
			return "locked"
	var group := String(node.exclusive_group)
	if not group.is_empty():
		for other_id in runtime_purchased:
			var other: SporeProgressionNodeDefinition = _node_by_id(String(other_id))
			if other != null and String(other.id) != node_id and String(other.exclusive_group) == group:
				return "exclusive"
	if int(node.cost) > runtime_points_available:
		return "locked"
	return "available"


func _fill_color(node: SporeProgressionNodeDefinition) -> Color:
	var state := _runtime_state_for(node)
	match state:
		"auto":
			return AUTO
		"purchased":
			return PURCHASED
		"available":
			return AVAILABLE
		"locked":
			return LOCKED
		"exclusive":
			return EXCLUSIVE
	match String(node.node_type):
		"skill":
			return SKILL
		"passive":
			return PASSIVE
		_:
			return STAT


func _gui_input(event: InputEvent) -> void:
	if job == null:
		return
	if event is InputEventMouseMotion:
		var hit := _node_at(event.position)
		if hit != hovered_node_id:
			hovered_node_id = hit
			queue_redraw()
		if editable_positions and not dragging_node_id.is_empty():
			var node: SporeProgressionNodeDefinition = _node_by_id(dragging_node_id)
			if node != null:
				node.editor_position = event.position - drag_offset
				node.editor_position.x = maxf(10.0, node.editor_position.x)
				node.editor_position.y = maxf(20.0, node.editor_position.y)
				node.emit_changed()
				node_moved.emit(dragging_node_id, node.editor_position)
				queue_redraw()
			accept_event()
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			var hit := _node_at(event.position)
			if not hit.is_empty():
				selected_node_id = hit
				node_selected.emit(hit)
				if editable_positions:
					dragging_node_id = hit
					var node: SporeProgressionNodeDefinition = _node_by_id(hit)
					var index := _nodes().find(node)
					drag_offset = event.position - _node_position(node, index)
				queue_redraw()
				accept_event()
		else:
			dragging_node_id = ""


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), BG, true)
	for x in range(0, int(size.x), 40):
		draw_line(Vector2(x, 0), Vector2(x, size.y), GRID, 1.0)
	for y in range(0, int(size.y), 40):
		draw_line(Vector2(0, y), Vector2(size.x, y), GRID, 1.0)
	if job == null:
		draw_string(ThemeDB.fallback_font, Vector2(24, 40), "Aucun job", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color.WHITE)
		return
	var nodes: Array[SporeProgressionNodeDefinition] = _nodes()
	# Dependencies first.
	for index in range(nodes.size()):
		var node: SporeProgressionNodeDefinition = nodes[index]
		if node == null:
			continue
		var to_rect := _node_rect(node, index)
		for required_id in node.required_node_ids:
			var parent: SporeProgressionNodeDefinition = _node_by_id(String(required_id))
			if parent == null:
				continue
			var parent_index := nodes.find(parent)
			var from_rect := _node_rect(parent, parent_index)
			var from_point := Vector2(from_rect.end.x, from_rect.get_center().y)
			var to_point := Vector2(to_rect.position.x, to_rect.get_center().y)
			draw_line(from_point, to_point, EDGE, 3.0)
			var direction := (to_point - from_point).normalized()
			if direction.length() > 0.0:
				var normal := Vector2(-direction.y, direction.x)
				draw_colored_polygon(PackedVector2Array([to_point, to_point - direction * 10.0 + normal * 5.0, to_point - direction * 10.0 - normal * 5.0]), EDGE)
	for index in range(nodes.size()):
		var node: SporeProgressionNodeDefinition = nodes[index]
		if node == null:
			continue
		var rect := _node_rect(node, index)
		var fill := _fill_color(node)
		if String(node.id) == hovered_node_id:
			fill = fill.lightened(0.10)
		draw_rect(rect, fill, true)
		var border := SELECTED if String(node.id) == selected_node_id else Color("#9ab5c8")
		draw_rect(rect, border, false, 3.0 if String(node.id) == selected_node_id else 1.4)
		var icon := "◆" if String(node.node_type) == "skill" else ("●" if String(node.node_type) == "stat" else "✦")
		draw_string(ThemeDB.fallback_font, rect.position + Vector2(10, 22), "%s %s" % [icon, String(node.display_name)], HORIZONTAL_ALIGNMENT_LEFT, card_size.x - 20.0, 14, Color.WHITE)
		draw_string(ThemeDB.fallback_font, rect.position + Vector2(10, 44), String(node.id), HORIZONTAL_ALIGNMENT_LEFT, card_size.x - 20.0, 10, Color("#d5e0e8"))
		var detail := "AUTO • niv.%d" % int(node.required_level) if bool(node.auto_unlock) else "%d pt • niv.%d" % [int(node.cost), int(node.required_level)]
		if not String(node.exclusive_group).is_empty():
			detail += " • [%s]" % String(node.exclusive_group)
		draw_string(ThemeDB.fallback_font, rect.position + Vector2(10, 66), detail, HORIZONTAL_ALIGNMENT_LEFT, card_size.x - 20.0, 10, Color("#ffe3a0"))
		if show_runtime_state:
			draw_string(ThemeDB.fallback_font, rect.position + Vector2(10, 81), _runtime_state_for(node).to_upper(), HORIZONTAL_ALIGNMENT_LEFT, card_size.x - 20.0, 9, Color("#c6f3d9"))
