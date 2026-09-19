class_name SporeCombatFloatingText3D
extends Node3D

@onready var label: Label3D = $Label


func present(text_value: String, color: Color, kind: String = "default") -> void:
	label.text = text_value
	label.modulate = color
	label.outline_modulate = Color(0.02, 0.02, 0.025, 1.0)

	match kind:
		"damage":
			label.font_size = 30
			label.outline_size = 7
		"heal":
			label.font_size = 27
			label.outline_size = 6
		"skill":
			label.font_size = 22
			label.outline_size = 6
		"objective":
			label.font_size = 22
			label.outline_size = 6
		"status":
			label.font_size = 21
			label.outline_size = 6
		_:
			label.font_size = 24
			label.outline_size = 6

	scale = Vector3(0.82, 0.82, 0.82)
	label.modulate = Color(color.r, color.g, color.b, 0.0)

	var target_position: Vector3 = position + Vector3(0.0, 0.46, 0.0)
	var tween := create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(label, "modulate", color, 0.08)
	tween.tween_property(self, "scale", Vector3.ONE, 0.14)
	tween.tween_property(self, "position", target_position, 0.52)
	tween.set_parallel(false)
	tween.tween_interval(0.14)
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tween.tween_property(label, "modulate", Color(color.r, color.g, color.b, 0.0), 0.20)
	tween.tween_property(self, "position", target_position + Vector3(0.0, 0.18, 0.0), 0.20)
	tween.tween_property(self, "scale", Vector3(0.92, 0.92, 0.92), 0.20)
	tween.set_parallel(false)
	tween.tween_callback(Callable(self, "queue_free"))
