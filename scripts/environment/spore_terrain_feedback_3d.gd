class_name SporeTerrainFeedback3D
extends Node3D

## Presentation-only feedback for footsteps and special cells.
## It never changes gameplay state, damage, movement or mission rules.

@export var ground_steps_enabled: bool = true
@export_range(-50.0, -5.0, 0.5) var ground_step_volume_db: float = -35.0
@export_range(-50.0, -5.0, 0.5) var special_step_volume_db: float = -26.0
@export_range(0.1, 12.0, 0.5) var max_distance: float = 5.0

var _rng: RandomNumberGenerator = RandomNumberGenerator.new()


func _ready() -> void:
	add_to_group("spore_terrain_feedback")
	_rng.seed = 0x51A7E


func play_step_feedback(
	terrain_type: String,
	world_position: Vector3,
	elevation_delta: int,
	_team: String
) -> void:
	match terrain_type:
		"hazard":
			_spawn_ring(world_position, Color(0.60, 0.20, 0.90, 0.55), 0.42)
			_play_tone(world_position, 92.0, 0.085, special_step_volume_db, "wet")
		"extraction":
			_spawn_ring(world_position, Color(0.26, 0.95, 0.54, 0.42), 0.34)
			_play_tone(world_position, 260.0, 0.070, special_step_volume_db - 2.0, "chime")
		"bonus":
			_spawn_ring(world_position, Color(0.25, 0.78, 1.0, 0.48), 0.38)
			_play_tone(world_position, 330.0, 0.080, special_step_volume_db - 1.0, "chime")
		"crown":
			_spawn_ring(world_position, Color(1.0, 0.78, 0.24, 0.55), 0.50)
			_play_tone(world_position, 220.0, 0.12, special_step_volume_db, "bell")
		_:
			if elevation_delta != 0:
				_spawn_ring(world_position, Color(0.72, 0.62, 0.45, 0.20), 0.22)
			if ground_steps_enabled:
				_play_tone(world_position, 115.0 + _rng.randf_range(-8.0, 8.0), 0.038, ground_step_volume_db, "step")


func _spawn_ring(world_position: Vector3, color: Color, radius: float) -> void:
	var ring: MeshInstance3D = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius * 1.08
	mesh.height = 0.025
	mesh.radial_segments = 20
	ring.mesh = mesh
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.emission_enabled = true
	material.emission = Color(color.r, color.g, color.b, 1.0)
	material.emission_energy_multiplier = 0.36
	ring.material_override = material
	add_child(ring)
	ring.global_position = world_position + Vector3(0.0, 0.035, 0.0)
	ring.scale = Vector3(0.45, 1.0, 0.45)
	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(ring, "scale", Vector3(1.35, 1.0, 1.35), 0.24).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	var light: OmniLight3D = OmniLight3D.new()
	light.light_color = Color(color.r, color.g, color.b, 1.0)
	light.light_energy = 0.34
	light.omni_range = 1.2
	ring.add_child(light)
	tween.tween_property(light, "light_energy", 0.0, 0.24)
	tween.set_parallel(false)
	tween.tween_callback(Callable(ring, "queue_free"))


func _play_tone(
	world_position: Vector3,
	frequency: float,
	duration: float,
	volume_db: float,
	kind: String
) -> void:
	var player: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	player.volume_db = volume_db
	player.max_distance = max_distance
	player.unit_size = 1.4
	player.panning_strength = 0.85
	var generator: AudioStreamGenerator = AudioStreamGenerator.new()
	generator.mix_rate = 22050.0
	generator.buffer_length = duration + 0.08
	player.stream = generator
	add_child(player)
	player.global_position = world_position + Vector3(0.0, 0.25, 0.0)
	player.play()
	var playback: AudioStreamGeneratorPlayback = player.get_stream_playback() as AudioStreamGeneratorPlayback
	if playback != null:
		var sample_count: int = mini(int(22050.0 * duration), playback.get_frames_available())
		for sample_index: int in range(sample_count):
			var time_value: float = float(sample_index) / 22050.0
			var phase: float = time_value / maxf(0.001, duration)
			var envelope: float = sin(PI * clampf(phase, 0.0, 1.0))
			var sample: float = 0.0
			match kind:
				"wet":
					sample = sin(TAU * frequency * time_value) * 0.17
					sample += _rng.randf_range(-1.0, 1.0) * 0.055
				"chime":
					sample = sin(TAU * frequency * time_value) * 0.13
					sample += sin(TAU * frequency * 2.02 * time_value) * 0.045
				"bell":
					sample = sin(TAU * frequency * time_value) * 0.12
					sample += sin(TAU * frequency * 1.50 * time_value) * 0.055
					sample += sin(TAU * frequency * 2.50 * time_value) * 0.025
				_:
					sample = sin(TAU * frequency * time_value) * 0.075
					sample += _rng.randf_range(-1.0, 1.0) * 0.025
			sample *= envelope * envelope
			playback.push_frame(Vector2(sample, sample))
	var timer: SceneTreeTimer = get_tree().create_timer(duration + 0.12)
	timer.timeout.connect(player.queue_free)
