@tool
class_name SporeMapInspectorPlugin
extends EditorInspectorPlugin

var native_editor: SporeNativeMapEditor


func setup(editor: SporeNativeMapEditor) -> void:
	native_editor = editor


func _can_handle(object: Object) -> bool:
	return (
		object is SporeMap2D
		or object is SporeHeroSpawn2D
		or object is SporeEnemySpawn2D
		or object is SporeMapInteractable2D
		or object is SporeMapZone2D
		or object is SporeMap3D
		or object is SporeTacticalTile3D
		or object is SporeHeroSpawn3D
		or object is SporeEnemySpawn3D
		or object is SporeMapInteractable3D
	)


func _parse_begin(object: Object) -> void:
	if native_editor == null:
		return
	var panel: PanelContainer = PanelContainer.new()
	panel.name = "SporeboundMapInspectorTools"
	var box: VBoxContainer = VBoxContainer.new()
	panel.add_child(box)

	var title: Label = Label.new()
	title.text = _title_for(object)
	title.tooltip_text = "Outils natifs Sporebound pour le level design."
	box.add_child(title)

	var info: Label = Label.new()
	info.text = _info_for(object)
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(info)

	var buttons: HBoxContainer = HBoxContainer.new()
	box.add_child(buttons)

	if _is_3d_map_object(object):
		_add_button(buttons, "Vue 3D", "Passe dans le workspace 3D et sélectionne cet élément.", _focus_3d.bind(object))
		_add_button(buttons, "Recaler", "Recalcule la position et l'aperçu depuis les propriétés tactiques.", _refresh_3d.bind(object))
		if object is Node3D and not object is SporeMap3D:
			_add_button(buttons, "Capturer pos.", "Convertit la position 3D actuelle vers la case/hauteur tactique la plus proche.", _capture_3d_transform.bind(object as Node3D))
		if object is SporeMap3D:
			_add_button(buttons, "Valider", "Valide les cases, spawns et identifiants de la map 3D.", _validate_3d.bind(object as SporeMap3D))
			_add_button(buttons, "▶ Combat 3D", "Sauvegarde les scènes puis lance le prototype tactique 3D.", _play_3d_battle)
		elif object is SporeEnemySpawn3D:
			_add_button(buttons, "Ouvrir unité", "Ouvre la UnitDefinition de ce monstre.", _open_enemy_3d_unit.bind(object as SporeEnemySpawn3D))
	else:
		_add_button(buttons, "Cadrer", "Centre la vue 2D sur cet élément.", native_editor.focus_node.bind(object))
		if object is SporeMap2D:
			_add_button(buttons, "Valider", "Valide la map et affiche les erreurs dans la viewport.", native_editor.validate_map_from_inspector)
			_add_button(buttons, "Aperçu tactique", "Active/désactive l'aperçu mouvement/attaque.", native_editor.toggle_tactical_preview)
			_add_button(buttons, "▶ Tester ici", "Sauvegarde et lance directement cette mission en mode playtest.", native_editor.play_current_map)
		elif object is Node2D:
			_add_button(buttons, "Snap grille", "Aligne cet élément au centre de sa case.", native_editor.snap_node.bind(object))

		if object is SporeEnemySpawn2D:
			_add_button(buttons, "Ouvrir unité", "Ouvre la UnitDefinition de ce monstre.", native_editor.open_unit_resource.bind(object))
		elif object is SporeMapInteractable2D:
			var map_object: SporeMapInteractable2D = object as SporeMapInteractable2D
			if not map_object.linked_object_id.is_empty():
				_add_button(buttons, "Voir liaison", "Sélectionne l'objet lié.", native_editor.select_linked_object.bind(map_object))

	add_custom_control(panel)


func _add_button(parent: HBoxContainer, text: String, tooltip: String, callback: Callable) -> void:
	var button: Button = Button.new()
	button.text = text
	button.tooltip_text = tooltip
	button.pressed.connect(callback)
	parent.add_child(button)


func _title_for(object: Object) -> String:
	if object is SporeMap3D:
		return "Sporebound • Map tactique 2.5D / 3D"
	if object is SporeTacticalTile3D:
		return "Sporebound • Case tactique 3D"
	if object is SporeHeroSpawn3D:
		return "Sporebound • Spawn héros 3D"
	if object is SporeEnemySpawn3D:
		return "Sporebound • Spawn ennemi 3D"
	if object is SporeMapInteractable3D:
		return "Sporebound • Objet interactif 3D"
	if object is SporeMap2D:
		return "Sporebound • Map native 2D"
	if object is SporeHeroSpawn2D:
		return "Sporebound • Spawn héros"
	if object is SporeEnemySpawn2D:
		return "Sporebound • Spawn ennemi"
	if object is SporeMapZone2D:
		return "Sporebound • Zone gameplay"
	return "Sporebound • Objet interactif"


func _info_for(object: Object) -> String:
	if object is SporeMap3D:
		var map_3d: SporeMap3D = object as SporeMap3D
		var stats_3d: Dictionary = map_3d.editor_stats()
		return "%dx%d • %d cases • %d héros • %d ennemis • %d objets" % [
			map_3d.grid_width,
			map_3d.grid_height,
			int(stats_3d.get("tiles", 0)),
			int(stats_3d.get("heroes", 0)),
			int(stats_3d.get("enemies", 0)),
			int(stats_3d.get("interactables", 0)),
		]
	if object is SporeTacticalTile3D:
		var tile: SporeTacticalTile3D = object as SporeTacticalTile3D
		var terrain_info: String = tile.terrain_type
		if tile.terrain_type == "cover":
			terrain_info += " • face " + tile.cover_facing
		return "Case %s • hauteur %d • %s" % [str(tile.cell), tile.elevation, terrain_info]
	if object is SporeHeroSpawn3D:
		var hero_3d: SporeHeroSpawn3D = object as SporeHeroSpawn3D
		return "Case %s • héros %d" % [str(hero_3d.cell), hero_3d.order + 1]
	if object is SporeEnemySpawn3D:
		var enemy_3d: SporeEnemySpawn3D = object as SporeEnemySpawn3D
		return "Case %s • unité: %s" % [str(enemy_3d.cell), enemy_3d.unit_id]
	if object is SporeMapInteractable3D:
		var object_3d: SporeMapInteractable3D = object as SporeMapInteractable3D
		return "Case %s • %s • id: %s" % [str(object_3d.cell), object_3d.object_type, object_3d.object_id]
	if object is SporeMap2D:
		var map: SporeMap2D = object as SporeMap2D
		var stats: Dictionary = map.editor_stats()
		return "%dx%d • %d héros • %d ennemis • %d objets • %d zones" % [
			map.grid_width,
			map.grid_height,
			int(stats.get("heroes", 0)),
			int(stats.get("enemies", 0)),
			int(stats.get("interactables", 0)),
			int(stats.get("zones", 0)),
		]
	if object is Node2D:
		var node_2d: Node2D = object as Node2D
		var parent_map: SporeMap2D = native_editor.map_for_object(object)
		if parent_map != null:
			var cell: Vector2i = parent_map.local_to_cell(node_2d.position)
			if object is SporeMapZone2D:
				var zone: SporeMapZone2D = object as SporeMapZone2D
				return "%s • %s • %d case(s)" % [zone.zone_id, zone.zone_type, zone.occupied_cells(parent_map).size()]
			if object is SporeEnemySpawn2D:
				var spawn: SporeEnemySpawn2D = object as SporeEnemySpawn2D
				return "Case %s • unité: %s" % [str(cell), spawn.unit_id]
			if object is SporeMapInteractable2D:
				var map_object: SporeMapInteractable2D = object as SporeMapInteractable2D
				return "Case %s • %s • id: %s" % [str(cell), map_object.object_type, map_object.object_id]
			return "Case %s" % str(cell)
	return ""


func _is_3d_map_object(object: Object) -> bool:
	return (
		object is SporeMap3D
		or object is SporeTacticalTile3D
		or object is SporeHeroSpawn3D
		or object is SporeEnemySpawn3D
		or object is SporeMapInteractable3D
	)


func _focus_3d(object: Object) -> void:
	if not object is Node3D:
		return
	EditorInterface.set_main_screen_editor("3D")
	var selection: EditorSelection = EditorInterface.get_selection()
	selection.clear()
	selection.add_node(object as Node3D)


func _refresh_3d(object: Object) -> void:
	if object is SporeMap3D:
		(object as SporeMap3D).refresh_layout()
	elif object.has_method("refresh_from_map"):
		object.call("refresh_from_map")
	EditorInterface.mark_scene_as_unsaved()


func _validate_3d(map: SporeMap3D) -> void:
	var issues: Array[Dictionary] = map.validation_issues()
	if issues.is_empty():
		print("[Sporebound] Map 3D valide : %s" % map.scene_file_path)
		return
	for issue: Dictionary in issues:
		var severity: String = String(issue.get("severity", "warning"))
		var message: String = String(issue.get("message", "Problème de map"))
		if severity == "error":
			push_error("[Sporebound] %s" % message)
		else:
			push_warning("[Sporebound] %s" % message)


func _play_3d_battle() -> void:
	const BATTLE_SCENE: String = "res://scenes/mission_1_battle_3d.tscn"
	if not ResourceLoader.exists(BATTLE_SCENE):
		push_error("[Sporebound] Scène de combat 3D introuvable : %s" % BATTLE_SCENE)
		return
	EditorInterface.save_all_scenes()
	EditorInterface.play_custom_scene(BATTLE_SCENE)


func _open_enemy_3d_unit(spawn: SporeEnemySpawn3D) -> void:
	var path: String = "res://data/units/%s.tres" % spawn.unit_id
	if not ResourceLoader.exists(path):
		push_warning("[Sporebound] UnitDefinition introuvable : %s" % spawn.unit_id)
		return
	var resource: Resource = load(path) as Resource
	if resource != null:
		EditorInterface.edit_resource(resource)


func _capture_3d_transform(node_3d: Node3D) -> void:
	var map: SporeMap3D = _map_3d_parent(node_3d)
	if map == null:
		return
	var map_local: Vector3 = map.to_local(node_3d.global_position)
	var snapped_cell: Vector2i = map.local_to_cell(map_local)
	if node_3d is SporeTacticalTile3D:
		var tile: SporeTacticalTile3D = node_3d as SporeTacticalTile3D
		tile.cell = snapped_cell
		tile.elevation = maxi(0, roundi(map_local.y / map.elevation_step))
	elif node_3d is SporeHeroSpawn3D:
		(node_3d as SporeHeroSpawn3D).cell = snapped_cell
	elif node_3d is SporeEnemySpawn3D:
		(node_3d as SporeEnemySpawn3D).cell = snapped_cell
	elif node_3d is SporeMapInteractable3D:
		(node_3d as SporeMapInteractable3D).cell = snapped_cell
	EditorInterface.mark_scene_as_unsaved()


func _map_3d_parent(node: Node) -> SporeMap3D:
	var current: Node = node
	while current != null:
		if current is SporeMap3D:
			return current as SporeMap3D
		current = current.get_parent()
	return null
