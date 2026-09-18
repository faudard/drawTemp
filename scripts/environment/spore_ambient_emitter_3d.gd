class_name SporeAmbientEmitter3D
extends Node3D

## Spatial ambience component. Prefer assigning final audio through the profile's
## AudioStream. A synthetic low-volume fallback keeps the scene alive meanwhile.

@export var profile: SporeAmbientAudioProfile
@export var autoplay: bool = true
@export var fallback_synthesis: bool = true
@export_range(8000, 48000, 1000) var fallback_mix_rate: int = 22000

var _player: AudioStreamPlayer3D
var _generator: AudioStreamGenerator
var _playback: AudioStreamGeneratorPlayback
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _sample_time: float = 0.0
var _smooth_noise: float = 0.0


func _ready() -> void:
	_player = get_node_or_null("Player") as AudioStreamPlayer3D
	if _player == null:
		_player = AudioStreamPlayer3D.new()
		_player.name = "Player"
		add_child(_player)
	_rng.seed = int(abs(global_position.x * 311.0 + global_position.z * 733.0)) + 1701
	_configure_player()
	if autoplay:
		start()


func _configure_player() -> void:
	if _player == null or profile == null:
		return
	_player.volume_db = profile.volume_db
	_player.max_distance = profile.max_distance
	_player.unit_size = profile.unit_size
	_player.panning_strength = 0.72


func start() -> void:
	if _player == null or profile == null:
		return
	_configure_player()
	if profile.stream != null:
		_player.stream = profile.stream
		_player.play()
		set_process(false)
		return
	if not fallback_synthesis:
		return
	_generator = AudioStreamGenerator.new()
	_generator.mix_rate = float(fallback_mix_rate)
	_generator.buffer_length = 0.35
	_player.stream = _generator
	_player.play()
	_playback = _player.get_stream_playback() as AudioStreamGeneratorPlayback
	set_process(_playback != null)


func stop() -> void:
	set_process(false)
	if _player != null:
		_player.stop()
	_playback = null


func _process(_delta: float) -> void:
	if _playback == null or profile == null:
		return
	var available: int = mini(_playback.get_frames_available(), 900)
	for _index: int in range(available):
		var sample: float = _next_sample()
		_playback.push_frame(Vector2(sample, sample))


func _next_sample() -> float:
	var mix_rate: float = float(fallback_mix_rate)
	var dt: float = 1.0 / maxf(1.0, mix_rate)
	_sample_time += dt
	var base: float = profile.fallback_base_frequency
	var motion: float = profile.fallback_motion
	var noise_amount: float = profile.fallback_noise
	var raw_noise: float = _rng.randf_range(-1.0, 1.0)
	_smooth_noise = lerpf(_smooth_noise, raw_noise, 0.018)
	var value: float = 0.0

	match profile.fallback_kind:
		"spores":
			var wobble: float = 1.0 + sin(_sample_time * 0.83) * 0.035 * motion
			value = sin(TAU * base * wobble * _sample_time) * 0.055
			value += sin(TAU * base * 1.51 * _sample_time) * 0.018
			value += _smooth_noise * noise_amount * 0.045
		"crown":
			var shimmer: float = 0.55 + sin(_sample_time * 1.17) * 0.20
			value = sin(TAU * base * _sample_time) * 0.026
			value += sin(TAU * base * 1.50 * _sample_time) * 0.018 * shimmer
			value += sin(TAU * base * 2.01 * _sample_time) * 0.010 * shimmer
		"exit":
			var breathe: float = 0.55 + 0.45 * sin(_sample_time * 0.61)
			value = sin(TAU * base * _sample_time) * 0.018 * breathe
			value += _smooth_noise * noise_amount * 0.035
		_:
			var wind: float = _smooth_noise * noise_amount * 0.065
			var distant: float = sin(TAU * base * 0.25 * _sample_time) * 0.010 * motion
			value = wind + distant
	return clampf(value, -0.18, 0.18)
