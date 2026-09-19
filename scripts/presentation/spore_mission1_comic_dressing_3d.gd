@tool
class_name SporeMission1ComicDressing3D
extends Node3D

## Comic/BD dressing for Mission 1.
## Purely visual: no collision, no gameplay state, no authored cell data.
## Everything is positioned from SporeMap3D cell coordinates so it remains aligned
## if tile_size/elevation settings change.

const INK := Color("#161616")
const INK_SOFT := Color("#2b2b2b")
const PAPER := Color("#e8e2d4")
const STONE := Color("#55534f")
const STONE_LIGHT := Color("#73706a")
const GOLD := Color("#f0bf35")
const RED := Color("#d83b2f")
const GREEN := Color("#55c77d")
const PURPLE := Color("#8d59d9")
const CYAN := Color("#53bfe8")

var _built := false


func _ready() -> void:
	if Engine.is_editor_hint():
		call_deferred("_rebuild")
	else:
		_rebuild()


func _notification(what: int) -> void:
	if what == NOTIFICATION_EDITOR_POST_SAVE and Engine.is_editor_hint():
		call_deferred("_rebuild")


func _rebuild() -> void:
	var map := get_parent() as SporeMap3D
	if map == null:
		return
	_clear_generated()
	_build_crown_focus(map)
	_build_direction_signs(map)
	_build_ink_frame(map)
	_build_ruin_accents(map)
	_build_objective_lights(map)
	_built = true


func _clear_generated() -> void:
	for child: Node in get_children():
		if child.name.begins_with("_Comic"):
			child.free()


func _build_crown_focus(map: SporeMap3D) -> void:
	var root := Node3D.new()
	root.name = "_ComicCrownFocus"
	add_child(root)

	var crown_cell := Vector2i(9, 0)
	var center := map.cell_to_local(crown_cell, map.elevation_at(crown_cell))

	# Low stepped altar: readable silhouette without blocking units.
	root.add_child(_box("CrownStepLow", Vector3(map.tile_size * 1.18, 0.14, map.tile_size * 1.18), center + Vector3(0.0, -0.08, 0.0), STONE))
	root.add_child(_box("CrownStepMid", Vector3(map.tile_size * 0.86, 0.14, map.tile_size * 0.86), center + Vector3(0.0, 0.02, 0.0), STONE_LIGHT))
	root.add_child(_box("CrownStepTop", Vector3(map.tile_size * 0.54, 0.12, map.tile_size * 0.54), center + Vector3(0.0, 0.13, 0.0), INK_SOFT))

	var ring := MeshInstance3D.new()
	ring.name = "CrownGoldRing"
	var ring_mesh := CylinderMesh.new()
	ring_mesh.top_radius = map.tile_size * 0.32
	ring_mesh.bottom_radius = map.tile_size * 0.37
	ring_mesh.height = 0.035
	ring_mesh.radial_segments = 32
	ring.mesh = ring_mesh
	ring.position = center + Vector3(0.0, 0.205, 0.0)
	ring.material_override = _material(GOLD, true, 0.75)
	root.add_child(ring)

	# Three black "ink fins" create a graphic frame around the objective.
	for index in range(3):
		var fin := _box(
			"InkFin%d" % index,
			Vector3(0.08, 1.55 + 0.18 * index, 0.18),
			center + Vector3(-0.58 + index * 0.58, 0.68, -0.62 - 0.08 * abs(index - 1)),
			INK
		)
		fin.rotation.z = deg_to_rad(-8.0 + 8.0 * index)
		root.add_child(fin)

	var crown_label := _label3d("♛  LA COURONNE", GOLD, 46, 10)
	crown_label.position = center + Vector3(0.0, 1.65, -0.18)
	root.add_child(crown_label)


func _build_direction_signs(map: SporeMap3D) -> void:
	var root := Node3D.new()
	root.name = "_ComicSigns"
	add_child(root)

	var crown_pos := map.cell_to_local(Vector2i(8, 1), map.elevation_at(Vector2i(8, 1)))
	_add_sign(root, crown_pos + Vector3(0.20, 0.0, -0.28), "←  LA COURONNE", GOLD, -0.18)

	var exit_pos := map.cell_to_local(Vector2i(0, 7), map.elevation_at(Vector2i(0, 7)))
	_add_sign(root, exit_pos + Vector3(-0.38, 0.0, 0.34), "SORTIE  →", GREEN, 0.24)

	var vinyl_pos := map.cell_to_local(Vector2i(7, 7), map.elevation_at(Vector2i(7, 7)))
	_add_small_tag(root, vinyl_pos + Vector3(0.0, 0.72, 0.0), "VINYLE", CYAN)

	var chapter := _label3d("CHAPITRE I  •  PETITS CHAPEAUX, GRANDS DESTINS", PAPER, 30, 8)
	chapter.position = Vector3(0.0, 0.35, -6.7)
	root.add_child(chapter)


func _build_ink_frame(map: SporeMap3D) -> void:
	var root := Node3D.new()
	root.name = "_ComicInkFrame"
	add_child(root)

	var half_x := float(map.grid_width) * map.tile_size * 0.5
	var half_z := float(map.grid_height) * map.tile_size * 0.5

	var positions := [
		Vector3(-half_x - 0.9, 0.0, -half_z + 0.9),
		Vector3(half_x + 0.9, 0.0, half_z - 1.2),
		Vector3(-half_x - 0.8, 0.0, half_z - 2.0),
		Vector3(half_x + 0.8, 0.0, -half_z + 2.0),
	]
	for index in range(positions.size()):
		_add_ink_mushroom(root, positions[index], 1.0 + float(index % 2) * 0.16, index)

	# Brush-stroke-like slabs under the diorama edges.
	var left_stroke := _box("LeftBrushStroke", Vector3(0.18, 0.18, map.grid_height * map.tile_size * 0.78), Vector3(-half_x - 0.48, -0.20, 0.0), INK)
	left_stroke.rotation.y = deg_to_rad(2.0)
	root.add_child(left_stroke)
	var right_stroke := _box("RightBrushStroke", Vector3(0.18, 0.18, map.grid_height * map.tile_size * 0.74), Vector3(half_x + 0.48, -0.22, 0.1), INK)
	right_stroke.rotation.y = deg_to_rad(-3.0)
	root.add_child(right_stroke)


func _build_ruin_accents(map: SporeMap3D) -> void:
	var root := Node3D.new()
	root.name = "_ComicRuins"
	add_child(root)

	var cells := [
		Vector2i(6, 1),
		Vector2i(7, 2),
		Vector2i(5, 4),
		Vector2i(2, 3),
	]
	for index in range(cells.size()):
		var p := map.cell_to_local(cells[index], map.elevation_at(cells[index]))
		var stone := _box(
			"RuinStone%d" % index,
			Vector3(0.34 + 0.08 * (index % 2), 0.30 + 0.06 * index, 0.34),
			p + Vector3(0.42 * (-1.0 if index % 2 == 0 else 1.0), 0.12, 0.38),
			STONE if index % 2 == 0 else STONE_LIGHT
		)
		stone.rotation.y = deg_to_rad(float(index * 17 - 22))
		stone.rotation.z = deg_to_rad(float(index * 3 - 4))
		root.add_child(stone)

	# Purple "story stain" near the gate: strong selective-color beat.
	var gate_cell := Vector2i(5, 6)
	var gate_pos := map.cell_to_local(gate_cell, map.elevation_at(gate_cell))
	var stain := MeshInstance3D.new()
	stain.name = "GateStoryStain"
	var stain_mesh := CylinderMesh.new()
	stain_mesh.top_radius = map.tile_size * 0.28
	stain_mesh.bottom_radius = map.tile_size * 0.34
	stain_mesh.height = 0.025
	stain_mesh.radial_segments = 28
	stain.mesh = stain_mesh
	stain.position = gate_pos + Vector3(0.0, 0.04, 0.0)
	stain.material_override = _material(PURPLE, true, 0.55)
	root.add_child(stain)


func _build_objective_lights(map: SporeMap3D) -> void:
	var root := Node3D.new()
	root.name = "_ComicObjectiveLights"
	add_child(root)

	var crown_pos := map.cell_to_local(Vector2i(9, 0), map.elevation_at(Vector2i(9, 0)))
	var crown_light := OmniLight3D.new()
	crown_light.name = "CrownGoldLight"
	crown_light.position = crown_pos + Vector3(0.0, 1.45, 0.0)
	crown_light.light_color = GOLD
	crown_light.light_energy = 1.55
	crown_light.omni_range = 4.8
	crown_light.shadow_enabled = true
	root.add_child(crown_light)

	var gate_pos := map.cell_to_local(Vector2i(5, 6), map.elevation_at(Vector2i(5, 6)))
	var purple_light := OmniLight3D.new()
	purple_light.name = "GatePurpleLight"
	purple_light.position = gate_pos + Vector3(0.0, 0.75, 0.0)
	purple_light.light_color = PURPLE
	purple_light.light_energy = 0.62
	purple_light.omni_range = 2.4
	root.add_child(purple_light)


func _add_sign(parent: Node3D, position_value: Vector3, text_value: String, accent: Color, rotation_y: float) -> void:
	var sign := Node3D.new()
	sign.name = "Sign_%s" % text_value.replace(" ", "_")
	sign.position = position_value
	sign.rotation.y = rotation_y
	parent.add_child(sign)

	var post := MeshInstance3D.new()
	var post_mesh := CylinderMesh.new()
	post_mesh.top_radius = 0.055
	post_mesh.bottom_radius = 0.075
	post_mesh.height = 1.35
	post_mesh.radial_segments = 8
	post.mesh = post_mesh
	post.position = Vector3(0.0, 0.66, 0.0)
	post.material_override = _material(INK)
	sign.add_child(post)

	var board := _box("Board", Vector3(1.95, 0.58, 0.10), Vector3(0.0, 1.28, 0.0), INK)
	sign.add_child(board)

	var accent_bar := _box("Accent", Vector3(1.78, 0.055, 0.12), Vector3(0.0, 1.05, -0.055), accent)
	sign.add_child(accent_bar)

	var label := _label3d(text_value, PAPER, 32, 8)
	label.position = Vector3(0.0, 1.29, -0.09)
	sign.add_child(label)


func _add_small_tag(parent: Node3D, position_value: Vector3, text_value: String, accent: Color) -> void:
	var tag := _label3d(text_value, accent, 28, 7)
	tag.position = position_value
	parent.add_child(tag)


func _add_ink_mushroom(parent: Node3D, base: Vector3, scale_value: float, seed_value: int) -> void:
	var trunk := MeshInstance3D.new()
	trunk.name = "InkTrunk%d" % seed_value
	var trunk_mesh := CylinderMesh.new()
	trunk_mesh.top_radius = 0.16 * scale_value
	trunk_mesh.bottom_radius = 0.22 * scale_value
	trunk_mesh.height = 2.35 * scale_value
	trunk_mesh.radial_segments = 9
	trunk.mesh = trunk_mesh
	trunk.position = base + Vector3(0.0, 1.12 * scale_value, 0.0)
	trunk.rotation.z = deg_to_rad(-3.0 + float(seed_value) * 2.0)
	trunk.material_override = _material(INK)
	parent.add_child(trunk)

	var canopy := MeshInstance3D.new()
	canopy.name = "InkCanopy%d" % seed_value
	var canopy_mesh := SphereMesh.new()
	canopy_mesh.radius = 0.78 * scale_value
	canopy_mesh.height = 0.56 * scale_value
	canopy_mesh.radial_segments = 12
	canopy_mesh.rings = 6
	canopy.mesh = canopy_mesh
	canopy.position = base + Vector3(0.0, 2.42 * scale_value, 0.0)
	canopy.scale = Vector3(1.35, 0.56, 1.10)
	canopy.material_override = _material(INK_SOFT)
	parent.add_child(canopy)


func _box(name_value: String, size_value: Vector3, position_value: Vector3, color: Color) -> MeshInstance3D:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = name_value
	var mesh := BoxMesh.new()
	mesh.size = size_value
	mesh_instance.mesh = mesh
	mesh_instance.position = position_value
	mesh_instance.material_override = _material(color)
	return mesh_instance


func _label3d(text_value: String, color: Color, font_size_value: int, outline_size_value: int) -> Label3D:
	var label := Label3D.new()
	label.text = text_value
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.font_size = font_size_value
	label.outline_size = outline_size_value
	label.modulate = color
	label.outline_modulate = INK
	label.fixed_size = true
	return label


func _material(color: Color, emissive: bool = false, emission_energy: float = 0.0) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.94
	if emissive:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = emission_energy
	return material
