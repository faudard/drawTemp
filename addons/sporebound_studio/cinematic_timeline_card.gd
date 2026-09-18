@tool
class_name SporeCinematicTimelineCard
extends PanelContainer

signal selected(index: int)
signal drop_requested(from_index: int, to_index: int)
signal duplicate_requested(index: int)
signal delete_requested(index: int)
signal play_from_requested(index: int)

var action_index: int = -1
var action_id: String = ""
var _action_type: String = ""
var _selected: bool = false
var _playing: bool = false

var _index_label: Label
var _type_label: Label
var _summary_label: Label
var _play_button: Button
var _duplicate_button: Button
var _delete_button: Button


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(0.0, 84.0)
	_build_ui()
	gui_input.connect(_on_gui_input)


func configure(
	index: int,
	action: Resource,
	selected_value: bool,
	playing_value: bool = false
) -> void:
	action_index = index
	_selected = selected_value
	_playing = playing_value
	_action_type = String(action.get("action_type")) if action != null else "invalid"
	action_id = String(action.get("id")) if action != null else ""

	if _index_label == null:
		_build_ui()

	_index_label.text = "%02d" % (index + 1)
	_type_label.text = _category_name(_action_type)
	_summary_label.text = _action_summary(action)
	_apply_style()


func set_selected(value: bool) -> void:
	_selected = value
	_apply_style()


func set_playing(value: bool) -> void:
	_playing = value
	_apply_style()


func _build_ui() -> void:
	if _index_label != null:
		return

	var margin: MarginContainer = MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 10)
	margin.add_theme_constant_override("margin_right", 8)
	margin.add_theme_constant_override("margin_top", 8)
	margin.add_theme_constant_override("margin_bottom", 8)
	add_child(margin)

	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	margin.add_child(row)

	_index_label = Label.new()
	_index_label.custom_minimum_size = Vector2(34.0, 0.0)
	_index_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_index_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_index_label.add_theme_font_size_override("font_size", 15)
	_index_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(_index_label)

	var content: VBoxContainer = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 3)
	row.add_child(content)

	_type_label = Label.new()
	_type_label.add_theme_font_size_override("font_size", 12)
	_type_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(_type_label)

	_summary_label = Label.new()
	_summary_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_summary_label.add_theme_font_size_override("font_size", 13)
	_summary_label.add_theme_color_override(
		"font_color",
		Color(0.88, 0.90, 0.94, 1.0)
	)
	_summary_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(_summary_label)

	var buttons: VBoxContainer = VBoxContainer.new()
	buttons.custom_minimum_size.x = 58.0
	buttons.add_theme_constant_override("separation", 3)
	row.add_child(buttons)

	_play_button = _small_button("PLAY")
	_play_button.tooltip_text = "Lire à partir de cette action"
	_play_button.pressed.connect(
		func() -> void:
			play_from_requested.emit(action_index)
	)
	buttons.add_child(_play_button)

	var button_row: HBoxContainer = HBoxContainer.new()
	button_row.add_theme_constant_override("separation", 3)
	buttons.add_child(button_row)

	_duplicate_button = _small_button("DUP")
	_duplicate_button.custom_minimum_size.x = 37.0
	_duplicate_button.tooltip_text = "Dupliquer"
	_duplicate_button.pressed.connect(
		func() -> void:
			duplicate_requested.emit(action_index)
	)
	button_row.add_child(_duplicate_button)

	_delete_button = _small_button("X")
	_delete_button.custom_minimum_size.x = 20.0
	_delete_button.tooltip_text = "Supprimer"
	_delete_button.pressed.connect(
		func() -> void:
			delete_requested.emit(action_index)
	)
	button_row.add_child(_delete_button)


func _small_button(text_value: String) -> Button:
	var button: Button = Button.new()
	button.text = text_value
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size.y = 26.0
	button.add_theme_font_size_override("font_size", 10)
	return button


func _on_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse_event: InputEventMouseButton = event as InputEventMouseButton
		if mouse_event.pressed and mouse_event.button_index == MOUSE_BUTTON_LEFT:
			selected.emit(action_index)


func _get_drag_data(_at_position: Vector2) -> Variant:
	if action_index < 0:
		return null

	var preview: PanelContainer = PanelContainer.new()
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.08, 0.11, 0.17, 0.97)
	style.border_color = _category_color(_action_type)
	style.border_width_left = 2
	style.border_width_top = 2
	style.border_width_right = 2
	style.border_width_bottom = 2
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	preview.add_theme_stylebox_override("panel", style)

	var label: Label = Label.new()
	label.text = "  %02d  %s  " % [action_index + 1, _category_name(_action_type)]
	label.add_theme_font_size_override("font_size", 13)
	preview.add_child(label)
	set_drag_preview(preview)

	return {
		"kind": "spore_cinematic_action",
		"index": action_index,
	}


func _can_drop_data(_at_position: Vector2, data: Variant) -> bool:
	if not (data is Dictionary):
		return false
	var dictionary: Dictionary = data as Dictionary
	return (
		String(dictionary.get("kind", "")) == "spore_cinematic_action"
		and int(dictionary.get("index", -1)) != action_index
	)


func _drop_data(_at_position: Vector2, data: Variant) -> void:
	if not _can_drop_data(Vector2.ZERO, data):
		return
	var dictionary: Dictionary = data as Dictionary
	drop_requested.emit(
		int(dictionary.get("index", -1)),
		action_index
	)


func _apply_style() -> void:
	if not is_inside_tree():
		return

	var color: Color = _category_color(_action_type)
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.055, 0.072, 0.105, 0.98)
	style.border_color = color
	style.border_width_left = 4 if _selected else 2
	style.border_width_top = 2 if _playing else 1
	style.border_width_right = 2 if _playing else 1
	style.border_width_bottom = 2 if _playing else 1
	style.corner_radius_top_left = 9
	style.corner_radius_top_right = 9
	style.corner_radius_bottom_left = 9
	style.corner_radius_bottom_right = 9

	if _selected:
		style.bg_color = Color(0.075, 0.105, 0.155, 1.0)
	if _playing:
		style.bg_color = color.darkened(0.68)
		style.border_color = Color(1.0, 0.84, 0.36, 1.0)
		style.border_width_left = 4
		style.border_width_top = 3
		style.border_width_right = 3
		style.border_width_bottom = 3

	add_theme_stylebox_override("panel", style)

	if _type_label != null:
		_type_label.add_theme_color_override("font_color", color)
	if _index_label != null:
		_index_label.add_theme_color_override(
			"font_color",
			Color(1.0, 0.86, 0.42, 1.0) if _playing else color.lightened(0.18)
		)


func _category_name(action_type: String) -> String:
	if action_type == "dialogue":
		return "DIALOGUE"
	if action_type.begins_with("camera_"):
		return "CAMERA"
	if action_type in ["play_music", "stop_music", "play_sfx"]:
		return "AUDIO"
	if action_type in ["fade_in", "fade_out"]:
		return "FADE"
	if action_type in ["wait", "play_cinematic"]:
		return "FLOW"
	if action_type in ["message", "set_objective_text", "set_phase"]:
		return "MISSION"
	return action_type.to_upper()


func _category_color(action_type: String) -> Color:
	if action_type == "dialogue":
		return Color(0.72, 0.52, 1.0, 1.0)
	if action_type.begins_with("camera_"):
		return Color(0.38, 0.72, 1.0, 1.0)
	if action_type in ["play_music", "stop_music", "play_sfx"]:
		return Color(0.38, 0.88, 0.62, 1.0)
	if action_type in ["fade_in", "fade_out"]:
		return Color(0.82, 0.84, 0.88, 1.0)
	if action_type in ["wait", "play_cinematic"]:
		return Color(1.0, 0.72, 0.34, 1.0)
	if action_type in ["message", "set_objective_text", "set_phase"]:
		return Color(1.0, 0.56, 0.36, 1.0)
	return Color(0.66, 0.72, 0.80, 1.0)


func _action_summary(action: Resource) -> String:
	if action == null:
		return "<action invalide>"
	if action.has_method("summary"):
		return String(action.call("summary"))
	return String(action.get("action_type"))
