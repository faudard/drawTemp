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

	var color: Color = Color("#ffd166")
	if object_type == "switch":
		var switch_mesh: CylinderMesh = CylinderMesh.new()
		switch_mesh.top_radius = 0.22
		switch_mesh.bottom_radius = 0.30
		switch_mesh.height = 0.10
		marker.mesh = switch_mesh
		color = Color("#67c8ff")
	elif object_type == "chest":
		var chest_mesh: BoxMesh = BoxMesh.new()
		chest_mesh.size = Vector3(0.55, 0.30, 0.38)
		marker.mesh = chest_mesh
		color = Color("#c99245")
	else:
		var door_mesh: BoxMesh = BoxMesh.new()
		door_mesh.size = Vector3(0.16, 0.95, 0.85)
		marker.mesh = door_mesh
	marker.position.y = 0.18 if object_type != "door" else 0.48
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	marker.material_override = material

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
	label.position = Vector3(0.0, 0.92, 0.0)


func _map_parent() -> SporeMap3D:
	var node: Node = get_parent()
	while node != null:
		if node is SporeMap3D:
			return node as SporeMap3D
		node = node.get_parent()
	return null
