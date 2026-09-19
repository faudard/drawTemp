#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()

FILES = {
    "runner": ROOT / "scripts/presentation/spore_cinematic_player_3d.gd",
    "cinematic_def": ROOT / "scripts/data/cinematic_definition.gd",
    "editor": ROOT / "addons/sporebound_studio/cinematic_editor.gd",
    "shot_set": ROOT / "data/cinematic_shots/dialogue_default_set.tres",
    "shot_catalog": ROOT / "scripts/catalogs/cinematic_shot_catalog.gd",
}

for key, path in FILES.items():
    if not path.exists():
        print(f"[ERROR] Missing {key}: {path}")
        print("Run this after add_reusable_shot_reverse_shot_bricks.py from the drawTemp repository root.")
        sys.exit(1)


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".director_bricks_backup")
    if not target.exists():
        target.write_bytes(path.read_bytes())


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup(path)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def replace_function(text: str, name: str, code: str) -> str:
    pattern = re.compile(
        rf"(?ms)^func {re.escape(name)}\([^\n]*\)(?: -> [^:\n]+)?:\n.*?(?=^func |\Z)"
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Function not found: {name}")
    return text[:match.start()] + code.rstrip() + "\n\n\n" + text[match.end():]


for path in FILES.values():
    backup(path)

# -----------------------------------------------------------------------------
# Godot-native director profile resource.
# -----------------------------------------------------------------------------
DIRECTOR_DEF = r'''@tool
class_name SporeCinematicDirectorProfile
extends Resource

## Reusable cinematic direction rules.
## The runtime runner executes actions; this Resource decides how dialogue is framed.

@export_group("Identity")
@export var id: String = "jrpg_default"
@export var display_name: String = "JRPG — dialogue tactique"
@export_multiline var description: String = ""

@export_group("Dialogue Grammar")
@export var shot_set: Resource
@export var establish_first_exchange: bool = true
@export var establish_new_participant: bool = true
@export var keep_same_speaker_shot: bool = true
@export var alternate_on_speaker_change: bool = true
@export_range(0.0, 1.0, 0.01) var establishing_hold: float = 0.16
@export_range(0.0, 1.0, 0.01) var cut_hold: float = 0.05

@export_group("Pacing")
@export_range(1, 8, 1) var max_consecutive_lines_same_shot: int = 4
@export var return_to_wide_after_exchange: bool = false
@export_range(0.0, 1.5, 0.05) var end_wide_hold: float = 0.15


func summary() -> String:
	return "%s • establish=%s • same-speaker=%s • alternate=%s" % [
		display_name,
		str(establish_first_exchange),
		str(keep_same_speaker_shot),
		str(alternate_on_speaker_change),
	]
'''

DIRECTOR_CATALOG = r'''class_name SporeCinematicDirectorCatalog
extends RefCounted

const DIRECTOR_DIR: String = "res://data/cinematic_directors/"

static var _cache: Dictionary = {}


static func definition(profile_id: String) -> Resource:
	if profile_id.is_empty():
		return null
	if _cache.has(profile_id):
		return _cache[profile_id]
	var path: String = DIRECTOR_DIR + profile_id + ".tres"
	if not ResourceLoader.exists(path):
		return null
	var data: Resource = load(path) as Resource
	if data != null:
		_cache[profile_id] = data
	return data


static func ids() -> Array[String]:
	var result: Array[String] = []
	var directory: DirAccess = DirAccess.open(DIRECTOR_DIR)
	if directory == null:
		return result
	for file_name: String in directory.get_files():
		if not file_name.ends_with(".tres"):
			continue
		var data: Resource = load(DIRECTOR_DIR + file_name) as Resource
		if data == null:
			continue
		var profile_id: String = String(data.get("id"))
		if not profile_id.is_empty():
			result.append(profile_id)
	result.sort()
	return result


static func clear_cache() -> void:
	_cache.clear()
'''

DIRECTOR_SCRIPT = r'''class_name SporeCinematicDirector3D
extends Node

const ShotCatalog = preload("res://scripts/catalogs/cinematic_shot_catalog.gd")

var _host: Node = null
var _profile: Resource = null
var _shot_set: Resource = null
var _last_speaker_id: String = ""
var _previous_speaker_id: String = ""
var _last_shot_id: String = ""
var _participants: Dictionary = {}
var _same_shot_line_count: int = 0
var _first_dialogue_line: bool = true


func configure(host: Node, profile: Resource, fallback_shot_set: Resource = null) -> void:
	_host = host
	_profile = profile
	_shot_set = fallback_shot_set
	if _profile != null:
		var profile_set: Resource = _profile.get("shot_set") as Resource
		if profile_set != null:
			_shot_set = profile_set
	reset()


func reset() -> void:
	_last_speaker_id = ""
	_previous_speaker_id = ""
	_last_shot_id = ""
	_participants.clear()
	_same_shot_line_count = 0
	_first_dialogue_line = true


func prepare_dialogue(action: Resource, speaker_unit_id: String) -> float:
	if action == null or speaker_unit_id.is_empty() or _host == null:
		return 0.0
	if not _host.has_method("cinematic_3d_apply_shot"):
		return 0.0

	var requested_id: String = String(action.get("shot_preset_id"))
	if requested_id == "none":
		_track_speaker(speaker_unit_id)
		return 0.0

	var participant_is_new: bool = not _participants.has(speaker_unit_id)
	var speaker_changed: bool = not _last_speaker_id.is_empty() and speaker_unit_id != _last_speaker_id
	var shot: Resource = null
	var hold: float = _profile_float("cut_hold", 0.05)

	if not requested_id.is_empty() and requested_id != "auto":
		shot = ShotCatalog.definition(requested_id)
	elif _should_establish(speaker_unit_id, participant_is_new):
		shot = _wide_shot()
		hold = _profile_float("establishing_hold", 0.16)
	else:
		shot = _dialogue_shot(speaker_unit_id, speaker_changed)

	if shot == null:
		_track_speaker(speaker_unit_id)
		return 0.0

	var counterpart_id: String = _counterpart_for(speaker_unit_id)
	_host.call("cinematic_3d_apply_shot", speaker_unit_id, counterpart_id, shot)
	_last_shot_id = String(shot.get("id"))

	if speaker_unit_id == _last_speaker_id:
		_same_shot_line_count += 1
	else:
		_same_shot_line_count = 1

	_track_speaker(speaker_unit_id)
	_first_dialogue_line = false

	if not bool(shot.get("instant_cut")):
		hold = maxf(hold, float(shot.get("transition_seconds")))
	return hold


func finish_exchange() -> float:
	if _host == null or not _profile_bool("return_to_wide_after_exchange", false):
		return 0.0
	if _last_speaker_id.is_empty():
		return 0.0
	var wide: Resource = _wide_shot()
	if wide == null:
		return 0.0
	_host.call(
		"cinematic_3d_apply_shot",
		_last_speaker_id,
		_previous_speaker_id,
		wide
	)
	return _profile_float("end_wide_hold", 0.15)


func _should_establish(speaker_unit_id: String, participant_is_new: bool) -> bool:
	if _first_dialogue_line and _profile_bool("establish_first_exchange", true):
		return _wide_shot() != null
	if participant_is_new and not _last_speaker_id.is_empty() and _profile_bool("establish_new_participant", true):
		# Do not interrupt the first A/B hand-off. A third participant gets a new establishing beat.
		if _participants.size() >= 2:
			return _wide_shot() != null
	return false


func _dialogue_shot(speaker_unit_id: String, speaker_changed: bool) -> Resource:
	var shot_a: Resource = _shot_from_set("shot_a")
	var shot_b: Resource = _shot_from_set("shot_b")
	if shot_a == null and shot_b == null:
		return ShotCatalog.definition("show_1")

	if speaker_unit_id == _last_speaker_id and _profile_bool("keep_same_speaker_shot", true):
		var max_same: int = _profile_int("max_consecutive_lines_same_shot", 4)
		if _same_shot_line_count < max_same:
			var current: Resource = ShotCatalog.definition(_last_shot_id)
			if current != null:
				return current

	if not speaker_changed or not _profile_bool("alternate_on_speaker_change", true):
		return shot_a if shot_a != null else shot_b

	var shot_a_id: String = String(shot_a.get("id")) if shot_a != null else ""
	if _last_shot_id == shot_a_id:
		return shot_b if shot_b != null else shot_a
	return shot_a if shot_a != null else shot_b


func _counterpart_for(speaker_unit_id: String) -> String:
	if not _last_speaker_id.is_empty() and _last_speaker_id != speaker_unit_id:
		return _last_speaker_id
	if not _previous_speaker_id.is_empty() and _previous_speaker_id != speaker_unit_id:
		return _previous_speaker_id
	for key: Variant in _participants.keys():
		var candidate: String = String(key)
		if candidate != speaker_unit_id:
			return candidate
	return ""


func _track_speaker(speaker_unit_id: String) -> void:
	_participants[speaker_unit_id] = true
	if speaker_unit_id != _last_speaker_id:
		_previous_speaker_id = _last_speaker_id
		_last_speaker_id = speaker_unit_id


func _wide_shot() -> Resource:
	return _shot_from_set("wide_shot")


func _shot_from_set(property_name: String) -> Resource:
	if _shot_set == null:
		return null
	return _shot_set.get(property_name) as Resource


func _profile_bool(property_name: String, fallback: bool) -> bool:
	if _profile == null:
		return fallback
	var value: Variant = _profile.get(property_name)
	return bool(value) if value != null else fallback


func _profile_float(property_name: String, fallback: float) -> float:
	if _profile == null:
		return fallback
	var value: Variant = _profile.get(property_name)
	return float(value) if value != null else fallback


func _profile_int(property_name: String, fallback: int) -> int:
	if _profile == null:
		return fallback
	var value: Variant = _profile.get(property_name)
	return int(value) if value != null else fallback
'''

DIRECTOR_SCENE = r'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/presentation/spore_cinematic_director_3d.gd" id="1_script"]

[node name="CinematicDirector3D" type="Node"]
script = ExtResource("1_script")
'''

DEFAULT_DIRECTOR = r'''[gd_resource type="Resource" script_class="SporeCinematicDirectorProfile" load_steps=3 format=3]

[ext_resource type="Script" path="res://scripts/data/cinematic_director_profile.gd" id="1_profile"]
[ext_resource type="Resource" path="res://data/cinematic_shots/dialogue_default_set.tres" id="2_set"]

[resource]
script = ExtResource("1_profile")
id = "jrpg_default"
display_name = "JRPG — champ / contrechamp"
description = "Plan large d'installation, champ/contrechamp sur changement de locuteur, plan conservé quand le même personnage continue."
shot_set = ExtResource("2_set")
establish_first_exchange = true
establish_new_participant = true
keep_same_speaker_shot = true
alternate_on_speaker_change = true
establishing_hold = 0.16
cut_hold = 0.05
max_consecutive_lines_same_shot = 4
return_to_wide_after_exchange = false
end_wide_hold = 0.15
'''

write(ROOT / "scripts/data/cinematic_director_profile.gd", DIRECTOR_DEF)
write(ROOT / "scripts/catalogs/cinematic_director_catalog.gd", DIRECTOR_CATALOG)
write(ROOT / "scripts/presentation/spore_cinematic_director_3d.gd", DIRECTOR_SCRIPT)
write(ROOT / "scenes/components/cinematic_director_3d.tscn", DIRECTOR_SCENE)
write(ROOT / "data/cinematic_directors/jrpg_default.tres", DEFAULT_DIRECTOR)

# -----------------------------------------------------------------------------
# CinematicDefinition: each cinematic may choose its director profile as a Resource.
# -----------------------------------------------------------------------------
cinematic_def = FILES["cinematic_def"].read_text(encoding="utf-8")
if "var director_profile:" not in cinematic_def:
    anchor = '@export_multiline var description: String = ""\n'
    if anchor not in cinematic_def:
        raise RuntimeError("CinematicDefinition identity anchor not found")
    cinematic_def = cinematic_def.replace(
        anchor,
        anchor
        + '\n@export_group("Direction")\n'
        + '@export var director_profile: Resource = preload("res://data/cinematic_directors/jrpg_default.tres")\n',
        1,
    )
FILES["cinematic_def"].write_text(cinematic_def, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Runner delegates framing decisions to the Director component.
# -----------------------------------------------------------------------------
runner = FILES["runner"].read_text(encoding="utf-8")

if 'const DirectorScene = preload("res://scenes/components/cinematic_director_3d.tscn")' not in runner:
    anchor = 'const ShotCatalog = preload("res://scripts/catalogs/cinematic_shot_catalog.gd")\n'
    if anchor not in runner:
        raise RuntimeError("ShotCatalog preload not found in runner")
    runner = runner.replace(
        anchor,
        anchor + 'const DirectorScene = preload("res://scenes/components/cinematic_director_3d.tscn")\n',
        1,
    )

if 'var _director: SporeCinematicDirector3D' not in runner:
    anchor = 'var _running: bool = false\n'
    if anchor not in runner:
        raise RuntimeError("Runner state anchor not found")
    runner = runner.replace(
        anchor,
        anchor + 'var _director: SporeCinematicDirector3D = null\n',
        1,
    )

ensure_pattern = re.compile(r'(?ms)^func _ensure_runtime\(\) -> void:\n.*?(?=^func |\Z)')
em = ensure_pattern.search(runner)
if not em:
    raise RuntimeError("Runner _ensure_runtime() not found")
ensure_func = em.group(0)
if 'DirectorScene.instantiate()' not in ensure_func:
    first_newline = ensure_func.find('\n')
    addition = '''\tif _director == null or not is_instance_valid(_director):
\t\tvar director_instance: Node = DirectorScene.instantiate()
\t\tif director_instance is SporeCinematicDirector3D:
\t\t\t_director = director_instance as SporeCinematicDirector3D
\t\t\tadd_child(_director)

'''
    ensure_func = ensure_func[:first_newline + 1] + addition + ensure_func[first_newline + 1:]
    runner = runner[:em.start()] + ensure_func + runner[em.end():]

# Configure the director per cinematic before executing its actions.
play_pattern = re.compile(r'(?ms)^func play\(cinematic_id: String\) -> bool:\n.*?(?=^func |\Z)')
pm = play_pattern.search(runner)
if not pm:
    raise RuntimeError("Runner play() not found")
play_func = pm.group(0)
if '_director.configure' not in play_func:
    anchor = '\t_running = true\n'
    if anchor not in play_func:
        raise RuntimeError("Runner play() running anchor not found")
    configure = '''\tvar director_profile: Resource = definition.get("director_profile") as Resource
\tif _director != null:
\t\t_director.configure(_host, director_profile, dialogue_shot_set)
'''
    play_func = play_func.replace(anchor, anchor + configure, 1)
    runner = runner[:pm.start()] + play_func + runner[pm.end():]

# Replace the older embedded auto-shot helper with Director delegation.
old_helper_pattern = re.compile(
    r'(?ms)^func _apply_dialogue_shot_reverse_shot\(action: Resource, unit_id: String\) -> float:\n.*?(?=^func _automatic_dialogue_shot|^func _resolve_portrait|\Z)'
)
hm = old_helper_pattern.search(runner)
if hm:
    new_helper = '''func _apply_dialogue_shot_reverse_shot(action: Resource, unit_id: String) -> float:
\tif _director == null:
\t\treturn 0.0
\treturn _director.prepare_dialogue(action, unit_id)


'''
    runner = runner[:hm.start()] + new_helper + runner[hm.end():]

# Remove obsolete automatic helper if still present.
auto_pattern = re.compile(
    r'(?ms)^func _automatic_dialogue_shot\(unit_id: String\) -> Resource:\n.*?(?=^func _resolve_portrait|\Z)'
)
am = auto_pattern.search(runner)
if am:
    runner = runner[:am.start()] + runner[am.end():]

# Reset legacy fields are harmless, but Director is authoritative now.
FILES["runner"].write_text(runner, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Studio editor: Director profile dropdown at cinematic level.
# -----------------------------------------------------------------------------
editor = FILES["editor"].read_text(encoding="utf-8")

if 'const DirectorCatalog = preload("res://scripts/catalogs/cinematic_director_catalog.gd")' not in editor:
    anchor = 'const ShotCatalog = preload("res://scripts/catalogs/cinematic_shot_catalog.gd")\n'
    if anchor not in editor:
        # fallback for an editor not yet patched with ShotCatalog
        anchor = 'const BattleActionDefinition = preload("res://scripts/data/battle_action_definition.gd")\n'
    if anchor not in editor:
        raise RuntimeError("Editor preload anchor not found")
    editor = editor.replace(
        anchor,
        anchor + 'const DirectorCatalog = preload("res://scripts/catalogs/cinematic_director_catalog.gd")\n',
        1,
    )

if 'var director_profile_select: OptionButton' not in editor:
    anchor = 'var description_edit: TextEdit\n'
    if anchor not in editor:
        raise RuntimeError("Editor variable anchor not found")
    editor = editor.replace(anchor, anchor + 'var director_profile_select: OptionButton\n', 1)

if 'director_profile_select = OptionButton.new()' not in editor:
    anchor = 'description_edit = _text(left, "Description", 65)\n'
    if anchor not in editor:
        raise RuntimeError("Editor description UI anchor not found")
    ui = '''\t_add_label(left, "Direction / grammaire caméra")
\tdirector_profile_select = OptionButton.new()
\tfor profile_id: String in DirectorCatalog.ids():
\t\tvar profile: Resource = DirectorCatalog.definition(profile_id)
\t\tvar title: String = String(profile.get("display_name")) if profile != null else profile_id
\t\tdirector_profile_select.add_item(title)
\t\tdirector_profile_select.set_item_metadata(director_profile_select.item_count - 1, profile_id)
\tleft.add_child(director_profile_select)
'''
    editor = editor.replace(anchor, anchor + ui, 1)

select_pattern = re.compile(r'(?ms)^func _on_selected\(index: int\) -> void:\n.*?(?=^func |\Z)')
sm = select_pattern.search(editor)
if not sm:
    raise RuntimeError("Editor _on_selected() not found")
select_func = sm.group(0)
if '_select_metadata(director_profile_select' not in select_func:
    anchor = '\tdescription_edit.text = String(current.description)\n'
    if anchor not in select_func:
        raise RuntimeError("Editor cinematic selected anchor not found")
    addition = '''\tvar current_director: Resource = current.get("director_profile") as Resource
\tvar current_director_id: String = String(current_director.get("id")) if current_director != null else "jrpg_default"
\t_select_metadata(director_profile_select, current_director_id)
'''
    select_func = select_func.replace(anchor, anchor + addition, 1)
    editor = editor[:sm.start()] + select_func + editor[sm.end():]

save_pattern = re.compile(r'(?ms)^func _save_current\(\) -> void:\n.*?(?=^func |\Z)')
sv = save_pattern.search(editor)
if not sv:
    raise RuntimeError("Editor _save_current() not found")
save_func = sv.group(0)
if 'current.director_profile' not in save_func:
    anchor = '\tcurrent.description = description_edit.text\n'
    if anchor not in save_func:
        raise RuntimeError("Editor save cinematic anchor not found")
    addition = '''\tif director_profile_select.selected >= 0:
\t\tvar director_id: String = String(director_profile_select.get_item_metadata(director_profile_select.selected))
\t\tvar director_data: Resource = DirectorCatalog.definition(director_id)
\t\tif director_data != null:
\t\t\tcurrent.director_profile = director_data
'''
    save_func = save_func.replace(anchor, anchor + addition, 1)
    editor = editor[:sv.start()] + save_func + editor[sv.end():]

FILES["editor"].write_text(editor, encoding="utf-8", newline="\n")

print("[OK] Cinematic Director bricks installed.")
print()
print("Created Godot-native reusable assets:")
print("  scripts/data/cinematic_director_profile.gd")
print("  scripts/catalogs/cinematic_director_catalog.gd")
print("  scripts/presentation/spore_cinematic_director_3d.gd")
print("  scenes/components/cinematic_director_3d.tscn")
print("  data/cinematic_directors/jrpg_default.tres")
print()
print("Direction rules are now data-driven:")
print("  - establishing shot on first exchange")
print("  - A/B shot-reverse-shot when speaker changes")
print("  - keep framing for consecutive lines from same speaker")
print("  - third participant can trigger a new wide establishing shot")
print("  - explicit shot preset always overrides AUTO")
print()
print("Godot workflow:")
print("  edit jrpg_default.tres in Inspector")
print("  assign a Director Profile per CinematicDefinition")
print("  Cinematic Studio exposes the profile selector")
print()
print("Backups use: .director_bricks_backup")
