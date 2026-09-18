@tool
class_name SporeMapInteractable3D
extends Node3D

const MapInteractableDefinition = preload("res://scripts/data/map_interactable_definition.gd")

@export_group("Placement")
@export var cell: Vector2i = Vector2i.ZERO:
	set(value):
		cell = value
		_refresh_deferred()

@export_group("Identity")
@export var object_id: String = "object"
@export var display_name: String = "Objet":
	set(value):
		display_name = value
		_refresh_deferred()
@export_enum("door", "switch", "chest") var object_type: String = "door":
	set(value):
		object_type = value
		_refresh_deferred()
@export var linked_object_id: String = ""

@export_group("State")
@export var starts_active: bool = false
@export var one_shot: bool = true

@export_group("Reward")
@export_enum("none", "heal_team", "focus_team") var reward_type: String = "none"
@export_range(0, 20, 1) var reward_value: int = 0
@export_enum("player", "enemy") var reward_team: String = "player"

var _refresh_queued: bool = false


func spore_map_role() -> String:
	return "interactable"


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
	position = map.cell_top_local(cell) + Vector3(0.0, 0.08, 0.0)
	_rebuild_visual()


func to_definition() -> Resource:
	var definition: Resource = MapInteractableDefinition.new()
	definition.id = object_id
	definition.display_name = display_name
	definition.object_type = object_type
	definition.cell = cell
	definition.linked_object_id = linked_object_id
	definition.starts_active = starts_active
	definition.one_shot = one_shot
	definition.reward_type = reward_type
	definition.reward_value = reward_value
	definition.reward_team = reward_team
	return definition


func _rebuild_visual() -> void:
	var marker: MeshInstance3D = get_node_or_null("_Marker") as MeshInstance3D
	if marker == null:
		marker = MeshInstance3D.new()
		marker.name = "_Marker"
		add_child(marker, false, Node.INTERNAL_MODE_BACK)
	var details: Node3D = get_node_or_null("_Details") as Node3D
	if details == null:
		details = Node3D.new()
		details.name = "_Details"
		add_child(details, false, Node.INTERNAL_MODE_BACK)
	for child: Node in details.get_children():
		child.free()

	marker.rotation = Vector3.ZERO
	marker.scale = Vector3.ONE
	marker.position = Vector3.ZERO
	match object_type:
		"switch":
			_build_switch(marker, details)
		"chest":
			_build_chest(marker, details)
		_:
			_build_gate(marker, details)

	var label: Label3D = get_node_or_null("_Label") as Label3D
	if label == null:
		label = Label3D.new()
		label.name = "_Label"
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.font_size = 24
		label.outline_size = 7
		add_child(label, false, Node.INTERNAL_MODE_BACK)
	label.text = display_name
	label.position = Vector3(0.0, 1.12, 0.0)
	label.visible = Engine.is_editor_hint()


func _build_gate(marker: MeshInstance3D, details: Node3D) -> void:
	var beam_mesh: BoxMesh = BoxMesh.new()
	beam_mesh.size = Vector3(0.16, 0.92, 0.82)
	marker.mesh = beam_mesh
	marker.position = Vector3(0.0, 0.48, 0.0)
	marker.material_override = _material(Color("#604a37"), 0.98)
	for side_value: Variant in [-1, 1]:
		var side: int = int(side_value)
		var cap: MeshInstance3D = _box(Vector3(0.24, 0.13, 0.26), Color("#8b6a43"), 0.94)
		cap.position = Vector3(0.0, 0.88, float(side) * 0.30)
		details.add_child(cap)
	var rune: MeshInstance3D = _sphere(Vector3(0.12, 0.12, 0.06), Color("#efc764"), 0.35, true)
	rune.position = Vector3(-0.10, 0.56, 0.0)
	details.add_child(rune)


func _build_switch(marker: MeshInstance3D, details: Node3D) -> void:
	var stem_mesh: CylinderMesh = CylinderMesh.new()
	stem_mesh.top_radius = 0.09
	stem_mesh.bottom_radius = 0.13
	stem_mesh.height = 0.28
	stem_mesh.radial_segments = 10
	marker.mesh = stem_mesh
	marker.position = Vector3(0.0, 0.14, 0.0)
	marker.material_override = _material(Color("#d8caa3"), 0.96)
	var cap: MeshInstance3D = _sphere(Vector3(0.26, 0.11, 0.26), Color("#55bfe9"), 0.45, true)
	cap.position = Vector3(0.0, 0.34, 0.0)
	details.add_child(cap)
	var center: MeshInstance3D = _sphere(Vector3(0.07, 0.035, 0.07), Color("#d8f7ff"), 0.30, true)
	center.position = Vector3(0.0, 0.44, 0.0)
	details.add_child(center)


func _build_chest(marker: MeshInstance3D, details: Node3D) -> void:
	var chest_mesh: BoxMesh = BoxMesh.new()
	chest_mesh.size = Vector3(0.58, 0.28, 0.40)
	marker.mesh = chest_mesh
	marker.position = Vector3(0.0, 0.17, 0.0)
	marker.material_override = _material(Color("#966640"), 0.96)
	var lid: MeshInstance3D = _box(Vector3(0.60, 0.13, 0.42), Color("#b67d49"), 0.93)
	lid.position = Vector3(0.0, 0.37, 0.0)
	details.add_child(lid)
	for side_value: Variant in [-1, 1]:
		var side: int = int(side_value)
		var band: MeshInstance3D = _box(Vector3(0.07, 0.45, 0.44), Color("#d6ae58"), 0.48)
		band.position = Vector3(float(side) * 0.20, 0.23, 0.0)
		details.add_child(band)
	var lock: MeshInstance3D = _box(Vector3(0.10, 0.12, 0.04), Color("#f0cb67"), 0.36, true)
	lock.position = Vector3(0.0, 0.25, -0.22)
	details.add_child(lock)


func _box(size_value: Vector3, color: Color, roughness: float, emissive: bool = false) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = size_value
	instance.mesh = mesh
	instance.material_override = _material(color, roughness, emissive)
	return instance


func _sphere(scale_value: Vector3, color: Color, roughness: float, emissive: bool = false) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 12
	mesh.rings = 6
	instance.mesh = mesh
	instance.scale = scale_value * 2.0
	instance.material_override = _material(color, roughness, emissive)
	return instance


func _material(color: Color, roughness: float, emissive: bool = false) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	if emissive:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.24
	return material


func _map_parent() -> SporeMap3D:
	var node: Node = get_parent()
	while node != null:
		if node is SporeMap3D:
			return node as SporeMap3D
		node = node.get_parent()
	return null
