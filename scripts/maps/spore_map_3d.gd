@tool
class_name SporeMap3D
extends Node3D

## Native 2.5D tactical map authored in Godot's 3D workspace.
##
## Children identify their runtime role through spore_map_role(). The map exposes
## the same data contract as SporeMap2D, so MissionCatalog can consume either.

@export_group("Grid")
@export_range(1, 64, 1) var grid_width: int = 10:
	set(value):
		grid_width = maxi(1, value)
		_refresh_layout_deferred()
@export_range(1, 64, 1) var grid_height: int = 8:
	set(value):
		grid_height = maxi(1, value)
		_refresh_layout_deferred()
@export_range(0.5, 4.0, 0.05) var tile_size: float = 1.4:
	set(value):
		tile_size = maxf(0.5, value)
		_refresh_layout_deferred()
@export_range(0.15, 2.0, 0.05) var elevation_step: float = 0.55:
	set(value):
		elevation_step = maxf(0.15, value)
		_refresh_layout_deferred()

@export_group("Editor preview")
@export var show_cell_coordinates: bool = false:
	set(value):
		show_cell_coordinates = value
		_refresh_layout_deferred()
@export var preview_camera_enabled: bool = true

var _refresh_queued: bool = false
var _marker_refresh_queued: bool = false


func _ready() -> void:
	refresh_layout()
	if not Engine.is_editor_hint() and preview_camera_enabled:
		_configure_preview_camera()


func _refresh_layout_deferred() -> void:
	if not is_inside_tree() or _refresh_queued:
		return
	_refresh_queued = true
	call_deferred("_apply_deferred_refresh")


func _apply_deferred_refresh() -> void:
	_refresh_queued = false
	refresh_layout()


func refresh_layout() -> void:
	for node: Node in _descendants(self):
		if node.has_method("refresh_from_map"):
			node.call("refresh_from_map")


func queue_marker_refresh() -> void:
	if not is_inside_tree() or _marker_refresh_queued:
		return
	_marker_refresh_queued = true
	call_deferred("_apply_marker_refresh")


func _apply_marker_refresh() -> void:
	_marker_refresh_queued = false
	refresh_marker_positions()


func refresh_marker_positions() -> void:
	for node: Node in _descendants(self):
		var role: String = _node_role(node)
		if role in ["hero", "enemy", "interactable"] and node.has_method("refresh_from_map"):
			node.call("refresh_from_map")


func is_cell_valid(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < grid_width and cell.y < grid_height


func cell_to_local(cell: Vector2i, elevation: int = 0) -> Vector3:
	var half_x: float = (float(grid_width) - 1.0) * 0.5
	var half_z: float = (float(grid_height) - 1.0) * 0.5
	return Vector3(
		(float(cell.x) - half_x) * tile_size,
		float(elevation) * elevation_step,
		(float(cell.y) - half_z) * tile_size
	)


func local_to_cell(local_position: Vector3) -> Vector2i:
	var half_x: float = (float(grid_width) - 1.0) * 0.5
	var half_z: float = (float(grid_height) - 1.0) * 0.5
	return Vector2i(
		roundi(local_position.x / tile_size + half_x),
		roundi(local_position.z / tile_size + half_z)
	)


func tile_at(cell: Vector2i) -> Node:
	for node: Node in _descendants(self):
		if _node_role(node) != "tile":
			continue
		var raw_cell: Variant = node.get("cell")
		if raw_cell is Vector2i and raw_cell == cell:
			return node
	return null


func elevation_at(cell: Vector2i) -> int:
	var tile: Node = tile_at(cell)
	return int(tile.get("elevation")) if tile != null else 0


func cell_top_local(cell: Vector2i) -> Vector3:
	return cell_to_local(cell, elevation_at(cell))


func to_environment() -> Dictionary:
	var obstacle_cells: Array[Vector2i] = []
	var cover_cells: Array[Vector2i] = []
	var cover_directions: Dictionary = {}
	var hazard_cells: Array[Vector2i] = []
	var extraction_cells: Array[Vector2i] = []
	var bonus_cells: Array[Vector2i] = []
	var crown_cell: Vector2i = Vector2i(-9, -9)
	var heights: Dictionary = {}

	for node: Node in _descendants(self):
		if _node_role(node) != "tile":
			continue
		var raw_cell: Variant = node.get("cell")
		if not raw_cell is Vector2i:
			continue
		var cell: Vector2i = raw_cell
		if not is_cell_valid(cell):
			continue
		var elevation: int = int(node.get("elevation"))
		var terrain_type: String = String(node.get("terrain_type"))
		if elevation > 0:
			heights[cell] = elevation
		match terrain_type:
			"obstacle":
				obstacle_cells.append(cell)
			"cover":
				cover_cells.append(cell)
				if node.has_method("cover_direction"):
					var raw_cover_direction: Variant = node.call("cover_direction")
					if raw_cover_direction is Vector2i:
						cover_directions[cell] = raw_cover_direction
			"hazard":
				hazard_cells.append(cell)
			"extraction":
				extraction_cells.append(cell)
			"bonus":
				bonus_cells.append(cell)
			"crown":
				crown_cell = cell

	return {
		"obstacles": obstacle_cells,
		"cover": cover_cells,
		"cover_directions": cover_directions,
		"hazards": hazard_cells,
		"extraction": extraction_cells,
		"bonus": bonus_cells,
		"crown": crown_cell,
		"heights": heights,
		"grid_width": grid_width,
		"grid_height": grid_height,
		"zones": [],
	}


func hero_start_cells() -> Array[Vector2i]:
	var entries: Array[Dictionary] = []
	for node: Node in _descendants(self):
		if _node_role(node) != "hero":
			continue
		var raw_cell: Variant = node.get("cell")
		if raw_cell is Vector2i:
			entries.append({"order": int(node.get("order")), "cell": raw_cell})
	entries.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["order"]) < int(b["order"]))
	var result: Array[Vector2i] = []
	for entry: Dictionary in entries:
		var raw_cell: Variant = entry.get("cell", Vector2i.ZERO)
		if raw_cell is Vector2i:
			result.append(raw_cell)
	return result


func enemy_spawn_data() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for node: Node in _descendants(self):
		if _node_role(node) != "enemy":
			continue
		result.append({
			"unit_id": String(node.get("unit_id")),
			"cell": node.get("cell"),
			"role": String(node.get("role_override")),
			"hp": int(node.get("hp_override")),
			"attack": int(node.get("attack_override")),
			"move": int(node.get("move_override")),
			"range": int(node.get("range_override")),
		})
	return result


func interactable_definitions() -> Array[Resource]:
	var result: Array[Resource] = []
	for node: Node in _descendants(self):
		if _node_role(node) != "interactable" or not node.has_method("to_definition"):
			continue
		var raw_definition: Variant = node.call("to_definition")
		if raw_definition is Resource:
			result.append(raw_definition)
	return result


func editor_stats() -> Dictionary:
	var tile_count: int = 0
	var hero_count: int = 0
	var enemy_count: int = 0
	var interactable_count: int = 0
	for node: Node in _descendants(self):
		match _node_role(node):
			"tile":
				tile_count += 1
			"hero":
				hero_count += 1
			"enemy":
				enemy_count += 1
			"interactable":
				interactable_count += 1
	return {
		"tiles": tile_count,
		"heroes": hero_count,
		"enemies": enemy_count,
		"interactables": interactable_count,
	}


func validation_issues() -> Array[Dictionary]:
	var issues: Array[Dictionary] = []
	var seen_cells: Dictionary = {}
	var hero_orders: Dictionary = {}
	var object_ids: Dictionary = {}
	var hero_count: int = 0

	for node: Node in _descendants(self):
		var role: String = _node_role(node)
		var raw_cell: Variant = node.get("cell") if role in ["tile", "hero", "enemy", "interactable"] else null
		var cell: Vector2i = Vector2i(-99, -99)
		if raw_cell is Vector2i:
			cell = raw_cell
		match role:
			"tile":
				if not is_cell_valid(cell):
					issues.append({"severity": "error", "message": "%s est hors grille." % node.name, "cell": cell})
				elif seen_cells.has(cell):
					issues.append({"severity": "error", "message": "Case dupliquée : %s." % str(cell), "cell": cell})
				else:
					seen_cells[cell] = true
			"hero":
				hero_count += 1
				var order: int = int(node.get("order"))
				if hero_orders.has(order):
					issues.append({"severity": "error", "message": "Ordre héros dupliqué : %d." % order, "cell": cell})
				else:
					hero_orders[order] = true
			"enemy":
				if String(node.get("unit_id")).is_empty():
					issues.append({"severity": "error", "message": "%s n'a pas de Unit Id." % node.name, "cell": cell})
			"interactable":
				var object_id: String = String(node.get("object_id"))
				if object_id.is_empty():
					issues.append({"severity": "error", "message": "%s n'a pas d'Object Id." % node.name, "cell": cell})
				elif object_ids.has(object_id):
					issues.append({"severity": "error", "message": "Object Id dupliqué : %s." % object_id, "cell": cell})
				else:
					object_ids[object_id] = true

	if seen_cells.size() < grid_width * grid_height:
		issues.append({
			"severity": "warning",
			"message": "La map contient %d/%d cases." % [seen_cells.size(), grid_width * grid_height],
		})
	if hero_count == 0:
		issues.append({"severity": "error", "message": "Aucun spawn héros n'est défini."})
	return issues


func _configure_preview_camera() -> void:
	var camera: Camera3D = get_node_or_null("PreviewRig/Camera3D") as Camera3D
	if camera == null:
		return
	camera.current = true
	camera.look_at(global_position, Vector3.UP)


func _node_role(node: Node) -> String:
	if node == null or not node.has_method("spore_map_role"):
		return ""
	return String(node.call("spore_map_role"))


func _descendants(root: Node) -> Array[Node]:
	var result: Array[Node] = []
	for child: Node in root.get_children():
		result.append(child)
		result.append_array(_descendants(child))
	return result
