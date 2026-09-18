@tool
class_name SporeCinematicEditor
extends VBoxContainer

const CinematicDefinition = preload("res://scripts/data/cinematic_definition.gd")
const BattleActionDefinition = preload("res://scripts/data/battle_action_definition.gd")
const TimelineEditorScript = preload("res://addons/sporebound_studio/cinematic_timeline_editor.gd")
const TimelinePreviewPlayerScene = preload("res://scenes/ui/cinematic_player_3d.tscn")
const DialogueSpeakerCatalog = preload("res://scripts/catalogs/dialogue_speaker_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")
const DialoguePreviewScene = preload("res://scenes/ui/cinematic_dialogue_3d.tscn")

const CINEMATIC_DIR := "res://data/cinematics/"
const MISSION_DIR := "res://data/missions/"
const UNIT_DIR := "res://data/units/"
const DIALOGUE_PROFILE_DIR := "res://data/dialogue_speakers/"
const ACTION_TYPES := [
	"dialogue", "wait", "camera_focus_cell", "camera_focus_unit", "camera_zoom",
	"camera_reset", "camera_shake", "play_music", "stop_music", "play_sfx",
	"fade_out", "fade_in", "play_cinematic", "message", "set_objective_text", "set_phase"
]

var cinematic_select: OptionButton
var current: Resource
var current_path := ""
var dirty := false
var name_edit: LineEdit
var description_edit: TextEdit
var action_list: SporeCinematicTimelineEditor
var action_index := -1
var action_type: OptionButton
var action_delay: SpinBox
var action_message: TextEdit
var action_speaker: LineEdit
var action_unit: OptionButton
var action_cell_x: SpinBox
var action_cell_y: SpinBox
var action_value: SpinBox
var action_nested: OptionButton
var action_portrait: LineEdit
var action_side: OptionButton
var action_wait_input: CheckBox
var action_auto: SpinBox
var action_dialogue_profile: OptionButton
var action_override_dialogue_profile: CheckBox
var action_text_speed: SpinBox
var action_voice_pitch: SpinBox
var action_blip_every: SpinBox
var action_zoom: SpinBox
var action_duration: SpinBox
var action_audio: LineEdit
var action_volume: SpinBox
var mission_select: OptionButton
var mission_intro: OptionButton
var mission_victory: OptionButton
var mission_defeat: OptionButton
var validation: Label
var dialogue_preview_container: SubViewportContainer
var dialogue_preview_viewport: SubViewport
var dialogue_preview: SporeCinematicDialogue3D
var dialogue_preview_status: Label
var dialogue_preview_sound: CheckBox
var dialogue_preview_play: Button
var dialogue_preview_refresh: Button
var timeline_preview_player: SporeCinematicPlayer3D
var timeline_preview_ui: Control
var timeline_preview_running: bool = false


func _ready() -> void:
	name = "Cinematics"
	_build_ui()
	refresh()


func has_unsaved_data() -> bool:
	return dirty


func save_external_data() -> void:
	_save_current()


func refresh() -> void:
	if dirty:
		_save_current()
	_refresh_selector()
	_refresh_mission_binding()


func _build_ui() -> void:
	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_child(split)

	var left := VBoxContainer.new()
	left.custom_minimum_size.x = 350
	split.add_child(left)
	var title := Label.new()
	title.text = "CINEMATIC TIMELINE"
	title.add_theme_font_size_override("font_size", 18)
	left.add_child(title)
	cinematic_select = OptionButton.new()
	cinematic_select.item_selected.connect(_on_selected)
	left.add_child(cinematic_select)
	var bar := HBoxContainer.new()
	left.add_child(bar)
	for spec in [["+ Nouvelle", _new_cinematic], ["Dupliquer", _duplicate_cinematic], ["Sauver", _save_current]]:
		var button := Button.new()
		button.text = spec[0]
		button.pressed.connect(spec[1])
		bar.add_child(button)
	name_edit = _line(left, "Nom affiché")
	description_edit = _text(left, "Description", 65)
	var actions_title := Label.new()
	actions_title.text = "Timeline"
	left.add_child(actions_title)
	var action_bar := HBoxContainer.new()
	left.add_child(action_bar)
	for spec in [["+ Action", _add_action], ["Dupliquer", _duplicate_action], ["↑", _move_action.bind(-1)], ["↓", _move_action.bind(1)], ["Suppr.", _remove_action]]:
		var button := Button.new()
		button.text = spec[0]
		button.pressed.connect(spec[1])
		action_bar.add_child(button)
	action_list = TimelineEditorScript.new() as SporeCinematicTimelineEditor
	action_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	action_list.item_selected.connect(_on_action_selected)
	action_list.move_requested.connect(_on_timeline_move_requested)
	action_list.duplicate_requested.connect(_on_timeline_duplicate_requested)
	action_list.delete_requested.connect(_on_timeline_delete_requested)
	action_list.play_from_requested.connect(_on_timeline_play_from_requested)
	action_list.play_sequence_requested.connect(_on_timeline_play_sequence_requested)
	left.add_child(action_list)

	var right_scroll := ScrollContainer.new()
	right_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.add_child(right_scroll)
	var right := VBoxContainer.new()
	right.custom_minimum_size.x = 690
	right_scroll.add_child(right)
	var action_title := Label.new()
	action_title.text = "ACTION SÉLECTIONNÉE"
	action_title.add_theme_font_size_override("font_size", 18)
	right.add_child(action_title)
	_build_dialogue_preview(right)
	action_type = OptionButton.new()
	for value in ACTION_TYPES:
		action_type.add_item(value)
	right.add_child(action_type)
	action_delay = _spin(right, "Délai avant action (s)", 0, 30, 0.1)
	action_message = _text(right, "Dialogue / message / objectif / phase", 90)
	action_speaker = _line(right, "Locuteur")
	_add_label(right, "Unité cible / focus")
	action_unit = OptionButton.new()
	right.add_child(action_unit)
	var cell_row := HBoxContainer.new()
	right.add_child(cell_row)
	action_cell_x = _compact_spin(cell_row, "Cell X", -1, 29)
	action_cell_y = _compact_spin(cell_row, "Y", -1, 29)
	action_value = _spin(right, "Valeur / intensité", -99, 99, 1)
	_add_label(right, "Cinématique appelée")
	action_nested = OptionButton.new()
	right.add_child(action_nested)
	action_portrait = _line(right, "Portrait res://... (optionnel)")
	action_side = OptionButton.new()
	action_side.add_item("left")
	action_side.add_item("right")
	right.add_child(action_side)
	action_wait_input = CheckBox.new()
	action_wait_input.text = "Dialogue : attendre Entrée/Espace/clic"
	right.add_child(action_wait_input)
	action_auto = _spin(right, "Auto-avance (s, si attente décochée)", 0, 30, 0.1)
	_add_label(right, "Profil dialogue (auto = unité/locuteur)")
	action_dialogue_profile = OptionButton.new()
	right.add_child(action_dialogue_profile)
	action_override_dialogue_profile = CheckBox.new()
	action_override_dialogue_profile.text = "Surcharger voix/couleur/côté pour cette réplique"
	right.add_child(action_override_dialogue_profile)
	action_text_speed = _spin(right, "Dialogue : vitesse écriture (car./s)", 10, 120, 1)
	action_voice_pitch = _spin(right, "Dialogue : hauteur voix", 0.55, 1.75, 0.05)
	action_blip_every = _spin(right, "Dialogue : blip tous les N caractères", 1, 8, 1)
	action_zoom = _spin(right, "Zoom caméra", 0.25, 3.0, 0.05)
	action_duration = _spin(right, "Durée caméra/fondu (s)", 0, 5, 0.05)
	action_audio = _line(right, "Audio res://... (.ogg/.wav/.mp3)")
	action_volume = _spin(right, "Volume dB", -40, 6, 0.5)
	var apply := Button.new()
	apply.text = "Appliquer l'action"
	apply.pressed.connect(_apply_action)
	right.add_child(apply)
	_connect_dialogue_preview_signals()

	var sep := HSeparator.new()
	right.add_child(sep)
	var bind_title := Label.new()
	bind_title.text = "ASSIGNATION À UNE MISSION"
	bind_title.add_theme_font_size_override("font_size", 16)
	right.add_child(bind_title)
	mission_select = OptionButton.new()
	mission_select.item_selected.connect(_on_mission_selected)
	right.add_child(mission_select)
	mission_intro = _cinematic_option(right, "Intro")
	mission_victory = _cinematic_option(right, "Victoire")
	mission_defeat = _cinematic_option(right, "Défaite")
	var bind := Button.new()
	bind.text = "Appliquer Intro / Victoire / Défaite"
	bind.pressed.connect(_apply_mission_binding)
	right.add_child(bind)
	validation = Label.new()
	validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(validation)
	var help := Label.new()
	help.text = "Une timeline est réutilisable : une mission peut l'utiliser en Intro/Victoire/Défaite, et un trigger Mission Logic peut l'appeler avec play_cinematic. Les chemins portrait/audio sont optionnels. Si le portrait est vide, le runtime tente le portrait du skin associé à unit_id ou au nom du locuteur."
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(help)


func _build_dialogue_preview(parent: VBoxContainer) -> void:
	var title: Label = Label.new()
	title.text = "APERÇU JRPG — 16:9"
	title.add_theme_font_size_override("font_size", 16)
	title.add_theme_color_override("font_color", Color(0.78, 0.90, 1.0, 1.0))
	parent.add_child(title)

	var frame: PanelContainer = PanelContainer.new()
	frame.custom_minimum_size = Vector2(650.0, 366.0)
	var frame_style: StyleBoxFlat = StyleBoxFlat.new()
	frame_style.bg_color = Color(0.025, 0.035, 0.055, 1.0)
	frame_style.border_color = Color(0.24, 0.36, 0.52, 1.0)
	frame_style.border_width_left = 1
	frame_style.border_width_top = 1
	frame_style.border_width_right = 1
	frame_style.border_width_bottom = 1
	frame_style.corner_radius_top_left = 10
	frame_style.corner_radius_top_right = 10
	frame_style.corner_radius_bottom_left = 10
	frame_style.corner_radius_bottom_right = 10
	frame.add_theme_stylebox_override("panel", frame_style)
	parent.add_child(frame)

	dialogue_preview_container = SubViewportContainer.new()
	dialogue_preview_container.custom_minimum_size = Vector2(640.0, 360.0)
	dialogue_preview_container.stretch = true
	frame.add_child(dialogue_preview_container)

	dialogue_preview_viewport = SubViewport.new()
	dialogue_preview_viewport.name = "DialoguePreviewViewport"
	dialogue_preview_viewport.size = Vector2i(1280, 720)
	dialogue_preview_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	dialogue_preview_viewport.gui_disable_input = true
	dialogue_preview_container.add_child(dialogue_preview_viewport)

	var background: ColorRect = ColorRect.new()
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.color = Color(0.075, 0.12, 0.10, 1.0)
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dialogue_preview_viewport.add_child(background)

	var horizon: ColorRect = ColorRect.new()
	horizon.anchor_left = 0.0
	horizon.anchor_top = 0.0
	horizon.anchor_right = 1.0
	horizon.anchor_bottom = 0.52
	horizon.color = Color(0.10, 0.16, 0.21, 1.0)
	horizon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dialogue_preview_viewport.add_child(horizon)

	var instance: Node = DialoguePreviewScene.instantiate()
	if instance is SporeCinematicDialogue3D:
		dialogue_preview = instance as SporeCinematicDialogue3D
		dialogue_preview_viewport.add_child(dialogue_preview)

	var toolbar: HBoxContainer = HBoxContainer.new()
	toolbar.add_theme_constant_override("separation", 8)
	parent.add_child(toolbar)

	dialogue_preview_play = Button.new()
	dialogue_preview_play.text = "▶ TEST TYPEWRITER"
	dialogue_preview_play.pressed.connect(_play_dialogue_preview)
	toolbar.add_child(dialogue_preview_play)

	dialogue_preview_refresh = Button.new()
	dialogue_preview_refresh.text = "⟳ RAFRAÎCHIR"
	dialogue_preview_refresh.pressed.connect(_refresh_dialogue_preview.bind(false))
	toolbar.add_child(dialogue_preview_refresh)

	dialogue_preview_sound = CheckBox.new()
	dialogue_preview_sound.text = "Son JRPG"
	dialogue_preview_sound.button_pressed = true
	dialogue_preview_sound.toggled.connect(_on_dialogue_preview_changed)
	toolbar.add_child(dialogue_preview_sound)

	dialogue_preview_status = Label.new()
	dialogue_preview_status.text = "Sélectionne une action dialogue."
	dialogue_preview_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	dialogue_preview_status.add_theme_font_size_override("font_size", 11)
	dialogue_preview_status.add_theme_color_override("font_color", Color(0.68, 0.76, 0.84, 1.0))
	parent.add_child(dialogue_preview_status)


func _connect_dialogue_preview_signals() -> void:
	action_message.text_changed.connect(_on_dialogue_preview_changed)
	action_speaker.text_changed.connect(_on_dialogue_preview_changed)
	action_portrait.text_changed.connect(_on_dialogue_preview_changed)
	action_unit.item_selected.connect(_on_dialogue_preview_changed)
	action_side.item_selected.connect(_on_dialogue_preview_changed)
	action_dialogue_profile.item_selected.connect(_on_dialogue_preview_changed)
	action_override_dialogue_profile.toggled.connect(_on_dialogue_preview_changed)
	action_text_speed.value_changed.connect(_on_dialogue_preview_changed)
	action_voice_pitch.value_changed.connect(_on_dialogue_preview_changed)
	action_blip_every.value_changed.connect(_on_dialogue_preview_changed)


func _on_dialogue_preview_changed(_value: Variant = null) -> void:
	call_deferred("_refresh_dialogue_preview", false)


func _play_dialogue_preview() -> void:
	_refresh_dialogue_preview(true)


func _refresh_dialogue_preview(animate_typewriter: bool = false) -> void:
	if dialogue_preview == null or not is_instance_valid(dialogue_preview):
		return
	if current == null or action_index < 0 or action_index >= current.actions.size():
		dialogue_preview.editor_clear_preview()
		if dialogue_preview_status != null:
			dialogue_preview_status.text = "Aucune action sélectionnée."
		return

	var selected_action: Resource = current.actions[action_index] as Resource
	if selected_action == null or String(selected_action.get("action_type")) != "dialogue":
		dialogue_preview.editor_clear_preview()
		if dialogue_preview_status != null:
			dialogue_preview_status.text = "L'aperçu JRPG s'affiche pour les actions de type dialogue."
		return

	var unit_id: String = ""
	if action_unit.selected >= 0:
		unit_id = String(action_unit.get_item_metadata(action_unit.selected))

	var speaker: String = action_speaker.text.strip_edges()
	if speaker.is_empty() and not unit_id.is_empty():
		var unit_definition: Resource = UnitCatalog.definition(unit_id)
		if unit_definition != null:
			speaker = String(unit_definition.get("display_name"))
	if speaker.is_empty():
		speaker = "Narrateur"

	var profile_id: String = ""
	if action_dialogue_profile.selected >= 0:
		profile_id = String(
			action_dialogue_profile.get_item_metadata(
				action_dialogue_profile.selected
			)
		)
	var profile: Resource = DialogueSpeakerCatalog.resolve(
		profile_id,
		unit_id,
		speaker
	)
	var override_profile: bool = action_override_dialogue_profile.button_pressed

	var portrait_side: String = (
		action_side.get_item_text(action_side.selected)
		if action_side.selected >= 0
		else "left"
	)
	var text_speed: float = float(action_text_speed.value)
	var voice_pitch: float = float(action_voice_pitch.value)
	var blip_every: int = int(action_blip_every.value)
	var accent: String = "neutral"
	var accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
	var name_color: Color = Color(0.76, 0.92, 1.0, 1.0)
	var blip_volume: float = -16.0

	if profile != null and not override_profile:
		portrait_side = String(profile.get("portrait_side"))
		text_speed = float(profile.get("text_speed"))
		voice_pitch = float(profile.get("voice_pitch"))
		blip_every = int(profile.get("blip_every"))
		blip_volume = float(profile.get("blip_volume_db"))
		accent_color = Color(profile.get("accent_color"))
		name_color = Color(profile.get("name_color"))
		accent = "profile"
	elif speaker.to_lower() in ["narrateur", "narrator"]:
		accent = "narrator"

	var portrait: Texture2D = _preview_resolve_portrait(
		action_portrait.text.strip_edges(),
		unit_id,
		speaker,
		profile
	)

	dialogue_preview.set_line_profile(
		accent_color,
		name_color,
		blip_volume
	)
	dialogue_preview.editor_preview_line(
		speaker,
		action_message.text if not action_message.text.is_empty() else "Nouvelle réplique...",
		portrait,
		portrait_side,
		text_speed,
		voice_pitch,
		blip_every,
		accent,
		animate_typewriter,
		dialogue_preview_sound.button_pressed
	)

	if dialogue_preview_status != null:
		var profile_name: String = "Réglages de la réplique"
		if profile != null and not override_profile:
			profile_name = String(profile.get("display_name"))
		dialogue_preview_status.text = (
			"Profil : %s • %.0f car/s • voix %.2fx • blip / %d • portrait %s"
			% [
				profile_name,
				text_speed,
				voice_pitch,
				blip_every,
				portrait_side
			]
		)


func _preview_resolve_portrait(
	explicit_path: String,
	unit_id: String,
	speaker: String,
	profile: Resource
) -> Texture2D:
	if not explicit_path.is_empty() and ResourceLoader.exists(explicit_path):
		return load(explicit_path) as Texture2D

	if profile != null:
		var profile_path: String = String(profile.get("portrait_path"))
		if not profile_path.is_empty() and ResourceLoader.exists(profile_path):
			return load(profile_path) as Texture2D

	if not unit_id.is_empty():
		var unit: Resource = UnitCatalog.definition(unit_id)
		if unit != null:
			var visual_id: String = String(unit.get("visual_id"))
			if visual_id.is_empty():
				visual_id = unit_id
			var visual: Resource = VisualCatalog.definition(visual_id)
			if visual != null:
				var visual_path: String = String(visual.get("portrait_path"))
				if not visual_path.is_empty() and ResourceLoader.exists(visual_path):
					return load(visual_path) as Texture2D

	for candidate_id: String in UnitCatalog.all_unit_ids():
		var candidate: Resource = UnitCatalog.definition(candidate_id)
		if candidate == null:
			continue
		if String(candidate.get("display_name")).to_lower() != speaker.to_lower():
			continue
		var candidate_visual_id: String = String(candidate.get("visual_id"))
		if candidate_visual_id.is_empty():
			candidate_visual_id = candidate_id
		var candidate_visual: Resource = VisualCatalog.definition(candidate_visual_id)
		if candidate_visual == null:
			continue
		var candidate_path: String = String(candidate_visual.get("portrait_path"))
		if not candidate_path.is_empty() and ResourceLoader.exists(candidate_path):
			return load(candidate_path) as Texture2D

	return null


func _resource_files(directory: String) -> Array[String]:
	var result: Array[String] = []
	var dir := DirAccess.open(directory)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(directory + file_name)
	result.sort()
	return result


func _refresh_selector() -> void:
	var wanted := current_path
	cinematic_select.clear()
	for path in _resource_files(CINEMATIC_DIR):
		var data := load(path)
		if data == null:
			continue
		cinematic_select.add_item("%s  [%s]" % [String(data.display_name), String(data.id)])
		cinematic_select.set_item_metadata(cinematic_select.item_count - 1, path)
	if cinematic_select.item_count > 0:
		var idx := _metadata_index(cinematic_select, wanted)
		if idx < 0:
			idx = 0
		cinematic_select.select(idx)
		_on_selected(idx)


func _on_selected(index: int) -> void:
	if dirty:
		_save_current()
	if index < 0 or index >= cinematic_select.item_count:
		return
	current_path = String(cinematic_select.get_item_metadata(index))
	current = load(current_path)
	if current == null:
		return
	name_edit.text = String(current.display_name)
	description_edit.text = String(current.description)
	dirty = false
	_refresh_nested_options()
	_refresh_action_list()


func _new_cinematic() -> void:
	_save_current()
	var id := _unique_id("cinematic")
	var data := CinematicDefinition.new()
	data.id = id
	data.display_name = "Nouvelle cinématique"
	data.description = "Créée dans Sporebound Studio V1.7"
	var path := CINEMATIC_DIR + id + ".tres"
	ResourceSaver.save(data, path)
	current_path = path
	_refresh_selector()


func _duplicate_cinematic() -> void:
	if current == null:
		return
	_save_current()
	var copy := current.duplicate(true)
	copy.id = _unique_id(String(current.id) + "_copy")
	copy.display_name = String(current.display_name) + " — copie"
	var path := CINEMATIC_DIR + String(copy.id) + ".tres"
	ResourceSaver.save(copy, path)
	current_path = path
	_refresh_selector()


func _save_current() -> void:
	if current == null or current_path.is_empty():
		return
	current.display_name = name_edit.text.strip_edges()
	current.description = description_edit.text
	ResourceSaver.save(current, current_path)
	dirty = false
	_validate_current()


func _refresh_action_list() -> void:
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
	_validate_current()


func _add_action() -> void:
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
	_refresh_action_list()


func _duplicate_action() -> void:
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
	_refresh_action_list()


func _move_action(direction: int) -> void:
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
	_refresh_action_list()


func _remove_action() -> void:
	if current == null or action_index < 0 or action_index >= current.actions.size():
		return
	current.actions.remove_at(action_index)
	if current.actions.is_empty():
		action_index = -1
	else:
		action_index = mini(action_index, current.actions.size() - 1)
	dirty = true
	_refresh_action_list()


func _unique_action_id(base_id: String) -> String:
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


func _on_action_selected(index: int) -> void:
	if current == null or index < 0 or index >= current.actions.size():
		return
	action_index = index
	if action_list != null:
		action_list.select(index)
	var action = current.actions[index]
	_select_text(action_type, String(action.action_type))
	action_delay.value = float(action.delay_seconds)
	action_message.text = String(action.message)
	action_speaker.text = String(action.speaker)
	_select_metadata(action_unit, String(action.unit_id))
	action_cell_x.value = action.cell.x
	action_cell_y.value = action.cell.y
	action_value.value = int(action.value)
	_select_metadata(action_nested, String(action.cinematic_id))
	action_portrait.text = String(action.portrait_path)
	_select_text(action_side, String(action.portrait_side))
	action_wait_input.button_pressed = bool(action.wait_for_input)
	action_auto.value = float(action.auto_advance_seconds)
	_refresh_dialogue_profile_options()
	_select_metadata(action_dialogue_profile, String(action.dialogue_profile_id))
	action_override_dialogue_profile.button_pressed = bool(action.override_dialogue_profile)
	action_text_speed.value = float(action.text_speed)
	action_voice_pitch.value = float(action.voice_pitch)
	action_blip_every.value = int(action.blip_every)
	action_zoom.value = float(action.camera_zoom)
	action_duration.value = float(action.camera_duration)
	action_audio.text = String(action.audio_path)
	action_volume.value = float(action.volume_db)
	call_deferred("_refresh_dialogue_preview", false)


func _apply_action() -> void:
	if current == null or action_index < 0 or action_index >= current.actions.size():
		return
	var action = current.actions[action_index]
	action.action_type = action_type.get_item_text(action_type.selected)
	action.delay_seconds = float(action_delay.value)
	action.message = action_message.text
	action.speaker = action_speaker.text.strip_edges()
	action.unit_id = String(action_unit.get_item_metadata(action_unit.selected)) if action_unit.selected >= 0 else ""
	action.cell = Vector2i(int(action_cell_x.value), int(action_cell_y.value))
	action.value = int(action_value.value)
	action.cinematic_id = String(action_nested.get_item_metadata(action_nested.selected)) if action_nested.selected >= 0 else ""
	action.portrait_path = action_portrait.text.strip_edges()
	action.portrait_side = action_side.get_item_text(action_side.selected)
	action.wait_for_input = action_wait_input.button_pressed
	action.auto_advance_seconds = float(action_auto.value)
	action.text_speed = float(action_text_speed.value)
	action.voice_pitch = float(action_voice_pitch.value)
	action.blip_every = int(action_blip_every.value)
	action.camera_zoom = float(action_zoom.value)
	action.camera_duration = float(action_duration.value)
	action.audio_path = action_audio.text.strip_edges()
	action.volume_db = float(action_volume.value)
	dirty = true
	_refresh_action_list()
	action_list.select(action_index)
	call_deferred("_refresh_dialogue_preview", false)


func _refresh_nested_options() -> void:
	if action_nested == null:
		return
	var selected_id := ""
	if current != null and action_index >= 0 and action_index < current.actions.size():
		selected_id = String(current.actions[action_index].cinematic_id)
	action_nested.clear()
	action_nested.add_item("— aucune —")
	action_nested.set_item_metadata(0, "")
	for path in _resource_files(CINEMATIC_DIR):
		var data := load(path)
		action_nested.add_item(String(data.display_name))
		action_nested.set_item_metadata(action_nested.item_count - 1, String(data.id))
	_select_metadata(action_nested, selected_id)
	_refresh_unit_options()
	_refresh_dialogue_profile_options()


func _refresh_dialogue_profile_options() -> void:
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


func _refresh_unit_options() -> void:
	var wanted := ""
	if action_unit != null and action_unit.selected >= 0:
		wanted = String(action_unit.get_item_metadata(action_unit.selected))
	action_unit.clear()
	action_unit.add_item("— aucune —")
	action_unit.set_item_metadata(0, "")
	for path in _resource_files(UNIT_DIR):
		var data := load(path)
		action_unit.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		action_unit.set_item_metadata(action_unit.item_count - 1, String(data.id))
	_select_metadata(action_unit, wanted)


func _refresh_mission_binding() -> void:
	if mission_select == null:
		return
	mission_select.clear()
	for path in _resource_files(MISSION_DIR):
		var mission := load(path)
		mission_select.add_item("%s [%s]" % [String(mission.display_name), String(mission.id)])
		mission_select.set_item_metadata(mission_select.item_count - 1, path)
	_refresh_binding_options(mission_intro)
	_refresh_binding_options(mission_victory)
	_refresh_binding_options(mission_defeat)
	if mission_select.item_count > 0:
		mission_select.select(0)
		_on_mission_selected(0)


func _refresh_binding_options(option: OptionButton) -> void:
	option.clear()
	option.add_item("— aucune —")
	option.set_item_metadata(0, "")
	for path in _resource_files(CINEMATIC_DIR):
		var data := load(path)
		option.add_item(String(data.display_name))
		option.set_item_metadata(option.item_count - 1, String(data.id))


func _on_mission_selected(index: int) -> void:
	if index < 0 or index >= mission_select.item_count:
		return
	var mission := load(String(mission_select.get_item_metadata(index)))
	if mission == null:
		return
	_select_metadata(mission_intro, String(mission.intro_cinematic_id))
	_select_metadata(mission_victory, String(mission.victory_cinematic_id))
	_select_metadata(mission_defeat, String(mission.defeat_cinematic_id))


func _apply_mission_binding() -> void:
	if mission_select.selected < 0:
		return
	var path := String(mission_select.get_item_metadata(mission_select.selected))
	var mission := load(path)
	if mission == null:
		return
	mission.intro_cinematic_id = String(mission_intro.get_item_metadata(mission_intro.selected))
	mission.victory_cinematic_id = String(mission_victory.get_item_metadata(mission_victory.selected))
	mission.defeat_cinematic_id = String(mission_defeat.get_item_metadata(mission_defeat.selected))
	ResourceSaver.save(mission, path)
	validation.text = "✓ Assignation cinématique sauvegardée dans %s" % String(mission.display_name)


func _validate_current() -> void:
	if validation == null:
		return
	if current == null:
		validation.text = "Aucune cinématique."
		return
	var issues: Array[String] = []
	for i in range(current.actions.size()):
		var action = current.actions[i]
		if action == null:
			issues.append("Action %d vide" % (i + 1))
			continue
		if String(action.action_type) == "dialogue" and String(action.message).strip_edges().is_empty():
			issues.append("Dialogue %d sans texte" % (i + 1))
		if String(action.action_type) == "play_cinematic" and String(action.cinematic_id).is_empty():
			issues.append("Action %d play_cinematic sans cible" % (i + 1))
		if String(action.portrait_path) != "" and not ResourceLoader.exists(String(action.portrait_path)):
			issues.append("Portrait introuvable action %d" % (i + 1))
		if String(action.audio_path) != "" and not ResourceLoader.exists(String(action.audio_path)):
			issues.append("Audio introuvable action %d" % (i + 1))
	validation.text = "✓ Timeline valide • %d action(s)" % current.actions.size() if issues.is_empty() else "⚠ " + " • ".join(issues)


func _cinematic_option(parent: VBoxContainer, label_text: String) -> OptionButton:
	_add_label(parent, label_text)
	var option := OptionButton.new()
	parent.add_child(option)
	return option


func _line(parent: VBoxContainer, label_text: String) -> LineEdit:
	_add_label(parent, label_text)
	var edit := LineEdit.new()
	parent.add_child(edit)
	return edit


func _text(parent: VBoxContainer, label_text: String, min_height: float) -> TextEdit:
	_add_label(parent, label_text)
	var edit := TextEdit.new()
	edit.custom_minimum_size.y = min_height
	edit.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	parent.add_child(edit)
	return edit


func _spin(parent: VBoxContainer, label_text: String, min_value: float, max_value: float, step_value: float) -> SpinBox:
	_add_label(parent, label_text)
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = step_value
	parent.add_child(spin)
	return spin


func _compact_spin(parent: HBoxContainer, label_text: String, min_value: float, max_value: float) -> SpinBox:
	var box := VBoxContainer.new()
	parent.add_child(box)
	var label := Label.new()
	label.text = label_text
	box.add_child(label)
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = 1
	spin.custom_minimum_size.x = 120
	box.add_child(spin)
	return spin


func _add_label(parent: VBoxContainer, value: String) -> void:
	var label := Label.new()
	label.text = value
	parent.add_child(label)


func _metadata_index(option: OptionButton, metadata_value: String) -> int:
	for i in range(option.item_count):
		if String(option.get_item_metadata(i)) == metadata_value:
			return i
	return -1


func _select_metadata(option: OptionButton, metadata_value: String) -> void:
	var idx := _metadata_index(option, metadata_value)
	option.select(max(0, idx))


func _select_text(option: OptionButton, value: String) -> void:
	for i in range(option.item_count):
		if option.get_item_text(i) == value:
			option.select(i)
			return
	option.select(0)


func _unique_id(base: String) -> String:
	var clean := base.to_lower().replace(" ", "_").replace("-", "_")
	var candidate := clean
	var index := 2
	while ResourceLoader.exists(CINEMATIC_DIR + candidate + ".tres"):
		candidate = "%s_%d" % [clean, index]
		index += 1
	return candidate
