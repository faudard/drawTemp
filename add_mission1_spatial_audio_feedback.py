#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
ENV_DIR = ROOT / "scenes" / "environment"
SCRIPT_DIR = ROOT / "scripts" / "environment"
DATA_DIR = ROOT / "data" / "ambient_audio"
DATA_SCRIPT_DIR = ROOT / "scripts" / "data"
DRESSING = ENV_DIR / "mission_1_dressing.tscn"
BOARD = ROOT / "scripts" / "prototypes" / "spore_battle_board_3d.gd"

required = [DRESSING, BOARD]
missing = [str(p) for p in required if not p.exists()]
if missing:
    print("[ERROR] Missing required files:")
    for item in missing:
        print("  -", item)
    print()
    print("Run first:")
    print("  python beautify_mission1_immersive_garden.py")
    print("  python add_mission1_living_ambience.py")
    sys.exit(1)

SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_SCRIPT_DIR.mkdir(parents=True, exist_ok=True)


def backup(path: Path) -> None:
    out = path.with_suffix(path.suffix + ".spatial_audio_backup")
    if not out.exists():
        out.write_bytes(path.read_bytes())


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


for p in required:
    backup(p)

AMBIENT_PROFILE = r'''@tool
class_name SporeAmbientAudioProfile
extends Resource

## Reusable Godot-native spatial ambience profile.
## Assign a real .ogg/.wav stream later; the emitter uses a quiet procedural
## fallback while the project has no final audio asset.

@export_group("Identity")
@export var id: String = "ambient"
@export var display_name: String = "Ambient"

@export_group("Audio")
@export var stream: AudioStream
@export_enum("forest", "spores", "crown", "exit") var fallback_kind: String = "forest"
@export_range(-50.0, 0.0, 0.5) var volume_db: float = -28.0
@export_range(1.0, 30.0, 0.5) var max_distance: float = 12.0
@export_range(0.1, 8.0, 0.1) var unit_size: float = 2.0
@export_range(30.0, 900.0, 1.0) var fallback_base_frequency: float = 110.0
@export_range(0.0, 1.0, 0.01) var fallback_motion: float = 0.25
@export_range(0.0, 0.5, 0.01) var fallback_noise: float = 0.10
'''

AMBIENT_EMITTER = r'''class_name SporeAmbientEmitter3D
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
'''

TERRAIN_FEEDBACK = r'''class_name SporeTerrainFeedback3D
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
'''

AMBIENT_SCENE = r'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/environment/spore_ambient_emitter_3d.gd" id="1_script"]

[node name="AmbientEmitter3D" type="Node3D"]
script = ExtResource("1_script")

[node name="Player" type="AudioStreamPlayer3D" parent="."]
'''

TERRAIN_SCENE = r'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/environment/spore_terrain_feedback_3d.gd" id="1_script"]

[node name="TerrainFeedback3D" type="Node3D"]
script = ExtResource("1_script")
'''

FOREST_PROFILE = r'''[gd_resource type="Resource" script_class="SporeAmbientAudioProfile" load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/data/ambient_audio_profile.gd" id="1_profile"]

[resource]
script = ExtResource("1_profile")
id = "forest_night"
display_name = "Forêt nocturne"
fallback_kind = "forest"
volume_db = -31.0
max_distance = 18.0
unit_size = 5.0
fallback_base_frequency = 68.0
fallback_motion = 0.32
fallback_noise = 0.18
'''

SPORE_PROFILE = r'''[gd_resource type="Resource" script_class="SporeAmbientAudioProfile" load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/data/ambient_audio_profile.gd" id="1_profile"]

[resource]
script = ExtResource("1_profile")
id = "spore_hum"
display_name = "Bourdonnement des spores"
fallback_kind = "spores"
volume_db = -29.0
max_distance = 7.5
unit_size = 2.5
fallback_base_frequency = 82.0
fallback_motion = 0.30
fallback_noise = 0.12
'''

CROWN_PROFILE = r'''[gd_resource type="Resource" script_class="SporeAmbientAudioProfile" load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/data/ambient_audio_profile.gd" id="1_profile"]

[resource]
script = ExtResource("1_profile")
id = "crown_shimmer"
display_name = "Résonance de la Couronne"
fallback_kind = "crown"
volume_db = -25.0
max_distance = 5.5
unit_size = 1.8
fallback_base_frequency = 196.0
fallback_motion = 0.35
fallback_noise = 0.0
'''

EXIT_PROFILE = r'''[gd_resource type="Resource" script_class="SporeAmbientAudioProfile" load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/data/ambient_audio_profile.gd" id="1_profile"]

[resource]
script = ExtResource("1_profile")
id = "exit_whisper"
display_name = "Souffle de sortie"
fallback_kind = "exit"
volume_db = -31.0
max_distance = 5.0
unit_size = 1.8
fallback_base_frequency = 132.0
fallback_motion = 0.25
fallback_noise = 0.08
'''

write(DATA_SCRIPT_DIR / "ambient_audio_profile.gd", AMBIENT_PROFILE)
write(SCRIPT_DIR / "spore_ambient_emitter_3d.gd", AMBIENT_EMITTER)
write(SCRIPT_DIR / "spore_terrain_feedback_3d.gd", TERRAIN_FEEDBACK)
write(ENV_DIR / "ambient_emitter_3d.tscn", AMBIENT_SCENE)
write(ENV_DIR / "terrain_feedback_3d.tscn", TERRAIN_SCENE)
write(DATA_DIR / "forest_night.tres", FOREST_PROFILE)
write(DATA_DIR / "spore_hum.tres", SPORE_PROFILE)
write(DATA_DIR / "crown_shimmer.tres", CROWN_PROFILE)
write(DATA_DIR / "exit_whisper.tres", EXIT_PROFILE)

# -----------------------------------------------------------------------------
# Mission 1 dressing: authored spatial emitters, visible/selectable in the scene.
# -----------------------------------------------------------------------------
dressing = DRESSING.read_text(encoding="utf-8")

if 'path="res://scenes/environment/ambient_emitter_3d.tscn"' not in dressing:
    header = re.search(r'^\[gd_scene[^\n]*\]\n', dressing)
    if not header:
        raise RuntimeError("Invalid mission_1_dressing.tscn header")
    ext = '''
[ext_resource type="PackedScene" path="res://scenes/environment/ambient_emitter_3d.tscn" id="94_ambient"]
[ext_resource type="PackedScene" path="res://scenes/environment/terrain_feedback_3d.tscn" id="95_feedback"]
[ext_resource type="Resource" path="res://data/ambient_audio/forest_night.tres" id="96_forest_audio"]
[ext_resource type="Resource" path="res://data/ambient_audio/spore_hum.tres" id="97_spore_audio"]
[ext_resource type="Resource" path="res://data/ambient_audio/crown_shimmer.tres" id="98_crown_audio"]
[ext_resource type="Resource" path="res://data/ambient_audio/exit_whisper.tres" id="99_exit_audio"]
'''
    dressing = dressing[:header.end()] + ext + dressing[header.end():]

if '[node name="SpatialAudio" type="Node3D" parent="."]' not in dressing:
    audio_nodes = r'''[node name="SpatialAudio" type="Node3D" parent="."]

[node name="ForestBed" parent="SpatialAudio" instance=ExtResource("94_ambient")]
position = Vector3(0, 0.6, 0)
profile = ExtResource("96_forest_audio")

[node name="SporeHum" parent="SpatialAudio" instance=ExtResource("94_ambient")]
position = Vector3(1.0, 0.35, 0.7)
profile = ExtResource("97_spore_audio")

[node name="CrownResonance" parent="SpatialAudio" instance=ExtResource("94_ambient")]
position = Vector3(6.30, 0.55, -5.55)
profile = ExtResource("98_crown_audio")

[node name="ExitWhisper" parent="SpatialAudio" instance=ExtResource("94_ambient")]
position = Vector3(-5.70, 0.35, 4.95)
profile = ExtResource("99_exit_audio")

[node name="TerrainFeedback" parent="SpatialAudio" instance=ExtResource("95_feedback")]
'''
    dressing = dressing.rstrip() + "\n\n" + audio_nodes + "\n"

DRESSING.write_text(dressing, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Board: presentation-only hook after a movement step.
# -----------------------------------------------------------------------------
board = BOARD.read_text(encoding="utf-8")

step_anchor = '''\t\tvar move_tween: Tween = actor.move_to_cell(map_root, step_cell, duration_per_step)\n\t\tawait move_tween.finished\n'''
step_replacement = '''\t\tvar move_tween: Tween = actor.move_to_cell(map_root, step_cell, duration_per_step)\n\t\tawait move_tween.finished\n\t\t_play_terrain_feedback_3d(actor, from_cell, step_cell)\n'''
if "_play_terrain_feedback_3d(actor, from_cell, step_cell)" not in board:
    if step_anchor not in board:
        raise RuntimeError("Movement step anchor not found in spore_battle_board_3d.gd")
    board = board.replace(step_anchor, step_replacement, 1)

# Player-specific teleport branch.
player_teleport = '''\t\tif battle_rng.randi_range(1, 100) <= chance:\n\t\t\tactive_actor.place_on_map(map_root, cell)\n\t\t\t_show_floating_text(active_actor.position + Vector3(0.0, 1.2, 0.0), "TELEPORT", Color(0.70, 0.55, 1.0, 1.0))\n'''
player_teleport_new = '''\t\tif battle_rng.randi_range(1, 100) <= chance:\n\t\t\tactive_actor.place_on_map(map_root, cell)\n\t\t\t_play_terrain_feedback_3d(active_actor, start_cell, cell)\n\t\t\t_show_floating_text(active_actor.position + Vector3(0.0, 1.2, 0.0), "TELEPORT", Color(0.70, 0.55, 1.0, 1.0))\n'''
if "_play_terrain_feedback_3d(active_actor, start_cell, cell)" not in board and player_teleport in board:
    board = board.replace(player_teleport, player_teleport_new, 1)

# Generic teleport inside _move_actor_along_path.
generic_teleport = '''\t\tif battle_rng.randi_range(1, 100) <= chance:\n\t\t\tactor.place_on_map(map_root, destination)\n\t\t\t_show_floating_text(actor.position + Vector3(0.0, 1.2, 0.0), "TELEPORT", Color(0.70, 0.55, 1.0, 1.0))\n'''
generic_teleport_new = '''\t\tif battle_rng.randi_range(1, 100) <= chance:\n\t\t\tvar teleport_from: Vector2i = actor.cell\n\t\t\tactor.place_on_map(map_root, destination)\n\t\t\t_play_terrain_feedback_3d(actor, teleport_from, destination)\n\t\t\t_show_floating_text(actor.position + Vector3(0.0, 1.2, 0.0), "TELEPORT", Color(0.70, 0.55, 1.0, 1.0))\n'''
if "_play_terrain_feedback_3d(actor, teleport_from, destination)" not in board and generic_teleport in board:
    board = board.replace(generic_teleport, generic_teleport_new, 1)

if "func _play_terrain_feedback_3d(" not in board:
    insert_at = board.find("func _check_opportunity_reactions(")
    if insert_at < 0:
        raise RuntimeError("Could not find terrain feedback helper insertion point")
    helper = r'''func _play_terrain_feedback_3d(
	actor: SporeUnitActor3D,
	from_cell: Vector2i,
	to_cell: Vector2i
) -> void:
	if map_root == null or actor == null:
		return
	var tile: Node = map_root.tile_at(to_cell)
	var terrain_type: String = String(tile.get("terrain_type")) if tile != null else "ground"
	var elevation_delta: int = map_root.elevation_at(to_cell) - map_root.elevation_at(from_cell)
	var world_position: Vector3 = map_root.to_global(map_root.cell_top_local(to_cell))
	var candidates: Array[Node] = get_tree().get_nodes_in_group("spore_terrain_feedback")
	for candidate: Node in candidates:
		if candidate == null or not is_instance_valid(candidate):
			continue
		if candidate != map_root and not map_root.is_ancestor_of(candidate):
			continue
		if candidate.has_method("play_step_feedback"):
			candidate.call("play_step_feedback", terrain_type, world_position, elevation_delta, actor.team)
			return


'''
    board = board[:insert_at] + helper + board[insert_at:]

BOARD.write_text(board, encoding="utf-8", newline="\n")

print("[OK] Mission 1 spatial audio + terrain feedback pass applied.")
print()
print("Godot-native reusable assets added:")
print("  scripts/data/ambient_audio_profile.gd")
print("  data/ambient_audio/forest_night.tres")
print("  data/ambient_audio/spore_hum.tres")
print("  data/ambient_audio/crown_shimmer.tres")
print("  data/ambient_audio/exit_whisper.tres")
print("  scenes/environment/ambient_emitter_3d.tscn")
print("  scenes/environment/terrain_feedback_3d.tscn")
print()
print("Mission 1 gets spatial ambience around forest, spores, crown and exit.")
print("If a profile has no final AudioStream, a very quiet procedural fallback is used.")
print("Later you can assign .ogg/.wav directly in each .tres profile from the Inspector.")
print()
print("Movement feedback is presentation-only:")
print("  ground     -> quiet footstep")
print("  height     -> small dust ring")
print("  hazard     -> purple pulse + wet blip")
print("  extraction -> green pulse + soft chime")
print("  bonus      -> cyan pulse + chime")
print("  crown      -> gold pulse + bell")
print()
print("No movement range, CT, damage, cover, LOS or mission rules are changed.")
print("Backups: *.spatial_audio_backup")
