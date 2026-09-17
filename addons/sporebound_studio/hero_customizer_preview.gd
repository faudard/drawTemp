@tool
class_name SporeHeroCustomizerPreview
extends Control

signal transform_delta_requested(edit_group: String, offset_delta: Vector2, scale_factor: float, rotation_delta: float)
signal edit_group_selected(edit_group: String)
signal group_reset_requested(edit_group: String)

const HERO_COMPOSITOR_SCRIPT = preload("res://scripts/visual/hero_compositor.gd")
const HANDLE_SIZE := 12.0
const ROTATION_HANDLE_DISTANCE := 30.0
const HIT_GROUP_ORDER := ["weapon", "accessory", "face", "head", "body"]

var appearance: Resource = null
var reference_appearance: Resource = null
var comparison_enabled: bool = false
var direction: String = "front"
var state: String = "idle"
var preview_zoom: float = 1.0
var selected_edit_group: String = "head"
var locked_groups: Dictionary = {}
var composite_texture: Texture2D = null
var reference_texture: Texture2D = null
var caption: Label
var selection_bounds_image: Rect2 = Rect2()
var drag_mode: String = ""


func _ready() -> void:
	custom_minimum_size = Vector2(470.0, 470.0)
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	caption = Label.new()
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	caption.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	caption.set_anchors_preset(Control.PRESET_FULL_RECT)
	caption.offset_bottom = -10.0
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(caption)
	_refresh_composite()
	queue_redraw()


func set_appearance(value: Resource) -> void:
	appearance = value
	_refresh_composite()


func set_reference_appearance(value: Resource) -> void:
	reference_appearance = value
	_refresh_reference()


func set_comparison_enabled(value: bool) -> void:
	comparison_enabled = value
	_refresh_caption()
	queue_redraw()


func set_direction(value: String) -> void:
	direction = value
	_refresh_composite()


func set_state(value: String) -> void:
	state = value if HERO_COMPOSITOR_SCRIPT.STATES.has(value) else "idle"
	_refresh_composite()


func set_zoom(value: float) -> void:
	preview_zoom = clampf(value, 0.65, 1.8)
	_refresh_selection_bounds()
	queue_redraw()


func set_selected_edit_group(value: String) -> void:
	if not HERO_COMPOSITOR_SCRIPT.EDIT_GROUPS.has(value):
		return
	selected_edit_group = value
	_refresh_selection_bounds()
	_refresh_caption()
	queue_redraw()


func set_group_locked(edit_group: String, value: bool) -> void:
	locked_groups[edit_group] = value
	_refresh_caption()
	queue_redraw()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color("#111824"), true)
	var grid_size: float = 24.0
	var columns: int = ceili(size.x / grid_size)
	var rows: int = ceili(size.y / grid_size)
	for y: int in range(rows):
		for x: int in range(columns):
			if (x + y) % 2 == 0:
				draw_rect(Rect2(float(x) * grid_size, float(y) * grid_size, grid_size, grid_size), Color(1.0, 1.0, 1.0, 0.025), true)
	var center: Vector2 = size * Vector2(0.5, 0.79)
	_draw_ellipse_shadow(center)
	if composite_texture != null:
		var display_scale: float = _display_scale()
		var display_origin: Vector2 = _display_origin(display_scale)
		var display_size: Vector2 = Vector2(HERO_COMPOSITOR_SCRIPT.FRAME_SIZE) * display_scale
		if comparison_enabled and reference_texture != null:
			var half_target_width: float = display_size.x * 0.5
			var half_source_width: float = float(HERO_COMPOSITOR_SCRIPT.FRAME_SIZE.x) * 0.5
			draw_texture_rect_region(
				reference_texture,
				Rect2(display_origin, Vector2(half_target_width, display_size.y)),
				Rect2(Vector2.ZERO, Vector2(half_source_width, float(HERO_COMPOSITOR_SCRIPT.FRAME_SIZE.y)))
			)
			draw_texture_rect_region(
				composite_texture,
				Rect2(display_origin + Vector2(half_target_width, 0.0), Vector2(half_target_width, display_size.y)),
				Rect2(Vector2(half_source_width, 0.0), Vector2(half_source_width, float(HERO_COMPOSITOR_SCRIPT.FRAME_SIZE.y)))
			)
			draw_line(
				display_origin + Vector2(half_target_width, 0.0),
				display_origin + Vector2(half_target_width, display_size.y),
				Color(1.0, 1.0, 1.0, 0.65),
				2.0
			)
		else:
			draw_texture_rect(composite_texture, Rect2(display_origin, display_size), false)
	_draw_selection_overlay()


func _draw_ellipse_shadow(center: Vector2) -> void:
	var points: PackedVector2Array = PackedVector2Array()
	for index: int in range(33):
		var angle: float = TAU * float(index) / 32.0
		points.append(center + Vector2(cos(angle) * 72.0, sin(angle) * 16.0))
	draw_colored_polygon(points, Color(0.0, 0.0, 0.0, 0.28))


func _draw_selection_overlay() -> void:
	var rect: Rect2 = _selection_rect_screen()
	if rect.size.x <= 0.0 or rect.size.y <= 0.0:
		return
	var locked: bool = _is_selected_locked()
	var outline: Color = Color("#ef767a") if locked else Color("#70d6ff")
	draw_rect(rect, outline, false, 2.0)
	for handle: Rect2 in _resize_handle_rects(rect):
		draw_rect(handle, outline, true)
	var rotation_rect: Rect2 = _rotation_handle_rect(rect)
	var rotation_center: Vector2 = rotation_rect.get_center()
	draw_line(Vector2(rect.get_center().x, rect.position.y), rotation_center, outline, 1.5)
	draw_circle(rotation_center, HANDLE_SIZE * 0.45, outline)
	var anchor_screen: Vector2 = _image_to_screen(HERO_COMPOSITOR_SCRIPT.edit_group_anchor(selected_edit_group))
	draw_line(anchor_screen - Vector2(5.0, 0.0), anchor_screen + Vector2(5.0, 0.0), outline, 1.0)
	draw_line(anchor_screen - Vector2(0.0, 5.0), anchor_screen + Vector2(0.0, 5.0), outline, 1.0)


func _refresh_composite() -> void:
	if not is_inside_tree():
		return
	composite_texture = null
	if appearance != null:
		var image: Image = HERO_COMPOSITOR_SCRIPT.compose_frame(appearance, direction, state)
		composite_texture = ImageTexture.create_from_image(image)
	_refresh_reference()
	_refresh_selection_bounds()
	_refresh_caption()
	queue_redraw()


func _refresh_reference() -> void:
	reference_texture = null
	if not is_inside_tree():
		return
	if reference_appearance != null:
		var image: Image = HERO_COMPOSITOR_SCRIPT.compose_frame(reference_appearance, direction, state)
		reference_texture = ImageTexture.create_from_image(image)
	queue_redraw()


func _refresh_selection_bounds() -> void:
	selection_bounds_image = Rect2()
	if appearance == null or selected_edit_group.is_empty():
		return
	selection_bounds_image = HERO_COMPOSITOR_SCRIPT.edit_group_bounds(appearance, selected_edit_group, direction, state)


func _refresh_caption() -> void:
	if caption == null:
		return
	var hero_name: String = "Aucun héros"
	if appearance != null:
		hero_name = String(appearance.get("display_name"))
	var edit_state: String = "VERROUILLÉ" if _is_selected_locked() else "édition directe"
	var compare_state: String = " • AVANT/APRÈS" if comparison_enabled and reference_texture != null else ""
	caption.text = "%s  •  %s / %s  •  %s [%s]%s" % [hero_name, direction.to_upper(), state.to_upper(), _group_label(selected_edit_group), edit_state, compare_state]


func _gui_input(event: InputEvent) -> void:
	if appearance == null:
		return
	if event is InputEventMouseButton:
		var button_event: InputEventMouseButton = event as InputEventMouseButton
		_handle_mouse_button(button_event)
		return
	if event is InputEventMouseMotion:
		var motion_event: InputEventMouseMotion = event as InputEventMouseMotion
		_handle_mouse_motion(motion_event)


func _handle_mouse_button(event: InputEventMouseButton) -> void:
	if event.button_index == MOUSE_BUTTON_LEFT:
		if not event.pressed:
			drag_mode = ""
			accept_event()
			return
		var current_rect: Rect2 = _selection_rect_screen()
		if not _is_selected_locked() and _rotation_handle_rect(current_rect).has_point(event.position):
			drag_mode = "rotate"
			accept_event()
			return
		if not _is_selected_locked() and _point_on_resize_handle(event.position, current_rect):
			drag_mode = "scale"
			accept_event()
			return
		var hit_group: String = _find_group_at_position(event.position)
		if not hit_group.is_empty() and hit_group != selected_edit_group:
			selected_edit_group = hit_group
			_refresh_selection_bounds()
			_refresh_caption()
			edit_group_selected.emit(hit_group)
			queue_redraw()
		if _is_selected_locked():
			accept_event()
			return
		var rect: Rect2 = _selection_rect_screen()
		drag_mode = "move" if rect.has_point(event.position) else ""
		accept_event()
		return
	if event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
		if not selected_edit_group.is_empty() and not _is_selected_locked():
			group_reset_requested.emit(selected_edit_group)
		accept_event()
		return
	if not event.pressed or _is_selected_locked():
		return
	if event.button_index == MOUSE_BUTTON_WHEEL_UP or event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
		var direction_sign: float = 1.0 if event.button_index == MOUSE_BUTTON_WHEEL_UP else -1.0
		if event.ctrl_pressed:
			transform_delta_requested.emit(selected_edit_group, Vector2.ZERO, 1.0, direction_sign)
		else:
			var factor: float = 1.03 if direction_sign > 0.0 else 0.97
			transform_delta_requested.emit(selected_edit_group, Vector2.ZERO, factor, 0.0)
		accept_event()


func _handle_mouse_motion(event: InputEventMouseMotion) -> void:
	if drag_mode.is_empty() or selected_edit_group.is_empty() or _is_selected_locked():
		return
	var scale: float = _display_scale()
	if scale <= 0.001:
		return
	if drag_mode == "move":
		var offset_delta: Vector2 = event.relative / scale
		transform_delta_requested.emit(selected_edit_group, offset_delta, 1.0, 0.0)
		accept_event()
		return
	var rect: Rect2 = _selection_rect_screen()
	var center: Vector2 = rect.get_center()
	var previous_position: Vector2 = event.position - event.relative
	if drag_mode == "scale":
		var old_distance: float = maxf(1.0, previous_position.distance_to(center))
		var new_distance: float = maxf(1.0, event.position.distance_to(center))
		var factor: float = clampf(new_distance / old_distance, 0.85, 1.15)
		transform_delta_requested.emit(selected_edit_group, Vector2.ZERO, factor, 0.0)
		accept_event()
	elif drag_mode == "rotate":
		var old_angle: float = (previous_position - center).angle()
		var new_angle: float = (event.position - center).angle()
		var delta_radians: float = wrapf(new_angle - old_angle, -PI, PI)
		var delta_degrees: float = clampf(rad_to_deg(delta_radians), -5.0, 5.0)
		transform_delta_requested.emit(selected_edit_group, Vector2.ZERO, 1.0, delta_degrees)
		accept_event()


func _find_group_at_position(screen_position: Vector2) -> String:
	for edit_group: String in HIT_GROUP_ORDER:
		var bounds: Rect2 = HERO_COMPOSITOR_SCRIPT.edit_group_bounds(appearance, edit_group, direction, state)
		if bounds.size.x <= 0.0 or bounds.size.y <= 0.0:
			continue
		if _image_rect_to_screen(bounds).has_point(screen_position):
			return edit_group
	return ""


func _point_on_resize_handle(position: Vector2, rect: Rect2) -> bool:
	for handle: Rect2 in _resize_handle_rects(rect):
		if handle.has_point(position):
			return true
	return false


func _resize_handle_rects(rect: Rect2) -> Array[Rect2]:
	var half: float = HANDLE_SIZE * 0.5
	return [
		Rect2(rect.position - Vector2(half, half), Vector2(HANDLE_SIZE, HANDLE_SIZE)),
		Rect2(Vector2(rect.end.x - half, rect.position.y - half), Vector2(HANDLE_SIZE, HANDLE_SIZE)),
		Rect2(Vector2(rect.position.x - half, rect.end.y - half), Vector2(HANDLE_SIZE, HANDLE_SIZE)),
		Rect2(rect.end - Vector2(half, half), Vector2(HANDLE_SIZE, HANDLE_SIZE)),
	]


func _rotation_handle_rect(rect: Rect2) -> Rect2:
	var center: Vector2 = Vector2(rect.get_center().x, rect.position.y - ROTATION_HANDLE_DISTANCE)
	return Rect2(center - Vector2(HANDLE_SIZE * 0.5, HANDLE_SIZE * 0.5), Vector2(HANDLE_SIZE, HANDLE_SIZE))


func _selection_rect_screen() -> Rect2:
	if selection_bounds_image.size.x <= 0.0 or selection_bounds_image.size.y <= 0.0:
		return Rect2()
	return _image_rect_to_screen(selection_bounds_image)


func _image_rect_to_screen(image_rect: Rect2) -> Rect2:
	var scale: float = _display_scale()
	var origin: Vector2 = _display_origin(scale)
	return Rect2(origin + image_rect.position * scale, image_rect.size * scale)


func _image_to_screen(image_position: Vector2) -> Vector2:
	var scale: float = _display_scale()
	return _display_origin(scale) + image_position * scale


func _display_scale() -> float:
	if size.x <= 0.0 or size.y <= 0.0:
		return 1.0
	var base: float = minf(size.x / float(HERO_COMPOSITOR_SCRIPT.FRAME_SIZE.x), size.y / float(HERO_COMPOSITOR_SCRIPT.FRAME_SIZE.y))
	return base * preview_zoom


func _display_origin(scale: float) -> Vector2:
	var displayed_size: Vector2 = Vector2(HERO_COMPOSITOR_SCRIPT.FRAME_SIZE) * scale
	return (size - displayed_size) * 0.5


func _is_selected_locked() -> bool:
	return bool(locked_groups.get(selected_edit_group, false))


func _group_label(edit_group: String) -> String:
	match edit_group:
		"body": return "CORPS"
		"head": return "TÊTE"
		"face": return "VISAGE"
		"accessory": return "ACCESSOIRE"
		"weapon": return "ARME"
		_: return edit_group.to_upper()
