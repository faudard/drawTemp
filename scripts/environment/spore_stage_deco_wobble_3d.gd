@tool
extends Node3D
class_name SporeStageDecoWobble3D

@export var sway_amount_degrees: float = 2.5
@export var sway_speed: float = 0.55
@export var bob_amount: float = 0.05
@export var bob_speed: float = 0.65

var _base_rotation: Vector3
var _base_position: Vector3
var _time: float = 0.0

func _ready() -> void:
	_base_rotation = rotation
	_base_position = position
	set_process(true)

func _process(delta: float) -> void:
	_time += delta
	rotation = _base_rotation + Vector3(0.0, 0.0, deg_to_rad(sin(_time * sway_speed) * sway_amount_degrees))
	position = _base_position + Vector3(0.0, sin(_time * bob_speed) * bob_amount, 0.0)
