#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
EDITOR = ROOT / "addons/sporebound_studio/cinematic_editor.gd"
RUNNER = ROOT / "scripts/presentation/spore_cinematic_player_3d.gd"
DIALOGUE_SCENE = ROOT / "scenes/ui/cinematic_dialogue_3d.tscn"

required = [EDITOR, RUNNER, DIALOGUE_SCENE]
for path in required:
    if not path.exists():
        print(f"[ERROR] Missing file: {path}")
        print("Apply refactor_cinematics_3d_jrpg.py and the JRPG preview pass first.")
        sys.exit(1)


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".timeline_v2_backup")
    if not target.exists():
        target.write_bytes(path.read_bytes())


def replace_function(text: str, name: str, code: str) -> str:
    pattern = re.compile(
        rf"(?ms)^func {re.escape(name)}\([^\n]*\)(?: -> [^:\n]+)?:\n.*?(?=^func |\Z)"
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Function not found: {name}")
    return text[:match.start()] + code.rstrip() + "\n\n\n" + text[match.end():]


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


for path in required:
    backup(path)

# =============================================================================
# Reusable action card
# =============================================================================
CARD_SCRIPT = r'''@tool
class_name SporeCinematicTimelineCard
extends PanelContainer

signal selected(index: int)
signal drop_requested(from_index: int, to_index: int)
signal duplicate_requested(index: int)
signal delete_requested(index: int)
signal play_from_requested(index: int)

var action_index: int = -1
var action_id: String = ""
var _action_type: String = ""
var _selected: bool = false
var _playing: bool = false

var _index_label: Label
var _type_label: Label
var _summary_label: Label
var _play_button: Button
var _duplicate_button: Button
var _delete_button: Button


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(0.0, 84.0)
	_build_ui()
	gui_input.connect(_on_gui_input)


func configure(
	index: int,
	action: Resource,
	selected_value: bool,
	playing_value: bool = false
) -> void:
	action_index = index
	_selected = selected_value
	_playing = playing_value
	_action_type = String(action.get("action_type")) if action != null else "invalid"
	action_id = String(action.get("id")) if action != null else ""

	if _index_label == null:
		_build_ui()

	_index_label.text = "%02d" % (index + 1)
	_type_label.text = _category_name(_action_type)
	_summary_label.text = _action_summary(action)
	_apply_style()


func set_selected(value: bool) -> void:
	_selected = value
	_apply_style()


func set_playing(value: bool) -> void:
	_playing = value
	_apply_style()


func _build_ui() -> void:
	if _index_label != null:
		return

	var margin: MarginContainer = MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 10)
	margin.add_theme_constant_override("margin_right", 8)
	margin.add_theme_constant_override("margin_top", 8)
	margin.add_theme_constant_override("margin_bottom", 8)
	add_child(margin)

	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	margin.add_child(row)

	_index_label = Label.new()
	_index_label.custom_minimum_size = Vector2(34.0, 0.0)
	_index_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_index_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_index_label.add_theme_font_size_override("font_size", 15)
	_index_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(_index_label)

	var content: VBoxContainer = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 3)
	row.add_child(content)

	_type_label = Label.new()
	_type_label.add_theme_font_size_override("font_size", 12)
	_type_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(_type_label)

	_summary_label = Label.new()
	_summary_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_summary_label.add_theme_font_size_override("font_size", 13)
	_summary_label.add_theme_color_override(
		"font_color",
		Color(0.88, 0.90, 0.94, 1.0)
	)
	_summary_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(_summary_label)

	var buttons: VBoxContainer = VBoxContainer.new()
	buttons.custom_minimum_size.x = 58.0
	buttons.add_theme_constant_override("separation", 3)
	row.add_child(buttons)

	_play_button = _small_button("PLAY")
	_play_button.tooltip_text = "Lire à partir de cette action"
	_play_button.pressed.connect(
		func() -> void:
			play_from_requested.emit(action_index)
	)
	buttons.add_child(_play_button)

	var button_row: HBoxContainer = HBoxContainer.new()
	button_row.add_theme_constant_override("separation", 3)
	buttons.add_child(button_row)

	_duplicate_button = _small_button("DUP")
	_duplicate_button.custom_minimum_size.x = 37.0
	_duplicate_button.tooltip_text = "Dupliquer"
	_duplicate_button.pressed.connect(
		func() -> void:
			duplicate_requested.emit(action_index)
	)
	button_row.add_child(_duplicate_button)

	_delete_button = _small_button("X")
	_delete_button.custom_minimum_size.x = 20.0
	_delete_button.tooltip_text = "Supprimer"
	_delete_button.pressed.connect(
		func() -> void:
			delete_requested.emit(action_index)
	)
	button_row.add_child(_delete_button)


func _small_button(text_value: String) -> Button:
	var button: Button = Button.new()
	button.text = text_value
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size.y = 26.0
	button.add_theme_font_size_override("font_size", 10)
	return button


func _on_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse_event: InputEventMouseButton = event as InputEventMouseButton
		if mouse_event.pressed and mouse_event.button_index == MOUSE_BUTTON_LEFT:
			selected.emit(action_index)


func _get_drag_data(_at_position: Vector2) -> Variant:
	if action_index < 0:
		return null

	var preview: PanelContainer = PanelContainer.new()
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.08, 0.11, 0.17, 0.97)
	style.border_color = _category_color(_action_type)
	style.border_width_left = 2
	style.border_width_top = 2
	style.border_width_right = 2
	style.border_width_bottom = 2
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	preview.add_theme_stylebox_override("panel", style)

	var label: Label = Label.new()
	label.text = "  %02d  %s  " % [action_index + 1, _category_name(_action_type)]
	label.add_theme_font_size_override("font_size", 13)
	preview.add_child(label)
	set_drag_preview(preview)

	return {
		"kind": "spore_cinematic_action",
		"index": action_index,
	}


func _can_drop_data(_at_position: Vector2, data: Variant) -> bool:
	if not (data is Dictionary):
		return false
	var dictionary: Dictionary = data as Dictionary
	return (
		String(dictionary.get("kind", "")) == "spore_cinematic_action"
		and int(dictionary.get("index", -1)) != action_index
	)


func _drop_data(_at_position: Vector2, data: Variant) -> void:
	if not _can_drop_data(Vector2.ZERO, data):
		return
	var dictionary: Dictionary = data as Dictionary
	drop_requested.emit(
		int(dictionary.get("index", -1)),
		action_index
	)


func _apply_style() -> void:
	if not is_inside_tree():
		return

	var color: Color = _category_color(_action_type)
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.055, 0.072, 0.105, 0.98)
	style.border_color = color
	style.border_width_left = 4 if _selected else 2
	style.border_width_top = 2 if _playing else 1
	style.border_width_right = 2 if _playing else 1
	style.border_width_bottom = 2 if _playing else 1
	style.corner_radius_top_left = 9
	style.corner_radius_top_right = 9
	style.corner_radius_bottom_left = 9
	style.corner_radius_bottom_right = 9

	if _selected:
		style.bg_color = Color(0.075, 0.105, 0.155, 1.0)
	if _playing:
		style.bg_color = color.darkened(0.68)
		style.border_color = Color(1.0, 0.84, 0.36, 1.0)
		style.border_width_left = 4
		style.border_width_top = 3
		style.border_width_right = 3
		style.border_width_bottom = 3

	add_theme_stylebox_override("panel", style)

	if _type_label != null:
		_type_label.add_theme_color_override("font_color", color)
	if _index_label != null:
		_index_label.add_theme_color_override(
			"font_color",
			Color(1.0, 0.86, 0.42, 1.0) if _playing else color.lightened(0.18)
		)


func _category_name(action_type: String) -> String:
	if action_type == "dialogue":
		return "DIALOGUE"
	if action_type.begins_with("camera_"):
		return "CAMERA"
	if action_type in ["play_music", "stop_music", "play_sfx"]:
		return "AUDIO"
	if action_type in ["fade_in", "fade_out"]:
		return "FADE"
	if action_type in ["wait", "play_cinematic"]:
		return "FLOW"
	if action_type in ["message", "set_objective_text", "set_phase"]:
		return "MISSION"
	return action_type.to_upper()


func _category_color(action_type: String) -> Color:
	if action_type == "dialogue":
		return Color(0.72, 0.52, 1.0, 1.0)
	if action_type.begins_with("camera_"):
		return Color(0.38, 0.72, 1.0, 1.0)
	if action_type in ["play_music", "stop_music", "play_sfx"]:
		return Color(0.38, 0.88, 0.62, 1.0)
	if action_type in ["fade_in", "fade_out"]:
		return Color(0.82, 0.84, 0.88, 1.0)
	if action_type in ["wait", "play_cinematic"]:
		return Color(1.0, 0.72, 0.34, 1.0)
	if action_type in ["message", "set_objective_text", "set_phase"]:
		return Color(1.0, 0.56, 0.36, 1.0)
	return Color(0.66, 0.72, 0.80, 1.0)


func _action_summary(action: Resource) -> String:
	if action == null:
		return "<action invalide>"
	if action.has_method("summary"):
		return String(action.call("summary"))
	return String(action.get("action_type"))
'''

# =============================================================================
# Reusable timeline widget
# =============================================================================
TIMELINE_SCRIPT = r'''@tool
class_name SporeCinematicTimelineEditor
extends VBoxContainer

const CardScript = preload("res://addons/sporebound_studio/cinematic_timeline_card.gd")

signal item_selected(index: int)
signal move_requested(from_index: int, to_index: int)
signal duplicate_requested(index: int)
signal delete_requested(index: int)
signal play_from_requested(index: int)
signal play_sequence_requested

var _scroll: ScrollContainer
var _cards: VBoxContainer
var _empty_label: Label
var _status_label: Label
var _actions: Array = []
var _selected_index: int = -1
var _playing_action_id: String = ""


func _ready() -> void:
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	custom_minimum_size = Vector2(350.0, 300.0)
	_build_ui()


func _build_ui() -> void:
	if _cards != null:
		return

	var toolbar: HBoxContainer = HBoxContainer.new()
	toolbar.add_theme_constant_override("separation", 6)
	add_child(toolbar)

	var play_all: Button = Button.new()
	play_all.text = "▶ LIRE TOUT"
	play_all.focus_mode = Control.FOCUS_NONE
	play_all.tooltip_text = "Prévisualiser la timeline entière"
	play_all.pressed.connect(
		func() -> void:
			play_sequence_requested.emit()
	)
	toolbar.add_child(play_all)

	var help: Label = Label.new()
	help.text = "glisser-déposer pour réordonner"
	help.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	help.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	help.add_theme_font_size_override("font_size", 10)
	help.add_theme_color_override(
		"font_color",
		Color(0.62, 0.70, 0.80, 1.0)
	)
	toolbar.add_child(help)

	_scroll = ScrollContainer.new()
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_child(_scroll)

	_cards = VBoxContainer.new()
	_cards.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_cards.add_theme_constant_override("separation", 6)
	_scroll.add_child(_cards)

	_empty_label = Label.new()
	_empty_label.text = "Aucune action. Utilise + Action pour commencer."
	_empty_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_empty_label.add_theme_color_override(
		"font_color",
		Color(0.62, 0.68, 0.76, 1.0)
	)
	_cards.add_child(_empty_label)

	_status_label = Label.new()
	_status_label.text = ""
	_status_label.add_theme_font_size_override("font_size", 10)
	_status_label.add_theme_color_override(
		"font_color",
		Color(1.0, 0.82, 0.38, 1.0)
	)
	add_child(_status_label)


func clear() -> void:
	_actions.clear()
	_selected_index = -1
	_playing_action_id = ""
	_rebuild()


func set_actions(actions: Array, selected_index: int = -1) -> void:
	_actions = actions.duplicate()
	_selected_index = selected_index
	_rebuild()


func select(index: int) -> void:
	_selected_index = index
	_update_card_states()


func set_playing_action(action_id: String) -> void:
	_playing_action_id = action_id
	_status_label.text = "Lecture : %s" % action_id if not action_id.is_empty() else ""
	_update_card_states()


func clear_playing_action() -> void:
	_playing_action_id = ""
	_status_label.text = ""
	_update_card_states()


func _rebuild() -> void:
	if _cards == null:
		_build_ui()

	for child: Node in _cards.get_children():
		child.queue_free()

	if _actions.is_empty():
		_empty_label = Label.new()
		_empty_label.text = "Aucune action. Utilise + Action pour commencer."
		_empty_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_empty_label.add_theme_color_override(
			"font_color",
			Color(0.62, 0.68, 0.76, 1.0)
		)
		_cards.add_child(_empty_label)
		return

	for index: int in range(_actions.size()):
		var action: Resource = _actions[index] as Resource
		var card: SporeCinematicTimelineCard = CardScript.new() as SporeCinematicTimelineCard
		_cards.add_child(card)
		var action_id: String = String(action.get("id")) if action != null else ""
		card.configure(
			index,
			action,
			index == _selected_index,
			not _playing_action_id.is_empty() and action_id == _playing_action_id
		)
		card.selected.connect(_on_card_selected)
		card.drop_requested.connect(_on_card_drop)
		card.duplicate_requested.connect(
			func(card_index: int) -> void:
				duplicate_requested.emit(card_index)
		)
		card.delete_requested.connect(
			func(card_index: int) -> void:
				delete_requested.emit(card_index)
		)
		card.play_from_requested.connect(
			func(card_index: int) -> void:
				play_from_requested.emit(card_index)
		)


func _update_card_states() -> void:
	if _cards == null:
		return
	for child: Node in _cards.get_children():
		if not (child is SporeCinematicTimelineCard):
			continue
		var card: SporeCinematicTimelineCard = child as SporeCinematicTimelineCard
		card.set_selected(card.action_index == _selected_index)
		card.set_playing(
			not _playing_action_id.is_empty()
			and card.action_id == _playing_action_id
		)


func _on_card_selected(index: int) -> void:
	_selected_index = index
	_update_card_states()
	item_selected.emit(index)


func _on_card_drop(from_index: int, to_index: int) -> void:
	if from_index == to_index:
		return
	move_requested.emit(from_index, to_index)
'''

write(ROOT / "addons/sporebound_studio/cinematic_timeline_card.gd", CARD_SCRIPT)
write(ROOT / "addons/sporebound_studio/cinematic_timeline_editor.gd", TIMELINE_SCRIPT)

# =============================================================================
# Generic runner: public play_from + playback signals.
# =============================================================================
runner = RUNNER.read_text(encoding="utf-8")

if "signal action_started(action_id: String)" not in runner:
    class_anchor = "extends Node\n"
    if class_anchor not in runner:
        raise RuntimeError("Cinematic player class anchor not found")
    runner = runner.replace(
        class_anchor,
        class_anchor + "\nsignal action_started(action_id: String)\nsignal playback_finished\n",
        1,
    )

if "func play_from(cinematic_id: String" not in runner:
    play_pattern = re.compile(
        r"(?ms)^func play\(cinematic_id: String\) -> bool:\n.*?(?=^func _ensure_runtime\()"
    )
    match = play_pattern.search(runner)
    if not match:
        raise RuntimeError("Could not replace CinematicPlayer3D.play()")

    new_play = '''func play(cinematic_id: String) -> bool:
	return await play_from(cinematic_id, 0)


func play_from(cinematic_id: String, start_index: int = 0) -> bool:
	if cinematic_id.is_empty():
		return false
	_ensure_runtime()
	var definition: Resource = CinematicCatalog.definition(cinematic_id)
	if definition == null:
		return false

	var raw_actions: Variant = definition.get("actions")
	if not (raw_actions is Array):
		return false

	var source: Array = raw_actions as Array
	var selected_actions: Array = []
	var first_index: int = clampi(start_index, 0, source.size())
	for index: int in range(first_index, source.size()):
		selected_actions.append(source[index])

	return await play_actions(selected_actions)


func play_actions(actions: Array) -> bool:
	_ensure_runtime()
	if _running:
		return false

	_running = true
	await _run_actions(actions, 0)

	if _host != null and _host.has_method("cinematic_3d_reset_camera"):
		_host.call("cinematic_3d_reset_camera", 0.20)
		await get_tree().create_timer(0.20).timeout
		if _host.has_method("cinematic_3d_release_camera_override"):
			_host.call("cinematic_3d_release_camera_override")

	if _dialogue != null:
		_dialogue.hide_all()

	_running = false
	playback_finished.emit()
	return true


'''
    runner = runner[:match.start()] + new_play + runner[match.end():]

# Emit the current action id from the common executor.
run_actions_pattern = re.compile(
    r"(?ms)^func _run_actions\(raw_actions: Variant, depth: int\) -> void:\n.*?(?=^func _play_dialogue\()"
)
match = run_actions_pattern.search(runner)
if not match:
    raise RuntimeError("CinematicPlayer3D._run_actions() not found")
run_actions = match.group(0)
if "action_started.emit" not in run_actions:
    anchor = '''\t\tvar action_type: String = String(action.get("action_type"))\n'''
    if anchor not in run_actions:
        raise RuntimeError("CinematicPlayer3D action emission anchor not found")
    run_actions = run_actions.replace(
        anchor,
        '\t\taction_started.emit(String(action.get("id")))\n' + anchor,
        1,
    )
    runner = runner[:match.start()] + run_actions + runner[match.end():]

RUNNER.write_text(runner, encoding="utf-8", newline="\n")

# =============================================================================
# Cinematic Editor integration.
# =============================================================================
editor = EDITOR.read_text(encoding="utf-8")

# The V2 editor intentionally builds on the previous generic JRPG passes.
if "dialogue_preview_viewport" not in editor:
    raise RuntimeError(
        "JRPG live preview not found. Apply add_cinematic_editor_jrpg_preview.py first."
    )

if "TimelineEditorScript" not in editor:
    anchor = 'const BattleActionDefinition = preload("res://scripts/data/battle_action_definition.gd")\n'
    if anchor not in editor:
        raise RuntimeError("Cinematic Editor preload insertion point not found")
    editor = editor.replace(
        anchor,
        anchor
        + 'const TimelineEditorScript = preload("res://addons/sporebound_studio/cinematic_timeline_editor.gd")\n'
        + 'const TimelinePreviewPlayerScene = preload("res://scenes/ui/cinematic_player_3d.tscn")\n',
        1,
    )

editor = editor.replace(
    "var action_list: ItemList\n",
    "var action_list: SporeCinematicTimelineEditor\n",
    1,
)

if "var timeline_preview_player: SporeCinematicPlayer3D" not in editor:
    anchor = "var dialogue_preview_refresh: Button\n"
    if anchor not in editor:
        raise RuntimeError("Timeline preview variable insertion point not found")
    editor = editor.replace(
        anchor,
        anchor
        + "var timeline_preview_player: SporeCinematicPlayer3D\n"
        + "var timeline_preview_ui: Control\n"
        + "var timeline_preview_running: bool = false\n",
        1,
    )

old_widget = '''\taction_list = ItemList.new()\n\taction_list.size_flags_vertical = Control.SIZE_EXPAND_FILL\n\taction_list.item_selected.connect(_on_action_selected)\n\tleft.add_child(action_list)'''
new_widget = '''\taction_list = TimelineEditorScript.new() as SporeCinematicTimelineEditor\n\taction_list.size_flags_vertical = Control.SIZE_EXPAND_FILL\n\taction_list.item_selected.connect(_on_action_selected)\n\taction_list.move_requested.connect(_on_timeline_move_requested)\n\taction_list.duplicate_requested.connect(_on_timeline_duplicate_requested)\n\taction_list.delete_requested.connect(_on_timeline_delete_requested)\n\taction_list.play_from_requested.connect(_on_timeline_play_from_requested)\n\taction_list.play_sequence_requested.connect(_on_timeline_play_sequence_requested)\n\tleft.add_child(action_list)'''
if old_widget in editor:
    editor = editor.replace(old_widget, new_widget, 1)
elif "action_list = TimelineEditorScript.new()" not in editor:
    raise RuntimeError("Could not replace Cinematic Editor ItemList")

editor = replace_function(
    editor,
    "_refresh_action_list",
    '''func _refresh_action_list() -> void:
	if action_list == null:
		return
	if current == null:
		action_index = -1
		action_list.clear()
		return
	if current.actions.is_empty():
		action_index = -1
		action_list.set_actions(current.actions, -1)
		_validate_current()
		return

	var wanted_index: int = action_index
	if wanted_index < 0 or wanted_index >= current.actions.size():
		wanted_index = 0
	action_index = wanted_index
	action_list.set_actions(current.actions, action_index)
	_on_action_selected(action_index)
	_validate_current()''',
)

editor = replace_function(
    editor,
    "_add_action",
    '''func _add_action() -> void:
	if current == null:
		return
	var action: Resource = BattleActionDefinition.new()
	action.id = "action_%02d" % (current.actions.size() + 1)
	action.action_type = "dialogue"
	action.speaker = "Narrateur"
	action.message = "Nouvelle réplique."
	current.actions.append(action)
	action_index = current.actions.size() - 1
	dirty = true
	_refresh_action_list()''',
)

editor = replace_function(
    editor,
    "_duplicate_action",
    '''func _duplicate_action() -> void:
	if current == null or action_index < 0 or action_index >= current.actions.size():
		return
	var source: Resource = current.actions[action_index] as Resource
	if source == null:
		return
	var copy: Resource = source.duplicate(true) as Resource
	copy.set("id", _unique_action_id(String(source.get("id")) + "_copy"))
	current.actions.insert(action_index + 1, copy)
	action_index += 1
	dirty = true
	_refresh_action_list()''',
)

editor = replace_function(
    editor,
    "_move_action",
    '''func _move_action(direction: int) -> void:
	if current == null or action_index < 0:
		return
	var target: int = action_index + direction
	if target < 0 or target >= current.actions.size():
		return
	var action: Resource = current.actions[action_index] as Resource
	current.actions.remove_at(action_index)
	current.actions.insert(target, action)
	action_index = target
	dirty = true
	_refresh_action_list()''',
)

editor = replace_function(
    editor,
    "_remove_action",
    '''func _remove_action() -> void:
	if current == null or action_index < 0 or action_index >= current.actions.size():
		return
	current.actions.remove_at(action_index)
	if current.actions.is_empty():
		action_index = -1
	else:
		action_index = mini(action_index, current.actions.size() - 1)
	dirty = true
	_refresh_action_list()''',
)

# Keep visual selection synchronized when form selection changes.
select_pattern = re.compile(
    r"(?ms)^func _on_action_selected\(index: int\) -> void:\n.*?(?=^func |\Z)"
)
match = select_pattern.search(editor)
if not match:
    raise RuntimeError("_on_action_selected() not found")
select_func = match.group(0)
if "action_list.select(index)" not in select_func:
    anchor = "\taction_index = index\n"
    if anchor not in select_func:
        raise RuntimeError("Action selection anchor not found")
    select_func = select_func.replace(
        anchor,
        anchor + "\tif action_list != null:\n\t\taction_list.select(index)\n",
        1,
    )
    editor = editor[:match.start()] + select_func + editor[match.end():]

handlers = '''func _unique_action_id(base_id: String) -> String:
	if current == null:
		return base_id
	var used: Dictionary = {}
	for action_var: Variant in current.actions:
		var action: Resource = action_var as Resource
		if action != null:
			used[String(action.get("id"))] = true
	var candidate: String = base_id
	var suffix: int = 2
	while used.has(candidate):
		candidate = "%s_%d" % [base_id, suffix]
		suffix += 1
	return candidate


func _on_timeline_move_requested(from_index: int, to_index: int) -> void:
	if current == null:
		return
	if from_index < 0 or from_index >= current.actions.size():
		return
	if to_index < 0 or to_index >= current.actions.size():
		return
	if from_index == to_index:
		return

	var action: Resource = current.actions[from_index] as Resource
	current.actions.remove_at(from_index)
	var destination: int = to_index
	if from_index < to_index:
		destination -= 1
	destination = clampi(destination, 0, current.actions.size())
	current.actions.insert(destination, action)
	action_index = destination
	dirty = true
	_refresh_action_list()


func _on_timeline_duplicate_requested(index: int) -> void:
	action_index = index
	_duplicate_action()


func _on_timeline_delete_requested(index: int) -> void:
	action_index = index
	_remove_action()


func _on_timeline_play_sequence_requested() -> void:
	_play_timeline_preview_from(0)


func _on_timeline_play_from_requested(index: int) -> void:
	_play_timeline_preview_from(index)


func _ensure_timeline_preview_player() -> void:
	if timeline_preview_player != null and is_instance_valid(timeline_preview_player):
		return
	if dialogue_preview_viewport == null:
		return

	timeline_preview_ui = Control.new()
	timeline_preview_ui.name = "TimelinePreviewUI"
	timeline_preview_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	timeline_preview_ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dialogue_preview_viewport.add_child(timeline_preview_ui)

	var instance: Node = TimelinePreviewPlayerScene.instantiate()
	if instance is SporeCinematicPlayer3D:
		timeline_preview_player = instance as SporeCinematicPlayer3D
		dialogue_preview_viewport.add_child(timeline_preview_player)
		timeline_preview_player.configure(self, timeline_preview_ui)
		timeline_preview_player.action_started.connect(_on_timeline_preview_action_started)
		timeline_preview_player.playback_finished.connect(_on_timeline_preview_finished)


func _play_timeline_preview_from(start_index: int) -> void:
	if timeline_preview_running or current == null:
		return
	if current.actions.is_empty():
		return

	# Commit the form currently being edited so the preview uses exactly what
	# the Resource will contain.
	if action_index >= 0 and action_index < current.actions.size():
		_apply_action()
	_save_current()
	_ensure_timeline_preview_player()
	if timeline_preview_player == null:
		return

	timeline_preview_running = true
	if dialogue_preview != null and is_instance_valid(dialogue_preview):
		dialogue_preview.visible = false
	if dialogue_preview_status != null:
		dialogue_preview_status.text = "Lecture de la timeline…"

	await timeline_preview_player.play_from(
		String(current.get("id")),
		clampi(start_index, 0, current.actions.size() - 1)
	)
	_on_timeline_preview_finished()


func _on_timeline_preview_action_started(action_id: String) -> void:
	if action_list != null:
		action_list.set_playing_action(action_id)
	if dialogue_preview_status != null:
		dialogue_preview_status.text = "Lecture • %s" % action_id


func _on_timeline_preview_finished() -> void:
	if not timeline_preview_running:
		return
	timeline_preview_running = false
	if action_list != null:
		action_list.clear_playing_action()
	if dialogue_preview != null and is_instance_valid(dialogue_preview):
		dialogue_preview.visible = true
	call_deferred("_refresh_dialogue_preview", false)


func cinematic_3d_focus_cell(cell: Vector2i, zoom: float, _duration: float) -> void:
	if dialogue_preview_status != null:
		dialogue_preview_status.text = "CAMERA • cellule %s • zoom %.2f" % [cell, zoom]


func cinematic_3d_focus_unit(unit_id: String, zoom: float, _duration: float) -> void:
	if dialogue_preview_status != null:
		dialogue_preview_status.text = "CAMERA • %s • zoom %.2f" % [unit_id, zoom]


func cinematic_3d_zoom(zoom: float, _duration: float) -> void:
	if dialogue_preview_status != null:
		dialogue_preview_status.text = "CAMERA • zoom %.2f" % zoom


func cinematic_3d_reset_camera(_duration: float) -> void:
	if dialogue_preview_status != null:
		dialogue_preview_status.text = "CAMERA • reset"


func cinematic_3d_release_camera_override() -> void:
	pass


func cinematic_3d_camera_shake(strength: float) -> void:
	if dialogue_preview_status != null:
		dialogue_preview_status.text = "CAMERA • shake %.1f" % strength


func cinematic_3d_execute_action(action: Resource) -> void:
	if dialogue_preview_status == null or action == null:
		return
	dialogue_preview_status.text = "ACTION • %s" % String(action.get("action_type"))
'''

editor = insert_before(
    editor,
    "_on_action_selected",
    handlers,
    "func _on_timeline_move_requested(",
)

EDITOR.write_text(editor, encoding="utf-8", newline="\n")

print("[OK] Cinematic Editor V2 visual timeline installed.")
print()
print("Added:")
print("  - reusable cinematic timeline editor component")
print("  - color-coded action cards")
print("  - drag & drop reordering")
print("  - duplicate / delete / play-from-here per card")
print("  - PLAY ALL timeline preview")
print("  - active card highlighting during playback")
print("  - editor playback uses SporeCinematicPlayer3D")
print("  - public play_from()/play_actions() in the generic runner")
print()
print("New files:")
print("  addons/sporebound_studio/cinematic_timeline_card.gd")
print("  addons/sporebound_studio/cinematic_timeline_editor.gd")
print()
print("Backups:")
print("  cinematic_editor.gd.timeline_v2_backup")
print("  spore_cinematic_player_3d.gd.timeline_v2_backup")
