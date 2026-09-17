@tool
class_name SporeTacticalTile3D
extends Node3D

## One editable logical cell of a SporeMap3D.
## Cell/elevation/type are the authored data; the colored block is generated
## automatically in the editor so the scene remains asset-free and portable.

@export_group("Cell")
@export var cell: Vector2i = Vector2i.ZERO:
	set(value):
		cell = value
		_refresh_deferred()
@export_range(0, 8, 1) var elevation: int = 0:
	set(value):
		elevation = maxi(0, value)
		_refresh_deferred()
@export_enum("ground", "obstacle", "cover", "hazard", "extraction", "bonus", "crown") var terrain_type: String = "ground":
	set(value):
		terrain_type = value
		_refresh_deferred()
@export_enum("north", "east", "south", "west") var cover_facing: String = "north":
	set(value):
		cover_facing = value
		_refresh_deferred()

@export_group("Visual")
@export var display_label: String = "":
	set(value):
		display_label = value
		_refresh_deferred()

var _refresh_queued: bool = false


func spore_map_role() -> String:
	return "tile"


func _ready() -> void:
	refresh_from_map()


func _refresh_deferred() -> void:
	if not is_inside_tree() or _refresh_queued:
		return
	_refresh_queued = true
	call_deferred("_apply_refresh")


func _apply_refresh() -> void:
	_refresh_queued = false
	refresh_from_map()


func refresh_from_map() -> void:
	var map: SporeMap3D = _map_parent()
	if map == null:
		return
	position = map.cell_to_local(cell, elevation)
	_rebuild_visual(map)
	map.queue_marker_refresh()


func _rebuild_visual(map: SporeMap3D) -> void:
	var body: MeshInstance3D = get_node_or_null("_EditorBody") as MeshInstance3D
	if body == null:
		body = MeshInstance3D.new()
		body.name = "_EditorBody"
		add_child(body, false, Node.INTERNAL_MODE_BACK)

	var top: MeshInstance3D = get_node_or_null("_EditorTop") as MeshInstance3D
	if top == null:
		top = MeshInstance3D.new()
		top.name = "_EditorTop"
		add_child(top, false, Node.INTERNAL_MODE_BACK)

	var total_height: float = 0.22 + float(elevation) * map.elevation_step
	var body_mesh: BoxMesh = BoxMesh.new()
	body_mesh.size = Vector3(map.tile_size * 0.94, total_height, map.tile_size * 0.94)
	body.mesh = body_mesh
	body.position = Vector3(0.0, -total_height * 0.5 - 0.02, 0.0)
	body.material_override = _material(_side_color())

	var top_mesh: BoxMesh = BoxMesh.new()
	top_mesh.size = Vector3(map.tile_size * 0.90, 0.08, map.tile_size * 0.90)
	top.mesh = top_mesh
	top.position = Vector3(0.0, -0.04, 0.0)
	top.material_override = _material(_top_color())

	var label: Label3D = get_node_or_null("_EditorLabel") as Label3D
	if label == null:
		label = Label3D.new()
		label.name = "_EditorLabel"
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.font_size = 28
		label.outline_size = 6
		add_child(label, false, Node.INTERNAL_MODE_BACK)
	var text: String = display_label
	if text.is_empty() and map.show_cell_coordinates:
		text = "%d,%d  h%d" % [cell.x, cell.y, elevation]
	label.text = text
	label.visible = not text.is_empty()
	label.position = Vector3(0.0, 0.22, 0.0)
	_rebuild_terrain_prop(map)


func _rebuild_terrain_prop(map: SporeMap3D) -> void:
	var prop: MeshInstance3D = get_node_or_null("_EditorProp") as MeshInstance3D
	if prop == null:
		prop = MeshInstance3D.new()
		prop.name = "_EditorProp"
		add_child(prop, false, Node.INTERNAL_MODE_BACK)
	prop.visible = terrain_type in ["obstacle", "cover", "hazard", "bonus", "crown"]
	prop.rotation = Vector3.ZERO
	prop.position = Vector3.ZERO
	if not prop.visible:
		prop.mesh = null
		return

	var color: Color = _top_color().lightened(0.08)
	match terrain_type:
		"obstacle":
			var obstacle_mesh: BoxMesh = BoxMesh.new()
			obstacle_mesh.size = Vector3(map.tile_size * 0.58, 0.92, map.tile_size * 0.58)
			prop.mesh = obstacle_mesh
			prop.position.y = 0.46
		"cover":
			var cover_mesh: BoxMesh = BoxMesh.new()
			cover_mesh.size = Vector3(map.tile_size * 0.70, 0.38, map.tile_size * 0.20)
			prop.mesh = cover_mesh
			prop.position.y = 0.19
			prop.rotation.y = PI * 0.5 if cover_facing in ["east", "west"] else 0.0
			var offset: Vector2i = _cover_direction()
			prop.position.x = float(offset.x) * map.tile_size * 0.28
			prop.position.z = float(offset.y) * map.tile_size * 0.28
		"hazard":
			var hazard_mesh: CylinderMesh = CylinderMesh.new()
			hazard_mesh.top_radius = map.tile_size * 0.30
			hazard_mesh.bottom_radius = map.tile_size * 0.36
			hazard_mesh.height = 0.10
			prop.mesh = hazard_mesh
			prop.position.y = 0.05
		"bonus":
			var bonus_mesh: CylinderMesh = CylinderMesh.new()
			bonus_mesh.top_radius = 0.18
			bonus_mesh.bottom_radius = 0.18
			bonus_mesh.height = 0.12
			prop.mesh = bonus_mesh
			prop.rotation.z = PI * 0.5
			prop.position.y = 0.32
		"crown":
			var crown_mesh: CylinderMesh = CylinderMesh.new()
			crown_mesh.top_radius = 0.18
			crown_mesh.bottom_radius = 0.30
			crown_mesh.height = 0.42
			prop.mesh = crown_mesh
			prop.position.y = 0.23
	prop.material_override = _material(color)


func cover_direction() -> Vector2i:
	return _cover_direction()


func _cover_direction() -> Vector2i:
	match cover_facing:
		"east":
			return Vector2i.RIGHT
		"south":
			return Vector2i.DOWN
		"west":
			return Vector2i.LEFT
	return Vector2i.UP


func _material(color: Color) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.9
	return material


func _top_color() -> Color:
	match terrain_type:
		"obstacle":
			return Color("#5c5143")
		"cover":
			return Color("#8d7145")
		"hazard":
			return Color("#b95cff")
		"extraction":
			return Color("#51d88a")
		"bonus":
			return Color("#4ec8ff")
		"crown":
			return Color("#ffd45c")
		_:
			var shade: float = minf(0.12, float(elevation) * 0.035)
			return Color(0.34 + shade, 0.56 + shade, 0.30 + shade, 1.0)


func _side_color() -> Color:
	return _top_color().darkened(0.26)


func _map_parent() -> SporeMap3D:
	var node: Node = get_parent()
	while node != null:
		if node is SporeMap3D:
			return node as SporeMap3D
		node = node.get_parent()
	return null
