@tool
class_name SporeCinematicEditor
extends VBoxContainer

const CinematicDefinition = preload("res://scripts/data/cinematic_definition.gd")
const BattleActionDefinition = preload("res://scripts/data/battle_action_definition.gd")

const CINEMATIC_DIR := "res://data/cinematics/"
const MISSION_DIR := "res://data/missions/"
const UNIT_DIR := "res://data/units/"
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
var action_list: ItemList
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
var action_zoom: SpinBox
var action_duration: SpinBox
var action_audio: LineEdit
var action_volume: SpinBox
var mission_select: OptionButton
var mission_intro: OptionButton
var mission_victory: OptionButton
var mission_defeat: OptionButton
var validation: Label


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
	action_list = ItemList.new()
	action_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	action_list.item_selected.connect(_on_action_selected)
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
	action_zoom = _spin(right, "Zoom caméra", 0.25, 3.0, 0.05)
	action_duration = _spin(right, "Durée caméra/fondu (s)", 0, 5, 0.05)
	action_audio = _line(right, "Audio res://... (.ogg/.wav/.mp3)")
	action_volume = _spin(right, "Volume dB", -40, 6, 0.5)
	var apply := Button.new()
	apply.text = "Appliquer l'action"
	apply.pressed.connect(_apply_action)
	right.add_child(apply)

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
	action_list.clear()
	action_index = -1
	if current == null:
		return
	for action in current.actions:
		action_list.add_item(action.summary() if action != null and action.has_method("summary") else "<action>")
	if not current.actions.is_empty():
		action_list.select(0)
		_on_action_selected(0)
	_validate_current()


func _add_action() -> void:
	if current == null:
		return
	var action := BattleActionDefinition.new()
	action.id = "action_%02d" % (current.actions.size() + 1)
	action.action_type = "dialogue"
	action.speaker = "Narrateur"
	action.message = "Nouvelle réplique."
	current.actions.append(action)
	dirty = true
	_refresh_action_list()
	action_index = current.actions.size() - 1
	action_list.select(action_index)
	_on_action_selected(action_index)


func _duplicate_action() -> void:
	if current == null or action_index < 0 or action_index >= current.actions.size():
		return
	var copy := current.actions[action_index].duplicate(true)
	copy.id = String(copy.id) + "_copy"
	current.actions.insert(action_index + 1, copy)
	dirty = true
	_refresh_action_list()
	action_index += 1
	action_list.select(action_index)
	_on_action_selected(action_index)


func _move_action(direction: int) -> void:
	if current == null or action_index < 0:
		return
	var target := action_index + direction
	if target < 0 or target >= current.actions.size():
		return
	var action = current.actions[action_index]
	current.actions.remove_at(action_index)
	current.actions.insert(target, action)
	action_index = target
	dirty = true
	_refresh_action_list()
	action_list.select(action_index)
	_on_action_selected(action_index)


func _remove_action() -> void:
	if current == null or action_index < 0 or action_index >= current.actions.size():
		return
	current.actions.remove_at(action_index)
	dirty = true
	_refresh_action_list()


func _on_action_selected(index: int) -> void:
	if current == null or index < 0 or index >= current.actions.size():
		return
	action_index = index
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
	action_zoom.value = float(action.camera_zoom)
	action_duration.value = float(action.camera_duration)
	action_audio.text = String(action.audio_path)
	action_volume.value = float(action.volume_db)


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
	action.camera_zoom = float(action_zoom.value)
	action.camera_duration = float(action_duration.value)
	action.audio_path = action_audio.text.strip_edges()
	action.volume_db = float(action_volume.value)
	dirty = true
	_refresh_action_list()
	action_list.select(action_index)


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
