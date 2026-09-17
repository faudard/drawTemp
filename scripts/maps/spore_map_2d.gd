@tool
class_name SporeMap2D
extends Node2D

## Native Godot 2D level scene for Sporebound Tactics.
##
## V1.9.4: terrain is authored with real TileMapLayer children. The exported arrays
## below are kept only as a migration/fallback source for old maps.

const TILESET_PATH: String = "res://assets/editor/spore_map_tileset.tres"
const SOURCE_ID: int = 0
const TILE_GROUND: Vector2i = Vector2i(0, 0)
const TILE_OBSTACLE: Vector2i = Vector2i(1, 0)
const TILE_COVER: Vector2i = Vector2i(2, 0)
const TILE_HAZARD: Vector2i = Vector2i(3, 0)
const TILE_EXTRACTION: Vector2i = Vector2i(4, 0)
const TILE_BONUS: Vector2i = Vector2i(5, 0)
const TILE_CROWN: Vector2i = Vector2i(6, 0)
const TILE_HEIGHT_1: Vector2i = Vector2i(7, 0)
const TILE_HEIGHT_2: Vector2i = Vector2i(8, 0)

const LAYER_GROUND: StringName = &"Ground"
const LAYER_HEIGHT: StringName = &"Height"
const LAYER_TERRAIN: StringName = &"Terrain"
const LAYER_OBJECTIVES: StringName = &"Objectives"

@export_group("Grid")
@export_range(1, 64, 1) var grid_width: int = 10:
	set(value):
		grid_width = maxi(1, value)
		queue_redraw()
@export_range(1, 64, 1) var grid_height: int = 8:
	set(value):
		grid_height = maxi(1, value)
		queue_redraw()
@export_range(32.0, 128.0, 1.0) var cell_size: float = 64.0:
	set(value):
		cell_size = maxf(32.0, value)
		_sync_layer_scale()
		queue_redraw()
@export var show_grid: bool = true:
	set(value):
		show_grid = value
		queue_redraw()
@export var show_coordinates: bool = true:
	set(value):
		show_coordinates = value
		queue_redraw()

@export_group("Legacy migration data")
@export var obstacles: Array[Vector2i] = []
@export var cover: Array[Vector2i] = []
@export var hazards: Array[Vector2i] = []
@export var extraction: Array[Vector2i] = []
@export var bonus: Array[Vector2i] = []
@export var crown: Vector2i = Vector2i(-9, -9)
@export var height_level_1: Array[Vector2i] = []
@export var height_level_2: Array[Vector2i] = []


func _ready() -> void:
	_ensure_native_layers()
	_sync_layer_scale()
	if not _native_layers_have_data():
		sync_legacy_to_native_layers(true)
	queue_redraw()


func _ensure_native_layers() -> void:
	var tile_set: TileSet = load(TILESET_PATH) as TileSet
	if tile_set == null:
		return
	_ensure_layer(LAYER_GROUND, tile_set, -40)
	_ensure_layer(LAYER_HEIGHT, tile_set, -30)
	_ensure_layer(LAYER_TERRAIN, tile_set, -20)
	_ensure_layer(LAYER_OBJECTIVES, tile_set, -10)


func _ensure_layer(layer_name: StringName, tile_set: TileSet, wanted_z: int) -> TileMapLayer:
	var existing: TileMapLayer = get_node_or_null(NodePath(String(layer_name))) as TileMapLayer
	if existing != null:
		if existing.tile_set == null:
			existing.tile_set = tile_set
		existing.z_index = wanted_z
		return existing
	var layer: TileMapLayer = TileMapLayer.new()
	layer.name = String(layer_name)
	layer.tile_set = tile_set
	layer.z_index = wanted_z
	add_child(layer)
	if owner != null:
		layer.owner = owner
	elif Engine.is_editor_hint():
		layer.owner = self
	return layer


func _sync_layer_scale() -> void:
	var scale_value: float = cell_size / 64.0
	for layer_name: StringName in [LAYER_GROUND, LAYER_HEIGHT, LAYER_TERRAIN, LAYER_OBJECTIVES]:
		var layer: TileMapLayer = get_node_or_null(NodePath(String(layer_name))) as TileMapLayer
		if layer != null:
			layer.scale = Vector2(scale_value, scale_value)


func native_layer(layer_name: StringName) -> TileMapLayer:
	return get_node_or_null(NodePath(String(layer_name))) as TileMapLayer


func _native_layers_have_data() -> bool:
	var ground: TileMapLayer = native_layer(LAYER_GROUND)
	if ground != null and not ground.get_used_cells().is_empty():
		return true
	for layer_name: StringName in [LAYER_HEIGHT, LAYER_TERRAIN, LAYER_OBJECTIVES]:
		var layer: TileMapLayer = native_layer(layer_name)
		if layer != null and not layer.get_used_cells().is_empty():
			return true
	return false


func sync_legacy_to_native_layers(force: bool = false) -> void:
	_ensure_native_layers()
	if not force and _native_layers_have_data():
		return
	var ground: TileMapLayer = native_layer(LAYER_GROUND)
	var height: TileMapLayer = native_layer(LAYER_HEIGHT)
	var terrain: TileMapLayer = native_layer(LAYER_TERRAIN)
	var objectives: TileMapLayer = native_layer(LAYER_OBJECTIVES)
	if ground == null or height == null or terrain == null or objectives == null:
		return
	ground.clear()
	height.clear()
	terrain.clear()
	objectives.clear()
	for y: int in range(grid_height):
		for x: int in range(grid_width):
			ground.set_cell(Vector2i(x, y), SOURCE_ID, TILE_GROUND, 0)
	for cell: Vector2i in height_level_1:
		if is_cell_valid(cell):
			height.set_cell(cell, SOURCE_ID, TILE_HEIGHT_1, 0)
	for cell: Vector2i in height_level_2:
		if is_cell_valid(cell):
			height.set_cell(cell, SOURCE_ID, TILE_HEIGHT_2, 0)
	for cell: Vector2i in obstacles:
		if is_cell_valid(cell):
			terrain.set_cell(cell, SOURCE_ID, TILE_OBSTACLE, 0)
	for cell: Vector2i in cover:
		if is_cell_valid(cell):
			terrain.set_cell(cell, SOURCE_ID, TILE_COVER, 0)
	for cell: Vector2i in hazards:
		if is_cell_valid(cell):
			terrain.set_cell(cell, SOURCE_ID, TILE_HAZARD, 0)
	for cell: Vector2i in extraction:
		if is_cell_valid(cell):
			objectives.set_cell(cell, SOURCE_ID, TILE_EXTRACTION, 0)
	for cell: Vector2i in bonus:
		if is_cell_valid(cell):
			objectives.set_cell(cell, SOURCE_ID, TILE_BONUS, 0)
	if is_cell_valid(crown):
		objectives.set_cell(crown, SOURCE_ID, TILE_CROWN, 0)
	ground.update_internals()
	height.update_internals()
	terrain.update_internals()
	objectives.update_internals()
	queue_redraw()


func is_cell_valid(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < grid_width and cell.y < grid_height


func cell_to_local(cell: Vector2i, centered: bool = true) -> Vector2:
	var offset: Vector2 = Vector2(0.5, 0.5) if centered else Vector2.ZERO
	return (Vector2(cell) + offset) * cell_size


func local_to_cell(local_position: Vector2) -> Vector2i:
	return Vector2i(floori(local_position.x / cell_size), floori(local_position.y / cell_size))


func snap_local_position(local_position: Vector2) -> Vector2:
	return cell_to_local(local_to_cell(local_position), true)


func cell_snapshot(cell: Vector2i) -> Dictionary:
	var terrain_layer: TileMapLayer = native_layer(LAYER_TERRAIN)
	var height_layer: TileMapLayer = native_layer(LAYER_HEIGHT)
	var objective_layer: TileMapLayer = native_layer(LAYER_OBJECTIVES)
	return {
		"terrain": terrain_layer.get_cell_atlas_coords(cell) if terrain_layer != null else Vector2i(-1, -1),
		"height": height_layer.get_cell_atlas_coords(cell) if height_layer != null else Vector2i(-1, -1),
		"objective": objective_layer.get_cell_atlas_coords(cell) if objective_layer != null else Vector2i(-1, -1),
	}


func paint_cell(tool: String, cell: Vector2i) -> void:
	if not is_cell_valid(cell):
		return
	_ensure_native_layers()
	var height_layer: TileMapLayer = native_layer(LAYER_HEIGHT)
	var terrain_layer: TileMapLayer = native_layer(LAYER_TERRAIN)
	var objective_layer: TileMapLayer = native_layer(LAYER_OBJECTIVES)
	if height_layer == null or terrain_layer == null or objective_layer == null:
		return
	match tool:
		"ground":
			terrain_layer.erase_cell(cell)
		"obstacle":
			terrain_layer.set_cell(cell, SOURCE_ID, TILE_OBSTACLE, 0)
		"cover":
			terrain_layer.set_cell(cell, SOURCE_ID, TILE_COVER, 0)
		"hazard":
			terrain_layer.set_cell(cell, SOURCE_ID, TILE_HAZARD, 0)
		"extraction":
			objective_layer.set_cell(cell, SOURCE_ID, TILE_EXTRACTION, 0)
		"bonus":
			objective_layer.set_cell(cell, SOURCE_ID, TILE_BONUS, 0)
		"crown":
			_clear_tile_from_layer(objective_layer, TILE_CROWN)
			objective_layer.set_cell(cell, SOURCE_ID, TILE_CROWN, 0)
		"height0":
			height_layer.erase_cell(cell)
		"height1":
			height_layer.set_cell(cell, SOURCE_ID, TILE_HEIGHT_1, 0)
		"height2":
			height_layer.set_cell(cell, SOURCE_ID, TILE_HEIGHT_2, 0)
		"erase":
			height_layer.erase_cell(cell)
			terrain_layer.erase_cell(cell)
			objective_layer.erase_cell(cell)
	queue_redraw()


func restore_cell_snapshot(cell: Vector2i, snapshot: Dictionary) -> void:
	_restore_layer_cell(native_layer(LAYER_TERRAIN), cell, snapshot.get("terrain", Vector2i(-1, -1)))
	_restore_layer_cell(native_layer(LAYER_HEIGHT), cell, snapshot.get("height", Vector2i(-1, -1)))
	_restore_layer_cell(native_layer(LAYER_OBJECTIVES), cell, snapshot.get("objective", Vector2i(-1, -1)))
	queue_redraw()


func _restore_layer_cell(layer: TileMapLayer, cell: Vector2i, raw_atlas: Variant) -> void:
	if layer == null:
		return
	if raw_atlas is Vector2i and raw_atlas != Vector2i(-1, -1):
		var atlas: Vector2i = raw_atlas
		layer.set_cell(cell, SOURCE_ID, atlas, 0)
	else:
		layer.erase_cell(cell)


func _clear_tile_from_layer(layer: TileMapLayer, atlas: Vector2i) -> void:
	if layer == null:
		return
	for cell: Vector2i in layer.get_used_cells():
		if layer.get_cell_atlas_coords(cell) == atlas:
			layer.erase_cell(cell)


func terrain_heights() -> Dictionary:
	var result: Dictionary = {}
	var layer: TileMapLayer = native_layer(LAYER_HEIGHT)
	if layer != null and not layer.get_used_cells().is_empty():
		for cell: Vector2i in layer.get_used_cells():
			var atlas: Vector2i = layer.get_cell_atlas_coords(cell)
			if atlas == TILE_HEIGHT_1:
				result[cell] = 1
			elif atlas == TILE_HEIGHT_2:
				result[cell] = 2
		return result
	for cell: Vector2i in height_level_1:
		result[cell] = 1
	for cell: Vector2i in height_level_2:
		result[cell] = 2
	return result


func to_environment() -> Dictionary:
	if _native_layers_have_data():
		return _native_environment()
	return {
		"obstacles": obstacles.duplicate(),
		"cover": cover.duplicate(),
		"hazards": hazards.duplicate(),
		"extraction": extraction.duplicate(),
		"bonus": bonus.duplicate(),
		"crown": crown,
		"heights": terrain_heights(),
		"grid_width": grid_width,
		"grid_height": grid_height,
		"zones": zone_definitions(),
	}


func _native_environment() -> Dictionary:
	var obstacle_cells: Array[Vector2i] = []
	var cover_cells: Array[Vector2i] = []
	var hazard_cells: Array[Vector2i] = []
	var extraction_cells: Array[Vector2i] = []
	var bonus_cells: Array[Vector2i] = []
	var crown_cell: Vector2i = Vector2i(-9, -9)
	var terrain_layer: TileMapLayer = native_layer(LAYER_TERRAIN)
	var objective_layer: TileMapLayer = native_layer(LAYER_OBJECTIVES)
	if terrain_layer != null:
		for cell: Vector2i in terrain_layer.get_used_cells():
			var atlas: Vector2i = terrain_layer.get_cell_atlas_coords(cell)
			if atlas == TILE_OBSTACLE:
				obstacle_cells.append(cell)
			elif atlas == TILE_COVER:
				cover_cells.append(cell)
			elif atlas == TILE_HAZARD:
				hazard_cells.append(cell)
	if objective_layer != null:
		for cell: Vector2i in objective_layer.get_used_cells():
			var atlas: Vector2i = objective_layer.get_cell_atlas_coords(cell)
			if atlas == TILE_EXTRACTION:
				extraction_cells.append(cell)
			elif atlas == TILE_BONUS:
				bonus_cells.append(cell)
			elif atlas == TILE_CROWN:
				crown_cell = cell
	return {
		"obstacles": obstacle_cells,
		"cover": cover_cells,
		"hazards": hazard_cells,
		"extraction": extraction_cells,
		"bonus": bonus_cells,
		"crown": crown_cell,
		"heights": terrain_heights(),
		"grid_width": grid_width,
		"grid_height": grid_height,
		"zones": zone_definitions(),
	}


func hero_start_cells() -> Array[Vector2i]:
	var entries: Array[Dictionary] = []
	for node: Node in _descendants(self):
		if node is SporeHeroSpawn2D:
			var spawn: SporeHeroSpawn2D = node as SporeHeroSpawn2D
			entries.append({"order": spawn.order, "cell": local_to_cell(spawn.position)})
	entries.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["order"]) < int(b["order"]))
	var result: Array[Vector2i] = []
	for entry: Dictionary in entries:
		var cell_value: Variant = entry.get("cell", Vector2i.ZERO)
		if cell_value is Vector2i:
			result.append(cell_value)
	return result


func enemy_spawn_data() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for node: Node in _descendants(self):
		if node is SporeEnemySpawn2D:
			var spawn: SporeEnemySpawn2D = node as SporeEnemySpawn2D
			result.append({
				"unit_id": spawn.unit_id,
				"cell": local_to_cell(spawn.position),
				"role": spawn.role_override,
				"hp": spawn.hp_override,
				"attack": spawn.attack_override,
				"move": spawn.move_override,
				"range": spawn.range_override,
			})
	return result


func interactable_definitions() -> Array[Resource]:
	var result: Array[Resource] = []
	for node: Node in _descendants(self):
		if node is SporeMapInteractable2D:
			var map_object: SporeMapInteractable2D = node as SporeMapInteractable2D
			result.append(map_object.to_definition(local_to_cell(map_object.position)))
	return result


func zone_definitions() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for node: Node in _descendants(self):
		if node is SporeMapZone2D:
			var zone: SporeMapZone2D = node as SporeMapZone2D
			result.append(zone.to_runtime_dict(self))
	return result


func zone_by_id(zone_id: String) -> SporeMapZone2D:
	for node: Node in _descendants(self):
		if node is SporeMapZone2D:
			var zone: SporeMapZone2D = node as SporeMapZone2D
			if zone.zone_id == zone_id:
				return zone
	return null


func editor_stats() -> Dictionary:
	var hero_count: int = 0
	var enemy_count: int = 0
	var interactable_count: int = 0
	var zone_count: int = 0
	for node: Node in _descendants(self):
		if node is SporeHeroSpawn2D:
			hero_count += 1
		elif node is SporeEnemySpawn2D:
			enemy_count += 1
		elif node is SporeMapInteractable2D:
			interactable_count += 1
		elif node is SporeMapZone2D:
			zone_count += 1
	return {
		"heroes": hero_count,
		"enemies": enemy_count,
		"interactables": interactable_count,
		"zones": zone_count,
	}


func validation_issues() -> Array[Dictionary]:
	var issues: Array[Dictionary] = []
	if grid_width < 1 or grid_height < 1:
		_add_validation_issue(issues, "error", "La grille doit avoir une taille positive.")
		return issues

	var ground_layer: TileMapLayer = native_layer(LAYER_GROUND)
	if ground_layer == null:
		_add_validation_issue(issues, "error", "La couche Ground est absente.")
	else:
		var expected_ground_cells: int = grid_width * grid_height
		var actual_ground_cells: int = ground_layer.get_used_cells().size()
		if actual_ground_cells < expected_ground_cells:
			_add_validation_issue(
				issues,
				"warning",
				"Ground ne couvre que %d/%d cases." % [actual_ground_cells, expected_ground_cells]
			)

	var environment: Dictionary = to_environment()
	var environment_groups: Array = [
		environment.get("obstacles", []),
		environment.get("cover", []),
		environment.get("hazards", []),
		environment.get("extraction", []),
		environment.get("bonus", []),
	]
	for raw_group: Variant in environment_groups:
		if raw_group is Array:
			for raw_cell: Variant in raw_group:
				if raw_cell is Vector2i:
					var typed_cell: Vector2i = raw_cell
					if not is_cell_valid(typed_cell):
						_add_validation_issue(issues, "error", "Case hors grille : %s" % str(typed_cell), typed_cell)

	var hero_orders: Dictionary = {}
	var hero_count: int = 0
	var terrain_layer: TileMapLayer = native_layer(LAYER_TERRAIN)
	var object_ids: Dictionary = {}
	var map_objects: Array[SporeMapInteractable2D] = []
	var zone_ids: Dictionary = {}
	for node: Node in _descendants(self):
		if node is SporeHeroSpawn2D:
			hero_count += 1
			var hero: SporeHeroSpawn2D = node as SporeHeroSpawn2D
			var hero_cell: Vector2i = local_to_cell(hero.position)
			_validate_editor_node_cell(issues, hero, hero_cell, terrain_layer)
			if hero_orders.has(hero.order):
				_add_validation_issue(
					issues,
					"error",
					"Ordre de spawn héros dupliqué : %d." % hero.order,
					hero_cell,
					get_path_to(hero)
				)
			else:
				hero_orders[hero.order] = true
		elif node is SporeEnemySpawn2D:
			var enemy: SporeEnemySpawn2D = node as SporeEnemySpawn2D
			var enemy_cell: Vector2i = local_to_cell(enemy.position)
			_validate_editor_node_cell(issues, enemy, enemy_cell, terrain_layer)
			if enemy.unit_id.is_empty():
				_add_validation_issue(issues, "error", "%s n'a pas de Unit Id." % enemy.name, enemy_cell, get_path_to(enemy))
			elif not ResourceLoader.exists("res://data/units/%s.tres" % enemy.unit_id):
				_add_validation_issue(issues, "error", "Unité inconnue : %s." % enemy.unit_id, enemy_cell, get_path_to(enemy))
		elif node is SporeMapZone2D:
			var zone: SporeMapZone2D = node as SporeMapZone2D
			var zone_cells: Array[Vector2i] = zone.occupied_cells(self)
			if zone.zone_id.is_empty():
				_add_validation_issue(issues, "error", "%s n'a pas de Zone Id." % zone.name, local_to_cell(zone.position), get_path_to(zone))
			elif zone_ids.has(zone.zone_id):
				_add_validation_issue(issues, "error", "Zone Id dupliqué : %s." % zone.zone_id, local_to_cell(zone.position), get_path_to(zone))
			else:
				zone_ids[zone.zone_id] = zone
			if zone.polygon.size() < 3:
				_add_validation_issue(issues, "error", "%s doit avoir au moins 3 points." % zone.name, local_to_cell(zone.position), get_path_to(zone))
			elif zone_cells.is_empty():
				_add_validation_issue(issues, "warning", "%s ne couvre aucune case de la grille." % zone.name, local_to_cell(zone.position), get_path_to(zone))
		elif node is SporeMapInteractable2D:
			var map_object: SporeMapInteractable2D = node as SporeMapInteractable2D
			map_objects.append(map_object)
			var object_cell: Vector2i = local_to_cell(map_object.position)
			if not is_cell_valid(object_cell):
				_add_validation_issue(issues, "error", "%s est hors grille." % map_object.name, object_cell, get_path_to(map_object))
			if map_object.object_id.is_empty():
				_add_validation_issue(issues, "error", "%s n'a pas d'Object Id." % map_object.name, object_cell, get_path_to(map_object))
			elif object_ids.has(map_object.object_id):
				_add_validation_issue(issues, "error", "Object Id dupliqué : %s." % map_object.object_id, object_cell, get_path_to(map_object))
			else:
				object_ids[map_object.object_id] = map_object

	if hero_count == 0:
		_add_validation_issue(issues, "error", "Aucun spawn héros n'est défini.")

	for map_object: SporeMapInteractable2D in map_objects:
		if map_object.object_type == "switch" and not map_object.linked_object_id.is_empty():
			if not object_ids.has(map_object.linked_object_id):
				_add_validation_issue(
					issues,
					"error",
					"%s pointe vers l'objet inexistant '%s'." % [map_object.name, map_object.linked_object_id],
					local_to_cell(map_object.position),
					get_path_to(map_object)
				)
	return issues


func _validate_editor_node_cell(
	issues: Array[Dictionary],
	node: Node2D,
	cell: Vector2i,
	terrain_layer: TileMapLayer
) -> void:
	if not is_cell_valid(cell):
		_add_validation_issue(issues, "error", "%s est hors grille." % node.name, cell, get_path_to(node))
		return
	if terrain_layer != null and terrain_layer.get_cell_atlas_coords(cell) == TILE_OBSTACLE:
		_add_validation_issue(issues, "warning", "%s est placé sur un obstacle." % node.name, cell, get_path_to(node))


func _add_validation_issue(
	issues: Array[Dictionary],
	severity: String,
	message: String,
	cell: Vector2i = Vector2i(-999, -999),
	node_path: NodePath = NodePath("")
) -> void:
	issues.append({
		"severity": severity,
		"message": message,
		"cell": cell,
		"node_path": node_path,
	})


func validate_map() -> PackedStringArray:
	var messages: PackedStringArray = PackedStringArray()
	for issue: Dictionary in validation_issues():
		messages.append(String(issue.get("message", "Problème de map")))
	return messages


func refresh_editor() -> void:
	queue_redraw()
	for node: Node in _descendants(self):
		if node is CanvasItem:
			(node as CanvasItem).queue_redraw()


func _descendants(parent: Node) -> Array[Node]:
	var result: Array[Node] = []
	for child: Node in parent.get_children():
		result.append(child)
		result.append_array(_descendants(child))
	return result


func _draw() -> void:
	if not show_grid:
		return
	# The actual terrain is drawn by TileMapLayer. This overlay only provides
	# an editor-friendly border and optional coordinates.
	for y: int in range(grid_height):
		for x: int in range(grid_width):
			var rect: Rect2 = Rect2(Vector2(x, y) * cell_size, Vector2.ONE * cell_size)
			draw_rect(rect, Color(0.42, 0.60, 0.72, 0.50), false, 1.0)
			if show_coordinates:
				draw_string(ThemeDB.fallback_font, rect.position + Vector2(4.0, 13.0), "%d,%d" % [x, y], HORIZONTAL_ALIGNMENT_LEFT, -1.0, 9, Color(0.88, 0.95, 1.0, 0.74))
	var total_size: Vector2 = Vector2(float(grid_width), float(grid_height)) * cell_size
	draw_rect(Rect2(Vector2.ZERO, total_size), Color("#9fd6ff"), false, 3.0)
