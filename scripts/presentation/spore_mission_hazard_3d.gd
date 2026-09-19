class_name SporeMissionHazard3D
extends Node3D

@export var pulse_speed: float = 2.7
@export var pulse_amount: float = 0.055

@onready var pool: MeshInstance3D = $Pool
@onready var spores: GPUParticles3D = $SporeParticles
@onready var label: Label3D = $Label

var _phase: float = 0.0
var _base_radius: float = 0.42


func configure(tile_size: float, phase: float = 0.0) -> void:
	_phase = phase
	_base_radius = tile_size * 0.34
	pool.scale = Vector3(_base_radius, 1.0, _base_radius)
	spores.amount = 8
	label.text = "SPORES"


func _process(_delta: float) -> void:
	var pulse: float = 1.0 + sin(Time.get_ticks_msec() * 0.001 * pulse_speed + _phase) * pulse_amount
	pool.scale = Vector3(_base_radius * pulse, 1.0, _base_radius * pulse)
