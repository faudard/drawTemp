@tool
class_name SporeVfxEditor
extends VBoxContainer

signal library_changed

const VfxDefinition = preload("res://scripts/data/vfx_definition.gd")
const VfxPreview = preload("res://addons/sporebound_studio/vfx_preview.gd")
const VFX_DIR := "res://data/vfx/"
const KINDS := ["burst", "projectile", "beam", "aura", "ring", "cross", "slash"]

var select: OptionButton
var current: Resource
var current_path := ""
var dirty := false
var name_edit: LineEdit
var desc_edit: TextEdit
var kind_select: OptionButton
var primary: ColorPickerButton
var secondary: ColorPickerButton
var texture_edit: LineEdit
var texture_scale: SpinBox
var duration: SpinBox
var particle_count: SpinBox
var radius: SpinBox
var trail: SpinBox
var shake: SpinBox
var flash: SpinBox
var frame_w: SpinBox
var frame_h: SpinBox
var start_frame: SpinBox
var frame_count: SpinBox
var fps: SpinBox
var loop: CheckBox
var preview: SporeVfxPreview
var validation: Label
var file_dialog: FileDialog
var loading := false


func _ready() -> void:
	name = "VFX"
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
	_refresh_selector()


func _build_ui() -> void:
	var split := HSplitContainer.new()
	split.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(split)
	var left_scroll := ScrollContainer.new()
	left_scroll.custom_minimum_size.x = 620
	split.add_child(left_scroll)
	var left := VBoxContainer.new()
	left_scroll.add_child(left)
	var title := Label.new()
	title.text = "VFX LIBRARY"
	title.add_theme_font_size_override("font_size", 18)
	left.add_child(title)
	var bar := HBoxContainer.new()
	left.add_child(bar)
	select = OptionButton.new()
	select.custom_minimum_size.x = 280
	select.item_selected.connect(_on_selected)
	bar.add_child(select)
	for spec in [["+ VFX", _new_vfx], ["Dupliquer", _duplicate], ["Sauver", _save_current]]:
		var button := Button.new()
		button.text = spec[0]
		button.pressed.connect(spec[1])
		bar.add_child(button)
	name_edit = _line(left, "Nom affiché")
	_add_label(left, "Description")
	desc_edit = TextEdit.new()
	desc_edit.custom_minimum_size.y = 65
	left.add_child(desc_edit)
	_add_label(left, "Type")
	kind_select = OptionButton.new()
	for value in KINDS:
		kind_select.add_item(value)
	left.add_child(kind_select)
	var colors := HBoxContainer.new()
	left.add_child(colors)
	primary = _color(colors, "Primaire")
	secondary = _color(colors, "Secondaire")
	texture_edit = _path_row(left, "Texture / spritesheet optionnel")
	var grid := GridContainer.new()
	grid.columns = 2
	left.add_child(grid)
	texture_scale = _grid_spin(grid, "Échelle texture", 0.1, 8, 0.05)
	duration = _grid_spin(grid, "Durée (s)", 0.05, 4, 0.05)
	particle_count = _grid_spin(grid, "Particules", 0, 64, 1)
	radius = _grid_spin(grid, "Rayon", 1, 180, 1)
	trail = _grid_spin(grid, "Largeur traînée", 1, 24, 0.5)
	shake = _grid_spin(grid, "Shake", 0, 20, 0.5)
	flash = _grid_spin(grid, "Flash", 0, 1, 0.05)
	frame_w = _grid_spin(grid, "Frame largeur", 0, 1024, 1)
	frame_h = _grid_spin(grid, "Frame hauteur", 0, 1024, 1)
	start_frame = _grid_spin(grid, "Start frame", 0, 999, 1)
	frame_count = _grid_spin(grid, "Nb frames", 1, 999, 1)
	fps = _grid_spin(grid, "FPS", 0.1, 60, 0.1)
	loop = CheckBox.new()
	loop.text = "Boucler l'animation texture"
	left.add_child(loop)
	var apply := Button.new()
	apply.text = "Appliquer au VFX"
	apply.pressed.connect(_apply_fields)
	left.add_child(apply)
	validation = Label.new()
	validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(validation)

	var right := VBoxContainer.new()
	right.custom_minimum_size.x = 450
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.add_child(right)
	var preview_title := Label.new()
	preview_title.text = "PRÉVISUALISATION LIVE"
	preview_title.add_theme_font_size_override("font_size", 18)
	right.add_child(preview_title)
	preview = VfxPreview.new()
	preview.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	preview.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(preview)
	var help := Label.new()
	help.text = "Un même VFX peut être référencé par plusieurs Skills, Statuses ou attaques de base. Sans texture, le rendu procédural reste actif."
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(help)

	file_dialog = FileDialog.new()
	file_dialog.access = FileDialog.ACCESS_RESOURCES
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	file_dialog.filters = PackedStringArray(["*.png ; PNG", "*.jpg,*.jpeg ; JPEG", "*.webp ; WebP"])
	file_dialog.file_selected.connect(_on_file_selected)
	add_child(file_dialog)


func _resource_files() -> Array[String]:
	var result: Array[String] = []
	var dir := DirAccess.open(VFX_DIR)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(VFX_DIR + file_name)
	result.sort()
	return result


func _refresh_selector() -> void:
	var wanted := current_path
	select.clear()
	for path in _resource_files():
		var data := load(path)
		select.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		select.set_item_metadata(select.item_count - 1, path)
	if select.item_count > 0:
		var idx := _metadata_index(select, wanted)
		if idx < 0:
			idx = 0
		select.select(idx)
		_on_selected(idx)


func _on_selected(index: int) -> void:
	if dirty:
		_save_current()
	if index < 0 or index >= select.item_count:
		return
	current_path = String(select.get_item_metadata(index))
	current = load(current_path)
	loading = true
	name_edit.text = String(current.display_name)
	desc_edit.text = String(current.description)
	_select_text(kind_select, String(current.kind))
	primary.color = current.primary_color
	secondary.color = current.secondary_color
	texture_edit.text = String(current.texture_path)
	texture_scale.value = float(current.texture_scale)
	duration.value = float(current.duration)
	particle_count.value = int(current.particle_count)
	radius.value = float(current.radius)
	trail.value = float(current.trail_width)
	shake.value = float(current.shake_strength)
	flash.value = float(current.flash_strength)
	frame_w.value = int(current.frame_width)
	frame_h.value = int(current.frame_height)
	start_frame.value = int(current.start_frame)
	frame_count.value = int(current.frame_count)
	fps.value = float(current.fps)
	loop.button_pressed = bool(current.loop)
	dirty = false
	loading = false
	preview.set_definition(current)
	_validate()


func _apply_fields() -> void:
	if current == null or loading:
		return
	current.display_name = name_edit.text.strip_edges()
	current.description = desc_edit.text
	current.kind = kind_select.get_item_text(kind_select.selected)
	current.primary_color = primary.color
	current.secondary_color = secondary.color
	current.texture_path = texture_edit.text.strip_edges()
	current.texture_scale = float(texture_scale.value)
	current.duration = float(duration.value)
	current.particle_count = int(particle_count.value)
	current.radius = float(radius.value)
	current.trail_width = float(trail.value)
	current.shake_strength = float(shake.value)
	current.flash_strength = float(flash.value)
	current.frame_width = int(frame_w.value)
	current.frame_height = int(frame_h.value)
	current.start_frame = int(start_frame.value)
	current.frame_count = int(frame_count.value)
	current.fps = float(fps.value)
	current.loop = loop.button_pressed
	dirty = true
	preview.set_definition(current)
	_validate()


func _save_current() -> void:
	if current == null or current_path.is_empty():
		return
	_apply_fields()
	ResourceSaver.save(current, current_path)
	dirty = false
	library_changed.emit()


func _new_vfx() -> void:
	_save_current()
	var id := _unique_id("new_vfx")
	var data: Resource = VfxDefinition.new()
	data.id = id
	data.display_name = "Nouveau VFX"
	var path := VFX_DIR + id + ".tres"
	ResourceSaver.save(data, path)
	current_path = path
	_refresh_selector()


func _duplicate() -> void:
	if current == null:
		return
	_save_current()
	var copy: Resource = current.duplicate(true)
	copy.id = _unique_id(String(current.id) + "_copy")
	copy.display_name = String(current.display_name) + " Copie"
	var path := VFX_DIR + String(copy.id) + ".tres"
	ResourceSaver.save(copy, path)
	current_path = path
	_refresh_selector()


func _unique_id(base: String) -> String:
	var candidate := base
	var index := 2
	while ResourceLoader.exists(VFX_DIR + candidate + ".tres"):
		candidate = "%s_%d" % [base, index]
		index += 1
	return candidate


func _validate() -> void:
	if current == null:
		return
	var issues: Array[String] = []
	if not String(current.texture_path).is_empty() and not ResourceLoader.exists(String(current.texture_path)):
		issues.append("Texture introuvable")
	if not String(current.texture_path).is_empty() and (int(current.frame_width) == 0) != (int(current.frame_height) == 0):
		issues.append("Largeur/hauteur de frame doivent être définies ensemble")
	validation.text = "✓ VFX valide." if issues.is_empty() else "⚠ " + " • ".join(issues)
	validation.add_theme_color_override("font_color", Color("#8fe0ad") if issues.is_empty() else Color("#ffb36b"))


func _wire_signals() -> void:
	for edit in [name_edit, desc_edit, texture_edit]:
		edit.text_changed.connect(_live_changed)
	kind_select.item_selected.connect(_live_changed)
	for picker in [primary, secondary]:
		picker.color_changed.connect(_live_changed)
	for spin in [texture_scale, duration, particle_count, radius, trail, shake, flash, frame_w, frame_h, start_frame, frame_count, fps]:
		spin.value_changed.connect(_live_changed)
	loop.toggled.connect(_live_changed)


func _live_changed(_value: Variant = null) -> void:
	if loading:
		return
	_apply_fields()


func _path_row(parent: Control, label_text: String) -> LineEdit:
	_add_label(parent, label_text)
	var row := HBoxContainer.new()
	parent.add_child(row)
	var edit := LineEdit.new()
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(edit)
	var browse := Button.new()
	browse.text = "…"
	browse.pressed.connect(_open_file_dialog)
	row.add_child(browse)
	return edit


func _open_file_dialog() -> void:
	file_dialog.popup_centered_ratio(0.7)


func _on_file_selected(path: String) -> void:
	texture_edit.text = path
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
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = step
	spin.custom_minimum_size.x = 120
	grid.add_child(spin)
	return spin


func _color(parent: Control, label_text: String) -> ColorPickerButton:
	var box := VBoxContainer.new()
	parent.add_child(box)
	var label := Label.new()
	label.text = label_text
	box.add_child(label)
	var picker := ColorPickerButton.new()
	picker.custom_minimum_size = Vector2(150, 34)
	box.add_child(picker)
	return picker


func _metadata_index(option: OptionButton, wanted: Variant) -> int:
	for index in range(option.item_count):
		if option.get_item_metadata(index) == wanted:
			return index
	return -1


func _select_text(option: OptionButton, wanted: String) -> void:
	for index in range(option.item_count):
		if option.get_item_text(index) == wanted:
			option.select(index)
			return
