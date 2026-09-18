class_name SporeMissionDressing3D
extends Node3D

## Runtime visual dressing for the tactical board.
## Everything here is non-gameplay decoration: a diorama base and forest props
## around the authored grid, so tactical readability stays intact.

const EARTH := Color("#29261f")
const EARTH_EDGE := Color("#171914")
const MOSS := Color("#39563b")
const MOSS_LIGHT := Color("#53724b")
const CAP_RED := Color("#d85f5d")
const CAP_BLUE := Color("#5da7c8")
const CAP_GOLD := Color("#e2b85c")
const CRYSTAL := Color("#8c70dc")

var _rng: RandomNumberGenerator = RandomNumberGenerator.new()


func build_for_map(map: SporeMap3D) -> void:
	_clear_children()
	if map == null:
		return
	_rng.seed = 0x5A0B0D
	_build_diorama_base(map)
	_build_perimeter_props(map)


func _clear_children() -> void:
	for child: Node in get_children():
		child.free()


func _build_diorama_base(map: SporeMap3D) -> void:
	var width: float = float(map.grid_width) * map.tile_size
	var depth: float = float(map.grid_height) * map.tile_size

	var soil: MeshInstance3D = _box(
		Vector3(width + 1.9, 0.54, depth + 1.9),
		Vector3(0.0, -0.59, 0.0),
		EARTH,
		0.98
	)
	soil.name = "DioramaSoil"
	add_child(soil)

	var lower: MeshInstance3D = _box(
		Vector3(width + 2.35, 0.38, depth + 2.35),
		Vector3(0.0, -0.97, 0.0),
		EARTH_EDGE,
		1.0
	)
	lower.name = "DioramaShadowBase"
	add_child(lower)

	var moss_lip: MeshInstance3D = _box(
		Vector3(width + 1.55, 0.08, depth + 1.55),
		Vector3(0.0, -0.30, 0.0),
		MOSS.darkened(0.08),
		0.94
	)
	moss_lip.name = "MossLip"
	add_child(moss_lip)


func _build_perimeter_props(map: SporeMap3D) -> void:
	var half_x: float = float(map.grid_width) * map.tile_size * 0.5 + 0.70
	var half_z: float = float(map.grid_height) * map.tile_size * 0.5 + 0.70
	var count: int = 30
	for index: int in range(count):
		var side: int = index % 4
		var position_value: Vector3 = Vector3.ZERO
		if side == 0:
			position_value = Vector3(_rng.randf_range(-half_x, half_x), -0.22, -half_z - _rng.randf_range(0.10, 0.65))
		elif side == 1:
			position_value = Vector3(half_x + _rng.randf_range(0.10, 0.65), -0.22, _rng.randf_range(-half_z, half_z))
		elif side == 2:
			position_value = Vector3(_rng.randf_range(-half_x, half_x), -0.22, half_z + _rng.randf_range(0.10, 0.65))
		else:
			position_value = Vector3(-half_x - _rng.randf_range(0.10, 0.65), -0.22, _rng.randf_range(-half_z, half_z))

		var selector: int = (index * 7 + 3) % 10
		if selector <= 4:
			_build_mushroom_cluster(position_value, index)
		elif selector <= 7:
			_build_rock_cluster(position_value, index)
		else:
			_build_crystal_cluster(position_value, index)


func _build_mushroom_cluster(origin: Vector3, index: int) -> void:
	var cluster: Node3D = Node3D.new()
	cluster.name = "MushroomCluster_%02d" % index
	cluster.position = origin
	cluster.rotation.y = _rng.randf_range(-PI, PI)
	add_child(cluster)
	var mushroom_count: int = 2 + (index % 3)
	for mushroom_index: int in range(mushroom_count):
		var local_offset: Vector3 = Vector3(
			_rng.randf_range(-0.26, 0.26),
			0.0,
			_rng.randf_range(-0.22, 0.22)
		)
		var height: float = _rng.randf_range(0.26, 0.52)
		var scale_value: float = _rng.randf_range(0.72, 1.18)
		var stem: MeshInstance3D = _cylinder(0.055 * scale_value, 0.080 * scale_value, height, Color("#dfd3ad"), 0.96)
		stem.position = local_offset + Vector3(0.0, height * 0.5, 0.0)
		cluster.add_child(stem)

		var cap_color: Color = CAP_RED
		var palette_index: int = (index + mushroom_index) % 3
		if palette_index == 1:
			cap_color = CAP_BLUE
		elif palette_index == 2:
			cap_color = CAP_GOLD
		var cap: MeshInstance3D = _sphere(Vector3(0.23, 0.10, 0.23) * scale_value, cap_color, 0.88)
		cap.position = local_offset + Vector3(0.0, height + 0.025, 0.0)
		cluster.add_child(cap)

	var moss: MeshInstance3D = _sphere(Vector3(0.36, 0.08, 0.30), MOSS_LIGHT.darkened(0.08), 1.0)
	moss.position = Vector3(0.0, 0.02, 0.0)
	cluster.add_child(moss)


func _build_rock_cluster(origin: Vector3, index: int) -> void:
	var cluster: Node3D = Node3D.new()
	cluster.name = "RockCluster_%02d" % index
	cluster.position = origin
	cluster.rotation.y = _rng.randf_range(-PI, PI)
	add_child(cluster)
	for rock_index: int in range(2 + (index % 2)):
		var rock_color: Color = Color("#5f6559").lightened(float(rock_index) * 0.04)
		var rock: MeshInstance3D = _sphere(
			Vector3(_rng.randf_range(0.18, 0.35), _rng.randf_range(0.12, 0.24), _rng.randf_range(0.18, 0.32)),
			rock_color,
			0.98
		)
		rock.position = Vector3(_rng.randf_range(-0.23, 0.23), 0.10, _rng.randf_range(-0.18, 0.18))
		cluster.add_child(rock)


func _build_crystal_cluster(origin: Vector3, index: int) -> void:
	var cluster: Node3D = Node3D.new()
	cluster.name = "CrystalCluster_%02d" % index
	cluster.position = origin
	cluster.rotation.y = _rng.randf_range(-PI, PI)
	add_child(cluster)
	for crystal_index: int in range(3):
		var height: float = 0.30 + float(crystal_index) * 0.10
		var crystal: MeshInstance3D = _cylinder(0.025, 0.105, height, CRYSTAL.lightened(float(crystal_index) * 0.06), 0.50, true)
		crystal.position = Vector3(float(crystal_index - 1) * 0.13, height * 0.5, float((crystal_index % 2) * 2 - 1) * 0.06)
		crystal.rotation.z = float(crystal_index - 1) * 0.14
		cluster.add_child(crystal)


func _box(size_value: Vector3, position_value: Vector3, color: Color, roughness: float) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = size_value
	instance.mesh = mesh
	instance.position = position_value
	instance.material_override = _material(color, roughness)
	return instance


func _sphere(scale_value: Vector3, color: Color, roughness: float) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 12
	mesh.rings = 6
	instance.mesh = mesh
	instance.scale = scale_value * 2.0
	instance.material_override = _material(color, roughness)
	return instance


func _cylinder(top_radius: float, bottom_radius: float, height: float, color: Color, roughness: float, emissive: bool = false) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = top_radius
	mesh.bottom_radius = bottom_radius
	mesh.height = height
	mesh.radial_segments = 8
	instance.mesh = mesh
	instance.material_override = _material(color, roughness, emissive)
	return instance


func _material(color: Color, roughness: float, emissive: bool = false) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	if emissive:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.26
	return material
