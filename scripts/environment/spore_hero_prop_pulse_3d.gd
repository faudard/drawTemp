@tool
extends Node3D
class_name SporeHeroPropPulse3D

@export var pulse_speed: float = 1.2
@export var light_min: float = 0.45
@export var light_max: float = 0.85
@export var bob_amount: float = 0.02

var _t: float = 0.0
var _base: Vector3

func _ready() -> void:
	_base = position
	set_process(true)

func _process(delta: float) -> void:
	_t += delta
	position = _base + Vector3(0.0, sin(_t * pulse_speed) * bob_amount, 0.0)
	var e: float = lerpf(light_min, light_max, 0.5 + 0.5 * sin(_t * pulse_speed))
	for child: Node in find_children("*", "OmniLight3D", true, false):
		(child as OmniLight3D).light_energy = e
