@tool
class_name SporeGroundDetailPatch3D
extends Node3D

## Editor-visible, non-gameplay ground dressing.
## One reusable component for moss, dirt, stones, roots, flowers and leaves.

@export_group("Patch")
@export_enum("moss", "dirt", "stones", "roots", "flowers", "leaves") var patch_kind: String = "moss":
	set(value):
		patch_kind = value
		_queue_rebuild()
@export_range(0.20, 2.40, 0.05) var radius: float = 0.75:
	set(value):
		radius = maxf(0.20, value)
		_queue_rebuild()
@export_range(1, 14, 1) var density: int = 5:
	set(value):
		density = clampi(value, 1, 14)
		_queue_rebuild()
@export_range(0, 99999, 1) var seed_value: int = 1:
	set(value):
		seed_value = maxi(0, value)
		_queue_rebuild()
@export_range(0.25, 1.50, 0.05) var visual_strength: float = 0.82:
	set(value):
		visual_strength = clampf(value, 0.25, 1.50)
		_queue_rebuild()

@export_group("Palette")
@export var moss_color: Color = Color("#496643"):
	set(value):
		moss_color = value
		_queue_rebuild()
@export var dirt_color: Color = Color("#4c3b29"):
	set(value):
		dirt_color = value
		_queue_rebuild()
@export var stone_color: Color = Color("#687064"):
	set(value):
		stone_color = value
		_queue_rebuild()
@export var root_color: Color = Color("#59402c"):
	set(value):
		root_color = value
		_queue_rebuild()
@export var flower_color: Color = Color("#e9b9e8"):
	set(value):
		flower_color = value
		_queue_rebuild()
@export var leaf_color: Color = Color("#79653c"):
	set(value):
		leaf_color = value
		_queue_rebuild()

var _rebuild_queued: bool = false


func _ready() -> void:
	_rebuild()


func _queue_rebuild() -> void:
	if not is_inside_tree() or _rebuild_queued:
		return
	_rebuild_queued = true
	call_deferred("_apply_rebuild")


func _apply_rebuild() -> void:
	_rebuild_queued = false
	_rebuild()


func _rebuild() -> void:
	var generated: Node3D = get_node_or_null("_Generated") as Node3D
	if generated != null:
		generated.free()
	generated = Node3D.new()
	generated.name = "_Generated"
	add_child(generated, false, Node.INTERNAL_MODE_BACK)

	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value * 1009 + 17

	match patch_kind:
		"dirt":
			_build_flat_patch(generated, rng, dirt_color, false)
		"stones":
			_build_stones(generated, rng)
		"roots":
			_build_roots(generated, rng)
		"flowers":
			_build_flowers(generated, rng)
		"leaves":
			_build_leaves(generated, rng)
		_:
			_build_flat_patch(generated, rng, moss_color, true)


func _build_flat_patch(parent: Node3D, rng: RandomNumberGenerator, color: Color, moss: bool) -> void:
	var count: int = maxi(2, density)
	for index: int in range(count):
		var disc := MeshInstance3D.new()
		var mesh := CylinderMesh.new()
		var local_radius: float = radius * rng.randf_range(0.24, 0.52)
		mesh.top_radius = local_radius
		mesh.bottom_radius = local_radius * rng.randf_range(0.92, 1.08)
		mesh.height = 0.014 if moss else 0.010
		mesh.radial_segments = 10
		disc.mesh = mesh
		disc.position = Vector3(
			rng.randf_range(-radius * 0.62, radius * 0.62),
			0.010 + float(index % 3) * 0.001,
			rng.randf_range(-radius * 0.62, radius * 0.62)
		)
		disc.scale.z = rng.randf_range(0.55, 1.20)
		disc.rotation.y = rng.randf_range(-PI, PI)
		var shade: float = rng.randf_range(-0.055, 0.055)
		disc.material_override = _material(color.lightened(shade) if shade >= 0.0 else color.darkened(-shade), 0.88 if moss else 0.98, 0.72 * visual_strength)
		parent.add_child(disc)


func _build_stones(parent: Node3D, rng: RandomNumberGenerator) -> void:
	for index: int in range(density):
		var stone := MeshInstance3D.new()
		var mesh := SphereMesh.new()
		mesh.radius = 0.5
		mesh.height = 1.0
		mesh.radial_segments = 8
		mesh.rings = 4
		stone.mesh = mesh
		var size: float = rng.randf_range(0.09, 0.19) * visual_strength
		stone.scale = Vector3(size * rng.randf_range(0.9, 1.35), size * rng.randf_range(0.45, 0.8), size)
		stone.position = _random_xz(rng, radius * 0.72, size * 0.35)
		stone.rotation.y = rng.randf_range(-PI, PI)
		var stone_shade: float = rng.randf_range(-0.02, 0.08)
		var resolved_stone: Color = stone_color.lightened(stone_shade) if stone_shade >= 0.0 else stone_color.darkened(-stone_shade)
		stone.material_override = _material(resolved_stone, 0.96, 1.0)
		parent.add_child(stone)


func _build_roots(parent: Node3D, rng: RandomNumberGenerator) -> void:
	for index: int in range(maxi(2, density / 2)):
		var root := MeshInstance3D.new()
		var mesh := CylinderMesh.new()
		mesh.top_radius = 0.025 * visual_strength
		mesh.bottom_radius = 0.045 * visual_strength
		mesh.height = rng.randf_range(0.55, 1.05) * radius
		mesh.radial_segments = 7
		root.mesh = mesh
		root.position = _random_xz(rng, radius * 0.54, 0.035)
		root.rotation = Vector3(PI * 0.5, rng.randf_range(-PI, PI), rng.randf_range(-0.08, 0.08))
		root.material_override = _material(root_color.lightened(rng.randf_range(-0.03, 0.05)), 1.0, 1.0)
		parent.add_child(root)


func _build_flowers(parent: Node3D, rng: RandomNumberGenerator) -> void:
	for index: int in range(density):
		var flower := Node3D.new()
		flower.position = _random_xz(rng, radius * 0.70, 0.0)
		parent.add_child(flower)
		var height: float = rng.randf_range(0.08, 0.16) * visual_strength
		var stem := MeshInstance3D.new()
		var stem_mesh := CylinderMesh.new()
		stem_mesh.top_radius = 0.008
		stem_mesh.bottom_radius = 0.012
		stem_mesh.height = height
		stem_mesh.radial_segments = 6
		stem.mesh = stem_mesh
		stem.position.y = height * 0.5
		stem.material_override = _material(Color("#557348"), 0.95, 1.0)
		flower.add_child(stem)
		var bloom := MeshInstance3D.new()
		var bloom_mesh := SphereMesh.new()
		bloom_mesh.radius = 0.5
		bloom_mesh.height = 1.0
		bloom_mesh.radial_segments = 7
		bloom_mesh.rings = 4
		bloom.mesh = bloom_mesh
		bloom.scale = Vector3(0.055, 0.025, 0.055) * visual_strength
		bloom.position.y = height
		var bloom_shade: float = rng.randf_range(-0.03, 0.10)
		var bloom_color: Color = flower_color.lightened(bloom_shade) if bloom_shade >= 0.0 else flower_color.darkened(-bloom_shade)
		bloom.material_override = _material(bloom_color, 0.76, 1.0, true)
		flower.add_child(bloom)


func _build_leaves(parent: Node3D, rng: RandomNumberGenerator) -> void:
	for index: int in range(density * 2):
		var leaf := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = Vector3(rng.randf_range(0.05, 0.10), 0.008, rng.randf_range(0.025, 0.05)) * visual_strength
		leaf.mesh = mesh
		leaf.position = _random_xz(rng, radius * 0.75, 0.014)
		leaf.rotation.y = rng.randf_range(-PI, PI)
		var palette: Color = leaf_color
		if index % 3 == 1:
			palette = Color("#5d6937")
		elif index % 3 == 2:
			palette = Color("#8b5b36")
		leaf.material_override = _material(palette, 1.0, 0.95)
		parent.add_child(leaf)


func _random_xz(rng: RandomNumberGenerator, spread: float, y: float) -> Vector3:
	var angle: float = rng.randf_range(-PI, PI)
	var distance: float = sqrt(rng.randf()) * spread
	return Vector3(cos(angle) * distance, y, sin(angle) * distance)


func _material(color: Color, roughness: float, alpha: float, emissive: bool = false) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(color.r, color.g, color.b, clampf(alpha, 0.0, 1.0))
	material.roughness = roughness
	if alpha < 0.999:
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_OPAQUE_ONLY
	if emissive:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.12
	return material
