class_name SporeMissionDressing3D
extends Node3D

## Non-gameplay forest dressing for the tactical board.
## Tall props stay outside the playable grid; inside props stay low and near corners.

const EARTH: Color = Color("#29261f")
const EARTH_EDGE: Color = Color("#171914")
const MOSS: Color = Color("#39563b")
const MOSS_LIGHT: Color = Color("#53724b")
const TRUNK: Color = Color("#5a4432")
const TRUNK_DARK: Color = Color("#3b3027")
const LEAF: Color = Color("#375a3d")
const LEAF_LIGHT: Color = Color("#4d7449")
const CAP_RED: Color = Color("#d85f5d")
const CAP_BLUE: Color = Color("#5da7c8")
const CAP_GOLD: Color = Color("#e2b85c")
const CRYSTAL: Color = Color("#8c70dc")
const GRASS_A: Color = Color("#4c7045")
const GRASS_B: Color = Color("#668650")

var _rng: RandomNumberGenerator = RandomNumberGenerator.new()


func build_for_map(map: SporeMap3D) -> void:
	_clear_children()
	if map == null:
		return
	_rng.seed = 0x5A0B0D
	_build_diorama_base(map)
	_build_perimeter_forest(map)
	_build_inside_ground_details(map)
	_build_fireflies(map)


func _clear_children() -> void:
	for child: Node in get_children():
		child.free()


func _build_diorama_base(map: SporeMap3D) -> void:
	var width: float = float(map.grid_width) * map.tile_size
	var depth: float = float(map.grid_height) * map.tile_size

	var soil: MeshInstance3D = _box(
		Vector3(width + 2.1, 0.60, depth + 2.1),
		Vector3(0.0, -0.62, 0.0),
		EARTH,
		0.98
	)
	soil.name = "DioramaSoil"
	add_child(soil)

	var lower: MeshInstance3D = _box(
		Vector3(width + 2.65, 0.44, depth + 2.65),
		Vector3(0.0, -1.02, 0.0),
		EARTH_EDGE,
		1.0
	)
	lower.name = "DioramaShadowBase"
	add_child(lower)

	var moss_lip: MeshInstance3D = _box(
		Vector3(width + 1.75, 0.09, depth + 1.75),
		Vector3(0.0, -0.305, 0.0),
		MOSS.darkened(0.08),
		0.94
	)
	moss_lip.name = "MossLip"
	add_child(moss_lip)


func _build_perimeter_forest(map: SporeMap3D) -> void:
	var half_x: float = float(map.grid_width) * map.tile_size * 0.5 + 0.86
	var half_z: float = float(map.grid_height) * map.tile_size * 0.5 + 0.86
	var prop_count: int = 42

	for index: int in range(prop_count):
		var side: int = index % 4
		var position_value: Vector3 = Vector3.ZERO

		if side == 0:
			position_value = Vector3(
				_rng.randf_range(-half_x, half_x),
				-0.22,
				-half_z - _rng.randf_range(0.12, 1.10)
			)
		elif side == 1:
			position_value = Vector3(
				half_x + _rng.randf_range(0.12, 1.10),
				-0.22,
				_rng.randf_range(-half_z, half_z)
			)
		elif side == 2:
			position_value = Vector3(
				_rng.randf_range(-half_x, half_x),
				-0.22,
				half_z + _rng.randf_range(0.12, 1.10)
			)
		else:
			position_value = Vector3(
				-half_x - _rng.randf_range(0.12, 1.10),
				-0.22,
				_rng.randf_range(-half_z, half_z)
			)

		var selector: int = (index * 11 + 5) % 16
		if selector <= 4:
			_build_tree_cluster(position_value, index)
		elif selector <= 8:
			_build_mushroom_cluster(position_value, index)
		elif selector <= 12:
			_build_rock_cluster(position_value, index)
		elif selector <= 14:
			_build_fallen_log(position_value, index)
		else:
			_build_crystal_cluster(position_value, index)


func _build_tree_cluster(origin: Vector3, index: int) -> void:
	var cluster: Node3D = Node3D.new()
	cluster.name = "TreeCluster_%02d" % index
	cluster.position = origin
	cluster.rotation.y = _rng.randf_range(-PI, PI)
	add_child(cluster)

	var tree_count: int = 1 + (index % 2)
	for tree_index: int in range(tree_count):
		var local_offset: Vector3 = Vector3(
			_rng.randf_range(-0.30, 0.30),
			0.0,
			_rng.randf_range(-0.26, 0.26)
		)
		var height: float = _rng.randf_range(1.35, 2.15)
		var trunk_radius: float = _rng.randf_range(0.10, 0.16)

		var trunk: MeshInstance3D = _cylinder(
			trunk_radius * 0.78,
			trunk_radius,
			height,
			TRUNK.lightened(_rng.randf_range(-0.04, 0.05)),
			1.0
		)
		trunk.position = local_offset + Vector3(0.0, height * 0.5, 0.0)
		trunk.rotation.z = _rng.randf_range(-0.05, 0.05)
		cluster.add_child(trunk)

		var canopy_color: Color = LEAF if (index + tree_index) % 2 == 0 else LEAF_LIGHT
		var crown_low: MeshInstance3D = _sphere(
			Vector3(
				_rng.randf_range(0.55, 0.76),
				_rng.randf_range(0.35, 0.52),
				_rng.randf_range(0.55, 0.76)
			),
			canopy_color,
			0.95
		)
		crown_low.position = local_offset + Vector3(0.0, height * 0.83, 0.0)
		cluster.add_child(crown_low)

		var crown_high: MeshInstance3D = _sphere(
			Vector3(
				_rng.randf_range(0.40, 0.62),
				_rng.randf_range(0.30, 0.45),
				_rng.randf_range(0.40, 0.62)
			),
			canopy_color.lightened(0.05),
			0.95
		)
		crown_high.position = local_offset + Vector3(
			_rng.randf_range(-0.12, 0.12),
			height * 1.08,
			_rng.randf_range(-0.12, 0.12)
		)
		cluster.add_child(crown_high)

	var root_moss: MeshInstance3D = _sphere(
		Vector3(0.48, 0.07, 0.42),
		MOSS.darkened(0.02),
		1.0
	)
	root_moss.position = Vector3(0.0, 0.03, 0.0)
	cluster.add_child(root_moss)


func _build_mushroom_cluster(origin: Vector3, index: int) -> void:
	var cluster: Node3D = Node3D.new()
	cluster.name = "MushroomCluster_%02d" % index
	cluster.position = origin
	cluster.rotation.y = _rng.randf_range(-PI, PI)
	add_child(cluster)

	var mushroom_count: int = 3 + (index % 4)
	for mushroom_index: int in range(mushroom_count):
		var local_offset: Vector3 = Vector3(
			_rng.randf_range(-0.34, 0.34),
			0.0,
			_rng.randf_range(-0.30, 0.30)
		)
		var height: float = _rng.randf_range(0.22, 0.58)
		var scale_value: float = _rng.randf_range(0.62, 1.22)

		var stem: MeshInstance3D = _cylinder(
			0.045 * scale_value,
			0.072 * scale_value,
			height,
			Color("#dfd3ad"),
			0.96
		)
		stem.position = local_offset + Vector3(0.0, height * 0.5, 0.0)
		cluster.add_child(stem)

		var cap_color: Color = CAP_RED
		var palette_index: int = (index + mushroom_index) % 3
		if palette_index == 1:
			cap_color = CAP_BLUE
		elif palette_index == 2:
			cap_color = CAP_GOLD

		var cap: MeshInstance3D = _sphere(
			Vector3(0.22, 0.09, 0.22) * scale_value,
			cap_color,
			0.88
		)
		cap.position = local_offset + Vector3(0.0, height + 0.02, 0.0)
		cluster.add_child(cap)

	var moss: MeshInstance3D = _sphere(
		Vector3(0.42, 0.07, 0.34),
		MOSS_LIGHT.darkened(0.10),
		1.0
	)
	moss.position = Vector3(0.0, 0.02, 0.0)
	cluster.add_child(moss)


func _build_rock_cluster(origin: Vector3, index: int) -> void:
	var cluster: Node3D = Node3D.new()
	cluster.name = "RockCluster_%02d" % index
	cluster.position = origin
	cluster.rotation.y = _rng.randf_range(-PI, PI)
	add_child(cluster)

	for rock_index: int in range(2 + (index % 3)):
		var rock_color: Color = Color("#5f6559").lightened(float(rock_index) * 0.025)
		var rock: MeshInstance3D = _sphere(
			Vector3(
				_rng.randf_range(0.18, 0.40),
				_rng.randf_range(0.13, 0.27),
				_rng.randf_range(0.18, 0.36)
			),
			rock_color,
			0.98
		)
		rock.position = Vector3(
			_rng.randf_range(-0.28, 0.28),
			0.10,
			_rng.randf_range(-0.22, 0.22)
		)
		cluster.add_child(rock)


func _build_fallen_log(origin: Vector3, index: int) -> void:
	var cluster: Node3D = Node3D.new()
	cluster.name = "FallenLog_%02d" % index
	cluster.position = origin
	cluster.rotation.y = _rng.randf_range(-PI, PI)
	add_child(cluster)

	var length: float = _rng.randf_range(0.9, 1.55)
	var log_mesh: MeshInstance3D = _cylinder(
		0.13,
		0.16,
		length,
		TRUNK_DARK,
		1.0
	)
	log_mesh.rotation.z = PI * 0.5
	log_mesh.position.y = 0.16
	cluster.add_child(log_mesh)

	var moss: MeshInstance3D = _sphere(
		Vector3(length * 0.24, 0.05, 0.13),
		MOSS_LIGHT,
		0.96
	)
	moss.position = Vector3(0.0, 0.27, 0.0)
	cluster.add_child(moss)


func _build_crystal_cluster(origin: Vector3, index: int) -> void:
	var cluster: Node3D = Node3D.new()
	cluster.name = "CrystalCluster_%02d" % index
	cluster.position = origin
	cluster.rotation.y = _rng.randf_range(-PI, PI)
	add_child(cluster)

	for crystal_index: int in range(3):
		var height: float = 0.30 + float(crystal_index) * 0.11
		var crystal: MeshInstance3D = _cylinder(
			0.025,
			0.105,
			height,
			CRYSTAL.lightened(float(crystal_index) * 0.06),
			0.50,
			true
		)
		crystal.position = Vector3(
			float(crystal_index - 1) * 0.13,
			height * 0.5,
			float((crystal_index % 2) * 2 - 1) * 0.06
		)
		crystal.rotation.z = float(crystal_index - 1) * 0.14
		cluster.add_child(crystal)


func _build_inside_ground_details(map: SporeMap3D) -> void:
	for y: int in range(map.grid_height):
		for x: int in range(map.grid_width):
			var cell_value: Vector2i = Vector2i(x, y)
			var tile: Node = map.tile_at(cell_value)
			if tile == null:
				continue

			var terrain_type: String = String(tile.get("terrain_type"))
			if terrain_type != "ground":
				continue

			var selector: int = absi(
				x * 92821
				+ y * 68917
				+ map.elevation_at(cell_value) * 101
			)
			if selector % 4 != 0:
				continue

			var root: Node3D = Node3D.new()
			root.name = "GroundDetail_%02d_%02d" % [x, y]
			root.position = map.cell_top_local(cell_value)
			add_child(root)

			var corner_x: float = -1.0 if selector % 2 == 0 else 1.0
			var corner_z: float = -1.0 if (selector / 2) % 2 == 0 else 1.0
			var corner_offset: Vector3 = Vector3(
				corner_x * map.tile_size * 0.28,
				0.018,
				corner_z * map.tile_size * 0.28
			)

			var moss: MeshInstance3D = _sphere(
				Vector3(0.18, 0.025, 0.14),
				MOSS_LIGHT.darkened(0.08),
				1.0
			)
			moss.position = corner_offset
			root.add_child(moss)

			if selector % 3 == 0:
				for blade_index: int in range(3):
					var grass: MeshInstance3D = _box(
						Vector3(
							0.025,
							0.16 + 0.03 * blade_index,
							0.06
						),
						corner_offset + Vector3(
							float(blade_index - 1) * 0.055,
							0.08,
							0.03 * float(blade_index % 2)
						),
						GRASS_A if blade_index % 2 == 0 else GRASS_B,
						0.96
					)
					grass.rotation.z = -0.10 + 0.10 * float(blade_index)
					root.add_child(grass)

			if selector % 5 == 0:
				var pebble: MeshInstance3D = _sphere(
					Vector3(0.08, 0.04, 0.07),
					Color("#77796d"),
					1.0
				)
				pebble.position = corner_offset + Vector3(0.12, 0.02, -0.05)
				root.add_child(pebble)


func _build_fireflies(map: SporeMap3D) -> void:
	var width: float = float(map.grid_width) * map.tile_size
	var depth: float = float(map.grid_height) * map.tile_size

	for index: int in range(14):
		var firefly: MeshInstance3D = _sphere(
			Vector3(0.025, 0.025, 0.025),
			Color("#d8f18a"),
			0.45,
			true
		)
		firefly.name = "Firefly_%02d" % index
		firefly.position = Vector3(
			_rng.randf_range(-width * 0.58, width * 0.58),
			_rng.randf_range(0.65, 1.65),
			_rng.randf_range(-depth * 0.58, depth * 0.58)
		)
		add_child(firefly)


func _box(
	size_value: Vector3,
	position_value: Vector3,
	color: Color,
	roughness: float
) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = size_value
	instance.mesh = mesh
	instance.position = position_value
	instance.material_override = _material(color, roughness)
	return instance


func _sphere(
	scale_value: Vector3,
	color: Color,
	roughness: float,
	emissive: bool = false
) -> MeshInstance3D:
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


func _cylinder(
	top_radius: float,
	bottom_radius: float,
	height: float,
	color: Color,
	roughness: float,
	emissive: bool = false
) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = top_radius
	mesh.bottom_radius = bottom_radius
	mesh.height = height
	mesh.radial_segments = 8
	instance.mesh = mesh
	instance.material_override = _material(color, roughness, emissive)
	return instance


func _material(
	color: Color,
	roughness: float,
	emissive: bool = false
) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	if emissive:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.42
	return material
