class_name SporeMissionHazard3D
extends Node3D

@export var pulse_speed: float = 2.7
@export var pulse_amount: float = 0.055

@onready var pool: MeshInstance3D = $Pool
@onready var spores: GPUParticles3D = $SporeParticles
@onready var label: Label3D = $Label

var _phase: float = 0.0


func configure(tile_size: float, phase: float = 0.0) -> void:
	_phase = phase
	var radius: float = tile_size * 0.34
	pool.scale = Vector3(radius, 1.0, radius)
	spores.amount = 8
	label.text = "SPORES"


func _process(_delta: float) -> void:
	var pulse: float = 1.0 + sin(Time.get_ticks_msec() * 0.001 * pulse_speed + _phase) * pulse_amount
	pool.scale.x = absf(pool.scale.x) * pulse
	pool.scale.z = absf(pool.scale.z) * pulse
