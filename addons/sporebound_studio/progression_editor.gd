@tool
class_name SporeProgressionEditor
extends VBoxContainer

signal library_changed

const JobDefinition = preload("res://scripts/data/job_definition.gd")
const JobSkillUnlock = preload("res://scripts/data/job_skill_unlock.gd")
const ResistanceEntry = preload("res://scripts/data/resistance_entry.gd")
const EquipmentDefinition = preload("res://scripts/data/equipment_definition.gd")
const ProgressionTreeEditor = preload("res://addons/sporebound_studio/progression_tree_editor.gd")

const JOB_DIR := "res://data/jobs/"
const EQUIPMENT_DIR := "res://data/equipment/"
const SKILL_DIR := "res://data/skills/"
const STATUS_DIR := "res://data/statuses/"
const SLOTS := ["weapon", "armor", "accessory"]

var dirty_job := false
var dirty_equipment := false
var tree_editor: SporeProgressionTreeEditor
var status_label: Label

var job_select: OptionButton
var job_current: Resource
var job_path := ""
var job_name: LineEdit
var job_desc: TextEdit
var job_parent: OptionButton
var job_unlock_level: SpinBox
var job_next: LineEdit
var job_max_level: SpinBox
var job_hp: SpinBox
var job_attack: SpinBox
var job_move: SpinBox
var job_range: SpinBox
var job_init: SpinBox
var job_focus: SpinBox
var job_hp_growth: SpinBox
var job_attack_growth: SpinBox
var job_move_growth: SpinBox
var job_range_growth: SpinBox
var job_init_growth: SpinBox
var job_focus_growth: SpinBox
var job_xp_base: SpinBox
var job_xp_step: SpinBox
var job_slots: Dictionary = {}
var job_skill_list: ItemList
var job_skill_select: OptionButton
var job_skill_level: SpinBox
var job_res_list: ItemList
var job_res_type: LineEdit
var job_res_percent: SpinBox
var job_power_skill: OptionButton
var job_power_bonus: SpinBox
var job_guard_skill: OptionButton
var job_validation: Label

var equipment_select: OptionButton
var equipment_current: Resource
var equipment_path := ""
var equipment_name: LineEdit
var equipment_desc: TextEdit
var equipment_slot: OptionButton
var equipment_hp: SpinBox
var equipment_attack: SpinBox
var equipment_move: SpinBox
var equipment_range: SpinBox
var equipment_init: SpinBox
var equipment_focus: SpinBox
var equipment_skill: OptionButton
var equipment_status: OptionButton
var equipment_res_list: ItemList
var equipment_res_type: LineEdit
var equipment_res_percent: SpinBox
var equipment_validation: Label


func _ready() -> void:
	var tabs := TabContainer.new()
	tabs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(tabs)
	_build_jobs_tab(tabs)
	_build_tree_tab(tabs)
	_build_equipment_tab(tabs)

	status_label = Label.new()
	status_label.text = "Jobs et équipements utilisent directement les Resources du runtime."
	status_label.add_theme_color_override("font_color", Color("#8fd9ba"))
	add_child(status_label)
	refresh()


func has_unsaved_data() -> bool:
	return dirty_job or dirty_equipment or (tree_editor != null and tree_editor.has_unsaved_data())


func save_external_data() -> void:
	if dirty_job:
		_save_job()
	if dirty_equipment:
		_save_equipment()
	if tree_editor != null:
		tree_editor.save_external_data()


func refresh() -> void:
	_refresh_jobs()
	_refresh_equipment()
	if tree_editor != null:
		tree_editor.refresh()


func _build_jobs_tab(tabs: TabContainer) -> void:
	var scroll := ScrollContainer.new()
	scroll.name = "Jobs"
	tabs.add_child(scroll)

	var root := VBoxContainer.new()
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(root)

	var toolbar := HBoxContainer.new()
	root.add_child(toolbar)
	job_select = OptionButton.new()
	job_select.custom_minimum_size.x = 280.0
	job_select.item_selected.connect(_on_job_selected)
	toolbar.add_child(job_select)
	_add_button(toolbar, "+ Job", _new_job)
	_add_button(toolbar, "Dupliquer", _duplicate_job)
	_add_button(toolbar, "Enregistrer", _save_job)

	var grid := GridContainer.new()
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_child(grid)
	job_name = _grid_line(grid, "Nom")
	_grid_label(grid, "Description")
	job_desc = TextEdit.new()
	job_desc.custom_minimum_size = Vector2(430.0, 70.0)
	grid.add_child(job_desc)
	_grid_label(grid, "Job parent")
	job_parent = OptionButton.new()
	grid.add_child(job_parent)
	job_unlock_level = _grid_spin(grid, "Niveau requis parent", 1.0, 20.0, 1.0)
	job_next = _grid_line(grid, "Jobs suivants (ids séparés par virgule)")
	job_max_level = _grid_spin(grid, "Niveau max", 1.0, 20.0, 1.0)
	job_xp_base = _grid_spin(grid, "XP niv.2", 1.0, 99.0, 1.0)
	job_xp_step = _grid_spin(grid, "XP + par niveau", 0.0, 99.0, 1.0)

	_separator(root, "Modificateurs de base")
	var stats := GridContainer.new()
	stats.columns = 6
	root.add_child(stats)
	job_hp = _compact_spin(stats, "PV", -30.0, 30.0, 1.0)
	job_attack = _compact_spin(stats, "ATQ", -20.0, 20.0, 1.0)
	job_move = _compact_spin(stats, "MVT", -8.0, 8.0, 1.0)
	job_range = _compact_spin(stats, "POR", -8.0, 8.0, 1.0)
	job_init = _compact_spin(stats, "INIT", -20.0, 20.0, 1.0)
	job_focus = _compact_spin(stats, "FOCUS", -10.0, 10.0, 1.0)

	_separator(root, "Croissance par niveau")
	var growth := GridContainer.new()
	growth.columns = 6
	root.add_child(growth)
	job_hp_growth = _compact_spin(growth, "PV/niv", 0.0, 5.0, 0.05)
	job_attack_growth = _compact_spin(growth, "ATQ/niv", 0.0, 2.0, 0.05)
	job_move_growth = _compact_spin(growth, "MVT/niv", 0.0, 1.0, 0.05)
	job_range_growth = _compact_spin(growth, "POR/niv", 0.0, 1.0, 0.05)
	job_init_growth = _compact_spin(growth, "INIT/niv", 0.0, 2.0, 0.05)
	job_focus_growth = _compact_spin(growth, "FOCUS/niv", 0.0, 1.0, 0.05)

	_separator(root, "Slots autorisés")
	var slot_row := HBoxContainer.new()
	root.add_child(slot_row)
	for slot in SLOTS:
		var check := CheckBox.new()
		check.text = slot
		slot_row.add_child(check)
		job_slots[slot] = check

	_separator(root, "Déblocages de compétences (fallback si arbre vide)")
	job_skill_list = ItemList.new()
	job_skill_list.custom_minimum_size.y = 130.0
	root.add_child(job_skill_list)
	var skill_row := HBoxContainer.new()
	root.add_child(skill_row)
	job_skill_select = OptionButton.new()
	job_skill_select.custom_minimum_size.x = 260.0
	skill_row.add_child(job_skill_select)
	job_skill_level = _compact_spin(skill_row, "Niveau", 1.0, 20.0, 1.0)
	_add_button(skill_row, "+", _add_job_skill)
	_add_button(skill_row, "Supprimer", _remove_job_skill)

	_separator(root, "Résistances")
	job_res_list = ItemList.new()
	job_res_list.custom_minimum_size.y = 105.0
	root.add_child(job_res_list)
	var res_row := HBoxContainer.new()
	root.add_child(res_row)
	job_res_type = LineEdit.new()
	job_res_type.placeholder_text = "physical / spore / fire..."
	job_res_type.custom_minimum_size.x = 230.0
	res_row.add_child(job_res_type)
	job_res_percent = _compact_spin(res_row, "%", -100.0, 100.0, 5.0)
	_add_button(res_row, "+", _add_job_resistance)
	_add_button(res_row, "Supprimer", _remove_job_resistance)

	_separator(root, "Passifs de job")
	var passives := GridContainer.new()
	passives.columns = 2
	root.add_child(passives)
	_grid_label(passives, "Bonus puissance sur skill")
	job_power_skill = OptionButton.new()
	passives.add_child(job_power_skill)
	job_power_bonus = _grid_spin(passives, "Bonus numérique", -10.0, 10.0, 1.0)
	_grid_label(passives, "GARDE après skill")
	job_guard_skill = OptionButton.new()
	passives.add_child(job_guard_skill)

	job_validation = Label.new()
	job_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(job_validation)


func _build_tree_tab(tabs: TabContainer) -> void:
	tree_editor = ProgressionTreeEditor.new()
	tree_editor.name = "Skill Tree"
	tree_editor.library_changed.connect(_on_tree_library_changed)
	tabs.add_child(tree_editor)


func _on_tree_library_changed() -> void:
	_refresh_jobs()
	library_changed.emit()


func _build_equipment_tab(tabs: TabContainer) -> void:
	var scroll := ScrollContainer.new()
	scroll.name = "Equipment"
	tabs.add_child(scroll)

	var root := VBoxContainer.new()
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(root)

	var toolbar := HBoxContainer.new()
	root.add_child(toolbar)
	equipment_select = OptionButton.new()
	equipment_select.custom_minimum_size.x = 300.0
	equipment_select.item_selected.connect(_on_equipment_selected)
	toolbar.add_child(equipment_select)
	_add_button(toolbar, "+ Équipement", _new_equipment)
	_add_button(toolbar, "Dupliquer", _duplicate_equipment)
	_add_button(toolbar, "Enregistrer", _save_equipment)

	var grid := GridContainer.new()
	grid.columns = 2
	root.add_child(grid)
	equipment_name = _grid_line(grid, "Nom")
	_grid_label(grid, "Description")
	equipment_desc = TextEdit.new()
	equipment_desc.custom_minimum_size = Vector2(430.0, 70.0)
	grid.add_child(equipment_desc)
	_grid_label(grid, "Slot")
	equipment_slot = OptionButton.new()
	for slot in SLOTS:
		equipment_slot.add_item(slot)
	grid.add_child(equipment_slot)
	equipment_hp = _grid_spin(grid, "PV", -30.0, 30.0, 1.0)
	equipment_attack = _grid_spin(grid, "ATQ", -20.0, 20.0, 1.0)
	equipment_move = _grid_spin(grid, "MVT", -8.0, 8.0, 1.0)
	equipment_range = _grid_spin(grid, "Portée", -8.0, 8.0, 1.0)
	equipment_init = _grid_spin(grid, "Initiative", -20.0, 20.0, 1.0)
	equipment_focus = _grid_spin(grid, "Focus", -10.0, 10.0, 1.0)
	_grid_label(grid, "Compétence accordée")
	equipment_skill = OptionButton.new()
	grid.add_child(equipment_skill)
	_grid_label(grid, "Statut au déploiement")
	equipment_status = OptionButton.new()
	grid.add_child(equipment_status)

	_separator(root, "Résistances")
	equipment_res_list = ItemList.new()
	equipment_res_list.custom_minimum_size.y = 120.0
	root.add_child(equipment_res_list)
	var res_row := HBoxContainer.new()
	root.add_child(res_row)
	equipment_res_type = LineEdit.new()
	equipment_res_type.placeholder_text = "physical / spore / fire..."
	equipment_res_type.custom_minimum_size.x = 230.0
	res_row.add_child(equipment_res_type)
	equipment_res_percent = _compact_spin(res_row, "%", -100.0, 100.0, 5.0)
	_add_button(res_row, "+", _add_equipment_resistance)
	_add_button(res_row, "Supprimer", _remove_equipment_resistance)

	equipment_validation = Label.new()
	equipment_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(equipment_validation)


func _refresh_jobs() -> void:
	var wanted := job_path
	job_select.clear()
	for path in _resource_files(JOB_DIR):
		var data := load(path)
		job_select.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		job_select.set_item_metadata(job_select.item_count - 1, path)
	_refresh_job_selectors()
	if job_select.item_count > 0:
		var index := _metadata_index(job_select, wanted)
		if index < 0:
			index = 0
		job_select.select(index)
		_on_job_selected(index)


func _refresh_equipment() -> void:
	var wanted := equipment_path
	equipment_select.clear()
	for path in _resource_files(EQUIPMENT_DIR):
		var data := load(path)
		equipment_select.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		equipment_select.set_item_metadata(equipment_select.item_count - 1, path)
	_refresh_skill_option(equipment_skill, true)
	_refresh_status_option(equipment_status, true)
	if equipment_select.item_count > 0:
		var index := _metadata_index(equipment_select, wanted)
		if index < 0:
			index = 0
		equipment_select.select(index)
		_on_equipment_selected(index)


func _refresh_job_selectors() -> void:
	var wanted_parent := _selected_meta(job_parent)
	job_parent.clear()
	job_parent.add_item("— aucun / job initial —")
	job_parent.set_item_metadata(0, "")
	for path in _resource_files(JOB_DIR):
		var data := load(path)
		job_parent.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		job_parent.set_item_metadata(job_parent.item_count - 1, String(data.id))
	_select_metadata(job_parent, wanted_parent)
	_refresh_skill_option(job_skill_select, false)
	_refresh_skill_option(job_power_skill, true)
	_refresh_skill_option(job_guard_skill, true)


func _refresh_skill_option(option: OptionButton, allow_none: bool) -> void:
	if option == null:
		return
	var wanted := _selected_meta(option)
	option.clear()
	if allow_none:
		option.add_item("— aucune —")
		option.set_item_metadata(0, "")
	for path in _resource_files(SKILL_DIR):
		var data := load(path)
		option.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		option.set_item_metadata(option.item_count - 1, String(data.id))
	_select_metadata(option, wanted)


func _refresh_status_option(option: OptionButton, allow_none: bool) -> void:
	if option == null:
		return
	var wanted := _selected_meta(option)
	option.clear()
	if allow_none:
		option.add_item("— aucun —")
		option.set_item_metadata(0, "")
	for path in _resource_files(STATUS_DIR):
		var data := load(path)
		option.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		option.set_item_metadata(option.item_count - 1, String(data.id))
	_select_metadata(option, wanted)


func _on_job_selected(index: int) -> void:
	if index < 0 or index >= job_select.item_count:
		return
	job_path = String(job_select.get_item_metadata(index))
	job_current = load(job_path)
	job_name.text = String(job_current.display_name)
	job_desc.text = String(job_current.description)
	_select_metadata(job_parent, String(job_current.unlock_from_job_id))
	job_unlock_level.value = int(job_current.unlock_level)
	var next_parts: Array[String] = []
	for next_id in job_current.next_job_ids:
		next_parts.append(String(next_id))
	job_next.text = ", ".join(next_parts)
	job_max_level.value = int(job_current.max_level)
	job_hp.value = int(job_current.hp_bonus)
	job_attack.value = int(job_current.attack_bonus)
	job_move.value = int(job_current.movement_bonus)
	job_range.value = int(job_current.range_bonus)
	job_init.value = int(job_current.initiative_bonus)
	job_focus.value = int(job_current.focus_bonus)
	job_hp_growth.value = float(job_current.hp_growth)
	job_attack_growth.value = float(job_current.attack_growth)
	job_move_growth.value = float(job_current.movement_growth)
	job_range_growth.value = float(job_current.range_growth)
	job_init_growth.value = float(job_current.initiative_growth)
	job_focus_growth.value = float(job_current.focus_growth)
	job_xp_base.value = int(job_current.xp_base)
	job_xp_step.value = int(job_current.xp_step)
	for slot in SLOTS:
		var check: CheckBox = job_slots[slot]
		check.button_pressed = job_current.allowed_slots.has(slot)
	_select_metadata(job_power_skill, String(job_current.skill_power_skill_id))
	job_power_bonus.value = int(job_current.skill_power_bonus)
	_select_metadata(job_guard_skill, String(job_current.guard_after_skill_id))
	_refresh_job_skill_list()
	_refresh_job_res_list()
	_validate_job()


func _write_job_fields() -> void:
	if job_current == null:
		return
	job_current.display_name = job_name.text.strip_edges()
	job_current.description = job_desc.text.strip_edges()
	job_current.unlock_from_job_id = _selected_meta(job_parent)
	job_current.unlock_level = int(job_unlock_level.value)
	var next_ids := PackedStringArray()
	for token in job_next.text.split(","):
		var clean := token.strip_edges()
		if not clean.is_empty():
			next_ids.append(clean)
	job_current.next_job_ids = next_ids
	job_current.max_level = int(job_max_level.value)
	job_current.hp_bonus = int(job_hp.value)
	job_current.attack_bonus = int(job_attack.value)
	job_current.movement_bonus = int(job_move.value)
	job_current.range_bonus = int(job_range.value)
	job_current.initiative_bonus = int(job_init.value)
	job_current.focus_bonus = int(job_focus.value)
	job_current.hp_growth = float(job_hp_growth.value)
	job_current.attack_growth = float(job_attack_growth.value)
	job_current.movement_growth = float(job_move_growth.value)
	job_current.range_growth = float(job_range_growth.value)
	job_current.initiative_growth = float(job_init_growth.value)
	job_current.focus_growth = float(job_focus_growth.value)
	job_current.xp_base = int(job_xp_base.value)
	job_current.xp_step = int(job_xp_step.value)
	var allowed := PackedStringArray()
	for slot in SLOTS:
		var check: CheckBox = job_slots[slot]
		if check.button_pressed:
			allowed.append(slot)
	job_current.allowed_slots = allowed
	job_current.skill_power_skill_id = _selected_meta(job_power_skill)
	job_current.skill_power_bonus = int(job_power_bonus.value)
	job_current.guard_after_skill_id = _selected_meta(job_guard_skill)


func _save_job() -> void:
	if job_current == null:
		return
	_write_job_fields()
	var error := ResourceSaver.save(job_current, job_path)
	dirty_job = false
	status_label.text = "✓ Job enregistré : %s" % job_path if error == OK else "⚠ Erreur job : %s" % error
	_validate_job()
	library_changed.emit()


func _new_job() -> void:
	var new_id := _unique_id(JOB_DIR, "new_job")
	var data: Resource = JobDefinition.new()
	data.id = new_id
	data.display_name = "Nouveau job"
	var path := JOB_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	job_path = path
	_rescan()
	_refresh_jobs()
	library_changed.emit()


func _duplicate_job() -> void:
	if job_current == null:
		return
	var new_id := _unique_id(JOB_DIR, String(job_current.id) + "_copy")
	var data: Resource = job_current.duplicate(true)
	data.id = new_id
	data.display_name = String(job_current.display_name) + " Copie"
	var path := JOB_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	job_path = path
	_rescan()
	_refresh_jobs()
	library_changed.emit()


func _refresh_job_skill_list() -> void:
	job_skill_list.clear()
	if job_current == null:
		return
	for item in job_current.skill_unlocks:
		if item != null:
			job_skill_list.add_item(item.summary())


func _add_job_skill() -> void:
	if job_current == null or job_skill_select.item_count == 0:
		return
	var item: Resource = JobSkillUnlock.new()
	item.skill_id = _selected_meta(job_skill_select)
	item.required_level = int(job_skill_level.value)
	job_current.skill_unlocks.append(item)
	dirty_job = true
	_refresh_job_skill_list()


func _remove_job_skill() -> void:
	if job_current == null or job_skill_list.get_selected_items().is_empty():
		return
	var index := int(job_skill_list.get_selected_items()[0])
	job_current.skill_unlocks.remove_at(index)
	dirty_job = true
	_refresh_job_skill_list()


func _refresh_job_res_list() -> void:
	job_res_list.clear()
	if job_current == null:
		return
	for item in job_current.resistances:
		if item != null:
			job_res_list.add_item(item.summary())


func _add_job_resistance() -> void:
	if job_current == null or job_res_type.text.strip_edges().is_empty():
		return
	var item: Resource = ResistanceEntry.new()
	item.damage_type = job_res_type.text.strip_edges()
	item.percent = int(job_res_percent.value)
	job_current.resistances.append(item)
	dirty_job = true
	_refresh_job_res_list()


func _remove_job_resistance() -> void:
	if job_current == null or job_res_list.get_selected_items().is_empty():
		return
	var index := int(job_res_list.get_selected_items()[0])
	job_current.resistances.remove_at(index)
	dirty_job = true
	_refresh_job_res_list()


func _validate_job() -> void:
	if job_current == null:
		return
	var issues: Array[String] = []
	if not String(job_current.unlock_from_job_id).is_empty():
		if not ResourceLoader.exists(JOB_DIR + String(job_current.unlock_from_job_id) + ".tres"):
			issues.append("Job parent inconnu")
	for item in job_current.skill_unlocks:
		if item != null and not ResourceLoader.exists(SKILL_DIR + String(item.skill_id) + ".tres"):
			issues.append("Skill inconnu : %s" % item.skill_id)
	job_validation.text = "✓ Job valide." if issues.is_empty() else "⚠ " + " • ".join(issues)
	job_validation.add_theme_color_override("font_color", Color("#8fe0ad") if issues.is_empty() else Color("#ffb36b"))


func _on_equipment_selected(index: int) -> void:
	if index < 0 or index >= equipment_select.item_count:
		return
	equipment_path = String(equipment_select.get_item_metadata(index))
	equipment_current = load(equipment_path)
	equipment_name.text = String(equipment_current.display_name)
	equipment_desc.text = String(equipment_current.description)
	_select_text(equipment_slot, String(equipment_current.slot))
	equipment_hp.value = int(equipment_current.hp_bonus)
	equipment_attack.value = int(equipment_current.attack_bonus)
	equipment_move.value = int(equipment_current.movement_bonus)
	equipment_range.value = int(equipment_current.range_bonus)
	equipment_init.value = int(equipment_current.initiative_bonus)
	equipment_focus.value = int(equipment_current.focus_bonus)
	_select_metadata(equipment_skill, String(equipment_current.granted_skill_id))
	_select_metadata(equipment_status, String(equipment_current.start_status_id))
	_refresh_equipment_res_list()
	_validate_equipment()


func _write_equipment_fields() -> void:
	if equipment_current == null:
		return
	equipment_current.display_name = equipment_name.text.strip_edges()
	equipment_current.description = equipment_desc.text.strip_edges()
	equipment_current.slot = equipment_slot.get_item_text(equipment_slot.selected)
	equipment_current.hp_bonus = int(equipment_hp.value)
	equipment_current.attack_bonus = int(equipment_attack.value)
	equipment_current.movement_bonus = int(equipment_move.value)
	equipment_current.range_bonus = int(equipment_range.value)
	equipment_current.initiative_bonus = int(equipment_init.value)
	equipment_current.focus_bonus = int(equipment_focus.value)
	equipment_current.granted_skill_id = _selected_meta(equipment_skill)
	equipment_current.start_status_id = _selected_meta(equipment_status)


func _save_equipment() -> void:
	if equipment_current == null:
		return
	_write_equipment_fields()
	var error := ResourceSaver.save(equipment_current, equipment_path)
	dirty_equipment = false
	status_label.text = "✓ Équipement enregistré : %s" % equipment_path if error == OK else "⚠ Erreur équipement : %s" % error
	_validate_equipment()
	library_changed.emit()


func _new_equipment() -> void:
	var new_id := _unique_id(EQUIPMENT_DIR, "new_equipment")
	var data: Resource = EquipmentDefinition.new()
	data.id = new_id
	data.display_name = "Nouvel équipement"
	var path := EQUIPMENT_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	equipment_path = path
	_rescan()
	_refresh_equipment()
	library_changed.emit()


func _duplicate_equipment() -> void:
	if equipment_current == null:
		return
	var new_id := _unique_id(EQUIPMENT_DIR, String(equipment_current.id) + "_copy")
	var data: Resource = equipment_current.duplicate(true)
	data.id = new_id
	data.display_name = String(equipment_current.display_name) + " Copie"
	var path := EQUIPMENT_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	equipment_path = path
	_rescan()
	_refresh_equipment()
	library_changed.emit()


func _refresh_equipment_res_list() -> void:
	equipment_res_list.clear()
	if equipment_current == null:
		return
	for item in equipment_current.resistances:
		if item != null:
			equipment_res_list.add_item(item.summary())


func _add_equipment_resistance() -> void:
	if equipment_current == null or equipment_res_type.text.strip_edges().is_empty():
		return
	var item: Resource = ResistanceEntry.new()
	item.damage_type = equipment_res_type.text.strip_edges()
	item.percent = int(equipment_res_percent.value)
	equipment_current.resistances.append(item)
	dirty_equipment = true
	_refresh_equipment_res_list()


func _remove_equipment_resistance() -> void:
	if equipment_current == null or equipment_res_list.get_selected_items().is_empty():
		return
	var index := int(equipment_res_list.get_selected_items()[0])
	equipment_current.resistances.remove_at(index)
	dirty_equipment = true
	_refresh_equipment_res_list()


func _validate_equipment() -> void:
	if equipment_current == null:
		return
	var issues: Array[String] = []
	if not String(equipment_current.granted_skill_id).is_empty():
		if not ResourceLoader.exists(SKILL_DIR + String(equipment_current.granted_skill_id) + ".tres"):
			issues.append("Skill inconnu")
	if not String(equipment_current.start_status_id).is_empty():
		if not ResourceLoader.exists(STATUS_DIR + String(equipment_current.start_status_id) + ".tres"):
			issues.append("Statut inconnu")
	equipment_validation.text = "✓ Équipement valide." if issues.is_empty() else "⚠ " + " • ".join(issues)
	equipment_validation.add_theme_color_override("font_color", Color("#8fe0ad") if issues.is_empty() else Color("#ffb36b"))


func _resource_files(dir_path: String) -> PackedStringArray:
	var result := PackedStringArray()
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(dir_path + file_name)
	result.sort()
	return result


func _unique_id(dir_path: String, base: String) -> String:
	var candidate := base
	var suffix := 2
	while ResourceLoader.exists(dir_path + candidate + ".tres"):
		candidate = "%s_%d" % [base, suffix]
		suffix += 1
	return candidate


func _metadata_index(option: OptionButton, wanted: Variant) -> int:
	for index in range(option.item_count):
		if option.get_item_metadata(index) == wanted:
			return index
	return -1


func _selected_meta(option: OptionButton) -> String:
	if option == null or option.item_count == 0:
		return ""
	return String(option.get_item_metadata(option.selected))


func _select_metadata(option: OptionButton, value: String) -> void:
	if option == null:
		return
	var index := _metadata_index(option, value)
	option.select(max(0, index))


func _select_text(option: OptionButton, value: String) -> void:
	if option == null:
		return
	for index in range(option.item_count):
		if option.get_item_text(index) == value:
			option.select(index)
			return


func _grid_label(grid: GridContainer, text: String) -> void:
	var label := Label.new()
	label.text = text
	grid.add_child(label)


func _grid_line(grid: GridContainer, label_text: String) -> LineEdit:
	_grid_label(grid, label_text)
	var edit := LineEdit.new()
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_child(edit)
	return edit


func _grid_spin(grid: GridContainer, label_text: String, min_value: float, max_value: float, step: float) -> SpinBox:
	_grid_label(grid, label_text)
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = step
	spin.allow_greater = true
	spin.allow_lesser = true
	grid.add_child(spin)
	return spin


func _compact_spin(parent: Control, label_text: String, min_value: float, max_value: float, step: float) -> SpinBox:
	var box := VBoxContainer.new()
	parent.add_child(box)
	var label := Label.new()
	label.text = label_text
	box.add_child(label)
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = step
	spin.allow_greater = true
	spin.allow_lesser = true
	spin.custom_minimum_size.x = 90.0
	box.add_child(spin)
	return spin


func _separator(parent: Control, text: String) -> void:
	var label := Label.new()
	label.text = "── %s ──" % text
	label.add_theme_color_override("font_color", Color("#ffd166"))
	parent.add_child(label)


func _add_button(parent: Control, text: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(callback)
	parent.add_child(button)
	return button


func _rescan() -> void:
	if Engine.is_editor_hint():
		EditorInterface.get_resource_filesystem().scan()
