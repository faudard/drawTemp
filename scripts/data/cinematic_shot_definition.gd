@tool
class_name SporeCinematicShotDefinition
extends Resource

## Reusable 3D cinematic framing asset.
## Edit .tres instances in the Godot Inspector instead of hard-coding camera values.

@export_group("Identity")
@export var id: String = "shot"
@export var display_name: String = "Shot"
@export_multiline var description: String = ""

@export_group("Framing")
@export_enum("center", "head", "feet") var target_anchor: String = "head"
@export_range(5.0, 18.0, 0.1) var camera_distance: float = 7.8
@export_range(3.0, 16.0, 0.1) var camera_height: float = 7.2
@export_range(-90.0, 90.0, 1.0) var shoulder_angle_degrees: float = 18.0
@export_range(-1.5, 1.5, 0.05) var lateral_offset: float = 0.30
@export_range(-1.0, 1.0, 0.05) var depth_offset: float = 0.0

@export_group("Transition")
@export var instant_cut: bool = true
@export_range(0.0, 1.5, 0.05) var transition_seconds: float = 0.0


func summary() -> String:
	return "%s • dist %.1f • h %.1f • épaule %.0f°" % [
		display_name,
		camera_distance,
		camera_height,
		shoulder_angle_degrees,
	]
