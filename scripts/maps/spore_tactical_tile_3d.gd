@tool
class_name SporeTacticalTile3D
extends Node3D

## Editable logical cell of a SporeMap3D.
## The generated mesh is deliberately stylized as a compact forest diorama:
## readable tactical colors, softer earth sides and small non-blocking details.

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

	var inset: MeshInstance3D = get_node_or_null("_EditorInset") as MeshInstance3D
	if inset == null:
		inset = MeshInstance3D.new()
		inset.name = "_EditorInset"
		add_child(inset, false, Node.INTERNAL_MODE_BACK)

	var total_height: float = 0.24 + float(elevation) * map.elevation_step
	var body_mesh: BoxMesh = BoxMesh.new()
	body_mesh.size = Vector3(map.tile_size * 0.97, total_height, map.tile_size * 0.97)
	body.mesh = body_mesh
	body.position = Vector3(0.0, -total_height * 0.5 - 0.025, 0.0)
	body.material_override = _material(_side_color(), 0.98)

	var top_mesh: BoxMesh = BoxMesh.new()
	top_mesh.size = Vector3(map.tile_size * 0.93, 0.075, map.tile_size * 0.93)
	top.mesh = top_mesh
	top.position = Vector3(0.0, -0.036, 0.0)
	top.material_override = _material(_top_color(), 0.93, _terrain_emissive())

	var inset_mesh: BoxMesh = BoxMesh.new()
	inset_mesh.size = Vector3(map.tile_size * 0.78, 0.022, map.tile_size * 0.78)
	inset.mesh = inset_mesh
	inset.position = Vector3(0.0, 0.012, 0.0)
	inset.material_override = _material(_inset_color(), 0.96, _terrain_emissive())

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
	label.visible = Engine.is_editor_hint() and not text.is_empty()
	label.position = Vector3(0.0, 0.28, 0.0)

	_rebuild_ground_details(map)
	_rebuild_terrain_prop(map)


func _rebuild_ground_details(map: SporeMap3D) -> void:
	var root: Node3D = _detail_root("_EditorGroundDetailRoot")
	_clear_children(root)
	if terrain_type != "ground" or ((cell.x * 17 + cell.y * 11) % 7) > 1:
		return
	var sign_x: float = -1.0 if ((cell.x + cell.y) % 2) == 0 else 1.0
	var sign_z: float = -1.0 if ((cell.x * 3 + cell.y) % 2) == 0 else 1.0
	var stone: MeshInstance3D = _sphere_mesh(Vector3(0.12, 0.055, 0.10), Color("#69705f"), 1.0)
	stone.position = Vector3(sign_x * map.tile_size * 0.28, 0.055, sign_z * map.tile_size * 0.26)
	root.add_child(stone)
	if ((cell.x + cell.y * 3) % 4) == 0:
		var stem: MeshInstance3D = _cylinder_mesh(0.025, 0.035, 0.13, Color("#d8cba8"), 0.96)
		stem.position = Vector3(-sign_x * map.tile_size * 0.24, 0.065, sign_z * map.tile_size * 0.20)
		root.add_child(stem)
		var cap: MeshInstance3D = _sphere_mesh(Vector3(0.10, 0.045, 0.10), Color("#cf665f"), 0.90)
		cap.position = stem.position + Vector3(0.0, 0.10, 0.0)
		root.add_child(cap)


func _rebuild_terrain_prop(map: SporeMap3D) -> void:
	var prop: MeshInstance3D = get_node_or_null("_EditorProp") as MeshInstance3D
	if prop == null:
		prop = MeshInstance3D.new()
		prop.name = "_EditorProp"
		add_child(prop, false, Node.INTERNAL_MODE_BACK)
	var special_root: Node3D = _detail_root("_EditorSpecialRoot")
	_clear_children(special_root)
	prop.visible = terrain_type in ["obstacle", "cover", "hazard", "bonus", "crown"]
	prop.rotation = Vector3.ZERO
	prop.position = Vector3.ZERO
	prop.scale = Vector3.ONE
	if not prop.visible:
		prop.mesh = null
		if terrain_type == "extraction":
			_build_extraction_details(map, special_root)
		return

	match terrain_type:
		"obstacle":
			var obstacle_mesh: BoxMesh = BoxMesh.new()
			obstacle_mesh.size = Vector3(map.tile_size * 0.50, 0.72, map.tile_size * 0.46)
			prop.mesh = obstacle_mesh
			prop.position = Vector3(-0.04, 0.36, 0.02)
			prop.rotation = Vector3(0.08, float((cell.x + cell.y) % 3 - 1) * 0.16, -0.05)
			prop.material_override = _material(Color("#5d6153"), 1.0)
			var rock_a: MeshInstance3D = _sphere_mesh(Vector3(0.24, 0.17, 0.21), Color("#707466"), 1.0)
			rock_a.position = Vector3(0.23, 0.17, -0.16)
			special_root.add_child(rock_a)
			var rock_b: MeshInstance3D = _sphere_mesh(Vector3(0.18, 0.12, 0.16), Color("#4e5549"), 1.0)
			rock_b.position = Vector3(-0.26, 0.12, 0.19)
			special_root.add_child(rock_b)
		"cover":
			var cover_mesh: BoxMesh = BoxMesh.new()
			cover_mesh.size = Vector3(map.tile_size * 0.68, 0.30, map.tile_size * 0.17)
			prop.mesh = cover_mesh
			prop.position.y = 0.16
			prop.rotation.y = PI * 0.5 if cover_facing in ["east", "west"] else 0.0
			var offset: Vector2i = _cover_direction()
			prop.position.x = float(offset.x) * map.tile_size * 0.28
			prop.position.z = float(offset.y) * map.tile_size * 0.28
			prop.material_override = _material(Color("#916e46"), 0.98)
			_build_cover_posts(map, special_root, prop.position, prop.rotation.y)
		"hazard":
			var hazard_mesh: CylinderMesh = CylinderMesh.new()
			hazard_mesh.top_radius = map.tile_size * 0.31
			hazard_mesh.bottom_radius = map.tile_size * 0.37
			hazard_mesh.height = 0.065
			hazard_mesh.radial_segments = 16
			prop.mesh = hazard_mesh
			prop.position.y = 0.035
			prop.material_override = _material(Color(0.62, 0.28, 0.86, 0.72), 0.42, true)
			_build_hazard_spores(map, special_root)
		"bonus":
			var vinyl_mesh: CylinderMesh = CylinderMesh.new()
			vinyl_mesh.top_radius = 0.23
			vinyl_mesh.bottom_radius = 0.23
			vinyl_mesh.height = 0.055
			vinyl_mesh.radial_segments = 24
			prop.mesh = vinyl_mesh
			prop.position.y = 0.065
			prop.material_override = _material(Color("#20242b"), 0.42)
			var center: MeshInstance3D = _cylinder_mesh(0.075, 0.075, 0.024, Color("#54c8ed"), 0.46, true)
			center.position.y = 0.102
			special_root.add_child(center)
		"crown":
			var crown_base: CylinderMesh = CylinderMesh.new()
			crown_base.top_radius = 0.17
			crown_base.bottom_radius = 0.27
			crown_base.height = 0.24
			crown_base.radial_segments = 10
			prop.mesh = crown_base
			prop.position.y = 0.14
			prop.material_override = _material(Color("#e6b94e"), 0.35, true)
			_build_crown_spikes(special_root)


func _build_cover_posts(map: SporeMap3D, root: Node3D, base_position: Vector3, rotation_y: float) -> void:
	for side_value: Variant in [-1, 1]:
		var side: int = int(side_value)
		var post: MeshInstance3D = _box_mesh(Vector3(0.10, 0.38, 0.10), Color("#5f4934"), 1.0)
		var local_offset: Vector3 = Vector3(float(side) * map.tile_size * 0.26, 0.18, 0.0)
		local_offset = local_offset.rotated(Vector3.UP, rotation_y)
		post.position = base_position + local_offset
		root.add_child(post)


func _build_hazard_spores(map: SporeMap3D, root: Node3D) -> void:
	for index: int in range(3):
		var angle: float = TAU * float(index) / 3.0 + float(cell.x + cell.y) * 0.27
		var orb: MeshInstance3D = _sphere_mesh(Vector3(0.055, 0.055, 0.055), Color("#d899ff"), 0.34, true)
		orb.position = Vector3(cos(angle) * map.tile_size * 0.22, 0.15 + float(index) * 0.035, sin(angle) * map.tile_size * 0.22)
		root.add_child(orb)


func _build_extraction_details(map: SporeMap3D, root: Node3D) -> void:
	var offsets: Array[Vector3] = [
		Vector3(-1.0, 0.0, -1.0),
		Vector3(1.0, 0.0, -1.0),
		Vector3(-1.0, 0.0, 1.0),
		Vector3(1.0, 0.0, 1.0),
	]
	for offset: Vector3 in offsets:
		var beacon: MeshInstance3D = _cylinder_mesh(0.035, 0.055, 0.11, Color("#66e19a"), 0.42, true)
		beacon.position = Vector3(offset.x * map.tile_size * 0.33, 0.06, offset.z * map.tile_size * 0.33)
		root.add_child(beacon)


func _build_crown_spikes(root: Node3D) -> void:
	for index: int in range(5):
		var angle: float = TAU * float(index) / 5.0
		var spike: MeshInstance3D = _cylinder_mesh(0.015, 0.055, 0.22, Color("#ffd86c"), 0.30, true)
		spike.position = Vector3(cos(angle) * 0.14, 0.30, sin(angle) * 0.14)
		spike.rotation.z = cos(angle) * 0.10
		spike.rotation.x = sin(angle) * 0.10
		root.add_child(spike)


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


func _detail_root(node_name: String) -> Node3D:
	var root: Node3D = get_node_or_null(node_name) as Node3D
	if root == null:
		root = Node3D.new()
		root.name = node_name
		add_child(root, false, Node.INTERNAL_MODE_BACK)
	return root


func _clear_children(root: Node3D) -> void:
	if root == null:
		return
	for child: Node in root.get_children():
		child.free()


func _box_mesh(size_value: Vector3, color: Color, roughness: float, emissive: bool = false) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = size_value
	instance.mesh = mesh
	instance.material_override = _material(color, roughness, emissive)
	return instance


func _sphere_mesh(scale_value: Vector3, color: Color, roughness: float, emissive: bool = false) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 10
	mesh.rings = 5
	instance.mesh = mesh
	instance.scale = scale_value * 2.0
	instance.material_override = _material(color, roughness, emissive)
	return instance


func _cylinder_mesh(top_radius: float, bottom_radius: float, height: float, color: Color, roughness: float, emissive: bool = false) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = top_radius
	mesh.bottom_radius = bottom_radius
	mesh.height = height
	mesh.radial_segments = 12
	instance.mesh = mesh
	instance.material_override = _material(color, roughness, emissive)
	return instance


func _material(color: Color, roughness: float, emissive: bool = false) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	if color.a < 0.999:
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if emissive:
		material.emission_enabled = true
		material.emission = Color(color.r, color.g, color.b, 1.0)
		material.emission_energy_multiplier = 0.20
	return material


func _top_color() -> Color:
	match terrain_type:
		"obstacle":
			return Color("#545b4e")
		"cover":
			return Color("#7f6848")
		"hazard":
			return Color("#8552a8")
		"extraction":
			return Color("#44855d")
		"bonus":
			return Color("#4d7f8e")
		"crown":
			return Color("#a78947")
		_:
			var variation: float = float((cell.x * 5 + cell.y * 3) % 4) * 0.018
			var height_lift: float = minf(0.10, float(elevation) * 0.035)
			return Color(0.27 + variation + height_lift, 0.43 + variation + height_lift, 0.25 + variation, 1.0)


func _inset_color() -> Color:
	var base: Color = _top_color()
	if terrain_type == "ground":
		return base.lightened(0.06)
	if terrain_type in ["hazard", "extraction", "bonus", "crown"]:
		return base.lightened(0.10)
	return base.lightened(0.035)


func _side_color() -> Color:
	if terrain_type in ["hazard", "extraction", "bonus", "crown"]:
		return Color("#353529")
	return Color("#3b392f").lightened(minf(0.05, float(elevation) * 0.012))


func _terrain_emissive() -> bool:
	return terrain_type in ["hazard", "extraction", "bonus", "crown"]


func _map_parent() -> SporeMap3D:
	var node: Node = get_parent()
	while node != null:
		if node is SporeMap3D:
			return node as SporeMap3D
		node = node.get_parent()
	return null
