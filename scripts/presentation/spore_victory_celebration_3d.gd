class_name SporeVictoryCelebration3D
extends Node3D

@onready var confetti_gold: GPUParticles3D = $ConfettiGold
@onready var confetti_cyan: GPUParticles3D = $ConfettiCyan
@onready var spore_glow: GPUParticles3D = $SporeGlow


func play() -> void:
	for emitter: GPUParticles3D in [confetti_gold, confetti_cyan, spore_glow]:
		emitter.emitting = true
		emitter.restart()

	await get_tree().create_timer(1.25).timeout
	queue_free()
