class_name SporeComicActionCutin
extends CanvasLayer

## Short non-blocking manga cut-in used for attacks, skills and reactions.
## It deliberately does not capture mouse/keyboard input.

var _root: Control
var _dimmer: ColorRect
var _panel: Panel
var _portrait: TextureRect
var _name_label: Label
var _action_label: Label
var _category_label: Label
var _speed_lines: Control
var _tween: Tween


func _ready() -> void:
	layer = 26
	_build_ui()


func show_action(
	portrait_texture: Texture2D,
	actor_name: String,
	action_name: String,
	category: String,
	team: String = "player",
	side: String = "left"
) -> void:
	if _root == null:
		_build_ui()

	if _tween != null and _tween.is_valid():
		_tween.kill()

	var accent := _accent_for(category, team)
	var on_right := side == "right"

	_portrait.texture = portrait_texture
	_name_label.text = actor_name.to_upper()
	_action_label.text = action_name.to_upper()
	_category_label.text = category.to_upper()

	_name_label.add_theme_color_override("font_color", accent)
	_category_label.add_theme_color_override("font_color", accent)

	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.012, 0.012, 0.015, 0.985)
	style.border_color = accent
	style.border_width_left = 5
	style.border_width_top = 5
	style.border_width_right = 5
	style.border_width_bottom = 5
	style.corner_radius_top_left = 2
	style.corner_radius_top_right = 2
	style.corner_radius_bottom_left = 2
	style.corner_radius_bottom_right = 2
	style.shadow_color = Color(0.0, 0.0, 0.0, 0.82)
	style.shadow_size = 16
	_panel.add_theme_stylebox_override("panel", style)

	var viewport_size := get_viewport().get_visible_rect().size
	var panel_size := Vector2(
		clampf(viewport_size.x * 0.31, 330.0, 520.0),
		clampf(viewport_size.y * 0.34, 230.0, 330.0)
	)
	_panel.size = panel_size
	_panel.pivot_offset = panel_size * 0.5
	_panel.position = Vector2(
		viewport_size.x - panel_size.x - 24.0 if on_right else 24.0,
		viewport_size.y * 0.47 - panel_size.y * 0.5
	)
	_panel.rotation = deg_to_rad(3.0 if on_right else -3.0)

	_layout_panel(panel_size, on_right)
	_build_speed_lines(accent, on_right)

	_root.visible = true
	_panel.visible = true
	_dimmer.visible = true
	_speed_lines.visible = true

	var target_pos := _panel.position
	var slide := Vector2(72.0 if on_right else -72.0, 12.0)
	_panel.position = target_pos + slide
	_panel.scale = Vector2(0.86, 0.86)
	_panel.modulate = Color(1.0, 1.0, 1.0, 0.0)
	_dimmer.color = Color(0.0, 0.0, 0.0, 0.0)
	_speed_lines.modulate = Color(1.0, 1.0, 1.0, 0.0)

	_tween = create_tween()
	_tween.set_parallel(true)
	_tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_tween.tween_property(_panel, "position", target_pos, 0.14)
	_tween.tween_property(_panel, "scale", Vector2.ONE, 0.16)
	_tween.tween_property(_panel, "modulate", Color.WHITE, 0.10)
	_tween.tween_property(_dimmer, "color", Color(0.0, 0.0, 0.0, 0.17), 0.08)
	_tween.tween_property(_speed_lines, "modulate", Color.WHITE, 0.08)
	_tween.set_parallel(false)
	_tween.tween_interval(0.34)
	_tween.set_parallel(true)
	_tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	_tween.tween_property(_panel, "position", target_pos - slide * 0.30, 0.16)
	_tween.tween_property(_panel, "modulate", Color(1.0, 1.0, 1.0, 0.0), 0.16)
	_tween.tween_property(_dimmer, "color", Color(0.0, 0.0, 0.0, 0.0), 0.16)
	_tween.tween_property(_speed_lines, "modulate", Color(1.0, 1.0, 1.0, 0.0), 0.14)
	_tween.set_parallel(false)
	_tween.tween_callback(_hide)


func _build_ui() -> void:
	_root = Control.new()
	_root.name = "ComicActionCutinRoot"
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_root)

	_dimmer = ColorRect.new()
	_dimmer.name = "Dimmer"
	_dimmer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_dimmer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(_dimmer)

	_speed_lines = Control.new()
	_speed_lines.name = "SpeedLines"
	_speed_lines.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_speed_lines.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(_speed_lines)

	_panel = Panel.new()
	_panel.name = "CutinPanel"
	_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(_panel)

	_portrait = TextureRect.new()
	_portrait.name = "Portrait"
	_portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.add_child(_portrait)

	_name_label = Label.new()
	_name_label.name = "ActorName"
	_name_label.add_theme_font_size_override("font_size", 22)
	_name_label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 1.0))
	_name_label.add_theme_constant_override("outline_size", 7)
	_name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.add_child(_name_label)

	_action_label = Label.new()
	_action_label.name = "ActionName"
	_action_label.add_theme_font_size_override("font_size", 34)
	_action_label.add_theme_color_override("font_color", Color(0.97, 0.96, 0.91, 1.0))
	_action_label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 1.0))
	_action_label.add_theme_constant_override("outline_size", 9)
	_action_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_action_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.add_child(_action_label)

	_category_label = Label.new()
	_category_label.name = "Category"
	_category_label.add_theme_font_size_override("font_size", 14)
	_category_label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 1.0))
	_category_label.add_theme_constant_override("outline_size", 5)
	_category_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.add_child(_category_label)


func _layout_panel(panel_size: Vector2, on_right: bool) -> void:
	var portrait_width := panel_size.x * 0.46
	if on_right:
		_portrait.position = Vector2(panel_size.x - portrait_width - 12.0, 12.0)
		_portrait.size = Vector2(portrait_width, panel_size.y - 24.0)
		_name_label.position = Vector2(18.0, 28.0)
		_name_label.size = Vector2(panel_size.x - portrait_width - 30.0, 34.0)
		_action_label.position = Vector2(18.0, 68.0)
		_action_label.size = Vector2(panel_size.x - portrait_width - 32.0, 116.0)
		_category_label.position = Vector2(18.0, panel_size.y - 54.0)
		_category_label.size = Vector2(panel_size.x - portrait_width - 32.0, 28.0)
	else:
		_portrait.position = Vector2(12.0, 12.0)
		_portrait.size = Vector2(portrait_width, panel_size.y - 24.0)
		_name_label.position = Vector2(portrait_width + 24.0, 28.0)
		_name_label.size = Vector2(panel_size.x - portrait_width - 36.0, 34.0)
		_action_label.position = Vector2(portrait_width + 24.0, 68.0)
		_action_label.size = Vector2(panel_size.x - portrait_width - 38.0, 116.0)
		_category_label.position = Vector2(portrait_width + 24.0, panel_size.y - 54.0)
		_category_label.size = Vector2(panel_size.x - portrait_width - 38.0, 28.0)


func _build_speed_lines(accent: Color, on_right: bool) -> void:
	for child: Node in _speed_lines.get_children():
		child.queue_free()

	var viewport_size := get_viewport().get_visible_rect().size
	for index: int in range(12):
		var line := ColorRect.new()
		line.mouse_filter = Control.MOUSE_FILTER_IGNORE
		line.color = Color(
			accent.r,
			accent.g,
			accent.b,
			0.16 if index % 3 == 0 else 0.10
		)
		line.size = Vector2(
			viewport_size.x * (0.17 + 0.018 * float(index % 4)),
			2.0 + float(index % 3)
		)
		var y := viewport_size.y * (0.18 + 0.052 * float(index))
		line.position = Vector2(
			viewport_size.x * (0.50 if on_right else 0.34),
			y
		)
		line.rotation = deg_to_rad(
			-10.0 - float(index % 4) * 2.4
			if on_right
			else 10.0 + float(index % 4) * 2.4
		)
		_speed_lines.add_child(line)


func _accent_for(category: String, team: String) -> Color:
	if team == "enemy":
		return Color(0.96, 0.20, 0.16, 1.0)
	match category:
		"ATTAQUE":
			return Color(0.96, 0.22, 0.16, 1.0)
		"COMPÉTENCE", "PRÉPARATION":
			return Color(0.58, 0.36, 0.95, 1.0)
		"RÉACTION":
			return Color(1.0, 0.80, 0.16, 1.0)
	return Color(0.32, 0.78, 1.0, 1.0)


func _hide() -> void:
	if _root != null:
		_root.visible = false
