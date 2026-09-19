class_name SporeComicActionCutin
extends CanvasLayer

## Short non-blocking manga cut-in.
## Structure and visual styling live in comic_action_cutin.tscn.

@onready var _root: Control = $ComicActionCutinRoot
@onready var _dimmer: ColorRect = $ComicActionCutinRoot/Dimmer
@onready var _speed_lines: Control = $ComicActionCutinRoot/SpeedLines
@onready var _panel: Panel = $ComicActionCutinRoot/CutinPanel
@onready var _portrait: TextureRect = $ComicActionCutinRoot/CutinPanel/Portrait
@onready var _name_label: Label = $ComicActionCutinRoot/CutinPanel/ActorName
@onready var _action_label: Label = $ComicActionCutinRoot/CutinPanel/ActionName
@onready var _category_label: Label = $ComicActionCutinRoot/CutinPanel/Category

var _tween: Tween


func _ready() -> void:
	_root.visible = false


func show_action(
	portrait_texture: Texture2D,
	actor_name: String,
	action_name: String,
	category: String,
	team: String = "player",
	side: String = "left"
) -> void:
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

	var viewport_size := get_viewport().get_visible_rect().size
	var panel_size := Vector2(
		clampf(viewport_size.x * 0.28, 300.0, 440.0),
		clampf(viewport_size.y * 0.30, 210.0, 285.0)
	)
	_panel.size = panel_size
	_panel.pivot_offset = panel_size * 0.5
	_panel.position = Vector2(
		viewport_size.x - panel_size.x - 20.0 if on_right else 20.0,
		viewport_size.y * 0.48 - panel_size.y * 0.5
	)
	_panel.rotation = deg_to_rad(2.0 if on_right else -2.0)

	_layout_panel(panel_size, on_right)
	_build_speed_lines(accent, on_right)

	_root.visible = true
	var target_pos := _panel.position
	var slide := Vector2(54.0 if on_right else -54.0, 8.0)
	_panel.position = target_pos + slide
	_panel.scale = Vector2(0.90, 0.90)
	_panel.modulate = Color(1.0, 1.0, 1.0, 0.0)
	_dimmer.color = Color(0.0, 0.0, 0.0, 0.0)
	_speed_lines.modulate = Color(1.0, 1.0, 1.0, 0.0)

	_tween = create_tween()
	_tween.set_parallel(true)
	_tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_tween.tween_property(_panel, "position", target_pos, 0.12)
	_tween.tween_property(_panel, "scale", Vector2.ONE, 0.14)
	_tween.tween_property(_panel, "modulate", Color.WHITE, 0.09)
	_tween.tween_property(_dimmer, "color", Color(0.0, 0.0, 0.0, 0.10), 0.07)
	_tween.tween_property(_speed_lines, "modulate", Color.WHITE, 0.07)
	_tween.set_parallel(false)
	_tween.tween_interval(0.30)
	_tween.set_parallel(true)
	_tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	_tween.tween_property(_panel, "position", target_pos - slide * 0.24, 0.14)
	_tween.tween_property(_panel, "modulate", Color(1.0, 1.0, 1.0, 0.0), 0.14)
	_tween.tween_property(_dimmer, "color", Color(0.0, 0.0, 0.0, 0.0), 0.14)
	_tween.tween_property(_speed_lines, "modulate", Color(1.0, 1.0, 1.0, 0.0), 0.12)
	_tween.set_parallel(false)
	_tween.tween_callback(_hide)


func _layout_panel(panel_size: Vector2, on_right: bool) -> void:
	var portrait_width := panel_size.x * 0.44
	if on_right:
		_portrait.position = Vector2(panel_size.x - portrait_width - 10.0, 10.0)
		_portrait.size = Vector2(portrait_width, panel_size.y - 20.0)
		_name_label.position = Vector2(16.0, 22.0)
		_name_label.size = Vector2(panel_size.x - portrait_width - 28.0, 28.0)
		_action_label.position = Vector2(16.0, 54.0)
		_action_label.size = Vector2(panel_size.x - portrait_width - 30.0, panel_size.y - 112.0)
		_category_label.position = Vector2(16.0, panel_size.y - 42.0)
		_category_label.size = Vector2(panel_size.x - portrait_width - 30.0, 24.0)
	else:
		_portrait.position = Vector2(10.0, 10.0)
		_portrait.size = Vector2(portrait_width, panel_size.y - 20.0)
		_name_label.position = Vector2(portrait_width + 20.0, 22.0)
		_name_label.size = Vector2(panel_size.x - portrait_width - 30.0, 28.0)
		_action_label.position = Vector2(portrait_width + 20.0, 54.0)
		_action_label.size = Vector2(panel_size.x - portrait_width - 32.0, panel_size.y - 112.0)
		_category_label.position = Vector2(portrait_width + 20.0, panel_size.y - 42.0)
		_category_label.size = Vector2(panel_size.x - portrait_width - 32.0, 24.0)


func _build_speed_lines(accent: Color, on_right: bool) -> void:
	for child: Node in _speed_lines.get_children():
		child.queue_free()

	var viewport_size := get_viewport().get_visible_rect().size
	for index: int in range(8):
		var line := ColorRect.new()
		line.mouse_filter = Control.MOUSE_FILTER_IGNORE
		line.color = Color(accent.r, accent.g, accent.b, 0.10 if index % 2 == 0 else 0.06)
		line.size = Vector2(viewport_size.x * (0.12 + 0.012 * float(index % 3)), 2.0)
		line.position = Vector2(
			viewport_size.x * (0.58 if on_right else 0.28),
			viewport_size.y * (0.24 + 0.065 * float(index))
		)
		line.rotation = deg_to_rad(-8.0 if on_right else 8.0)
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
	_root.visible = false
