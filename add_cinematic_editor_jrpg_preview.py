#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
EDITOR = ROOT / "addons/sporebound_studio/cinematic_editor.gd"
DIALOGUE = ROOT / "scripts/presentation/spore_cinematic_dialogue_3d.gd"
DIALOGUE_SCENE = ROOT / "scenes/ui/cinematic_dialogue_3d.tscn"
PROFILE_CATALOG = ROOT / "scripts/catalogs/dialogue_speaker_catalog.gd"

required = [EDITOR, DIALOGUE, DIALOGUE_SCENE, PROFILE_CATALOG]
for path in required:
    if not path.exists():
        print(f"[ERROR] Missing file: {path}")
        print("Apply refactor_cinematics_3d_jrpg.py and add_dialogue_speaker_profiles.py first.")
        sys.exit(1)


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".jrpg_preview_backup")
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


backup(EDITOR)
backup(DIALOGUE)

# =============================================================================
# Same dialogue component in game and editor preview.
# =============================================================================
dialogue = DIALOGUE.read_text(encoding="utf-8")

if not dialogue.startswith("@tool\n"):
    dialogue = "@tool\n" + dialogue

if "var _editor_preview_audio_enabled: bool" not in dialogue:
    anchors = [
        "var _line_blip_volume_db: float = -16.0\n",
        "var _base_panel_style: StyleBoxFlat = null\n",
    ]
    anchor = next((item for item in anchors if item in dialogue), None)
    if anchor is None:
        raise RuntimeError("Dialogue preview state insertion point not found")
    dialogue = dialogue.replace(
        anchor,
        anchor + "var _editor_preview_audio_enabled: bool = true\n",
        1,
    )

preview_method = '''func editor_preview_line(
\tspeaker: String,
\ttext_value: String,
\tportrait: Texture2D,
\tportrait_side: String,
\tchars_per_second: float,
\tvoice_pitch: float,
\tblip_every: int,
\taccent: String,
\tanimate_typewriter: bool,
\tenable_audio: bool
) -> void:
\tvisible = true
\tdimmer.visible = true
\tletterbox_top.visible = true
\tletterbox_bottom.visible = true
\tdialogue_panel.visible = true
\tfade_rect.color.a = 0.0
\tdialogue_panel.modulate = Color.WHITE
\tdialogue_panel.scale = Vector2.ONE

\t_editor_preview_audio_enabled = enable_audio
\t_apply_accent(accent)
\t_set_portrait(portrait, portrait_side)

\tspeaker_label.text = speaker if not speaker.is_empty() else "Narrateur"
\t_full_text = text_value
\t_char_index = 0
\t_char_accumulator = 0.0
\t_punctuation_delay = 0.0
\t_chars_per_second = chars_per_second if chars_per_second > 0.0 else default_chars_per_second
\t_voice_pitch = clampf(voice_pitch, 0.55, 1.75)
\t_blip_every = maxi(1, blip_every)
\t_waiting = false
\thint_label.text = "APERÇU ÉDITEUR • même scène que le runtime"

\tif animate_typewriter:
\t\tmessage_label.text = ""
\t\t_typing = true
\t\tcontinue_button.text = "APERÇU..."
\t\tadvance_pulse.visible = false
\telse:
\t\tmessage_label.text = _full_text
\t\t_char_index = _full_text.length()
\t\t_typing = false
\t\tcontinue_button.text = "CONTINUER  ▸"
\t\tadvance_pulse.visible = true


func editor_clear_preview() -> void:
\t_editor_preview_audio_enabled = false
\thide_all()'''

dialogue = insert_before(
    dialogue,
    "set_fade_alpha",
    preview_method,
    "func editor_preview_line(",
)

# Runtime dialogues always restore audio; editor preview can mute it.
present_pattern = re.compile(r"(?ms)^func present_line\([^\n]*\n.*?(?=^func |\Z)")
m = present_pattern.search(dialogue)
if not m:
    # Multi-line signature fallback.
    present_pattern = re.compile(r"(?ms)^func present_line\(.*?\) -> void:\n.*?(?=^func |\Z)")
    m = present_pattern.search(dialogue)
if not m:
    raise RuntimeError("Dialogue present_line() not found")
present_func = m.group(0)
if "_editor_preview_audio_enabled = true" not in present_func:
    body_anchor = ") -> void:\n"
    pos = present_func.find(body_anchor)
    if pos < 0:
        raise RuntimeError("Could not patch present_line() preview audio reset")
    pos += len(body_anchor)
    present_func = (
        present_func[:pos]
        + "\t_editor_preview_audio_enabled = true\n"
        + present_func[pos:]
    )
    dialogue = dialogue[:m.start()] + present_func + dialogue[m.end():]

# Do not produce blips when editor preview mute is selected.
blip_pattern = re.compile(r"(?ms)^func _play_blip\(\) -> void:\n.*?(?=^func |\Z)")
m = blip_pattern.search(dialogue)
if not m:
    raise RuntimeError("Dialogue _play_blip() not found")
blip_func = m.group(0)
if "not _editor_preview_audio_enabled" not in blip_func:
    blip_func = blip_func.replace(
        "func _play_blip() -> void:\n",
        "func _play_blip() -> void:\n\tif not _editor_preview_audio_enabled:\n\t\treturn\n",
        1,
    )
    dialogue = dialogue[:m.start()] + blip_func + dialogue[m.end():]

DIALOGUE.write_text(dialogue, encoding="utf-8", newline="\n")

# =============================================================================
# Cinematic editor: embedded 16:9 JRPG preview.
# =============================================================================
editor = EDITOR.read_text(encoding="utf-8")

if "DialogueSpeakerCatalog" not in editor:
    const_anchor = 'const BattleActionDefinition = preload("res://scripts/data/battle_action_definition.gd")\n'
    if const_anchor not in editor:
        raise RuntimeError("Cinematic Editor preload insertion point not found")
    editor = editor.replace(
        const_anchor,
        const_anchor
        + 'const DialogueSpeakerCatalog = preload("res://scripts/catalogs/dialogue_speaker_catalog.gd")\n'
        + 'const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")\n'
        + 'const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")\n'
        + 'const DialoguePreviewScene = preload("res://scenes/ui/cinematic_dialogue_3d.tscn")\n',
        1,
    )

if "var dialogue_preview_container: SubViewportContainer" not in editor:
    anchor = "var validation: Label\n"
    if anchor not in editor:
        raise RuntimeError("Cinematic Editor preview variable insertion point not found")
    variables = '''var dialogue_preview_container: SubViewportContainer
var dialogue_preview_viewport: SubViewport
var dialogue_preview: SporeCinematicDialogue3D
var dialogue_preview_status: Label
var dialogue_preview_sound: CheckBox
var dialogue_preview_play: Button
var dialogue_preview_refresh: Button
'''
    editor = editor.replace(anchor, anchor + variables, 1)

# Build preview high in the right pane so it stays near the edited dialogue.
build_pattern = re.compile(r"(?ms)^func _build_ui\(\) -> void:\n.*?(?=^func |\Z)")
m = build_pattern.search(editor)
if not m:
    raise RuntimeError("Cinematic Editor _build_ui() not found")
build_func = m.group(0)
if "_build_dialogue_preview(right)" not in build_func:
    anchor = '''\tvar action_title := Label.new()\n\taction_title.text = "ACTION SÉLECTIONNÉE"\n\taction_title.add_theme_font_size_override("font_size", 18)\n\tright.add_child(action_title)\n'''
    if anchor not in build_func:
        raise RuntimeError("Cinematic Editor action title insertion point not found")
    build_func = build_func.replace(
        anchor,
        anchor + "\t_build_dialogue_preview(right)\n",
        1,
    )

    # All dialogue controls exist by the time the Apply button is added.
    connect_anchor = '''\tvar apply := Button.new()\n\tapply.text = "Appliquer l'action"\n\tapply.pressed.connect(_apply_action)\n\tright.add_child(apply)\n'''
    if connect_anchor not in build_func:
        raise RuntimeError("Cinematic Editor apply-button insertion point not found")
    build_func = build_func.replace(
        connect_anchor,
        connect_anchor + "\t_connect_dialogue_preview_signals()\n",
        1,
    )
    editor = editor[:m.start()] + build_func + editor[m.end():]

preview_helpers = '''func _build_dialogue_preview(parent: VBoxContainer) -> void:
\tvar title: Label = Label.new()
\ttitle.text = "APERÇU JRPG — 16:9"
\ttitle.add_theme_font_size_override("font_size", 16)
\ttitle.add_theme_color_override("font_color", Color(0.78, 0.90, 1.0, 1.0))
\tparent.add_child(title)

\tvar frame: PanelContainer = PanelContainer.new()
\tframe.custom_minimum_size = Vector2(650.0, 366.0)
\tvar frame_style: StyleBoxFlat = StyleBoxFlat.new()
\tframe_style.bg_color = Color(0.025, 0.035, 0.055, 1.0)
\tframe_style.border_color = Color(0.24, 0.36, 0.52, 1.0)
\tframe_style.border_width_left = 1
\tframe_style.border_width_top = 1
\tframe_style.border_width_right = 1
\tframe_style.border_width_bottom = 1
\tframe_style.corner_radius_top_left = 10
\tframe_style.corner_radius_top_right = 10
\tframe_style.corner_radius_bottom_left = 10
\tframe_style.corner_radius_bottom_right = 10
\tframe.add_theme_stylebox_override("panel", frame_style)
\tparent.add_child(frame)

\tdialogue_preview_container = SubViewportContainer.new()
\tdialogue_preview_container.custom_minimum_size = Vector2(640.0, 360.0)
\tdialogue_preview_container.stretch = true
\tframe.add_child(dialogue_preview_container)

\tdialogue_preview_viewport = SubViewport.new()
\tdialogue_preview_viewport.name = "DialoguePreviewViewport"
\tdialogue_preview_viewport.size = Vector2i(1280, 720)
\tdialogue_preview_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
\tdialogue_preview_viewport.gui_disable_input = true
\tdialogue_preview_container.add_child(dialogue_preview_viewport)

\tvar background: ColorRect = ColorRect.new()
\tbackground.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
\tbackground.color = Color(0.075, 0.12, 0.10, 1.0)
\tbackground.mouse_filter = Control.MOUSE_FILTER_IGNORE
\tdialogue_preview_viewport.add_child(background)

\tvar horizon: ColorRect = ColorRect.new()
\thorizon.anchor_left = 0.0
\thorizon.anchor_top = 0.0
\thorizon.anchor_right = 1.0
\thorizon.anchor_bottom = 0.52
\thorizon.color = Color(0.10, 0.16, 0.21, 1.0)
\thorizon.mouse_filter = Control.MOUSE_FILTER_IGNORE
\tdialogue_preview_viewport.add_child(horizon)

\tvar instance: Node = DialoguePreviewScene.instantiate()
\tif instance is SporeCinematicDialogue3D:
\t\tdialogue_preview = instance as SporeCinematicDialogue3D
\t\tdialogue_preview_viewport.add_child(dialogue_preview)

\tvar toolbar: HBoxContainer = HBoxContainer.new()
\ttoolbar.add_theme_constant_override("separation", 8)
\tparent.add_child(toolbar)

\tdialogue_preview_play = Button.new()
\tdialogue_preview_play.text = "▶ TEST TYPEWRITER"
\tdialogue_preview_play.pressed.connect(_play_dialogue_preview)
\ttoolbar.add_child(dialogue_preview_play)

\tdialogue_preview_refresh = Button.new()
\tdialogue_preview_refresh.text = "⟳ RAFRAÎCHIR"
\tdialogue_preview_refresh.pressed.connect(_refresh_dialogue_preview.bind(false))
\ttoolbar.add_child(dialogue_preview_refresh)

\tdialogue_preview_sound = CheckBox.new()
\tdialogue_preview_sound.text = "Son JRPG"
\tdialogue_preview_sound.button_pressed = true
\tdialogue_preview_sound.toggled.connect(_on_dialogue_preview_changed)
\ttoolbar.add_child(dialogue_preview_sound)

\tdialogue_preview_status = Label.new()
\tdialogue_preview_status.text = "Sélectionne une action dialogue."
\tdialogue_preview_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
\tdialogue_preview_status.add_theme_font_size_override("font_size", 11)
\tdialogue_preview_status.add_theme_color_override("font_color", Color(0.68, 0.76, 0.84, 1.0))
\tparent.add_child(dialogue_preview_status)


func _connect_dialogue_preview_signals() -> void:
\taction_message.text_changed.connect(_on_dialogue_preview_changed)
\taction_speaker.text_changed.connect(_on_dialogue_preview_changed)
\taction_portrait.text_changed.connect(_on_dialogue_preview_changed)
\taction_unit.item_selected.connect(_on_dialogue_preview_changed)
\taction_side.item_selected.connect(_on_dialogue_preview_changed)
\taction_dialogue_profile.item_selected.connect(_on_dialogue_preview_changed)
\taction_override_dialogue_profile.toggled.connect(_on_dialogue_preview_changed)
\taction_text_speed.value_changed.connect(_on_dialogue_preview_changed)
\taction_voice_pitch.value_changed.connect(_on_dialogue_preview_changed)
\taction_blip_every.value_changed.connect(_on_dialogue_preview_changed)


func _on_dialogue_preview_changed(_value: Variant = null) -> void:
\tcall_deferred("_refresh_dialogue_preview", false)


func _play_dialogue_preview() -> void:
\t_refresh_dialogue_preview(true)


func _refresh_dialogue_preview(animate_typewriter: bool = false) -> void:
\tif dialogue_preview == null or not is_instance_valid(dialogue_preview):
\t\treturn
\tif current == null or action_index < 0 or action_index >= current.actions.size():
\t\tdialogue_preview.editor_clear_preview()
\t\tif dialogue_preview_status != null:
\t\t\tdialogue_preview_status.text = "Aucune action sélectionnée."
\t\treturn

\tvar selected_action: Resource = current.actions[action_index] as Resource
\tif selected_action == null or String(selected_action.get("action_type")) != "dialogue":
\t\tdialogue_preview.editor_clear_preview()
\t\tif dialogue_preview_status != null:
\t\t\tdialogue_preview_status.text = "L'aperçu JRPG s'affiche pour les actions de type dialogue."
\t\treturn

\tvar unit_id: String = ""
\tif action_unit.selected >= 0:
\t\tunit_id = String(action_unit.get_item_metadata(action_unit.selected))

\tvar speaker: String = action_speaker.text.strip_edges()
\tif speaker.is_empty() and not unit_id.is_empty():
\t\tvar unit_definition: Resource = UnitCatalog.definition(unit_id)
\t\tif unit_definition != null:
\t\t\tspeaker = String(unit_definition.get("display_name"))
\tif speaker.is_empty():
\t\tspeaker = "Narrateur"

\tvar profile_id: String = ""
\tif action_dialogue_profile.selected >= 0:
\t\tprofile_id = String(
\t\t\taction_dialogue_profile.get_item_metadata(
\t\t\t\taction_dialogue_profile.selected
\t\t\t)
\t\t)
\tvar profile: Resource = DialogueSpeakerCatalog.resolve(
\t\tprofile_id,
\t\tunit_id,
\t\tspeaker
\t)
\tvar override_profile: bool = action_override_dialogue_profile.button_pressed

\tvar portrait_side: String = (
\t\taction_side.get_item_text(action_side.selected)
\t\tif action_side.selected >= 0
\t\telse "left"
\t)
\tvar text_speed: float = float(action_text_speed.value)
\tvar voice_pitch: float = float(action_voice_pitch.value)
\tvar blip_every: int = int(action_blip_every.value)
\tvar accent: String = "neutral"
\tvar accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
\tvar name_color: Color = Color(0.76, 0.92, 1.0, 1.0)
\tvar blip_volume: float = -16.0

\tif profile != null and not override_profile:
\t\tportrait_side = String(profile.get("portrait_side"))
\t\ttext_speed = float(profile.get("text_speed"))
\t\tvoice_pitch = float(profile.get("voice_pitch"))
\t\tblip_every = int(profile.get("blip_every"))
\t\tblip_volume = float(profile.get("blip_volume_db"))
\t\taccent_color = Color(profile.get("accent_color"))
\t\tname_color = Color(profile.get("name_color"))
\t\taccent = "profile"
\telif speaker.to_lower() in ["narrateur", "narrator"]:
\t\taccent = "narrator"

\tvar portrait: Texture2D = _preview_resolve_portrait(
\t\taction_portrait.text.strip_edges(),
\t\tunit_id,
\t\tspeaker,
\t\tprofile
\t)

\tdialogue_preview.set_line_profile(
\t\taccent_color,
\t\tname_color,
\t\tblip_volume
\t)
\tdialogue_preview.editor_preview_line(
\t\tspeaker,
\t\taction_message.text if not action_message.text.is_empty() else "Nouvelle réplique...",
\t\tportrait,
\t\tportrait_side,
\t\ttext_speed,
\t\tvoice_pitch,
\t\tblip_every,
\t\taccent,
\t\tanimate_typewriter,
\t\tdialogue_preview_sound.button_pressed
\t)

\tif dialogue_preview_status != null:
\t\tvar profile_name: String = "Réglages de la réplique"
\t\tif profile != null and not override_profile:
\t\t\tprofile_name = String(profile.get("display_name"))
\t\tdialogue_preview_status.text = (
\t\t\t"Profil : %s • %.0f car/s • voix %.2fx • blip / %d • portrait %s"
\t\t\t% [
\t\t\t\tprofile_name,
\t\t\t\ttext_speed,
\t\t\t\tvoice_pitch,
\t\t\t\tblip_every,
\t\t\t\tportrait_side
\t\t\t]
\t\t)


func _preview_resolve_portrait(
\texplicit_path: String,
\tunit_id: String,
\tspeaker: String,
\tprofile: Resource
) -> Texture2D:
\tif not explicit_path.is_empty() and ResourceLoader.exists(explicit_path):
\t\treturn load(explicit_path) as Texture2D

\tif profile != null:
\t\tvar profile_path: String = String(profile.get("portrait_path"))
\t\tif not profile_path.is_empty() and ResourceLoader.exists(profile_path):
\t\t\treturn load(profile_path) as Texture2D

\tif not unit_id.is_empty():
\t\tvar unit: Resource = UnitCatalog.definition(unit_id)
\t\tif unit != null:
\t\t\tvar visual_id: String = String(unit.get("visual_id"))
\t\t\tif visual_id.is_empty():
\t\t\t\tvisual_id = unit_id
\t\t\tvar visual: Resource = VisualCatalog.definition(visual_id)
\t\t\tif visual != null:
\t\t\t\tvar visual_path: String = String(visual.get("portrait_path"))
\t\t\t\tif not visual_path.is_empty() and ResourceLoader.exists(visual_path):
\t\t\t\t\treturn load(visual_path) as Texture2D

\tfor candidate_id: String in UnitCatalog.all_unit_ids():
\t\tvar candidate: Resource = UnitCatalog.definition(candidate_id)
\t\tif candidate == null:
\t\t\tcontinue
\t\tif String(candidate.get("display_name")).to_lower() != speaker.to_lower():
\t\t\tcontinue
\t\tvar candidate_visual_id: String = String(candidate.get("visual_id"))
\t\tif candidate_visual_id.is_empty():
\t\t\tcandidate_visual_id = candidate_id
\t\tvar candidate_visual: Resource = VisualCatalog.definition(candidate_visual_id)
\t\tif candidate_visual == null:
\t\t\tcontinue
\t\tvar candidate_path: String = String(candidate_visual.get("portrait_path"))
\t\tif not candidate_path.is_empty() and ResourceLoader.exists(candidate_path):
\t\t\treturn load(candidate_path) as Texture2D

\treturn null'''

editor = insert_before(
    editor,
    "_resource_files",
    preview_helpers,
    "func _build_dialogue_preview(",
)

# Selecting an action immediately refreshes the preview after all form fields are loaded.
select_pattern = re.compile(r"(?ms)^func _on_action_selected\(index: int\) -> void:\n.*?(?=^func |\Z)")
m = select_pattern.search(editor)
if not m:
    raise RuntimeError("Cinematic Editor _on_action_selected() not found")
select_func = m.group(0)
if "_refresh_dialogue_preview(false)" not in select_func:
    select_func = select_func.rstrip() + '\n\tcall_deferred("_refresh_dialogue_preview", false)\n'
    editor = editor[:m.start()] + select_func + "\n\n" + editor[m.end():]

# Applying a line also refreshes using the persisted resource.
apply_pattern = re.compile(r"(?ms)^func _apply_action\(\) -> void:\n.*?(?=^func |\Z)")
m = apply_pattern.search(editor)
if not m:
    raise RuntimeError("Cinematic Editor _apply_action() not found")
apply_func = m.group(0)
if 'call_deferred("_refresh_dialogue_preview", false)' not in apply_func:
    apply_func = apply_func.rstrip() + '\n\tcall_deferred("_refresh_dialogue_preview", false)\n'
    editor = editor[:m.start()] + apply_func + "\n\n" + editor[m.end():]

EDITOR.write_text(editor, encoding="utf-8", newline="\n")

print("[OK] Cinematic Editor JRPG live preview installed.")
print()
print("Editor preview:")
print("  - uses the exact runtime cinematic_dialogue_3d.tscn")
print("  - 16:9 embedded preview")
print("  - automatic portrait resolution")
print("  - automatic speaker profile resolution")
print("  - live refresh while editing text / speaker / profile / voice")
print("  - static preview or real typewriter test")
print("  - optional JRPG blip sound")
print()
print("Backups:")
print("  addons/sporebound_studio/cinematic_editor.gd.jrpg_preview_backup")
print("  scripts/presentation/spore_cinematic_dialogue_3d.gd.jrpg_preview_backup")
