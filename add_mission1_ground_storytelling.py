#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
SCRIPT_DIR = ROOT / "scripts" / "environment"
ENV_DIR = ROOT / "scenes" / "environment"
DRESSING = ENV_DIR / "mission_1_dressing.tscn"

if not DRESSING.exists():
    print("[ERROR] scenes/environment/mission_1_dressing.tscn not found.")
    print("Run first: python beautify_mission1_immersive_garden.py")
    sys.exit(1)

SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
ENV_DIR.mkdir(parents=True, exist_ok=True)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def backup(path: Path) -> None:
    out = path.with_suffix(path.suffix + ".ground_story_backup")
    if not out.exists():
        out.write_bytes(path.read_bytes())


GROUND_SCRIPT = r'''@tool
class_name SporeGroundDetailPatch3D
extends Node3D

## Editor-visible, non-gameplay ground dressing.
## One reusable component for moss, dirt, stones, roots, flowers and leaves.

@export_group("Patch")
@export_enum("moss", "dirt", "stones", "roots", "flowers", "leaves") var patch_kind: String = "moss":
	set(value):
		patch_kind = value
		_queue_rebuild()
@export_range(0.20, 2.40, 0.05) var radius: float = 0.75:
	set(value):
		radius = maxf(0.20, value)
		_queue_rebuild()
@export_range(1, 14, 1) var density: int = 5:
	set(value):
		density = clampi(value, 1, 14)
		_queue_rebuild()
@export_range(0, 99999, 1) var seed_value: int = 1:
	set(value):
		seed_value = maxi(0, value)
		_queue_rebuild()
@export_range(0.25, 1.50, 0.05) var visual_strength: float = 0.82:
	set(value):
		visual_strength = clampf(value, 0.25, 1.50)
		_queue_rebuild()

@export_group("Palette")
@export var moss_color: Color = Color("#496643"):
	set(value):
		moss_color = value
		_queue_rebuild()
@export var dirt_color: Color = Color("#4c3b29"):
	set(value):
		dirt_color = value
		_queue_rebuild()
@export var stone_color: Color = Color("#687064"):
	set(value):
		stone_color = value
		_queue_rebuild()
@export var root_color: Color = Color("#59402c"):
	set(value):
		root_color = value
		_queue_rebuild()
@export var flower_color: Color = Color("#e9b9e8"):
	set(value):
		flower_color = value
		_queue_rebuild()
@export var leaf_color: Color = Color("#79653c"):
	set(value):
		leaf_color = value
		_queue_rebuild()

var _rebuild_queued: bool = false


func _ready() -> void:
	_rebuild()


func _queue_rebuild() -> void:
	if not is_inside_tree() or _rebuild_queued:
		return
	_rebuild_queued = true
	call_deferred("_apply_rebuild")


func _apply_rebuild() -> void:
	_rebuild_queued = false
	_rebuild()


func _rebuild() -> void:
	var generated: Node3D = get_node_or_null("_Generated") as Node3D
	if generated != null:
		generated.free()
	generated = Node3D.new()
	generated.name = "_Generated"
	add_child(generated, false, Node.INTERNAL_MODE_BACK)

	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value * 1009 + 17

	match patch_kind:
		"dirt":
			_build_flat_patch(generated, rng, dirt_color, false)
		"stones":
			_build_stones(generated, rng)
		"roots":
			_build_roots(generated, rng)
		"flowers":
			_build_flowers(generated, rng)
		"leaves":
			_build_leaves(generated, rng)
		_:
			_build_flat_patch(generated, rng, moss_color, true)


func _build_flat_patch(parent: Node3D, rng: RandomNumberGenerator, color: Color, moss: bool) -> void:
	var count: int = maxi(2, density)
	for index: int in range(count):
		var disc := MeshInstance3D.new()
		var mesh := CylinderMesh.new()
		var local_radius: float = radius * rng.randf_range(0.24, 0.52)
		mesh.top_radius = local_radius
		mesh.bottom_radius = local_radius * rng.randf_range(0.92, 1.08)
		mesh.height = 0.014 if moss else 0.010
		mesh.radial_segments = 10
		disc.mesh = mesh
		disc.position = Vector3(
			rng.randf_range(-radius * 0.62, radius * 0.62),
			0.010 + float(index % 3) * 0.001,
			rng.randf_range(-radius * 0.62, radius * 0.62)
		)
		disc.scale.z = rng.randf_range(0.55, 1.20)
		disc.rotation.y = rng.randf_range(-PI, PI)
		var shade: float = rng.randf_range(-0.055, 0.055)
		disc.material_override = _material(color.lightened(shade) if shade >= 0.0 else color.darkened(-shade), 0.88 if moss else 0.98, 0.72 * visual_strength)
		parent.add_child(disc)


func _build_stones(parent: Node3D, rng: RandomNumberGenerator) -> void:
	for index: int in range(density):
		var stone := MeshInstance3D.new()
		var mesh := SphereMesh.new()
		mesh.radius = 0.5
		mesh.height = 1.0
		mesh.radial_segments = 8
		mesh.rings = 4
		stone.mesh = mesh
		var size: float = rng.randf_range(0.09, 0.19) * visual_strength
		stone.scale = Vector3(size * rng.randf_range(0.9, 1.35), size * rng.randf_range(0.45, 0.8), size)
		stone.position = _random_xz(rng, radius * 0.72, size * 0.35)
		stone.rotation.y = rng.randf_range(-PI, PI)
		var stone_shade: float = rng.randf_range(-0.02, 0.08)
		var resolved_stone: Color = stone_color.lightened(stone_shade) if stone_shade >= 0.0 else stone_color.darkened(-stone_shade)
		stone.material_override = _material(resolved_stone, 0.96, 1.0)
		parent.add_child(stone)


func _build_roots(parent: Node3D, rng: RandomNumberGenerator) -> void:
	for index: int in range(maxi(2, density / 2)):
		var root := MeshInstance3D.new()
		var mesh := CylinderMesh.new()
		mesh.top_radius = 0.025 * visual_strength
		mesh.bottom_radius = 0.045 * visual_strength
		mesh.height = rng.randf_range(0.55, 1.05) * radius
		mesh.radial_segments = 7
		root.mesh = mesh
		root.position = _random_xz(rng, radius * 0.54, 0.035)
		root.rotation = Vector3(PI * 0.5, rng.randf_range(-PI, PI), rng.randf_range(-0.08, 0.08))
		root.material_override = _material(root_color.lightened(rng.randf_range(-0.03, 0.05)), 1.0, 1.0)
		parent.add_child(root)


func _build_flowers(parent: Node3D, rng: RandomNumberGenerator) -> void:
	for index: int in range(density):
		var flower := Node3D.new()
		flower.position = _random_xz(rng, radius * 0.70, 0.0)
		parent.add_child(flower)
		var height: float = rng.randf_range(0.08, 0.16) * visual_strength
		var stem := MeshInstance3D.new()
		var stem_mesh := CylinderMesh.new()
		stem_mesh.top_radius = 0.008
		stem_mesh.bottom_radius = 0.012
		stem_mesh.height = height
		stem_mesh.radial_segments = 6
		stem.mesh = stem_mesh
		stem.position.y = height * 0.5
		stem.material_override = _material(Color("#557348"), 0.95, 1.0)
		flower.add_child(stem)
		var bloom := MeshInstance3D.new()
		var bloom_mesh := SphereMesh.new()
		bloom_mesh.radius = 0.5
		bloom_mesh.height = 1.0
		bloom_mesh.radial_segments = 7
		bloom_mesh.rings = 4
		bloom.mesh = bloom_mesh
		bloom.scale = Vector3(0.055, 0.025, 0.055) * visual_strength
		bloom.position.y = height
		var bloom_shade: float = rng.randf_range(-0.03, 0.10)
		var bloom_color: Color = flower_color.lightened(bloom_shade) if bloom_shade >= 0.0 else flower_color.darkened(-bloom_shade)
		bloom.material_override = _material(bloom_color, 0.76, 1.0, true)
		flower.add_child(bloom)


func _build_leaves(parent: Node3D, rng: RandomNumberGenerator) -> void:
	for index: int in range(density * 2):
		var leaf := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = Vector3(rng.randf_range(0.05, 0.10), 0.008, rng.randf_range(0.025, 0.05)) * visual_strength
		leaf.mesh = mesh
		leaf.position = _random_xz(rng, radius * 0.75, 0.014)
		leaf.rotation.y = rng.randf_range(-PI, PI)
		var palette: Color = leaf_color
		if index % 3 == 1:
			palette = Color("#5d6937")
		elif index % 3 == 2:
			palette = Color("#8b5b36")
		leaf.material_override = _material(palette, 1.0, 0.95)
		parent.add_child(leaf)


func _random_xz(rng: RandomNumberGenerator, spread: float, y: float) -> Vector3:
	var angle: float = rng.randf_range(-PI, PI)
	var distance: float = sqrt(rng.randf()) * spread
	return Vector3(cos(angle) * distance, y, sin(angle) * distance)


func _material(color: Color, roughness: float, alpha: float, emissive: bool = false) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(color.r, color.g, color.b, clampf(alpha, 0.0, 1.0))
	material.roughness = roughness
	if alpha < 0.999:
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_OPAQUE_ONLY
	if emissive:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.12
	return material
'''

GROUND_SCENE = r'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/environment/spore_ground_detail_patch_3d.gd" id="1_script"]

[node name="GroundDetailPatch3D" type="Node3D"]
script = ExtResource("1_script")
'''

write(SCRIPT_DIR / "spore_ground_detail_patch_3d.gd", GROUND_SCRIPT)
write(ENV_DIR / "ground_detail_patch_3d.tscn", GROUND_SCENE)

backup(DRESSING)
dressing = DRESSING.read_text(encoding="utf-8")

if 'path="res://scenes/environment/ground_detail_patch_3d.tscn"' not in dressing:
    header = re.search(r'^\[gd_scene load_steps=(\d+) format=3\]\n', dressing)
    if not header:
        raise RuntimeError("Invalid mission_1_dressing.tscn header")
    steps = int(header.group(1)) + 1
    dressing = dressing[:header.start()] + f'[gd_scene load_steps={steps} format=3]\n' + dressing[header.end():]

    insert_after = '[ext_resource type="PackedScene" path="res://scenes/environment/crown_shrine_3d.tscn" id="5_shrine"]\n'
    ext = '[ext_resource type="PackedScene" path="res://scenes/environment/ground_detail_patch_3d.tscn" id="96_ground"]\n'
    if insert_after in dressing:
        dressing = dressing.replace(insert_after, insert_after + ext, 1)
    else:
        first_sub = dressing.find('[sub_resource')
        dressing = dressing[:first_sub] + ext + '\n' + dressing[first_sub:]

if '[node name="GroundDetails" type="Node3D" parent="."]' not in dressing:
    ground_nodes = r'''
[node name="GroundDetails" type="Node3D" parent="."]

; --- visual path: exit -> switch/gate -> garden -> crown ---
[node name="Path_Exit_A" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-5.85, 0.055, 3.55)
rotation = Vector3(0, 0.08, 0)
patch_kind = "dirt"
radius = 0.78
density = 5
seed_value = 101
visual_strength = 0.66

[node name="Path_Exit_B" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-4.55, 0.055, 3.42)
rotation = Vector3(0, -0.18, 0)
patch_kind = "dirt"
radius = 0.72
density = 4
seed_value = 102
visual_strength = 0.62

[node name="Path_Switch" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-3.35, 0.055, 3.52)
rotation = Vector3(0, 0.20, 0)
patch_kind = "dirt"
radius = 0.68
density = 4
seed_value = 103
visual_strength = 0.62

[node name="Path_Gate_A" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-1.75, 0.055, 3.48)
rotation = Vector3(0, -0.11, 0)
patch_kind = "dirt"
radius = 0.72
density = 4
seed_value = 104
visual_strength = 0.60

[node name="Path_Gate_B" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-0.25, 0.055, 3.46)
rotation = Vector3(0, 0.13, 0)
patch_kind = "dirt"
radius = 0.70
density = 4
seed_value = 105
visual_strength = 0.59

[node name="Path_Inside_A" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(0.95, 0.055, 2.85)
rotation = Vector3(0, 0.55, 0)
patch_kind = "dirt"
radius = 0.66
density = 4
seed_value = 106
visual_strength = 0.57

[node name="Path_Inside_B" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(1.55, 0.055, 1.55)
rotation = Vector3(0, 0.38, 0)
patch_kind = "dirt"
radius = 0.64
density = 4
seed_value = 107
visual_strength = 0.55

[node name="Path_Inside_C" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(2.65, 0.055, 0.35)
rotation = Vector3(0, 0.68, 0)
patch_kind = "dirt"
radius = 0.62
density = 4
seed_value = 108
visual_strength = 0.52

[node name="Path_Crown_A" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(4.05, 0.055, -1.25)
rotation = Vector3(0, 0.62, 0)
patch_kind = "dirt"
radius = 0.64
density = 4
seed_value = 109
visual_strength = 0.52

[node name="Path_Crown_B" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(5.10, 0.055, -2.95)
rotation = Vector3(0, 0.38, 0)
patch_kind = "dirt"
radius = 0.62
density = 4
seed_value = 110
visual_strength = 0.50

; --- moss breaks the square silhouette of the diorama ---
[node name="Moss_NW" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-5.85, 0.058, -4.55)
patch_kind = "moss"
radius = 0.92
density = 6
seed_value = 201
visual_strength = 0.85

[node name="Moss_N" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-1.55, 0.058, -4.63)
rotation = Vector3(0, -0.32, 0)
patch_kind = "moss"
radius = 0.88
density = 6
seed_value = 202
visual_strength = 0.78

[node name="Moss_NE" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(3.35, 0.058, -4.38)
rotation = Vector3(0, 0.20, 0)
patch_kind = "moss"
radius = 0.82
density = 5
seed_value = 203
visual_strength = 0.72

[node name="Moss_SW" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-5.35, 0.058, 4.42)
rotation = Vector3(0, 0.44, 0)
patch_kind = "moss"
radius = 0.86
density = 6
seed_value = 204
visual_strength = 0.80

[node name="Moss_SE" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(4.35, 0.058, 4.42)
rotation = Vector3(0, -0.26, 0)
patch_kind = "moss"
radius = 0.78
density = 5
seed_value = 205
visual_strength = 0.70

; --- environmental storytelling clusters ---
[node name="Roots_West" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-6.05, 0.060, 0.15)
rotation = Vector3(0, 0.55, 0)
patch_kind = "roots"
radius = 0.82
density = 6
seed_value = 301
visual_strength = 0.82

[node name="Roots_North" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(0.25, 0.060, -4.58)
rotation = Vector3(0, -0.35, 0)
patch_kind = "roots"
radius = 0.76
density = 5
seed_value = 302
visual_strength = 0.72

[node name="Stones_Chest" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(3.80, 0.060, -2.05)
patch_kind = "stones"
radius = 0.62
density = 5
seed_value = 401
visual_strength = 0.72

[node name="Stones_Gate" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(0.35, 0.060, 4.18)
patch_kind = "stones"
radius = 0.58
density = 4
seed_value = 402
visual_strength = 0.68

[node name="Flowers_Exit" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-6.00, 0.060, 4.26)
patch_kind = "flowers"
radius = 0.66
density = 5
seed_value = 501
flower_color = Color(0.66, 0.91, 0.69, 1)
visual_strength = 0.72

[node name="Flowers_Crown" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(5.55, 0.060, -4.05)
patch_kind = "flowers"
radius = 0.58
density = 4
seed_value = 502
flower_color = Color(0.95, 0.69, 0.32, 1)
visual_strength = 0.68

[node name="Leaves_West" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(-5.65, 0.060, -1.75)
rotation = Vector3(0, 0.25, 0)
patch_kind = "leaves"
radius = 0.74
density = 5
seed_value = 601
visual_strength = 0.72

[node name="Leaves_East" parent="GroundDetails" instance=ExtResource("96_ground")]
position = Vector3(5.75, 0.060, 1.80)
rotation = Vector3(0, -0.30, 0)
patch_kind = "leaves"
radius = 0.70
density = 5
seed_value = 602
visual_strength = 0.66
'''

    # Put the authored ground pass before set pieces when possible, otherwise append.
    marker = '[node name="SetPieces" type="Node3D" parent="."]'
    if marker in dressing:
        dressing = dressing.replace(marker, ground_nodes.rstrip() + '\n\n' + marker, 1)
    else:
        dressing = dressing.rstrip() + '\n\n' + ground_nodes.strip() + '\n'

DRESSING.write_text(dressing, encoding="utf-8", newline="\n")

print("[OK] Mission 1 ground storytelling pass applied.")
print()
print("Created:")
print("  scripts/environment/spore_ground_detail_patch_3d.gd")
print("  scenes/environment/ground_detail_patch_3d.tscn")
print()
print("Added to mission_1_dressing.tscn:")
print("  - subtle dirt route from extraction/gate toward the crown")
print("  - moss patches that break up the square grid silhouette")
print("  - roots / stones / leaves around authored points")
print("  - flowers at exit and crown landmarks")
print()
print("All patches are editor-visible scene instances and non-gameplay.")
print("Backup: mission_1_dressing.tscn.ground_story_backup")
