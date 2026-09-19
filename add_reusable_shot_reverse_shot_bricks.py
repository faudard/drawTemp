#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()

FILES = {
    "actor": ROOT / "scripts/maps/spore_unit_actor_3d.gd",
    "action": ROOT / "scripts/data/battle_action_definition.gd",
    "runner": ROOT / "scripts/presentation/spore_cinematic_player_3d.gd",
    "board": ROOT / "scripts/prototypes/spore_battle_board_3d.gd",
    "editor": ROOT / "addons/sporebound_studio/cinematic_editor.gd",
}

for key, path in FILES.items():
    if not path.exists():
        print(f"[ERROR] Missing {key}: {path}")
        print("Run this patch after refactor_cinematics_3d_jrpg.py from the drawTemp repository root.")
        sys.exit(1)


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".shot_bricks_backup")
    if not target.exists():
        target.write_bytes(path.read_bytes())


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup(path)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def insert_before(text: str, function_name: str, code: str, marker: str) -> str:
    if marker in text:
        return text
    needle = f"func {function_name}("
    pos = text.find(needle)
    if pos < 0:
        raise RuntimeError(f"Cannot find insertion point before {function_name}")
    return text[:pos] + code.rstrip() + "\n\n\n" + text[pos:]


for path in FILES.values():
    backup(path)

# -----------------------------------------------------------------------------
# Reusable Godot resources: one asset = one camera shot.
# -----------------------------------------------------------------------------
SHOT_DEF = r'''@tool
class_name SporeCinematicShotDefinition
extends Resource

## Reusable 3D cinematic framing asset.
## Edit .tres instances in the Godot Inspector instead of hard-coding camera values.

@export_group("Identity")
@export var id: String = "shot"
@export var display_name: String = "Shot"
@export_multiline var description: String = ""

@export_group("Framing")
@export_enum("center", "head", "feet") var target_anchor: String = "head"
@export_range(5.0, 18.0, 0.1) var camera_distance: float = 7.8
@export_range(3.0, 16.0, 0.1) var camera_height: float = 7.2
@export_range(-90.0, 90.0, 1.0) var shoulder_angle_degrees: float = 18.0
@export_range(-1.5, 1.5, 0.05) var lateral_offset: float = 0.30
@export_range(-1.0, 1.0, 0.05) var depth_offset: float = 0.0

@export_group("Transition")
@export var instant_cut: bool = true
@export_range(0.0, 1.5, 0.05) var transition_seconds: float = 0.0


func summary() -> String:
	return "%s • dist %.1f • h %.1f • épaule %.0f°" % [
		display_name,
		camera_distance,
		camera_height,
		shoulder_angle_degrees,
	]
'''

SHOT_SET_DEF = r'''@tool
class_name SporeCinematicShotSetDefinition
extends Resource

## A reusable shot/reverse-shot grammar.
## Shot A and Shot B are complementary dialogue framings; Wide is optional.

@export_group("Identity")
@export var id: String = "dialogue_default"
@export var display_name: String = "Dialogue — champ / contrechamp"

@export_group("Shots")
@export var shot_a: Resource
@export var shot_b: Resource
@export var wide_shot: Resource

@export_group("Automatic Dialogue")
@export var alternate_when_speaker_changes: bool = true
@export var use_wide_for_first_line: bool = false
@export_range(0.0, 1.0, 0.05) var pre_dialogue_hold: float = 0.06
'''

SHOT_CATALOG = r'''class_name SporeCinematicShotCatalog
extends RefCounted

const SHOT_DIR: String = "res://data/cinematic_shots/"

static var _cache: Dictionary = {}


static func definition(shot_id: String) -> Resource:
	if shot_id.is_empty() or shot_id in ["auto", "none"]:
		return null
	if _cache.has(shot_id):
		return _cache[shot_id]
	var path: String = SHOT_DIR + shot_id + ".tres"
	if not ResourceLoader.exists(path):
		return null
	var data: Resource = load(path) as Resource
	if data != null:
		_cache[shot_id] = data
	return data


static func ids() -> Array[String]:
	var result: Array[String] = []
	var directory: DirAccess = DirAccess.open(SHOT_DIR)
	if directory == null:
		return result
	for file_name: String in directory.get_files():
		if not file_name.ends_with(".tres"):
			continue
		if file_name == "dialogue_default_set.tres":
			continue
		var path: String = SHOT_DIR + file_name
		var data: Resource = load(path) as Resource
		if data == null:
			continue
		var shot_id: String = String(data.get("id"))
		if not shot_id.is_empty():
			result.append(shot_id)
	result.sort()
	return result


static func clear_cache() -> void:
	_cache.clear()
'''

TARGET_SCRIPT = r'''@tool
class_name SporeCinematicTarget3D
extends Node3D

## Reusable focus anchors attached to a battle actor.
## The .tscn owns the Marker3D positions so framing can evolve visually in Godot.


func anchor_global(anchor_name: String) -> Vector3:
	var wanted: String = anchor_name.to_lower()
	var marker_name: String = "Center"
	match wanted:
		"head":
			marker_name = "Head"
		"feet":
			marker_name = "Feet"
		_:
			marker_name = "Center"
	var marker: Marker3D = get_node_or_null(marker_name) as Marker3D
	return marker.global_position if marker != null else global_position
'''

TARGET_SCENE = r'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/components/spore_cinematic_target_3d.gd" id="1_script"]

[node name="CinematicTarget3D" type="Node3D"]
script = ExtResource("1_script")

[node name="Feet" type="Marker3D" parent="."]
position = Vector3(0, 0.12, 0)

[node name="Center" type="Marker3D" parent="."]
position = Vector3(0, 0.72, 0)

[node name="Head" type="Marker3D" parent="."]
position = Vector3(0, 1.28, 0)
'''

SHOW_1 = r'''[gd_resource type="Resource" script_class="SporeCinematicShotDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/data/cinematic_shot_definition.gd" id="1_shot"]

[resource]
script = ExtResource("1_shot")
id = "show_1"
display_name = "SHOW 1 — Champ"
description = "Plan dialogue épaule A, sujet légèrement décentré."
target_anchor = "head"
camera_distance = 7.7
camera_height = 7.0
shoulder_angle_degrees = -18.0
lateral_offset = 0.34
depth_offset = 0.0
instant_cut = true
transition_seconds = 0.0
'''

SHOW_2 = r'''[gd_resource type="Resource" script_class="SporeCinematicShotDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/data/cinematic_shot_definition.gd" id="1_shot"]

[resource]
script = ExtResource("1_shot")
id = "show_2"
display_name = "SHOW 2 — Contrechamp"
description = "Plan dialogue complémentaire au SHOW 1."
target_anchor = "head"
camera_distance = 7.7
camera_height = 7.0
shoulder_angle_degrees = 18.0
lateral_offset = -0.34
depth_offset = 0.0
instant_cut = true
transition_seconds = 0.0
'''

SHOW_WIDE = r'''[gd_resource type="Resource" script_class="SporeCinematicShotDefinition" load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/data/cinematic_shot_definition.gd" id="1_shot"]

[resource]
script = ExtResource("1_shot")
id = "show_wide"
display_name = "SHOW WIDE — Plan d'ensemble"
description = "Plan large de respiration ou d'installation."
target_anchor = "center"
camera_distance = 11.2
camera_height = 9.2
shoulder_angle_degrees = 0.0
lateral_offset = 0.0
depth_offset = 0.0
instant_cut = true
transition_seconds = 0.0
'''

SHOT_SET = r'''[gd_resource type="Resource" script_class="SporeCinematicShotSetDefinition" load_steps=5 format=3]

[ext_resource type="Script" path="res://scripts/data/cinematic_shot_set_definition.gd" id="1_set"]
[ext_resource type="Resource" path="res://data/cinematic_shots/show_1.tres" id="2_a"]
[ext_resource type="Resource" path="res://data/cinematic_shots/show_2.tres" id="3_b"]
[ext_resource type="Resource" path="res://data/cinematic_shots/show_wide.tres" id="4_wide"]

[resource]
script = ExtResource("1_set")
id = "dialogue_default"
display_name = "Dialogue — champ / contrechamp"
shot_a = ExtResource("2_a")
shot_b = ExtResource("3_b")
wide_shot = ExtResource("4_wide")
alternate_when_speaker_changes = true
use_wide_for_first_line = false
pre_dialogue_hold = 0.06
'''

write(ROOT / "scripts/data/cinematic_shot_definition.gd", SHOT_DEF)
write(ROOT / "scripts/data/cinematic_shot_set_definition.gd", SHOT_SET_DEF)
write(ROOT / "scripts/catalogs/cinematic_shot_catalog.gd", SHOT_CATALOG)
write(ROOT / "scripts/components/spore_cinematic_target_3d.gd", TARGET_SCRIPT)
write(ROOT / "scenes/components/cinematic_target_3d.tscn", TARGET_SCENE)
write(ROOT / "data/cinematic_shots/show_1.tres", SHOW_1)
write(ROOT / "data/cinematic_shots/show_2.tres", SHOW_2)
write(ROOT / "data/cinematic_shots/show_wide.tres", SHOW_WIDE)
write(ROOT / "data/cinematic_shots/dialogue_default_set.tres", SHOT_SET)

# -----------------------------------------------------------------------------
# Attach the reusable CinematicTarget3D scene to every runtime unit.
# -----------------------------------------------------------------------------
actor = FILES["actor"].read_text(encoding="utf-8")

if 'const CinematicTargetScene = preload("res://scenes/components/cinematic_target_3d.tscn")' not in actor:
    preload_anchor = 'const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")\n'
    if preload_anchor not in actor:
        raise RuntimeError("Could not find actor preload insertion point")
    actor = actor.replace(
        preload_anchor,
        preload_anchor + 'const CinematicTargetScene = preload("res://scenes/components/cinematic_target_3d.tscn")\n',
        1,
    )

if 'var _cinematic_target: SporeCinematicTarget3D' not in actor:
    var_anchor = 'var _status_vfx_root: Node3D\n'
    if var_anchor not in actor:
        raise RuntimeError("Could not find actor variable insertion point")
    actor = actor.replace(
        var_anchor,
        var_anchor + 'var _cinematic_target: SporeCinematicTarget3D\n',
        1,
    )

ensure_pattern = re.compile(r'(?ms)^func _ensure_visual_nodes\(\) -> void:\n.*?(?=^func |\Z)')
em = ensure_pattern.search(actor)
if not em:
    raise RuntimeError("Actor _ensure_visual_nodes() not found")
ensure_func = em.group(0)
if 'CinematicTargetScene.instantiate()' not in ensure_func:
    first_newline = ensure_func.find('\n')
    addition = '''\tif _cinematic_target == null:
\t\t_cinematic_target = get_node_or_null("CinematicTarget3D") as SporeCinematicTarget3D
\tif _cinematic_target == null:
\t\tvar target_instance: Node = CinematicTargetScene.instantiate()
\t\tif target_instance is SporeCinematicTarget3D:
\t\t\t_cinematic_target = target_instance as SporeCinematicTarget3D
\t\t\tadd_child(_cinematic_target)

'''
    ensure_func = ensure_func[:first_newline + 1] + addition + ensure_func[first_newline + 1:]
    actor = actor[:em.start()] + ensure_func + actor[em.end():]

anchor_method = '''func cinematic_anchor_global(anchor_name: String = "head") -> Vector3:
\t_ensure_visual_nodes()
\tif _cinematic_target != null:
\t\treturn _cinematic_target.anchor_global(anchor_name)
\treturn global_position
'''
actor = insert_before(actor, "begin_activation", anchor_method, "func cinematic_anchor_global(")
FILES["actor"].write_text(actor, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Action data: refer to a preset ID, not camera numbers copied into every line.
# -----------------------------------------------------------------------------
action = FILES["action"].read_text(encoding="utf-8")

if '"camera_shot",' not in action:
    action = action.replace(
        '\t"camera_focus_unit",\n\t"camera_zoom",',
        '\t"camera_focus_unit",\n\t"camera_shot",\n\t"camera_zoom",',
        1,
    )

if 'var shot_preset_id:' not in action:
    anchor = '@export_range(1, 8, 1) var blip_every: int = 2\n'
    if anchor not in action:
        # Support speaker-profile patch versions where the new fields moved.
        anchor = '@export_range(0.0, 5.0, 0.05) var camera_duration: float = 0.35\n'
    if anchor not in action:
        raise RuntimeError("Could not find action cinematic property insertion point")
    action = action.replace(
        anchor,
        anchor + '@export var shot_preset_id: String = "auto"\n',
        1,
    )

FILES["action"].write_text(action, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Runtime cinematic player: automatic shot/reverse-shot using the ShotSet asset.
# -----------------------------------------------------------------------------
runner = FILES["runner"].read_text(encoding="utf-8")

if 'const ShotCatalog = preload("res://scripts/catalogs/cinematic_shot_catalog.gd")' not in runner:
    anchor = 'const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")\n'
    if anchor not in runner:
        raise RuntimeError("Runner catalog preload insertion point not found")
    runner = runner.replace(
        anchor,
        anchor + 'const ShotCatalog = preload("res://scripts/catalogs/cinematic_shot_catalog.gd")\n',
        1,
    )

if 'var dialogue_shot_set: Resource' not in runner:
    anchor = '@export_range(0, 8, 1) var max_nested_depth: int = 6\n'
    if anchor not in runner:
        raise RuntimeError("Runner export insertion point not found")
    runner = runner.replace(
        anchor,
        anchor + '@export var dialogue_shot_set: Resource = preload("res://data/cinematic_shots/dialogue_default_set.tres")\n',
        1,
    )

if 'var _last_dialogue_unit_id: String' not in runner:
    anchor = 'var _running: bool = false\n'
    if anchor not in runner:
        raise RuntimeError("Runner state insertion point not found")
    runner = runner.replace(
        anchor,
        anchor
        + 'var _last_dialogue_unit_id: String = ""\n'
        + 'var _last_dialogue_shot_id: String = ""\n',
        1,
    )

# Reset exchange state when playing a new cinematic.
play_pattern = re.compile(r'(?ms)^func play\(cinematic_id: String\) -> bool:\n.*?(?=^func |\Z)')
pm = play_pattern.search(runner)
if not pm:
    raise RuntimeError("Runner play() not found")
play_func = pm.group(0)
if '_last_dialogue_unit_id = ""' not in play_func:
    target = '\t_running = true\n'
    if target not in play_func:
        raise RuntimeError("Runner play() running marker not found")
    play_func = play_func.replace(
        target,
        target + '\t_last_dialogue_unit_id = ""\n\t_last_dialogue_shot_id = ""\n',
        1,
    )
    runner = runner[:pm.start()] + play_func + runner[pm.end():]

# Generic explicit camera_shot action.
if '"camera_shot":' not in runner:
    old = '''\t\t\t"camera_focus_unit":
\t\t\t\tvar unit_duration: float = float(action.get("camera_duration"))
\t\t\t\t_call_host("cinematic_3d_focus_unit", [String(action.get("unit_id")), float(action.get("camera_zoom")), unit_duration])
\t\t\t\tif unit_duration > 0.0:
\t\t\t\t\tawait get_tree().create_timer(unit_duration).timeout
'''
    if old not in runner:
        # Previous SHOW patch may have extended this section; insert before camera_zoom instead.
        anchor = '\t\t\t"camera_zoom":\n'
        if anchor not in runner:
            raise RuntimeError("Could not add camera_shot action to runner")
        add = '''\t\t\t"camera_shot":
\t\t\t\tvar explicit_shot: Resource = ShotCatalog.definition(String(action.get("shot_preset_id")))
\t\t\t\tif explicit_shot != null:
\t\t\t\t\t_call_host("cinematic_3d_apply_shot", [String(action.get("unit_id")), _last_dialogue_unit_id, explicit_shot])
\t\t\t\tvar shot_wait: float = maxf(float(action.get("camera_duration")), float(explicit_shot.get("transition_seconds")) if explicit_shot != null else 0.0)
\t\t\t\tif shot_wait > 0.0:
\t\t\t\t\tawait get_tree().create_timer(shot_wait).timeout
'''
        runner = runner.replace(anchor, add + anchor, 1)
    else:
        new = old + '''\t\t\t"camera_shot":
\t\t\t\tvar explicit_shot: Resource = ShotCatalog.definition(String(action.get("shot_preset_id")))
\t\t\t\tif explicit_shot != null:
\t\t\t\t\t_call_host("cinematic_3d_apply_shot", [String(action.get("unit_id")), _last_dialogue_unit_id, explicit_shot])
\t\t\t\tvar shot_wait: float = maxf(float(action.get("camera_duration")), float(explicit_shot.get("transition_seconds")) if explicit_shot != null else 0.0)
\t\t\t\tif shot_wait > 0.0:
\t\t\t\t\tawait get_tree().create_timer(shot_wait).timeout
'''
        runner = runner.replace(old, new, 1)

# Hook automatic shot before dialogue rendering.
dialogue_pattern = re.compile(r'(?ms)^func _play_dialogue\(action: Resource\) -> void:\n.*?(?=^func |\Z)')
dm = dialogue_pattern.search(runner)
if not dm:
    raise RuntimeError("Runner _play_dialogue() not found")
dialogue_func = dm.group(0)
if '_apply_dialogue_shot_reverse_shot' not in dialogue_func:
    # Insert after speaker/unit_id are known and speaker fallback completed.
    anchor = '\tif speaker.is_empty():\n\t\tspeaker = "Narrateur"\n'
    if anchor not in dialogue_func:
        raise RuntimeError("Runner dialogue speaker anchor not found")
    dialogue_func = dialogue_func.replace(
        anchor,
        anchor
        + '\n\tvar dialogue_shot_hold: float = _apply_dialogue_shot_reverse_shot(action, unit_id)\n'
        + '\tif dialogue_shot_hold > 0.0:\n'
        + '\t\tawait get_tree().create_timer(dialogue_shot_hold).timeout\n',
        1,
    )
    # update last speaker after line has been shown
    marker = '\tawait _dialogue.present_line(\n'
    if marker not in dialogue_func:
        raise RuntimeError("Runner present_line anchor not found")
    # We cannot insert after multiline call reliably here; last speaker can be set before await.
    dialogue_func = dialogue_func.replace(
        marker,
        '\t_last_dialogue_unit_id = unit_id\n\n' + marker,
        1,
    )
    runner = runner[:dm.start()] + dialogue_func + runner[dm.end():]

shot_helpers = '''func _apply_dialogue_shot_reverse_shot(action: Resource, unit_id: String) -> float:
\tif action == null or _host == null or unit_id.is_empty():
\t\treturn 0.0
\tif not _host.has_method("cinematic_3d_apply_shot"):
\t\treturn 0.0

\tvar requested_id: String = String(action.get("shot_preset_id"))
\tif requested_id == "none":
\t\treturn 0.0

\tvar shot: Resource = null
\tif not requested_id.is_empty() and requested_id != "auto":
\t\tshot = ShotCatalog.definition(requested_id)
\telse:
\t\tshot = _automatic_dialogue_shot(unit_id)

\tif shot == null:
\t\treturn 0.0

\t_host.call(
\t\t"cinematic_3d_apply_shot",
\t\tunit_id,
\t\t_last_dialogue_unit_id,
\t\tshot
\t)
\t_last_dialogue_shot_id = String(shot.get("id"))

\tvar hold: float = 0.0
\tif dialogue_shot_set != null:
\t\thold = float(dialogue_shot_set.get("pre_dialogue_hold"))
\tif not bool(shot.get("instant_cut")):
\t\thold = maxf(hold, float(shot.get("transition_seconds")))
\treturn hold


func _automatic_dialogue_shot(unit_id: String) -> Resource:
\tif dialogue_shot_set == null:
\t\treturn ShotCatalog.definition("show_1")

\tvar shot_a: Resource = dialogue_shot_set.get("shot_a") as Resource
\tvar shot_b: Resource = dialogue_shot_set.get("shot_b") as Resource
\tvar wide: Resource = dialogue_shot_set.get("wide_shot") as Resource

\tif _last_dialogue_unit_id.is_empty():
\t\tif bool(dialogue_shot_set.get("use_wide_for_first_line")) and wide != null:
\t\t\treturn wide
\t\treturn shot_a if shot_a != null else shot_b

\tif unit_id == _last_dialogue_unit_id:
\t\t# Same speaker keeps the same framing: no pointless camera ping-pong.
\t\tvar same: Resource = ShotCatalog.definition(_last_dialogue_shot_id)
\t\tif same != null:
\t\t\treturn same
\t\treturn shot_a

\tif not bool(dialogue_shot_set.get("alternate_when_speaker_changes")):
\t\treturn shot_a

\tvar shot_a_id: String = String(shot_a.get("id")) if shot_a != null else ""
\tif _last_dialogue_shot_id == shot_a_id:
\t\treturn shot_b if shot_b != null else shot_a
\treturn shot_a if shot_a != null else shot_b
'''
runner = insert_before(runner, "_resolve_portrait", shot_helpers, "func _apply_dialogue_shot_reverse_shot(")
FILES["runner"].write_text(runner, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Board: apply a reusable shot asset against speaker + previous interlocutor.
# -----------------------------------------------------------------------------
board = FILES["board"].read_text(encoding="utf-8")

# Cinematic camera height state.
if 'var _cinematic_camera_height: float' not in board:
    anchor = 'var _cinematic_camera_saved_distance: float = 12.5\n'
    if anchor not in board:
        raise RuntimeError("Cinematic camera state not found. Apply refactor_cinematics_3d_jrpg.py first.")
    board = board.replace(
        anchor,
        anchor
        + 'var _cinematic_camera_height: float = 11.0\n'
        + 'var _cinematic_camera_saved_height: float = 11.0\n',
        1,
    )

# Camera transform uses cinematic height while override is active.
old_height_line = '\t_camera.position = Vector3(0.0, camera_height, _camera_current_distance)\n'
if old_height_line in board and 'effective_camera_height' not in board:
    board = board.replace(
        old_height_line,
        '\tvar effective_camera_height: float = _cinematic_camera_height if _cinematic_camera_active else camera_height\n'
        '\t_camera.position = Vector3(0.0, effective_camera_height, _camera_current_distance)\n',
        1,
    )

# Save/restore height in existing override helpers.
begin_pattern = re.compile(r'(?ms)^func _begin_cinematic_camera_override_3d\(\) -> void:\n.*?(?=^func |\Z)')
bm = begin_pattern.search(board)
if not bm:
    raise RuntimeError("_begin_cinematic_camera_override_3d() not found")
begin_func = bm.group(0)
if '_cinematic_camera_saved_height' not in begin_func:
    begin_func = begin_func.replace(
        '\t_cinematic_camera_saved_distance = _camera_target_distance\n',
        '\t_cinematic_camera_saved_distance = _camera_target_distance\n'
        '\t_cinematic_camera_saved_height = camera_height\n'
        '\t_cinematic_camera_height = camera_height\n',
        1,
    )
    board = board[:bm.start()] + begin_func + board[bm.end():]

reset_pattern = re.compile(r'(?ms)^func cinematic_3d_reset_camera\([^\n]*\) -> void:\n.*?(?=^func |\Z)')
rm = reset_pattern.search(board)
if rm:
    reset_func = rm.group(0)
    if '_cinematic_camera_height' not in reset_func:
        reset_func = reset_func.replace(
            '\t_camera_target_distance = _cinematic_camera_saved_distance\n',
            '\t_camera_target_distance = _cinematic_camera_saved_distance\n'
            '\t_cinematic_camera_height = _cinematic_camera_saved_height\n',
            1,
        )
        board = board[:rm.start()] + reset_func + board[rm.end():]

apply_shot = '''func cinematic_3d_apply_shot(
\tunit_id: String,
\tcounterpart_unit_id: String,
\tshot: Resource
) -> void:
\tif shot == null:
\t\treturn
\tvar actor: SporeUnitActor3D = _actor_by_unit_id(unit_id)
\tif actor == null:
\t\treturn

\t_begin_cinematic_camera_override_3d()

\tvar anchor_name: String = String(shot.get("target_anchor"))
\tvar anchor_global: Vector3 = actor.global_position
\tif actor.has_method("cinematic_anchor_global"):
\t\tanchor_global = actor.cinematic_anchor_global(anchor_name)
\tvar focus: Vector3 = to_local(anchor_global)

\tvar counterpart: SporeUnitActor3D = _actor_by_unit_id(counterpart_unit_id)
\tvar axis: Vector3 = Vector3.ZERO
\tif counterpart != null and counterpart != actor:
\t\taxis = counterpart.global_position - actor.global_position
\t\taxis.y = 0.0

\tif axis.length_squared() < 0.0001:
\t\t# First line: use the actor facing to establish a stable eyeline.
\t\taxis = Vector3(float(actor.facing.x), 0.0, float(actor.facing.y))
\tif axis.length_squared() < 0.0001:
\t\taxis = Vector3(0.0, 0.0, 1.0)
\taxis = axis.normalized()

\tvar right_axis: Vector3 = Vector3(axis.z, 0.0, -axis.x).normalized()
\tfocus += right_axis * float(shot.get("lateral_offset"))
\tfocus += axis * float(shot.get("depth_offset"))

\t# Camera rig yaw 0 points from +Z toward the focus point.
\tvar base_angle: float = rad_to_deg(atan2(axis.x, axis.z))
\tvar shot_angle: float = base_angle + float(shot.get("shoulder_angle_degrees"))
\tvar shot_distance: float = clampf(float(shot.get("camera_distance")), 5.0, 22.0)
\tvar shot_height: float = clampf(float(shot.get("camera_height")), 3.0, 18.0)

\t_camera_focus_target = focus
\t_camera_target_angle = shot_angle
\t_camera_target_distance = shot_distance
\t_cinematic_camera_height = shot_height

\tif bool(shot.get("instant_cut")):
\t\t_camera_focus_current = focus
\t\t_camera_current_angle = shot_angle
\t\t_camera_current_distance = shot_distance
\t\t_apply_camera_transform()
'''
board = insert_before(board, "cinematic_3d_zoom", apply_shot, "func cinematic_3d_apply_shot(")
FILES["board"].write_text(board, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Cinematic Studio: dynamic preset dropdown from .tres assets.
# -----------------------------------------------------------------------------
editor = FILES["editor"].read_text(encoding="utf-8")

if 'const ShotCatalog = preload("res://scripts/catalogs/cinematic_shot_catalog.gd")' not in editor:
    anchor = 'const BattleActionDefinition = preload("res://scripts/data/battle_action_definition.gd")\n'
    if anchor not in editor:
        raise RuntimeError("Editor preload insertion point not found")
    editor = editor.replace(
        anchor,
        anchor + 'const ShotCatalog = preload("res://scripts/catalogs/cinematic_shot_catalog.gd")\n',
        1,
    )

if '"camera_shot"' not in editor.split('const ACTION_TYPES :=', 1)[1].split(']', 1)[0]:
    editor = editor.replace(
        '"camera_reset", "camera_shake",',
        '"camera_reset", "camera_shake", "camera_shot",',
        1,
    )

if 'var action_shot_preset: OptionButton' not in editor:
    anchor = 'var action_side: OptionButton\n'
    if anchor not in editor:
        raise RuntimeError("Editor action_side variable not found")
    editor = editor.replace(anchor, anchor + 'var action_shot_preset: OptionButton\n', 1)

if 'action_shot_preset = OptionButton.new()' not in editor:
    # Work both with and without the previous action_camera_shot UI patch.
    anchor = '\taction_side.add_item("right")\n\tright.add_child(action_side)\n'
    if anchor not in editor:
        raise RuntimeError("Editor portrait side UI anchor not found")
    ui = '''\t_add_label(right, "Plan caméra (.tres réutilisable)")
\taction_shot_preset = OptionButton.new()
\taction_shot_preset.add_item("AUTO — champ/contrechamp")
\taction_shot_preset.set_item_metadata(0, "auto")
\taction_shot_preset.add_item("NONE — conserver le plan")
\taction_shot_preset.set_item_metadata(1, "none")
\tfor shot_id: String in ShotCatalog.ids():
\t\tvar shot: Resource = ShotCatalog.definition(shot_id)
\t\tvar title: String = String(shot.get("display_name")) if shot != null else shot_id
\t\taction_shot_preset.add_item(title)
\t\taction_shot_preset.set_item_metadata(action_shot_preset.item_count - 1, shot_id)
\tright.add_child(action_shot_preset)
'''
    editor = editor.replace(anchor, anchor + ui, 1)

select_pattern = re.compile(r'(?ms)^func _on_action_selected\(index: int\) -> void:\n.*?(?=^func |\Z)')
sm = select_pattern.search(editor)
if not sm:
    raise RuntimeError("Editor _on_action_selected() not found")
select_func = sm.group(0)
if '_select_metadata(action_shot_preset' not in select_func:
    anchor = '\t_select_text(action_side, String(action.portrait_side))\n'
    if anchor not in select_func:
        raise RuntimeError("Editor selected portrait side anchor not found")
    select_func = select_func.replace(
        anchor,
        anchor + '\t_select_metadata(action_shot_preset, String(action.shot_preset_id))\n',
        1,
    )
    editor = editor[:sm.start()] + select_func + editor[sm.end():]

apply_pattern = re.compile(r'(?ms)^func _apply_action\(\) -> void:\n.*?(?=^func |\Z)')
am = apply_pattern.search(editor)
if not am:
    raise RuntimeError("Editor _apply_action() not found")
apply_func = am.group(0)
if 'action.shot_preset_id' not in apply_func:
    anchor = '\taction.portrait_side = action_side.get_item_text(action_side.selected)\n'
    if anchor not in apply_func:
        raise RuntimeError("Editor apply portrait side anchor not found")
    apply_func = apply_func.replace(
        anchor,
        anchor
        + '\tvar selected_shot_index: int = action_shot_preset.selected\n'
        + '\taction.shot_preset_id = String(action_shot_preset.get_item_metadata(selected_shot_index)) if selected_shot_index >= 0 else "auto"\n',
        1,
    )
    editor = editor[:am.start()] + apply_func + editor[am.end():]

FILES["editor"].write_text(editor, encoding="utf-8", newline="\n")

print("[OK] Reusable Godot shot/reverse-shot bricks installed.")
print()
print("Created Godot assets:")
print("  scripts/data/cinematic_shot_definition.gd")
print("  scripts/data/cinematic_shot_set_definition.gd")
print("  scripts/catalogs/cinematic_shot_catalog.gd")
print("  scripts/components/spore_cinematic_target_3d.gd")
print("  scenes/components/cinematic_target_3d.tscn")
print("  data/cinematic_shots/show_1.tres")
print("  data/cinematic_shots/show_2.tres")
print("  data/cinematic_shots/show_wide.tres")
print("  data/cinematic_shots/dialogue_default_set.tres")
print()
print("Behaviour:")
print("  - first dialogue line establishes Shot A")
print("  - when the speaker changes, Shot A / Shot B alternate")
print("  - camera eyeline is calculated from the two interlocutors")
print("  - consecutive lines from the same speaker keep the framing")
print("  - explicit shot_preset_id overrides AUTO")
print("  - NONE keeps the current camera")
print()
print("Godot workflow:")
print("  edit data/cinematic_shots/*.tres in the Inspector")
print("  edit CinematicTarget3D Marker3D anchors visually in the scene editor")
print("  select reusable shot presets from Sporebound Studio > Cinematics")
print()
print("Backups use the suffix: .shot_bricks_backup")
