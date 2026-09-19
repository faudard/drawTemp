@tool
class_name SporeTacticalTile3D
extends Node3D

## One editable logical cell of a SporeMap3D.
## Cell/elevation/type are the authored data; the colored block is generated
## automatically in the editor so the scene remains asset-free and portable.

@export_group("Cell")
@export var cell: Vector2i = Vector2i.ZERO:
	set(value):
		cell = value
		_refresh_deferred()
@export_range(0, 8, 1) var elevation: int = 0:
	set(value):
		elevation = maxi(0, value)
		_refresh_deferred()
@export_enum("ground", "obstacle", "cover", "hazard", "extraction", "bonus", "crown") var terrain_type: String = "ground":
	set(value):
		terrain_type = value
		_refresh_deferred()
@export_enum("north", "east", "south", "west") var cover_facing: String = "north":
	set(value):
		cover_facing = value
		_refresh_deferred()

@export_group("Visual")
@export var display_label: String = "":
	set(value):
		display_label = value
		_refresh_deferred()

var _refresh_queued: bool = false


func spore_map_role() -> String:
	return "tile"


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
	position = map.cell_to_local(cell, elevation)
	_rebuild_visual(map)
	map.queue_marker_refresh()


func _rebuild_visual(map: SporeMap3D) -> void:
	var body: MeshInstance3D = get_node_or_null("_EditorBody") as MeshInstance3D
	if body == null:
		body = MeshInstance3D.new()
		body.name = "_EditorBody"
		add_child(body, false, Node.INTERNAL_MODE_BACK)

	var top: MeshInstance3D = get_node_or_null("_EditorTop") as MeshInstance3D
	if top == null:
		top = MeshInstance3D.new()
		top.name = "_EditorTop"
		add_child(top, false, Node.INTERNAL_MODE_BACK)

	var total_height: float = 0.34 + float(elevation) * map.elevation_step
	var body_mesh: BoxMesh = BoxMesh.new()
	body_mesh.size = Vector3(map.tile_size * 0.975, total_height, map.tile_size * 0.975)
	body.mesh = body_mesh
	body.position = Vector3(0.0, -total_height * 0.5 - 0.02, 0.0)
	body.material_override = _surface_material(_side_color(), 0.022, 0.0)

	var top_mesh: BoxMesh = BoxMesh.new()
	top_mesh.size = Vector3(map.tile_size * 0.955, 0.10, map.tile_size * 0.955)
	top.mesh = top_mesh
	top.position = Vector3(0.0, -0.05, 0.0)
	top.material_override = _surface_material(_top_color(), 0.050, _surface_emission())

	var rim: MeshInstance3D = get_node_or_null("_EditorRim") as MeshInstance3D
	if rim == null:
		rim = MeshInstance3D.new()
		rim.name = "_EditorRim"
		add_child(rim, false, Node.INTERNAL_MODE_BACK)
	var rim_mesh: BoxMesh = BoxMesh.new()
	rim_mesh.size = Vector3(map.tile_size * 0.965, 0.035, map.tile_size * 0.965)
	rim.mesh = rim_mesh
	rim.position = Vector3(0.0, -0.092, 0.0)
	rim.material_override = _material(_side_color().darkened(0.10))
	rim.visible = false

	var label: Label3D = get_node_or_null("_EditorLabel") as Label3D
	if label == null:
		label = Label3D.new()
		label.name = "_EditorLabel"
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.font_size = 28
		label.outline_size = 6
		add_child(label, false, Node.INTERNAL_MODE_BACK)
	var text: String = display_label
	if not Engine.is_editor_hint():
		text = _runtime_terrain_label()
	elif text.is_empty() and map.show_cell_coordinates:
		text = "%d,%d  h%d" % [cell.x, cell.y, elevation]
	label.text = text
	# IMMERSIVE_GARDEN: author labels are editor aids; runtime uses HUD/objective markers.
	label.visible = not text.is_empty() and Engine.is_editor_hint()
	label.position = Vector3(0.0, 0.22, 0.0)
	_rebuild_terrain_prop(map)
	_rebuild_ground_detail(map)


func _runtime_terrain_label() -> String:
	match terrain_type:
		"obstacle":
			return "ROCHER"
		"cover":
			return "COUVERT"
		"hazard":
			return "SPORES"
		"extraction":
			return "SORTIE"
		"bonus":
			return "VINYLE"
		"crown":
			return "COURONNE"
	return ""


func _rebuild_ground_detail(map: SporeMap3D) -> void:
	var root: Node3D = get_node_or_null("_EditorGroundDetail") as Node3D
	if root == null:
		root = Node3D.new()
		root.name = "_EditorGroundDetail"
		add_child(root, false, Node.INTERNAL_MODE_BACK)

	# Runtime stays clean: no per-cell moss/mushroom geometry.
	if not Engine.is_editor_hint():
		root.visible = false
		return

	root.visible = false


func _rebuild_terrain_prop(map: SporeMap3D) -> void:
	var prop: MeshInstance3D = get_node_or_null("_EditorProp") as MeshInstance3D
	if prop == null:
		prop = MeshInstance3D.new()
		prop.name = "_EditorProp"
		add_child(prop, false, Node.INTERNAL_MODE_BACK)

	prop.visible = terrain_type in ["obstacle", "cover", "hazard", "bonus", "crown"]
	prop.rotation = Vector3.ZERO
	prop.position = Vector3.ZERO
	prop.scale = Vector3.ONE
	if not prop.visible:
		prop.mesh = null
		return

	var color: Color = _top_color().lightened(0.06)
	match terrain_type:
		"obstacle":
			# Organic boulder instead of a gameplay-looking cube.
			var obstacle_mesh: SphereMesh = SphereMesh.new()
			obstacle_mesh.radius = 0.5
			obstacle_mesh.height = 1.0
			obstacle_mesh.radial_segments = 12
			obstacle_mesh.rings = 7
			prop.mesh = obstacle_mesh
			prop.scale = Vector3(0.92, 1.18, 0.84)
			prop.position.y = 0.49
			prop.rotation.y = float((cell.x * 19 + cell.y * 11) % 8) * 0.18

		"cover":
			# Mossy log silhouette: keeps the cover direction readable.
			var cover_mesh: CylinderMesh = CylinderMesh.new()
			cover_mesh.top_radius = 0.15
			cover_mesh.bottom_radius = 0.18
			cover_mesh.height = map.tile_size * 0.70
			cover_mesh.radial_segments = 10
			prop.mesh = cover_mesh
			if cover_facing in ["east", "west"]:
				prop.rotation.x = PI * 0.5
			else:
				prop.rotation.z = PI * 0.5
			var offset: Vector2i = _cover_direction()
			prop.position.x = float(offset.x) * map.tile_size * 0.25
			prop.position.z = float(offset.y) * map.tile_size * 0.25
			prop.position.y = 0.18

		"hazard":
			var hazard_mesh: CylinderMesh = CylinderMesh.new()
			hazard_mesh.top_radius = map.tile_size * 0.31
			hazard_mesh.bottom_radius = map.tile_size * 0.35
			hazard_mesh.height = 0.055
			hazard_mesh.radial_segments = 24
			prop.mesh = hazard_mesh
			prop.position.y = 0.028

		"bonus":
			var bonus_mesh: CylinderMesh = CylinderMesh.new()
			bonus_mesh.top_radius = 0.18
			bonus_mesh.bottom_radius = 0.18
			bonus_mesh.height = 0.08
			bonus_mesh.radial_segments = 24
			prop.mesh = bonus_mesh
			prop.rotation.z = PI * 0.5
			prop.position.y = 0.28

		"crown":
			var crown_mesh: CylinderMesh = CylinderMesh.new()
			crown_mesh.top_radius = 0.16
			crown_mesh.bottom_radius = 0.29
			crown_mesh.height = 0.38
			crown_mesh.radial_segments = 12
			prop.mesh = crown_mesh
			prop.position.y = 0.22

	prop.material_override = _material(color)


func cover_direction() -> Vector2i:
	return _cover_direction()


func _cover_direction() -> Vector2i:
	match cover_facing:
		"east":
			return Vector2i.RIGHT
		"south":
			return Vector2i.DOWN
		"west":
			return Vector2i.LEFT
	return Vector2i.UP



static var _tile_surface_shader_cache: Shader = null


func _tile_surface_shader() -> Shader:
	if _tile_surface_shader_cache != null:
		return _tile_surface_shader_cache

	var shader: Shader = Shader.new()
	shader.code = """
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform vec4 base_color : source_color = vec4(0.3, 0.45, 0.3, 1.0);
uniform float variation = 0.04;
uniform float emission_strength = 0.0;
uniform float pattern_phase = 0.0;

void fragment() {
	float broad = sin(UV.x * 8.0 + UV.y * 5.0 + pattern_phase) * 0.5 + 0.5;
	float fine = sin(UV.x * 31.0 - UV.y * 23.0 + pattern_phase * 1.7) * 0.5 + 0.5;
	float grain = ((broad - 0.5) * 0.65 + (fine - 0.5) * 0.35) * variation;
	float hatch_a = smoothstep(0.965, 1.0, sin((UV.x + UV.y) * 34.0 + pattern_phase) * 0.5 + 0.5);
	float hatch_b = smoothstep(0.975, 1.0, sin((UV.x - UV.y) * 49.0 - pattern_phase * 0.7) * 0.5 + 0.5);
	float ink_wear = hatch_a * 0.075 + hatch_b * 0.045;
	vec3 c = clamp(base_color.rgb * (1.0 + grain) - vec3(ink_wear), vec3(0.0), vec3(1.0));
	ALBEDO = c;
	ROUGHNESS = 0.94;
	METALLIC = 0.0;
	EMISSION = c * emission_strength;
}
"""
	_tile_surface_shader_cache = shader
	return shader


func _surface_material(color: Color, variation: float, emission_strength: float) -> ShaderMaterial:
	var material: ShaderMaterial = ShaderMaterial.new()
	material.shader = _tile_surface_shader()
	material.set_shader_parameter("base_color", color)
	material.set_shader_parameter("variation", variation)
	material.set_shader_parameter("emission_strength", emission_strength)
	var cell_hash: int = absi(cell.x * 193 + cell.y * 389)
	material.set_shader_parameter("pattern_phase", float(cell_hash % 19) * 0.73)
	return material


func _surface_emission() -> float:
	match terrain_type:
		"hazard":
			return 0.055
		"extraction":
			return 0.045
		"bonus":
			return 0.035
		"crown":
			return 0.075
	return 0.0


func _material(color: Color) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.metallic = 0.0
	material.roughness = 0.96

	# Only gameplay landmarks get a very restrained emissive cue.
	if terrain_type in ["hazard", "bonus", "crown", "extraction"]:
		material.emission_enabled = true
		material.emission = color.darkened(0.30)
		material.emission_energy_multiplier = 0.08 if terrain_type != "crown" else 0.14

	return material


func _top_color() -> Color:
	match terrain_type:
		"obstacle":
			return Color("#3c3d39")
		"cover":
			return Color("#4d4234")
		"hazard":
			return Color("#503b5b")
		"extraction":
			return Color("#275140")
		"bonus":
			return Color("#315566")
		"crown":
			return Color("#745f31")
		_:
			var elevation_light: float = minf(0.055, float(elevation) * 0.018)
			var hash_value: int = absi(cell.x * 92821 + cell.y * 68917)
			var variation: float = float(hash_value % 5) * 0.007 - 0.014
			return Color(
				0.170 + elevation_light + variation,
				0.205 + elevation_light + variation,
				0.170 + elevation_light + variation * 0.5,
				1.0
			)


func _side_color() -> Color:
	return _top_color().darkened(0.34)


func _map_parent() -> SporeMap3D:
	var node: Node = get_parent()
	while node != null:
		if node is SporeMap3D:
			return node as SporeMap3D
		node = node.get_parent()
	return null
