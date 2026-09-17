@tool
class_name SporeEnemySpawn3D
extends Node3D

@export_group("Placement")
@export var cell: Vector2i = Vector2i.ZERO:
	set(value):
		cell = value
		_refresh_deferred()

@export_group("Unit")
@export var unit_id: String = "baveux":
	set(value):
		unit_id = value.strip_edges()
		_refresh_deferred()
@export var role_override: String = ""

@export_group("Mission overrides (-1 = global)")
@export_range(-1, 99, 1) var hp_override: int = -1
@export_range(-1, 30, 1) var attack_override: int = -1
@export_range(-1, 20, 1) var move_override: int = -1
@export_range(-1, 20, 1) var range_override: int = -1

var _refresh_queued: bool = false


func spore_map_role() -> String:
	return "enemy"


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
	var short_name: String = unit_id.substr(0, mini(3, unit_id.length())).to_upper()
	_build_marker(short_name, Color("#ff776e"))


func _build_marker(text: String, color: Color) -> void:
	var marker: MeshInstance3D = get_node_or_null("_Marker") as MeshInstance3D
	if marker == null:
		marker = MeshInstance3D.new()
		marker.name = "_Marker"
		add_child(marker, false, Node.INTERNAL_MODE_BACK)
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = 0.28
	mesh.bottom_radius = 0.34
	mesh.height = 0.12
	marker.mesh = mesh
	marker.position.y = 0.06
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.emission_enabled = true
	material.emission = color.darkened(0.18)
	material.emission_energy_multiplier = 0.3
	marker.material_override = material

	var label: Label3D = get_node_or_null("_Label") as Label3D
	if label == null:
		label = Label3D.new()
		label.name = "_Label"
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.font_size = 32
		label.outline_size = 8
		add_child(label, false, Node.INTERNAL_MODE_BACK)
	label.text = text
	label.position = Vector3(0.0, 0.58, 0.0)


func _map_parent() -> SporeMap3D:
	var node: Node = get_parent()
	while node != null:
		if node is SporeMap3D:
			return node as SporeMap3D
		node = node.get_parent()
	return null
