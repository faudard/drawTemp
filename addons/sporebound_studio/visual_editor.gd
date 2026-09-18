@tool
class_name SporeVisualEditor
extends VBoxContainer

signal library_changed

const VisualDefinition = preload("res://scripts/data/unit_visual_definition.gd")
const VisualPreview = preload("res://addons/sporebound_studio/visual_preview.gd")
const VISUAL_DIR := "res://data/visuals/units/"
const UNIT_DIR := "res://data/units/"
const VFX_DIR := "res://data/vfx/"
const STATES := ["idle", "move", "attack", "cast", "hit", "ko"]

var select: OptionButton
var current: Resource
var current_path := ""
var dirty := false
var name_edit: LineEdit
var unit_select: OptionButton
var render_mode: OptionButton
var portrait_edit: LineEdit
var attack_pose_edit: LineEdit
var cast_pose_edit: LineEdit
var sprite_edit: LineEdit
var use_sprite: CheckBox
var frame_w: SpinBox
var frame_h: SpinBox
var scale_edit: SpinBox
var offset_x: SpinBox
var offset_y: SpinBox
var flip_facing: CheckBox
var direction_mode: OptionButton
var direction_layout: OptionButton
var direction_stride: SpinBox
var four_order: LineEdit
var eight_order: LineEdit
var shape_select: OptionButton
var primary: ColorPickerButton
var secondary: ColorPickerButton
var accent: ColorPickerButton
var outline: ColorPickerButton
var tint_sprite: CheckBox
var basic_vfx: OptionButton
var clip_controls: Dictionary = {}
var preview_state: OptionButton
var preview_direction: OptionButton
var preview: SporeVisualPreview
var validation: Label
var file_dialog: FileDialog
var file_target := ""
var loading := false


func _ready() -> void:
	name = "Visuals"
	_build_ui()
	_wire_signals()
	refresh()


func has_unsaved_data() -> bool:
	return dirty


func save_external_data() -> void:
	_save_current()


func refresh() -> void:
	if dirty:
		_save_current()
	_refresh_units()
	_refresh_vfx()
	_refresh_selector()


func _build_ui() -> void:
	var split := HSplitContainer.new()
	split.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(split)
	var left_scroll := ScrollContainer.new()
	left_scroll.custom_minimum_size.x = 610
	split.add_child(left_scroll)
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_scroll.add_child(left)
	var title := Label.new()
	title.text = "UNIT VISUALS / SKINS"
	title.add_theme_font_size_override("font_size", 18)
	left.add_child(title)
	var bar := HBoxContainer.new()
	left.add_child(bar)
	select = OptionButton.new()
	select.custom_minimum_size.x = 260
	select.item_selected.connect(_on_selected)
	bar.add_child(select)
	for spec in [["+ Visuel", _new_visual], ["Dupliquer", _duplicate], ["Sauver", _save_current]]:
		var button := Button.new()
		button.text = spec[0]
		button.pressed.connect(spec[1])
		bar.add_child(button)
	name_edit = _line(left, "Nom affiché")
	_add_label(left, "Unité associée")
	unit_select = OptionButton.new()
	left.add_child(unit_select)
	_add_label(left, "Mode de rendu")
	render_mode = OptionButton.new()
	for value: String in ["auto", "procedural", "sprite_sheet", "portrait_billboard"]:
		render_mode.add_item(value)
	left.add_child(render_mode)
	portrait_edit = _path_row(left, "Portrait", "portrait")
	attack_pose_edit = _path_row(left, "Pose attaque (portrait billboard)", "attack_pose")
	cast_pose_edit = _path_row(left, "Pose cast (portrait billboard)", "cast_pose")
	sprite_edit = _path_row(left, "Spritesheet", "sprite")
	use_sprite = CheckBox.new()
	use_sprite.text = "Utiliser le spritesheet au runtime"
	left.add_child(use_sprite)
	var atlas := GridContainer.new()
	atlas.columns = 2
	left.add_child(atlas)
	frame_w = _grid_spin(atlas, "Frame largeur", 0, 1024, 1)
	frame_h = _grid_spin(atlas, "Frame hauteur", 0, 1024, 1)
	scale_edit = _grid_spin(atlas, "Échelle", 0.1, 8, 0.05)
	offset_x = _grid_spin(atlas, "Offset X", -300, 300, 1)
	offset_y = _grid_spin(atlas, "Offset Y", -300, 300, 1)
	flip_facing = CheckBox.new()
	flip_facing.text = "Flip horizontal selon orientation"
	left.add_child(flip_facing)
	var direction_title := Label.new()
	direction_title.text = "DIRECTIONS DU SPRITESHEET"
	direction_title.add_theme_font_size_override("font_size", 15)
	left.add_child(direction_title)
	var direction_grid := GridContainer.new()
	direction_grid.columns = 2
	left.add_child(direction_grid)
	_add_label(direction_grid, "Mode")
	direction_mode = OptionButton.new()
	for value: String in ["single", "4_way", "8_way"]:
		direction_mode.add_item(value)
	direction_grid.add_child(direction_mode)
	_add_label(direction_grid, "Layout")
	direction_layout = OptionButton.new()
	for value: String in ["rows", "blocks"]:
		direction_layout.add_item(value)
	direction_grid.add_child(direction_layout)
	direction_stride = _grid_spin(direction_grid, "Stride frames", 0, 999, 1)
	four_order = _line(left, "Ordre 4 directions")
	eight_order = _line(left, "Ordre 8 directions")
	_add_label(left, "Fallback procédural")
	shape_select = OptionButton.new()
	for value in ["mushroom", "slime", "armored", "orb"]:
		shape_select.add_item(value)
	left.add_child(shape_select)
	var colors := GridContainer.new()
	colors.columns = 4
	left.add_child(colors)
	primary = _color(colors, "Primaire")
	secondary = _color(colors, "Secondaire")
	accent = _color(colors, "Accent")
	outline = _color(colors, "Contour")
	tint_sprite = CheckBox.new()
	tint_sprite.text = "Teinter le sprite avec la couleur primaire"
	left.add_child(tint_sprite)
	_add_label(left, "VFX attaque de base")
	basic_vfx = OptionButton.new()
	left.add_child(basic_vfx)
	var clip_title := Label.new()
	clip_title.text = "CLIPS D'ANIMATION (index de frame dans le spritesheet)"
	clip_title.add_theme_font_size_override("font_size", 15)
	left.add_child(clip_title)
	var clips := GridContainer.new()
	clips.columns = 6
	left.add_child(clips)
	for label in ["État", "Start", "Frames", "FPS", "Loop", ""]:
		var header := Label.new()
		header.text = label
		clips.add_child(header)
	for state in STATES:
		var state_label := Label.new()
		state_label.text = state.capitalize()
		clips.add_child(state_label)
		var start := _bare_spin(0, 999, 1)
		var count := _bare_spin(1, 999, 1)
		var fps := _bare_spin(0.1, 60, 0.1)
		var loop := CheckBox.new()
		var spacer := Control.new()
		clips.add_child(start)
		clips.add_child(count)
		clips.add_child(fps)
		clips.add_child(loop)
		clips.add_child(spacer)
		clip_controls[state] = {"start": start, "count": count, "fps": fps, "loop": loop}
	var apply := Button.new()
	apply.text = "Appliquer les champs au visuel"
	apply.pressed.connect(_apply_fields)
	left.add_child(apply)
	validation = Label.new()
	validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(validation)

	var right := VBoxContainer.new()
	right.custom_minimum_size.x = 460
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.add_child(right)
	var preview_title := Label.new()
	preview_title.text = "PRÉVISUALISATION LIVE"
	preview_title.add_theme_font_size_override("font_size", 18)
	right.add_child(preview_title)
	preview_state = OptionButton.new()
	for state in STATES:
		preview_state.add_item(state)
	preview_state.item_selected.connect(_on_preview_state)
	right.add_child(preview_state)
	preview_direction = OptionButton.new()
	for view_name: String in ["front", "front_right", "right", "back_right", "back", "back_left", "left", "front_left"]:
		preview_direction.add_item(view_name)
	preview_direction.item_selected.connect(_on_preview_direction)
	right.add_child(preview_direction)
	preview = VisualPreview.new()
	preview.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	preview.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(preview)
	var help := Label.new()
	help.text = "portrait_billboard affiche directement le portrait de bibliothèque dans la carte 3D. sprite_sheet utilise l’atlas directionnel. procedural conserve le rendu généré. En mode rows : une ligne = une direction."
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(help)

	file_dialog = FileDialog.new()
	file_dialog.access = FileDialog.ACCESS_RESOURCES
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	file_dialog.filters = PackedStringArray(["*.png ; PNG", "*.jpg,*.jpeg ; JPEG", "*.webp ; WebP", "*.svg ; SVG"])
	file_dialog.file_selected.connect(_on_file_selected)
	add_child(file_dialog)


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
	select.clear()
	for path in _resource_files(VISUAL_DIR):
		var data := load(path)
		if data == null:
			continue
		select.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		select.set_item_metadata(select.item_count - 1, path)
	if select.item_count > 0:
		var index := _metadata_index(select, wanted)
		if index < 0:
			index = 0
		select.select(index)
		_on_selected(index)


func _refresh_units() -> void:
	if unit_select == null:
		return
	var wanted = unit_select.get_item_metadata(unit_select.selected) if unit_select.item_count > 0 else ""
	unit_select.clear()
	unit_select.add_item("(Aucune — skin bibliothèque)")
	unit_select.set_item_metadata(0, "")
	for path in _resource_files(UNIT_DIR):
		var data := load(path)
		unit_select.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		unit_select.set_item_metadata(unit_select.item_count - 1, String(data.id))
	_select_metadata(unit_select, wanted)


func _refresh_vfx() -> void:
	if basic_vfx == null:
		return
	var wanted = basic_vfx.get_item_metadata(basic_vfx.selected) if basic_vfx.item_count > 0 else "default_hit"
	basic_vfx.clear()
	for path in _resource_files(VFX_DIR):
		var data := load(path)
		basic_vfx.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		basic_vfx.set_item_metadata(basic_vfx.item_count - 1, String(data.id))
	_select_metadata(basic_vfx, wanted)


func _on_selected(index: int) -> void:
	if dirty:
		_save_current()
	if index < 0 or index >= select.item_count:
		return
	current_path = String(select.get_item_metadata(index))
	current = load(current_path)
	if current == null:
		return
	loading = true
	name_edit.text = String(current.display_name)
	_select_metadata(unit_select, String(current.unit_id))
	_select_text(render_mode, String(current.render_mode))
	portrait_edit.text = String(current.portrait_path)
	attack_pose_edit.text = String(current.attack_pose_path)
	cast_pose_edit.text = String(current.cast_pose_path)
	sprite_edit.text = String(current.sprite_sheet_path)
	use_sprite.button_pressed = bool(current.use_sprite_sheet)
	frame_w.value = int(current.frame_width)
	frame_h.value = int(current.frame_height)
	scale_edit.value = float(current.sprite_scale)
	offset_x.value = float(current.sprite_offset.x)
	offset_y.value = float(current.sprite_offset.y)
	flip_facing.button_pressed = bool(current.flip_with_facing)
	_select_text(direction_mode, String(current.direction_mode))
	_select_text(direction_layout, String(current.direction_layout))
	direction_stride.value = int(current.direction_stride_frames)
	four_order.text = String(current.four_direction_order)
	eight_order.text = String(current.eight_direction_order)
	_select_text(shape_select, String(current.fallback_shape))
	primary.color = current.primary_color
	secondary.color = current.secondary_color
	accent.color = current.accent_color
	outline.color = current.outline_color
	tint_sprite.button_pressed = bool(current.tint_sprite_with_primary)
	_select_metadata(basic_vfx, String(current.basic_attack_vfx_id))
	for state in STATES:
		var controls: Dictionary = clip_controls[state]
		var clip: Dictionary = current.clip_data(state)
		controls["start"].value = int(clip["start"])
		controls["count"].value = int(clip["count"])
		controls["fps"].value = float(clip["fps"])
		controls["loop"].button_pressed = bool(clip["loop"])
	dirty = false
	loading = false
	preview.set_visual(current)
	_validate()


func _apply_fields() -> void:
	if current == null or loading:
		return
	current.display_name = name_edit.text.strip_edges()
	current.unit_id = String(unit_select.get_item_metadata(unit_select.selected)) if unit_select.item_count > 0 else ""
	current.render_mode = render_mode.get_item_text(render_mode.selected)
	current.portrait_path = portrait_edit.text.strip_edges()
	current.attack_pose_path = attack_pose_edit.text.strip_edges()
	current.cast_pose_path = cast_pose_edit.text.strip_edges()
	current.sprite_sheet_path = sprite_edit.text.strip_edges()
	current.use_sprite_sheet = use_sprite.button_pressed
	current.frame_width = int(frame_w.value)
	current.frame_height = int(frame_h.value)
	current.sprite_scale = float(scale_edit.value)
	current.sprite_offset = Vector2(float(offset_x.value), float(offset_y.value))
	current.flip_with_facing = flip_facing.button_pressed
	current.direction_mode = direction_mode.get_item_text(direction_mode.selected)
	current.direction_layout = direction_layout.get_item_text(direction_layout.selected)
	current.direction_stride_frames = int(direction_stride.value)
	current.four_direction_order = four_order.text.strip_edges()
	current.eight_direction_order = eight_order.text.strip_edges()
	current.fallback_shape = shape_select.get_item_text(shape_select.selected)
	current.primary_color = primary.color
	current.secondary_color = secondary.color
	current.accent_color = accent.color
	current.outline_color = outline.color
	current.tint_sprite_with_primary = tint_sprite.button_pressed
	current.basic_attack_vfx_id = String(basic_vfx.get_item_metadata(basic_vfx.selected)) if basic_vfx.item_count > 0 else "default_hit"
	for state in STATES:
		var controls: Dictionary = clip_controls[state]
		current.set(state + "_start", int(controls["start"].value))
		current.set(state + "_count", int(controls["count"].value))
		current.set(state + "_fps", float(controls["fps"].value))
		current.set(state + "_loop", bool(controls["loop"].button_pressed))
	dirty = true
	preview.set_visual(current)
	_validate()


func _save_current() -> void:
	if current == null or current_path.is_empty():
		return
	_apply_fields()
	ResourceSaver.save(current, current_path)
	dirty = false
	library_changed.emit()
	_validate()


func _new_visual() -> void:
	_save_current()
	var base := "visual"
	if unit_select.item_count > 0:
		base = String(unit_select.get_item_metadata(unit_select.selected))
	var id := _unique_id(base)
	var data: Resource = VisualDefinition.new()
	data.id = id
	data.display_name = id.capitalize()
	data.unit_id = base
	var path := VISUAL_DIR + id + ".tres"
	ResourceSaver.save(data, path)
	current_path = path
	_refresh_selector()


func _duplicate() -> void:
	if current == null:
		return
	_save_current()
	var copy: Resource = current.duplicate(true)
	copy.id = _unique_id(String(current.id) + "_skin")
	copy.display_name = String(current.display_name) + " Skin"
	var path := VISUAL_DIR + String(copy.id) + ".tres"
	ResourceSaver.save(copy, path)
	current_path = path
	_refresh_selector()


func _unique_id(base: String) -> String:
	var clean := base.to_lower().replace(" ", "_").replace("-", "_")
	if clean.is_empty():
		clean = "visual"
	var candidate := clean
	var index := 2
	while ResourceLoader.exists(VISUAL_DIR + candidate + ".tres"):
		candidate = "%s_%d" % [clean, index]
		index += 1
	return candidate


func _validate() -> void:
	if current == null:
		return
	var issues: Array[String] = []
	var visual_id: String = String(current.id)
	var unit_id: String = String(current.unit_id)
	if not unit_id.is_empty() and not ResourceLoader.exists(UNIT_DIR + unit_id + ".tres"):
		issues.append("Unité associée inconnue")
	elif unit_id.is_empty() and not visual_id.begins_with("lib_"):
		issues.append("Unité associée requise hors skin bibliothèque")
	var current_render_mode: String = String(current.render_mode)
	if current_render_mode == "portrait_billboard":
		if String(current.portrait_path).is_empty() or not ResourceLoader.exists(String(current.portrait_path)):
			issues.append("Mode portrait_billboard : portrait requis")
	if current_render_mode == "sprite_sheet" or (current_render_mode == "auto" and bool(current.use_sprite_sheet)):
		if String(current.sprite_sheet_path).is_empty() or not ResourceLoader.exists(String(current.sprite_sheet_path)):
			issues.append("Spritesheet activé mais ressource introuvable")
		if int(current.frame_width) <= 0 or int(current.frame_height) <= 0:
			issues.append("Définis la taille des frames")
	if not String(current.portrait_path).is_empty() and not ResourceLoader.exists(String(current.portrait_path)):
		issues.append("Portrait introuvable")
	if not String(current.attack_pose_path).is_empty() and not ResourceLoader.exists(String(current.attack_pose_path)):
		issues.append("Pose attaque introuvable")
	if not String(current.cast_pose_path).is_empty() and not ResourceLoader.exists(String(current.cast_pose_path)):
		issues.append("Pose cast introuvable")
	if String(current.direction_mode) == "4_way" and String(current.four_direction_order).split(",").size() != 4:
		issues.append("Ordre 4 directions : 4 noms requis")
	if String(current.direction_mode) == "8_way" and String(current.eight_direction_order).split(",").size() != 8:
		issues.append("Ordre 8 directions : 8 noms requis")
	var mode_label: String = String(current.render_mode)
	validation.text = "✓ Visuel valide — mode %s." % mode_label if issues.is_empty() else "⚠ " + " • ".join(issues)
	validation.add_theme_color_override("font_color", Color("#8fe0ad") if issues.is_empty() else Color("#ffb36b"))


func _on_preview_state(index: int) -> void:
	if index >= 0 and index < preview_state.item_count:
		preview.set_state(preview_state.get_item_text(index))


func _on_preview_direction(index: int) -> void:
	if index >= 0 and index < preview_direction.item_count:
		preview.set_direction(preview_direction.get_item_text(index))


func _wire_signals() -> void:
	for edit in [name_edit, portrait_edit, attack_pose_edit, cast_pose_edit, sprite_edit, four_order, eight_order]:
		edit.text_changed.connect(_live_changed)
	for option in [unit_select, render_mode, shape_select, basic_vfx, direction_mode, direction_layout]:
		option.item_selected.connect(_live_changed)
	for check in [use_sprite, flip_facing, tint_sprite]:
		check.toggled.connect(_live_changed)
	for spin in [frame_w, frame_h, scale_edit, offset_x, offset_y, direction_stride]:
		spin.value_changed.connect(_live_changed)
	for picker in [primary, secondary, accent, outline]:
		picker.color_changed.connect(_live_changed)
	for state in STATES:
		var controls: Dictionary = clip_controls[state]
		controls["start"].value_changed.connect(_live_changed)
		controls["count"].value_changed.connect(_live_changed)
		controls["fps"].value_changed.connect(_live_changed)
		controls["loop"].toggled.connect(_live_changed)


func _live_changed(_value: Variant = null) -> void:
	if loading:
		return
	_apply_fields()


func _path_row(parent: Control, label_text: String, target: String) -> LineEdit:
	_add_label(parent, label_text)
	var row := HBoxContainer.new()
	parent.add_child(row)
	var edit := LineEdit.new()
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(edit)
	var browse := Button.new()
	browse.text = "…"
	browse.pressed.connect(_browse.bind(target))
	row.add_child(browse)
	return edit


func _browse(target: String) -> void:
	file_target = target
	file_dialog.popup_centered_ratio(0.7)


func _on_file_selected(path: String) -> void:
	if file_target == "portrait":
		portrait_edit.text = path
	elif file_target == "attack_pose":
		attack_pose_edit.text = path
	elif file_target == "cast_pose":
		cast_pose_edit.text = path
	elif file_target == "sprite":
		sprite_edit.text = path
	_apply_fields()


func _line(parent: Control, label_text: String) -> LineEdit:
	_add_label(parent, label_text)
	var edit := LineEdit.new()
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(edit)
	return edit


func _add_label(parent: Control, text: String) -> void:
	var label := Label.new()
	label.text = text
	parent.add_child(label)


func _grid_spin(grid: GridContainer, label_text: String, min_value: float, max_value: float, step: float) -> SpinBox:
	var label := Label.new()
	label.text = label_text
	grid.add_child(label)
	var spin := _bare_spin(min_value, max_value, step)
	grid.add_child(spin)
	return spin


func _bare_spin(min_value: float, max_value: float, step: float) -> SpinBox:
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = step
	spin.allow_greater = false
	spin.allow_lesser = false
	spin.custom_minimum_size.x = 90
	return spin


func _color(grid: GridContainer, label_text: String) -> ColorPickerButton:
	var box := VBoxContainer.new()
	grid.add_child(box)
	var label := Label.new()
	label.text = label_text
	box.add_child(label)
	var picker := ColorPickerButton.new()
	picker.custom_minimum_size = Vector2(120, 32)
	box.add_child(picker)
	return picker


func _metadata_index(option: OptionButton, wanted: Variant) -> int:
	for index in range(option.item_count):
		if option.get_item_metadata(index) == wanted:
			return index
	return -1


func _select_metadata(option: OptionButton, wanted: Variant) -> void:
	var index := _metadata_index(option, wanted)
	if index >= 0:
		option.select(index)


func _select_text(option: OptionButton, wanted: String) -> void:
	for index in range(option.item_count):
		if option.get_item_text(index) == wanted:
			option.select(index)
			return
