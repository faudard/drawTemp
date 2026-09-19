class_name SporeMissionEventBanner
extends Panel

@onready var body_label: Label = $Body


func present(message: String) -> void:
	body_label.text = message
	modulate = Color(1.0, 1.0, 1.0, 0.0)

	var shown_position: Vector2 = position + Vector2(0.0, 10.0)
	var tween := create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "modulate", Color.WHITE, 0.18)
	tween.tween_property(self, "position", shown_position, 0.22)
	tween.set_parallel(false)
	tween.tween_interval(1.05)
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tween.tween_property(self, "modulate", Color(1.0, 1.0, 1.0, 0.0), 0.22)
	tween.tween_property(self, "position", shown_position - Vector2(0.0, 8.0), 0.22)
	tween.set_parallel(false)
	tween.tween_callback(Callable(self, "queue_free"))
