@tool
class_name SporeNativeMapEditor
extends RefCounted

const Map2DScript = preload("res://scripts/maps/spore_map_2d.gd")
const HeroSpawnScript = preload("res://scripts/maps/spore_hero_spawn_2d.gd")
const EnemySpawnScript = preload("res://scripts/maps/spore_enemy_spawn_2d.gd")
const InteractableScript = preload("res://scripts/maps/spore_map_interactable_2d.gd")
const ZoneScript = preload("res://scripts/maps/spore_map_zone_2d.gd")

const TOOL_ITEMS: Array[Array] = [
	["Sol", "ground"],
	["Obstacle", "obstacle"],
	["Couverture", "cover"],
	["Spores", "hazard"],
	["Extraction", "extraction"],
	["Bonus", "bonus"],
	["Couronne", "crown"],
	["Hauteur 0", "height0"],
	["Hauteur 1", "height1"],
	["Hauteur 2", "height2"],
	["Spawn héros", "hero"],
	["Spawn ennemi", "enemy"],
	["Porte", "door"],
	["Interrupteur", "switch"],
	["Coffre", "chest"],
	["Zone", "zone"],
	["Gomme", "erase"],
]

var plugin: EditorPlugin
var toolbar: HBoxContainer
var paint_toggle: CheckButton
var tool_select: OptionButton
var enemy_select: OptionButton
var tactical_preview_toggle: CheckButton
var validation_overlay_toggle: CheckButton
var status_label: Label
var current_map: SporeMap2D
var hover_cell: Vector2i = Vector2i(-999, -999)
var mouse_down: bool = false
var last_painted_cell: Vector2i = Vector2i(-999, -999)


func setup(owner_plugin: EditorPlugin) -> void:
	plugin = owner_plugin
	_build_toolbar()
	plugin.add_control_to_container(EditorPlugin.CONTAINER_CANVAS_EDITOR_MENU, toolbar)
	toolbar.visible = false
	_refresh_enemy_choices()
	var selection: EditorSelection = EditorInterface.get_selection()
	if selection != null and not selection.selection_changed.is_connected(_on_selection_changed):
		selection.selection_changed.connect(_on_selection_changed)


func cleanup() -> void:
	var selection: EditorSelection = EditorInterface.get_selection()
	if selection != null and selection.selection_changed.is_connected(_on_selection_changed):
		selection.selection_changed.disconnect(_on_selection_changed)
	current_map = null
	if toolbar != null and is_instance_valid(toolbar):
		plugin.remove_control_from_container(EditorPlugin.CONTAINER_CANVAS_EDITOR_MENU, toolbar)
		toolbar.queue_free()
	toolbar = null


func handles(object: Object) -> bool:
	return _map_for_object(object) != null


func edit(object: Object) -> void:
	current_map = _map_for_object(object)
	hover_cell = Vector2i(-999, -999)
	mouse_down = false
	last_painted_cell = Vector2i(-999, -999)
	if toolbar != null:
		toolbar.visible = current_map != null
	if current_map != null:
		current_map.sync_legacy_to_native_layers(false)
		_refresh_enemy_choices()
		_set_status("TileMap natif : sélectionne Ground/Height/Terrain/Objectives puis peins avec Godot.")
	plugin.update_overlays()


func set_visible(visible: bool) -> void:
	if toolbar != null:
		toolbar.visible = visible and current_map != null
	if not visible:
		mouse_down = false


func forward_canvas_input(event: InputEvent) -> bool:
	if current_map == null or not is_instance_valid(current_map):
		return false
	if event is InputEventMouseMotion:
		var motion: InputEventMouseMotion = event as InputEventMouseMotion
		var cell: Vector2i = _viewport_to_cell(motion.position)
		if cell != hover_cell:
			hover_cell = cell
			plugin.update_overlays()
		if paint_toggle == null or not paint_toggle.button_pressed:
			return false
		if mouse_down and current_map.is_cell_valid(cell) and cell != last_painted_cell:
			_apply_tool(cell, _selected_tool())
			last_painted_cell = cell
		return true
	if paint_toggle == null or not paint_toggle.button_pressed:
		return false
	if event is InputEventMouseButton:
		var button: InputEventMouseButton = event as InputEventMouseButton
		if button.button_index != MOUSE_BUTTON_LEFT and button.button_index != MOUSE_BUTTON_RIGHT:
			return false
		var cell: Vector2i = _viewport_to_cell(button.position)
		if button.pressed:
			if not current_map.is_cell_valid(cell):
				return true
			mouse_down = true
			last_painted_cell = cell
			var tool: String = "erase" if button.button_index == MOUSE_BUTTON_RIGHT else _selected_tool()
			_apply_tool(cell, tool)
		else:
			mouse_down = false
			last_painted_cell = Vector2i(-999, -999)
		return true
	return false


func draw_canvas_overlay(overlay: Control) -> void:
	if current_map == null or not is_instance_valid(current_map):
		return
	if paint_toggle != null and paint_toggle.button_pressed and current_map.is_cell_valid(hover_cell):
		var hover_rect: Rect2 = _cell_view_rect(hover_cell)
		overlay.draw_rect(hover_rect.grow(-2.0), Color(1.0, 0.9, 0.35, 0.18), true)
		overlay.draw_rect(hover_rect.grow(-2.0), Color("#ffe28a"), false, 2.0)
	if tactical_preview_toggle != null and tactical_preview_toggle.button_pressed:
		_draw_tactical_preview(overlay)
	if validation_overlay_toggle != null and validation_overlay_toggle.button_pressed:
		_draw_validation_overlay(overlay)
	_draw_selected_link_overlay(overlay)
	_draw_selected_zone_overlay(overlay)


func _build_toolbar() -> void:
	toolbar = HBoxContainer.new()
	toolbar.name = "SporeboundMap2DToolbar"
	var title: Label = Label.new()
	title.text = "Spore Map 2D • TileMap natif"
	toolbar.add_child(title)
	for layer_info: Array in [["Sol", "Ground"], ["Hauteur", "Height"], ["Terrain", "Terrain"], ["Objectifs", "Objectives"]]:
		var layer_button: Button = Button.new()
		layer_button.text = String(layer_info[0])
		layer_button.tooltip_text = "Sélectionner la couche TileMapLayer %s et utiliser la palette native Godot." % String(layer_info[1])
		layer_button.pressed.connect(_select_native_layer.bind(StringName(layer_info[1])))
		toolbar.add_child(layer_button)
	paint_toggle = CheckButton.new()
	paint_toggle.text = "Pinceau rapide"
	paint_toggle.tooltip_text = "Optionnel. Le workflow principal utilise les TileMapLayer natifs de Godot."
	paint_toggle.toggled.connect(_on_paint_toggled)
	toolbar.add_child(paint_toggle)
	tool_select = OptionButton.new()
	tool_select.custom_minimum_size.x = 145.0
	for item: Array in TOOL_ITEMS:
		tool_select.add_item(String(item[0]))
		tool_select.set_item_metadata(tool_select.item_count - 1, String(item[1]))
	toolbar.add_child(tool_select)
	enemy_select = OptionButton.new()
	enemy_select.custom_minimum_size.x = 135.0
	enemy_select.tooltip_text = "Type utilisé par le pinceau Spawn ennemi."
	toolbar.add_child(enemy_select)
	var add_menu: MenuButton = MenuButton.new()
	add_menu.text = "+ Objet"
	add_menu.tooltip_text = "Ajoute un élément au centre de la case survolée/sélectionnée, sans activer le pinceau."
	var add_popup: PopupMenu = add_menu.get_popup()
	add_popup.add_item("Spawn héros", 0)
	add_popup.add_item("Spawn ennemi", 1)
	add_popup.add_separator()
	add_popup.add_item("Porte", 2)
	add_popup.add_item("Interrupteur", 3)
	add_popup.add_item("Coffre", 4)
	add_popup.add_separator()
	add_popup.add_item("Zone polygonale", 5)
	add_popup.id_pressed.connect(_on_add_menu_pressed)
	toolbar.add_child(add_menu)
	var play_button: Button = Button.new()
	play_button.text = "▶ Ici"
	play_button.tooltip_text = "Sauvegarde la scène puis lance immédiatement cette mission en mode playtest, sans modifier la sauvegarde campagne."
	play_button.pressed.connect(play_current_map)
	toolbar.add_child(play_button)
	tactical_preview_toggle = CheckButton.new()
	tactical_preview_toggle.text = "Aperçu tactique"
	tactical_preview_toggle.tooltip_text = "Affiche déplacement et zone d'attaque du spawn ennemi sélectionné."
	tactical_preview_toggle.toggled.connect(_on_overlay_toggled)
	toolbar.add_child(tactical_preview_toggle)
	validation_overlay_toggle = CheckButton.new()
	validation_overlay_toggle.text = "Erreurs"
	validation_overlay_toggle.tooltip_text = "Affiche directement les erreurs et avertissements sur la map."
	validation_overlay_toggle.toggled.connect(_on_overlay_toggled)
	toolbar.add_child(validation_overlay_toggle)
	var snap_button: Button = Button.new()
	snap_button.text = "Snap sélection"
	snap_button.tooltip_text = "Aligne les spawns/objets sélectionnés au centre de leur case."
	snap_button.pressed.connect(_snap_selected)
	toolbar.add_child(snap_button)
	var focus_button: Button = Button.new()
	focus_button.text = "Cadrer sélection"
	focus_button.tooltip_text = "Centre le viewport sur le spawn/objet sélectionné."
	focus_button.pressed.connect(_focus_selected)
	toolbar.add_child(focus_button)
	var validate_button: Button = Button.new()
	validate_button.text = "✓"
	validate_button.tooltip_text = "Valider la map native"
	validate_button.pressed.connect(_validate_map)
	toolbar.add_child(validate_button)
	status_label = Label.new()
	status_label.custom_minimum_size.x = 210.0
	status_label.clip_text = true
	toolbar.add_child(status_label)



func _select_native_layer(layer_name: StringName) -> void:
	if current_map == null or not is_instance_valid(current_map):
		return
	var layer: TileMapLayer = current_map.native_layer(layer_name)
	if layer == null:
		return
	var selection: EditorSelection = EditorInterface.get_selection()
	selection.clear()
	selection.add_node(layer)
	EditorInterface.set_main_screen_editor("2D")
	_set_status("Couche %s sélectionnée — peins avec la palette TileMap de Godot." % String(layer_name))


func focus_in_viewport(select_ground: bool = true) -> void:
	if current_map == null or not is_instance_valid(current_map):
		return
	EditorInterface.set_main_screen_editor("2D")
	current_map.sync_legacy_to_native_layers(false)
	var viewport: SubViewport = EditorInterface.get_editor_viewport_2d()
	if viewport != null:
		var viewport_size: Vector2 = Vector2(viewport.size)
		var map_size: Vector2 = Vector2(float(current_map.grid_width), float(current_map.grid_height)) * current_map.cell_size
		if viewport_size.x > 64.0 and viewport_size.y > 64.0 and map_size.x > 0.0 and map_size.y > 0.0:
			var fit_x: float = (viewport_size.x - 120.0) / map_size.x
			var fit_y: float = (viewport_size.y - 120.0) / map_size.y
			var zoom: float = clampf(minf(fit_x, fit_y), 0.25, 2.0)
			var map_center_global: Vector2 = current_map.to_global(map_size * 0.5)
			var canvas_transform: Transform2D = Transform2D.IDENTITY.scaled(Vector2(zoom, zoom))
			canvas_transform.origin = viewport_size * 0.5 - map_center_global * zoom
			viewport.global_canvas_transform = canvas_transform
	if select_ground:
		_select_native_layer(SporeMap2D.LAYER_GROUND)
	else:
		var selection: EditorSelection = EditorInterface.get_selection()
		selection.clear()
		selection.add_node(current_map)


func _on_paint_toggled(enabled: bool) -> void:
	mouse_down = false
	last_painted_cell = Vector2i(-999, -999)
	_set_status("Mode peinture actif" if enabled else "Mode Godot normal : sélection/déplacement")
	plugin.update_overlays()


func _refresh_enemy_choices() -> void:
	if enemy_select == null:
		return
	var wanted: String = ""
	if enemy_select.item_count > 0 and enemy_select.selected >= 0:
		wanted = String(enemy_select.get_item_metadata(enemy_select.selected))
	enemy_select.clear()
	var dir: DirAccess = DirAccess.open("res://data/units/")
	if dir == null:
		return
	for file_name: String in dir.get_files():
		if not file_name.ends_with(".tres"):
			continue
		var path: String = "res://data/units/" + file_name
		var definition: Resource = load(path)
		if definition == null or String(definition.get("team")) != "enemy":
			continue
		var label: String = String(definition.get("display_name"))
		var unit_id: String = String(definition.get("id"))
		enemy_select.add_item(label)
		enemy_select.set_item_metadata(enemy_select.item_count - 1, unit_id)
		if unit_id == wanted:
			enemy_select.select(enemy_select.item_count - 1)
	if enemy_select.item_count > 0 and enemy_select.selected < 0:
		enemy_select.select(0)


func _selected_tool() -> String:
	if tool_select == null or tool_select.item_count == 0 or tool_select.selected < 0:
		return "ground"
	return String(tool_select.get_item_metadata(tool_select.selected))


func _map_for_object(object: Object) -> SporeMap2D:
	if object is SporeMap2D:
		return object as SporeMap2D
	if object is Node:
		var node: Node = object as Node
		while node != null:
			if node is SporeMap2D:
				return node as SporeMap2D
			node = node.get_parent()
	var scene_root: Node = EditorInterface.get_edited_scene_root()
	if scene_root is SporeMap2D:
		return scene_root as SporeMap2D
	return null


func _map_to_viewport_transform() -> Transform2D:
	var viewport: SubViewport = EditorInterface.get_editor_viewport_2d()
	return viewport.global_canvas_transform * current_map.get_global_transform()


func _viewport_to_cell(viewport_position: Vector2) -> Vector2i:
	var transform: Transform2D = _map_to_viewport_transform()
	var local_position: Vector2 = transform.affine_inverse() * viewport_position
	return current_map.local_to_cell(local_position)


func _apply_tool(cell: Vector2i, tool: String) -> void:
	if current_map == null or not current_map.is_cell_valid(cell):
		return
	match tool:
		"hero":
			_add_hero_spawn(cell)
		"enemy":
			_add_enemy_spawn(cell)
		"door", "switch", "chest":
			_add_interactable(cell, tool)
		"zone":
			_add_zone(cell)
		"erase":
			_erase_cell_and_nodes(cell)
		_:
			_paint_terrain(cell, tool)
	plugin.update_overlays()


func _paint_terrain(cell: Vector2i, tool: String) -> void:
	var before: Dictionary = current_map.cell_snapshot(cell)
	var undo_redo: EditorUndoRedoManager = plugin.get_undo_redo()
	undo_redo.create_action("Spore Map: %s %s" % [tool, str(cell)], UndoRedo.MERGE_ENDS, current_map)
	undo_redo.add_do_method(current_map, &"paint_cell", tool, cell)
	undo_redo.add_undo_method(current_map, &"restore_cell_snapshot", cell, before)
	undo_redo.commit_action()
	EditorInterface.mark_scene_as_unsaved()


func _erase_cell_and_nodes(cell: Vector2i) -> void:
	_paint_terrain(cell, "erase")
	var targets: Array[Node] = []
	for child: Node in current_map.get_children():
		if child is Node2D and (child is SporeHeroSpawn2D or child is SporeEnemySpawn2D or child is SporeMapInteractable2D):
			var child_2d: Node2D = child as Node2D
			if current_map.local_to_cell(child_2d.position) == cell:
				targets.append(child)
	for target: Node in targets:
		_remove_map_node(target)


func _add_hero_spawn(cell: Vector2i) -> void:
	var spawn: SporeHeroSpawn2D = HeroSpawnScript.new() as SporeHeroSpawn2D
	spawn.name = _unique_child_name("HeroSpawn")
	spawn.position = current_map.cell_to_local(cell)
	spawn.order = _hero_spawn_count()
	_add_map_node(spawn, "Ajouter spawn héros")


func _add_enemy_spawn(cell: Vector2i) -> void:
	if enemy_select.item_count <= 0:
		_set_status("Aucun monstre disponible.")
		return
	var spawn: SporeEnemySpawn2D = EnemySpawnScript.new() as SporeEnemySpawn2D
	var unit_id: String = String(enemy_select.get_item_metadata(enemy_select.selected))
	spawn.name = _unique_child_name("EnemySpawn_%s" % unit_id)
	spawn.position = current_map.cell_to_local(cell)
	spawn.unit_id = unit_id
	_add_map_node(spawn, "Ajouter spawn ennemi")


func _add_interactable(cell: Vector2i, object_type: String) -> void:
	var map_object: SporeMapInteractable2D = InteractableScript.new() as SporeMapInteractable2D
	var unique_id: String = _unique_object_id(object_type)
	map_object.name = _unique_child_name(object_type.capitalize())
	map_object.position = current_map.cell_to_local(cell)
	map_object.object_id = unique_id
	map_object.display_name = object_type.capitalize()
	map_object.object_type = object_type
	if object_type == "chest":
		map_object.reward_type = "focus_team"
		map_object.reward_value = 1
	_add_map_node(map_object, "Ajouter %s" % object_type)


func _add_zone(cell: Vector2i) -> void:
	var zone: SporeMapZone2D = ZoneScript.new() as SporeMapZone2D
	var unique_id: String = _unique_zone_id("zone")
	zone.name = _unique_child_name("Zone")
	zone.position = current_map.cell_to_local(cell)
	zone.zone_id = unique_id
	zone.display_name = "Zone"
	zone.zone_type = "trigger"
	var half: float = current_map.cell_size * 0.5
	zone.polygon = PackedVector2Array([
		Vector2(-half, -half),
		Vector2(half, -half),
		Vector2(half, half),
		Vector2(-half, half),
	])
	_add_map_node(zone, "Ajouter zone")


func _on_add_menu_pressed(item_id: int) -> void:
	if current_map == null or not is_instance_valid(current_map):
		return
	var cell: Vector2i = _preferred_creation_cell()
	match item_id:
		0:
			_add_hero_spawn(cell)
		1:
			_add_enemy_spawn(cell)
		2:
			_add_interactable(cell, "door")
		3:
			_add_interactable(cell, "switch")
		4:
			_add_interactable(cell, "chest")
		5:
			_add_zone(cell)
	plugin.update_overlays()


func _preferred_creation_cell() -> Vector2i:
	if current_map != null and current_map.is_cell_valid(hover_cell):
		return hover_cell
	var selected: Array[Node] = EditorInterface.get_selection().get_selected_nodes()
	if selected.size() == 1 and selected[0] is Node2D:
		var selected_2d: Node2D = selected[0] as Node2D
		if _map_for_object(selected_2d) == current_map and selected_2d != current_map:
			var selected_cell: Vector2i = current_map.local_to_cell(selected_2d.position)
			if current_map.is_cell_valid(selected_cell):
				return selected_cell
	return Vector2i(floori(float(current_map.grid_width) / 2.0), floori(float(current_map.grid_height) / 2.0))


func play_current_map() -> void:
	if current_map == null or not is_instance_valid(current_map):
		_set_status("Aucune map active.")
		return
	EditorInterface.save_all_scenes()
	var mission_info: Dictionary = _mission_for_current_map()
	if mission_info.is_empty():
		_set_status("Mission introuvable pour %s." % current_map.scene_file_path)
		return
	var file: FileAccess = FileAccess.open("user://sporebound_editor_test.json", FileAccess.WRITE)
	if file == null:
		_set_status("Impossible de créer la requête de playtest.")
		return
	file.store_string(JSON.stringify({
		"mission_id": String(mission_info.get("id", "")),
		"mission_path": String(mission_info.get("path", "")),
		"autostart": true,
	}))
	file.close()
	_set_status("▶ Playtest direct : %s" % String(mission_info.get("name", "Mission")))
	plugin.get_editor_interface().play_main_scene()


func _mission_for_current_map() -> Dictionary:
	if current_map == null:
		return {}
	var current_path: String = current_map.scene_file_path
	if current_path.is_empty():
		var edited_root: Node = EditorInterface.get_edited_scene_root()
		if edited_root != null:
			current_path = edited_root.scene_file_path
	var dir: DirAccess = DirAccess.open("res://data/missions/")
	if dir == null:
		return {}
	for file_name: String in dir.get_files():
		if not file_name.ends_with(".tres"):
			continue
		var mission_path: String = "res://data/missions/" + file_name
		var mission: Resource = load(mission_path) as Resource
		if mission == null:
			continue
		if String(mission.get("map_scene_path")) == current_path:
			return {
				"id": String(mission.get("id")),
				"name": String(mission.get("display_name")),
				"path": mission_path,
			}
	return {}


func _add_map_node(node: Node2D, action_name: String) -> void:
	var scene_root: Node = EditorInterface.get_edited_scene_root()
	if scene_root == null:
		return
	var undo_redo: EditorUndoRedoManager = plugin.get_undo_redo()
	undo_redo.create_action(action_name, UndoRedo.MERGE_DISABLE, current_map)
	undo_redo.add_do_method(current_map, &"add_child", node)
	undo_redo.add_do_method(node, &"set_owner", scene_root)
	undo_redo.add_do_reference(node)
	undo_redo.add_undo_method(current_map, &"remove_child", node)
	undo_redo.commit_action()
	EditorInterface.mark_scene_as_unsaved()
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(node)


func _remove_map_node(node: Node) -> void:
	if node.get_parent() != current_map:
		return
	var scene_root: Node = EditorInterface.get_edited_scene_root()
	var undo_redo: EditorUndoRedoManager = plugin.get_undo_redo()
	undo_redo.create_action("Supprimer objet de map", UndoRedo.MERGE_DISABLE, current_map)
	undo_redo.add_do_method(current_map, &"remove_child", node)
	undo_redo.add_undo_method(current_map, &"add_child", node)
	if scene_root != null:
		undo_redo.add_undo_method(node, &"set_owner", scene_root)
	undo_redo.add_undo_reference(node)
	undo_redo.commit_action()
	EditorInterface.mark_scene_as_unsaved()


func _snap_selected() -> void:
	if current_map == null:
		return
	var selected: Array[Node] = EditorInterface.get_selection().get_selected_nodes()
	var candidates: Array[Node2D] = []
	for node: Node in selected:
		if node is Node2D and _map_for_object(node) == current_map and node != current_map:
			candidates.append(node as Node2D)
	if candidates.is_empty():
		_set_status("Sélectionne un spawn/objet Node2D.")
		return
	var undo_redo: EditorUndoRedoManager = plugin.get_undo_redo()
	undo_redo.create_action("Snap Spore Map", UndoRedo.MERGE_DISABLE, current_map)
	for node_2d: Node2D in candidates:
		var old_position: Vector2 = node_2d.position
		var snapped: Vector2 = current_map.snap_local_position(old_position)
		undo_redo.add_do_property(node_2d, &"position", snapped)
		undo_redo.add_undo_property(node_2d, &"position", old_position)
	undo_redo.commit_action()
	EditorInterface.mark_scene_as_unsaved()
	_set_status("%d objet(s) aligné(s) sur la grille." % candidates.size())


func _validate_map() -> void:
	if current_map == null:
		return
	if validation_overlay_toggle != null:
		validation_overlay_toggle.button_pressed = true
	var issues: PackedStringArray = current_map.validate_map()
	if issues.is_empty():
		_set_status("✓ Map valide")
		print("[Sporebound Studio] Map valide: ", current_map.scene_file_path)
	else:
		_set_status("⚠ %d problème(s) — voir Output" % issues.size())
		for issue: String in issues:
			push_warning("[Sporebound Map] " + issue)


func map_for_object(object: Object) -> SporeMap2D:
	return _map_for_object(object)


func validate_map_from_inspector() -> void:
	_validate_map()
	plugin.update_overlays()


func toggle_tactical_preview() -> void:
	if tactical_preview_toggle == null:
		return
	tactical_preview_toggle.button_pressed = not tactical_preview_toggle.button_pressed
	plugin.update_overlays()


func snap_node(object: Object) -> void:
	if not (object is Node2D):
		return
	var node_2d: Node2D = object as Node2D
	var map: SporeMap2D = _map_for_object(node_2d)
	if map == null or node_2d == map:
		return
	current_map = map
	var old_position: Vector2 = node_2d.position
	var snapped: Vector2 = map.snap_local_position(old_position)
	if old_position.is_equal_approx(snapped):
		_set_status("Déjà aligné sur la grille.")
		return
	var undo_redo: EditorUndoRedoManager = plugin.get_undo_redo()
	undo_redo.create_action("Snap Spore Map", UndoRedo.MERGE_DISABLE, map)
	undo_redo.add_do_property(node_2d, &"position", snapped)
	undo_redo.add_undo_property(node_2d, &"position", old_position)
	undo_redo.commit_action()
	EditorInterface.mark_scene_as_unsaved()
	_set_status("%s aligné sur %s." % [node_2d.name, str(map.local_to_cell(snapped))])
	plugin.update_overlays()


func focus_node(object: Object) -> void:
	if object is SporeMap2D:
		current_map = object as SporeMap2D
		focus_in_viewport(false)
		return
	if not (object is Node2D):
		return
	var node_2d: Node2D = object as Node2D
	var map: SporeMap2D = _map_for_object(node_2d)
	if map == null:
		return
	current_map = map
	EditorInterface.set_main_screen_editor("2D")
	var selection: EditorSelection = EditorInterface.get_selection()
	selection.clear()
	selection.add_node(node_2d)
	var viewport: SubViewport = EditorInterface.get_editor_viewport_2d()
	if viewport != null:
		var canvas_transform: Transform2D = viewport.global_canvas_transform
		var zoom: float = maxf(0.05, canvas_transform.x.length())
		var global_position: Vector2 = node_2d.global_position
		canvas_transform.origin = Vector2(viewport.size) * 0.5 - global_position * zoom
		viewport.global_canvas_transform = canvas_transform
	plugin.update_overlays()


func open_unit_resource(object: Object) -> void:
	if not object is SporeEnemySpawn2D:
		return
	var spawn: SporeEnemySpawn2D = object as SporeEnemySpawn2D
	var path: String = "res://data/units/%s.tres" % spawn.unit_id
	if not ResourceLoader.exists(path):
		_set_status("UnitDefinition introuvable : %s" % spawn.unit_id)
		return
	var resource: Resource = load(path) as Resource
	if resource != null:
		EditorInterface.edit_resource(resource)


func select_linked_object(map_object: SporeMapInteractable2D) -> void:
	var map: SporeMap2D = _map_for_object(map_object)
	if map == null or map_object.linked_object_id.is_empty():
		return
	var target: SporeMapInteractable2D = _find_interactable(map, map_object.linked_object_id)
	if target == null:
		_set_status("Objet lié introuvable : %s" % map_object.linked_object_id)
		return
	focus_node(target)


func _focus_selected() -> void:
	var selected: Array[Node] = EditorInterface.get_selection().get_selected_nodes()
	if selected.is_empty():
		_set_status("Aucune sélection.")
		return
	focus_node(selected[0])


func _on_overlay_toggled(_enabled: bool) -> void:
	plugin.update_overlays()


func _on_selection_changed() -> void:
	plugin.update_overlays()


func _cell_view_rect(cell: Vector2i) -> Rect2:
	var transform: Transform2D = _map_to_viewport_transform()
	var local_origin: Vector2 = Vector2(cell) * current_map.cell_size
	var p0: Vector2 = transform * local_origin
	var p1: Vector2 = transform * (local_origin + Vector2.ONE * current_map.cell_size)
	return Rect2(p0, p1 - p0)


func _draw_cell_overlay(overlay: Control, cell: Vector2i, fill: Color, border: Color, border_width: float = 1.5) -> void:
	if not current_map.is_cell_valid(cell):
		return
	var rect: Rect2 = _cell_view_rect(cell).grow(-2.0)
	overlay.draw_rect(rect, fill, true)
	overlay.draw_rect(rect, border, false, border_width)


func _draw_tactical_preview(overlay: Control) -> void:
	var selected: Array[Node] = EditorInterface.get_selection().get_selected_nodes()
	if selected.size() != 1:
		return
	var selected_node: Node = selected[0]
	if not selected_node is SporeEnemySpawn2D:
		return
	var spawn: SporeEnemySpawn2D = selected_node as SporeEnemySpawn2D
	if _map_for_object(spawn) != current_map:
		return
	var ranges: Dictionary = _preview_ranges_for_enemy(spawn)
	var attack_cells: Array[Vector2i] = []
	var raw_attack_cells: Variant = ranges.get("attack", [])
	if raw_attack_cells is Array:
		var raw_attack_array: Array = raw_attack_cells
		for raw_cell: Variant in raw_attack_array:
			if raw_cell is Vector2i:
				attack_cells.append(raw_cell)
	var move_cells: Array[Vector2i] = []
	var raw_move_cells: Variant = ranges.get("move", [])
	if raw_move_cells is Array:
		var raw_move_array: Array = raw_move_cells
		for raw_cell: Variant in raw_move_array:
			if raw_cell is Vector2i:
				move_cells.append(raw_cell)
	for cell: Vector2i in attack_cells:
		_draw_cell_overlay(overlay, cell, Color(1.0, 0.30, 0.23, 0.08), Color(1.0, 0.42, 0.32, 0.25), 1.0)
	for cell: Vector2i in move_cells:
		_draw_cell_overlay(overlay, cell, Color(0.25, 0.67, 1.0, 0.15), Color(0.42, 0.78, 1.0, 0.65), 1.5)
	var start_cell: Vector2i = current_map.local_to_cell(spawn.position)
	_draw_cell_overlay(overlay, start_cell, Color(1.0, 0.83, 0.25, 0.18), Color("#ffe28a"), 2.5)


func _preview_ranges_for_enemy(spawn: SporeEnemySpawn2D) -> Dictionary:
	var move_range: int = spawn.move_override
	var attack_range: int = spawn.range_override
	var path: String = "res://data/units/%s.tres" % spawn.unit_id
	if ResourceLoader.exists(path):
		var definition: SporeUnitDefinition = load(path) as SporeUnitDefinition
		if definition != null:
			if move_range < 0:
				move_range = definition.movement
			if attack_range < 0:
				attack_range = definition.attack_range
	move_range = maxi(0, move_range)
	attack_range = maxi(1, attack_range)
	var start: Vector2i = current_map.local_to_cell(spawn.position)
	var environment: Dictionary = current_map.to_environment()
	var blocked: Dictionary = {}
	var obstacle_values: Array = []
	var raw_obstacle_values: Variant = environment.get("obstacles", [])
	if raw_obstacle_values is Array:
		obstacle_values = raw_obstacle_values
	for raw_cell: Variant in obstacle_values:
		if raw_cell is Vector2i:
			blocked[raw_cell] = true
	for node: Node in _all_map_nodes(current_map):
		if node == spawn:
			continue
		if node is SporeHeroSpawn2D or node is SporeEnemySpawn2D:
			var occupied_node: Node2D = node as Node2D
			blocked[current_map.local_to_cell(occupied_node.position)] = true
		elif node is SporeMapInteractable2D:
			var map_object: SporeMapInteractable2D = node as SporeMapInteractable2D
			if map_object.object_type == "door" and not map_object.starts_active:
				blocked[current_map.local_to_cell(map_object.position)] = true
	var heights: Dictionary = environment.get("heights", {}) as Dictionary
	var costs: Dictionary = {start: 0}
	var frontier: Array[Vector2i] = [start]
	while not frontier.is_empty():
		var current: Vector2i = frontier.pop_front()
		var current_cost: int = int(costs.get(current, 0))
		for direction: Vector2i in [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.DOWN, Vector2i.UP]:
			var next_cell: Vector2i = current + direction
			if not current_map.is_cell_valid(next_cell) or blocked.has(next_cell):
				continue
			var climb: int = maxi(0, int(heights.get(next_cell, 0)) - int(heights.get(current, 0)))
			var next_cost: int = current_cost + 1 + climb
			if next_cost > move_range:
				continue
			if costs.has(next_cell) and int(costs[next_cell]) <= next_cost:
				continue
			costs[next_cell] = next_cost
			frontier.append(next_cell)
	var move_cells: Array[Vector2i] = []
	var origins: Array[Vector2i] = [start]
	for raw_cell: Variant in costs.keys():
		if raw_cell is Vector2i:
			var move_cell: Vector2i = raw_cell
			if move_cell != start:
				move_cells.append(move_cell)
			origins.append(move_cell)
	var attack_set: Dictionary = {}
	for origin: Vector2i in origins:
		for y: int in range(current_map.grid_height):
			for x: int in range(current_map.grid_width):
				var candidate: Vector2i = Vector2i(x, y)
				var distance: int = absi(candidate.x - origin.x) + absi(candidate.y - origin.y)
				if distance > 0 and distance <= attack_range and not costs.has(candidate):
					attack_set[candidate] = true
	var attack_cells: Array[Vector2i] = []
	for raw_cell: Variant in attack_set.keys():
		if raw_cell is Vector2i:
			attack_cells.append(raw_cell)
	return {"move": move_cells, "attack": attack_cells}


func _draw_validation_overlay(overlay: Control) -> void:
	var issues: Array[Dictionary] = current_map.validation_issues()
	var global_messages: Array[String] = []
	for issue: Dictionary in issues:
		var severity: String = String(issue.get("severity", "warning"))
		var cell_value: Variant = issue.get("cell", Vector2i(-999, -999))
		if cell_value is Vector2i and current_map.is_cell_valid(cell_value):
			var cell: Vector2i = cell_value
			var fill: Color = Color(1.0, 0.18, 0.18, 0.16) if severity == "error" else Color(1.0, 0.72, 0.18, 0.12)
			var border: Color = Color("#ff5b5b") if severity == "error" else Color("#ffc857")
			_draw_cell_overlay(overlay, cell, fill, border, 3.0)
			var rect: Rect2 = _cell_view_rect(cell)
			overlay.draw_string(ThemeDB.fallback_font, rect.position + Vector2(6.0, 18.0), "!", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 16, border)
		else:
			global_messages.append(String(issue.get("message", "Problème de map")))
	if not global_messages.is_empty():
		var banner: Rect2 = Rect2(Vector2(18.0, 18.0), Vector2(440.0, 28.0 + 18.0 * float(global_messages.size())))
		overlay.draw_rect(banner, Color(0.12, 0.08, 0.10, 0.90), true)
		overlay.draw_rect(banner, Color("#ffc857"), false, 2.0)
		for index: int in range(global_messages.size()):
			overlay.draw_string(ThemeDB.fallback_font, banner.position + Vector2(10.0, 22.0 + 18.0 * float(index)), global_messages[index], HORIZONTAL_ALIGNMENT_LEFT, banner.size.x - 20.0, 12, Color("#fff0c8"))


func _draw_selected_link_overlay(overlay: Control) -> void:
	var selected: Array[Node] = EditorInterface.get_selection().get_selected_nodes()
	if selected.size() != 1 or not (selected[0] is SporeMapInteractable2D):
		return
	var source: SporeMapInteractable2D = selected[0] as SporeMapInteractable2D
	if source.linked_object_id.is_empty() or _map_for_object(source) != current_map:
		return
	var target: SporeMapInteractable2D = _find_interactable(current_map, source.linked_object_id)
	if target == null:
		return
	var transform: Transform2D = _map_to_viewport_transform()
	var from_point: Vector2 = transform * source.position
	var to_point: Vector2 = transform * target.position
	overlay.draw_line(from_point, to_point, Color("#d78cff"), 3.0, true)
	overlay.draw_circle(to_point, 6.0, Color("#f1c6ff"))


func _draw_selected_zone_overlay(overlay: Control) -> void:
	var selected: Array[Node] = EditorInterface.get_selection().get_selected_nodes()
	if selected.size() != 1 or not (selected[0] is SporeMapZone2D):
		return
	var zone: SporeMapZone2D = selected[0] as SporeMapZone2D
	if _map_for_object(zone) != current_map:
		return
	for cell: Vector2i in zone.occupied_cells(current_map):
		_draw_cell_overlay(overlay, cell, Color(0.84, 0.55, 1.0, 0.08), Color(0.84, 0.55, 1.0, 0.48), 1.5)


func _find_interactable(map: SporeMap2D, object_id: String) -> SporeMapInteractable2D:
	for node: Node in _all_map_nodes(map):
		if node is SporeMapInteractable2D:
			var map_object: SporeMapInteractable2D = node as SporeMapInteractable2D
			if map_object.object_id == object_id:
				return map_object
	return null


func _all_map_nodes(parent: Node) -> Array[Node]:
	var result: Array[Node] = []
	for child: Node in parent.get_children():
		result.append(child)
		result.append_array(_all_map_nodes(child))
	return result


func _hero_spawn_count() -> int:
	var count: int = 0
	for child: Node in current_map.get_children():
		if child is SporeHeroSpawn2D:
			count += 1
	return count


func _unique_child_name(base: String) -> String:
	var candidate: String = base
	var suffix: int = 2
	while current_map.has_node(NodePath(candidate)):
		candidate = "%s%d" % [base, suffix]
		suffix += 1
	return candidate


func _unique_object_id(base: String) -> String:
	var used: Dictionary = {}
	for child: Node in current_map.get_children():
		if child is SporeMapInteractable2D:
			var map_object: SporeMapInteractable2D = child as SporeMapInteractable2D
			used[map_object.object_id] = true
	var candidate: String = base
	var suffix: int = 2
	while used.has(candidate):
		candidate = "%s_%d" % [base, suffix]
		suffix += 1
	return candidate


func _unique_zone_id(base: String) -> String:
	var used: Dictionary = {}
	for node: Node in _all_map_nodes(current_map):
		if node is SporeMapZone2D:
			var zone: SporeMapZone2D = node as SporeMapZone2D
			used[zone.zone_id] = true
	var candidate: String = base
	var suffix: int = 2
	while used.has(candidate):
		candidate = "%s_%d" % [base, suffix]
		suffix += 1
	return candidate


func _set_status(text: String) -> void:
	if status_label != null:
		status_label.text = text
		status_label.tooltip_text = text
