@tool
extends Node3D
class_name SporePrettyCluster3D

@export var pulse_lights: bool = false
@export var pulse_speed: float = 1.4
@export var min_energy: float = 0.45
@export var max_energy: float = 0.85

var _time: float = 0.0

func _ready() -> void:
	set_process(true)

func _process(delta: float) -> void:
	if not pulse_lights:
		return
	_time += delta
	var t: float = 0.5 + 0.5 * sin(_time * pulse_speed)
	var energy: float = lerpf(min_energy, max_energy, t)
	for child: Node in find_children("*", "OmniLight3D", true, false):
		(child as OmniLight3D).light_energy = energy
