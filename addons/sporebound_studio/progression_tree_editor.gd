@tool
class_name SporeProgressionTreeEditor
extends VBoxContainer

signal library_changed

const ProgressionNode = preload("res://scripts/data/progression_node_definition.gd")
const TreeCanvas = preload("res://scripts/ui/progression_tree_canvas.gd")

const JOB_DIR := "res://data/jobs/"
const SKILL_DIR := "res://data/skills/"

var dirty := false
var current_job: SporeJobDefinition
var current_path := ""
var selected_node_id := ""

var job_select: OptionButton
var start_points: SpinBox
var points_per_level: SpinBox
var canvas: SporeProgressionTreeCanvas
var validation_label: Label
var status_label: Label

var node_id: LineEdit
var node_name: LineEdit
var node_desc: TextEdit
var node_type: OptionButton
var node_cost: SpinBox
var node_level: SpinBox
var node_auto: CheckBox
var node_requirements: LineEdit
var node_exclusive: LineEdit
var node_skill: OptionButton
var node_stat: OptionButton
var node_stat_value: SpinBox
var node_passive: OptionButton
var node_passive_target: LineEdit
var node_passive_value: SpinBox


func _ready() -> void:
	_build_ui()
	refresh()


func has_unsaved_data() -> bool:
	return dirty


func save_external_data() -> void:
	if dirty:
		_save_job()


func refresh() -> void:
	var wanted := current_path
	job_select.clear()
	for path in _resource_files(JOB_DIR):
		var data := load(path)
		job_select.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		job_select.set_item_metadata(job_select.item_count - 1, path)
	_refresh_skill_selector()
	if job_select.item_count > 0:
		var index := _metadata_index(job_select, wanted)
		job_select.select(0 if index < 0 else index)
		_on_job_selected(job_select.selected)


func _build_ui() -> void:
	var toolbar := HBoxContainer.new()
	add_child(toolbar)
	job_select = OptionButton.new()
	job_select.custom_minimum_size.x = 290.0
	job_select.item_selected.connect(_on_job_selected)
	toolbar.add_child(job_select)
	_add_button(toolbar, "+ Nœud", _new_node)
	_add_button(toolbar, "Dupliquer", _duplicate_node)
	_add_button(toolbar, "Supprimer", _delete_node)
	_add_button(toolbar, "Enregistrer arbre", _save_job)

	var points_row := HBoxContainer.new()
	add_child(points_row)
	var point_label := Label.new()
	point_label.text = "Points :"
	points_row.add_child(point_label)
	start_points = _compact_spin(points_row, "Départ", 0.0, 9.0, 1.0)
	points_per_level = _compact_spin(points_row, "/ niveau", 0.0, 9.0, 1.0)
	var help := Label.new()
	help.text = "Les nœuds AUTO ne coûtent rien au joueur. Les groupes exclusifs créent des choix de branche."
	help.add_theme_color_override("font_color", Color("#a9bdd0"))
	points_row.add_child(help)

	var split := HSplitContainer.new()
	split.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(split)

	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size.x = 760.0
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.add_child(scroll)
	canvas = TreeCanvas.new()
	canvas.editable_positions = true
	canvas.node_selected.connect(_on_node_selected)
	canvas.node_moved.connect(_on_node_moved)
	scroll.add_child(canvas)

	var inspector_scroll := ScrollContainer.new()
	inspector_scroll.custom_minimum_size.x = 350.0
	inspector_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.add_child(inspector_scroll)
	var inspector := VBoxContainer.new()
	inspector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inspector_scroll.add_child(inspector)

	var grid := GridContainer.new()
	grid.columns = 2
	inspector.add_child(grid)
	node_id = _grid_line(grid, "ID")
	node_name = _grid_line(grid, "Nom")
	_grid_label(grid, "Description")
	node_desc = TextEdit.new()
	node_desc.custom_minimum_size = Vector2(240.0, 66.0)
	grid.add_child(node_desc)
	_grid_label(grid, "Type")
	node_type = OptionButton.new()
	for value in ["skill", "stat", "passive"]:
		node_type.add_item(value)
	grid.add_child(node_type)
	node_cost = _grid_spin(grid, "Coût points", 0.0, 9.0, 1.0)
	node_level = _grid_spin(grid, "Niveau job requis", 1.0, 20.0, 1.0)
	_grid_label(grid, "Auto-débloqué")
	node_auto = CheckBox.new()
	grid.add_child(node_auto)
	node_requirements = _grid_line(grid, "Prérequis (ids, virgule)")
	node_exclusive = _grid_line(grid, "Groupe exclusif")
	_grid_label(grid, "Compétence")
	node_skill = OptionButton.new()
	grid.add_child(node_skill)
	_grid_label(grid, "Stat")
	node_stat = OptionButton.new()
	for value in ["hp", "attack", "movement", "range", "initiative", "focus"]:
		node_stat.add_item(value)
	grid.add_child(node_stat)
	node_stat_value = _grid_spin(grid, "Valeur stat", -20.0, 20.0, 1.0)
	_grid_label(grid, "Passif")
	node_passive = OptionButton.new()
	for value in ["skill_power", "resistance", "guard_after_skill", "focus_regen"]:
		node_passive.add_item(value)
	grid.add_child(node_passive)
	node_passive_target = _grid_line(grid, "Cible passif (skill/type)")
	node_passive_value = _grid_spin(grid, "Valeur passif", -100.0, 100.0, 1.0)

	_add_button(inspector, "Appliquer au nœud", _apply_node_fields)
	validation_label = Label.new()
	validation_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inspector.add_child(validation_label)

	status_label = Label.new()
	status_label.text = "Glisse les cartes pour organiser visuellement l’arbre."
	status_label.add_theme_color_override("font_color", Color("#8fd9ba"))
	add_child(status_label)


func _on_job_selected(index: int) -> void:
	if index < 0 or index >= job_select.item_count:
		return
	current_path = String(job_select.get_item_metadata(index))
	current_job = load(current_path) as SporeJobDefinition
	selected_node_id = ""
	start_points.value = int(current_job.starting_tree_points)
	points_per_level.value = int(current_job.tree_points_per_level)
	canvas.set_job(current_job)
	_clear_node_fields()
	_validate_tree()


func _new_node() -> void:
	if current_job == null:
		return
	var node: SporeProgressionNodeDefinition = ProgressionNode.new()
	node.id = _unique_node_id("node")
	node.display_name = "Nouveau nœud"
	node.editor_position = Vector2(60.0 + float(current_job.progression_nodes.size() % 4) * 230.0, 60.0 + float(current_job.progression_nodes.size() / 4) * 120.0)
	current_job.progression_nodes.append(node)
	dirty = true
	canvas.set_job(current_job)
	_on_node_selected(String(node.id))


func _duplicate_node() -> void:
	var node: SporeProgressionNodeDefinition = _selected_node()
	if node == null or current_job == null:
		return
	var copy: SporeProgressionNodeDefinition = node.duplicate(true) as SporeProgressionNodeDefinition
	copy.id = _unique_node_id(String(node.id) + "_copy")
	copy.display_name = String(node.display_name) + " Copie"
	copy.editor_position = node.editor_position + Vector2(40.0, 110.0)
	copy.auto_unlock = false
	current_job.progression_nodes.append(copy)
	dirty = true
	canvas.set_job(current_job)
	_on_node_selected(String(copy.id))


func _delete_node() -> void:
	var node: SporeProgressionNodeDefinition = _selected_node()
	if node == null or current_job == null:
		return
	var removed_id := String(node.id)
	current_job.progression_nodes.erase(node)
	for other in current_job.progression_nodes:
		if other == null:
			continue
		var req := PackedStringArray()
		for required_id in other.required_node_ids:
			if String(required_id) != removed_id:
				req.append(String(required_id))
		other.required_node_ids = req
	selected_node_id = ""
	dirty = true
	canvas.set_job(current_job)
	_clear_node_fields()
	_validate_tree()


func _on_node_selected(node_id_value: String) -> void:
	selected_node_id = node_id_value
	canvas.set_selected_node(node_id_value)
	var node: SporeProgressionNodeDefinition = _selected_node()
	if node == null:
		return
	node_id.text = String(node.id)
	node_name.text = String(node.display_name)
	node_desc.text = String(node.description)
	_select_text(node_type, String(node.node_type))
	node_cost.value = int(node.cost)
	node_level.value = int(node.required_level)
	node_auto.button_pressed = bool(node.auto_unlock)
	var req_parts: Array[String] = []
	for required_id in node.required_node_ids:
		req_parts.append(String(required_id))
	node_requirements.text = ", ".join(req_parts)
	node_exclusive.text = String(node.exclusive_group)
	_select_metadata(node_skill, String(node.skill_id))
	_select_text(node_stat, String(node.stat_type))
	node_stat_value.value = int(node.stat_value)
	_select_text(node_passive, String(node.passive_type))
	node_passive_target.text = String(node.passive_target)
	node_passive_value.value = int(node.passive_value)


func _apply_node_fields() -> void:
	var node: SporeProgressionNodeDefinition = _selected_node()
	if node == null or current_job == null:
		return
	var old_id := String(node.id)
	var new_id := _slug(node_id.text)
	if new_id.is_empty():
		new_id = old_id
	if new_id != old_id and current_job.progression_node_by_id(new_id) != null:
		status_label.text = "⚠ ID déjà utilisé : %s" % new_id
		return
	if new_id != old_id:
		for other in current_job.progression_nodes:
			if other == null or other == node:
				continue
			var req := PackedStringArray()
			for required_id in other.required_node_ids:
				req.append(new_id if String(required_id) == old_id else String(required_id))
			other.required_node_ids = req
		node.id = new_id
		selected_node_id = new_id
	node.display_name = node_name.text.strip_edges()
	node.description = node_desc.text.strip_edges()
	node.node_type = node_type.get_item_text(node_type.selected)
	node.cost = int(node_cost.value)
	node.required_level = int(node_level.value)
	node.auto_unlock = node_auto.button_pressed
	var req_ids := PackedStringArray()
	for token in node_requirements.text.split(","):
		var clean := _slug(token)
		if not clean.is_empty() and clean != String(node.id) and not req_ids.has(clean):
			req_ids.append(clean)
	node.required_node_ids = req_ids
	node.exclusive_group = _slug(node_exclusive.text)
	node.skill_id = _selected_meta(node_skill)
	node.stat_type = node_stat.get_item_text(node_stat.selected)
	node.stat_value = int(node_stat_value.value)
	node.passive_type = node_passive.get_item_text(node_passive.selected)
	node.passive_target = node_passive_target.text.strip_edges()
	node.passive_value = int(node_passive_value.value)
	dirty = true
	canvas.set_job(current_job)
	canvas.set_selected_node(selected_node_id)
	_validate_tree()


func _on_node_moved(_node_id_value: String, _position: Vector2) -> void:
	dirty = true


func _save_job() -> void:
	if current_job == null or current_path.is_empty():
		return
	if not selected_node_id.is_empty():
		_apply_node_fields()
	current_job.starting_tree_points = int(start_points.value)
	current_job.tree_points_per_level = int(points_per_level.value)
	var error: Error = ResourceSaver.save(current_job, current_path)
	if error == OK:
		dirty = false
		status_label.text = "✓ Arbre enregistré : %s" % current_path
		library_changed.emit()
	else:
		status_label.text = "⚠ Erreur ResourceSaver : %s" % error
	_validate_tree()


func _validate_tree() -> void:
	if current_job == null:
		return
	var issues: Array[String] = []
	var ids: Dictionary = {}
	for node in current_job.progression_nodes:
		if node == null:
			issues.append("Nœud null")
			continue
		var id := String(node.id)
		if id.is_empty():
			issues.append("ID de nœud vide")
		elif ids.has(id):
			issues.append("ID dupliqué : %s" % id)
		ids[id] = true
		if String(node.node_type) == "skill" and not String(node.skill_id).is_empty() and not ResourceLoader.exists(SKILL_DIR + String(node.skill_id) + ".tres"):
			issues.append("Skill inconnu : %s" % String(node.skill_id))
	for node in current_job.progression_nodes:
		if node == null:
			continue
		for required_id in node.required_node_ids:
			if not ids.has(String(required_id)):
				issues.append("%s → prérequis inconnu %s" % [String(node.id), String(required_id)])
	if _has_cycle():
		issues.append("Cycle détecté dans les prérequis")
	validation_label.text = "✓ Arbre valide • %d nœuds" % current_job.progression_nodes.size() if issues.is_empty() else "⚠ " + " • ".join(issues)
	validation_label.add_theme_color_override("font_color", Color("#8fe0ad") if issues.is_empty() else Color("#ffb36b"))


func _has_cycle() -> bool:
	if current_job == null:
		return false
	var visiting: Dictionary = {}
	var visited: Dictionary = {}
	for node in current_job.progression_nodes:
		if node != null and _cycle_visit(String(node.id), visiting, visited):
			return true
	return false


func _cycle_visit(node_id_value: String, visiting: Dictionary, visited: Dictionary) -> bool:
	if visited.has(node_id_value):
		return false
	if visiting.has(node_id_value):
		return true
	visiting[node_id_value] = true
	var node: SporeProgressionNodeDefinition = current_job.progression_node_by_id(node_id_value)
	if node != null:
		for required_id in node.required_node_ids:
			if _cycle_visit(String(required_id), visiting, visited):
				return true
	visiting.erase(node_id_value)
	visited[node_id_value] = true
	return false


func _selected_node() -> SporeProgressionNodeDefinition:
	return current_job.progression_node_by_id(selected_node_id) if current_job != null and not selected_node_id.is_empty() else null


func _clear_node_fields() -> void:
	for edit in [node_id, node_name, node_requirements, node_exclusive, node_passive_target]:
		if edit != null:
			edit.text = ""
	if node_desc != null:
		node_desc.text = ""


func _refresh_skill_selector() -> void:
	if node_skill == null:
		return
	var wanted := _selected_meta(node_skill)
	node_skill.clear()
	node_skill.add_item("— aucune —")
	node_skill.set_item_metadata(0, "")
	for path in _resource_files(SKILL_DIR):
		var data := load(path)
		node_skill.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		node_skill.set_item_metadata(node_skill.item_count - 1, String(data.id))
	_select_metadata(node_skill, wanted)


func _unique_node_id(base: String) -> String:
	var clean := _slug(base)
	if clean.is_empty():
		clean = "node"
	var candidate := clean
	var suffix := 2
	while current_job != null and current_job.progression_node_by_id(candidate) != null:
		candidate = "%s_%d" % [clean, suffix]
		suffix += 1
	return candidate


func _slug(value: String) -> String:
	return value.strip_edges().to_lower().replace(" ", "_").replace("-", "_")


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
	option.select(maxi(0, index))


func _select_text(option: OptionButton, value: String) -> void:
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
	spin.custom_minimum_size.x = 80.0
	box.add_child(spin)
	return spin


func _add_button(parent: Control, text: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(callback)
	parent.add_child(button)
	return button
