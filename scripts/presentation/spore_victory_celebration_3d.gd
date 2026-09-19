class_name SporeVictoryCelebration3D
extends Node3D

@onready var confetti_gold: GPUParticles3D = $ConfettiGold
@onready var confetti_cyan: GPUParticles3D = $ConfettiCyan
@onready var spore_glow: GPUParticles3D = $SporeGlow


func play(include_confetti: bool = true, include_spores: bool = true) -> void:
	confetti_gold.visible = include_confetti
	confetti_cyan.visible = include_confetti
	spore_glow.visible = include_spores

	if include_confetti:
		confetti_gold.emitting = true
		confetti_cyan.emitting = true
		confetti_gold.restart()
		confetti_cyan.restart()
	if include_spores:
		spore_glow.emitting = true
		spore_glow.restart()

	await get_tree().create_timer(1.25).timeout
	queue_free()
