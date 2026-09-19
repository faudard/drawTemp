class_name SporeBattleResultOverlay
extends Control

@onready var dimmer: ColorRect = $Dimmer
@onready var panel: Panel = $Panel
@onready var title_label: Label = $Panel/Title
@onready var body_label: Label = $Panel/Body
@onready var replay_button: Button = $Panel/Replay


func _ready() -> void:
	visible = false
	if not replay_button.pressed.is_connected(_on_replay_pressed):
		replay_button.pressed.connect(_on_replay_pressed)


func present(victory: bool, survivors: int) -> void:
	title_label.text = "VICTOIRE !" if victory else "DÉFAITE"
	title_label.add_theme_color_override(
		"font_color",
		Color(1.0, 0.86, 0.38, 1.0)
		if victory
		else Color(1.0, 0.50, 0.46, 1.0)
	)
	body_label.text = (
		"Mission accomplie.\n%d membre(s) de l'escouade encore debout." % survivors
		if victory
		else "L'escouade a été mise hors combat.\nAdapte ton placement et retente la mission."
	)

	var style := panel.get_theme_stylebox("panel").duplicate() as StyleBoxFlat
	if style != null:
		style.border_color = (
			Color(1.0, 0.80, 0.30, 1.0)
			if victory
			else Color(1.0, 0.38, 0.34, 1.0)
		)
		panel.add_theme_stylebox_override("panel", style)

	visible = true
	modulate = Color(1.0, 1.0, 1.0, 0.0)
	panel.scale = Vector2(0.88, 0.88)
	panel.pivot_offset = panel.size * 0.5

	var tween := create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "modulate", Color.WHITE, 0.24)
	tween.tween_property(panel, "scale", Vector2.ONE, 0.34)


func _on_replay_pressed() -> void:
	get_tree().reload_current_scene()


func _unhandled_key_input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey):
		return
	var key_event := event as InputEventKey
	if key_event.pressed and not key_event.echo and key_event.keycode == KEY_R:
		_on_replay_pressed()
