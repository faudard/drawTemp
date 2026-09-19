@tool
class_name SporeComicWorldSign3D
extends Node3D

## Small reusable world sign.
## Geometry/layout lives in the .tscn so it can be edited visually in Godot.

@export var label_text: String = "SIGN":
	set(value):
		label_text = value
		_refresh_deferred()

@export var accent_color: Color = Color(1.0, 0.78, 0.20, 1.0):
	set(value):
		accent_color = value
		_refresh_deferred()

var _refresh_queued: bool = false


func _ready() -> void:
	_refresh()


func _refresh_deferred() -> void:
	if not is_inside_tree() or _refresh_queued:
		return
	_refresh_queued = true
	call_deferred("_apply_refresh")


func _apply_refresh() -> void:
	_refresh_queued = false
	_refresh()


func _refresh() -> void:
	var label := get_node_or_null("Label") as Label3D
	if label != null:
		label.text = label_text

	var stripe := get_node_or_null("Accent") as MeshInstance3D
	if stripe == null:
		return
	var material := stripe.material_override as StandardMaterial3D
	if material == null:
		return
	material = material.duplicate() as StandardMaterial3D
	material.albedo_color = accent_color
	material.emission_enabled = true
	material.emission = accent_color
	material.emission_energy_multiplier = 0.18
	stripe.material_override = material
