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
	if kind == "bullet":
		duration = clampf(duration * 0.72, 0.22, 0.34)
		arc_height = 0.0
		radius_world = minf(radius_world, 0.36)
		trail_width_world = minf(trail_width_world, 0.055)
	global_position = source_world
	follow_position = source_world


func start() -> void:
	if started:
		return
	started = true
	match kind:
		"heal_bloom_fx":
			_build_heal_bloom_fx()
		"mist_field":
			_build_mist_field()
		"mark_target":
			_build_mark_target()
		"taunt_wave":
			_build_taunt_wave()
		"prism_shot":
			_build_prism_shot()
		"bullet":
			_build_bullet()
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
		"heal_bloom_fx":
			_update_heal_bloom_fx(t)
		"mist_field":
			_update_mist_field(t)
		"mark_target":
			_update_mark_target(t)
		"taunt_wave":
			_update_taunt_wave(t)
		"prism_shot":
			_update_prism_shot(delta, t)
		"bullet":
			_update_bullet(delta, t)
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
	if kind == "bullet":
		return t >= 0.82
	if kind == "projectile":
		return t >= 0.78
	if kind == "beam":
		return t >= 0.42
	if kind == "slash":
		return t >= 0.34
	return t >= 0.28


func _build_bullet() -> void:
	_body = MeshInstance3D.new()
	_body.name = "BulletTracer"

	var tracer_mesh: BoxMesh = BoxMesh.new()
	tracer_mesh.size = Vector3(
		maxf(0.025, trail_width_world * 0.65),
		maxf(0.025, trail_width_world * 0.65),
		maxf(0.20, radius_world * 0.72)
	)
	_body.mesh = tracer_mesh
	_body.material_override = _material(Color(1.0, 0.90, 0.52, 1.0), true, 2.4)
	add_child(_body)

	var core: MeshInstance3D = MeshInstance3D.new()
	core.name = "BulletCore"
	var core_mesh: BoxMesh = BoxMesh.new()
	core_mesh.size = Vector3(
		maxf(0.012, trail_width_world * 0.26),
		maxf(0.012, trail_width_world * 0.26),
		maxf(0.23, radius_world * 0.82)
	)
	core.mesh = core_mesh
	core.material_override = _material(Color.WHITE, true, 3.1)
	_body.add_child(core)

	var direction: Vector3 = target_world - source_world
	if direction.length_squared() > 0.0001:
		look_at(target_world, Vector3.UP, true)


func _update_bullet(delta: float, t: float) -> void:
	const TRAVEL_END: float = 0.82
	var travel_t: float = clampf(t / TRAVEL_END, 0.0, 1.0)
	var eased: float = smoothstep(0.0, 1.0, travel_t)

	global_position = source_world.lerp(target_world, eased)
	follow_position = global_position

	if travel_t < 1.0:
		if _body != null:
			var pulse: float = 1.0 + sin(elapsed * 52.0) * 0.08
			_body.scale = Vector3(1.0, 1.0, pulse)

		_trail_accumulator += delta
		if _trail_accumulator >= 0.025:
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

		var impact_t: float = clampf(
			(t - TRAVEL_END) / (1.0 - TRAVEL_END),
			0.0,
			1.0
		)
		_update_projectile_impact(impact_t)


func _build_heal_bloom_fx() -> void:
	global_position = target_world

	_body = MeshInstance3D.new()
	_body.name = "HealRing"
	var ring_mesh: CylinderMesh = CylinderMesh.new()
	ring_mesh.top_radius = radius_world * 0.34
	ring_mesh.bottom_radius = radius_world * 0.42
	ring_mesh.height = 0.035
	_body.mesh = ring_mesh
	_body.material_override = _material(
		Color(0.36, 0.95, 0.58, 0.70),
		true,
		1.4
	)
	add_child(_body)

	for index: int in range(8):
		var spark: MeshInstance3D = MeshInstance3D.new()
		var mesh: SphereMesh = SphereMesh.new()
		mesh.radius = 0.045
		mesh.height = 0.09
		spark.mesh = mesh
		spark.material_override = _material(
			Color(0.82, 1.0, 0.72, 0.92) if index % 2 == 0 else Color(1.0, 0.88, 0.48, 0.92),
			true,
			1.8
		)
		var angle: float = TAU * float(index) / 8.0
		spark.position = Vector3(
			cos(angle) * radius_world * 0.30,
			0.06,
			sin(angle) * radius_world * 0.30
		)
		spark.set_meta("heal_angle", angle)
		spark.set_meta("heal_index", index)
		add_child(spark)
		_aux_nodes.append(spark)


func _update_heal_bloom_fx(t: float) -> void:
	if _body != null:
		var ring_scale: float = 0.35 + t * 1.65
		_body.scale = Vector3(ring_scale, 1.0, ring_scale)

	for node: Node3D in _aux_nodes:
		if node == null:
			continue
		var angle: float = float(node.get_meta("heal_angle", 0.0))
		var index: int = int(node.get_meta("heal_index", 0))
		var orbit: float = radius_world * (0.26 + t * 0.20)
		node.position.x = cos(angle + t * 1.8) * orbit
		node.position.z = sin(angle + t * 1.8) * orbit
		node.position.y = 0.08 + t * (0.68 + 0.04 * float(index % 3))
		var pulse: float = 0.72 + sin(t * PI * 4.0 + float(index)) * 0.16
		node.scale = Vector3.ONE * pulse


func _build_mist_field() -> void:
	global_position = target_world

	for index: int in range(10):
		var cloud: MeshInstance3D = MeshInstance3D.new()
		var mesh: SphereMesh = SphereMesh.new()
		mesh.radius = 0.24
		mesh.height = 0.34
		mesh.radial_segments = 10
		mesh.rings = 5
		cloud.mesh = mesh

		var cloud_color: Color = Color(0.50, 0.88, 0.78, 0.26)
		if index % 2 != 0:
			cloud_color = Color(0.66, 0.82, 0.96, 0.22)

		cloud.material_override = _material(cloud_color, true, 0.55)

		var angle: float = TAU * float(index) / 10.0
		var radius_value: float = 0.18 + 0.06 * float(index % 4)
		cloud.position = Vector3(
			cos(angle) * radius_value,
			0.10 + 0.03 * float(index % 3),
			sin(angle) * radius_value
		)
		cloud.set_meta("mist_angle", angle)
		cloud.set_meta("mist_radius", radius_value)
		cloud.set_meta("mist_index", index)
		add_child(cloud)
		_aux_nodes.append(cloud)


func _update_mist_field(t: float) -> void:
	for node: Node3D in _aux_nodes:
		if node == null:
			continue

		var angle: float = float(node.get_meta("mist_angle", 0.0))
		var base_radius: float = float(node.get_meta("mist_radius", 0.2))
		var index: int = int(node.get_meta("mist_index", 0))
		var spread: float = base_radius + t * radius_world * 0.55

		node.position.x = cos(angle + t * 0.65) * spread
		node.position.z = sin(angle + t * 0.65) * spread
		node.position.y = 0.10 + sin(t * PI + float(index) * 0.5) * 0.08

		var cloud_scale: float = 0.42 + sin(t * PI) * 1.10
		node.scale = Vector3(
			cloud_scale * 1.25,
			cloud_scale * 0.65,
			cloud_scale
		)


func _build_mark_target() -> void:
	global_position = target_world

	for index: int in range(4):
		var bracket: MeshInstance3D = MeshInstance3D.new()
		var mesh: BoxMesh = BoxMesh.new()
		mesh.size = Vector3(0.26, 0.045, 0.055)
		bracket.mesh = mesh
		bracket.material_override = _material(
			Color(0.42, 0.82, 1.0, 0.92),
			true,
			2.0
		)

		var angle: float = TAU * float(index) / 4.0
		bracket.position = Vector3(
			cos(angle) * 0.40,
			0.55,
			sin(angle) * 0.40
		)
		bracket.rotation.y = -angle
		bracket.set_meta("mark_angle", angle)
		add_child(bracket)
		_aux_nodes.append(bracket)

	_body = MeshInstance3D.new()
	_body.name = "MarkCore"
	var core_mesh: SphereMesh = SphereMesh.new()
	core_mesh.radius = 0.08
	core_mesh.height = 0.16
	_body.mesh = core_mesh
	_body.position = Vector3(0.0, 0.85, 0.0)
	_body.material_override = _material(Color.WHITE, true, 2.8)
	add_child(_body)


func _update_mark_target(t: float) -> void:
	var lock_radius: float = lerpf(0.72, 0.32, minf(1.0, t * 1.25))

	for node: Node3D in _aux_nodes:
		if node == null:
			continue
		var angle: float = float(node.get_meta("mark_angle", 0.0))
		node.position.x = cos(angle + t * 1.2) * lock_radius
		node.position.z = sin(angle + t * 1.2) * lock_radius
		node.position.y = 0.54 + sin(t * PI * 2.0 + angle) * 0.05
		node.rotation.y = -(angle + t * 1.2)

	if _body != null:
		var pulse: float = 0.65 + sin(t * PI * 4.0) * 0.20
		_body.scale = Vector3.ONE * pulse
		_body.position.y = 0.82 + sin(t * PI * 2.0) * 0.08


func _build_taunt_wave() -> void:
	global_position = target_world

	_body = MeshInstance3D.new()
	_body.name = "TauntWave"

	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = 0.34
	mesh.bottom_radius = 0.42
	mesh.height = 0.035
	_body.mesh = mesh
	_body.material_override = _material(
		Color(1.0, 0.70, 0.24, 0.65),
		true,
		1.8
	)
	add_child(_body)

	var inner: MeshInstance3D = MeshInstance3D.new()
	var inner_mesh: CylinderMesh = CylinderMesh.new()
	inner_mesh.top_radius = 0.22
	inner_mesh.bottom_radius = 0.28
	inner_mesh.height = 0.045
	inner.mesh = inner_mesh
	inner.material_override = _material(
		Color(1.0, 0.34, 0.24, 0.58),
		true,
		1.6
	)
	add_child(inner)
	_aux_nodes.append(inner)


func _update_taunt_wave(t: float) -> void:
	var outer_scale: float = 0.32 + t * 3.0
	if _body != null:
		_body.scale = Vector3(outer_scale, 1.0, outer_scale)

	for node: Node3D in _aux_nodes:
		if node == null:
			continue
		var inner_scale: float = 0.26 + t * 2.25
		node.scale = Vector3(inner_scale, 1.0, inner_scale)


func _build_prism_shot() -> void:
	_body = MeshInstance3D.new()
	_body.name = "PrismShot"

	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = Vector3(0.05, 0.05, 0.42)
	_body.mesh = mesh
	_body.material_override = _material(
		Color(0.38, 0.84, 1.0, 1.0),
		true,
		2.6
	)
	add_child(_body)

	var core: MeshInstance3D = MeshInstance3D.new()
	var core_mesh: BoxMesh = BoxMesh.new()
	core_mesh.size = Vector3(0.018, 0.018, 0.48)
	core.mesh = core_mesh
	core.material_override = _material(Color.WHITE, true, 3.2)
	_body.add_child(core)

	var direction: Vector3 = target_world - source_world
	if direction.length_squared() > 0.0001:
		look_at(target_world, Vector3.UP, true)


func _update_prism_shot(delta: float, t: float) -> void:
	const TRAVEL_END: float = 0.82
	var travel_t: float = clampf(t / TRAVEL_END, 0.0, 1.0)
	var eased: float = ease(travel_t, -0.18)

	var base: Vector3 = source_world.lerp(target_world, eased)
	base.y += sin(PI * travel_t) * 0.10
	global_position = base
	follow_position = base

	if travel_t < 1.0:
		if _body != null:
			var pulse: float = 1.0 + sin(elapsed * 40.0) * 0.10
			_body.scale = Vector3(pulse, pulse, 1.0)

		_trail_accumulator += delta
		if _trail_accumulator >= 0.030:
			_trail_accumulator = 0.0
			_spawn_trail_point()
	else:
		if _body != null:
			_body.visible = false
		if not _projectile_burst_spawned:
			_projectile_burst_spawned = true
			_spawn_projectile_impact_sparks()


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
	_spawn_comic_radial_lines(10, radius_world * 1.45, 0.42, primary_color)
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
	_spawn_comic_radial_lines(8, radius_world * 1.15, 0.52, primary_color)
	_spawn_comic_onomatopoeia("TCHAK !", primary_color, 0.98)


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
	_spawn_comic_radial_lines(8, radius_world * 1.05, 0.36, secondary_color)
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



func _spawn_comic_radial_lines(
	count: int,
	radius_value: float,
	height_value: float,
	accent: Color
) -> void:
	var resolved_count: int = maxi(4, count)
	for index: int in range(resolved_count):
		var line := MeshInstance3D.new()
		line.name = "ComicImpactLine_%d" % index
		var mesh := BoxMesh.new()
		var length: float = radius_value * (0.72 + 0.10 * float(index % 4))
		mesh.size = Vector3(0.025 + 0.008 * float(index % 2), 0.025, length)
		line.mesh = mesh
		var color := Color(0.02, 0.02, 0.02, 0.94)
		if index % 5 == 0:
			color = Color(accent.r, accent.g, accent.b, 0.88)
		line.material_override = _material(color, index % 5 == 0, 0.9 if index % 5 == 0 else 0.0)
		var angle: float = TAU * float(index) / float(resolved_count)
		line.rotation.y = -angle
		line.rotation.z = deg_to_rad(-18.0 + 9.0 * float(index % 5))
		line.position = Vector3(
			cos(angle) * radius_value * 0.34,
			height_value + 0.035 * float(index % 3),
			sin(angle) * radius_value * 0.34
		)
		line.scale = Vector3(0.22, 1.0, 0.22)
		add_child(line)

		var tween := create_tween()
		tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tween.tween_property(line, "scale", Vector3.ONE, 0.12 + 0.012 * float(index % 3))
		tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
		tween.tween_property(line, "scale", Vector3(0.08, 1.0, 0.08), 0.18)


func _spawn_comic_onomatopoeia(text_value: String, accent: Color, height_value: float) -> void:
	var label := Label3D.new()
	label.name = "ComicOnomatopoeia"
	label.text = text_value
	label.font_size = 34
	label.outline_size = 10
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.modulate = accent
	label.outline_modulate = Color(0.02, 0.02, 0.02, 1.0)
	label.position = Vector3(0.18, height_value, 0.0)
	label.rotation.z = deg_to_rad(-8.0)
	label.scale = Vector3(0.58, 0.58, 0.58)
	add_child(label)

	var tween := create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(label, "scale", Vector3.ONE, 0.14)
	tween.tween_property(label, "position:y", height_value + 0.22, 0.18)
	tween.set_parallel(false)
	tween.tween_interval(0.10)
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tween.tween_property(label, "scale", Vector3(0.72, 0.72, 0.72), 0.16)
	tween.tween_property(label, "modulate", Color(accent.r, accent.g, accent.b, 0.0), 0.16)


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
