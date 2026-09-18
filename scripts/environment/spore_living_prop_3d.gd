@tool
class_name SporeLivingProp3D
extends Node3D

## Very small reusable presentation component for environmental props.
## The geometry remains authored in .tscn scenes; this script only adds subtle life.

@export_enum("none", "tree", "mushroom", "crystal", "shrine", "speaker", "lantern") var animation_kind: String = "none"
@export_range(0.05, 4.0, 0.05) var animation_speed: float = 1.0
@export_range(0.0, 0.25, 0.005) var animation_amplitude: float = 0.035
@export var animate_in_editor: bool = false
@export var phase_offset: float = 0.0

var _time: float = 0.0
var _base_transforms: Dictionary = {}
var _base_light_energy: Dictionary = {}


func _ready() -> void:
	_cache_base_state()
	set_process(not Engine.is_editor_hint() or animate_in_editor)


func _notification(what: int) -> void:
	if what == NOTIFICATION_EDITOR_PRE_SAVE and Engine.is_editor_hint():
		_restore_base_state()


func _cache_base_state() -> void:
	_base_transforms.clear()
	_base_light_energy.clear()
	for child: Node in get_children():
		if child is Node3D:
			_base_transforms[child] = (child as Node3D).transform
		if child is Light3D:
			_base_light_energy[child] = (child as Light3D).light_energy


func _restore_base_state() -> void:
	for node_value: Variant in _base_transforms.keys():
		var node: Node3D = node_value as Node3D
		if node != null and is_instance_valid(node):
			node.transform = _base_transforms[node]
	for light_value: Variant in _base_light_energy.keys():
		var light: Light3D = light_value as Light3D
		if light != null and is_instance_valid(light):
			light.light_energy = float(_base_light_energy[light])


func _process(delta: float) -> void:
	if Engine.is_editor_hint() and not animate_in_editor:
		return
	_time += delta * animation_speed
	match animation_kind:
		"tree":
			_animate_tree()
		"mushroom":
			_animate_mushrooms()
		"crystal":
			_animate_crystal()
		"shrine":
			_animate_shrine()
		"speaker":
			_animate_speaker()
		"lantern":
			_animate_lantern()
		_:
			pass


func _base_transform(node: Node3D) -> Transform3D:
	if _base_transforms.has(node):
		return _base_transforms[node]
	return node.transform


func _animate_tree() -> void:
	for name_value: String in ["CanopyLow", "CanopyHigh"]:
		var node: Node3D = get_node_or_null(name_value) as Node3D
		if node == null:
			continue
		var base: Transform3D = _base_transform(node)
		node.transform = base
		var phase: float = phase_offset + (0.7 if name_value == "CanopyHigh" else 0.0)
		node.rotation.z += sin(_time * 0.62 + phase) * animation_amplitude
		node.rotation.x += cos(_time * 0.47 + phase) * animation_amplitude * 0.35


func _animate_mushrooms() -> void:
	var names: Array[String] = ["CapA", "CapB", "CapC"]
	for index: int in range(names.size()):
		var node: Node3D = get_node_or_null(names[index]) as Node3D
		if node == null:
			continue
		var base: Transform3D = _base_transform(node)
		node.transform = base
		var breathe: float = 1.0 + sin(_time * 1.18 + phase_offset + float(index) * 0.9) * animation_amplitude
		node.scale = base.basis.get_scale() * Vector3(1.0, breathe, 1.0)


func _animate_crystal() -> void:
	var names: Array[String] = ["CrystalA", "CrystalB", "CrystalC"]
	for index: int in range(names.size()):
		var node: Node3D = get_node_or_null(names[index]) as Node3D
		if node == null:
			continue
		var base: Transform3D = _base_transform(node)
		node.transform = base
		var pulse: float = 1.0 + sin(_time * 1.35 + phase_offset + float(index) * 0.55) * animation_amplitude * 0.60
		node.scale = base.basis.get_scale() * pulse
	_pulse_light("Glow", 0.18)


func _animate_shrine() -> void:
	var ring: Node3D = get_node_or_null("GlowRing") as Node3D
	if ring != null:
		var base: Transform3D = _base_transform(ring)
		ring.transform = base
		var pulse: float = 1.0 + sin(_time * 1.15 + phase_offset) * animation_amplitude * 0.55
		ring.scale = base.basis.get_scale() * Vector3(pulse, 1.0, pulse)
	_pulse_light("CrownLight", 0.16)


func _animate_speaker() -> void:
	var cone: Node3D = get_node_or_null("Glow") as Node3D
	if cone != null:
		var base: Transform3D = _base_transform(cone)
		cone.transform = base
		var beat: float = maxf(0.0, sin(_time * 2.25 + phase_offset))
		cone.scale = base.basis.get_scale() * (1.0 + beat * animation_amplitude * 1.4)
	_pulse_light("BeatLight", 0.10)


func _animate_lantern() -> void:
	var glow: Node3D = get_node_or_null("GlowCap") as Node3D
	if glow != null:
		var base: Transform3D = _base_transform(glow)
		glow.transform = base
		var pulse: float = 1.0 + sin(_time * 0.92 + phase_offset) * animation_amplitude * 0.55
		glow.scale = base.basis.get_scale() * pulse
	_pulse_light("LanternLight", 0.12)


func _pulse_light(node_name: String, relative_amount: float) -> void:
	var light: Light3D = get_node_or_null(node_name) as Light3D
	if light == null:
		return
	var base_energy: float = float(_base_light_energy.get(light, light.light_energy))
	light.light_energy = base_energy * (1.0 + sin(_time * 1.05 + phase_offset) * relative_amount)
