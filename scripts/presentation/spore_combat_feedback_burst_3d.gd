class_name SporeCombatFeedbackBurst3D
extends Node3D

@onready var accent_particles: GPUParticles3D = $AccentParticles
@onready var ink_particles: GPUParticles3D = $InkParticles


func play(color: Color) -> void:
	var accent_material := accent_particles.process_material as ParticleProcessMaterial
	if accent_material != null:
		accent_material = accent_material.duplicate() as ParticleProcessMaterial
		accent_material.color = color
		accent_particles.process_material = accent_material

	accent_particles.emitting = true
	ink_particles.emitting = true
	accent_particles.restart()
	ink_particles.restart()

	await get_tree().create_timer(0.72).timeout
	queue_free()
