#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
ACTION_DEF = ROOT / "scripts/data/battle_action_definition.gd"
EDITOR = ROOT / "addons/sporebound_studio/cinematic_editor.gd"
RUNNER = ROOT / "scripts/presentation/spore_cinematic_player_3d.gd"
DIALOGUE = ROOT / "scripts/presentation/spore_cinematic_dialogue_3d.gd"

required = [ACTION_DEF, EDITOR, RUNNER, DIALOGUE]
for path in required:
    if not path.exists():
        print(f"[ERROR] Missing file: {path}")
        print("Apply refactor_cinematics_3d_jrpg.py first, then run this script from the repo root.")
        sys.exit(1)


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".speaker_profiles_backup")
    if not target.exists():
        target.write_bytes(path.read_bytes())


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


for path in required:
    backup(path)

# =============================================================================
# Data resource + catalog
# =============================================================================
PROFILE_SCRIPT = r'''@tool
class_name SporeDialogueSpeakerProfile
extends Resource

## Reusable JRPG dialogue presentation defaults for one speaker.
## Dialogue lines remain content-only; this resource owns presentation identity.

@export_group("Identity")
@export var id: String = "speaker"
@export var display_name: String = "Speaker"
@export var unit_id: String = ""

@export_group("Dialogue Look")
@export_enum("left", "right") var portrait_side: String = "left"
@export var accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
@export var name_color: Color = Color(0.76, 0.92, 1.0, 1.0)
@export_file("*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg") var portrait_path: String = ""

@export_group("JRPG Voice")
@export_range(10.0, 120.0, 1.0) var text_speed: float = 46.0
@export_range(0.55, 1.75, 0.05) var voice_pitch: float = 1.0
@export_range(1, 8, 1) var blip_every: int = 2
@export_range(-40.0, 0.0, 0.5) var blip_volume_db: float = -16.0


func summary() -> String:
	return "%s • %.2fx • %.0f car/s" % [display_name, voice_pitch, text_speed]
'''

CATALOG_SCRIPT = r'''class_name SporeDialogueSpeakerCatalog
extends RefCounted

const PROFILE_DIR: String = "res://data/dialogue_speakers/"

static var _definitions: Dictionary = {}
static var _loaded: bool = false


static func _ensure_loaded() -> void:
	if _loaded:
		return
	_definitions.clear()
	var directory: DirAccess = DirAccess.open(PROFILE_DIR)
	if directory != null:
		for filename: String in directory.get_files():
			if not filename.ends_with(".tres"):
				continue
			var resource: Resource = load(PROFILE_DIR + filename) as Resource
			if resource == null:
				continue
			var profile_id: String = String(resource.get("id"))
			if not profile_id.is_empty():
				_definitions[profile_id] = resource
	_loaded = true


static func reload() -> void:
	_loaded = false
	_ensure_loaded()


static func definition(profile_id: String) -> Resource:
	_ensure_loaded()
	return _definitions.get(profile_id, null) as Resource


static func ids() -> Array[String]:
	_ensure_loaded()
	var result: Array[String] = []
	for key: Variant in _definitions.keys():
		result.append(String(key))
	result.sort()
	return result


static func resolve(profile_id: String, unit_id: String, speaker: String) -> Resource:
	_ensure_loaded()

	if not profile_id.is_empty():
		var explicit: Resource = definition(profile_id)
		if explicit != null:
			return explicit

	if not unit_id.is_empty():
		var by_unit_id: Resource = definition(unit_id)
		if by_unit_id != null:
			return by_unit_id
		for candidate_var: Variant in _definitions.values():
			var candidate: Resource = candidate_var as Resource
			if candidate != null and String(candidate.get("unit_id")) == unit_id:
				return candidate

	var wanted: String = speaker.strip_edges().to_lower()
	if wanted in ["narrateur", "narrator"]:
		return definition("narrator")

	for candidate_var: Variant in _definitions.values():
		var candidate: Resource = candidate_var as Resource
		if candidate == null:
			continue
		if String(candidate.get("display_name")).strip_edges().to_lower() == wanted:
			return candidate

	return null
'''

write(ROOT / "scripts/data/dialogue_speaker_profile.gd", PROFILE_SCRIPT)
write(ROOT / "scripts/catalogs/dialogue_speaker_catalog.gd", CATALOG_SCRIPT)

PROFILE_TEMPLATE = '''[gd_resource type="Resource" script_class="SporeDialogueSpeakerProfile" load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://scripts/data/dialogue_speaker_profile.gd" id="1_profile"]\n\n[resource]\nscript = ExtResource("1_profile")\nid = "{id}"\ndisplay_name = "{name}"\nunit_id = "{unit}"\nportrait_side = "{side}"\naccent_color = Color({ar}, {ag}, {ab}, 1)\nname_color = Color({nr}, {ng}, {nb}, 1)\nportrait_path = ""\ntext_speed = {speed}\nvoice_pitch = {pitch}\nblip_every = {every}\nblip_volume_db = {volume}\n'''

profiles = [
    dict(id="narrator", name="Narrateur", unit="", side="left", ar=0.70, ag=0.58, ab=0.96, nr=0.88, ng=0.80, nb=1.00, speed=42.0, pitch=0.95, every=3, volume=-18.0),
    dict(id="luma", name="Luma", unit="luma", side="left", ar=0.32, ag=0.76, ab=1.00, nr=0.72, ng=0.91, nb=1.00, speed=50.0, pitch=1.10, every=2, volume=-17.0),
    dict(id="momo", name="Momo", unit="momo", side="left", ar=0.48, ag=0.88, ab=0.54, nr=0.78, ng=1.00, nb=0.78, speed=43.0, pitch=0.88, every=2, volume=-16.0),
    dict(id="pipo", name="Pipo", unit="pipo", side="left", ar=0.96, ag=0.72, ab=0.36, nr=1.00, ng=0.88, nb=0.62, speed=46.0, pitch=1.02, every=2, volume=-17.0),
    dict(id="dj_morille", name="DJ Morille", unit="dj_morille", side="right", ar=0.88, ag=0.30, ab=0.72, nr=1.00, ng=0.66, nb=0.88, speed=37.0, pitch=0.78, every=2, volume=-14.5),
]
for spec in profiles:
    path = ROOT / "data/dialogue_speakers" / f"{spec['id']}.tres"
    write(path, PROFILE_TEMPLATE.format(**spec))

# =============================================================================
# BattleActionDefinition: profile selection + optional per-line override
# =============================================================================
action = ACTION_DEF.read_text(encoding="utf-8")
if "dialogue_profile_id" not in action:
    anchor = '@export_group("Dialogue Presentation")\n'
    if anchor not in action:
        raise RuntimeError("Dialogue Presentation group not found. Apply cinematic refactor first.")
    addition = '''@export var dialogue_profile_id: String = ""
@export var override_dialogue_profile: bool = false
'''
    action = action.replace(anchor, anchor + addition, 1)
ACTION_DEF.write_text(action, encoding="utf-8", newline="\n")

# =============================================================================
# Dialogue view: profile colors + per-line volume
# =============================================================================
dialogue = DIALOGUE.read_text(encoding="utf-8")

if "var _profile_accent_color:" not in dialogue:
    anchor = "var _base_panel_style: StyleBoxFlat = null\n"
    if anchor not in dialogue:
        raise RuntimeError("Dialogue runtime state insertion point not found")
    dialogue = dialogue.replace(
        anchor,
        anchor
        + "var _profile_accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)\n"
        + "var _profile_name_color: Color = Color(0.76, 0.92, 1.0, 1.0)\n"
        + "var _line_blip_volume_db: float = -16.0\n",
        1,
    )

if "func set_line_profile(" not in dialogue:
    marker = "func present_line(\n"
    pos = dialogue.find(marker)
    if pos < 0:
        raise RuntimeError("Dialogue present_line() not found")
    helper = '''func set_line_profile(
	accent_color: Color,
	name_color: Color,
	blip_volume: float
) -> void:
	_profile_accent_color = accent_color
	_profile_name_color = name_color
	_line_blip_volume_db = clampf(blip_volume, -40.0, 0.0)


'''
    dialogue = dialogue[:pos] + helper + dialogue[pos:]

old_accent = '''func _apply_accent(accent: String) -> void:
	var accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
	if accent == "enemy":
		accent_color = Color(1.0, 0.46, 0.40, 1.0)
	elif accent == "narrator":
		accent_color = Color(0.86, 0.72, 1.0, 1.0)

	speaker_label.add_theme_color_override("font_color", accent_color.lightened(0.18))'''
new_accent = '''func _apply_accent(accent: String) -> void:
	var accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
	var resolved_name_color: Color = accent_color.lightened(0.18)
	if accent == "profile":
		accent_color = _profile_accent_color
		resolved_name_color = _profile_name_color
	elif accent == "enemy":
		accent_color = Color(1.0, 0.46, 0.40, 1.0)
		resolved_name_color = accent_color.lightened(0.18)
	elif accent == "narrator":
		accent_color = Color(0.86, 0.72, 1.0, 1.0)
		resolved_name_color = accent_color.lightened(0.18)

	speaker_label.add_theme_color_override("font_color", resolved_name_color)'''
if old_accent in dialogue:
    dialogue = dialogue.replace(old_accent, new_accent, 1)
elif 'if accent == "profile":' not in dialogue:
    raise RuntimeError("Could not patch dialogue accent handling")

# Per-line volume is applied when the line is presented.
volume_anchor = "\t_voice_pitch = clampf(voice_pitch, 0.55, 1.75)\n"
if "typewriter_audio.volume_db = _line_blip_volume_db" not in dialogue:
    if volume_anchor not in dialogue:
        raise RuntimeError("Dialogue voice-pitch anchor not found")
    dialogue = dialogue.replace(
        volume_anchor,
        volume_anchor + "\ttypewriter_audio.volume_db = _line_blip_volume_db\n",
        1,
    )

DIALOGUE.write_text(dialogue, encoding="utf-8", newline="\n")

# =============================================================================
# Runner: automatically resolve speaker profile
# =============================================================================
runner = RUNNER.read_text(encoding="utf-8")
if "DialogueSpeakerCatalog" not in runner:
    anchor = 'const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")\n'
    if anchor not in runner:
        raise RuntimeError("Runner catalog preload insertion point not found")
    runner = runner.replace(
        anchor,
        anchor + 'const DialogueSpeakerCatalog = preload("res://scripts/catalogs/dialogue_speaker_catalog.gd")\n',
        1,
    )

play_pattern = re.compile(r"(?ms)^func _play_dialogue\(action: Resource\) -> void:\n.*?(?=^func |\Z)")
m = play_pattern.search(runner)
if not m:
    raise RuntimeError("Runner _play_dialogue() not found")

new_play = '''func _play_dialogue(action: Resource) -> void:
	if _dialogue == null:
		return

	var speaker: String = String(action.get("speaker"))
	var unit_id: String = String(action.get("unit_id"))
	if speaker.is_empty() and not unit_id.is_empty():
		var unit: Resource = UnitCatalog.definition(unit_id)
		if unit != null:
			speaker = String(unit.get("display_name"))
	if speaker.is_empty():
		speaker = "Narrateur"

	var profile_id: String = String(action.get("dialogue_profile_id"))
	var profile: Resource = DialogueSpeakerCatalog.resolve(
		profile_id,
		unit_id,
		speaker
	)
	var override_profile: bool = bool(action.get("override_dialogue_profile"))

	var portrait: Texture2D = _resolve_portrait(action, speaker, profile)
	var portrait_side: String = String(action.get("portrait_side"))
	var accent: String = _speaker_accent(unit_id, speaker)
	var chars_per_second: float = float(action.get("text_speed"))
	var voice_pitch: float = float(action.get("voice_pitch"))
	var blip_every: int = int(action.get("blip_every"))

	if profile != null and not override_profile:
		portrait_side = String(profile.get("portrait_side"))
		chars_per_second = float(profile.get("text_speed"))
		voice_pitch = float(profile.get("voice_pitch"))
		blip_every = int(profile.get("blip_every"))
		accent = "profile"
		var profile_accent: Color = Color(profile.get("accent_color"))
		var profile_name: Color = Color(profile.get("name_color"))
		_dialogue.set_line_profile(
			profile_accent,
			profile_name,
			float(profile.get("blip_volume_db"))
		)
	else:
		_dialogue.set_line_profile(
			Color(0.48, 0.82, 1.0, 1.0),
			Color(0.76, 0.92, 1.0, 1.0),
			-16.0
		)

	await _dialogue.present_line(
		speaker,
		String(action.get("message")),
		portrait,
		portrait_side,
		bool(action.get("wait_for_input")),
		float(action.get("auto_advance_seconds")),
		chars_per_second,
		voice_pitch,
		blip_every,
		accent
	)'''
runner = runner[:m.start()] + new_play + "\n\n\n" + runner[m.end():]

portrait_pattern = re.compile(r"(?ms)^func _resolve_portrait\(action: Resource, speaker: String\) -> Texture2D:\n.*?(?=^func |\Z)")
m = portrait_pattern.search(runner)
if not m:
    raise RuntimeError("Runner _resolve_portrait() not found")
old_portrait = m.group(0)
old_portrait = old_portrait.replace(
    "func _resolve_portrait(action: Resource, speaker: String) -> Texture2D:",
    "func _resolve_portrait(action: Resource, speaker: String, profile: Resource = null) -> Texture2D:",
    1,
)
profile_lookup = '''\n\tif profile != null:\n\t\tvar profile_path: String = String(profile.get("portrait_path"))\n\t\tif not profile_path.is_empty() and ResourceLoader.exists(profile_path):\n\t\t\treturn load(profile_path) as Texture2D\n'''
explicit_block = '''\tif not explicit_path.is_empty() and ResourceLoader.exists(explicit_path):\n\t\treturn load(explicit_path) as Texture2D\n'''
if profile_lookup.strip() not in old_portrait:
    if explicit_block not in old_portrait:
        raise RuntimeError("Runner portrait explicit block not found")
    old_portrait = old_portrait.replace(explicit_block, explicit_block + profile_lookup, 1)
runner = runner[:m.start()] + old_portrait.rstrip() + "\n\n\n" + runner[m.end():]

RUNNER.write_text(runner, encoding="utf-8", newline="\n")

# =============================================================================
# Cinematic editor: select automatic/explicit profile, optional per-line override
# =============================================================================
editor = EDITOR.read_text(encoding="utf-8")

if 'const DIALOGUE_PROFILE_DIR' not in editor:
    anchor = 'const UNIT_DIR := "res://data/units/"\n'
    if anchor not in editor:
        raise RuntimeError("Editor directory constants insertion point not found")
    editor = editor.replace(
        anchor,
        anchor + 'const DIALOGUE_PROFILE_DIR := "res://data/dialogue_speakers/"\n',
        1,
    )

if "var action_dialogue_profile: OptionButton" not in editor:
    anchor = "var action_text_speed: SpinBox\n"
    if anchor not in editor:
        raise RuntimeError("Editor text-speed variable not found")
    editor = editor.replace(
        anchor,
        "var action_dialogue_profile: OptionButton\n"
        "var action_override_dialogue_profile: CheckBox\n"
        + anchor,
        1,
    )

ui_anchor = 'action_text_speed = _spin(right, "Dialogue : vitesse écriture (car./s)", 10, 120, 1)\n'
if "Profil dialogue (auto = unité/locuteur)" not in editor:
    if ui_anchor not in editor:
        raise RuntimeError("Editor dialogue presentation controls not found")
    ui = '''_add_label(right, "Profil dialogue (auto = unité/locuteur)")
\taction_dialogue_profile = OptionButton.new()
\tright.add_child(action_dialogue_profile)
\taction_override_dialogue_profile = CheckBox.new()
\taction_override_dialogue_profile.text = "Surcharger voix/couleur/côté pour cette réplique"
\tright.add_child(action_override_dialogue_profile)
\t'''
    editor = editor.replace(ui_anchor, ui + ui_anchor, 1)

# Refresh options whenever nested/unit options are refreshed.
refresh_nested_pattern = re.compile(r"(?ms)^func _refresh_nested_options\(\) -> void:\n.*?(?=^func |\Z)")
m = refresh_nested_pattern.search(editor)
if not m:
    raise RuntimeError("Editor _refresh_nested_options() not found")
refresh_nested = m.group(0)
if "_refresh_dialogue_profile_options()" not in refresh_nested:
    refresh_nested = refresh_nested.rstrip() + "\n\t_refresh_dialogue_profile_options()\n"
    editor = editor[:m.start()] + refresh_nested + "\n\n" + editor[m.end():]

if "func _refresh_dialogue_profile_options()" not in editor:
    marker = "func _refresh_unit_options() -> void:\n"
    pos = editor.find(marker)
    if pos < 0:
        raise RuntimeError("Editor profile helper insertion point not found")
    helper = '''func _refresh_dialogue_profile_options() -> void:
	if action_dialogue_profile == null:
		return
	var wanted: String = ""
	if action_dialogue_profile.selected >= 0:
		wanted = String(action_dialogue_profile.get_item_metadata(action_dialogue_profile.selected))
	action_dialogue_profile.clear()
	action_dialogue_profile.add_item("AUTO — unité / locuteur")
	action_dialogue_profile.set_item_metadata(0, "")
	for path: String in _resource_files(DIALOGUE_PROFILE_DIR):
		var profile: Resource = load(path) as Resource
		if profile == null:
			continue
		action_dialogue_profile.add_item(String(profile.get("display_name")))
		action_dialogue_profile.set_item_metadata(
			action_dialogue_profile.item_count - 1,
			String(profile.get("id"))
		)
	_select_metadata(action_dialogue_profile, wanted)


'''
    editor = editor[:pos] + helper + editor[pos:]

# Selection loads current profile fields.
select_anchor = "\taction_text_speed.value = float(action.text_speed)\n"
if "action_override_dialogue_profile.button_pressed" not in editor:
    if select_anchor not in editor:
        raise RuntimeError("Editor action selection presentation anchor not found")
    select_add = '''\t_refresh_dialogue_profile_options()\n\t_select_metadata(action_dialogue_profile, String(action.dialogue_profile_id))\n\taction_override_dialogue_profile.button_pressed = bool(action.override_dialogue_profile)\n'''
    editor = editor.replace(select_anchor, select_add + select_anchor, 1)

# Apply stores current profile fields.
apply_anchor = "\taction.text_speed = float(action_text_speed.value)\n"
if "action.dialogue_profile_id" not in editor:
    if apply_anchor not in editor:
        raise RuntimeError("Editor action apply presentation anchor not found")
    apply_add = '''\taction.dialogue_profile_id = String(action_dialogue_profile.get_item_metadata(action_dialogue_profile.selected)) if action_dialogue_profile.selected >= 0 else ""\n\taction.override_dialogue_profile = action_override_dialogue_profile.button_pressed\n'''
    editor = editor.replace(apply_anchor, apply_add + apply_anchor, 1)

EDITOR.write_text(editor, encoding="utf-8", newline="\n")

print("[OK] Dialogue speaker profiles installed.")
print()
print("Created:")
print("  scripts/data/dialogue_speaker_profile.gd")
print("  scripts/catalogs/dialogue_speaker_catalog.gd")
print("  data/dialogue_speakers/{narrator,luma,momo,pipo,dj_morille}.tres")
print()
print("Cinematic Editor:")
print("  - AUTO profile from unit_id/speaker")
print("  - optional explicit profile")
print("  - optional per-line override")
print()
print("Profiles own:")
print("  - accent/name colors")
print("  - default portrait side")
print("  - optional portrait override")
print("  - text speed")
print("  - voice pitch")
print("  - blip frequency and volume")
print()
print("Dialogue content remains in data/cinematics/*.tres.")
print("No combat mechanics changed.")
