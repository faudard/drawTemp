@tool
class_name SporeMistPatch3D
extends Node3D

## Low ground mist used only as decoration. It never changes tactical state.

@export var mist_color: Color = Color(0.42, 0.20, 0.62, 0.17):
	set(value):
		mist_color = value
		_rebuild_deferred()
@export_range(0.4, 3.0, 0.1) var width: float = 1.20:
	set(value):
		width = maxf(0.4, value)
		_rebuild_deferred()
@export_range(0.05, 1.0, 0.05) var height: float = 0.18:
	set(value):
		height = maxf(0.05, value)
		_rebuild_deferred()
@export_range(0.05, 2.0, 0.05) var drift_speed: float = 0.28
@export_range(0.0, 0.4, 0.01) var drift_amount: float = 0.10
@export var animate_in_editor: bool = false

var _time: float = 0.0
var _rebuild_queued: bool = false
var _base_positions: Dictionary = {}


func _ready() -> void:
	_rebuild()
	set_process(not Engine.is_editor_hint() or animate_in_editor)


func _rebuild_deferred() -> void:
	if not is_inside_tree() or _rebuild_queued:
		return
	_rebuild_queued = true
	call_deferred("_apply_rebuild")


func _apply_rebuild() -> void:
	_rebuild_queued = false
	_rebuild()


func _rebuild() -> void:
	for child: Node in get_children():
		if child.name.begins_with("_Mist"):
			child.free()
	_base_positions.clear()

	for index: int in range(3):
		var cloud: MeshInstance3D = MeshInstance3D.new()
		cloud.name = "_Mist%02d" % index
		var sphere: SphereMesh = SphereMesh.new()
		sphere.radius = 0.5
		sphere.height = 1.0
		sphere.radial_segments = 12
		sphere.rings = 6
		cloud.mesh = sphere
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = mist_color
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.no_depth_test = false
		cloud.material_override = material
		cloud.scale = Vector3(width * (0.72 + float(index) * 0.10), height, width * (0.52 + float(index) * 0.08))
		cloud.position = Vector3(float(index - 1) * width * 0.22, 0.12 + float(index) * 0.025, float((index % 2) * 2 - 1) * width * 0.12)
		_base_positions[cloud] = cloud.position
		add_child(cloud, false, Node.INTERNAL_MODE_BACK)


func _process(delta: float) -> void:
	if Engine.is_editor_hint() and not animate_in_editor:
		return
	_time += delta * drift_speed
	var index: int = 0
	for node_value: Variant in _base_positions.keys():
		var cloud: Node3D = node_value as Node3D
		if cloud == null or not is_instance_valid(cloud):
			continue
		var base: Vector3 = _base_positions[cloud]
		var phase: float = float(index) * 1.35
		cloud.position = base + Vector3(
			sin(_time + phase) * drift_amount,
			0.0,
			cos(_time * 0.72 + phase) * drift_amount * 0.65
		)
		index += 1
