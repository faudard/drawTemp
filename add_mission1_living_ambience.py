#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
ENV_DIR = ROOT / "scenes" / "environment"
SCRIPT_DIR = ROOT / "scripts" / "environment"
DRESSING = ENV_DIR / "mission_1_dressing.tscn"

required = [
    ENV_DIR / "forest_tree_3d.tscn",
    ENV_DIR / "mushroom_cluster_3d.tscn",
    ENV_DIR / "spore_crystal_3d.tscn",
    ENV_DIR / "crown_shrine_3d.tscn",
    DRESSING,
]

missing = [str(p) for p in required if not p.exists()]
if missing:
    print("[ERROR] Mission 1 immersive garden files are missing:")
    for item in missing:
        print("  -", item)
    print()
    print("Run this patch first:")
    print("  python beautify_mission1_immersive_garden.py")
    sys.exit(1)

SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
ENV_DIR.mkdir(parents=True, exist_ok=True)


def backup(path: Path) -> None:
    out = path.with_suffix(path.suffix + ".living_ambience_backup")
    if not out.exists():
        out.write_bytes(path.read_bytes())


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def add_script_to_scene(path: Path, script_path: str, mode: str, speed: float, amplitude: float) -> None:
    text = path.read_text(encoding="utf-8")
    if script_path in text:
        return

    # Use a high ext_resource id to avoid colliding with the authored scene.
    header = re.search(r'^\[gd_scene[^\n]*\]\n', text)
    if not header:
        raise RuntimeError(f"Invalid .tscn header: {path}")

    ext_line = f'\n[ext_resource type="Script" path="{script_path}" id="99_living"]\n'
    text = text[:header.end()] + ext_line + text[header.end():]

    root_match = re.search(r'^\[node name="[^"]+" type="Node3D"\]\n', text, re.M)
    if not root_match:
        raise RuntimeError(f"Root Node3D not found in {path}")

    props = (
        'script = ExtResource("99_living")\n'
        f'animation_kind = "{mode}"\n'
        f'animation_speed = {speed:.3f}\n'
        f'animation_amplitude = {amplitude:.3f}\n'
    )
    text = text[:root_match.end()] + props + text[root_match.end():]
    path.write_text(text, encoding="utf-8", newline="\n")


for path in required:
    backup(path)

LIVING_PROP = r'''@tool
class_name SporeLivingProp3D
extends Node3D

## Very small reusable presentation component for environmental props.
## The geometry remains authored in .tscn scenes; this script only adds subtle life.

@export_enum("none", "tree", "mushroom", "crystal", "shrine", "speaker", "lantern") var animation_kind: String = "none"
@export_range(0.05, 4.0, 0.05) var animation_speed: float = 1.0
@export_range(0.0, 0.25, 0.005) var animation_amplitude: float = 0.035
@export var animate_in_editor: bool = false
@export var phase_offset: float = 0.0

var _time: float = 0.0
var _base_transforms: Dictionary = {}
var _base_light_energy: Dictionary = {}


func _ready() -> void:
	_cache_base_state()
	set_process(not Engine.is_editor_hint() or animate_in_editor)


func _notification(what: int) -> void:
	if what == NOTIFICATION_EDITOR_PRE_SAVE and Engine.is_editor_hint():
		_restore_base_state()


func _cache_base_state() -> void:
	_base_transforms.clear()
	_base_light_energy.clear()
	for child: Node in get_children():
		if child is Node3D:
			_base_transforms[child] = (child as Node3D).transform
		if child is Light3D:
			_base_light_energy[child] = (child as Light3D).light_energy


func _restore_base_state() -> void:
	for node_value: Variant in _base_transforms.keys():
		var node: Node3D = node_value as Node3D
		if node != null and is_instance_valid(node):
			node.transform = _base_transforms[node]
	for light_value: Variant in _base_light_energy.keys():
		var light: Light3D = light_value as Light3D
		if light != null and is_instance_valid(light):
			light.light_energy = float(_base_light_energy[light])


func _process(delta: float) -> void:
	if Engine.is_editor_hint() and not animate_in_editor:
		return
	_time += delta * animation_speed
	match animation_kind:
		"tree":
			_animate_tree()
		"mushroom":
			_animate_mushrooms()
		"crystal":
			_animate_crystal()
		"shrine":
			_animate_shrine()
		"speaker":
			_animate_speaker()
		"lantern":
			_animate_lantern()
		_:
			pass


func _base_transform(node: Node3D) -> Transform3D:
	if _base_transforms.has(node):
		return _base_transforms[node]
	return node.transform


func _animate_tree() -> void:
	for name_value: String in ["CanopyLow", "CanopyHigh"]:
		var node: Node3D = get_node_or_null(name_value) as Node3D
		if node == null:
			continue
		var base: Transform3D = _base_transform(node)
		node.transform = base
		var phase: float = phase_offset + (0.7 if name_value == "CanopyHigh" else 0.0)
		node.rotation.z += sin(_time * 0.62 + phase) * animation_amplitude
		node.rotation.x += cos(_time * 0.47 + phase) * animation_amplitude * 0.35


func _animate_mushrooms() -> void:
	var names: Array[String] = ["CapA", "CapB", "CapC"]
	for index: int in range(names.size()):
		var node: Node3D = get_node_or_null(names[index]) as Node3D
		if node == null:
			continue
		var base: Transform3D = _base_transform(node)
		node.transform = base
		var breathe: float = 1.0 + sin(_time * 1.18 + phase_offset + float(index) * 0.9) * animation_amplitude
		node.scale = base.basis.get_scale() * Vector3(1.0, breathe, 1.0)


func _animate_crystal() -> void:
	var names: Array[String] = ["CrystalA", "CrystalB", "CrystalC"]
	for index: int in range(names.size()):
		var node: Node3D = get_node_or_null(names[index]) as Node3D
		if node == null:
			continue
		var base: Transform3D = _base_transform(node)
		node.transform = base
		var pulse: float = 1.0 + sin(_time * 1.35 + phase_offset + float(index) * 0.55) * animation_amplitude * 0.60
		node.scale = base.basis.get_scale() * pulse
	_pulse_light("Glow", 0.18)


func _animate_shrine() -> void:
	var ring: Node3D = get_node_or_null("GlowRing") as Node3D
	if ring != null:
		var base: Transform3D = _base_transform(ring)
		ring.transform = base
		var pulse: float = 1.0 + sin(_time * 1.15 + phase_offset) * animation_amplitude * 0.55
		ring.scale = base.basis.get_scale() * Vector3(pulse, 1.0, pulse)
	_pulse_light("CrownLight", 0.16)


func _animate_speaker() -> void:
	var cone: Node3D = get_node_or_null("Glow") as Node3D
	if cone != null:
		var base: Transform3D = _base_transform(cone)
		cone.transform = base
		var beat: float = maxf(0.0, sin(_time * 2.25 + phase_offset))
		cone.scale = base.basis.get_scale() * (1.0 + beat * animation_amplitude * 1.4)
	_pulse_light("BeatLight", 0.10)


func _animate_lantern() -> void:
	var glow: Node3D = get_node_or_null("GlowCap") as Node3D
	if glow != null:
		var base: Transform3D = _base_transform(glow)
		glow.transform = base
		var pulse: float = 1.0 + sin(_time * 0.92 + phase_offset) * animation_amplitude * 0.55
		glow.scale = base.basis.get_scale() * pulse
	_pulse_light("LanternLight", 0.12)


func _pulse_light(node_name: String, relative_amount: float) -> void:
	var light: Light3D = get_node_or_null(node_name) as Light3D
	if light == null:
		return
	var base_energy: float = float(_base_light_energy.get(light, light.light_energy))
	light.light_energy = base_energy * (1.0 + sin(_time * 1.05 + phase_offset) * relative_amount)
'''

FIREFLIES = r'''@tool
class_name SporeFireflyField3D
extends Node3D

## Lightweight reusable firefly field. Points are generated deterministically so
## the field remains visible in the editor and identical at runtime.

@export_range(1, 24, 1) var amount: int = 8:
	set(value):
		amount = maxi(1, value)
		_rebuild_deferred()
@export_range(0.2, 8.0, 0.1) var radius: float = 2.0:
	set(value):
		radius = maxf(0.2, value)
		_rebuild_deferred()
@export_range(0.1, 4.0, 0.1) var height: float = 1.5:
	set(value):
		height = maxf(0.1, value)
		_rebuild_deferred()
@export var glow_color: Color = Color(0.74, 1.0, 0.54, 1.0):
	set(value):
		glow_color = value
		_rebuild_deferred()
@export var seed_value: int = 1337:
	set(value):
		seed_value = value
		_rebuild_deferred()
@export_range(0.05, 3.0, 0.05) var drift_speed: float = 0.55
@export_range(0.0, 0.6, 0.01) var drift_amount: float = 0.22
@export var animate_in_editor: bool = false

var _time: float = 0.0
var _rebuild_queued: bool = false
var _base_positions: Dictionary = {}


func _ready() -> void:
	_rebuild()
	set_process(not Engine.is_editor_hint() or animate_in_editor)


func _rebuild_deferred() -> void:
	if not is_inside_tree() or _rebuild_queued:
		return
	_rebuild_queued = true
	call_deferred("_apply_rebuild")


func _apply_rebuild() -> void:
	_rebuild_queued = false
	_rebuild()


func _rebuild() -> void:
	for child: Node in get_children():
		if child.name.begins_with("_Firefly"):
			child.free()
	_base_positions.clear()

	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = seed_value
	for index: int in range(amount):
		var point: MeshInstance3D = MeshInstance3D.new()
		point.name = "_Firefly%02d" % index
		var sphere: SphereMesh = SphereMesh.new()
		sphere.radius = 0.035
		sphere.height = 0.070
		sphere.radial_segments = 6
		sphere.rings = 4
		point.mesh = sphere
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = glow_color
		material.emission_enabled = true
		material.emission = glow_color
		material.emission_energy_multiplier = 1.65
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		point.material_override = material
		var angle: float = rng.randf_range(-PI, PI)
		var distance: float = sqrt(rng.randf()) * radius
		point.position = Vector3(
			cos(angle) * distance,
			rng.randf_range(0.28, height),
			sin(angle) * distance
		)
		_base_positions[point] = point.position
		add_child(point, false, Node.INTERNAL_MODE_BACK)


func _process(delta: float) -> void:
	if Engine.is_editor_hint() and not animate_in_editor:
		return
	_time += delta * drift_speed
	var index: int = 0
	for node_value: Variant in _base_positions.keys():
		var point: Node3D = node_value as Node3D
		if point == null or not is_instance_valid(point):
			continue
		var base: Vector3 = _base_positions[point]
		var phase: float = float(index) * 1.71 + float(seed_value % 31) * 0.11
		point.position = base + Vector3(
			sin(_time * 0.83 + phase) * drift_amount,
			sin(_time * 1.31 + phase * 0.73) * drift_amount * 0.42,
			cos(_time * 0.67 + phase) * drift_amount
		)
		var blink: float = 0.72 + maxf(0.0, sin(_time * 2.2 + phase)) * 0.42
		point.scale = Vector3.ONE * blink
		index += 1
'''

MIST = r'''@tool
class_name SporeMistPatch3D
extends Node3D

## Low ground mist used only as decoration. It never changes tactical state.

@export var mist_color: Color = Color(0.42, 0.20, 0.62, 0.17):
	set(value):
		mist_color = value
		_rebuild_deferred()
@export_range(0.4, 3.0, 0.1) var width: float = 1.20:
	set(value):
		width = maxf(0.4, value)
		_rebuild_deferred()
@export_range(0.05, 1.0, 0.05) var height: float = 0.18:
	set(value):
		height = maxf(0.05, value)
		_rebuild_deferred()
@export_range(0.05, 2.0, 0.05) var drift_speed: float = 0.28
@export_range(0.0, 0.4, 0.01) var drift_amount: float = 0.10
@export var animate_in_editor: bool = false

var _time: float = 0.0
var _rebuild_queued: bool = false
var _base_positions: Dictionary = {}


func _ready() -> void:
	_rebuild()
	set_process(not Engine.is_editor_hint() or animate_in_editor)


func _rebuild_deferred() -> void:
	if not is_inside_tree() or _rebuild_queued:
		return
	_rebuild_queued = true
	call_deferred("_apply_rebuild")


func _apply_rebuild() -> void:
	_rebuild_queued = false
	_rebuild()


func _rebuild() -> void:
	for child: Node in get_children():
		if child.name.begins_with("_Mist"):
			child.free()
	_base_positions.clear()

	for index: int in range(3):
		var cloud: MeshInstance3D = MeshInstance3D.new()
		cloud.name = "_Mist%02d" % index
		var sphere: SphereMesh = SphereMesh.new()
		sphere.radius = 0.5
		sphere.height = 1.0
		sphere.radial_segments = 12
		sphere.rings = 6
		cloud.mesh = sphere
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = mist_color
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.no_depth_test = false
		cloud.material_override = material
		cloud.scale = Vector3(width * (0.72 + float(index) * 0.10), height, width * (0.52 + float(index) * 0.08))
		cloud.position = Vector3(float(index - 1) * width * 0.22, 0.12 + float(index) * 0.025, float((index % 2) * 2 - 1) * width * 0.12)
		_base_positions[cloud] = cloud.position
		add_child(cloud, false, Node.INTERNAL_MODE_BACK)


func _process(delta: float) -> void:
	if Engine.is_editor_hint() and not animate_in_editor:
		return
	_time += delta * drift_speed
	var index: int = 0
	for node_value: Variant in _base_positions.keys():
		var cloud: Node3D = node_value as Node3D
		if cloud == null or not is_instance_valid(cloud):
			continue
		var base: Vector3 = _base_positions[cloud]
		var phase: float = float(index) * 1.35
		cloud.position = base + Vector3(
			sin(_time + phase) * drift_amount,
			0.0,
			cos(_time * 0.72 + phase) * drift_amount * 0.65
		)
		index += 1
'''

write(SCRIPT_DIR / "spore_living_prop_3d.gd", LIVING_PROP)
write(SCRIPT_DIR / "spore_firefly_field_3d.gd", FIREFLIES)
write(SCRIPT_DIR / "spore_mist_patch_3d.gd", MIST)

FIREFLY_SCENE = r'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/environment/spore_firefly_field_3d.gd" id="1_script"]

[node name="FireflyField3D" type="Node3D"]
script = ExtResource("1_script")
amount = 8
radius = 2.0
height = 1.65
drift_speed = 0.55
drift_amount = 0.20
'''

MIST_SCENE = r'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/environment/spore_mist_patch_3d.gd" id="1_script"]

[node name="SporeMistPatch3D" type="Node3D"]
script = ExtResource("1_script")
width = 1.15
height = 0.17
drift_speed = 0.26
drift_amount = 0.08
'''

LANTERN_SCENE = r'''[gd_scene load_steps=7 format=3]

[ext_resource type="Script" path="res://scripts/environment/spore_living_prop_3d.gd" id="1_script"]

[sub_resource type="StandardMaterial3D" id="MatStem"]
albedo_color = Color(0.36, 0.27, 0.18, 1)
roughness = 0.96

[sub_resource type="StandardMaterial3D" id="MatGlow"]
albedo_color = Color(0.35, 0.72, 0.38, 1)
emission_enabled = true
emission = Color(0.28, 0.84, 0.40, 1)
emission_energy_multiplier = 0.75
roughness = 0.78

[sub_resource type="CylinderMesh" id="StemMesh"]
top_radius = 0.055
bottom_radius = 0.085
height = 0.66
radial_segments = 8

[sub_resource type="SphereMesh" id="CapMesh"]
radius = 0.5
height = 1.0
radial_segments = 12
rings = 6

[sub_resource type="SphereMesh" id="MossMesh"]
radius = 0.5
height = 1.0
radial_segments = 10
rings = 5

[node name="GardenLantern3D" type="Node3D"]
script = ExtResource("1_script")
animation_kind = "lantern"
animation_speed = 0.72
animation_amplitude = 0.045

[node name="Moss" type="MeshInstance3D" parent="."]
position = Vector3(0, 0.025, 0)
scale = Vector3(0.42, 0.06, 0.34)
mesh = SubResource("MossMesh")
material_override = SubResource("MatStem")

[node name="Stem" type="MeshInstance3D" parent="."]
position = Vector3(0, 0.33, 0)
mesh = SubResource("StemMesh")
material_override = SubResource("MatStem")

[node name="GlowCap" type="MeshInstance3D" parent="."]
position = Vector3(0, 0.72, 0)
scale = Vector3(0.34, 0.16, 0.34)
mesh = SubResource("CapMesh")
material_override = SubResource("MatGlow")

[node name="LanternLight" type="OmniLight3D" parent="."]
position = Vector3(0, 0.70, 0)
light_color = Color(0.44, 1, 0.52, 1)
light_energy = 0.55
omni_range = 2.6
shadow_enabled = false
'''

SPEAKER_SCENE = r'''[gd_scene load_steps=7 format=3]

[ext_resource type="Script" path="res://scripts/environment/spore_living_prop_3d.gd" id="1_script"]

[sub_resource type="StandardMaterial3D" id="MatBody"]
albedo_color = Color(0.08, 0.07, 0.12, 1)
roughness = 0.72

[sub_resource type="StandardMaterial3D" id="MatGlow"]
albedo_color = Color(0.40, 0.16, 0.58, 1)
emission_enabled = true
emission = Color(0.38, 0.10, 0.62, 1)
emission_energy_multiplier = 0.72
roughness = 0.52

[sub_resource type="BoxMesh" id="BodyMesh"]
size = Vector3(0.52, 1.02, 0.42)

[sub_resource type="CylinderMesh" id="ConeMesh"]
top_radius = 0.12
bottom_radius = 0.15
height = 0.045
radial_segments = 18

[sub_resource type="BoxMesh" id="FootMesh"]
size = Vector3(0.40, 0.08, 0.34)

[node name="BeatboxSpeaker3D" type="Node3D"]
script = ExtResource("1_script")
animation_kind = "speaker"
animation_speed = 1.0
animation_amplitude = 0.055

[node name="Body" type="MeshInstance3D" parent="."]
position = Vector3(0, 0.51, 0)
mesh = SubResource("BodyMesh")
material_override = SubResource("MatBody")

[node name="Glow" type="MeshInstance3D" parent="."]
position = Vector3(0, 0.63, 0.235)
rotation = Vector3(1.5708, 0, 0)
mesh = SubResource("ConeMesh")
material_override = SubResource("MatGlow")

[node name="Foot" type="MeshInstance3D" parent="."]
position = Vector3(0, 0.04, 0)
mesh = SubResource("FootMesh")
material_override = SubResource("MatBody")

[node name="BeatLight" type="OmniLight3D" parent="."]
position = Vector3(0, 0.63, 0.34)
light_color = Color(0.62, 0.25, 1, 1)
light_energy = 0.24
omni_range = 1.9
shadow_enabled = false
'''

write(ENV_DIR / "firefly_field_3d.tscn", FIREFLY_SCENE)
write(ENV_DIR / "spore_mist_patch_3d.tscn", MIST_SCENE)
write(ENV_DIR / "garden_lantern_3d.tscn", LANTERN_SCENE)
write(ENV_DIR / "beatbox_speaker_3d.tscn", SPEAKER_SCENE)

# Add the tiny reusable living component to already-authored props.
add_script_to_scene(
    ENV_DIR / "forest_tree_3d.tscn",
    "res://scripts/environment/spore_living_prop_3d.gd",
    "tree",
    0.62,
    0.028,
)
add_script_to_scene(
    ENV_DIR / "mushroom_cluster_3d.tscn",
    "res://scripts/environment/spore_living_prop_3d.gd",
    "mushroom",
    0.80,
    0.040,
)
add_script_to_scene(
    ENV_DIR / "spore_crystal_3d.tscn",
    "res://scripts/environment/spore_living_prop_3d.gd",
    "crystal",
    0.72,
    0.035,
)
add_script_to_scene(
    ENV_DIR / "crown_shrine_3d.tscn",
    "res://scripts/environment/spore_living_prop_3d.gd",
    "shrine",
    0.66,
    0.038,
)

# -----------------------------------------------------------------------------
# Mission 1 authored ambience instances.
# -----------------------------------------------------------------------------
dressing = DRESSING.read_text(encoding="utf-8")

if 'path="res://scenes/environment/firefly_field_3d.tscn"' not in dressing:
    header = re.search(r'^\[gd_scene[^\n]*\]\n', dressing)
    if not header:
        raise RuntimeError("Invalid mission_1_dressing.tscn header")
    ext = '''
[ext_resource type="PackedScene" path="res://scenes/environment/firefly_field_3d.tscn" id="90_fireflies"]
[ext_resource type="PackedScene" path="res://scenes/environment/spore_mist_patch_3d.tscn" id="91_mist"]
[ext_resource type="PackedScene" path="res://scenes/environment/garden_lantern_3d.tscn" id="92_lantern"]
[ext_resource type="PackedScene" path="res://scenes/environment/beatbox_speaker_3d.tscn" id="93_speaker"]
'''
    dressing = dressing[:header.end()] + ext + dressing[header.end():]

# Replace the old raw speaker blocks with reusable instances if present.
speaker_pattern = re.compile(
    r'(?ms)^\[node name="SpeakerLeft" type="MeshInstance3D" parent="SetPieces"\].*?(?=^\[node name="SpeakerRight" type="MeshInstance3D" parent="SetPieces"\])'
    r'|^\[node name="SpeakerRight" type="MeshInstance3D" parent="SetPieces"\].*?(?=\Z)'
)
# Do targeted trimming instead because the scene may have future nodes after speakers.
start_left = dressing.find('[node name="SpeakerLeft" type="MeshInstance3D" parent="SetPieces"]')
if start_left >= 0:
    # Current immersive garden file ends with SpeakerRightGlow. Remove from SpeakerLeft to EOF.
    dressing = dressing[:start_left].rstrip() + "\n\n"

if '[node name="AmbientLife" type="Node3D" parent="."]' not in dressing:
    ambience = r'''[node name="SpeakerLeft" parent="SetPieces" instance=ExtResource("93_speaker")]
position = Vector3(5.25, 0.0, -5.95)
rotation = Vector3(0, 0.18, 0)
phase_offset = 0.0

[node name="SpeakerRight" parent="SetPieces" instance=ExtResource("93_speaker")]
position = Vector3(7.30, 0.0, -5.92)
rotation = Vector3(0, -0.18, 0)
phase_offset = 1.20

[node name="AmbientLife" type="Node3D" parent="."]

[node name="FirefliesNorthWest" parent="AmbientLife" instance=ExtResource("90_fireflies")]
position = Vector3(-4.8, 0.0, -4.3)
amount = 7
radius = 2.2
height = 1.75
seed_value = 113

[node name="FirefliesCrown" parent="AmbientLife" instance=ExtResource("90_fireflies")]
position = Vector3(5.8, 0.0, -4.4)
amount = 6
radius = 1.7
height = 1.45
glow_color = Color(1.0, 0.76, 0.32, 1.0)
seed_value = 227
drift_speed = 0.42

[node name="FirefliesSouthWest" parent="AmbientLife" instance=ExtResource("90_fireflies")]
position = Vector3(-5.1, 0.0, 4.7)
amount = 6
radius = 1.8
height = 1.6
seed_value = 331

[node name="MistHazardA" parent="AmbientLife" instance=ExtResource("91_mist")]
position = Vector3(-2.1, 0.10, -2.1)
width = 1.0

[node name="MistHazardB" parent="AmbientLife" instance=ExtResource("91_mist")]
position = Vector3(0.7, 0.10, -0.7)
width = 1.0
mist_color = Color(0.44, 0.18, 0.66, 0.15)

[node name="MistHazardC" parent="AmbientLife" instance=ExtResource("91_mist")]
position = Vector3(2.1, 0.10, 2.1)
width = 1.0
mist_color = Color(0.36, 0.18, 0.58, 0.14)

[node name="MistHazardD" parent="AmbientLife" instance=ExtResource("91_mist")]
position = Vector3(3.5, 0.10, 3.5)
width = 0.9
mist_color = Color(0.40, 0.18, 0.62, 0.14)

[node name="ExitLanternA" parent="AmbientLife" instance=ExtResource("92_lantern")]
position = Vector3(-6.25, 0.0, 4.72)
phase_offset = 0.1

[node name="ExitLanternB" parent="AmbientLife" instance=ExtResource("92_lantern")]
position = Vector3(-5.15, 0.0, 5.65)
scale = Vector3(0.86, 0.86, 0.86)
phase_offset = 1.0

[node name="GateLantern" parent="AmbientLife" instance=ExtResource("92_lantern")]
position = Vector3(-0.10, 0.0, 4.35)
scale = Vector3(0.72, 0.72, 0.72)
phase_offset = 2.0
'''
    dressing = dressing.rstrip() + "\n\n" + ambience + "\n"

DRESSING.write_text(dressing, encoding="utf-8", newline="\n")

print("[OK] Mission 1 living ambience pass applied.")
print()
print("Reusable Godot components added:")
print("  scripts/environment/spore_living_prop_3d.gd")
print("  scripts/environment/spore_firefly_field_3d.gd")
print("  scripts/environment/spore_mist_patch_3d.gd")
print("  scenes/environment/firefly_field_3d.tscn")
print("  scenes/environment/spore_mist_patch_3d.tscn")
print("  scenes/environment/garden_lantern_3d.tscn")
print("  scenes/environment/beatbox_speaker_3d.tscn")
print()
print("Mission 1 ambience:")
print("  - very subtle tree canopy sway")
print("  - mushroom breathing")
print("  - crystal + crown shrine light pulses")
print("  - reusable Beatbox speakers with restrained pulse")
print("  - three sparse firefly fields")
print("  - low decorative violet mist on authored hazard locations")
print("  - green mushroom lanterns near exit / gate")
print()
print("All ambience objects are visible/selectable as scene instances in Godot.")
print("No tactical cells, movement rules, cover, LOS, damage or mission logic are changed.")
print()
print("Backup:")
print("  scenes/environment/mission_1_dressing.tscn.living_ambience_backup")
