class_name SporeSkillBurst3D
extends Node3D

@onready var ring: MeshInstance3D = $Ring
@onready var accent_particles: GPUParticles3D = $AccentParticles


func play(color: Color) -> void:
	var material := ring.material_override as StandardMaterial3D
	if material != null:
		material = material.duplicate() as StandardMaterial3D
		material.albedo_color = Color(color.r, color.g, color.b, 0.70)
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.62
		ring.material_override = material

	var particles_material := accent_particles.process_material as ParticleProcessMaterial
	if particles_material != null:
		particles_material = particles_material.duplicate() as ParticleProcessMaterial
		particles_material.color = Color(color.r, color.g, color.b, 0.90)
		accent_particles.process_material = particles_material

	ring.scale = Vector3.ONE
	accent_particles.emitting = true
	accent_particles.restart()

	var tween := create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(ring, "scale", Vector3(4.6, 1.0, 4.6), 0.30)
	if material != null:
		tween.tween_property(
			material,
			"albedo_color",
			Color(color.r, color.g, color.b, 0.0),
			0.30
		)
	tween.set_parallel(false)
	tween.tween_interval(0.18)
	tween.tween_callback(Callable(self, "queue_free"))
