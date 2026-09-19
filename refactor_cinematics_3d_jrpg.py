#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()

BOARD = ROOT / "scripts/prototypes/spore_battle_board_3d.gd"
ACTION_DEF = ROOT / "scripts/data/battle_action_definition.gd"
EDITOR = ROOT / "addons/sporebound_studio/cinematic_editor.gd"
MISSION1 = ROOT / "data/missions/mission_1.tres"
MISSION_SCENE = ROOT / "scenes/mission_1_battle_3d.tscn"

required = [BOARD, ACTION_DEF, EDITOR, MISSION1, MISSION_SCENE]
for path in required:
    if not path.exists():
        print(f"[ERROR] Missing file: {path}")
        print("Run this script from the drawTemp repository root.")
        sys.exit(1)


def backup(path: Path, suffix: str = ".cinematic3d_backup") -> None:
    target = path.with_suffix(path.suffix + suffix)
    if not target.exists():
        target.write_bytes(path.read_bytes())


def replace_function(text: str, name: str, code: str | None) -> str:
    pattern = re.compile(
        rf"(?ms)^func {re.escape(name)}\([^\n]*\)(?: -> [^:\n]+)?:\n.*?(?=^func |\Z)"
    )
    match = pattern.search(text)
    if not match:
        if code is None:
            return text
        raise RuntimeError(f"Function not found: {name}")
    replacement = "" if code is None else code.rstrip() + "\n\n\n"
    return text[:match.start()] + replacement + text[match.end():]


def insert_before(text: str, function_name: str, code: str, marker: str) -> str:
    if marker in text:
        return text
    needle = f"func {function_name}("
    pos = text.find(needle)
    if pos < 0:
        raise RuntimeError(f"Cannot find insertion point: {function_name}")
    return text[:pos] + code.rstrip() + "\n\n\n" + text[pos:]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


for p in required:
    backup(p)

# =============================================================================
# Reusable JRPG dialogue view (editable scene + runtime script)
# =============================================================================
DIALOGUE_SCRIPT = r'''class_name SporeCinematicDialogue3D
extends Control

signal advance_requested

@export_group("Typewriter")
@export_range(10.0, 120.0, 1.0) var default_chars_per_second: float = 46.0
@export_range(1, 8, 1) var default_blip_every: int = 2
@export_range(0.0, 1.0, 0.01) var punctuation_pause_seconds: float = 0.08
@export_range(-40.0, 0.0, 0.5) var blip_volume_db: float = -16.0
@export var blip_stream: AudioStream

@export_group("Animation")
@export_range(0.05, 0.6, 0.05) var panel_enter_seconds: float = 0.18
@export_range(0.05, 0.6, 0.05) var panel_exit_seconds: float = 0.14

@onready var dimmer: ColorRect = $Dimmer
@onready var letterbox_top: ColorRect = $LetterboxTop
@onready var letterbox_bottom: ColorRect = $LetterboxBottom
@onready var dialogue_panel: Panel = $DialoguePanel
@onready var portrait_left: TextureRect = $DialoguePanel/Margin/Row/PortraitLeft
@onready var portrait_right: TextureRect = $DialoguePanel/Margin/Row/PortraitRight
@onready var speaker_label: Label = $DialoguePanel/Margin/Row/TextColumn/SpeakerName
@onready var message_label: Label = $DialoguePanel/Margin/Row/TextColumn/Message
@onready var hint_label: Label = $DialoguePanel/Margin/Row/TextColumn/Footer/Hint
@onready var continue_button: Button = $DialoguePanel/Margin/Row/TextColumn/Footer/Continue
@onready var advance_pulse: Label = $DialoguePanel/Margin/Row/TextColumn/Footer/AdvancePulse
@onready var fade_rect: ColorRect = $FadeRect
@onready var typewriter_audio: AudioStreamPlayer = $TypewriterAudio

var _full_text: String = ""
var _char_index: int = 0
var _char_accumulator: float = 0.0
var _chars_per_second: float = 46.0
var _blip_every: int = 2
var _voice_pitch: float = 1.0
var _typing: bool = false
var _waiting: bool = false
var _punctuation_delay: float = 0.0
var _generator_playback: AudioStreamGeneratorPlayback = null
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _base_panel_style: StyleBoxFlat = null


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	continue_button.pressed.connect(_advance_or_reveal)
	_rng.seed = 0xC1E3A
	var source_style: StyleBox = dialogue_panel.get_theme_stylebox("panel")
	if source_style is StyleBoxFlat:
		_base_panel_style = (source_style as StyleBoxFlat).duplicate()
	_setup_blip_audio()
	set_process_unhandled_key_input(true)


func _process(delta: float) -> void:
	if not visible:
		return
	advance_pulse.modulate.a = 0.55 + sin(Time.get_ticks_msec() * 0.008) * 0.35
	if not _typing:
		return

	if _punctuation_delay > 0.0:
		_punctuation_delay = maxf(0.0, _punctuation_delay - delta)
		return

	_char_accumulator += delta
	var seconds_per_char: float = 1.0 / maxf(1.0, _chars_per_second)
	while _char_accumulator >= seconds_per_char and _char_index < _full_text.length():
		_char_accumulator -= seconds_per_char
		_char_index += 1
		message_label.text = _full_text.substr(0, _char_index)

		var character: String = _full_text.substr(_char_index - 1, 1)
		if _should_blip(character) and (_char_index % maxi(1, _blip_every) == 0):
			_play_blip()
		if character in [".", "!", "?", ";", ":"]:
			_punctuation_delay = punctuation_pause_seconds
			break

	if _char_index >= _full_text.length():
		_finish_typing()


func present_line(
	speaker: String,
	text_value: String,
	portrait: Texture2D,
	portrait_side: String,
	wait_for_input: bool,
	auto_advance_seconds: float,
	chars_per_second: float,
	voice_pitch: float,
	blip_every: int,
	accent: String = "neutral"
) -> void:
	visible = true
	dimmer.visible = true
	letterbox_top.visible = true
	letterbox_bottom.visible = true
	dialogue_panel.visible = true
	_apply_accent(accent)
	_set_portrait(portrait, portrait_side)

	speaker_label.text = speaker if not speaker.is_empty() else "Narrateur"
	_full_text = text_value
	_char_index = 0
	_char_accumulator = 0.0
	_punctuation_delay = 0.0
	_chars_per_second = chars_per_second if chars_per_second > 0.0 else default_chars_per_second
	_voice_pitch = clampf(voice_pitch, 0.55, 1.75)
	_blip_every = maxi(1, blip_every)
	message_label.text = ""
	_typing = true
	_waiting = true
	continue_button.text = "AFFICHER TOUT"
	advance_pulse.visible = false
	hint_label.text = "Entrée / Espace / clic • 1× affiche tout • 2× continue"

	dialogue_panel.modulate = Color(1.0, 1.0, 1.0, 0.0)
	dialogue_panel.scale = Vector2(0.985, 0.94)
	var enter_tween: Tween = create_tween().set_parallel(true)
	enter_tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	enter_tween.tween_property(dialogue_panel, "modulate", Color.WHITE, panel_enter_seconds)
	enter_tween.tween_property(dialogue_panel, "scale", Vector2.ONE, panel_enter_seconds)

	if wait_for_input or auto_advance_seconds <= 0.0:
		await advance_requested
	else:
		while _typing:
			await get_tree().process_frame
		await get_tree().create_timer(maxf(0.1, auto_advance_seconds)).timeout

	_waiting = false
	await _hide_dialogue_panel()


func set_fade_alpha(alpha: float, duration: float) -> void:
	var target: Color = fade_rect.color
	target.a = clampf(alpha, 0.0, 1.0)
	if duration <= 0.0:
		fade_rect.color = target
		return
	var tween: Tween = create_tween()
	tween.tween_property(fade_rect, "color", target, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tween.finished


func hide_all() -> void:
	_typing = false
	_waiting = false
	dialogue_panel.visible = false
	letterbox_top.visible = false
	letterbox_bottom.visible = false
	dimmer.visible = false
	if fade_rect.color.a <= 0.001:
		visible = false


func _hide_dialogue_panel() -> void:
	var tween: Tween = create_tween().set_parallel(true)
	tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tween.tween_property(dialogue_panel, "modulate", Color(1.0, 1.0, 1.0, 0.0), panel_exit_seconds)
	tween.tween_property(dialogue_panel, "scale", Vector2(0.99, 0.96), panel_exit_seconds)
	await tween.finished
	dialogue_panel.visible = false
	letterbox_top.visible = false
	letterbox_bottom.visible = false
	dimmer.visible = false
	if fade_rect.color.a <= 0.001:
		visible = false


func _unhandled_key_input(event: InputEvent) -> void:
	if not visible or not _waiting or not event.pressed:
		return
	var key_event: InputEventKey = event as InputEventKey
	if key_event.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
		get_viewport().set_input_as_handled()
		_advance_or_reveal()


func _gui_input(event: InputEvent) -> void:
	if not visible or not _waiting:
		return
	if event is InputEventMouseButton:
		var mouse_event: InputEventMouseButton = event as InputEventMouseButton
		if mouse_event.pressed and mouse_event.button_index == MOUSE_BUTTON_LEFT:
			accept_event()
			_advance_or_reveal()


func _advance_or_reveal() -> void:
	if not _waiting:
		return
	if _typing:
		_char_index = _full_text.length()
		message_label.text = _full_text
		_finish_typing()
		return
	_waiting = false
	advance_requested.emit()


func _finish_typing() -> void:
	_typing = false
	message_label.text = _full_text
	continue_button.text = "CONTINUER  ▸"
	advance_pulse.visible = true


func _set_portrait(texture: Texture2D, side: String) -> void:
	portrait_left.texture = null
	portrait_right.texture = null
	portrait_left.visible = false
	portrait_right.visible = false
	if texture == null:
		return
	if side == "right":
		portrait_right.texture = texture
		portrait_right.visible = true
	else:
		portrait_left.texture = texture
		portrait_left.visible = true


func _apply_accent(accent: String) -> void:
	var accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
	if accent == "enemy":
		accent_color = Color(1.0, 0.46, 0.40, 1.0)
	elif accent == "narrator":
		accent_color = Color(0.86, 0.72, 1.0, 1.0)

	speaker_label.add_theme_color_override("font_color", accent_color.lightened(0.18))
	var style: StyleBoxFlat = StyleBoxFlat.new()
	if _base_panel_style != null:
		style = _base_panel_style.duplicate()
	else:
		style.bg_color = Color(0.035, 0.050, 0.080, 0.98)
		style.corner_radius_top_left = 18
		style.corner_radius_top_right = 18
		style.corner_radius_bottom_left = 18
		style.corner_radius_bottom_right = 18
	style.border_color = accent_color
	style.border_width_left = 2
	style.border_width_top = 2
	style.border_width_right = 2
	style.border_width_bottom = 2
	dialogue_panel.add_theme_stylebox_override("panel", style)


func _setup_blip_audio() -> void:
	typewriter_audio.volume_db = blip_volume_db
	if blip_stream != null:
		typewriter_audio.stream = blip_stream
		return
	var generator: AudioStreamGenerator = AudioStreamGenerator.new()
	generator.mix_rate = 22050.0
	generator.buffer_length = 0.10
	typewriter_audio.stream = generator
	typewriter_audio.play()
	_generator_playback = typewriter_audio.get_stream_playback() as AudioStreamGeneratorPlayback


func _play_blip() -> void:
	var random_pitch: float = _voice_pitch * _rng.randf_range(0.95, 1.05)
	if blip_stream != null:
		typewriter_audio.pitch_scale = random_pitch
		typewriter_audio.play()
		return
	if _generator_playback == null:
		return

	var frames: int = 180
	if _generator_playback.get_frames_available() < frames:
		return
	var mix_rate: float = 22050.0
	var frequency: float = 520.0 * random_pitch
	for index: int in range(frames):
		var t: float = float(index) / mix_rate
		var envelope: float = 1.0 - float(index) / float(frames)
		var sample: float = sin(TAU * frequency * t) * 0.045 * envelope
		_generator_playback.push_frame(Vector2(sample, sample))


func _should_blip(character: String) -> bool:
	return not character.is_empty() and character != " " and character != "\n" and not [".", ",", "!", "?", ";", ":"].has(character)
'''

DIALOGUE_SCENE = r'''[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="res://scripts/presentation/spore_cinematic_dialogue_3d.gd" id="1_script"]

[sub_resource type="StyleBoxFlat" id="Style_dialogue"]
bg_color = Color(0.035, 0.05, 0.08, 0.98)
border_width_left = 2
border_width_top = 2
border_width_right = 2
border_width_bottom = 2
border_color = Color(0.48, 0.82, 1, 1)
corner_radius_top_left = 18
corner_radius_top_right = 18
corner_radius_bottom_right = 18
corner_radius_bottom_left = 18
shadow_color = Color(0, 0, 0, 0.5)
shadow_size = 10

[node name="CinematicDialogue3D" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 0
script = ExtResource("1_script")

[node name="Dimmer" type="ColorRect" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
color = Color(0.01, 0.015, 0.03, 0.38)

[node name="LetterboxTop" type="ColorRect" parent="."]
layout_mode = 1
anchors_preset = 10
anchor_right = 1.0
offset_bottom = 54.0
grow_horizontal = 2
mouse_filter = 2
color = Color(0, 0, 0, 0.88)

[node name="LetterboxBottom" type="ColorRect" parent="."]
layout_mode = 1
anchors_preset = 12
anchor_top = 1.0
anchor_right = 1.0
anchor_bottom = 1.0
offset_top = -54.0
grow_horizontal = 2
grow_vertical = 0
mouse_filter = 2
color = Color(0, 0, 0, 0.88)

[node name="DialoguePanel" type="Panel" parent="."]
layout_mode = 1
anchors_preset = 12
anchor_left = 0.055
anchor_top = 1.0
anchor_right = 0.945
anchor_bottom = 1.0
offset_top = -238.0
offset_bottom = -64.0
grow_horizontal = 2
grow_vertical = 0
pivot_offset = Vector2(560, 87)
theme_override_styles/panel = SubResource("Style_dialogue")

[node name="Margin" type="MarginContainer" parent="DialoguePanel"]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
offset_left = 18.0
offset_top = 12.0
offset_right = -18.0
offset_bottom = -12.0
grow_horizontal = 2
grow_vertical = 2
theme_override_constants/margin_left = 2
theme_override_constants/margin_top = 2
theme_override_constants/margin_right = 2
theme_override_constants/margin_bottom = 2

[node name="Row" type="HBoxContainer" parent="DialoguePanel/Margin"]
layout_mode = 2
theme_override_constants/separation = 18

[node name="PortraitLeft" type="TextureRect" parent="DialoguePanel/Margin/Row"]
custom_minimum_size = Vector2(126, 150)
layout_mode = 2
expand_mode = 1
stretch_mode = 5
mouse_filter = 2

[node name="TextColumn" type="VBoxContainer" parent="DialoguePanel/Margin/Row"]
layout_mode = 2
size_flags_horizontal = 3
theme_override_constants/separation = 6

[node name="SpeakerName" type="Label" parent="DialoguePanel/Margin/Row/TextColumn"]
layout_mode = 2
theme_override_colors/font_color = Color(0.75, 0.9, 1, 1)
theme_override_font_sizes/font_size = 21
text = "Locuteur"

[node name="Message" type="Label" parent="DialoguePanel/Margin/Row/TextColumn"]
custom_minimum_size = Vector2(0, 86)
layout_mode = 2
size_flags_vertical = 3
theme_override_colors/font_color = Color(0.95, 0.96, 0.92, 1)
theme_override_font_sizes/font_size = 21
text = "Dialogue"
autowrap_mode = 2
vertical_alignment = 1

[node name="Footer" type="HBoxContainer" parent="DialoguePanel/Margin/Row/TextColumn"]
layout_mode = 2

[node name="Hint" type="Label" parent="DialoguePanel/Margin/Row/TextColumn/Footer"]
layout_mode = 2
size_flags_horizontal = 3
theme_override_colors/font_color = Color(0.67, 0.73, 0.82, 1)
theme_override_font_sizes/font_size = 11
text = "Entrée / Espace / clic"

[node name="AdvancePulse" type="Label" parent="DialoguePanel/Margin/Row/TextColumn/Footer"]
layout_mode = 2
theme_override_colors/font_color = Color(1, 0.83, 0.36, 1)
theme_override_font_sizes/font_size = 17
text = "▼"

[node name="Continue" type="Button" parent="DialoguePanel/Margin/Row/TextColumn/Footer"]
custom_minimum_size = Vector2(170, 32)
layout_mode = 2
text = "CONTINUER  ▸"
focus_mode = 0

[node name="PortraitRight" type="TextureRect" parent="DialoguePanel/Margin/Row"]
custom_minimum_size = Vector2(126, 150)
layout_mode = 2
expand_mode = 1
stretch_mode = 5
mouse_filter = 2

[node name="FadeRect" type="ColorRect" parent="."]
z_index = 100
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
color = Color(0, 0, 0, 0)

[node name="TypewriterAudio" type="AudioStreamPlayer" parent="."]
'''

RUNNER_SCRIPT = r'''class_name SporeCinematicPlayer3D
extends Node

const CinematicCatalog = preload("res://scripts/catalogs/cinematic_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")

@export var dialogue_scene: PackedScene = preload("res://scenes/ui/cinematic_dialogue_3d.tscn")
@export_range(0, 8, 1) var max_nested_depth: int = 6

var _host: Node = null
var _ui_parent: Control = null
var _dialogue: SporeCinematicDialogue3D = null
var _music_player: AudioStreamPlayer = null
var _sfx_player: AudioStreamPlayer = null
var _running: bool = false


func configure(host: Node, ui_parent: Control) -> void:
	_host = host
	_ui_parent = ui_parent
	_ensure_runtime()


func is_running() -> bool:
	return _running


func play(cinematic_id: String) -> bool:
	if cinematic_id.is_empty():
		return false
	_ensure_runtime()
	var definition: Resource = CinematicCatalog.definition(cinematic_id)
	if definition == null:
		return false

	_running = true
	await _run_actions(definition.get("actions"), 0)
	if _host != null and _host.has_method("cinematic_3d_reset_camera"):
		_host.call("cinematic_3d_reset_camera", 0.20)
		await get_tree().create_timer(0.20).timeout
		if _host.has_method("cinematic_3d_release_camera_override"):
			_host.call("cinematic_3d_release_camera_override")
	if _dialogue != null:
		_dialogue.hide_all()
	_running = false
	return true


func _ensure_runtime() -> void:
	if _ui_parent != null and (_dialogue == null or not is_instance_valid(_dialogue)):
		var instance: Node = dialogue_scene.instantiate()
		if instance is SporeCinematicDialogue3D:
			_dialogue = instance as SporeCinematicDialogue3D
			_ui_parent.add_child(_dialogue)

	if _music_player == null:
		_music_player = AudioStreamPlayer.new()
		_music_player.name = "CinematicMusic3D"
		add_child(_music_player)
	if _sfx_player == null:
		_sfx_player = AudioStreamPlayer.new()
		_sfx_player.name = "CinematicSfx3D"
		add_child(_sfx_player)


func _run_actions(raw_actions: Variant, depth: int) -> void:
	if depth > max_nested_depth or not (raw_actions is Array):
		return
	for action_var: Variant in raw_actions:
		if action_var == null:
			continue
		var action: Resource = action_var as Resource
		if action == null:
			continue

		var action_type: String = String(action.get("action_type"))
		var delay: float = float(action.get("delay_seconds"))
		if action_type == "wait":
			await get_tree().create_timer(maxf(0.1, delay)).timeout
			continue
		if delay > 0.0:
			await get_tree().create_timer(delay).timeout

		match action_type:
			"play_cinematic":
				var nested_id: String = String(action.get("cinematic_id"))
				var nested: Resource = CinematicCatalog.definition(nested_id)
				if nested != null:
					await _run_actions(nested.get("actions"), depth + 1)
			"dialogue":
				await _play_dialogue(action)
			"camera_focus_cell":
				var cell_duration: float = float(action.get("camera_duration"))
				_call_host("cinematic_3d_focus_cell", [action.get("cell"), float(action.get("camera_zoom")), cell_duration])
				if cell_duration > 0.0:
					await get_tree().create_timer(cell_duration).timeout
			"camera_focus_unit":
				var unit_duration: float = float(action.get("camera_duration"))
				_call_host("cinematic_3d_focus_unit", [String(action.get("unit_id")), float(action.get("camera_zoom")), unit_duration])
				if unit_duration > 0.0:
					await get_tree().create_timer(unit_duration).timeout
			"camera_zoom":
				var zoom_duration: float = float(action.get("camera_duration"))
				_call_host("cinematic_3d_zoom", [float(action.get("camera_zoom")), zoom_duration])
				if zoom_duration > 0.0:
					await get_tree().create_timer(zoom_duration).timeout
			"camera_reset":
				var reset_duration: float = float(action.get("camera_duration"))
				_call_host("cinematic_3d_reset_camera", [reset_duration])
				if reset_duration > 0.0:
					await get_tree().create_timer(reset_duration).timeout
				_call_host("cinematic_3d_release_camera_override", [])
			"camera_shake":
				_call_host("cinematic_3d_camera_shake", [float(maxi(1, int(action.get("value"))))])
				await get_tree().create_timer(0.18).timeout
			"fade_out":
				if _dialogue != null:
					_dialogue.visible = true
					await _dialogue.set_fade_alpha(1.0, float(action.get("camera_duration")))
			"fade_in":
				if _dialogue != null:
					_dialogue.visible = true
					await _dialogue.set_fade_alpha(0.0, float(action.get("camera_duration")))
			"play_music":
				_play_audio(action, _music_player)
			"stop_music":
				_music_player.stop()
			"play_sfx":
				_play_audio(action, _sfx_player)
			_:
				if _host != null and _host.has_method("cinematic_3d_execute_action"):
					_host.call("cinematic_3d_execute_action", action)


func _play_dialogue(action: Resource) -> void:
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

	var portrait: Texture2D = _resolve_portrait(action, speaker)
	var accent: String = _speaker_accent(unit_id, speaker)
	var chars_per_second: float = float(action.get("text_speed"))
	var voice_pitch: float = float(action.get("voice_pitch"))
	var blip_every: int = int(action.get("blip_every"))

	await _dialogue.present_line(
		speaker,
		String(action.get("message")),
		portrait,
		String(action.get("portrait_side")),
		bool(action.get("wait_for_input")),
		float(action.get("auto_advance_seconds")),
		chars_per_second,
		voice_pitch,
		blip_every,
		accent
	)


func _resolve_portrait(action: Resource, speaker: String) -> Texture2D:
	var explicit_path: String = String(action.get("portrait_path"))
	if not explicit_path.is_empty() and ResourceLoader.exists(explicit_path):
		return load(explicit_path) as Texture2D

	var unit_id: String = String(action.get("unit_id"))
	if not unit_id.is_empty():
		var unit: Resource = UnitCatalog.definition(unit_id)
		if unit != null:
			var visual_id: String = String(unit.get("visual_id"))
			if visual_id.is_empty():
				visual_id = unit_id
			var visual: Resource = VisualCatalog.definition(visual_id)
			if visual != null:
				var path: String = String(visual.get("portrait_path"))
				if not path.is_empty() and ResourceLoader.exists(path):
					return load(path) as Texture2D

	for candidate_id: String in UnitCatalog.all_unit_ids():
		var candidate: Resource = UnitCatalog.definition(candidate_id)
		if candidate == null or String(candidate.get("display_name")).to_lower() != speaker.to_lower():
			continue
		var candidate_visual_id: String = String(candidate.get("visual_id"))
		if candidate_visual_id.is_empty():
			candidate_visual_id = candidate_id
		var candidate_visual: Resource = VisualCatalog.definition(candidate_visual_id)
		if candidate_visual != null:
			var candidate_path: String = String(candidate_visual.get("portrait_path"))
			if not candidate_path.is_empty() and ResourceLoader.exists(candidate_path):
				return load(candidate_path) as Texture2D
	return null


func _speaker_accent(unit_id: String, speaker: String) -> String:
	if speaker.to_lower() == "narrateur":
		return "narrator"
	if _host != null and _host.has_method("cinematic_3d_unit_team"):
		var team: String = String(_host.call("cinematic_3d_unit_team", unit_id))
		if team == "enemy":
			return "enemy"
		if team == "player":
			return "player"
	return "neutral"


func _play_audio(action: Resource, player: AudioStreamPlayer) -> void:
	if player == null:
		return
	var audio_path: String = String(action.get("audio_path"))
	if audio_path.is_empty() or not ResourceLoader.exists(audio_path):
		return
	var stream: AudioStream = load(audio_path) as AudioStream
	if stream == null:
		return
	player.stream = stream
	player.volume_db = float(action.get("volume_db"))
	player.play()


func _call_host(method_name: String, args: Array) -> void:
	if _host == null or not _host.has_method(method_name):
		return
	_host.callv(method_name, args)
'''

RUNNER_SCENE = r'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/presentation/spore_cinematic_player_3d.gd" id="1_script"]

[node name="CinematicPlayer3D" type="Node"]
script = ExtResource("1_script")
'''

write(ROOT / "scripts/presentation/spore_cinematic_dialogue_3d.gd", DIALOGUE_SCRIPT)
write(ROOT / "scenes/ui/cinematic_dialogue_3d.tscn", DIALOGUE_SCENE)
write(ROOT / "scripts/presentation/spore_cinematic_player_3d.gd", RUNNER_SCRIPT)
write(ROOT / "scenes/ui/cinematic_player_3d.tscn", RUNNER_SCENE)

# =============================================================================
# Dialogue presentation fields stored in BattleActionDefinition
# =============================================================================
action_def = ACTION_DEF.read_text(encoding="utf-8")
if "var text_speed:" not in action_def:
    anchor = '@export_range(0.0, 30.0, 0.1) var auto_advance_seconds: float = 0.0\n'
    addition = '''\n@export_group("Dialogue Presentation")
@export_range(10.0, 120.0, 1.0) var text_speed: float = 46.0
@export_range(0.55, 1.75, 0.05) var voice_pitch: float = 1.0
@export_range(1, 8, 1) var blip_every: int = 2

@export_group("Cinematic Camera")
'''
    if anchor not in action_def:
        raise RuntimeError("BattleActionDefinition cinematic insertion point not found")
    action_def = action_def.replace(anchor, anchor + addition, 1)
    action_def = action_def.replace('@export_range(0.25, 3.0, 0.05) var camera_zoom', '@export_range(0.25, 3.0, 0.05) var camera_zoom', 1)
ACTION_DEF.write_text(action_def, encoding="utf-8", newline="\n")

# =============================================================================
# Cinematic Editor exposes speed / voice pitch / blip frequency
# =============================================================================
editor = EDITOR.read_text(encoding="utf-8")
if "var action_text_speed: SpinBox" not in editor:
    editor = editor.replace(
        "var action_auto: SpinBox\n",
        "var action_auto: SpinBox\nvar action_text_speed: SpinBox\nvar action_voice_pitch: SpinBox\nvar action_blip_every: SpinBox\n",
        1,
    )

    ui_anchor = 'action_auto = _spin(right, "Auto-avance (s, si attente décochée)", 0, 30, 0.1)\n'
    ui_add = '''action_text_speed = _spin(right, "Dialogue : vitesse écriture (car./s)", 10, 120, 1)\n\taction_voice_pitch = _spin(right, "Dialogue : hauteur voix", 0.55, 1.75, 0.05)\n\taction_blip_every = _spin(right, "Dialogue : blip tous les N caractères", 1, 8, 1)\n'''
    if ui_anchor not in editor:
        raise RuntimeError("Cinematic editor UI insertion point not found")
    editor = editor.replace(ui_anchor, ui_anchor + "\t" + ui_add, 1)

    select_anchor = "\taction_auto.value = float(action.auto_advance_seconds)\n"
    select_add = "\taction_text_speed.value = float(action.text_speed)\n\taction_voice_pitch.value = float(action.voice_pitch)\n\taction_blip_every.value = int(action.blip_every)\n"
    if select_anchor not in editor:
        raise RuntimeError("Cinematic editor selection insertion point not found")
    editor = editor.replace(select_anchor, select_anchor + select_add, 1)

    apply_anchor = "\taction.auto_advance_seconds = float(action_auto.value)\n"
    apply_add = "\taction.text_speed = float(action_text_speed.value)\n\taction.voice_pitch = float(action_voice_pitch.value)\n\taction.blip_every = int(action_blip_every.value)\n"
    if apply_anchor not in editor:
        raise RuntimeError("Cinematic editor apply insertion point not found")
    editor = editor.replace(apply_anchor, apply_anchor + apply_add, 1)

EDITOR.write_text(editor, encoding="utf-8", newline="\n")

# =============================================================================
# Board cleanup: remove the earlier hardcoded prototype dialogue if present
# =============================================================================
board = BOARD.read_text(encoding="utf-8")

for name in [
    "_start_battle_intro_if_needed",
    "_build_intro_dialogue_lines",
    "_ensure_intro_dialogue_ui",
    "_ensure_intro_dialogue_audio",
    "_show_next_intro_dialogue_line",
    "_apply_intro_dialogue_style",
    "_update_intro_dialogue_typing",
    "_play_intro_dialogue_blip",
    "_advance_intro_dialogue",
    "_finish_intro_dialogue",
]:
    board = replace_function(board, name, None)

board = re.sub(r"(?m)^var _intro_dialogue[^\n]*\n", "", board)
board = board.replace("\t_ensure_intro_dialogue_ui()\n", "")
board = board.replace("\t_update_intro_dialogue_typing(delta)\n", "")
board = board.replace("not _intro_dialogue_running and ", "")
board = re.sub(
    r"(?ms)\n\tif _intro_dialogue_running:\n.*?(?=\tif event is InputEventMouseMotion:)",
    "\n",
    board,
)

# =============================================================================
# Board integration with generic runner
# =============================================================================
if "CinematicPlayerScene" not in board:
    preload_anchor = 'const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")\n'
    if preload_anchor not in board:
        raise RuntimeError("Board preload insertion point not found")
    board = board.replace(
        preload_anchor,
        preload_anchor + 'const CinematicPlayerScene = preload("res://scenes/ui/cinematic_player_3d.tscn")\n',
        1,
    )

if "var _cinematic_player_3d:" not in board:
    var_anchor = "var _ui_layer: CanvasLayer\n"
    if var_anchor not in board:
        raise RuntimeError("Board runtime variable insertion point not found")
    board = board.replace(
        var_anchor,
        var_anchor
        + "var _cinematic_player_3d: SporeCinematicPlayer3D = null\n"
        + "var _cinematic_camera_active: bool = false\n"
        + "var _cinematic_camera_saved_focus: Vector3 = Vector3.ZERO\n"
        + "var _cinematic_camera_saved_distance: float = 12.5\n"
        + "var _cinematic_end_started: bool = false\n",
        1,
    )

integration = '''func _ensure_cinematic_player_3d() -> void:
	if _cinematic_player_3d != null and is_instance_valid(_cinematic_player_3d):
		return

	_cinematic_player_3d = get_node_or_null("CinematicPlayer3D") as SporeCinematicPlayer3D
	if _cinematic_player_3d == null:
		var instance: Node = CinematicPlayerScene.instantiate()
		if not (instance is SporeCinematicPlayer3D):
			return
		_cinematic_player_3d = instance as SporeCinematicPlayer3D
		add_child(_cinematic_player_3d)

	var root: Control = null
	if _ui_layer != null:
		root = _ui_layer.get_node_or_null("Root") as Control
	if root != null:
		_cinematic_player_3d.configure(self, root)


func _play_mission_intro_3d() -> void:
	_ensure_cinematic_player_3d()
	var mission: Resource = MissionCatalog.definition(mission_index)
	var cinematic_id: String = String(mission.get("intro_cinematic_id")) if mission != null else ""
	if _cinematic_player_3d != null and not cinematic_id.is_empty():
		player_busy = true
		await _cinematic_player_3d.play(cinematic_id)
		player_busy = false
	_start_next_activation()


func _update_cinematic_end_flow_3d() -> void:
	if not battle_finished or _cinematic_end_started:
		return
	_cinematic_end_started = true
	call_deferred("_play_mission_end_cinematic_3d", _cinematic_victory_state_3d())


func _cinematic_victory_state_3d() -> bool:
	if has_method("_mission_result_3d"):
		var mission_result: int = int(call("_mission_result_3d"))
		if mission_result != 0:
			return mission_result > 0
	var living_players: int = 0
	var living_enemies: int = 0
	for actor: SporeUnitActor3D in player_actors:
		if actor != null and actor.alive:
			living_players += 1
	for actor: SporeUnitActor3D in enemy_actors:
		if actor != null and actor.alive:
			living_enemies += 1
	if living_players <= 0:
		return false
	return living_enemies <= 0 or battle_finished


func _play_mission_end_cinematic_3d(victory: bool) -> void:
	_ensure_cinematic_player_3d()
	var mission: Resource = MissionCatalog.definition(mission_index)
	var cinematic_id: String = ""
	if mission != null:
		cinematic_id = String(
			mission.get("victory_cinematic_id")
			if victory
			else mission.get("defeat_cinematic_id")
		)
	player_busy = true
	enemy_busy = false
	if _cinematic_player_3d != null and not cinematic_id.is_empty():
		await _cinematic_player_3d.play(cinematic_id)
	player_busy = false
	if has_method("_show_battle_result"):
		call("_show_battle_result", victory)


func cinematic_3d_unit_team(unit_id: String) -> String:
	var actor: SporeUnitActor3D = _actor_by_unit_id(unit_id)
	return actor.team if actor != null else ""


func cinematic_3d_focus_cell(cell_value: Vector2i, zoom: float, duration: float) -> void:
	if map_root == null or not map_root.is_cell_valid(cell_value):
		return
	_begin_cinematic_camera_override_3d()
	var local_position: Vector3 = map_root.cell_top_local(cell_value)
	_camera_focus_target = Vector3(local_position.x, 0.0, local_position.z)
	_camera_target_distance = clampf(_cinematic_camera_saved_distance / maxf(0.25, zoom), 6.0, 22.0)


func cinematic_3d_focus_unit(unit_id: String, zoom: float, duration: float) -> void:
	var actor: SporeUnitActor3D = _actor_by_unit_id(unit_id)
	if actor == null:
		return
	_begin_cinematic_camera_override_3d()
	_camera_focus_target = Vector3(actor.position.x, 0.0, actor.position.z)
	_camera_target_distance = clampf(_cinematic_camera_saved_distance / maxf(0.25, zoom), 6.0, 22.0)


func cinematic_3d_zoom(zoom: float, duration: float) -> void:
	_begin_cinematic_camera_override_3d()
	_camera_target_distance = clampf(_cinematic_camera_saved_distance / maxf(0.25, zoom), 6.0, 22.0)


func cinematic_3d_reset_camera(duration: float) -> void:
	if not _cinematic_camera_active:
		return
	_camera_focus_target = _cinematic_camera_saved_focus
	_camera_target_distance = _cinematic_camera_saved_distance


func cinematic_3d_release_camera_override() -> void:
	_cinematic_camera_active = false


func cinematic_3d_camera_shake(intensity: float) -> void:
	_camera_shake_strength = maxf(_camera_shake_strength, clampf(intensity * 0.025, 0.04, 0.28))


func cinematic_3d_execute_action(action: Resource) -> void:
	if action == null:
		return
	var action_type: String = String(action.get("action_type"))
	match action_type:
		"message":
			_log("ÉVÉNEMENT : %s" % String(action.get("message")))
		"set_objective_text":
			_log("OBJECTIF : %s" % String(action.get("message")))
		"set_phase":
			_log("PHASE : %s" % String(action.get("message")))
		_:
			pass


func _begin_cinematic_camera_override_3d() -> void:
	if _cinematic_camera_active:
		return
	_cinematic_camera_active = true
	_cinematic_camera_saved_focus = _camera_focus_target
	_cinematic_camera_saved_distance = _camera_target_distance
'''
board = insert_before(
    board,
    "_build_turn_order",
    integration,
    "func _ensure_cinematic_player_3d(",
)

# Ready uses the cinematic resource instead of starting battle immediately.
ready_pattern = re.compile(r"(?ms)^func _ready\(\) -> void:\n.*?(?=^func |\Z)")
m = ready_pattern.search(board)
if not m:
    raise RuntimeError("Board _ready() not found")
ready = m.group(0)
ready = ready.replace("\t_start_battle_intro_if_needed()\n", "")
ready = ready.replace("\t_start_next_activation()\n", "")
if "_ensure_cinematic_player_3d()" not in ready:
    ready = ready.replace("\t_build_turn_order()\n", "\t_build_turn_order()\n\t_ensure_cinematic_player_3d()\n", 1)
if "_play_mission_intro_3d" not in ready:
    ready = ready.replace("\t_update_ui_text()\n", "\t_update_ui_text()\n\tcall_deferred(\"_play_mission_intro_3d\")\n", 1)
board = board[:m.start()] + ready + board[m.end():]

# Process checks for mission-end cinematic and disables the older presentation hook if present.
board = board.replace("\t_update_battle_end_presentation()\n", "")
process_pattern = re.compile(r"(?ms)^func _process\(delta: float\) -> void:\n.*?(?=^func |\Z)")
m = process_pattern.search(board)
if not m:
    raise RuntimeError("Board _process() not found")
process = m.group(0)
if "_update_cinematic_end_flow_3d()" not in process:
    first_newline = process.find("\n")
    process = process[:first_newline + 1] + "\t_update_cinematic_end_flow_3d()\n" + process[first_newline + 1:]
    board = board[:m.start()] + process + board[m.end():]

# Ensure runtime player is configured after UI exists.
ensure_pattern = re.compile(r"(?ms)^func _ensure_runtime_nodes\(\) -> void:\n.*?(?=^func |\Z)")
m = ensure_pattern.search(board)
if not m:
    raise RuntimeError("Board _ensure_runtime_nodes() not found")
ensure = m.group(0)
if "_ensure_cinematic_player_3d()" not in ensure:
    if "\t_build_ui()\n" not in ensure:
        raise RuntimeError("Board _build_ui() hook not found")
    ensure = ensure.replace("\t_build_ui()\n", "\t_build_ui()\n\t_ensure_cinematic_player_3d()\n", 1)
    board = board[:m.start()] + ensure + board[m.end():]

# Cinematic camera must override sticky follow / action camera.
# First add a priority branch so this also works after previous camera patches.
camera_pattern = re.compile(r"(?ms)^func _update_camera_smoothing\(delta: float\) -> void:\n.*?(?=^func |\Z)")
cm = camera_pattern.search(board)
if cm:
    camera_func = cm.group(0)
    if "# CINEMATIC_CAMERA_PRIORITY" not in camera_func:
        guard = "\tif not _camera_initialized:\n\t\treturn\n"
        priority = "\t# CINEMATIC_CAMERA_PRIORITY\n\tif _cinematic_camera_active:\n\t\tvar cinematic_weight: float = 1.0 - exp(-camera_smoothing * maxf(0.0, delta))\n\t\t_camera_current_angle = lerpf(_camera_current_angle, _camera_target_angle, cinematic_weight)\n\t\t_camera_current_distance = lerpf(_camera_current_distance, _camera_target_distance, cinematic_weight)\n\t\t_camera_focus_current = _camera_focus_current.lerp(_camera_focus_target, cinematic_weight)\n\t\t_apply_camera_transform()\n\t\treturn\n"
        if guard in camera_func:
            camera_func = camera_func.replace(guard, guard + priority, 1)
            board = board[:cm.start()] + camera_func + board[cm.end():]

board = board.replace(
    "var following_projectile: bool = projectile_camera_follow and _projectile_follow_vfx != null and is_instance_valid(_projectile_follow_vfx)",
    "var following_projectile: bool = not _cinematic_camera_active and projectile_camera_follow and _projectile_follow_vfx != null and is_instance_valid(_projectile_follow_vfx)",
)
board = board.replace(
    "elif _action_camera_timer > 0.0:\n\t\t_camera_focus_target = _action_camera_focus\n\telif camera_follow_active and active_actor != null and active_actor.alive:",
    "elif not _cinematic_camera_active and _action_camera_timer > 0.0:\n\t\t_camera_focus_target = _action_camera_focus\n\telif not _cinematic_camera_active and camera_follow_active and active_actor != null and active_actor.alive:",
)
board = board.replace(
    "elif _action_camera_timer > 0.0:\n\t\teffective_distance = maxf(6.0, effective_distance - _action_camera_zoom)",
    "elif not _cinematic_camera_active and _action_camera_timer > 0.0:\n\t\teffective_distance = maxf(6.0, effective_distance - _action_camera_zoom)",
)

BOARD.write_text(board, encoding="utf-8", newline="\n")

# =============================================================================
# Make CinematicPlayer visible in the mission scene editor.
# =============================================================================
scene = MISSION_SCENE.read_text(encoding="utf-8")
if 'cinematic_player_3d.tscn' not in scene:
    scene = scene.replace('[gd_scene load_steps=2 format=3]', '[gd_scene load_steps=3 format=3]', 1)
    scene = scene.replace(
        '[ext_resource type="Script" path="res://scripts/prototypes/spore_battle_board_3d.gd" id="1_board"]\n',
        '[ext_resource type="Script" path="res://scripts/prototypes/spore_battle_board_3d.gd" id="1_board"]\n'
        '[ext_resource type="PackedScene" path="res://scenes/ui/cinematic_player_3d.tscn" id="2_cinematic"]\n',
        1,
    )
    scene += '\n[node name="CinematicPlayer3D" parent="." instance=ExtResource("2_cinematic")]\n'
MISSION_SCENE.write_text(scene, encoding="utf-8", newline="\n")

# =============================================================================
# Mission 1 cinematics remain data-driven and editable in Sporebound Studio.
# =============================================================================
INTRO = r'''[gd_resource type="Resource" script_class="SporeCinematicDefinition" load_steps=12 format=3]

[ext_resource type="Script" path="res://scripts/data/cinematic_definition.gd" id="1_cine"]
[ext_resource type="Script" path="res://scripts/data/battle_action_definition.gd" id="2_action"]

[sub_resource type="Resource" id="FadeOut"]
script = ExtResource("2_action")
id = "fade_out"
action_type = "fade_out"
camera_duration = 0.18

[sub_resource type="Resource" id="FocusBoss"]
script = ExtResource("2_action")
id = "focus_boss"
action_type = "camera_focus_unit"
unit_id = "dj_morille"
camera_zoom = 1.28
camera_duration = 0.38

[sub_resource type="Resource" id="FadeIn"]
script = ExtResource("2_action")
id = "fade_in"
action_type = "fade_in"
camera_duration = 0.24

[sub_resource type="Resource" id="BossLine1"]
script = ExtResource("2_action")
id = "boss_line_1"
action_type = "dialogue"
message = "Oh. Des touristes. Et pas même de billet pour mon jardin."
unit_id = "dj_morille"
speaker = "DJ Morille"
portrait_side = "right"
wait_for_input = true
text_speed = 36.0
voice_pitch = 0.88
blip_every = 2

[sub_resource type="Resource" id="FocusLuma"]
script = ExtResource("2_action")
id = "focus_luma"
action_type = "camera_focus_unit"
unit_id = "luma"
camera_zoom = 1.18
camera_duration = 0.28

[sub_resource type="Resource" id="LumaLine1"]
script = ExtResource("2_action")
id = "luma_line_1"
action_type = "dialogue"
message = "On vient seulement récupérer une couronne. Ensuite, on disparaît."
unit_id = "luma"
speaker = "Luma"
portrait_side = "left"
wait_for_input = true
text_speed = 48.0
voice_pitch = 1.05
blip_every = 2

[sub_resource type="Resource" id="FocusMomo"]
script = ExtResource("2_action")
id = "focus_momo"
action_type = "camera_focus_unit"
unit_id = "momo"
camera_zoom = 1.15
camera_duration = 0.22

[sub_resource type="Resource" id="MomoLine"]
script = ExtResource("2_action")
id = "momo_line"
action_type = "dialogue"
message = "Il vient vraiment de dire « billet pour mon jardin » ?"
unit_id = "momo"
speaker = "Momo"
portrait_side = "left"
wait_for_input = true
text_speed = 52.0
voice_pitch = 1.12
blip_every = 2

[sub_resource type="Resource" id="FocusCrown"]
script = ExtResource("2_action")
id = "focus_crown"
action_type = "camera_focus_cell"
cell = Vector2i(9, 0)
camera_zoom = 1.35
camera_duration = 0.34

[sub_resource type="Resource" id="BossLine2"]
script = ExtResource("2_action")
id = "boss_line_2"
action_type = "dialogue"
message = "MA couronne. Groove propriétaire. Les spores ! Montez le volume !"
unit_id = "dj_morille"
speaker = "DJ Morille"
portrait_side = "right"
wait_for_input = true
text_speed = 34.0
voice_pitch = 0.84
blip_every = 2

[sub_resource type="Resource" id="Reset"]
script = ExtResource("2_action")
id = "camera_reset"
action_type = "camera_reset"
camera_zoom = 1.0
camera_duration = 0.28

[resource]
script = ExtResource("1_cine")
id = "intro_crown"
display_name = "Intro — Couronne Beatbox"
description = "Intro JRPG éditable dans Sporebound Studio."
actions = Array[Resource]([SubResource("FadeOut"), SubResource("FocusBoss"), SubResource("FadeIn"), SubResource("BossLine1"), SubResource("FocusLuma"), SubResource("LumaLine1"), SubResource("FocusMomo"), SubResource("MomoLine"), SubResource("FocusCrown"), SubResource("BossLine2"), SubResource("Reset")])
'''

VICTORY = r'''[gd_resource type="Resource" script_class="SporeCinematicDefinition" load_steps=9 format=3]

[ext_resource type="Script" path="res://scripts/data/cinematic_definition.gd" id="1_cine"]
[ext_resource type="Script" path="res://scripts/data/battle_action_definition.gd" id="2_action"]

[sub_resource type="Resource" id="FocusLuma"]
script = ExtResource("2_action")
id = "focus_luma"
action_type = "camera_focus_unit"
unit_id = "luma"
camera_zoom = 1.22
camera_duration = 0.30

[sub_resource type="Resource" id="Luma"]
script = ExtResource("2_action")
id = "victory_luma"
action_type = "dialogue"
message = "Couronne récupérée. On rentre avant qu'il ne lance un rappel."
unit_id = "luma"
speaker = "Luma"
portrait_side = "left"
wait_for_input = true
text_speed = 48.0
voice_pitch = 1.04
blip_every = 2

[sub_resource type="Resource" id="Momo"]
script = ExtResource("2_action")
id = "victory_momo"
action_type = "dialogue"
message = "Et les vinyles ? On ne va quand même pas laisser les vinyles."
unit_id = "momo"
speaker = "Momo"
portrait_side = "left"
wait_for_input = true
text_speed = 52.0
voice_pitch = 1.12
blip_every = 2

[sub_resource type="Resource" id="FocusBoss"]
script = ExtResource("2_action")
id = "focus_boss"
action_type = "camera_focus_unit"
unit_id = "dj_morille"
camera_zoom = 1.18
camera_duration = 0.24

[sub_resource type="Resource" id="Boss"]
script = ExtResource("2_action")
id = "victory_boss"
action_type = "dialogue"
message = "Revenez ! Cette couronne n'est même pas accordée !"
unit_id = "dj_morille"
speaker = "DJ Morille"
portrait_side = "right"
wait_for_input = true
text_speed = 35.0
voice_pitch = 0.86
blip_every = 2

[sub_resource type="Resource" id="Luma2"]
script = ExtResource("2_action")
id = "victory_luma_2"
action_type = "dialogue"
message = "Maintenant si."
unit_id = "luma"
speaker = "Luma"
portrait_side = "left"
wait_for_input = true
text_speed = 42.0
voice_pitch = 1.02
blip_every = 2

[sub_resource type="Resource" id="Reset"]
script = ExtResource("2_action")
id = "reset"
action_type = "camera_reset"
camera_duration = 0.25

[resource]
script = ExtResource("1_cine")
id = "victory_crown"
display_name = "Victoire — Couronne"
description = "Dialogue de victoire JRPG éditable."
actions = Array[Resource]([SubResource("FocusLuma"), SubResource("Luma"), SubResource("Momo"), SubResource("FocusBoss"), SubResource("Boss"), SubResource("Luma2"), SubResource("Reset")])
'''

DEFEAT = r'''[gd_resource type="Resource" script_class="SporeCinematicDefinition" load_steps=8 format=3]

[ext_resource type="Script" path="res://scripts/data/cinematic_definition.gd" id="1_cine"]
[ext_resource type="Script" path="res://scripts/data/battle_action_definition.gd" id="2_action"]

[sub_resource type="Resource" id="FocusBoss"]
script = ExtResource("2_action")
id = "focus_boss"
action_type = "camera_focus_unit"
unit_id = "dj_morille"
camera_zoom = 1.22
camera_duration = 0.28

[sub_resource type="Resource" id="Boss"]
script = ExtResource("2_action")
id = "defeat_boss"
action_type = "dialogue"
message = "Et c'est ainsi que s'achève votre tournée. Merci, bonsoir !"
unit_id = "dj_morille"
speaker = "DJ Morille"
portrait_side = "right"
wait_for_input = true
text_speed = 35.0
voice_pitch = 0.84
blip_every = 2

[sub_resource type="Resource" id="Momo"]
script = ExtResource("2_action")
id = "defeat_momo"
action_type = "dialogue"
message = "Je déteste ce type."
unit_id = "momo"
speaker = "Momo"
portrait_side = "left"
wait_for_input = true
text_speed = 50.0
voice_pitch = 1.12
blip_every = 2

[sub_resource type="Resource" id="Luma"]
script = ExtResource("2_action")
id = "defeat_luma"
action_type = "dialogue"
message = "On recommence. Et cette fois, personne ne marche dans les spores."
unit_id = "luma"
speaker = "Luma"
portrait_side = "left"
wait_for_input = true
text_speed = 46.0
voice_pitch = 1.02
blip_every = 2

[sub_resource type="Resource" id="Fade"]
script = ExtResource("2_action")
id = "fade_out"
action_type = "fade_out"
camera_duration = 0.22

[sub_resource type="Resource" id="Reset"]
script = ExtResource("2_action")
id = "reset"
action_type = "camera_reset"
camera_duration = 0.20

[sub_resource type="Resource" id="FadeIn"]
script = ExtResource("2_action")
id = "fade_in"
action_type = "fade_in"
camera_duration = 0.20

[resource]
script = ExtResource("1_cine")
id = "defeat_crown"
display_name = "Défaite — Couronne"
description = "Dialogue de défaite spécifique à la mission 1."
actions = Array[Resource]([SubResource("FocusBoss"), SubResource("Boss"), SubResource("Momo"), SubResource("Luma"), SubResource("Fade"), SubResource("Reset"), SubResource("FadeIn")])
'''

write(ROOT / "data/cinematics/intro_crown.tres", INTRO)
write(ROOT / "data/cinematics/victory_crown.tres", VICTORY)
write(ROOT / "data/cinematics/defeat_crown.tres", DEFEAT)

mission = MISSION1.read_text(encoding="utf-8")
mission = mission.replace('defeat_cinematic_id = "defeat_generic"', 'defeat_cinematic_id = "defeat_crown"')
MISSION1.write_text(mission, encoding="utf-8", newline="\n")

print("[OK] Generic 3D cinematic/JRPG refactor applied.")
print()
print("Created:")
print("  scenes/ui/cinematic_dialogue_3d.tscn")
print("  scenes/ui/cinematic_player_3d.tscn")
print("  scripts/presentation/spore_cinematic_dialogue_3d.gd")
print("  scripts/presentation/spore_cinematic_player_3d.gd")
print("  data/cinematics/defeat_crown.tres")
print()
print("Refactored:")
print("  battle_board_3d -> only starts/ends generic cinematics")
print("  BattleActionDefinition -> text speed / voice pitch / blip frequency")
print("  Cinematic Editor -> edits those three properties")
print("  Mission 1 -> data-driven intro/victory/defeat")
print()
print("The old hardcoded intro-dialogue prototype is removed when detected.")
print("All cinematic content remains editable through Sporebound Studio / .tres resources.")
