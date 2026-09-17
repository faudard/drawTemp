class_name SporeActionVfx3D
extends Node3D

signal impact(world_position: Vector3)
signal finished

var definition: Resource = null
var source_world: Vector3 = Vector3.ZERO
var target_world: Vector3 = Vector3.ZERO
var target_tracker: Node3D = null
var target_tracker_offset: Vector3 = Vector3.ZERO
var kind: String = "burst"
var duration: float = 0.4
var primary_color: Color = Color.WHITE
var secondary_color: Color = Color.WHITE
var radius_world: float = 0.55
var trail_width_world: float = 0.08
var elapsed: float = 0.0
var started: bool = false
var impacted: bool = false
var follow_position: Vector3 = Vector3.ZERO
var arc_height: float = 0.65
var _body: MeshInstance3D = null
var _aux_nodes: Array[Node3D] = []
var _trail_points: Array[Dictionary] = []
var _trail_accumulator: float = 0.0
var _projectile_burst_spawned: bool = false
var _beam_mesh: BoxMesh = null


func configure(vfx: Resource, source: Vector3, target: Vector3, kind_override: String = "", tracked_target: Node3D = null, tracked_offset: Vector3 = Vector3.ZERO) -> void:
	definition = vfx
	source_world = source
	target_world = target
	target_tracker = tracked_target
	target_tracker_offset = tracked_offset
	kind = String(vfx.get("kind")) if vfx != null else "burst"
	if not kind_override.is_empty():
		kind = kind_override
	duration = maxf(0.08, float(vfx.get("duration"))) if vfx != null else 0.38
	primary_color = vfx.get("primary_color") if vfx != null and vfx.get("primary_color") is Color else Color("#ff7b72")
	secondary_color = vfx.get("secondary_color") if vfx != null and vfx.get("secondary_color") is Color else Color.WHITE
	var radius_px: float = float(vfx.get("radius")) if vfx != null else 24.0
	var trail_px: float = float(vfx.get("trail_width")) if vfx != null else 5.0
	radius_world = clampf(radius_px / 42.0, 0.24, 1.35)
	trail_width_world = clampf(trail_px / 70.0, 0.035, 0.22)
	arc_height = 0.42 + minf(0.75, source.distance_to(target) * 0.045)
	global_position = source_world
	follow_position = source_world


func start() -> void:
	if started:
		return
	started = true
	match kind:
		"projectile":
			_build_projectile()
		"beam":
			_build_beam()
		"slash":
			_build_slash()
		"ring":
			_build_ring()
		"cross":
			_build_cross()
		"aura":
			_build_aura()
		_:
			_build_burst()
	set_process(true)


func _process(delta: float) -> void:
	if not started:
		return
	if target_tracker != null and is_instance_valid(target_tracker):
		target_world = target_tracker.global_position + target_tracker_offset
	elapsed += delta
	var t: float = clampf(elapsed / duration, 0.0, 1.0)
	match kind:
		"projectile":
			_update_projectile(delta, t)
		"beam":
			_update_beam(t)
		"slash":
			_update_slash(t)
		"ring", "aura":
			_update_ring_like(t)
		"cross":
			_update_cross(t)
		_:
			_update_burst(t)
	_update_trail(delta)
	if not impacted and _impact_fraction_reached(t):
		impacted = true
		impact.emit(target_world)
	if t >= 1.0:
		set_process(false)
		_clear_trail_points()
		finished.emit()
		queue_free()


func _impact_fraction_reached(t: float) -> bool:
	if kind == "projectile":
		return t >= 0.78
	if kind == "beam":
		return t >= 0.42
	if kind == "slash":
		return t >= 0.34
	return t >= 0.28


func _build_projectile() -> void:
	_body = MeshInstance3D.new()
	_body.name = "Projectile"
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = radius_world * 0.22
	mesh.height = radius_world * 0.44
	_body.mesh = mesh
	_body.material_override = _material(primary_color, true, 1.0)
	add_child(_body)
	var core: MeshInstance3D = MeshInstance3D.new()
	var core_mesh: SphereMesh = SphereMesh.new()
	core_mesh.radius = radius_world * 0.10
	core_mesh.height = radius_world * 0.20
	core.mesh = core_mesh
	core.material_override = _material(secondary_color, true, 1.6)
	_body.add_child(core)


func _build_beam() -> void:
	_body = MeshInstance3D.new()
	_body.name = "Beam"
	_beam_mesh = BoxMesh.new()
	_beam_mesh.size = Vector3(trail_width_world * 1.8, trail_width_world * 1.8, 1.0)
	_body.mesh = _beam_mesh
	_body.material_override = _material(primary_color, true, 1.55)
	add_child(_body)
	var core: MeshInstance3D = MeshInstance3D.new()
	core.name = "BeamCore"
	var core_mesh: BoxMesh = BoxMesh.new()
	core_mesh.size = Vector3(trail_width_world * 0.72, trail_width_world * 0.72, 1.0)
	core.mesh = core_mesh
	core.material_override = _material(secondary_color, true, 2.0)
	_body.add_child(core)
	_aux_nodes.append(core)
	_align_beam_geometry()


func _align_beam_geometry() -> void:
	if _body == null or _beam_mesh == null:
		return
	var direction: Vector3 = target_world - source_world
	var length: float = maxf(0.08, direction.length())
	global_position = source_world.lerp(target_world, 0.5)
	follow_position = global_position
	_beam_mesh.size = Vector3(trail_width_world * 1.8, trail_width_world * 1.8, length)
	if not _aux_nodes.is_empty():
		var core: MeshInstance3D = _aux_nodes[0] as MeshInstance3D
		if core != null and core.mesh is BoxMesh:
			(core.mesh as BoxMesh).size = Vector3(trail_width_world * 0.72, trail_width_world * 0.72, length * 1.005)
	if direction.length_squared() > 0.0001:
		look_at(target_world, Vector3.UP, true)


func _build_burst() -> void:
	global_position = target_world
	_body = MeshInstance3D.new()
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = radius_world * 0.18
	mesh.height = radius_world * 0.36
	_body.mesh = mesh
	_body.material_override = _material(primary_color, true, 1.2)
	add_child(_body)
	var count: int = clampi(int(definition.get("particle_count")) if definition != null else 8, 4, 18)
	for index: int in range(count):
		var spark: MeshInstance3D = MeshInstance3D.new()
		var spark_mesh: SphereMesh = SphereMesh.new()
		spark_mesh.radius = radius_world * 0.055
		spark_mesh.height = radius_world * 0.11
		spark.mesh = spark_mesh
		spark.material_override = _material(secondary_color if index % 2 == 0 else primary_color, true, 0.9)
		var angle: float = TAU * float(index) / float(count)
		spark.set_meta("direction", Vector3(cos(angle), 0.30 + 0.12 * float(index % 3), sin(angle)).normalized())
		add_child(spark)
		_aux_nodes.append(spark)


func _build_slash() -> void:
	global_position = target_world + Vector3(0.0, 0.58, 0.0)
	_body = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = Vector3(radius_world * 1.6, 0.055, trail_width_world)
	_body.mesh = mesh
	_body.material_override = _material(primary_color, true, 1.0)
	_body.rotation_degrees = Vector3(0.0, -35.0, -28.0)
	add_child(_body)
	var second: MeshInstance3D = MeshInstance3D.new()
	var second_mesh: BoxMesh = BoxMesh.new()
	second_mesh.size = Vector3(radius_world * 1.25, 0.04, trail_width_world * 0.75)
	second.mesh = second_mesh
	second.material_override = _material(secondary_color, true, 1.2)
	second.rotation_degrees = Vector3(0.0, 38.0, 32.0)
	add_child(second)
	_aux_nodes.append(second)


func _build_ring() -> void:
	global_position = target_world + Vector3(0.0, 0.04, 0.0)
	_body = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = radius_world * 0.26
	mesh.bottom_radius = radius_world * 0.26
	mesh.height = 0.028
	_body.mesh = mesh
	_body.material_override = _material(primary_color, true, 0.8)
	add_child(_body)


func _build_aura() -> void:
	_build_ring()
	if _body != null:
		_body.position.y = 0.06
	var halo: MeshInstance3D = MeshInstance3D.new()
	var halo_mesh: SphereMesh = SphereMesh.new()
	halo_mesh.radius = radius_world * 0.18
	halo_mesh.height = radius_world * 0.36
	halo.mesh = halo_mesh
	halo.material_override = _material(secondary_color, true, 0.55)
	halo.position.y = 0.46
	add_child(halo)
	_aux_nodes.append(halo)


func _build_cross() -> void:
	global_position = target_world + Vector3(0.0, 0.05, 0.0)
	for rotation_y: float in [0.0, 90.0]:
		var arm: MeshInstance3D = MeshInstance3D.new()
		var mesh: BoxMesh = BoxMesh.new()
		mesh.size = Vector3(radius_world * 1.65, 0.035, trail_width_world * 1.6)
		arm.mesh = mesh
		arm.rotation_degrees.y = rotation_y
		arm.material_override = _material(primary_color if rotation_y == 0.0 else secondary_color, true, 0.9)
		add_child(arm)
		_aux_nodes.append(arm)


func _update_beam(t: float) -> void:
	_align_beam_geometry()
	var envelope: float = sin(clampf(t, 0.0, 1.0) * PI)
	var width_scale: float = 0.35 + envelope * 0.95
	if _body != null:
		_body.scale = Vector3(width_scale, width_scale, 1.0)
		var material: StandardMaterial3D = _body.material_override as StandardMaterial3D
		if material != null:
			var beam_color: Color = material.albedo_color
			beam_color.a = clampf(0.15 + envelope * 0.85, 0.0, 1.0)
			material.albedo_color = beam_color
	for node: Node3D in _aux_nodes:
		if node != null:
			var pulse: float = 0.55 + sin(elapsed * 42.0) * 0.10
			node.scale = Vector3(pulse, pulse, 1.0)


func _update_projectile(delta: float, t: float) -> void:
	const TRAVEL_END: float = 0.78
	var travel_t: float = clampf(t / TRAVEL_END, 0.0, 1.0)
	var eased: float = ease(travel_t, -0.35)
	var base: Vector3 = source_world.lerp(target_world, eased)
	base.y += sin(PI * travel_t) * arc_height
	global_position = base
	follow_position = base
	if travel_t < 1.0:
		if _body != null:
			var pulse: float = 1.0 + sin(elapsed * 24.0) * 0.14
			_body.scale = Vector3.ONE * pulse
		_trail_accumulator += delta
		if _trail_accumulator >= 0.035:
			_trail_accumulator = 0.0
			_spawn_trail_point()
	else:
		global_position = target_world
		follow_position = target_world
		if _body != null:
			_body.visible = false
		if not _projectile_burst_spawned:
			_projectile_burst_spawned = true
			_spawn_projectile_impact_sparks()
		var impact_t: float = clampf((t - TRAVEL_END) / (1.0 - TRAVEL_END), 0.0, 1.0)
		_update_projectile_impact(impact_t)


func _spawn_projectile_impact_sparks() -> void:
	var count: int = clampi(int(definition.get("particle_count")) if definition != null else 7, 5, 14)
	for index: int in range(count):
		var spark: MeshInstance3D = MeshInstance3D.new()
		var mesh: SphereMesh = SphereMesh.new()
		mesh.radius = radius_world * 0.06
		mesh.height = radius_world * 0.12
		spark.mesh = mesh
		spark.material_override = _material(secondary_color if index % 2 == 0 else primary_color, true, 1.0)
		var angle: float = TAU * float(index) / float(count)
		var vertical: float = 0.18 + 0.14 * float(index % 4)
		spark.set_meta("impact_direction", Vector3(cos(angle), vertical, sin(angle)).normalized())
		add_child(spark)
		_aux_nodes.append(spark)


func _update_projectile_impact(t: float) -> void:
	for node: Node3D in _aux_nodes:
		if node == null or not node.has_meta("impact_direction"):
			continue
		var direction_value: Variant = node.get_meta("impact_direction")
		if not (direction_value is Vector3):
			continue
		var direction: Vector3 = direction_value
		node.position = direction * radius_world * 1.25 * t
		var scale_value: float = maxf(0.05, 1.0 - t)
		node.scale = Vector3.ONE * scale_value


func _spawn_trail_point() -> void:
	var node: MeshInstance3D = MeshInstance3D.new()
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = trail_width_world * 0.55
	mesh.height = trail_width_world * 1.1
	node.mesh = mesh
	var mat: StandardMaterial3D = _material(primary_color, true, 0.45)
	node.material_override = mat
	get_parent().add_child(node)
	node.global_position = global_position
	_trail_points.append({"node": node, "age": 0.0, "life": 0.24, "material": mat})


func _clear_trail_points() -> void:
	for entry: Dictionary in _trail_points:
		var node: MeshInstance3D = entry.get("node") as MeshInstance3D
		if node != null and is_instance_valid(node):
			node.queue_free()
	_trail_points.clear()


func _update_trail(delta: float) -> void:
	for index: int in range(_trail_points.size() - 1, -1, -1):
		var entry: Dictionary = _trail_points[index]
		var node: MeshInstance3D = entry.get("node") as MeshInstance3D
		var mat: StandardMaterial3D = entry.get("material") as StandardMaterial3D
		var age: float = float(entry.get("age", 0.0)) + delta
		var life: float = maxf(0.05, float(entry.get("life", 0.2)))
		if node == null or age >= life:
			if node != null:
				node.queue_free()
			_trail_points.remove_at(index)
			continue
		entry["age"] = age
		_trail_points[index] = entry
		var alpha: float = 1.0 - age / life
		node.scale = Vector3.ONE * (0.35 + alpha * 0.65)
		if mat != null:
			var c: Color = mat.albedo_color
			c.a = alpha * 0.65
			mat.albedo_color = c


func _update_burst(t: float) -> void:
	var burst_scale: float = 0.3 + sin(minf(1.0, t) * PI) * 1.35
	if _body != null:
		_body.scale = Vector3.ONE * burst_scale
	for index: int in range(_aux_nodes.size()):
		var node: Node3D = _aux_nodes[index]
		if node == null:
			continue
		var direction_value: Variant = node.get_meta("direction", Vector3.RIGHT)
		var direction: Vector3 = Vector3.RIGHT
		if direction_value is Vector3:
			direction = direction_value
		node.position = direction * radius_world * 1.15 * t
		var fade: float = maxf(0.0, 1.0 - t)
		node.scale = Vector3.ONE * (0.35 + fade * 0.85)


func _update_slash(t: float) -> void:
	var wave: float = sin(minf(1.0, t) * PI)
	if _body != null:
		_body.scale = Vector3(0.25 + wave * 1.1, 1.0, 0.25 + wave * 0.8)
	for node: Node3D in _aux_nodes:
		if node != null:
			node.scale = Vector3(0.2 + wave, 1.0, 0.2 + wave * 0.8)


func _update_ring_like(t: float) -> void:
	var scale_value: float = 0.28 + t * 1.8
	if _body != null:
		_body.scale = Vector3(scale_value, 1.0, scale_value)
	for node: Node3D in _aux_nodes:
		if node != null:
			node.scale = Vector3.ONE * (0.75 + sin(t * PI) * 0.55)


func _update_cross(t: float) -> void:
	var wave: float = sin(minf(1.0, t) * PI)
	for node: Node3D in _aux_nodes:
		if node != null:
			node.scale = Vector3(0.2 + wave * 1.25, 1.0, 0.5 + wave * 0.5)


func _material(color: Color, emission: bool, energy: float) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	if emission:
		material.emission_enabled = true
		material.emission = Color(color.r, color.g, color.b, 1.0)
		material.emission_energy_multiplier = energy
	return material
