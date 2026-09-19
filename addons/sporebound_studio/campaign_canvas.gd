@tool
class_name SporeCampaignCanvas
extends Control

signal node_selected(node_id: String)
signal node_moved(node_id: String, position: Vector2)

var campaign: Resource
var selected_node_id := ""
var hovered_node_id := ""
var dragging_node_id := ""
var drag_offset := Vector2.ZERO
var card_size := Vector2(190.0, 82.0)

const BG := Color("#172536")
const GRID := Color(0.32, 0.44, 0.57, 0.16)
const MISSION := Color("#2f6d74")
const EVENT := Color("#6b4d82")
const END := Color("#765648")
const EDGE := Color("#7ba4bf")
const SELECTED := Color("#ffd166")


func _ready() -> void:
	custom_minimum_size = Vector2(1500.0, 380.0)
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


func set_campaign(value: Resource) -> void:
	campaign = value
	queue_redraw()


func set_selected_node(node_id: String) -> void:
	selected_node_id = node_id
	queue_redraw()


func _node_position(node: Resource, index: int) -> Vector2:
	var pos: Vector2 = node.editor_position
	if pos == Vector2.ZERO:
		pos = Vector2(30.0 + float(index) * 220.0, 120.0)
	return pos


func _node_rect(node: Resource, index: int) -> Rect2:
	return Rect2(_node_position(node, index), card_size)


func _node_at(point: Vector2) -> String:
	if campaign == null:
		return ""
	for index in range(campaign.nodes.size() - 1, -1, -1):
		var node: Resource = campaign.nodes[index]
		if node != null and _node_rect(node, index).has_point(point):
			return String(node.id)
	return ""


func _gui_input(event: InputEvent) -> void:
	if campaign == null:
		return
	if event is InputEventMouseMotion:
		var hit: String = _node_at(event.position)
		if hit != hovered_node_id:
			hovered_node_id = hit
			queue_redraw()
		if not dragging_node_id.is_empty():
			var node: Resource = campaign.node_by_id(dragging_node_id) as Resource
			if node != null:
				node.editor_position = event.position - drag_offset
				node.editor_position.x = max(10.0, node.editor_position.x)
				node.editor_position.y = max(20.0, node.editor_position.y)
				node.emit_changed()
				node_moved.emit(dragging_node_id, node.editor_position)
				queue_redraw()
			accept_event()
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			var hit: String = _node_at(event.position)
			if not hit.is_empty():
				selected_node_id = hit
				dragging_node_id = hit
				var node: Resource = campaign.node_by_id(hit) as Resource
				var index: int = campaign.nodes.find(node)
				drag_offset = event.position - _node_position(node, index)
				node_selected.emit(hit)
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
	if campaign == null:
		draw_string(ThemeDB.fallback_font, Vector2(24, 40), "Aucune campagne", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color.WHITE)
		return

	# Links first, then cards.
	for index in range(campaign.nodes.size()):
		var node: Resource = campaign.nodes[index]
		if node == null:
			continue
		var from_rect: Rect2 = _node_rect(node, index)
		for target_id in node.outgoing_node_ids():
			var target: Resource = campaign.node_by_id(String(target_id)) as Resource
			if target == null:
				continue
			var target_index: int = campaign.nodes.find(target)
			var to_rect: Rect2 = _node_rect(target, target_index)
			var from_point: Vector2 = Vector2(from_rect.end.x, from_rect.get_center().y)
			var to_point: Vector2 = Vector2(to_rect.position.x, to_rect.get_center().y)
			draw_line(from_point, to_point, EDGE, 3.0)
			var direction: Vector2 = (to_point - from_point).normalized()
			if direction.length() > 0.0:
				var normal: Vector2 = Vector2(-direction.y, direction.x)
				draw_colored_polygon(PackedVector2Array([to_point, to_point - direction * 10.0 + normal * 5.0, to_point - direction * 10.0 - normal * 5.0]), EDGE)

	for index in range(campaign.nodes.size()):
		var node: Resource = campaign.nodes[index]
		if node == null:
			continue
		var rect := _node_rect(node, index)
		var node_type := String(node.node_type)
		var fill := MISSION if node_type == "mission" else (EVENT if node_type == "event" else END)
		if String(node.id) == hovered_node_id:
			fill = fill.lightened(0.12)
		draw_rect(rect, fill, true)
		var border := SELECTED if String(node.id) == selected_node_id else Color("#9ab5c8")
		draw_rect(rect, border, false, 3.0 if String(node.id) == selected_node_id else 1.5)
		var prefix := "⚔" if node_type == "mission" else ("◆" if node_type == "event" else "■")
		draw_string(ThemeDB.fallback_font, rect.position + Vector2(10, 24), "%s  %s" % [prefix, String(node.title)], HORIZONTAL_ALIGNMENT_LEFT, card_size.x - 20.0, 15, Color.WHITE)
		draw_string(ThemeDB.fallback_font, rect.position + Vector2(10, 48), String(node.id), HORIZONTAL_ALIGNMENT_LEFT, card_size.x - 20.0, 11, Color("#c7d6df"))
		var detail := String(node.mission_id) if node_type == "mission" else node_type
		draw_string(ThemeDB.fallback_font, rect.position + Vector2(10, 68), detail, HORIZONTAL_ALIGNMENT_LEFT, card_size.x - 20.0, 11, Color("#f3d8a0"))
