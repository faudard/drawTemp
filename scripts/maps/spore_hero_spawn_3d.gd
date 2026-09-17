@tool
class_name SporeHeroSpawn3D
extends Node3D

@export var cell: Vector2i = Vector2i.ZERO:
	set(value):
		cell = value
		_refresh_deferred()
@export_range(0, 20, 1) var order: int = 0:
	set(value):
		order = maxi(0, value)
		_refresh_deferred()

var _refresh_queued: bool = false


func spore_map_role() -> String:
	return "hero"


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
	_build_marker("H%d" % (order + 1), Color("#5fc8ff"))


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
	material.emission = color.darkened(0.15)
	material.emission_energy_multiplier = 0.35
	marker.material_override = material

	var label: Label3D = get_node_or_null("_Label") as Label3D
	if label == null:
		label = Label3D.new()
		label.name = "_Label"
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.font_size = 36
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
