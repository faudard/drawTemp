class_name SporeTacticalMarker3D
extends Node3D

@onready var ring: MeshInstance3D = $Ring
@onready var label: Label3D = $Label


func configure(
	text_value: String,
	color: Color,
	radius_world: float,
	label_height: float = 0.72,
	show_ring: bool = true,
	show_label: bool = true,
	font_size: int = 18,
	alpha: float = 0.34
) -> void:
	label.text = text_value
	label.visible = show_label and not text_value.is_empty()
	label.font_size = font_size
	label.position.y = label_height
	label.modulate = Color(color.r, color.g, color.b, 1.0)

	ring.visible = show_ring
	if show_ring:
		ring.scale = Vector3(radius_world, 1.0, radius_world)
		var material := ring.material_override as StandardMaterial3D
		if material != null:
			material = material.duplicate() as StandardMaterial3D
			material.albedo_color = Color(color.r, color.g, color.b, alpha)
			material.emission_enabled = true
			material.emission = Color(color.r, color.g, color.b, 1.0)
			material.emission_energy_multiplier = 0.26
			ring.material_override = material


func set_text(text_value: String) -> void:
	label.text = text_value
	label.visible = not text_value.is_empty()


func animate_in() -> void:
	scale = Vector3(0.72, 1.0, 0.72)
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "scale", Vector3.ONE, 0.16)
