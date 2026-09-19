class_name SporeTurnTransitionBanner
extends Panel

@onready var label: Label = $Label


func present(actor_name: String, team: String) -> void:
	var is_player: bool = team == "player"
	label.text = ("À TOI  •  %s" if is_player else "ENNEMI  •  %s") % actor_name
	label.add_theme_color_override(
		"font_color",
		Color(0.72, 0.91, 1.0, 1.0)
		if is_player
		else Color(1.0, 0.70, 0.64, 1.0)
	)

	var style := get_theme_stylebox("panel").duplicate() as StyleBoxFlat
	if style != null:
		style.border_color = (
			Color(0.36, 0.82, 1.0, 0.95)
			if is_player
			else Color(1.0, 0.42, 0.38, 0.95)
		)
		add_theme_stylebox_override("panel", style)

	modulate = Color(1.0, 1.0, 1.0, 0.0)
	var shown_position: Vector2 = position
	position = shown_position - Vector2(0.0, 12.0)

	var tween := create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "position", shown_position, 0.22)
	tween.tween_property(self, "modulate", Color.WHITE, 0.18)
	tween.set_parallel(false)
	tween.tween_interval(0.48)
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_SINE)
	tween.tween_property(self, "position", shown_position + Vector2(0.0, -8.0), 0.20)
	tween.tween_property(self, "modulate", Color(1.0, 1.0, 1.0, 0.0), 0.20)
	tween.set_parallel(false)
	tween.tween_callback(Callable(self, "queue_free"))
