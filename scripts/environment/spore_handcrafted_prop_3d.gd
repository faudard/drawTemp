@tool
extends Node3D
class_name SporeHandcraftedProp3D

@export var bob_amplitude: float = 0.0
@export var bob_speed: float = 1.0
@export var pulse_lights: bool = false
@export var pulse_speed: float = 1.4
@export var pulse_energy_min: float = 0.6
@export var pulse_energy_max: float = 1.1

var _base_position: Vector3
var _time: float = 0.0

func _ready() -> void:
	_base_position = position
	set_process(true)

func _process(delta: float) -> void:
	_time += delta
	if bob_amplitude > 0.0:
		position = _base_position + Vector3(0.0, sin(_time * bob_speed) * bob_amplitude, 0.0)
	if pulse_lights:
		var t: float = 0.5 + 0.5 * sin(_time * pulse_speed)
		var value: float = lerpf(pulse_energy_min, pulse_energy_max, t)
		for child: Node in find_children("*", "OmniLight3D", true, false):
			(child as OmniLight3D).light_energy = value
