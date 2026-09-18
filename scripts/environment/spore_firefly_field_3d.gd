@tool
class_name SporeFireflyField3D
extends Node3D

## Lightweight reusable firefly field. Points are generated deterministically so
## the field remains visible in the editor and identical at runtime.

@export_range(1, 24, 1) var amount: int = 8:
	set(value):
		amount = maxi(1, value)
		_rebuild_deferred()
@export_range(0.2, 8.0, 0.1) var radius: float = 2.0:
	set(value):
		radius = maxf(0.2, value)
		_rebuild_deferred()
@export_range(0.1, 4.0, 0.1) var height: float = 1.5:
	set(value):
		height = maxf(0.1, value)
		_rebuild_deferred()
@export var glow_color: Color = Color(0.74, 1.0, 0.54, 1.0):
	set(value):
		glow_color = value
		_rebuild_deferred()
@export var seed_value: int = 1337:
	set(value):
		seed_value = value
		_rebuild_deferred()
@export_range(0.05, 3.0, 0.05) var drift_speed: float = 0.55
@export_range(0.0, 0.6, 0.01) var drift_amount: float = 0.22
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
		if child.name.begins_with("_Firefly"):
			child.free()
	_base_positions.clear()

	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = seed_value
	for index: int in range(amount):
		var point: MeshInstance3D = MeshInstance3D.new()
		point.name = "_Firefly%02d" % index
		var sphere: SphereMesh = SphereMesh.new()
		sphere.radius = 0.035
		sphere.height = 0.070
		sphere.radial_segments = 6
		sphere.rings = 4
		point.mesh = sphere
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = glow_color
		material.emission_enabled = true
		material.emission = glow_color
		material.emission_energy_multiplier = 1.65
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		point.material_override = material
		var angle: float = rng.randf_range(-PI, PI)
		var distance: float = sqrt(rng.randf()) * radius
		point.position = Vector3(
			cos(angle) * distance,
			rng.randf_range(0.28, height),
			sin(angle) * distance
		)
		_base_positions[point] = point.position
		add_child(point, false, Node.INTERNAL_MODE_BACK)


func _process(delta: float) -> void:
	if Engine.is_editor_hint() and not animate_in_editor:
		return
	_time += delta * drift_speed
	var index: int = 0
	for node_value: Variant in _base_positions.keys():
		var point: Node3D = node_value as Node3D
		if point == null or not is_instance_valid(point):
			continue
		var base: Vector3 = _base_positions[point]
		var phase: float = float(index) * 1.71 + float(seed_value % 31) * 0.11
		point.position = base + Vector3(
			sin(_time * 0.83 + phase) * drift_amount,
			sin(_time * 1.31 + phase * 0.73) * drift_amount * 0.42,
			cos(_time * 0.67 + phase) * drift_amount
		)
		var blink: float = 0.72 + maxf(0.0, sin(_time * 2.2 + phase)) * 0.42
		point.scale = Vector3.ONE * blink
		index += 1
