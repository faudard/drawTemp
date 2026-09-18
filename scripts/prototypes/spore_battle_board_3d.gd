class_name SporeBattleBoard3D
extends Node3D

const MissionCatalog = preload("res://scripts/catalogs/mission_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")
const VfxCatalog = preload("res://scripts/catalogs/vfx_catalog.gd")
const ActionVfxScript = preload("res://scripts/prototypes/spore_action_vfx_3d.gd")
const UnitActorScript = preload("res://scripts/maps/spore_unit_actor_3d.gd")
const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")

const MODE_MOVE: String = "move"
const MODE_ATTACK: String = "attack"
const MODE_SKILL: String = "skill"

const ACTION_ATTACK: String = "attack"
const ACTION_SKILL: String = "skill"

@export_group("Mission")
@export_range(0, 99, 1) var mission_index: int = 0
@export var map_scene_path: String = "res://maps/mission_1_map.tscn"
@export var hero_unit_ids: PackedStringArray = PackedStringArray(["momo", "pipo", "luma"])

@export_group("Rules")
@export_range(0, 8, 1) var max_jump_up: int = 1
@export_range(0, 8, 1) var max_jump_down: int = 2
@export_range(0, 6, 1) var side_attack_bonus: int = 1
@export_range(0, 8, 1) var back_attack_bonus: int = 2
@export var height_attack_tolerance: int = 3
@export_range(0, 8, 1) var skill_target_height_tolerance: int = 3
@export_range(0, 8, 1) var skill_area_height_tolerance: int = 2
@export_range(0, 4, 1) var los_block_height_advantage: int = 1
@export_range(0, 4, 1) var ranged_cover_reduction: int = 1
@export_range(0, 4, 1) var intercept_damage_reduction: int = 1
@export_range(0, 4, 1) var opportunity_damage_penalty: int = 1
@export var show_reachable_overlay: bool = true

@export_group("Camera")
@export var camera_distance: float = 12.5
@export var camera_height: float = 11.0
@export var camera_angle_degrees: float = -38.0
@export var zoom_min: float = 5.0
@export var zoom_max: float = 18.0
@export var camera_follow_active: bool = true
@export_range(1.0, 20.0, 0.5) var camera_smoothing: float = 7.5
@export var action_camera_enabled: bool = true
@export_range(0.15, 1.2, 0.05) var action_camera_duration: float = 0.48
@export_range(0.0, 4.0, 0.1) var action_camera_zoom_in: float = 1.6
@export_range(0.0, 0.35, 0.01) var impact_shake_strength: float = 0.10
@export var show_action_wheel: bool = true

@export_group("Action VFX")
@export var action_vfx_enabled: bool = true
@export var projectile_camera_follow: bool = true
@export_range(0.0, 4.0, 0.1) var projectile_camera_zoom_in: float = 2.2
@export_range(0.0, 1.0, 0.05) var vfx_impact_pause: float = 0.05
@export var aoe_cell_impacts_enabled: bool = true
@export_range(0.0, 0.20, 0.005) var aoe_cell_impact_stagger: float = 0.035
@export var status_tick_vfx_enabled: bool = true

var map_root: SporeMap3D = null
var actors_by_cell: Dictionary = {}
var player_actors: Array[SporeUnitActor3D] = []
var enemy_actors: Array[SporeUnitActor3D] = []
var turn_order: Array[SporeUnitActor3D] = []
var active_actor: SporeUnitActor3D = null
var selected_actor: SporeUnitActor3D = null
var turn_index: int = -1
var round_number: int = 1
var input_mode: String = MODE_MOVE
var hovered_cell: Vector2i = Vector2i(-1, -1)
var reachable_cells: Dictionary = {}
var attack_cells: Dictionary = {}
var skill_target_cells: Dictionary = {}
var skill_preview_cells: Array[Vector2i] = []
var selected_skill_id: String = ""
var path_parents: Dictionary = {}
var preview_path_cells: Array[Vector2i] = []
var battle_finished: bool = false
var enemy_busy: bool = false
var player_busy: bool = false
var battle_log: Array[String] = []
var persistent_zones: Array[Dictionary] = []
var pending_action: Dictionary = {}
var _zone_serial: int = 0
var battle_clock_ticks: int = 0
var activation_count_in_round: int = 0
var round_activation_budget: int = 1
var activated_this_round: Dictionary = {}
var battle_rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _skill_hit_cache: Dictionary = {}

var _camera_rig: Node3D
var _camera: Camera3D
var _light: DirectionalLight3D
var _map_holder: Node3D
var _actor_holder: Node3D
var _highlight_holder: Node3D
var _zone_holder: Node3D
var _vfx_holder: Node3D
var _cursor_mesh: MeshInstance3D
var _ui_layer: CanvasLayer
var _info_label: Label
var _help_label: Label
var _turn_label: Label
var _log_label: Label
var _move_button: Button
var _attack_button: Button
var _end_button: Button
var _face_button: Button
var _primary_skill_button: Button
var _secondary_skill_button: Button
var _preview_panel: Panel
var _preview_title: Label
var _preview_body: Label
var _preview_confirm_button: Button
var _preview_cancel_button: Button
var _timeline_panel: Panel
var _timeline_bar: HBoxContainer
var _unit_card_panel: Panel
var _unit_card_title: Label
var _unit_card_body: Label
var _unit_portrait: TextureRect
var _unit_hp_bar: ProgressBar
var _unit_focus_bar: ProgressBar
var _action_wheel: Panel
var _action_wheel_label: Label
var _wheel_move_button: Button
var _wheel_attack_button: Button
var _wheel_primary_button: Button
var _wheel_secondary_button: Button
var _wheel_face_button: Button
var _wheel_end_button: Button
var _camera_current_angle: float = 0.0
var _camera_target_angle: float = 0.0
var _camera_current_distance: float = 12.5
var _camera_target_distance: float = 12.5
var _camera_focus_current: Vector3 = Vector3.ZERO
var _camera_focus_target: Vector3 = Vector3.ZERO
var _camera_initialized: bool = false
var _timeline_signature: String = ""
var _unit_card_last_actor: SporeUnitActor3D = null
var _presentation_time: float = 0.0
var _cursor_bob: float = 0.0
var _action_camera_timer: float = 0.0
var _action_camera_focus: Vector3 = Vector3.ZERO
var _action_camera_zoom: float = 0.0
var _camera_shake_strength: float = 0.0
var _impact_zoom_timer: float = 0.0
var _projectile_follow_vfx: SporeActionVfx3D = null


func _ready() -> void:
	_ensure_runtime_nodes()
	_load_map()
	_spawn_runtime_units()
	_build_turn_order()
	_start_next_activation()
	_update_ui_text()


func _unhandled_input(event: InputEvent) -> void:
	if _camera == null or map_root == null or battle_finished:
		return
	if event is InputEventMouseMotion:
		var next_hovered: Vector2i = _screen_to_cell((event as InputEventMouseMotion).position)
		if next_hovered != hovered_cell:
			hovered_cell = next_hovered
			if pending_action.is_empty():
				_refresh_context_preview()
		_update_cursor()
		_update_ui_text()
	elif event is InputEventMouseButton:
		var mouse_event: InputEventMouseButton = event as InputEventMouseButton
		if not mouse_event.pressed:
			return
		match mouse_event.button_index:
			MOUSE_BUTTON_LEFT:
				if _player_can_input():
					_handle_player_click(_screen_to_cell(mouse_event.position))
			MOUSE_BUTTON_RIGHT:
				_rotate_camera_90()
			MOUSE_BUTTON_WHEEL_UP:
				_set_camera_distance(camera_distance - 1.0)
			MOUSE_BUTTON_WHEEL_DOWN:
				_set_camera_distance(camera_distance + 1.0)
	elif event is InputEventKey and event.pressed:
		var key_event: InputEventKey = event as InputEventKey
		match key_event.keycode:
			KEY_Q:
				_rotate_camera_90(-1.0)
			KEY_E:
				_rotate_camera_90(1.0)
			KEY_M:
				_on_move_mode_pressed()
			KEY_A:
				_on_attack_mode_pressed()
			KEY_1:
				_on_skill_pressed(1)
			KEY_2:
				_on_skill_pressed(2)
			KEY_F:
				_on_face_pressed(-1 if key_event.shift_pressed else 1)
			KEY_C:
				_focus_camera_on_active(true)
			KEY_ENTER, KEY_KP_ENTER:
				if not pending_action.is_empty():
					_confirm_pending_action()
			KEY_ESCAPE:
				if not pending_action.is_empty():
					_cancel_pending_action()
				else:
					_cancel_skill_mode()
			KEY_SPACE:
				_on_end_activation_pressed()
			KEY_R:
				get_tree().reload_current_scene()


func _process(delta: float) -> void:
	_presentation_time += delta
	_update_action_camera(delta)
	_update_camera_smoothing(delta)
	_update_cursor_animation()
	_update_cursor()
	_update_action_wheel()


func _ensure_runtime_nodes() -> void:
	_map_holder = get_node_or_null("MapRoot") as Node3D
	if _map_holder == null:
		_map_holder = Node3D.new()
		_map_holder.name = "MapRoot"
		add_child(_map_holder)
	_actor_holder = get_node_or_null("Actors") as Node3D
	if _actor_holder == null:
		_actor_holder = Node3D.new()
		_actor_holder.name = "Actors"
		add_child(_actor_holder)
	_highlight_holder = get_node_or_null("Highlights") as Node3D
	if _highlight_holder == null:
		_highlight_holder = Node3D.new()
		_highlight_holder.name = "Highlights"
		add_child(_highlight_holder)
	_zone_holder = get_node_or_null("PersistentZones") as Node3D
	if _zone_holder == null:
		_zone_holder = Node3D.new()
		_zone_holder.name = "PersistentZones"
		add_child(_zone_holder)
	_vfx_holder = get_node_or_null("ActionVFX") as Node3D
	if _vfx_holder == null:
		_vfx_holder = Node3D.new()
		_vfx_holder.name = "ActionVFX"
		add_child(_vfx_holder)

	_camera_rig = get_node_or_null("CameraRig") as Node3D
	if _camera_rig == null:
		_camera_rig = Node3D.new()
		_camera_rig.name = "CameraRig"
		add_child(_camera_rig)
	_camera = _camera_rig.get_node_or_null("Camera3D") as Camera3D
	if _camera == null:
		_camera = Camera3D.new()
		_camera.name = "Camera3D"
		_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		_camera.current = true
		_camera_rig.add_child(_camera)
	_light = _camera_rig.get_node_or_null("DirectionalLight3D") as DirectionalLight3D
	if _light == null:
		_light = DirectionalLight3D.new()
		_light.name = "DirectionalLight3D"
		_light.light_energy = 1.3
		_camera_rig.add_child(_light)
	_position_camera()

	_cursor_mesh = get_node_or_null("Cursor") as MeshInstance3D
	if _cursor_mesh == null:
		_cursor_mesh = MeshInstance3D.new()
		_cursor_mesh.name = "Cursor"
		add_child(_cursor_mesh)
		var disc: CylinderMesh = CylinderMesh.new()
		disc.top_radius = 0.56
		disc.bottom_radius = 0.56
		disc.height = 0.026
		_cursor_mesh.mesh = disc
		var cursor_material: StandardMaterial3D = StandardMaterial3D.new()
		cursor_material.albedo_color = Color(1.0, 1.0, 0.82, 0.34)
		cursor_material.emission_enabled = true
		cursor_material.emission = Color(1.0, 1.0, 0.82)
		cursor_material.emission_energy_multiplier = 0.28
		cursor_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_cursor_mesh.material_override = cursor_material
	_build_ui()


func _build_ui() -> void:
	_ui_layer = get_node_or_null("UI") as CanvasLayer
	if _ui_layer != null:
		return
	_ui_layer = CanvasLayer.new()
	_ui_layer.name = "UI"
	add_child(_ui_layer)
	var root: Control = Control.new()
	root.name = "Root"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_ui_layer.add_child(root)

	var panel: Panel = Panel.new()
	panel.name = "Panel"
	panel.position = Vector2(18.0, 18.0)
	panel.size = Vector2(520.0, 258.0)
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.08, 0.11, 0.16, 0.92)
	style.border_color = Color(0.31, 0.43, 0.56, 1.0)
	style.border_width_left = 1
	style.border_width_top = 1
	style.border_width_right = 1
	style.border_width_bottom = 1
	style.corner_radius_top_left = 16
	style.corner_radius_top_right = 16
	style.corner_radius_bottom_left = 16
	style.corner_radius_bottom_right = 16
	panel.add_theme_stylebox_override("panel", style)
	root.add_child(panel)

	_turn_label = _make_label(panel, Vector2(16.0, 12.0), Vector2(488.0, 30.0), 20, Color(1.0, 0.82, 0.40, 1.0))
	_info_label = _make_label(panel, Vector2(16.0, 44.0), Vector2(488.0, 50.0), 16, Color(0.95, 0.94, 0.87, 1.0))
	_move_button = _make_button(panel, "DÉPLACER [M]", Vector2(16.0, 101.0), Vector2(118.0, 34.0))
	_attack_button = _make_button(panel, "ATTAQUER [A]", Vector2(142.0, 101.0), Vector2(118.0, 34.0))
	_move_button.toggle_mode = true
	_attack_button.toggle_mode = true
	_face_button = _make_button(panel, "FACE [F]", Vector2(268.0, 101.0), Vector2(104.0, 34.0))
	_end_button = _make_button(panel, "WAIT / FIN [ESPACE]", Vector2(380.0, 101.0), Vector2(124.0, 34.0))
	_primary_skill_button = _make_button(panel, "SKILL I [1]", Vector2(16.0, 142.0), Vector2(238.0, 34.0))
	_secondary_skill_button = _make_button(panel, "SKILL II [2]", Vector2(266.0, 142.0), Vector2(238.0, 34.0))
	_move_button.pressed.connect(_on_move_mode_pressed)
	_attack_button.pressed.connect(_on_attack_mode_pressed)
	_face_button.pressed.connect(_on_face_pressed.bind(1))
	_end_button.pressed.connect(_on_end_activation_pressed)
	_primary_skill_button.pressed.connect(_on_skill_pressed.bind(1))
	_secondary_skill_button.pressed.connect(_on_skill_pressed.bind(2))
	_help_label = _make_label(panel, Vector2(16.0, 184.0), Vector2(488.0, 60.0), 12, Color(0.68, 0.79, 0.87, 1.0))
	_help_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	var log_panel: Panel = Panel.new()
	log_panel.position = Vector2(18.0, 288.0)
	log_panel.size = Vector2(390.0, 116.0)
	log_panel.add_theme_stylebox_override("panel", style)
	root.add_child(log_panel)
	_log_label = _make_label(log_panel, Vector2(14.0, 10.0), Vector2(362.0, 96.0), 12, Color(0.84, 0.88, 0.92, 1.0))
	_log_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	_preview_panel = Panel.new()
	_preview_panel.name = "CombatPreview"
	_preview_panel.position = Vector2(790.0, 18.0)
	_preview_panel.size = Vector2(470.0, 382.0)
	_preview_panel.add_theme_stylebox_override("panel", style)
	_preview_panel.visible = false
	root.add_child(_preview_panel)
	_preview_title = _make_label(_preview_panel, Vector2(18.0, 14.0), Vector2(434.0, 32.0), 21, Color(1.0, 0.82, 0.40, 1.0))
	_preview_body = _make_label(_preview_panel, Vector2(18.0, 52.0), Vector2(434.0, 252.0), 14, Color(0.94, 0.94, 0.88, 1.0))
	_preview_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_preview_confirm_button = _make_button(_preview_panel, "CONFIRMER [ENTRÉE]", Vector2(18.0, 326.0), Vector2(250.0, 38.0))
	_preview_cancel_button = _make_button(_preview_panel, "ANNULER [ÉCHAP]", Vector2(280.0, 326.0), Vector2(172.0, 38.0))
	_preview_confirm_button.pressed.connect(_confirm_pending_action)
	_preview_cancel_button.pressed.connect(_cancel_pending_action)

	_timeline_panel = Panel.new()
	_timeline_panel.name = "InitiativeTimeline"
	_timeline_panel.position = Vector2(550.0, 18.0)
	_timeline_panel.size = Vector2(224.0, 92.0)
	_timeline_panel.add_theme_stylebox_override("panel", style)
	root.add_child(_timeline_panel)
	var timeline_title: Label = _make_label(_timeline_panel, Vector2(10.0, 7.0), Vector2(204.0, 22.0), 12, Color(0.68, 0.79, 0.87, 1.0))
	timeline_title.text = "INITIATIVE"
	_timeline_bar = HBoxContainer.new()
	_timeline_bar.position = Vector2(10.0, 31.0)
	_timeline_bar.size = Vector2(204.0, 50.0)
	_timeline_bar.add_theme_constant_override("separation", 3)
	_timeline_panel.add_child(_timeline_bar)

	_unit_card_panel = Panel.new()
	_unit_card_panel.name = "UnitCard"
	_unit_card_panel.position = Vector2(790.0, 414.0)
	_unit_card_panel.size = Vector2(470.0, 236.0)
	_unit_card_panel.add_theme_stylebox_override("panel", style)
	root.add_child(_unit_card_panel)
	_unit_portrait = TextureRect.new()
	_unit_portrait.position = Vector2(16.0, 18.0)
	_unit_portrait.size = Vector2(104.0, 136.0)
	_unit_portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_unit_portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_unit_card_panel.add_child(_unit_portrait)
	_unit_card_title = _make_label(_unit_card_panel, Vector2(136.0, 16.0), Vector2(316.0, 30.0), 21, Color(1.0, 0.82, 0.40, 1.0))
	_unit_hp_bar = ProgressBar.new()
	_unit_hp_bar.position = Vector2(136.0, 50.0)
	_unit_hp_bar.size = Vector2(316.0, 20.0)
	_unit_hp_bar.show_percentage = false
	_unit_hp_bar.add_theme_stylebox_override("background", _progress_style(Color(0.07, 0.08, 0.10, 0.95), 5))
	_unit_hp_bar.add_theme_stylebox_override("fill", _progress_style(Color(0.31, 0.82, 0.42, 1.0), 5))
	_unit_card_panel.add_child(_unit_hp_bar)
	_unit_focus_bar = ProgressBar.new()
	_unit_focus_bar.position = Vector2(136.0, 76.0)
	_unit_focus_bar.size = Vector2(316.0, 16.0)
	_unit_focus_bar.show_percentage = false
	_unit_focus_bar.add_theme_stylebox_override("background", _progress_style(Color(0.07, 0.08, 0.10, 0.95), 4))
	_unit_focus_bar.add_theme_stylebox_override("fill", _progress_style(Color(0.34, 0.64, 1.0, 1.0), 4))
	_unit_card_panel.add_child(_unit_focus_bar)
	_unit_card_body = _make_label(_unit_card_panel, Vector2(136.0, 99.0), Vector2(316.0, 120.0), 13, Color(0.92, 0.93, 0.88, 1.0))
	_unit_card_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	_action_wheel = Panel.new()
	_action_wheel.name = "ActionWheel"
	_action_wheel.size = Vector2(252.0, 190.0)
	_action_wheel.add_theme_stylebox_override("panel", style)
	_action_wheel.visible = false
	root.add_child(_action_wheel)
	_action_wheel_label = _make_label(_action_wheel, Vector2(71.0, 73.0), Vector2(110.0, 42.0), 13, Color(1.0, 0.88, 0.55, 1.0))
	_action_wheel_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_action_wheel_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_action_wheel_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_wheel_move_button = _make_button(_action_wheel, "MOVE", Vector2(78.0, 8.0), Vector2(96.0, 32.0))
	_wheel_attack_button = _make_button(_action_wheel, "ATK", Vector2(8.0, 55.0), Vector2(76.0, 32.0))
	_wheel_move_button.toggle_mode = true
	_wheel_attack_button.toggle_mode = true
	_wheel_primary_button = _make_button(_action_wheel, "S1", Vector2(168.0, 55.0), Vector2(76.0, 32.0))
	_wheel_secondary_button = _make_button(_action_wheel, "S2", Vector2(8.0, 111.0), Vector2(76.0, 32.0))
	_wheel_face_button = _make_button(_action_wheel, "FACE", Vector2(168.0, 111.0), Vector2(76.0, 32.0))
	_wheel_end_button = _make_button(_action_wheel, "WAIT / FIN", Vector2(78.0, 150.0), Vector2(96.0, 32.0))
	_wheel_move_button.pressed.connect(_on_move_mode_pressed)
	_wheel_attack_button.pressed.connect(_on_attack_mode_pressed)
	_wheel_primary_button.pressed.connect(_on_skill_pressed.bind(1))
	_wheel_secondary_button.pressed.connect(_on_skill_pressed.bind(2))
	_wheel_face_button.pressed.connect(_on_face_pressed.bind(1))
	_wheel_end_button.pressed.connect(_on_end_activation_pressed)


func _progress_style(color: Color, radius: int) -> StyleBoxFlat:
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = color
	style.corner_radius_top_left = radius
	style.corner_radius_top_right = radius
	style.corner_radius_bottom_left = radius
	style.corner_radius_bottom_right = radius
	return style


func _make_label(parent: Control, pos: Vector2, size_value: Vector2, font_size: int, color: Color) -> Label:
	var label: Label = Label.new()
	label.position = pos
	label.size = size_value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	parent.add_child(label)
	return label


func _make_button(parent: Control, title: String, pos: Vector2, size_value: Vector2) -> Button:
	var button: Button = Button.new()
	button.text = title
	button.position = pos
	button.size = size_value
	button.focus_mode = Control.FOCUS_NONE
	parent.add_child(button)
	return button


func _update_action_wheel() -> void:
	if _action_wheel == null or _camera == null:
		return
	var visible_now: bool = show_action_wheel and _player_can_input() and pending_action.is_empty() and _action_camera_timer <= 0.0
	_action_wheel.visible = visible_now
	if not visible_now or active_actor == null:
		return
	var world_anchor: Vector3 = active_actor.global_position + Vector3(0.0, 1.55, 0.0)
	if _camera.is_position_behind(world_anchor):
		_action_wheel.visible = false
		return
	var screen_pos: Vector2 = _camera.unproject_position(world_anchor)
	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	var desired: Vector2 = screen_pos - Vector2(_action_wheel.size.x * 0.5, _action_wheel.size.y + 18.0)
	desired.x = clampf(desired.x, 8.0, maxf(8.0, viewport_size.x - _action_wheel.size.x - 8.0))
	desired.y = clampf(desired.y, 8.0, maxf(8.0, viewport_size.y - _action_wheel.size.y - 8.0))
	_action_wheel.position = desired
	_action_wheel_label.text = active_actor.display_name
	_wheel_move_button.disabled = active_actor.moved_this_activation or active_actor.status_prevents_movement()
	_wheel_attack_button.disabled = active_actor.acted_this_activation or active_actor.status_prevents_action()
	_wheel_face_button.disabled = false
	_wheel_end_button.disabled = false
	var primary_ready: bool = active_actor.can_use_skill(active_actor.primary_skill)
	var secondary_ready: bool = active_actor.can_use_skill(active_actor.secondary_skill)
	_wheel_primary_button.disabled = not primary_ready
	_wheel_secondary_button.disabled = not secondary_ready
	_wheel_primary_button.text = "S1 " + _short_skill_name(active_actor.primary_skill)
	_wheel_secondary_button.text = "S2 " + _short_skill_name(active_actor.secondary_skill)
	_wheel_move_button.button_pressed = input_mode == MODE_MOVE
	_wheel_attack_button.button_pressed = input_mode == MODE_ATTACK


func _short_skill_name(skill_id: String) -> String:
	if skill_id.is_empty():
		return "—"
	var skill: Resource = SkillCatalog.definition(skill_id)
	if skill == null:
		return skill_id.substr(0, mini(6, skill_id.length())).to_upper()
	var title: String = String(skill.get("display_name"))
	return title.substr(0, mini(7, title.length())).to_upper()


func _load_map() -> void:
	for child: Node in _map_holder.get_children():
		child.queue_free()
	map_root = null
	var resolved_path: String = map_scene_path
	if mission_index >= 0:
		var mission_map_path: String = MissionCatalog.map_scene_path(mission_index)
		if not mission_map_path.is_empty():
			resolved_path = mission_map_path
	if resolved_path.is_empty() or not ResourceLoader.exists(resolved_path):
		return
	var packed: PackedScene = load(resolved_path) as PackedScene
	if packed == null:
		return
	var instance: Node = packed.instantiate()
	_map_holder.add_child(instance)
	if instance is SporeMap3D:
		map_root = instance as SporeMap3D
	if map_root == null:
		return
	var preview: Node = map_root.get_node_or_null("PreviewRig")
	if preview != null:
		preview.queue_free()
	_hide_spawn_markers()


func _hide_spawn_markers() -> void:
	if map_root == null:
		return
	for node: Node in _descendants(map_root):
		if not node.has_method("spore_map_role"):
			continue
		var role: String = String(node.call("spore_map_role"))
		if role not in ["hero", "enemy"]:
			continue
		for child: Node in node.get_children():
			_set_visibility_if_supported(child, false)


func _set_visibility_if_supported(node: Node, value: bool) -> void:
	for info: Dictionary in node.get_property_list():
		if String(info.get("name", "")) == "visible":
			node.set("visible", value)
			break


func _spawn_runtime_units() -> void:
	for child: Node in _actor_holder.get_children():
		child.queue_free()
	player_actors.clear()
	enemy_actors.clear()
	actors_by_cell.clear()
	if map_root == null:
		return

	var hero_starts: Array[Vector2i] = map_root.hero_start_cells()
	for index: int in range(mini(hero_starts.size(), hero_unit_ids.size())):
		var unit_id: String = hero_unit_ids[index]
		var unit_data: Resource = UnitCatalog.definition(unit_id)
		if unit_data == null:
			continue
		var actor: SporeUnitActor3D = UnitActorScript.new() as SporeUnitActor3D
		actor.name = "%sActor" % unit_id.capitalize()
		_actor_holder.add_child(actor)
		var runtime_unit: Dictionary = UnitCatalog.make_hero(unit_id, hero_starts[index], 1, UnitCatalog.default_job(unit_id), {}, {}, PackedStringArray())
		var runtime_overrides: Dictionary = {
			"hp": int(runtime_unit.get("max_hp", unit_data.get("max_hp"))),
			"attack": int(runtime_unit.get("attack", unit_data.get("attack"))),
			"magic_power": int(runtime_unit.get("magic_power", unit_data.get("magic_power"))),
			"physical_defense": int(runtime_unit.get("physical_defense", unit_data.get("physical_defense"))),
			"magic_defense": int(runtime_unit.get("magic_defense", unit_data.get("magic_defense"))),
			"move": int(runtime_unit.get("move", unit_data.get("movement"))),
			"range": int(runtime_unit.get("range", unit_data.get("attack_range"))),
			"attack_min_range": int(runtime_unit.get("attack_min_range", 1)),
			"threat_min_range": int(runtime_unit.get("threat_min_range", 1)),
			"threat_max_range": int(runtime_unit.get("threat_max_range", 1)),
			"weapon_family": String(runtime_unit.get("weapon_family", "unarmed")),
			"can_opportunity_attack": bool(runtime_unit.get("can_opportunity_attack", true)),
			"basic_attack_damage_type": String(runtime_unit.get("basic_attack_damage_type", "physical")),
			"shield_block_chance": int(runtime_unit.get("shield_block_chance", 0)),
			"shield_block_reduction": int(runtime_unit.get("shield_block_reduction", 0)),
			"initiative": int(runtime_unit.get("initiative", unit_data.get("initiative"))),
			"accuracy": int(runtime_unit.get("accuracy", unit_data.get("accuracy"))),
			"evasion": int(runtime_unit.get("evasion", unit_data.get("evasion"))),
			"max_focus": int(runtime_unit.get("max_focus", unit_data.get("max_focus"))),
			"primary_skill": String(runtime_unit.get("special", unit_data.get("primary_skill"))),
			"secondary_skill": String(runtime_unit.get("secondary", unit_data.get("secondary_skill"))),
			"reaction_type": String(runtime_unit.get("reaction_type", unit_data.get("reaction_type"))),
			"reaction_range": int(runtime_unit.get("reaction_range", unit_data.get("reaction_range"))),
			"reaction_damage_bonus": int(runtime_unit.get("reaction_damage_bonus", unit_data.get("reaction_damage_bonus"))),
			"end_ct_bonus": int(runtime_unit.get("end_ct_bonus", 0)),
			"basic_attack_damage_bonus": int(runtime_unit.get("basic_attack_damage_bonus", 0)),
			"basic_attack_accuracy_bonus": int(runtime_unit.get("basic_attack_accuracy_bonus", 0)),
			"flat_damage_reduction": int(runtime_unit.get("flat_damage_reduction", 0)),
			"focus_regen_bonus": int(runtime_unit.get("focus_regen_bonus", 0)),
			"revive_hp_bonus": int(runtime_unit.get("revive_hp_bonus", 0)),
			"jump_up_bonus": int(runtime_unit.get("jump_up_bonus", 0)),
			"jump_down_bonus": int(runtime_unit.get("jump_down_bonus", 0)),
			"ignore_opportunity": bool(runtime_unit.get("ignore_opportunity", false)),
		}
		actor.configure_from_unit_data(unit_data, hero_starts[index], map_root, "player", runtime_overrides)
		player_actors.append(actor)
		actors_by_cell[hero_starts[index]] = actor

	var enemies: Array = MissionCatalog.enemy_specs(mission_index)
	for entry_var: Variant in enemies:
		if not (entry_var is Dictionary):
			continue
		var entry: Dictionary = entry_var as Dictionary
		var enemy_id: String = String(entry.get("id", ""))
		var unit_data_enemy: Resource = UnitCatalog.definition(enemy_id)
		if unit_data_enemy == null:
			continue
		var enemy_cell_value: Variant = entry.get("position", Vector2i.ZERO)
		if not (enemy_cell_value is Vector2i):
			continue
		var enemy_cell: Vector2i = enemy_cell_value
		var enemy_actor: SporeUnitActor3D = UnitActorScript.new() as SporeUnitActor3D
		enemy_actor.name = "%sEnemy" % enemy_id.capitalize()
		_actor_holder.add_child(enemy_actor)
		var overrides: Dictionary = {
			"hp": int(entry.get("hp", -1)),
			"attack": int(entry.get("attack", -1)),
			"move": int(entry.get("move", -1)),
			"range": int(entry.get("range", -1)),
		}
		enemy_actor.configure_from_unit_data(unit_data_enemy, enemy_cell, map_root, "enemy", overrides)
		enemy_actors.append(enemy_actor)
		actors_by_cell[enemy_cell] = enemy_actor


func _build_turn_order() -> void:
	turn_order.clear()
	for actor: SporeUnitActor3D in player_actors:
		if actor.alive:
			turn_order.append(actor)
	for actor: SporeUnitActor3D in enemy_actors:
		if actor.alive:
			turn_order.append(actor)
	# Keep roster enumeration stable. Speed changes how fast CT fills; it does not
	# become a tie-breaker when several units are ready on the same clocktick.
	turn_index = -1
	round_number = 1
	battle_clock_ticks = 0
	activation_count_in_round = 0
	round_activation_budget = maxi(1, _alive_actor_count())
	activated_this_round.clear()
	battle_rng.seed = 0x5F0A300D + mission_index
	for actor: SporeUnitActor3D in turn_order:
		actor.ct = 0
		actor.casting.clear()
		actor.refresh_mechanics_label()


func _initiative_before(a: SporeUnitActor3D, b: SporeUnitActor3D) -> bool:
	if a.effective_speed() == b.effective_speed():
		if a.team != b.team:
			return a.team == "player"
		return a.display_name < b.display_name
	return a.effective_speed() > b.effective_speed()


func _alive_actor_count() -> int:
	var count: int = 0
	for actor: SporeUnitActor3D in turn_order:
		if actor != null and actor.alive:
			count += 1
	return count


func _actor_by_unit_id(unit_id: String) -> SporeUnitActor3D:
	for actor: SporeUnitActor3D in turn_order:
		if actor != null and actor.unit_id == unit_id:
			return actor
	return null


func _next_ready_ticks_3d() -> int:
	var best: int = 999999
	for actor: SporeUnitActor3D in turn_order:
		if actor == null or not actor.battle_present():
			continue
		# In FFT a caster keeps gaining unit CT while the slow action has its own CTR.
		best = mini(best, CombatMechanics.ticks_until_ready(actor.ct, actor.ct_gain_per_tick()))
	return best


func _next_cast_ticks_3d() -> int:
	var best: int = 999999
	for actor: SporeUnitActor3D in turn_order:
		if actor == null or not actor.alive or not actor.is_casting():
			continue
		best = mini(best, maxi(0, int(actor.casting.get("remaining_ticks", 0))))
	return best


func _next_status_ticks_3d() -> int:
	var best: int = 999999
	for actor: SporeUnitActor3D in turn_order:
		if actor == null or not actor.battle_present():
			continue
		best = mini(best, actor.next_status_expiry_ticks())
	return best


func _advance_battle_clock_3d(step_ticks: int) -> void:
	if step_ticks <= 0:
		return
	battle_clock_ticks += step_ticks
	var due_casts: Array[SporeUnitActor3D] = []
	for actor: SporeUnitActor3D in turn_order:
		if actor == null or not actor.battle_present():
			continue
		actor.ct = mini(199, actor.ct + actor.ct_gain_per_tick() * step_ticks)
		if actor.is_casting():
			actor.casting["remaining_ticks"] = int(actor.casting.get("remaining_ticks", 0)) - step_ticks
			if int(actor.casting.get("remaining_ticks", 0)) <= 0:
				due_casts.append(actor)
		var expired_clock_statuses: PackedStringArray = actor.tick_status_clock(step_ticks)
		if not expired_clock_statuses.is_empty():
			_log("%s : fin de %s (clocktick)." % [actor.display_name, ", ".join(expired_clock_statuses)])
		actor.refresh_mechanics_label()
	for caster: SporeUnitActor3D in due_casts:
		_resolve_due_cast_3d(caster)


func _resolve_ready_downed_actors_3d() -> bool:
	var resolved := false
	for actor: SporeUnitActor3D in turn_order:
		if actor == null or not actor.downed or actor.removed_from_battle or actor.ct < CombatMechanics.CT_THRESHOLD:
			continue
		resolved = true
		var remaining: int = actor.advance_downed_countdown()
		if remaining <= 0:
			actors_by_cell.erase(actor.cell)
			actor.visible = false
			_log("%s quitte définitivement la bataille faute de réanimation." % actor.display_name)
		else:
			_show_floating_text(actor.position + Vector3(0.0, 1.2, 0.0), "K.O. %d" % remaining, Color(1.0, 0.45, 0.38, 1.0))
			_log("%s reste K.O. • %d compte(s)." % [actor.display_name, remaining])
	return resolved


func _advance_clock_until_ready_3d() -> bool:
	for _guard: int in range(256):
		if _check_battle_end():
			return false
		if _resolve_ready_downed_actors_3d():
			if _check_battle_end():
				return false
			continue
		for actor: SporeUnitActor3D in turn_order:
			if actor != null and actor.alive and not actor.status_freezes_ct() and actor.ct >= CombatMechanics.CT_THRESHOLD:
				return true
		var unit_ticks: int = _next_ready_ticks_3d()
		var cast_ticks: int = _next_cast_ticks_3d()
		var status_ticks: int = _next_status_ticks_3d()
		var step_ticks: int = mini(unit_ticks, mini(cast_ticks, status_ticks))
		if step_ticks == 999999:
			return false
		if step_ticks <= 0:
			var resolved_any: bool = false
			for actor: SporeUnitActor3D in turn_order:
				if actor != null and actor.alive and actor.is_casting() and int(actor.casting.get("remaining_ticks", 0)) <= 0:
					_resolve_due_cast_3d(actor)
					resolved_any = true
			if not resolved_any:
				return false
			continue
		_advance_battle_clock_3d(step_ticks)
	return false


func _ready_actor_before(a: SporeUnitActor3D, b: SporeUnitActor3D) -> bool:
	# FFT resolves simultaneous natural ATs by unit-list enumeration, not by
	# overflowing CT or Speed. `turn_order` is our stable battle roster.
	return turn_order.find(a) < turn_order.find(b)


func _select_ready_actor_3d() -> SporeUnitActor3D:
	var ready: Array[SporeUnitActor3D] = []
	for actor: SporeUnitActor3D in turn_order:
		if actor != null and actor.alive and not actor.status_freezes_ct() and actor.ct >= CombatMechanics.CT_THRESHOLD:
			ready.append(actor)
	if ready.is_empty():
		return null
	ready.sort_custom(_ready_actor_before)
	return ready[0]


func _all_alive_actors_activated_this_round() -> bool:
	for candidate: SporeUnitActor3D in turn_order:
		if candidate == null or not candidate.alive:
			continue
		if not activated_this_round.has(candidate.unit_id):
			return false
	return true


func _finalize_actor_timing(actor: SporeUnitActor3D) -> void:
	if actor == null:
		return
	var paid_move: bool = actor.moved_this_activation or actor.status_treats_as_moved_for_ct()
	var paid_act: bool = actor.acted_this_activation or actor.status_treats_as_acted_for_ct()
	var end_ct: int = CombatMechanics.action_end_ct(actor.ct, paid_move, paid_act, false)
	actor.ct = CombatMechanics.apply_end_ct_bonus(end_ct, actor.end_ct_bonus)
	actor.refresh_mechanics_label()
	activation_count_in_round += 1
	activated_this_round[actor.unit_id] = true
	if _all_alive_actors_activated_this_round():
		activation_count_in_round = 0
		activated_this_round.clear()
		round_number += 1
		round_activation_budget = maxi(1, _alive_actor_count())
		_start_new_round()


func _queue_cast_3d(caster: SporeUnitActor3D, skill_id: String, anchor_cell: Vector2i) -> bool:
	if caster == null or not caster.alive or not caster.can_use_skill(skill_id):
		return false
	var cast_ticks: int = CombatMechanics.short_charge_ticks(SkillCatalog.cast_time_ticks(skill_id), caster.support_ability)
	if cast_ticks <= 0:
		return false
	var tracked_target: SporeUnitActor3D = actors_by_cell.get(anchor_cell, null) as SporeUnitActor3D
	caster.casting = {
		"skill_id": skill_id,
		"target_id": tracked_target.unit_id if tracked_target != null else "",
		"anchor_cell": anchor_cell,
		"remaining_ticks": cast_ticks,
		"interrupt_on_damage": SkillCatalog.interrupt_on_damage(skill_id),
	}
	# Starting a slow action consumes Act, but MP is paid only at resolution.
	caster.acted_this_activation = true
	caster.remove_statuses_on_attack()
	caster.refresh_mechanics_label()
	_log("%s prépare %s • lancement dans %d tick(s) CT." % [caster.display_name, SkillCatalog.display_name(skill_id), cast_ticks])
	_show_floating_text(caster.position + Vector3(0.0, 1.28, 0.0), "CAST %d" % cast_ticks, Color(0.76, 0.56, 1.0, 1.0))
	return true


func _resolve_due_cast_3d(caster: SporeUnitActor3D) -> void:
	if caster == null or not caster.alive or not caster.is_casting():
		return
	var casting: Dictionary = caster.casting.duplicate(true)
	caster.casting.clear()
	caster.refresh_mechanics_label()
	var skill_id: String = String(casting.get("skill_id", ""))
	var skill: Resource = SkillCatalog.definition(skill_id)
	if skill == null:
		return
	if not caster.spend_skill_resource_only(skill_id):
		_log("NO MP : %s ne peut pas libérer %s." % [caster.display_name, SkillCatalog.display_name(skill_id)])
		_show_floating_text(caster.position + Vector3(0.0, 1.28, 0.0), "NO MP", Color(0.48, 0.72, 1.0, 1.0))
		return
	var anchor_value: Variant = casting.get("anchor_cell", caster.cell)
	var anchor_cell: Vector2i = anchor_value if anchor_value is Vector2i else caster.cell
	var target_id: String = String(casting.get("target_id", ""))
	if not target_id.is_empty():
		var tracked_target: SporeUnitActor3D = _actor_by_unit_id(target_id)
		var revive_target_valid: bool = tracked_target != null and tracked_target.downed and not tracked_target.removed_from_battle and SkillCatalog.has_tag(skill_id, "revive")
		if tracked_target == null or (not tracked_target.alive and not revive_target_valid):
			_log("%s : %s se dissipe, la cible n'est plus valide." % [caster.display_name, SkillCatalog.display_name(skill_id)])
			_show_floating_text(caster.position + Vector3(0.0, 1.28, 0.0), "CAST PERDU", Color(1.0, 0.48, 0.36, 1.0))
			return
		anchor_cell = tracked_target.cell
	caster.face_cell(anchor_cell)
	_skill_hit_cache.clear()
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if effect_var is Resource and caster.alive:
				_apply_skill_effect(caster, skill, effect_var as Resource, anchor_cell)
	var anchor_global: Vector3 = map_root.to_global(map_root.cell_top_local(anchor_cell))
	_spawn_action_vfx(String(skill.get("vfx_id")), caster.global_position + Vector3(0.0, 0.78, 0.0), anchor_global + Vector3(0.0, 0.18, 0.0), false)
	_log("CAST : %s libère %s." % [caster.display_name, SkillCatalog.display_name(skill_id)])
	_check_battle_end()


func _interrupt_cast_3d(target: SporeUnitActor3D, damage: int) -> void:
	if target == null or damage <= 0 or not target.is_casting():
		return
	var skill_id: String = target.interrupt_cast()
	if skill_id.is_empty():
		return
	_show_floating_text(target.position + Vector3(0.0, 1.32, 0.0), "INTERROMPU", Color(1.0, 0.48, 0.36, 1.0))
	_log("INTERRUPTION : %s perd %s après avoir subi des dégâts." % [target.display_name, SkillCatalog.display_name(skill_id)])


func _cancel_cast_for_command_3d(actor: SporeUnitActor3D, command_name: String) -> void:
	if actor == null or not actor.is_casting():
		return
	var skill_id: String = String(actor.casting.get("skill_id", ""))
	actor.casting.clear()
	actor.refresh_mechanics_label()
	if not skill_id.is_empty():
		_log("%s annule %s en choisissant %s." % [actor.display_name, SkillCatalog.display_name(skill_id), command_name])
		_show_floating_text(actor.position + Vector3(0.0, 1.30, 0.0), "CAST ANNULÉ", Color(1.0, 0.60, 0.34, 1.0))


func _start_next_activation() -> void:
	if battle_finished:
		return
	if _check_battle_end():
		return
	if turn_order.is_empty():
		battle_finished = true
		_log("Aucune unité disponible pour démarrer le combat.")
		return
	if active_actor != null:
		_process_persistent_zones_for_actor(active_actor, "activation_end")
		if active_actor.alive:
			_process_status_phase(active_actor, "activation_end")
		var expired_statuses: PackedStringArray = active_actor.finish_status_activation()
		if not expired_statuses.is_empty():
			_log("%s : fin de %s." % [active_actor.display_name, ", ".join(expired_statuses)])
		active_actor.end_activation()
		_finalize_actor_timing(active_actor)
		if _check_battle_end():
			return
	_clear_overlays()
	active_actor = null
	selected_actor = null
	if not _advance_clock_until_ready_3d():
		return
	active_actor = _select_ready_actor_3d()
	if active_actor == null or not active_actor.alive:
		return
	turn_index = turn_order.find(active_actor)
	active_actor.begin_activation()
	selected_actor = active_actor if active_actor.team == "player" else null
	input_mode = MODE_MOVE
	_clear_pending_action()
	selected_skill_id = ""
	skill_preview_cells.clear()
	_process_persistent_zones_for_actor(active_actor, "activation_start")
	if active_actor.alive:
		_process_status_phase(active_actor, "activation_start")
	if not active_actor.alive:
		call_deferred("_start_next_activation")
		return
	if active_actor.status_prevents_movement():
		active_actor.moved_this_activation = true
	if active_actor.status_prevents_action():
		active_actor.acted_this_activation = true
	_log("Tour de %s • CT %d • VIT %d." % [active_actor.display_name, active_actor.ct, active_actor.effective_speed()])
	if active_actor.is_casting():
		_log("CHARGING : %s conserve %s en se déplaçant ou en WAIT ; une nouvelle Action annule le cast." % [active_actor.display_name, SkillCatalog.display_name(String(active_actor.casting.get("skill_id", "")))])
	if active_actor.moved_this_activation and active_actor.acted_this_activation:
		_log("%s ne peut pas agir pendant cette activation." % active_actor.display_name)
		call_deferred("_start_next_activation")
		return
	_focus_camera_on_active(false)
	if active_actor.team == "player":
		_refresh_player_overlays()
	else:
		enemy_busy = true
		call_deferred("_execute_enemy_activation")
	_update_ui_text()


func _player_can_input() -> bool:
	return not battle_finished and not enemy_busy and not player_busy and active_actor != null and active_actor.alive and active_actor.team == "player"


func _handle_player_click(cell: Vector2i) -> void:
	if not _player_can_input() or map_root == null or not map_root.is_cell_valid(cell):
		return
	if input_mode == MODE_MOVE:
		if not active_actor.moved_this_activation and reachable_cells.has(cell):
			_player_move_to(cell)
			return
		var actor_on_cell: SporeUnitActor3D = actors_by_cell.get(cell, null) as SporeUnitActor3D
		if actor_on_cell == active_actor:
			return
	elif input_mode == MODE_ATTACK:
		var target: SporeUnitActor3D = actors_by_cell.get(cell, null) as SporeUnitActor3D
		if target != null and target.alive and target.team != active_actor.team and attack_cells.has(cell):
			_stage_attack_preview(target)
	elif input_mode == MODE_SKILL:
		if not selected_skill_id.is_empty() and skill_target_cells.has(cell):
			_stage_skill_preview(cell)


func _player_move_to(cell: Vector2i) -> void:
	_clear_pending_action()
	if active_actor == null or active_actor.moved_this_activation or player_busy:
		return
	var path: Array[Vector2i] = _reconstruct_path(cell)
	if path.size() < 2:
		return
	player_busy = true
	preview_path_cells.clear()
	_rebuild_highlights()
	var start_cell: Vector2i = active_actor.cell
	actors_by_cell.erase(start_cell)
	if active_actor.uses_teleport():
		var distance: int = _cell_distance(start_cell, cell)
		var chance: int = CombatMechanics.teleport_success_chance(distance, active_actor.effective_move_range())
		if battle_rng.randi_range(1, 100) <= chance:
			active_actor.place_on_map(map_root, cell)
			_show_floating_text(active_actor.position + Vector3(0.0, 1.2, 0.0), "TELEPORT", Color(0.70, 0.55, 1.0, 1.0))
		else:
			active_actor.place_on_map(map_root, start_cell)
			_show_floating_text(active_actor.position + Vector3(0.0, 1.2, 0.0), "ÉCHEC %d%%" % chance, Color(1.0, 0.55, 0.40, 1.0))
			_log("%s rate sa téléportation (%d%%)." % [active_actor.display_name, chance])
	else:
		await _move_actor_along_path(active_actor, path, 0.13)
	if active_actor.alive:
		actors_by_cell[active_actor.cell] = active_actor
	active_actor.moved_this_activation = true
	if active_actor.movement_ability == "move_mp_up" and active_actor.cell != start_cell:
		var restored_mp: int = maxi(1, int(ceil(float(active_actor.max_focus) / 10.0)))
		active_actor.change_focus(restored_mp)
	player_busy = false
	if not active_actor.alive:
		_check_battle_end()
		call_deferred("_start_next_activation")
		return
	_log("%s se déplace en %d,%d (%d pas)." % [active_actor.display_name, active_actor.cell.x, active_actor.cell.y, path.size() - 1])
	if not active_actor.acted_this_activation:
		input_mode = MODE_ATTACK
	selected_skill_id = ""
	skill_preview_cells.clear()
	preview_path_cells.clear()
	_refresh_player_overlays()
	_update_ui_text()
	_finish_activation_if_complete()


func _player_attack(target: SporeUnitActor3D) -> void:
	if active_actor == null or active_actor.acted_this_activation or target == null or not target.alive:
		return
	_cancel_cast_for_command_3d(active_actor, "Attack")
	player_busy = true
	active_actor.acted_this_activation = true
	_begin_action_camera(active_actor.global_position, target.global_position, 0.72, action_camera_zoom_in)
	active_actor.play_attack(target.position)
	await _play_action_vfx_to_impact(active_actor.basic_attack_vfx_id, active_actor.global_position + Vector3(0.0, 0.72, 0.0), target.global_position + Vector3(0.0, 0.64, 0.0), true, target, Vector3(0.0, 0.64, 0.0))
	_resolve_attack(active_actor, target)
	_camera_impact()
	if vfx_impact_pause > 0.0:
		await get_tree().create_timer(vfx_impact_pause).timeout
	await get_tree().create_timer(0.08).timeout
	player_busy = false
	if not active_actor.alive:
		if not _check_battle_end():
			call_deferred("_start_next_activation")
		return
	if not active_actor.moved_this_activation and active_actor.alive:
		input_mode = MODE_MOVE
	selected_skill_id = ""
	skill_preview_cells.clear()
	preview_path_cells.clear()
	_refresh_player_overlays()
	_update_ui_text()
	_finish_activation_if_complete()


func _resolve_attack(attacker: SporeUnitActor3D, target: SporeUnitActor3D) -> void:
	if attacker == null or target == null or not attacker.alive or not target.alive:
		return
	if not _is_in_attack_range(attacker, target):
		_log("Ligne de vue bloquée entre %s et %s." % [attacker.display_name, target.display_name])
		return
	var details: Dictionary = _attack_damage_details(attacker, target)
	var hit_chance: int = int(details.get("hit_chance", CombatMechanics.BASIC_ATTACK_ACCURACY))
	attacker.face_cell(target.cell)
	if not _roll_hit_3d(hit_chance):
		attacker.remove_statuses_on_attack()
		_show_floating_text(target.position + Vector3(0.0, 1.20, 0.0), "MISS", Color(0.92, 0.92, 0.96, 1.0))
		_log("%s rate %s • %d%% HIT." % [attacker.display_name, target.display_name, hit_chance])
		return
	var height_bonus: int = int(details.get("height_bonus", 0))
	var cover_reduction: int = int(details.get("cover_reduction", 0))
	var attack_arc: String = String(details.get("arc", "front"))
	var positional_bonus: int = int(details.get("positional_bonus", 0))
	var damage: int = int(details.get("damage", 1))
	var result: Dictionary = _apply_damage_with_reactions(attacker, target, damage, "attaque", true, true, attacker.basic_attack_damage_type)
	attacker.remove_statuses_on_attack()
	var recipient: SporeUnitActor3D = result.get("target", target) as SporeUnitActor3D
	var applied: int = int(result.get("applied", 0))
	var modifiers: PackedStringArray = PackedStringArray()
	if height_bonus > 0:
		modifiers.append("+hauteur")
	if positional_bonus > 0:
		modifiers.append("+%d %s" % [positional_bonus, "dos" if attack_arc == "back" else "flanc"])
	if cover_reduction > 0:
		modifiers.append("-%d couvert directionnel" % cover_reduction)
	var suffix: String = "" if modifiers.is_empty() else " (" + ", ".join(modifiers) + ")"
	var target_name: String = recipient.display_name if recipient != null else target.display_name
	_log("%s frappe %s : %d dégâts • HIT %d%%%s." % [attacker.display_name, target_name, applied, hit_chance, suffix])
	_check_battle_end()


func _apply_damage_with_reactions(
	attacker: SporeUnitActor3D,
	target: SporeUnitActor3D,
	damage: int,
	source_label: String,
	allow_counter: bool = true,
	allow_intercept: bool = true,
	damage_type: String = "physical"
) -> Dictionary:
	if target == null or not target.alive:
		return {"target": target, "applied": 0, "intercepted": false}
	var recipient: SporeUnitActor3D = target
	var intercepted: bool = false
	if allow_intercept and attacker != null:
		var interceptor: SporeUnitActor3D = _find_interceptor(attacker, target)
		if interceptor != null:
			interceptor.consume_reaction()
			interceptor.face_cell(attacker.cell)
			recipient = interceptor
			# Damage previews are computed against the original target. Transfer the
			# incoming-damage modifier to the actor who actually receives the hit.
			damage -= target.status_modifier("incoming_damage_delta")
			damage += interceptor.status_modifier("incoming_damage_delta")
			damage += target.effective_defense_for_damage_type(damage_type) - interceptor.effective_defense_for_damage_type(damage_type)
			damage = maxi(1, damage - intercept_damage_reduction)
			intercepted = true
			_show_floating_text(interceptor.position + Vector3(0.0, 1.34, 0.0), "INTERCEPTION", Color(0.50, 0.86, 1.0, 1.0))
			_log("%s intercepte %s destiné à %s." % [interceptor.display_name, source_label, target.display_name])
	var reaction_was_blocked: bool = recipient.status_prevents_reaction()
	var mitigated_damage: int = maxi(0, damage - recipient.flat_damage_reduction)
	if mitigated_damage > 0 and recipient.shield_block_chance > 0 and recipient.shield_block_reduction > 0 and battle_rng.randi_range(1, 100) <= recipient.shield_block_chance:
		var blocked: int = mini(mitigated_damage, recipient.shield_block_reduction)
		mitigated_damage = maxi(0, mitigated_damage - blocked)
		_show_floating_text(recipient.position + Vector3(0.0, 1.42, 0.0), "BLOC -%d" % blocked, Color(0.50, 0.86, 1.0, 1.0))
	if mitigated_damage > 0 and recipient.reaction_type == "mp_switch" and recipient.reaction_available() and recipient.focus > 0 and _reaction_triggers_3d(recipient):
		var mp_before: int = recipient.focus
		var mp_lost: int = mini(mp_before, mitigated_damage)
		recipient.change_focus(-mitigated_damage)
		mitigated_damage = 0
		_show_floating_text(recipient.position + Vector3(0.0, 1.34, 0.0), "MP SWITCH -%d MP" % mp_lost, Color(0.45, 0.75, 1.0, 1.0))
	var applied: int = recipient.take_damage(mitigated_damage)
	_interrupt_cast_3d(recipient, applied)
	recipient.remove_statuses_on_damage_taken()
	_show_floating_text(recipient.position + Vector3(0.0, 1.15, 0.0), "-%d" % applied, Color(1.0, 0.42, 0.36, 1.0))
	if not recipient.alive:
		_handle_actor_ko(recipient, source_label)
	else:
		if applied > 0 and not reaction_was_blocked and recipient.reaction_type == "auto_potion" and recipient.reaction_available() and _reaction_triggers_3d(recipient):
			var potion_heal: int = maxi(1, int(floor(float(recipient.max_hp) / 4.0)))
			var healed: int = recipient.heal(potion_heal)
			_show_floating_text(recipient.position + Vector3(0.0, 1.34, 0.0), "AUTO-POTION +%d" % healed, Color(0.48, 0.90, 0.66, 1.0))
		if allow_counter and not reaction_was_blocked and attacker != null and attacker.alive:
			_try_counter_reaction(recipient, attacker)
	return {"target": recipient, "applied": applied, "intercepted": intercepted}


func _reaction_triggers_3d(reactor: SporeUnitActor3D) -> bool:
	if reactor == null or not reactor.reaction_available():
		return false
	if reactor.reaction_ready:
		# Sporebound can grant a one-shot guaranteed reaction. Consume that
		# guarantee here even for passive reactions such as MP Switch / Auto-Potion.
		reactor.reaction_ready = false
		reactor.refresh_mechanics_label()
		return true
	return battle_rng.randi_range(1, 100) <= CombatMechanics.reaction_chance(reactor.brave)


func _find_interceptor(attacker: SporeUnitActor3D, protected_target: SporeUnitActor3D) -> SporeUnitActor3D:
	if attacker == null or protected_target == null:
		return null
	var candidates: Array[SporeUnitActor3D] = player_actors if protected_target.team == "player" else enemy_actors
	var best: SporeUnitActor3D = null
	var best_hp: int = -1
	for candidate: SporeUnitActor3D in candidates:
		if candidate == null or candidate == protected_target or not candidate.alive:
			continue
		if candidate.reaction_type != "intercept" or not candidate.reaction_available():
			continue
		if _cell_distance(candidate.cell, protected_target.cell) > candidate.reaction_range:
			continue
		if candidate.hp > best_hp:
			best = candidate
			best_hp = candidate.hp
	# Intercept is a Sporebound reaction: select the eligible protector first,
	# then roll Brave once. This prevents failed/non-selected candidates from
	# consuming a one-shot reaction_ready proc.
	if best != null and not _reaction_triggers_3d(best):
		return null
	return best


func _try_counter_reaction(reactor: SporeUnitActor3D, attacker: SporeUnitActor3D) -> void:
	if reactor == null or attacker == null or not reactor.alive or not attacker.alive:
		return
	if reactor.reaction_type != "counter" or not reactor.reaction_available():
		return
	var counter_distance: int = _cell_distance(reactor.cell, attacker.cell)
	var counter_max: int = mini(reactor.reaction_range, maxi(1, reactor.attack_range + reactor.status_modifier("range_delta")))
	if not CombatMechanics.range_allowed(counter_distance, reactor.attack_min_range, counter_max):
		return
	if map_root != null and not _has_line_of_sight(reactor.cell, attacker.cell):
		return
	if not _reaction_triggers_3d(reactor):
		_log("RÉACTION : %s ne déclenche pas CONTRE (%d Brave)." % [reactor.display_name, reactor.brave])
		return
	_perform_reaction_attack(reactor, attacker, "CONTRE", 0)


func _perform_reaction_attack(reactor: SporeUnitActor3D, target: SporeUnitActor3D, reaction_label: String, damage_penalty: int) -> void:
	if reactor == null or target == null or not reactor.alive or not target.alive:
		return
	reactor.consume_reaction()
	reactor.face_cell(target.cell)
	reactor.play_attack(target.position)
	_spawn_action_vfx(reactor.basic_attack_vfx_id, reactor.global_position + Vector3(0.0, 0.72, 0.0), target.global_position + Vector3(0.0, 0.64, 0.0), false)
	_show_floating_text(reactor.position + Vector3(0.0, 1.34, 0.0), reaction_label, Color(1.0, 0.82, 0.40, 1.0))
	var hit: Dictionary = _hit_profile_3d(reactor, target, CombatMechanics.BASIC_ATTACK_ACCURACY, false)
	if not _roll_hit_3d(int(hit["chance"])):
		_show_floating_text(target.position + Vector3(0.0, 1.18, 0.0), "MISS", Color(0.92, 0.92, 0.96, 1.0))
		_log("%s déclenche %s sur %s mais rate • %d%% HIT." % [reactor.display_name, reaction_label.to_lower(), target.display_name, int(hit["chance"])])
		reactor.remove_statuses_on_attack()
		return
	var compatibility: String = CombatMechanics.zodiac_compatibility(reactor.zodiac_sign, target.zodiac_sign, reactor.sex, target.sex)
	var reaction_raw: int = CombatMechanics.fft_weapon_damage(
		reactor.effective_physical_power(), reactor.effective_magic_power(), reactor.effective_speed(), reactor.brave, reactor.weapon_power, reactor.weapon_family, compatibility
	) + reactor.status_modifier("outgoing_damage_delta") + target.status_modifier("incoming_damage_delta") + reactor.reaction_damage_bonus - damage_penalty
	var reaction_defense: int = target.effective_physical_defense() if reactor.basic_attack_damage_type == "physical" else target.effective_magic_defense()
	var damage: int = CombatMechanics.damage_after_defense(reaction_raw, reaction_defense, 1)
	if reactor.basic_attack_damage_type == "physical":
		damage = CombatMechanics.apply_charging_physical_vulnerability(damage, target.is_casting())
	_log("%s déclenche %s sur %s • %d%% HIT." % [reactor.display_name, reaction_label.to_lower(), target.display_name, int(hit["chance"])])
	_apply_damage_with_reactions(reactor, target, damage, reaction_label.to_lower(), false, false, reactor.basic_attack_damage_type)
	reactor.remove_statuses_on_attack()


func _handle_actor_ko(actor: SporeUnitActor3D, source_label: String = "") -> void:
	if actor == null:
		return
	actor.play_ko()
	actors_by_cell[actor.cell] = actor
	var suffix: String = "" if source_label.is_empty() else " via %s" % source_label
	_log("%s est K.O.%s." % [actor.display_name, suffix])


func _show_floating_text(world_position: Vector3, text_value: String, color: Color) -> void:
	var label: Label3D = Label3D.new()
	label.text = text_value
	label.font_size = 36
	label.outline_size = 8
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.modulate = color
	label.position = world_position
	_actor_holder.add_child(label)
	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(label, "position", world_position + Vector3(0.0, 0.48, 0.0), 0.55)
	tween.tween_property(label, "modulate", Color(color.r, color.g, color.b, 0.0), 0.55)
	tween.set_parallel(false)
	tween.tween_callback(Callable(label, "queue_free"))


func _finish_activation_if_complete() -> void:
	if active_actor == null or battle_finished:
		return
	if active_actor.moved_this_activation and active_actor.acted_this_activation:
		# FFT still lets the player validate the final facing before the Active Turn ends.
		_clear_pending_action()
		selected_skill_id = ""
		skill_preview_cells.clear()
		preview_path_cells.clear()
		_refresh_player_overlays()
		_update_ui_text()


func _on_move_mode_pressed() -> void:
	_clear_pending_action()
	if not _player_can_input() or active_actor.moved_this_activation:
		return
	input_mode = MODE_MOVE
	preview_path_cells.clear()
	_refresh_player_overlays()
	_update_ui_text()


func _on_attack_mode_pressed() -> void:
	_clear_pending_action()
	if not _player_can_input() or active_actor.acted_this_activation:
		return
	input_mode = MODE_ATTACK
	preview_path_cells.clear()
	_refresh_player_overlays()
	_update_ui_text()


func _on_skill_pressed(slot: int) -> void:
	_clear_pending_action()
	if not _player_can_input() or active_actor == null or active_actor.acted_this_activation:
		return
	var skill_id: String = active_actor.primary_skill if slot == 1 else active_actor.secondary_skill
	if skill_id.is_empty():
		_log("Aucune compétence dans ce slot.")
		return
	if not active_actor.can_use_skill(skill_id):
		var skill: Resource = SkillCatalog.definition(skill_id)
		var cost: int = int(skill.get("focus_cost")) if skill != null else 0
		_log("%s indisponible • MP %d/%d ou action déjà consommée." % [SkillCatalog.display_name(skill_id), active_actor.focus, cost])
		return
	selected_skill_id = skill_id
	input_mode = MODE_SKILL
	preview_path_cells.clear()
	skill_preview_cells.clear()
	_refresh_player_overlays()
	_refresh_context_preview()
	_update_ui_text()


func _cancel_skill_mode() -> void:
	_clear_pending_action()
	if not _player_can_input():
		return
	selected_skill_id = ""
	skill_preview_cells.clear()
	input_mode = MODE_MOVE if not active_actor.moved_this_activation else MODE_ATTACK
	_refresh_player_overlays()
	_update_ui_text()


func _on_face_pressed(turns: int = 1) -> void:
	_clear_pending_action()
	if not _player_can_input() or active_actor == null:
		return
	active_actor.rotate_facing_quarter(turns)
	_log("%s s'oriente vers %s." % [active_actor.display_name, active_actor.facing_name()])
	_update_ui_text()


func _on_end_activation_pressed() -> void:
	_clear_pending_action()
	if not _player_can_input():
		return
	active_actor.waited_this_activation = not active_actor.moved_this_activation and not active_actor.acted_this_activation
	var ct_cost: int = CombatMechanics.action_ct_cost(active_actor.moved_this_activation, active_actor.acted_this_activation, false)
	var wait_note: String = " • cast conservé" if active_actor.is_casting() and not active_actor.acted_this_activation else ""
	_log("%s termine son activation • face %s • coût CT %d%s." % [active_actor.display_name, active_actor.facing_name(), ct_cost, wait_note])
	_start_next_activation()


func _refresh_player_overlays() -> void:
	reachable_cells.clear()
	attack_cells.clear()
	skill_target_cells.clear()
	path_parents.clear()
	if not _player_can_input():
		_rebuild_highlights()
		return
	if input_mode == MODE_MOVE and not active_actor.moved_this_activation:
		_compute_reachable_cells(active_actor)
	elif input_mode == MODE_ATTACK and not active_actor.acted_this_activation:
		_compute_attack_cells(active_actor)
	elif input_mode == MODE_SKILL and not active_actor.acted_this_activation and not selected_skill_id.is_empty():
		_compute_skill_target_cells(active_actor, selected_skill_id)
	_rebuild_highlights()


func _compute_reachable_cells(actor: SporeUnitActor3D) -> void:
	reachable_cells.clear()
	path_parents.clear()
	if actor == null or map_root == null:
		return
	if actor.status_prevents_movement():
		return
	var blocked: Dictionary = _blocked_cells_except(actor)
	if actor.uses_teleport():
		var max_distance: int = actor.effective_move_range() + 9
		for y: int in range(map_root.grid_height):
			for x: int in range(map_root.grid_width):
				var teleport_cell: Vector2i = Vector2i(x, y)
				if teleport_cell == actor.cell or blocked.has(teleport_cell):
					continue
				var teleport_distance: int = _cell_distance(actor.cell, teleport_cell)
				if teleport_distance <= max_distance and CombatMechanics.teleport_success_chance(teleport_distance, actor.effective_move_range()) > 0:
					reachable_cells[teleport_cell] = teleport_distance
					path_parents[teleport_cell] = actor.cell
		return
	var environment: Dictionary = map_root.to_environment()
	var obstacle_cells_value: Variant = environment.get("obstacles", [])
	if obstacle_cells_value is Array:
		for obstacle_var: Variant in obstacle_cells_value:
			if obstacle_var is Vector2i:
				blocked[obstacle_var] = true
	var frontier: Array[Vector2i] = []
	frontier.append(actor.cell)
	var cost_by_cell: Dictionary = {actor.cell: 0}
	path_parents[actor.cell] = actor.cell
	var directions: Array[Vector2i] = [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]
	while not frontier.is_empty():
		var current: Vector2i = frontier[0]
		frontier.remove_at(0)
		var current_cost: int = int(cost_by_cell.get(current, 0))
		for direction: Vector2i in directions:
			var next_cell: Vector2i = current + direction
			if not map_root.is_cell_valid(next_cell) or blocked.has(next_cell):
				continue
			if not _can_step_between(current, next_cell, actor):
				continue
			var next_cost: int = current_cost + 1
			var effective_move: int = actor.effective_move_range()
			if next_cost > effective_move:
				continue
			if cost_by_cell.has(next_cell) and int(cost_by_cell[next_cell]) <= next_cost:
				continue
			cost_by_cell[next_cell] = next_cost
			path_parents[next_cell] = current
			frontier.append(next_cell)
			reachable_cells[next_cell] = next_cost
	reachable_cells.erase(actor.cell)


func _compute_attack_cells(actor: SporeUnitActor3D) -> void:
	attack_cells.clear()
	if actor == null or map_root == null:
		return
	if actor.status_prevents_action():
		return
	var origin_height: int = map_root.elevation_at(actor.cell)
	for y: int in range(map_root.grid_height):
		for x: int in range(map_root.grid_width):
			var cell_value: Vector2i = Vector2i(x, y)
			var distance: int = absi(cell_value.x - actor.cell.x) + absi(cell_value.y - actor.cell.y)
			var effective_range: int = maxi(1, actor.attack_range + actor.status_modifier("range_delta"))
			if not CombatMechanics.range_allowed(distance, actor.attack_min_range, effective_range):
				continue
			var delta_height: int = absi(map_root.elevation_at(cell_value) - origin_height)
			if delta_height > height_attack_tolerance:
				continue
			if not _has_line_of_sight(actor.cell, cell_value):
				continue
			attack_cells[cell_value] = distance


func _compute_skill_target_cells(actor: SporeUnitActor3D, skill_id: String) -> void:
	skill_target_cells.clear()
	if actor == null or map_root == null or actor.status_prevents_action():
		return
	var skill: Resource = SkillCatalog.definition(skill_id)
	if skill == null:
		return
	var target_mode: String = String(skill.get("target_mode"))
	if target_mode == "self":
		skill_target_cells[actor.cell] = 0
		return
	var skill_range: int = maxi(0, int(skill.get("range")) + actor.status_modifier("range_delta"))
	var ignore_los: bool = _skill_has_tag(skill, "ignore_los")
	for y: int in range(map_root.grid_height):
		for x: int in range(map_root.grid_width):
			var cell_value: Vector2i = Vector2i(x, y)
			var distance: int = _cell_distance(actor.cell, cell_value)
			if distance > skill_range:
				continue
			if absi(map_root.elevation_at(actor.cell) - map_root.elevation_at(cell_value)) > skill_target_height_tolerance:
				continue
			if not ignore_los and cell_value != actor.cell and not _has_line_of_sight(actor.cell, cell_value):
				continue
			if _skill_has_area_shape(skill, "line") and cell_value.x != actor.cell.x and cell_value.y != actor.cell.y:
				continue
			if not _skill_target_mode_accepts(actor, target_mode, cell_value):
				continue
			skill_target_cells[cell_value] = distance


func _skill_target_mode_accepts(actor: SporeUnitActor3D, target_mode: String, cell_value: Vector2i) -> bool:
	var occupant: SporeUnitActor3D = actors_by_cell.get(cell_value, null) as SporeUnitActor3D
	match target_mode:
		"ground":
			return true
		"ally":
			var revive_allowed: bool = not selected_skill_id.is_empty() and _skill_has_tag(SkillCatalog.definition(selected_skill_id), "revive")
			return occupant != null and occupant.team == actor.team and (occupant.alive or (revive_allowed and occupant.downed and not occupant.removed_from_battle))
		"enemy":
			return occupant != null and occupant.alive and occupant.team != actor.team
		"unit":
			return occupant != null and occupant.alive
		"self":
			return cell_value == actor.cell
	return false


func _skill_has_area_shape(skill: Resource, shape: String) -> bool:
	if skill == null:
		return false
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if effect_var is Resource and String((effect_var as Resource).get("area_shape")) == shape:
				return true
	return false


func _skill_has_tag(skill: Resource, tag: String) -> bool:
	if skill == null:
		return false
	var raw_tags: Variant = skill.get("effect_tags")
	if raw_tags is PackedStringArray:
		return (raw_tags as PackedStringArray).has(tag)
	return false


func _skill_area_cells(skill: Resource, anchor_cell: Vector2i, caster_cell: Vector2i) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	var lookup: Dictionary = {}
	if skill == null:
		return result
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if effect_var is Resource:
				for cell_value: Vector2i in _effect_area_cells(effect_var as Resource, anchor_cell, caster_cell):
					lookup[cell_value] = true
	for key: Variant in lookup.keys():
		if key is Vector2i:
			result.append(key)
	result.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return _cell_distance(anchor_cell, a) < _cell_distance(anchor_cell, b))
	return result


func _effect_area_cells(effect: Resource, anchor_cell: Vector2i, caster_cell: Vector2i) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	if effect == null or map_root == null:
		return result
	var radius: int = maxi(0, int(effect.get("radius")))
	var shape: String = String(effect.get("area_shape"))
	var candidates: Array[Vector2i] = []
	if shape == "line":
		var direction: Vector2i = _dominant_direction(anchor_cell - caster_cell)
		if direction == Vector2i.ZERO:
			direction = active_actor.facing if active_actor != null else Vector2i.DOWN
		var length: int = maxi(radius, _cell_distance(caster_cell, anchor_cell))
		length = maxi(1, length)
		for step: int in range(1, length + 1):
			candidates.append(caster_cell + direction * step)
	elif shape == "single" or radius <= 0:
		candidates.append(anchor_cell)
	else:
		for y_offset: int in range(-radius, radius + 1):
			for x_offset: int in range(-radius, radius + 1):
				var delta: Vector2i = Vector2i(x_offset, y_offset)
				var include: bool = false
				match shape:
					"cross": include = (x_offset == 0 or y_offset == 0) and absi(x_offset) + absi(y_offset) <= radius
					"diamond": include = absi(x_offset) + absi(y_offset) <= radius
					"circle": include = x_offset * x_offset + y_offset * y_offset <= radius * radius
					_: include = delta == Vector2i.ZERO
				if include:
					candidates.append(anchor_cell + delta)
	var anchor_height: int = map_root.elevation_at(anchor_cell) if map_root.is_cell_valid(anchor_cell) else 0
	var seen: Dictionary = {}
	for cell_value: Vector2i in candidates:
		if not map_root.is_cell_valid(cell_value) or seen.has(cell_value):
			continue
		if absi(map_root.elevation_at(cell_value) - anchor_height) > skill_area_height_tolerance:
			continue
		seen[cell_value] = true
		result.append(cell_value)
	return result


func _refresh_context_preview() -> void:
	if input_mode == MODE_SKILL:
		_refresh_skill_preview()
	else:
		_refresh_path_preview()


func _refresh_skill_preview() -> void:
	skill_preview_cells.clear()
	if not _player_can_input() or input_mode != MODE_SKILL or active_actor == null or selected_skill_id.is_empty():
		_rebuild_highlights()
		return
	if not skill_target_cells.has(hovered_cell):
		_rebuild_highlights()
		return
	var skill: Resource = SkillCatalog.definition(selected_skill_id)
	if skill != null:
		skill_preview_cells = _skill_area_cells(skill, hovered_cell, active_actor.cell)
	_rebuild_highlights()


func _player_use_skill(anchor_cell: Vector2i) -> void:
	if active_actor == null or active_actor.acted_this_activation or selected_skill_id.is_empty():
		return
	if not skill_target_cells.has(anchor_cell) or not active_actor.can_use_skill(selected_skill_id):
		return
	_cancel_cast_for_command_3d(active_actor, "une nouvelle action")
	var skill: Resource = SkillCatalog.definition(selected_skill_id)
	if skill == null:
		return
	if SkillCatalog.cast_time_ticks(selected_skill_id) > 0:
		active_actor.face_cell(anchor_cell)
		if _queue_cast_3d(active_actor, selected_skill_id, anchor_cell):
			selected_skill_id = ""
			skill_preview_cells.clear()
			if not active_actor.moved_this_activation:
				input_mode = MODE_MOVE
			_refresh_player_overlays()
			_update_ui_text()
			_finish_activation_if_complete()
		return
	player_busy = true
	var skill_name: String = String(skill.get("display_name"))
	var anchor_global: Vector3 = map_root.to_global(map_root.cell_top_local(anchor_cell))
	active_actor.face_cell(anchor_cell)
	_begin_action_camera(active_actor.global_position, anchor_global, 0.86, action_camera_zoom_in + 0.25)
	active_actor.play_cast(anchor_global)
	await get_tree().create_timer(0.06).timeout
	var tracked_skill_target: SporeUnitActor3D = actors_by_cell.get(anchor_cell, null) as SporeUnitActor3D
	var tracked_skill_offset: Vector3 = Vector3(0.0, 0.64, 0.0) if tracked_skill_target != null else Vector3.ZERO
	await _play_action_vfx_to_impact(String(skill.get("vfx_id")), active_actor.global_position + Vector3(0.0, 0.78, 0.0), anchor_global + Vector3(0.0, 0.18, 0.0), true, tracked_skill_target, tracked_skill_offset)
	await _play_skill_area_impacts(skill, active_actor, anchor_cell)
	_skill_hit_cache.clear()
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if effect_var is Resource and active_actor.alive:
				_apply_skill_effect(active_actor, skill, effect_var as Resource, anchor_cell)
	_camera_impact(impact_shake_strength * 0.85)
	await get_tree().create_timer(0.08).timeout
	player_busy = false
	if not active_actor.alive:
		selected_skill_id = ""
		skill_preview_cells.clear()
		if not _check_battle_end():
			call_deferred("_start_next_activation")
		return
	active_actor.spend_skill(selected_skill_id)
	active_actor.remove_statuses_on_attack()
	_log("%s utilise %s • MP %d/%d." % [active_actor.display_name, skill_name, active_actor.focus, active_actor.max_focus])
	selected_skill_id = ""
	skill_preview_cells.clear()
	if not active_actor.moved_this_activation and active_actor.alive:
		input_mode = MODE_MOVE
	_refresh_player_overlays()
	_update_ui_text()
	_check_battle_end()
	_finish_activation_if_complete()


func _apply_skill_effect(caster: SporeUnitActor3D, skill: Resource, effect: Resource, anchor_cell: Vector2i) -> void:
	var effect_type: String = String(effect.get("effect_type"))
	if effect_type == "zone":
		_create_persistent_zone(caster, skill, effect, anchor_cell)
		return
	var targets: Array[SporeUnitActor3D] = _skill_effect_targets(caster, effect, anchor_cell)
	for target: SporeUnitActor3D in targets:
		if target == null:
			continue
		if not target.alive and not (effect_type == "revive" and target.downed and not target.removed_from_battle):
			continue
		var uses_status_formula: bool = effect_type == "status" and int(skill.get("fft_status_modifier")) > 0
		var hostile_roll_effect: bool = effect_type in ["damage", "status", "push", "pull"] and target.team != caster.team and not uses_status_formula
		if hostile_roll_effect and not _skill_hits_target_3d(caster, skill, target):
			continue
		var amount: int = int(effect.get("amount"))
		match effect_type:
			"revive":
				var restored: int = target.revive(caster.revive_hp_bonus + maxi(0, amount))
				if restored > 0:
					actors_by_cell[target.cell] = target
					_show_floating_text(target.position + Vector3(0.0, 1.25, 0.0), "RELEVÉ +%d" % restored, Color(0.48, 0.90, 0.66, 1.0))
					_log("%s relève %s avec %d PV." % [caster.display_name, target.display_name, restored])
			"damage":
				var damage_type: String = String(effect.get("damage_type"))
				var damage: int = amount
				if bool(effect.get("use_attack_stat")):
					var compatibility: String = CombatMechanics.zodiac_compatibility(caster.zodiac_sign, target.zodiac_sign, caster.sex, target.sex)
					if damage_type == "physical":
						damage = CombatMechanics.zodiac_adjust(caster.effective_physical_power(), compatibility) + amount
					else:
						var spell_q: int = int(effect.get("fft_spell_power_q"))
						if spell_q <= 0:
							spell_q = maxi(1, amount + 3)
						damage = CombatMechanics.fft_magic_damage(caster.effective_magic_power(), spell_q, caster.faith, target.faith, compatibility)
				damage += caster.status_modifier("outgoing_damage_delta") + target.status_modifier("incoming_damage_delta")
				# FFT: elevation/terrain do not add flat damage here; height remains a
				# targeting/range concern and the formula owns the damage result.
				var defense: int = target.effective_physical_defense() if damage_type == "physical" else target.effective_magic_defense()
				damage = CombatMechanics.damage_after_defense(damage, defense, 1)
				if damage_type == "physical":
					damage = CombatMechanics.apply_charging_physical_vulnerability(damage, target.is_casting())
					if target.statuses.has("sleep"):
						damage = CombatMechanics.apply_charging_physical_vulnerability(damage, true)
				damage = CombatMechanics.defensive_ability_damage(damage, damage_type, target.statuses.has("protect"), target.statuses.has("shell"), target.support_ability)
				var single_target: bool = int(effect.get("radius")) <= 0 and String(effect.get("target_scope")) == "target"
				_apply_damage_with_reactions(caster, target, damage, String(skill.get("display_name")), true, single_target, String(effect.get("damage_type")))
			"heal":
				var healed: int = target.heal(maxi(0, amount))
				if healed > 0:
					_show_floating_text(target.position + Vector3(0.0, 1.15, 0.0), "+%d" % healed, Color(0.48, 0.90, 0.66, 1.0))
			"status":
				var status_id: String = String(effect.get("status_id"))
				var formula_modifier: int = int(skill.get("fft_status_modifier"))
				if formula_modifier > 0 and target.team != caster.team:
					var compatibility: String = CombatMechanics.zodiac_compatibility(caster.zodiac_sign, target.zodiac_sign, caster.sex, target.sex)
					var status_chance: int = CombatMechanics.fft_status_success_chance(caster.effective_magic_power(), formula_modifier, caster.faith, target.faith, compatibility, target.statuses.has("shell"), target.support_ability == "magic_defense_up")
					if not _roll_hit_3d(status_chance):
						_show_floating_text(target.position + Vector3(0.0, 1.28, 0.0), "STATUS MISS", Color(0.90, 0.90, 0.95, 1.0))
						continue
				if target.apply_status(status_id):
					var status_data: Resource = StatusCatalog.definition(status_id)
					var status_name: String = String(status_data.get("display_name")) if status_data != null else status_id
					_show_floating_text(target.position + Vector3(0.0, 1.28, 0.0), status_name, Color(0.78, 0.62, 1.0, 1.0))
			"guard":
				target.apply_status("guarded")
				_show_floating_text(target.position + Vector3(0.0, 1.28, 0.0), "GARDE", Color(0.56, 0.88, 0.68, 1.0))
			"focus":
				var focus_delta: int = target.change_focus(amount)
				_show_floating_text(target.position + Vector3(0.0, 1.28, 0.0), "%+d MP" % focus_delta, Color(0.42, 0.78, 1.0, 1.0))
			"reaction":
				target.reaction_ready = true
				_show_floating_text(target.position + Vector3(0.0, 1.28, 0.0), "RÉACTION", Color(1.0, 0.82, 0.40, 1.0))
			"push":
				_try_displace_actor(target, caster.cell, maxi(1, absi(amount)), true)
			"pull":
				_try_displace_actor(target, caster.cell, maxi(1, absi(amount)), false)


func _skill_effect_targets(caster: SporeUnitActor3D, effect: Resource, anchor_cell: Vector2i) -> Array[SporeUnitActor3D]:
	var result: Array[SporeUnitActor3D] = []
	var scope: String = String(effect.get("target_scope"))
	if scope == "self":
		result.append(caster)
		return result
	var cells: Array[Vector2i] = _effect_area_cells(effect, anchor_cell, caster.cell)
	if scope == "target":
		var anchor_actor: SporeUnitActor3D = actors_by_cell.get(anchor_cell, null) as SporeUnitActor3D
		var revive_effect: bool = String(effect.get("effect_type")) == "revive"
		if anchor_actor != null and (anchor_actor.alive or (revive_effect and anchor_actor.downed and not anchor_actor.removed_from_battle)):
			result.append(anchor_actor)
		return result
	var seen: Dictionary = {}
	for cell_value: Vector2i in cells:
		var target: SporeUnitActor3D = actors_by_cell.get(cell_value, null) as SporeUnitActor3D
		if target == null or not target.alive or seen.has(target):
			continue
		if scope == "allies" and target.team != caster.team:
			continue
		if scope == "enemies" and target.team == caster.team:
			continue
		seen[target] = true
		result.append(target)
	return result


func _try_displace_actor(target: SporeUnitActor3D, source_cell: Vector2i, distance: int, push: bool) -> void:
	if target == null or not target.alive or map_root == null:
		return
	var direction: Vector2i = _dominant_direction(target.cell - source_cell)
	if not push:
		direction = -direction
	if direction == Vector2i.ZERO:
		return
	for _step: int in range(distance):
		var next_cell: Vector2i = target.cell + direction
		if not map_root.is_cell_valid(next_cell) or actors_by_cell.has(next_cell):
			break
		var tile: Node = map_root.tile_at(next_cell)
		if tile != null and String(tile.get("terrain_type")) == "obstacle":
			break
		if not _can_step_between(target.cell, next_cell, target):
			break
		actors_by_cell.erase(target.cell)
		target.move_to_cell(map_root, next_cell, 0.13)
		actors_by_cell[next_cell] = target


func _show_skill_burst(cell_value: Vector2i, color: Color) -> void:
	if map_root == null:
		return
	var marker: MeshInstance3D = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = 0.18
	mesh.bottom_radius = 0.18
	mesh.height = 0.05
	marker.mesh = mesh
	marker.position = map_root.cell_top_local(cell_value) + Vector3(0.0, 0.11, 0.0)
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(color.r, color.g, color.b, 0.72)
	material.emission_enabled = true
	material.emission = color
	material.emission_energy_multiplier = 0.65
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	marker.material_override = material
	_actor_holder.add_child(marker)
	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(marker, "scale", Vector3(5.0, 1.0, 5.0), 0.32)
	tween.tween_property(material, "albedo_color", Color(color.r, color.g, color.b, 0.0), 0.32)
	tween.set_parallel(false)
	tween.tween_callback(Callable(marker, "queue_free"))


func _process_status_phase(actor: SporeUnitActor3D, phase: String) -> void:
	if actor == null or not actor.alive:
		return
	var events: Array[Dictionary] = actor.phase_status_events(phase)
	for event: Dictionary in events:
		var event_type: String = String(event.get("type", ""))
		var amount: int = int(event.get("amount", 0))
		var status_id: String = String(event.get("status_id", ""))
		var data: Resource = StatusCatalog.definition(status_id)
		var status_name: String = String(data.get("display_name")) if data != null else status_id
		if status_tick_vfx_enabled and data != null:
			var tick_vfx_id: String = String(data.get("vfx_id"))
			if not tick_vfx_id.is_empty():
				_spawn_action_vfx(tick_vfx_id, actor.global_position + Vector3(0.0, 0.42, 0.0), actor.global_position + Vector3(0.0, 0.42, 0.0), false, actor, Vector3(0.0, 0.42, 0.0))
		if event_type == "damage":
			var result: Dictionary = _apply_damage_with_reactions(null, actor, amount, status_name, false, false, String(event.get("damage_type", "physical")))
			var applied: int = int(result.get("applied", 0))
			_log("%s subit %d via %s." % [actor.display_name, applied, status_name])
			if not actor.alive:
				actor.play_ko()
				actors_by_cell[actor.cell] = actor
				_log("%s est K.O." % actor.display_name)
				return
		elif event_type == "heal":
			var healed: int = actor.heal(amount)
			if healed > 0:
				_show_floating_text(actor.position + Vector3(0.0, 1.15, 0.0), "+%d" % healed, Color(0.48, 0.90, 0.66, 1.0))


func _start_new_round() -> void:
	for actor: SporeUnitActor3D in player_actors:
		if actor != null:
			actor.reset_round_reaction()
			if actor.alive:
				actor.tick_skill_resources()
	for actor: SporeUnitActor3D in enemy_actors:
		if actor != null:
			actor.reset_round_reaction()
			if actor.alive:
				actor.tick_skill_resources()
	_advance_persistent_zones_round()
	_log("— Round %d • CT dynamique —" % round_number)


func _create_persistent_zone(caster: SporeUnitActor3D, skill: Resource, effect: Resource, anchor_cell: Vector2i) -> void:
	if caster == null or effect == null or map_root == null:
		return
	var cells: Array[Vector2i] = _effect_area_cells(effect, anchor_cell, caster.cell)
	if cells.is_empty():
		return
	_zone_serial += 1
	var zone: Dictionary = {
		"id": _zone_serial,
		"name": String(skill.get("display_name")) if skill != null else "Zone",
		"cells": cells,
		"anchor": anchor_cell,
		"owner_team": caster.team,
		"owner_actor": caster,
		"scope": String(effect.get("target_scope")),
		"tick_type": String(effect.get("zone_tick_type")),
		"tick_phase": String(effect.get("zone_tick_phase")),
		"remaining_rounds": maxi(1, int(effect.get("zone_duration_rounds"))),
		"amount": int(effect.get("amount")),
		"use_attack_stat": bool(effect.get("use_attack_stat")),
		"status_id": String(effect.get("status_id")),
	}
	zone["visual"] = _build_persistent_zone_visual(zone)
	persistent_zones.append(zone)
	_log("%s crée une zone persistante (%d rounds)." % [caster.display_name, int(zone["remaining_rounds"])])


func _build_persistent_zone_visual(zone: Dictionary) -> Node3D:
	var root: Node3D = Node3D.new()
	root.name = "Zone_%d" % int(zone.get("id", 0))
	_zone_holder.add_child(root)
	var tick_type: String = String(zone.get("tick_type", "damage"))
	var color: Color = Color(1.0, 0.34, 0.24, 0.34)
	if tick_type == "heal":
		color = Color(0.38, 0.92, 0.62, 0.34)
	elif tick_type == "status":
		color = Color(0.72, 0.48, 1.0, 0.34)
	var cells_value: Variant = zone.get("cells", [])
	if cells_value is Array:
		for cell_var: Variant in cells_value:
			if not (cell_var is Vector2i):
				continue
			var cell_value: Vector2i = cell_var
			var marker: MeshInstance3D = MeshInstance3D.new()
			var mesh: CylinderMesh = CylinderMesh.new()
			mesh.top_radius = map_root.tile_size * 0.40
			mesh.bottom_radius = map_root.tile_size * 0.40
			mesh.height = 0.025
			marker.mesh = mesh
			marker.position = map_root.cell_top_local(cell_value) + Vector3(0.0, 0.055, 0.0)
			var material: StandardMaterial3D = StandardMaterial3D.new()
			material.albedo_color = color
			material.emission_enabled = true
			material.emission = Color(color.r, color.g, color.b, 1.0)
			material.emission_energy_multiplier = 0.18
			material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			marker.material_override = material
			root.add_child(marker)
	var anchor_value: Variant = zone.get("anchor", Vector2i.ZERO)
	if anchor_value is Vector2i:
		var label: Label3D = Label3D.new()
		label.name = "DurationLabel"
		label.text = "ZONE %dr" % int(zone.get("remaining_rounds", 1))
		label.font_size = 24
		label.outline_size = 7
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.position = map_root.cell_top_local(anchor_value) + Vector3(0.0, 0.30, 0.0)
		root.add_child(label)
	return root


func _advance_persistent_zones_round() -> void:
	var kept: Array[Dictionary] = []
	for zone: Dictionary in persistent_zones:
		var remaining: int = int(zone.get("remaining_rounds", 1)) - 1
		zone["remaining_rounds"] = remaining
		var visual: Node3D = zone.get("visual", null) as Node3D
		if remaining <= 0:
			if visual != null:
				visual.queue_free()
			continue
		if visual != null:
			var label: Label3D = visual.get_node_or_null("DurationLabel") as Label3D
			if label != null:
				label.text = "ZONE %dr" % remaining
		kept.append(zone)
	persistent_zones = kept


func _process_persistent_zones_for_actor(actor: SporeUnitActor3D, phase: String) -> void:
	if actor == null or not actor.alive:
		return
	for zone: Dictionary in persistent_zones:
		if String(zone.get("tick_phase", "activation_start")) != phase:
			continue
		var cells_value: Variant = zone.get("cells", [])
		if not (cells_value is Array) or not (cells_value as Array).has(actor.cell):
			continue
		if not _persistent_zone_accepts_actor(zone, actor):
			continue
		var tick_type: String = String(zone.get("tick_type", "damage"))
		var amount: int = int(zone.get("amount", 0))
		var owner: SporeUnitActor3D = zone.get("owner_actor", null) as SporeUnitActor3D
		if bool(zone.get("use_attack_stat", false)) and owner != null:
			amount += owner.attack_power + owner.status_modifier("attack_delta")
		match tick_type:
			"damage":
				if owner != null:
					amount += owner.status_modifier("outgoing_damage_delta")
				amount += actor.status_modifier("incoming_damage_delta")
				var result: Dictionary = _apply_damage_with_reactions(owner, actor, maxi(1, amount), String(zone.get("name", "zone")), false, false)
				_log("%s subit %d dans %s." % [actor.display_name, int(result.get("applied", 0)), String(zone.get("name", "zone"))])
			"heal":
				var healed: int = actor.heal(maxi(0, amount))
				if healed > 0:
					_show_floating_text(actor.position + Vector3(0.0, 1.15, 0.0), "+%d" % healed, Color(0.48, 0.90, 0.66, 1.0))
			"status":
				var status_id: String = String(zone.get("status_id", ""))
				if actor.apply_status(status_id):
					var status_data: Resource = StatusCatalog.definition(status_id)
					var status_name: String = String(status_data.get("display_name")) if status_data != null else status_id
					_show_floating_text(actor.position + Vector3(0.0, 1.25, 0.0), status_name, Color(0.76, 0.58, 1.0, 1.0))
		if not actor.alive:
			return


func _persistent_zone_accepts_actor(zone: Dictionary, actor: SporeUnitActor3D) -> bool:
	var owner_team: String = String(zone.get("owner_team", ""))
	var scope: String = String(zone.get("scope", "enemies"))
	match scope:
		"enemies":
			return actor.team != owner_team
		"allies":
			return actor.team == owner_team
		"self":
			var owner: SporeUnitActor3D = zone.get("owner_actor", null) as SporeUnitActor3D
			return actor == owner
		"target":
			return true
	return true


func _blocked_cells_except(actor: SporeUnitActor3D) -> Dictionary:
	var blocked: Dictionary = {}
	for cell_var: Variant in actors_by_cell.keys():
		if not (cell_var is Vector2i):
			continue
		var cell_value: Vector2i = cell_var
		var occupant: SporeUnitActor3D = actors_by_cell.get(cell_value, null) as SporeUnitActor3D
		if occupant != null and occupant.battle_present() and occupant != actor:
			blocked[cell_value] = true
	return blocked


func _execute_enemy_activation() -> void:
	if battle_finished or active_actor == null or not active_actor.alive or active_actor.team != "enemy":
		enemy_busy = false
		return
	await get_tree().create_timer(0.30).timeout
	if active_actor.is_casting():
		active_actor.waited_this_activation = true
		_log("%s WAIT pour conserver %s." % [active_actor.display_name, SkillCatalog.display_name(String(active_actor.casting.get("skill_id", "")))])
		enemy_busy = false
		_start_next_activation()
		return
	var target: SporeUnitActor3D = _best_target_for(active_actor, player_actors)
	if target == null:
		enemy_busy = false
		_check_battle_end()
		return

	# First evaluate an immediately useful skill versus a basic attack.
	var skill_action: Dictionary = _best_ai_skill_action(active_actor)
	var basic_score: float = _ai_basic_attack_score(active_actor, target) if _is_in_attack_range(active_actor, target) else -999.0
	if not skill_action.is_empty() and float(skill_action.get("score", -999.0)) > basic_score + 0.35:
		await _enemy_use_skill(skill_action)
	elif not active_actor.acted_this_activation and _is_in_attack_range(active_actor, target):
		await _enemy_attack(target)

	# FFT allows Act -> Move as well as Move -> Act. Reposition whenever Move is still available.
	if active_actor.alive and not active_actor.moved_this_activation:
		target = _best_target_for(active_actor, player_actors)
		if target != null:
			var destination: Vector2i = _best_enemy_destination(active_actor, target)
			var path: Array[Vector2i] = _reconstruct_path(destination)
			if destination != active_actor.cell and path.size() >= 2:
				var ai_move_start: Vector2i = active_actor.cell
				actors_by_cell.erase(active_actor.cell)
				_log("%s avance vers %s." % [active_actor.display_name, target.display_name])
				await _move_actor_along_path(active_actor, path, 0.12)
				if active_actor.movement_ability == "move_mp_up" and active_actor.cell != ai_move_start:
					active_actor.change_focus(maxi(1, int(ceil(float(active_actor.max_focus) / 10.0))))
				if not active_actor.alive:
					enemy_busy = false
					if not _check_battle_end():
						_start_next_activation()
					return
				actors_by_cell[active_actor.cell] = active_actor
				active_actor.moved_this_activation = true
				await get_tree().create_timer(0.15).timeout

	if active_actor.alive and not active_actor.acted_this_activation:
		skill_action = _best_ai_skill_action(active_actor)
		target = _best_target_for(active_actor, player_actors)
		basic_score = _ai_basic_attack_score(active_actor, target) if target != null and _is_in_attack_range(active_actor, target) else -999.0
		if not skill_action.is_empty() and float(skill_action.get("score", -999.0)) > basic_score + 0.35:
			await _enemy_use_skill(skill_action)
		elif target != null and target.alive and _is_in_attack_range(active_actor, target):
			await _enemy_attack(target)
		elif target != null and target.alive:
			active_actor.face_cell(target.cell)

	enemy_busy = false
	if not battle_finished:
		_start_next_activation()


func _enemy_attack(target: SporeUnitActor3D) -> void:
	if active_actor == null or target == null or not target.alive:
		return
	active_actor.acted_this_activation = true
	_begin_action_camera(active_actor.global_position, target.global_position, 0.72, action_camera_zoom_in)
	active_actor.play_attack(target.position)
	await _play_action_vfx_to_impact(active_actor.basic_attack_vfx_id, active_actor.global_position + Vector3(0.0, 0.72, 0.0), target.global_position + Vector3(0.0, 0.64, 0.0), true, target, Vector3(0.0, 0.64, 0.0))
	_resolve_attack(active_actor, target)
	_camera_impact()
	if vfx_impact_pause > 0.0:
		await get_tree().create_timer(vfx_impact_pause).timeout
	await get_tree().create_timer(0.12).timeout


func _enemy_use_skill(action: Dictionary) -> void:
	if active_actor == null or not active_actor.alive:
		return
	var skill_id: String = String(action.get("skill_id", ""))
	var anchor_value: Variant = action.get("anchor", active_actor.cell)
	if skill_id.is_empty() or not (anchor_value is Vector2i) or not active_actor.can_use_skill(skill_id):
		return
	var anchor_cell: Vector2i = anchor_value
	var skill: Resource = SkillCatalog.definition(skill_id)
	if skill == null:
		return
	if SkillCatalog.cast_time_ticks(skill_id) > 0:
		active_actor.face_cell(anchor_cell)
		if _queue_cast_3d(active_actor, skill_id, anchor_cell):
			_log("%s choisit %s (score %.1f) et commence son cast." % [active_actor.display_name, String(skill.get("display_name")), float(action.get("score", 0.0))])
			await get_tree().create_timer(0.12).timeout
		return
	active_actor.face_cell(anchor_cell)
	var anchor_global: Vector3 = map_root.to_global(map_root.cell_top_local(anchor_cell))
	_begin_action_camera(active_actor.global_position, anchor_global, 0.86, action_camera_zoom_in + 0.25)
	active_actor.play_cast(anchor_global)
	await get_tree().create_timer(0.06).timeout
	var tracked_skill_target: SporeUnitActor3D = actors_by_cell.get(anchor_cell, null) as SporeUnitActor3D
	var tracked_skill_offset: Vector3 = Vector3(0.0, 0.64, 0.0) if tracked_skill_target != null else Vector3.ZERO
	await _play_action_vfx_to_impact(String(skill.get("vfx_id")), active_actor.global_position + Vector3(0.0, 0.78, 0.0), anchor_global + Vector3(0.0, 0.18, 0.0), true, tracked_skill_target, tracked_skill_offset)
	await _play_skill_area_impacts(skill, active_actor, anchor_cell)
	_skill_hit_cache.clear()
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if effect_var is Resource and active_actor.alive:
				_apply_skill_effect(active_actor, skill, effect_var as Resource, anchor_cell)
	_camera_impact(impact_shake_strength * 0.85)
	if not active_actor.alive:
		_check_battle_end()
		return
	active_actor.spend_skill(skill_id)
	active_actor.remove_statuses_on_attack()
	_log("%s choisit %s (score %.1f)." % [active_actor.display_name, String(skill.get("display_name")), float(action.get("score", 0.0))])
	await get_tree().create_timer(0.18).timeout
	_check_battle_end()


func _best_ai_skill_action(actor: SporeUnitActor3D) -> Dictionary:
	var best: Dictionary = {}
	var best_score: float = 0.35
	if actor == null or not actor.alive or actor.acted_this_activation:
		return best
	for skill_id: String in [actor.primary_skill, actor.secondary_skill]:
		if skill_id.is_empty() or not actor.can_use_skill(skill_id):
			continue
		var skill: Resource = SkillCatalog.definition(skill_id)
		if skill == null:
			continue
		if int(skill.get("cast_time_ticks")) > 0 and actor.focus < int(skill.get("focus_cost")):
			continue
		_compute_skill_target_cells(actor, skill_id)
		for anchor_var: Variant in skill_target_cells.keys():
			if not (anchor_var is Vector2i):
				continue
			var anchor_cell: Vector2i = anchor_var
			var score: float = _score_ai_skill_action(actor, skill, anchor_cell)
			if score > best_score:
				best_score = score
				best = {"skill_id": skill_id, "anchor": anchor_cell, "score": score}
	return best


func _score_ai_skill_action(actor: SporeUnitActor3D, skill: Resource, anchor_cell: Vector2i) -> float:
	if actor == null or skill == null:
		return -999.0
	var score: float = -float(int(skill.get("focus_cost"))) * 0.25
	score -= float(int(skill.get("cast_time_ticks"))) * 0.30
	var raw_effects: Variant = skill.get("effects")
	if not (raw_effects is Array):
		return score
	for effect_var: Variant in raw_effects:
		if not (effect_var is Resource):
			continue
		var effect: Resource = effect_var as Resource
		var effect_type: String = String(effect.get("effect_type"))
		if effect_type == "zone":
			score += _score_ai_persistent_zone(actor, effect, anchor_cell)
			continue
		var targets: Array[SporeUnitActor3D] = _skill_effect_targets(actor, effect, anchor_cell)
		for target: SporeUnitActor3D in targets:
			if target == null or not target.alive:
				continue
			var amount: int = int(effect.get("amount"))
			match effect_type:
				"damage":
					var damage: int = amount
					if bool(effect.get("use_attack_stat")):
						damage += actor.effective_physical_power() if String(effect.get("damage_type")) == "physical" else actor.effective_magic_power()
					var ai_defense: int = target.effective_physical_defense() if String(effect.get("damage_type")) == "physical" else target.effective_magic_defense()
					damage = CombatMechanics.damage_after_defense(damage, ai_defense, 1)
					var hit_factor: float = 1.0
					if bool(skill.get("uses_accuracy")) and target.team != actor.team:
						var ai_hit: Dictionary = _hit_profile_3d(actor, target, int(skill.get("accuracy")), _skill_has_tag(skill, "ignore_cover"))
						hit_factor = float(int(ai_hit["chance"])) / 100.0
					score += float(damage) * hit_factor
					if damage >= target.hp:
						score += 7.0 * hit_factor
				"heal":
					var missing: int = maxi(0, target.max_hp - target.hp)
					score += float(mini(missing, maxi(0, amount))) * 1.25
				"status":
					var status_id: String = String(effect.get("status_id"))
					if not target.statuses.has(status_id):
						score += 2.5
				"guard":
					score += 1.8 if target.hp < target.max_hp else 0.8
				"reaction":
					score += 1.5 if not target.reaction_available() else 0.3
				"focus":
					score += float(maxi(0, mini(amount, target.max_focus - target.focus))) * 0.75
				"push", "pull":
					score += 0.6
	return score


func _score_ai_persistent_zone(actor: SporeUnitActor3D, effect: Resource, anchor_cell: Vector2i) -> float:
	var score: float = 0.0
	var cells: Array[Vector2i] = _effect_area_cells(effect, anchor_cell, actor.cell)
	var tick_type: String = String(effect.get("zone_tick_type"))
	var duration: int = maxi(1, int(effect.get("zone_duration_rounds")))
	var scope: String = String(effect.get("target_scope"))
	for cell_value: Vector2i in cells:
		var occupant: SporeUnitActor3D = actors_by_cell.get(cell_value, null) as SporeUnitActor3D
		if occupant == null or not occupant.alive:
			continue
		var accepts: bool = true
		if scope == "enemies":
			accepts = occupant.team != actor.team
		elif scope == "allies":
			accepts = occupant.team == actor.team
		elif scope == "self":
			accepts = occupant == actor
		if not accepts:
			continue
		if tick_type == "damage":
			score += float(maxi(1, int(effect.get("amount")))) * minf(2.5, float(duration))
		elif tick_type == "heal":
			var missing: int = maxi(0, occupant.max_hp - occupant.hp)
			score += float(mini(missing, maxi(0, int(effect.get("amount"))))) * 1.1
		elif tick_type == "status":
			score += 2.0 if not occupant.statuses.has(String(effect.get("status_id"))) else 0.25
	return score


func _ai_basic_attack_score(actor: SporeUnitActor3D, target: SporeUnitActor3D) -> float:
	if actor == null or target == null or not target.alive or not _is_in_attack_range(actor, target):
		return -999.0
	var details: Dictionary = _attack_damage_details(actor, target)
	var damage: int = maxi(0, int(details.get("damage", 1)) - target.flat_damage_reduction)
	var hit_factor: float = float(int(details.get("hit_chance", 100))) / 100.0
	return (float(damage) + (7.0 if damage >= target.hp else 0.0)) * hit_factor


func _best_target_for(actor: SporeUnitActor3D, candidates: Array[SporeUnitActor3D]) -> SporeUnitActor3D:
	var best: SporeUnitActor3D = null
	var best_distance: int = 999999
	var best_hp: int = 999999
	for candidate: SporeUnitActor3D in candidates:
		if candidate == null or not candidate.alive:
			continue
		var distance: int = _cell_distance(actor.cell, candidate.cell)
		if distance < best_distance or (distance == best_distance and candidate.hp < best_hp):
			best = candidate
			best_distance = distance
			best_hp = candidate.hp
	return best


func _best_enemy_destination(actor: SporeUnitActor3D, target: SporeUnitActor3D) -> Vector2i:
	_compute_reachable_cells(actor)
	var best_cell: Vector2i = actor.cell
	var best_can_attack: bool = _can_attack_from_cell(actor, actor.cell, target)
	var best_distance: int = _cell_distance(actor.cell, target.cell)
	var best_height: int = map_root.elevation_at(actor.cell) if map_root != null else 0
	var best_arc_score: int = _arc_score(_relative_attack_arc(actor.cell, target)) if best_can_attack else -1
	var best_move_cost: int = 999999
	for cell_var: Variant in reachable_cells.keys():
		if not (cell_var is Vector2i):
			continue
		var cell_value: Vector2i = cell_var
		var can_attack: bool = _can_attack_from_cell(actor, cell_value, target)
		var distance: int = _cell_distance(cell_value, target.cell)
		var cell_height: int = map_root.elevation_at(cell_value) if map_root != null else 0
		var arc_score: int = _arc_score(_relative_attack_arc(cell_value, target)) if can_attack else -1
		var move_cost: int = int(reachable_cells.get(cell_value, 999999))
		var take_cell: bool = false
		if can_attack and not best_can_attack:
			take_cell = true
		elif can_attack == best_can_attack:
			if can_attack:
				if arc_score > best_arc_score:
					take_cell = true
				elif arc_score == best_arc_score and (cell_height > best_height or (cell_height == best_height and move_cost < best_move_cost)):
					take_cell = true
			elif distance < best_distance or (distance == best_distance and move_cost < best_move_cost):
				take_cell = true
		if take_cell:
			best_cell = cell_value
			best_can_attack = can_attack
			best_distance = distance
			best_height = cell_height
			best_arc_score = arc_score
			best_move_cost = move_cost
	return best_cell


func _can_attack_from_cell(actor: SporeUnitActor3D, from_cell: Vector2i, target: SporeUnitActor3D) -> bool:
	if actor == null or target == null or not target.alive:
		return false
	var distance: int = _cell_distance(from_cell, target.cell)
	var effective_range: int = maxi(1, actor.attack_range + actor.status_modifier("range_delta"))
	if not CombatMechanics.range_allowed(distance, actor.attack_min_range, effective_range):
		return false
	if map_root == null:
		return true
	if absi(map_root.elevation_at(from_cell) - map_root.elevation_at(target.cell)) > height_attack_tolerance:
		return false
	return _has_line_of_sight(from_cell, target.cell)


func _is_in_attack_range(attacker: SporeUnitActor3D, target: SporeUnitActor3D) -> bool:
	if attacker == null or target == null or not attacker.alive or not target.alive:
		return false
	var distance: int = _cell_distance(attacker.cell, target.cell)
	var effective_range: int = maxi(1, attacker.attack_range + attacker.status_modifier("range_delta"))
	if not CombatMechanics.range_allowed(distance, attacker.attack_min_range, effective_range):
		return false
	if map_root == null:
		return true
	if absi(map_root.elevation_at(attacker.cell) - map_root.elevation_at(target.cell)) > height_attack_tolerance:
		return false
	return _has_line_of_sight(attacker.cell, target.cell)


func _refresh_path_preview() -> void:
	preview_path_cells.clear()
	if not _player_can_input() or input_mode != MODE_MOVE or active_actor == null or active_actor.moved_this_activation:
		_rebuild_highlights()
		return
	if reachable_cells.has(hovered_cell):
		var path: Array[Vector2i] = _reconstruct_path(hovered_cell)
		if path.size() > 1:
			for index: int in range(1, path.size()):
				preview_path_cells.append(path[index])
	_rebuild_highlights()


func _reconstruct_path(destination: Vector2i) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	if active_actor == null:
		return result
	if destination == active_actor.cell:
		result.append(active_actor.cell)
		return result
	if not path_parents.has(destination):
		return result
	var current: Vector2i = destination
	result.push_front(current)
	var guard: int = 0
	while current != active_actor.cell and guard < 256:
		var parent_value: Variant = path_parents.get(current, current)
		if not (parent_value is Vector2i):
			result.clear()
			return result
		var parent_cell: Vector2i = parent_value
		if parent_cell == current:
			result.clear()
			return result
		current = parent_cell
		result.push_front(current)
		guard += 1
	return result


func _move_actor_along_path(actor: SporeUnitActor3D, path: Array[Vector2i], duration_per_step: float) -> void:
	if actor == null or map_root == null or path.size() < 2:
		return
	if actor.uses_teleport():
		var destination: Vector2i = path[path.size() - 1]
		var distance: int = _cell_distance(actor.cell, destination)
		var chance: int = CombatMechanics.teleport_success_chance(distance, actor.effective_move_range())
		if battle_rng.randi_range(1, 100) <= chance:
			actor.place_on_map(map_root, destination)
			_show_floating_text(actor.position + Vector3(0.0, 1.2, 0.0), "TELEPORT", Color(0.70, 0.55, 1.0, 1.0))
		else:
			_show_floating_text(actor.position + Vector3(0.0, 1.2, 0.0), "ÉCHEC %d%%" % chance, Color(1.0, 0.55, 0.40, 1.0))
		return
	for index: int in range(1, path.size()):
		if not actor.alive:
			return
		var from_cell: Vector2i = actor.cell
		var step_cell: Vector2i = path[index]
		await _check_opportunity_reactions(actor, from_cell, step_cell)
		if not actor.alive:
			return
		var move_tween: Tween = actor.move_to_cell(map_root, step_cell, duration_per_step)
		await move_tween.finished


func _check_opportunity_reactions(mover: SporeUnitActor3D, from_cell: Vector2i, to_cell: Vector2i) -> void:
	if mover == null or not mover.alive or mover.ignore_opportunity:
		return
	var opponents: Array[SporeUnitActor3D] = enemy_actors if mover.team == "player" else player_actors
	for reactor: SporeUnitActor3D in opponents:
		if reactor == null or not reactor.alive or reactor.reaction_type != "opportunity" or not reactor.reaction_available():
			continue
		if not reactor.can_opportunity_attack:
			continue
		var was_in_reach: bool = CombatMechanics.range_allowed(_cell_distance(reactor.cell, from_cell), reactor.threat_min_range, reactor.threat_max_range)
		var still_in_reach: bool = CombatMechanics.range_allowed(_cell_distance(reactor.cell, to_cell), reactor.threat_min_range, reactor.threat_max_range)
		if not was_in_reach or still_in_reach:
			continue
		if map_root != null and not _has_line_of_sight(reactor.cell, from_cell):
			continue
		if not _reaction_triggers_3d(reactor):
			continue
		_perform_reaction_attack(reactor, mover, "OPPORTUNITÉ", opportunity_damage_penalty)
		await get_tree().create_timer(0.14).timeout
		if not mover.alive:
			return


func _has_line_of_sight(from_cell: Vector2i, to_cell: Vector2i) -> bool:
	if map_root == null:
		return true
	var line_cells: Array[Vector2i] = _grid_line_cells(from_cell, to_cell)
	if line_cells.size() <= 2:
		return true
	var environment: Dictionary = map_root.to_environment()
	var obstacle_lookup: Dictionary = {}
	var raw_obstacles: Variant = environment.get("obstacles", [])
	if raw_obstacles is Array:
		for obstacle_var: Variant in raw_obstacles:
			if obstacle_var is Vector2i:
				obstacle_lookup[obstacle_var] = true
	var endpoint_height: int = maxi(map_root.elevation_at(from_cell), map_root.elevation_at(to_cell))
	for index: int in range(1, line_cells.size() - 1):
		var cell_value: Vector2i = line_cells[index]
		if obstacle_lookup.has(cell_value):
			return false
		if map_root.elevation_at(cell_value) >= endpoint_height + los_block_height_advantage and los_block_height_advantage > 0:
			return false
	return true


func _grid_line_cells(from_cell: Vector2i, to_cell: Vector2i) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	var x0: int = from_cell.x
	var y0: int = from_cell.y
	var x1: int = to_cell.x
	var y1: int = to_cell.y
	var dx: int = absi(x1 - x0)
	var sx: int = 1 if x0 < x1 else -1
	var dy: int = -absi(y1 - y0)
	var sy: int = 1 if y0 < y1 else -1
	var error: int = dx + dy
	while true:
		result.append(Vector2i(x0, y0))
		if x0 == x1 and y0 == y1:
			break
		var twice_error: int = 2 * error
		if twice_error >= dy:
			error += dy
			x0 += sx
		if twice_error <= dx:
			error += dx
			y0 += sy
	return result


func _is_cover_cell(cell_value: Vector2i) -> bool:
	if map_root == null:
		return false
	var environment: Dictionary = map_root.to_environment()
	var raw_cover: Variant = environment.get("cover", [])
	if raw_cover is Array:
		for cover_var: Variant in raw_cover:
			if cover_var is Vector2i and cover_var == cell_value:
				return true
	return false


func _can_step_between(from_cell: Vector2i, to_cell: Vector2i, actor: SporeUnitActor3D = null) -> bool:
	if actor != null and actor.ignores_height_for_movement():
		return true
	if map_root == null:
		return true
	var delta: int = map_root.elevation_at(to_cell) - map_root.elevation_at(from_cell)
	var jump_up: int = max_jump_up + (actor.jump_up_bonus if actor != null else 0)
	var jump_down: int = max_jump_down + (actor.jump_down_bonus if actor != null else 0)
	if delta > 0:
		return delta <= jump_up
	if delta < 0:
		return absi(delta) <= jump_down
	return true


func _dominant_direction(delta: Vector2i) -> Vector2i:
	if delta == Vector2i.ZERO:
		return Vector2i.ZERO
	if absi(delta.x) >= absi(delta.y):
		return Vector2i(1 if delta.x > 0 else -1, 0)
	return Vector2i(0, 1 if delta.y > 0 else -1)


func _relative_attack_arc(attacker_cell: Vector2i, target: SporeUnitActor3D) -> String:
	if target == null:
		return "front"
	var incoming: Vector2i = _dominant_direction(attacker_cell - target.cell)
	if incoming == -target.facing:
		return "back"
	if incoming == target.facing:
		return "front"
	return "side"


func _arc_score(arc: String) -> int:
	if arc == "back":
		return 2
	if arc == "side":
		return 1
	return 0


func _hit_profile_3d(attacker: SporeUnitActor3D, target: SporeUnitActor3D, base_accuracy: int, ignore_cover: bool = false) -> Dictionary:
	if attacker == null or target == null:
		return {"chance": 5, "arc": "front", "height_advantage": false, "covered": false}
	var arc: String = _relative_attack_arc(attacker.cell, target)
	var height_advantage: bool = map_root != null and map_root.elevation_at(attacker.cell) > map_root.elevation_at(target.cell)
	var covered: bool = not ignore_cover and _cell_distance(attacker.cell, target.cell) > 1 and _cover_protects_from(attacker.cell, target.cell)
	var adjusted_base_accuracy: int = base_accuracy
	if base_accuracy == CombatMechanics.BASIC_ATTACK_ACCURACY:
		adjusted_base_accuracy += attacker.basic_attack_accuracy_bonus
	var target_cannot_evade: bool = target.status_prevents_evasion()
	var no_equipment_evade: bool = target_cannot_evade or attacker.support_ability == "concentrate"
	var chance: int = CombatMechanics.fft_physical_hit_chance(
		adjusted_base_accuracy,
		attacker.effective_accuracy(),
		0 if no_equipment_evade else clampi(target.physical_class_evasion + target.status_modifier("evasion_delta"), 0, 100),
		0 if no_equipment_evade else target.physical_shield_evasion,
		0 if no_equipment_evade else target.physical_accessory_evasion,
		0 if no_equipment_evade else target.physical_weapon_evasion,
		arc,
		target.is_casting()
	)
	chance = CombatMechanics.blade_grasp_hit_chance(chance, target.brave, target.reaction_type == "blade_grasp" and target.reaction_available() and not target_cannot_evade)
	return {
		"chance": chance,
		"arc": arc,
		"height_advantage": height_advantage,
		"covered": covered,
	}


func _roll_hit_3d(chance: int) -> bool:
	return battle_rng.randi_range(1, 100) <= clampi(chance, 0, 100)


func _skill_accuracy_kind_3d(skill: Resource) -> String:
	if skill == null:
		return "physical"
	var configured: String = String(skill.get("accuracy_kind"))
	if configured == "physical" or configured == "magical":
		return configured
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if not (effect_var is Resource):
				continue
			var effect: Resource = effect_var as Resource
			if String(effect.get("effect_type")) != "damage":
				continue
			return "physical" if String(effect.get("damage_type")) == "physical" else "magical"
	# Accuracy-using status/control skills behave like magical evasion by default.
	return "magical"


func _skill_hits_target_3d(caster: SporeUnitActor3D, skill: Resource, target: SporeUnitActor3D) -> bool:
	if caster == null or skill == null or target == null or target.team == caster.team:
		return true
	if not bool(skill.get("uses_accuracy")):
		return true
	var cache_key: String = "%s>%s" % [caster.get_instance_id(), target.get_instance_id()]
	if _skill_hit_cache.has(cache_key):
		return bool(_skill_hit_cache[cache_key])
	var ignore_cover: bool = _skill_has_tag(skill, "ignore_cover")
	var hit: Dictionary = _hit_profile_3d(caster, target, int(skill.get("accuracy")), ignore_cover)
	if _skill_accuracy_kind_3d(skill) == "magical":
		var no_magic_evade: bool = target.status_prevents_evasion()
		hit["chance"] = CombatMechanics.fft_magic_hit_chance(
			int(skill.get("accuracy")),
			caster.effective_accuracy(),
			0 if no_magic_evade else target.magic_shield_evasion,
			0 if no_magic_evade else target.magic_accessory_evasion,
			target.is_casting()
		)
	var landed: bool = _roll_hit_3d(int(hit["chance"]))
	_skill_hit_cache[cache_key] = landed
	if not landed:
		_show_floating_text(target.position + Vector3(0.0, 1.18, 0.0), "MISS", Color(0.92, 0.92, 0.96, 1.0))
		_log("%s rate %s avec %s • %d%% HIT." % [caster.display_name, target.display_name, String(skill.get("display_name")), int(hit["chance"])])
	return landed


func _attack_damage_details(attacker: SporeUnitActor3D, target: SporeUnitActor3D) -> Dictionary:
	if attacker == null or target == null:
		return {"damage": 0, "height_bonus": 0, "cover_reduction": 0, "positional_bonus": 0, "arc": "front"}
	var height_bonus: int = 0
	if map_root != null and map_root.elevation_at(attacker.cell) > map_root.elevation_at(target.cell):
		height_bonus = 1
	var distance: int = _cell_distance(attacker.cell, target.cell)
	var cover_reduction: int = ranged_cover_reduction if distance > 1 and _cover_protects_from(attacker.cell, target.cell) else 0
	var arc: String = _relative_attack_arc(attacker.cell, target)
	var positional_bonus: int = 0
	if arc == "back":
		positional_bonus = back_attack_bonus
	elif arc == "side":
		positional_bonus = side_attack_bonus
	var hit: Dictionary = _hit_profile_3d(attacker, target, CombatMechanics.BASIC_ATTACK_ACCURACY, false)
	# Facing affects evasion in FFT; height/back/cover do not add flat weapon damage.
	height_bonus = 0
	positional_bonus = 0
	cover_reduction = 0
	var damage_type: String = attacker.basic_attack_damage_type
	var compatibility: String = CombatMechanics.zodiac_compatibility(attacker.zodiac_sign, target.zodiac_sign, attacker.sex, target.sex)
	var raw_damage: int = CombatMechanics.fft_weapon_damage(
		attacker.effective_physical_power(), attacker.effective_magic_power(), attacker.effective_speed(), attacker.brave, attacker.weapon_power, attacker.weapon_family, compatibility
	) + attacker.basic_attack_damage_bonus + attacker.status_modifier("outgoing_damage_delta") + target.status_modifier("incoming_damage_delta")
	var defense: int = target.effective_physical_defense() if damage_type == "physical" else target.effective_magic_defense()
	var final_damage: int = CombatMechanics.damage_after_defense(raw_damage, defense, 1)
	if damage_type == "physical":
		final_damage = CombatMechanics.apply_charging_physical_vulnerability(final_damage, target.is_casting())
		if target.statuses.has("sleep"):
			final_damage = CombatMechanics.apply_charging_physical_vulnerability(final_damage, true)
	final_damage = CombatMechanics.defensive_ability_damage(final_damage, damage_type, target.statuses.has("protect"), target.statuses.has("shell"), target.support_ability)
	return {
		"damage": final_damage,
		"defense": defense,
		"damage_type": damage_type,
		"hit_chance": int(hit["chance"]),
		"height_bonus": height_bonus,
		"cover_reduction": cover_reduction,
		"positional_bonus": positional_bonus,
		"arc": arc,
	}


func _arc_display_name(arc: String) -> String:
	match arc:
		"back":
			return "DOS +%d" % back_attack_bonus
		"side":
			return "FLANC +%d" % side_attack_bonus
	return "FACE"


func _cover_direction_at(cell_value: Vector2i) -> Vector2i:
	if map_root == null:
		return Vector2i.ZERO
	var tile: Node = map_root.tile_at(cell_value)
	if tile == null or String(tile.get("terrain_type")) != "cover":
		return Vector2i.ZERO
	if tile.has_method("cover_direction"):
		var raw_direction: Variant = tile.call("cover_direction")
		if raw_direction is Vector2i:
			return raw_direction
	return Vector2i.UP


func _cover_protects_from(attacker_cell: Vector2i, target_cell: Vector2i) -> bool:
	var cover_direction: Vector2i = _cover_direction_at(target_cell)
	if cover_direction == Vector2i.ZERO:
		return false
	var incoming: Vector2i = _dominant_direction(attacker_cell - target_cell)
	return incoming == cover_direction


func _cover_facing_name(cell_value: Vector2i) -> String:
	match _cover_direction_at(cell_value):
		Vector2i.UP:
			return "Nord"
		Vector2i.RIGHT:
			return "Est"
		Vector2i.DOWN:
			return "Sud"
		Vector2i.LEFT:
			return "Ouest"
	return "?"


func _cell_distance(a: Vector2i, b: Vector2i) -> int:
	return absi(a.x - b.x) + absi(a.y - b.y)


func _check_battle_end() -> bool:
	var living_players: int = 0
	var living_enemies: int = 0
	for actor: SporeUnitActor3D in player_actors:
		if actor != null and actor.alive:
			living_players += 1
	for actor: SporeUnitActor3D in enemy_actors:
		if actor != null and actor.alive:
			living_enemies += 1
	if living_enemies <= 0:
		battle_finished = true
		_log("VICTOIRE — tous les ennemis sont K.O.")
	elif living_players <= 0:
		battle_finished = true
		_log("DÉFAITE — l'escouade est K.O.")
	if battle_finished:
		enemy_busy = false
		_clear_overlays()
		if active_actor != null:
			active_actor.end_activation()
		_update_ui_text()
	return battle_finished


func _rebuild_highlights() -> void:
	for child: Node in _highlight_holder.get_children():
		child.queue_free()
	if not show_reachable_overlay or map_root == null:
		return
	if input_mode == MODE_MOVE:
		for cell_var: Variant in reachable_cells.keys():
			if cell_var is Vector2i:
				_add_cell_highlight(cell_var, Color(0.48, 0.88, 0.68, 0.56), 0.25)
		for index: int in range(preview_path_cells.size()):
			var preview_cell: Vector2i = preview_path_cells[index]
			var previous_cell: Vector2i = active_actor.cell if index == 0 else preview_path_cells[index - 1]
			var is_jump: bool = map_root.elevation_at(previous_cell) != map_root.elevation_at(preview_cell)
			var path_color: Color = Color(0.42, 0.84, 1.0, 0.92) if is_jump else Color(1.0, 0.84, 0.32, 0.88)
			_add_cell_highlight(preview_cell, path_color, 0.15)
	elif input_mode == MODE_ATTACK:
		for cell_var: Variant in attack_cells.keys():
			if cell_var is Vector2i:
				var attack_cell: Vector2i = cell_var
				var protected: bool = active_actor != null and _cell_distance(active_actor.cell, attack_cell) > 1 and _cover_protects_from(active_actor.cell, attack_cell)
				var attack_color: Color = Color(1.0, 0.64, 0.26, 0.72) if protected else Color(1.0, 0.40, 0.34, 0.58)
				_add_cell_highlight(attack_cell, attack_color, 0.25)
	elif input_mode == MODE_SKILL:
		for cell_var: Variant in skill_target_cells.keys():
			if cell_var is Vector2i:
				_add_cell_highlight(cell_var, Color(0.69, 0.46, 1.0, 0.42), 0.24)
		for preview_cell: Vector2i in skill_preview_cells:
			var occupant: SporeUnitActor3D = actors_by_cell.get(preview_cell, null) as SporeUnitActor3D
			var preview_color: Color = Color(0.42, 0.82, 1.0, 0.76)
			if occupant != null and active_actor != null:
				preview_color = Color(0.48, 0.90, 0.66, 0.84) if occupant.team == active_actor.team else Color(1.0, 0.38, 0.34, 0.86)
			_add_cell_highlight(preview_cell, preview_color, 0.19)
	if not pending_action.is_empty():
		var pending_cell_value: Variant = pending_action.get("cell", Vector2i(-1, -1))
		if pending_cell_value is Vector2i and map_root.is_cell_valid(pending_cell_value):
			_add_cell_highlight(pending_cell_value, Color(1.0, 0.94, 0.52, 0.95), 0.34)


func _add_cell_highlight(cell_value: Vector2i, color: Color, radius_scale: float = 0.25) -> void:
	var marker: MeshInstance3D = MeshInstance3D.new()
	marker.name = "Highlight_%d_%d" % [cell_value.x, cell_value.y]
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = map_root.tile_size * radius_scale
	mesh.bottom_radius = map_root.tile_size * radius_scale
	mesh.height = 0.04
	marker.mesh = mesh
	marker.position = map_root.cell_top_local(cell_value) + Vector3(0.0, 0.045, 0.0)
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.emission_enabled = true
	material.emission = Color(color.r, color.g, color.b, 1.0)
	material.emission_energy_multiplier = 0.24
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	marker.material_override = material
	_highlight_holder.add_child(marker)


func _clear_overlays() -> void:
	_clear_pending_action()
	reachable_cells.clear()
	attack_cells.clear()
	skill_target_cells.clear()
	skill_preview_cells.clear()
	path_parents.clear()
	preview_path_cells.clear()
	selected_skill_id = ""
	_rebuild_highlights()


func _update_cursor_animation() -> void:
	if _cursor_mesh == null:
		return
	var pulse: float = 1.0 + sin(_presentation_time * 5.5) * 0.075
	_cursor_bob = 0.018 + sin(_presentation_time * 4.0) * 0.012
	_cursor_mesh.scale = Vector3(pulse, 1.0, pulse)
	var material: StandardMaterial3D = _cursor_mesh.material_override as StandardMaterial3D
	if material != null:
		var mode_color: Color = Color(0.98, 0.94, 0.55, 0.42)
		if input_mode == MODE_ATTACK:
			mode_color = Color(1.0, 0.35, 0.30, 0.42)
		elif input_mode == MODE_SKILL:
			mode_color = Color(0.72, 0.45, 1.0, 0.42)
		material.albedo_color = mode_color
		material.emission = Color(mode_color.r, mode_color.g, mode_color.b, 1.0)


func _update_cursor() -> void:
	if map_root == null or _cursor_mesh == null:
		return
	if map_root.is_cell_valid(hovered_cell):
		_cursor_mesh.visible = true
		_cursor_mesh.position = map_root.cell_top_local(hovered_cell) + Vector3(0.0, 0.052 + _cursor_bob, 0.0)
	else:
		_cursor_mesh.visible = false


func _persistent_zone_count_at(cell_value: Vector2i) -> int:
	var count: int = 0
	for zone: Dictionary in persistent_zones:
		var cells_value: Variant = zone.get("cells", [])
		if cells_value is Array and (cells_value as Array).has(cell_value):
			count += 1
	return count


func _update_ui_text() -> void:
	if _info_label == null or _help_label == null or _turn_label == null:
		return
	if battle_finished:
		_turn_label.text = "COMBAT TERMINÉ"
		_info_label.text = battle_log[battle_log.size() - 1] if not battle_log.is_empty() else "Combat terminé."
	else:
		var active_name: String = active_actor.display_name if active_actor != null else "—"
		var team_text: String = "JOUEUR" if active_actor != null and active_actor.team == "player" else "ENNEMI"
		_turn_label.text = "Manche %d • %s • %s" % [round_number, team_text, active_name]
		var cell_text: String = "—"
		if map_root != null and map_root.is_cell_valid(hovered_cell):
			cell_text = "%d,%d h%d" % [hovered_cell.x, hovered_cell.y, map_root.elevation_at(hovered_cell)]
			if _is_cover_cell(hovered_cell):
				cell_text += " • couvert %s" % _cover_facing_name(hovered_cell)
			var zone_count: int = _persistent_zone_count_at(hovered_cell)
			if zone_count > 0:
				cell_text += " • zone x%d" % zone_count
			if input_mode == MODE_ATTACK and active_actor != null:
				var effective_range: int = maxi(1, active_actor.attack_range + active_actor.status_modifier("range_delta"))
				if _cell_distance(active_actor.cell, hovered_cell) <= effective_range and not _has_line_of_sight(active_actor.cell, hovered_cell):
					cell_text += " • vue bloquée"
		if active_actor != null:
			var mode_text: String = "DÉPLACEMENT"
			if input_mode == MODE_ATTACK:
				mode_text = "ATTAQUE"
			elif input_mode == MODE_SKILL:
				mode_text = "COMPÉTENCE"
			var extra_text: String = ""
			var hovered_actor: SporeUnitActor3D = actors_by_cell.get(hovered_cell, null) as SporeUnitActor3D
			if input_mode == MODE_ATTACK and hovered_actor != null and hovered_actor.team != active_actor.team:
				var details: Dictionary = _attack_damage_details(active_actor, hovered_actor)
				var arc: String = String(details.get("arc", "front"))
				extra_text = " • %s • dégâts %d • HIT %d%%" % [_arc_display_name(arc), int(details.get("damage", 0)), int(details.get("hit_chance", 0))]
				if int(details.get("cover_reduction", 0)) > 0:
					extra_text += " • couvert -%d" % int(details.get("cover_reduction", 0))
				if int(details.get("height_bonus", 0)) > 0:
					extra_text += " • hauteur +%d" % int(details.get("height_bonus", 0))
				var interceptor: SporeUnitActor3D = _find_interceptor(active_actor, hovered_actor)
				if interceptor != null:
					extra_text += " • intercepté par %s" % interceptor.display_name
			elif input_mode == MODE_SKILL and not selected_skill_id.is_empty():
				var skill: Resource = SkillCatalog.definition(selected_skill_id)
				if skill != null:
					var affected_count: int = _skill_preview_actor_count(active_actor, skill, hovered_cell) if skill_target_cells.has(hovered_cell) else 0
					var cast_ticks: int = int(skill.get("cast_time_ticks"))
					extra_text = " • %s • zone %d • unités affectées %d%s" % [String(skill.get("display_name")), skill_preview_cells.size(), affected_count, " • CAST %d" % cast_ticks if cast_ticks > 0 else ""]
			var statuses_text: String = active_actor.status_display_text()
			var status_suffix: String = "" if statuses_text.is_empty() else " • " + statuses_text
			var reaction_suffix: String = ""
			if active_actor.reaction_type != "none":
				var reaction_state: String = "prête" if active_actor.reaction_available() else "utilisée"
				reaction_suffix = " • R:%s %s" % [active_actor.reaction_type, reaction_state]
			var cast_suffix: String = ""
			if active_actor.is_casting():
				cast_suffix = " • CAST %s %dt" % [SkillCatalog.display_name(String(active_actor.casting.get("skill_id", ""))), maxi(0, int(active_actor.casting.get("remaining_ticks", 0)))]
			_info_label.text = "%s • HP %d/%d • MP %d/%d • CT %d • VIT %d • PRÉC %+d • ESQ %+d • face %s • %s%s%s%s\nCase : %s%s" % [active_actor.display_name, active_actor.hp, active_actor.max_hp, active_actor.focus, active_actor.max_focus, active_actor.ct, active_actor.effective_speed(), active_actor.effective_accuracy(), active_actor.effective_evasion(), active_actor.facing_name(), mode_text, reaction_suffix, status_suffix, cast_suffix, cell_text, extra_text]
		else:
			_info_label.text = "Case survolée : %s" % cell_text
	_help_label.text = "Boucle FFT : 1 Move + 1 Act dans l’ordre voulu • F choisit l’orientation • Espace = Wait/Fin • Vert déplacement • Rouge attaque • Violet skill • Entrée confirmer • Échap annuler • Q/E caméra • molette zoom • C recentrer • R recommencer"
	_refresh_timeline_ui()
	_refresh_unit_card_ui()
	_update_skill_buttons()
	if not pending_action.is_empty():
		_update_pending_preview_panel()
	if _move_button != null and active_actor != null:
		_move_button.disabled = not _player_can_input() or active_actor.moved_this_activation or active_actor.status_prevents_movement()
		_attack_button.disabled = not _player_can_input() or active_actor.acted_this_activation or active_actor.status_prevents_action()
		_end_button.disabled = not _player_can_input()
		if _face_button != null:
			_face_button.disabled = not _player_can_input()
		_move_button.button_pressed = input_mode == MODE_MOVE
		_attack_button.button_pressed = input_mode == MODE_ATTACK
	if _log_label != null:
		_log_label.text = _recent_log_text(5)


func _predict_timeline_3d(limit: int = 5) -> Array[SporeUnitActor3D]:
	var result: Array[SporeUnitActor3D] = []
	var states: Array[Dictionary] = []
	for actor: SporeUnitActor3D in turn_order:
		if actor == null or not actor.alive:
			continue
		states.append({
			"actor": actor,
			"ct": actor.ct,
			"speed": actor.effective_speed(),
			"casting": actor.is_casting(),
			"cast_ticks": maxi(0, int(actor.casting.get("remaining_ticks", 0))) if actor.is_casting() else 0,
		})
	if active_actor != null and active_actor.alive:
		result.append(active_actor)
		for state: Dictionary in states:
			if state["actor"] == active_actor:
				state["ct"] = CombatMechanics.action_end_ct(int(state["ct"]), true, true)
				break
	for _guard: int in range(64):
		if result.size() >= limit or states.is_empty():
			break
		var best_ticks: int = 999999
		for state: Dictionary in states:
			if bool(state["casting"]):
				best_ticks = mini(best_ticks, int(state["cast_ticks"]))
			else:
				best_ticks = mini(best_ticks, CombatMechanics.ticks_until_ready(int(state["ct"]), int(state["speed"])))
		if best_ticks == 999999:
			break
		for state: Dictionary in states:
			state["ct"] = mini(199, int(state["ct"]) + int(state["speed"]) * best_ticks)
			if bool(state["casting"]):
				state["cast_ticks"] = maxi(0, int(state["cast_ticks"]) - best_ticks)
				if int(state["cast_ticks"]) <= 0:
					state["casting"] = false
		var ready: Array[Dictionary] = []
		for state: Dictionary in states:
			if not bool(state["casting"]) and int(state["ct"]) >= CombatMechanics.CT_THRESHOLD:
				ready.append(state)
		if ready.is_empty():
			continue
		ready.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
			if int(a["ct"]) != int(b["ct"]):
				return int(a["ct"]) > int(b["ct"])
			if int(a["speed"]) != int(b["speed"]):
				return int(a["speed"]) > int(b["speed"])
			var aa: SporeUnitActor3D = a["actor"] as SporeUnitActor3D
			var bb: SporeUnitActor3D = b["actor"] as SporeUnitActor3D
			if aa.team != bb.team:
				return aa.team == "player"
			return aa.display_name < bb.display_name
		)
		var chosen: Dictionary = ready[0]
		result.append(chosen["actor"] as SporeUnitActor3D)
		chosen["ct"] = CombatMechanics.action_end_ct(int(chosen["ct"]), true, true)
	return result


func _refresh_timeline_ui() -> void:
	if _timeline_bar == null:
		return
	var signature_parts: PackedStringArray = PackedStringArray([str(round_number), str(battle_clock_ticks)])
	for unit: SporeUnitActor3D in turn_order:
		if unit != null:
			signature_parts.append("%s:%s:%d:%d:%d" % [unit.unit_id, "1" if unit.alive else "0", unit.ct, unit.effective_speed(), int(unit.casting.get("remaining_ticks", 0)) if unit.is_casting() else -1])
	var signature: String = "|".join(signature_parts)
	if signature == _timeline_signature:
		return
	_timeline_signature = signature
	for child: Node in _timeline_bar.get_children():
		child.free()
	var predicted: Array[SporeUnitActor3D] = _predict_timeline_3d(5)
	for actor: SporeUnitActor3D in predicted:
		if actor == null or not actor.alive:
			continue
		var card: Button = Button.new()
		card.custom_minimum_size = Vector2(44.0, 48.0)
		card.alignment = HORIZONTAL_ALIGNMENT_CENTER
		card.focus_mode = Control.FOCUS_NONE
		card.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_theme_font_size_override("font_size", 9)
		var timing_text: String = "C%d" % int(actor.casting.get("remaining_ticks", 0)) if actor.is_casting() else "%d/%d" % [actor.ct, actor.effective_speed()]
		card.text = "%s\n%s" % [actor.display_name.substr(0, mini(3, actor.display_name.length())).to_upper(), timing_text]
		card.tooltip_text = "%s • CT %d • VIT %d%s" % [actor.display_name, actor.ct, actor.effective_speed(), " • CAST" if actor.is_casting() else ""]
		var card_style: StyleBoxFlat = StyleBoxFlat.new()
		card_style.bg_color = Color(0.16, 0.42, 0.62, 0.92) if actor.team == "player" else Color(0.60, 0.24, 0.22, 0.92)
		card_style.corner_radius_top_left = 7
		card_style.corner_radius_top_right = 7
		card_style.corner_radius_bottom_left = 7
		card_style.corner_radius_bottom_right = 7
		if actor == active_actor:
			card_style.border_width_left = 2
			card_style.border_width_top = 2
			card_style.border_width_right = 2
			card_style.border_width_bottom = 2
			card_style.border_color = Color(1.0, 0.82, 0.40, 1.0)
		card.add_theme_stylebox_override("normal", card_style)
		card.add_theme_stylebox_override("hover", card_style)
		card.add_theme_stylebox_override("pressed", card_style)
		_timeline_bar.add_child(card)


func _unit_card_actor() -> SporeUnitActor3D:
	var hovered_actor: SporeUnitActor3D = actors_by_cell.get(hovered_cell, null) as SporeUnitActor3D
	if hovered_actor != null and hovered_actor.alive:
		return hovered_actor
	if selected_actor != null and selected_actor.alive:
		return selected_actor
	return active_actor if active_actor != null and active_actor.alive else null


func _refresh_unit_card_ui() -> void:
	if _unit_card_panel == null or _unit_card_title == null or _unit_card_body == null:
		return
	var actor: SporeUnitActor3D = _unit_card_actor()
	_unit_card_panel.visible = actor != null
	if actor == null:
		return
	_unit_card_title.text = "%s  •  %s" % [actor.display_name, "ALLIÉ" if actor.team == "player" else "ENNEMI"]
	if _unit_portrait != null and actor != _unit_card_last_actor:
		_unit_portrait.texture = actor.portrait_texture()
	_unit_card_last_actor = actor
	if _unit_hp_bar != null:
		_unit_hp_bar.max_value = maxi(1, actor.max_hp)
		_unit_hp_bar.value = actor.hp
		_unit_hp_bar.tooltip_text = "HP %d/%d" % [actor.hp, actor.max_hp]
	if _unit_focus_bar != null:
		_unit_focus_bar.max_value = maxi(1, actor.max_focus)
		_unit_focus_bar.value = actor.focus
		_unit_focus_bar.tooltip_text = "MP %d/%d" % [actor.focus, actor.max_focus]
	var primary_name: String = _skill_display_name(actor.primary_skill)
	var secondary_name: String = _skill_display_name(actor.secondary_skill)
	var status_text: String = actor.status_display_text()
	if status_text.is_empty():
		status_text = "Aucun statut"
	var reaction_text: String = "Aucune" if actor.reaction_type == "none" else actor.reaction_type
	var ability_text: String = "R:%s • S:%s • M:%s" % [reaction_text, actor.support_ability, actor.movement_ability]
	var casting_text: String = ""
	if actor.is_casting():
		casting_text = "\nCAST %s • %dt" % [SkillCatalog.display_name(String(actor.casting.get("skill_id", ""))), maxi(0, int(actor.casting.get("remaining_ticks", 0)))]
	_unit_card_body.text = "HP %d/%d   MP %d/%d\nPUI.P %d   PUI.M %d   DEF.P %d   DEF.M %d\nMOV %d   RNG %d-%d   VIT %d   CT %d\nPRÉC %+d   ESQ %+d • %s\n%s\nFace %s\nI. %s\nII. %s\n%s%s" % [actor.hp, actor.max_hp, actor.focus, actor.max_focus, actor.effective_physical_power(), actor.effective_magic_power(), actor.effective_physical_defense(), actor.effective_magic_defense(), actor.effective_move_range(), actor.attack_min_range, actor.attack_range, actor.effective_speed(), actor.ct, actor.effective_accuracy(), actor.effective_evasion(), actor.weapon_family.to_upper(), ability_text, actor.facing_name(), primary_name, secondary_name, status_text, casting_text]


func _skill_display_name(skill_id: String) -> String:
	if skill_id.is_empty():
		return "—"
	var skill: Resource = SkillCatalog.definition(skill_id)
	return String(skill.get("display_name")) if skill != null else skill_id


func _update_skill_buttons() -> void:
	if _primary_skill_button == null or _secondary_skill_button == null:
		return
	if active_actor == null:
		_primary_skill_button.text = "SKILL I [1]"
		_secondary_skill_button.text = "SKILL II [2]"
		_primary_skill_button.disabled = true
		_secondary_skill_button.disabled = true
		return
	_primary_skill_button.text = _skill_button_text(active_actor.primary_skill, "I [1]")
	_secondary_skill_button.text = _skill_button_text(active_actor.secondary_skill, "II [2]")
	_primary_skill_button.disabled = not _player_can_input() or active_actor.acted_this_activation or not active_actor.can_use_skill(active_actor.primary_skill)
	_secondary_skill_button.disabled = not _player_can_input() or active_actor.acted_this_activation or not active_actor.can_use_skill(active_actor.secondary_skill)


func _skill_button_text(skill_id: String, slot_label: String) -> String:
	if active_actor == null or skill_id.is_empty():
		return "%s —" % slot_label
	var skill: Resource = SkillCatalog.definition(skill_id)
	if skill == null:
		return "%s ?" % slot_label
	var suffix: String = " %dMP" % int(skill.get("focus_cost"))
	var cast_ticks: int = int(skill.get("cast_time_ticks"))
	if cast_ticks > 0:
		suffix += " C%d" % cast_ticks
	return "%s %s%s" % [slot_label, String(skill.get("display_name")), suffix]


func _skill_preview_actor_count(caster: SporeUnitActor3D, skill: Resource, anchor_cell: Vector2i) -> int:
	if caster == null or skill == null or map_root == null or not map_root.is_cell_valid(anchor_cell):
		return 0
	var seen: Dictionary = {}
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if not (effect_var is Resource):
				continue
			for target: SporeUnitActor3D in _skill_effect_targets(caster, effect_var as Resource, anchor_cell):
				seen[target] = true
	return seen.size()


func _recent_log_text(max_lines: int) -> String:
	var start_index: int = maxi(0, battle_log.size() - maxi(1, max_lines))
	var result: String = ""
	for index: int in range(start_index, battle_log.size()):
		if not result.is_empty():
			result += "\n"
		result += battle_log[index]
	return result


func _log(message: String) -> void:
	battle_log.append(message)
	while battle_log.size() > 24:
		battle_log.remove_at(0)
	_update_ui_text()


func _stage_attack_preview(target: SporeUnitActor3D) -> void:
	if active_actor == null or target == null or not target.alive or active_actor.acted_this_activation:
		return
	pending_action = {"type": ACTION_ATTACK, "target": target, "cell": target.cell}
	_update_pending_preview_panel()
	_rebuild_highlights()


func _stage_skill_preview(anchor_cell: Vector2i) -> void:
	if active_actor == null or selected_skill_id.is_empty() or not active_actor.can_use_skill(selected_skill_id):
		return
	if not skill_target_cells.has(anchor_cell):
		return
	pending_action = {"type": ACTION_SKILL, "skill_id": selected_skill_id, "cell": anchor_cell}
	var skill: Resource = SkillCatalog.definition(selected_skill_id)
	if skill != null:
		skill_preview_cells = _skill_area_cells(skill, anchor_cell, active_actor.cell)
	_update_pending_preview_panel()
	_rebuild_highlights()


func _confirm_pending_action() -> void:
	if pending_action.is_empty() or not _player_can_input():
		return
	var action: Dictionary = pending_action.duplicate()
	_clear_pending_action()
	var action_type: String = String(action.get("type", ""))
	if action_type == ACTION_ATTACK:
		var target: SporeUnitActor3D = action.get("target", null) as SporeUnitActor3D
		if target != null and target.alive:
			_player_attack(target)
	elif action_type == ACTION_SKILL:
		var skill_id: String = String(action.get("skill_id", ""))
		var anchor_value: Variant = action.get("cell", Vector2i(-1, -1))
		if anchor_value is Vector2i and not skill_id.is_empty():
			selected_skill_id = skill_id
			_player_use_skill(anchor_value)


func _cancel_pending_action() -> void:
	_clear_pending_action()
	_refresh_context_preview()
	_update_ui_text()


func _clear_pending_action() -> void:
	pending_action.clear()
	if _preview_panel != null:
		_preview_panel.visible = false


func _update_pending_preview_panel() -> void:
	if _preview_panel == null or _preview_title == null or _preview_body == null:
		return
	if pending_action.is_empty() or active_actor == null:
		_preview_panel.visible = false
		return
	_preview_panel.visible = true
	var action_type: String = String(pending_action.get("type", ""))
	if action_type == ACTION_ATTACK:
		var target: SporeUnitActor3D = pending_action.get("target", null) as SporeUnitActor3D
		_preview_title.text = "PRÉVISION • ATTAQUE"
		_preview_body.text = _attack_preview_text(active_actor, target)
	elif action_type == ACTION_SKILL:
		var skill_id: String = String(pending_action.get("skill_id", ""))
		var anchor_value: Variant = pending_action.get("cell", Vector2i(-1, -1))
		var anchor_cell: Vector2i = anchor_value if anchor_value is Vector2i else Vector2i(-1, -1)
		var skill: Resource = SkillCatalog.definition(skill_id)
		_preview_title.text = "PRÉVISION • %s" % (String(skill.get("display_name")) if skill != null else "COMPÉTENCE")
		_preview_body.text = _skill_preview_text(active_actor, skill, anchor_cell)
	else:
		_preview_panel.visible = false


func _attack_preview_text(attacker: SporeUnitActor3D, target: SporeUnitActor3D) -> String:
	if attacker == null or target == null:
		return "Cible invalide."
	var details: Dictionary = _attack_damage_details(attacker, target)
	var base_damage: int = int(details.get("damage", 0))
	var recipient: SporeUnitActor3D = target
	var final_damage: int = base_damage
	var interceptor: SporeUnitActor3D = _find_interceptor(attacker, target)
	var reaction_line: String = "Aucune réaction prévue"
	if interceptor != null:
		recipient = interceptor
		final_damage -= target.status_modifier("incoming_damage_delta")
		final_damage += interceptor.status_modifier("incoming_damage_delta")
		var preview_damage_type: String = String(details.get("damage_type", attacker.basic_attack_damage_type))
		final_damage += target.effective_defense_for_damage_type(preview_damage_type) - interceptor.effective_defense_for_damage_type(preview_damage_type)
		final_damage = maxi(1, final_damage - intercept_damage_reduction)
		reaction_line = "INTERCEPTION → %s reçoit le coup" % interceptor.display_name
	else:
		var counter_distance: int = _cell_distance(target.cell, attacker.cell)
		var counter_max: int = mini(target.reaction_range, maxi(1, target.attack_range + target.status_modifier("range_delta")))
		if target.reaction_type == "counter" and target.reaction_available() and CombatMechanics.range_allowed(counter_distance, target.attack_min_range, counter_max) and _has_line_of_sight(target.cell, attacker.cell):
			var counter_raw: int = target.effective_basic_attack_power() + target.status_modifier("outgoing_damage_delta") + attacker.status_modifier("incoming_damage_delta") + target.reaction_damage_bonus
			var counter_damage: int = CombatMechanics.damage_after_defense(counter_raw, attacker.effective_defense_for_damage_type(target.basic_attack_damage_type), 1)
			counter_damage = maxi(0, counter_damage - attacker.flat_damage_reduction)
			var attacker_after_counter: int = maxi(0, attacker.hp - counter_damage)
			reaction_line = "CONTRE probable → %d dégâts • vos PV %d→%d%s" % [counter_damage, attacker.hp, attacker_after_counter, " K.O." if attacker_after_counter <= 0 else ""]
	final_damage = maxi(0, final_damage - recipient.flat_damage_reduction)
	var recipient_after: int = maxi(0, recipient.hp - final_damage)
	var lines: PackedStringArray = PackedStringArray()
	lines.append("%s  →  %s" % [attacker.display_name, target.display_name])
	lines.append("Dégâts prévus : %d   •   HIT %d%%   •   %s" % [final_damage, int(details.get("hit_chance", 0)), _arc_display_name(String(details.get("arc", "front")))])
	lines.append("PV %s : %d → %d%s" % [recipient.display_name, recipient.hp, recipient_after, "  • K.O." if recipient_after <= 0 else ""])
	var modifiers: PackedStringArray = PackedStringArray()
	if int(details.get("height_bonus", 0)) > 0:
		modifiers.append("hauteur +%d" % int(details.get("height_bonus", 0)))
	if int(details.get("positional_bonus", 0)) > 0:
		modifiers.append("position +%d" % int(details.get("positional_bonus", 0)))
	if int(details.get("cover_reduction", 0)) > 0:
		modifiers.append("couvert -%d" % int(details.get("cover_reduction", 0)))
	if interceptor != null:
		modifiers.append("interception -%d" % intercept_damage_reduction)
	if recipient.flat_damage_reduction > 0:
		modifiers.append("armure -%d" % recipient.flat_damage_reduction)
	if recipient.shield_block_chance > 0 and recipient.shield_block_reduction > 0:
		modifiers.append("bloc %d%% -%d" % [recipient.shield_block_chance, recipient.shield_block_reduction])
	lines.append("Modificateurs : %s" % (", ".join(modifiers) if not modifiers.is_empty() else "aucun"))
	lines.append("Réaction : %s" % reaction_line)
	return "\n".join(lines)


func _skill_preview_text(caster: SporeUnitActor3D, skill: Resource, anchor_cell: Vector2i) -> String:
	if caster == null or skill == null or map_root == null or not map_root.is_cell_valid(anchor_cell):
		return "Cible de compétence invalide."
	var lines: PackedStringArray = PackedStringArray()
	var cast_ticks: int = int(skill.get("cast_time_ticks"))
	var timing_suffix: String = " • CAST %d" % cast_ticks if cast_ticks > 0 else " • instantané"
	var accuracy_suffix: String = " • précision %d" % int(skill.get("accuracy")) if bool(skill.get("uses_accuracy")) else " • garanti"
	lines.append("%s • coût %d MP%s%s" % [String(skill.get("display_name")), int(skill.get("focus_cost")), timing_suffix, accuracy_suffix])
	lines.append("Point ciblé : %d,%d h%d • zone %d case(s)" % [anchor_cell.x, anchor_cell.y, map_root.elevation_at(anchor_cell), _skill_area_cells(skill, anchor_cell, caster.cell).size()])
	var previews: Dictionary = _skill_target_previews(caster, skill, anchor_cell)
	var ordered_targets: Array = previews.keys()
	ordered_targets.sort_custom(func(a: Variant, b: Variant) -> bool: return String((a as SporeUnitActor3D).display_name) < String((b as SporeUnitActor3D).display_name))
	if ordered_targets.is_empty():
		lines.append("Aucune unité directement affectée.")
	for target_var: Variant in ordered_targets:
		var target: SporeUnitActor3D = target_var as SporeUnitActor3D
		var data: Dictionary = previews[target]
		var pieces: PackedStringArray = PackedStringArray()
		var damage: int = int(data.get("damage", 0))
		var heal_value: int = int(data.get("heal", 0))
		if target.team != caster.team and bool(skill.get("uses_accuracy")):
			pieces.append("HIT %d%%" % int(data.get("hit_chance", 100)))
		var recipient: SporeUnitActor3D = data.get("recipient", target) as SporeUnitActor3D
		if recipient == null:
			recipient = target
		if damage > 0:
			var after_damage: int = maxi(0, recipient.hp - damage)
			var recipient_prefix: String = "%s: " % recipient.display_name if recipient != target else ""
			pieces.append("%s-%d PV (%d→%d%s)" % [recipient_prefix, damage, recipient.hp, after_damage, " K.O." if after_damage <= 0 else ""])
		var revive_value: int = int(data.get("revive", 0))
		if revive_value > 0 and target.downed:
			pieces.append("RÉANIMATION → %d PV" % revive_value)
		if heal_value > 0:
			var preview_start_hp: int = revive_value if target.downed and revive_value > 0 else target.hp
			var healed_after: int = mini(target.max_hp, preview_start_hp + heal_value)
			pieces.append("+%d PV (%d→%d)" % [mini(heal_value, target.max_hp - preview_start_hp), preview_start_hp, healed_after])
		var statuses_value: Variant = data.get("statuses", PackedStringArray())
		if statuses_value is PackedStringArray and not (statuses_value as PackedStringArray).is_empty():
			pieces.append("statut: %s" % ", ".join(statuses_value))
		if bool(data.get("guard", false)):
			pieces.append("Garde")
		if bool(data.get("reaction", false)):
			pieces.append("réaction +1")
		var focus_delta: int = int(data.get("focus", 0))
		if focus_delta != 0:
			pieces.append("%+d MP" % focus_delta)
		var displacement: String = String(data.get("displacement", ""))
		if not displacement.is_empty():
			pieces.append(displacement)
		var reaction_note: String = String(data.get("reaction_note", ""))
		if not reaction_note.is_empty():
			pieces.append(reaction_note)
		lines.append("• %s [%s] : %s" % [target.display_name, "allié" if target.team == caster.team else "ennemi", ", ".join(pieces) if not pieces.is_empty() else "affecté"])
	var zone_descriptions: PackedStringArray = _skill_zone_preview_descriptions(skill)
	for description: String in zone_descriptions:
		lines.append("• %s" % description)
	return "\n".join(lines)


func _skill_target_previews(caster: SporeUnitActor3D, skill: Resource, anchor_cell: Vector2i) -> Dictionary:
	var result: Dictionary = {}
	var raw_effects: Variant = skill.get("effects")
	if not (raw_effects is Array):
		return result
	for effect_var: Variant in raw_effects:
		if not (effect_var is Resource):
			continue
		var effect: Resource = effect_var as Resource
		var effect_type: String = String(effect.get("effect_type"))
		if effect_type == "zone":
			continue
		for target: SporeUnitActor3D in _skill_effect_targets(caster, effect, anchor_cell):
			var data: Dictionary = result.get(target, {"damage": 0, "heal": 0, "revive": 0, "statuses": PackedStringArray(), "guard": false, "reaction": false, "focus": 0, "displacement": "", "reaction_note": "", "recipient": target, "hit_chance": 100})
			if target.team != caster.team and bool(skill.get("uses_accuracy")):
				var preview_hit: Dictionary = _hit_profile_3d(caster, target, int(skill.get("accuracy")), _skill_has_tag(skill, "ignore_cover"))
				data["hit_chance"] = int(preview_hit["chance"])
			var amount: int = int(effect.get("amount"))
			match effect_type:
				"revive": data["revive"] = CombatMechanics.revive_hp(target.max_hp, caster.revive_hp_bonus + maxi(0, amount))
				"damage":
					var damage: int = amount
					if bool(effect.get("use_attack_stat")):
						damage += caster.effective_physical_power() if String(effect.get("damage_type")) == "physical" else caster.effective_magic_power()
					damage += caster.status_modifier("outgoing_damage_delta") + target.status_modifier("incoming_damage_delta")
					if map_root.elevation_at(caster.cell) > map_root.elevation_at(target.cell):
						damage += 1
					if _cell_distance(caster.cell, target.cell) > 1 and not _skill_has_tag(skill, "ignore_cover") and _cover_protects_from(caster.cell, target.cell):
						damage -= ranged_cover_reduction
					var preview_damage_type: String = String(effect.get("damage_type"))
					var preview_defense: int = target.effective_physical_defense() if preview_damage_type == "physical" else target.effective_magic_defense()
					var predicted_damage: int = CombatMechanics.damage_after_defense(damage, preview_defense, 1)
					var single_target: bool = int(effect.get("radius")) <= 0 and String(effect.get("target_scope")) == "target"
					if single_target and target.team != caster.team:
						var interceptor: SporeUnitActor3D = _find_interceptor(caster, target)
						if interceptor != null:
							predicted_damage -= target.status_modifier("incoming_damage_delta")
							predicted_damage += interceptor.status_modifier("incoming_damage_delta")
							predicted_damage += target.effective_defense_for_damage_type(preview_damage_type) - interceptor.effective_defense_for_damage_type(preview_damage_type)
							predicted_damage = maxi(1, predicted_damage - intercept_damage_reduction)
							data["recipient"] = interceptor
							data["reaction_note"] = "interception probable par %s" % interceptor.display_name
						elif target.reaction_type == "counter" and target.reaction_available():
							data["reaction_note"] = "contre-attaque possible"
					var preview_recipient: SporeUnitActor3D = data.get("recipient", target) as SporeUnitActor3D
					if preview_recipient != null:
						predicted_damage = maxi(0, predicted_damage - preview_recipient.flat_damage_reduction)
					data["damage"] = int(data.get("damage", 0)) + predicted_damage
				"heal": data["heal"] = int(data.get("heal", 0)) + maxi(0, amount)
				"status":
					var status_id: String = String(effect.get("status_id"))
					var status: Resource = StatusCatalog.definition(status_id)
					var status_name: String = String(status.get("display_name")) if status != null else status_id
					var status_names: PackedStringArray = data.get("statuses", PackedStringArray())
					if not status_name.is_empty() and not status_names.has(status_name):
						status_names.append(status_name)
					data["statuses"] = status_names
				"guard": data["guard"] = true
				"reaction": data["reaction"] = true
				"focus": data["focus"] = int(data.get("focus", 0)) + amount
				"push": data["displacement"] = "poussée %d" % maxi(1, absi(amount))
				"pull": data["displacement"] = "traction %d" % maxi(1, absi(amount))
			result[target] = data
	return result


func _skill_zone_preview_descriptions(skill: Resource) -> PackedStringArray:
	var result: PackedStringArray = PackedStringArray()
	if skill == null:
		return result
	var raw_effects: Variant = skill.get("effects")
	if not (raw_effects is Array):
		return result
	for effect_var: Variant in raw_effects:
		if not (effect_var is Resource):
			continue
		var effect: Resource = effect_var as Resource
		if String(effect.get("effect_type")) != "zone":
			continue
		var tick_type: String = String(effect.get("zone_tick_type"))
		var amount: int = int(effect.get("amount"))
		var detail: String = "%s %+d" % [tick_type, amount]
		if tick_type == "status":
			var status_id: String = String(effect.get("status_id"))
			var status: Resource = StatusCatalog.definition(status_id)
			detail = "statut %s" % (String(status.get("display_name")) if status != null else status_id)
		result.append("Zone persistante : %s • %s • %d round(s)" % [detail, String(effect.get("zone_tick_phase")), int(effect.get("zone_duration_rounds"))])
	return result


func _screen_to_cell(screen_position: Vector2) -> Vector2i:
	if map_root == null or _camera == null:
		return Vector2i(-1, -1)
	var best_cell: Vector2i = Vector2i(-1, -1)
	var best_distance_sq: float = INF
	for y: int in range(map_root.grid_height):
		for x: int in range(map_root.grid_width):
			var cell_value: Vector2i = Vector2i(x, y)
			var world_position: Vector3 = map_root.to_global(map_root.cell_top_local(cell_value) + Vector3(0.0, 0.04, 0.0))
			if _camera.is_position_behind(world_position):
				continue
			var projected: Vector2 = _camera.unproject_position(world_position)
			var distance_sq: float = projected.distance_squared_to(screen_position)
			if distance_sq < best_distance_sq:
				best_distance_sq = distance_sq
				best_cell = cell_value
	return best_cell if best_distance_sq <= 3600.0 else Vector2i(-1, -1)



func _play_action_vfx_to_impact(
	vfx_id: String,
	source_world: Vector3,
	target_world: Vector3,
	follow_projectile: bool,
	tracked_target: Node3D = null,
	tracked_offset: Vector3 = Vector3.ZERO,
	kind_override: String = ""
) -> void:
	if not action_vfx_enabled:
		await get_tree().create_timer(0.085).timeout
		return
	var vfx: SporeActionVfx3D = _spawn_action_vfx(vfx_id, source_world, target_world, follow_projectile, tracked_target, tracked_offset, kind_override)
	if vfx == null:
		await get_tree().create_timer(0.085).timeout
		return
	await vfx.impact


func _spawn_action_vfx(
	vfx_id: String,
	source_world: Vector3,
	target_world: Vector3,
	follow_projectile: bool,
	tracked_target: Node3D = null,
	tracked_offset: Vector3 = Vector3.ZERO,
	kind_override: String = ""
) -> SporeActionVfx3D:
	if not action_vfx_enabled or _vfx_holder == null:
		return null
	var definition: Resource = VfxCatalog.definition(vfx_id)
	if definition == null:
		definition = VfxCatalog.definition("default_hit")
	if definition == null:
		return null
	var vfx: SporeActionVfx3D = ActionVfxScript.new() as SporeActionVfx3D
	if vfx == null:
		return null
	_vfx_holder.add_child(vfx)
	vfx.configure(definition, source_world, target_world, kind_override, tracked_target, tracked_offset)
	vfx.finished.connect(_on_action_vfx_finished.bind(vfx))
	var effective_kind: String = kind_override if not kind_override.is_empty() else String(definition.get("kind"))
	if follow_projectile and effective_kind == "projectile" and projectile_camera_follow:
		_projectile_follow_vfx = vfx
	vfx.call_deferred("start")
	return vfx


func _play_skill_area_impacts(skill: Resource, caster: SporeUnitActor3D, anchor_cell: Vector2i) -> void:
	if not action_vfx_enabled or not aoe_cell_impacts_enabled or skill == null or caster == null or map_root == null:
		return
	var cells_by_key: Dictionary = {}
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if not (effect_var is Resource):
				continue
			var effect: Resource = effect_var as Resource
			var radius: int = maxi(0, int(effect.get("radius")))
			var shape: String = String(effect.get("area_shape"))
			if radius <= 0 and shape == "single":
				continue
			var effect_cells: Array[Vector2i] = _effect_area_cells(effect, anchor_cell, caster.cell)
			for cell_value: Vector2i in effect_cells:
				if map_root.is_cell_valid(cell_value):
					cells_by_key[cell_value] = true
	if cells_by_key.size() <= 1:
		return
	var ordered_cells: Array[Vector2i] = []
	for cell_key: Variant in cells_by_key.keys():
		if cell_key is Vector2i:
			ordered_cells.append(cell_key)
	ordered_cells.sort_custom(func(a: Vector2i, b: Vector2i) -> bool:
		return _cell_distance(caster.cell, a) < _cell_distance(caster.cell, b)
	)
	var vfx_id: String = String(skill.get("vfx_id"))
	for cell_value: Vector2i in ordered_cells:
		var world_position: Vector3 = map_root.to_global(map_root.cell_top_local(cell_value) + Vector3(0.0, 0.14, 0.0))
		_spawn_action_vfx(vfx_id, world_position, world_position, false, null, Vector3.ZERO, "burst")
		if aoe_cell_impact_stagger > 0.0:
			await get_tree().create_timer(aoe_cell_impact_stagger).timeout


func _on_action_vfx_finished(vfx: SporeActionVfx3D) -> void:
	if _projectile_follow_vfx == vfx:
		_projectile_follow_vfx = null


func _position_camera() -> void:
	if _camera_rig == null or _camera == null or _light == null:
		return
	if not _camera_initialized:
		_camera_current_angle = camera_angle_degrees
		_camera_target_angle = camera_angle_degrees
		_camera_current_distance = camera_distance
		_camera_target_distance = camera_distance
		_camera_focus_current = Vector3.ZERO
		_camera_focus_target = Vector3.ZERO
		_camera_initialized = true
	_apply_camera_transform()


func _apply_camera_transform() -> void:
	if _camera_rig == null or _camera == null or _light == null:
		return
	var shake_offset: Vector3 = Vector3.ZERO
	if _camera_shake_strength > 0.0001:
		shake_offset.x = sin(_presentation_time * 79.0) * _camera_shake_strength
		shake_offset.z = cos(_presentation_time * 67.0) * _camera_shake_strength * 0.65
	_camera_rig.position = _camera_focus_current + shake_offset
	_camera_rig.rotation_degrees = Vector3(0.0, _camera_current_angle, 0.0)
	_camera.position = Vector3(0.0, camera_height, _camera_current_distance)
	_camera.look_at(_camera_focus_current, Vector3.UP)
	_camera.size = clampf(_camera_current_distance * 0.84, zoom_min, zoom_max)
	_light.rotation_degrees = Vector3(-48.0, 28.0, 0.0)


func _update_action_camera(delta: float) -> void:
	_action_camera_timer = maxf(0.0, _action_camera_timer - delta)
	_impact_zoom_timer = maxf(0.0, _impact_zoom_timer - delta)
	_camera_shake_strength = maxf(0.0, _camera_shake_strength - delta * 0.72)


func _update_camera_smoothing(delta: float) -> void:
	if not _camera_initialized:
		return
	var following_projectile: bool = projectile_camera_follow and _projectile_follow_vfx != null and is_instance_valid(_projectile_follow_vfx)
	if following_projectile:
		var projectile_position: Vector3 = _projectile_follow_vfx.follow_position
		_camera_focus_target = Vector3(projectile_position.x, 0.0, projectile_position.z)
	elif _action_camera_timer > 0.0:
		_camera_focus_target = _action_camera_focus
	elif camera_follow_active and active_actor != null and active_actor.alive:
		_camera_focus_target = Vector3(active_actor.position.x, 0.0, active_actor.position.z)
	var effective_distance: float = _camera_target_distance
	if following_projectile:
		effective_distance = maxf(6.0, effective_distance - projectile_camera_zoom_in)
	elif _action_camera_timer > 0.0:
		effective_distance = maxf(6.0, effective_distance - _action_camera_zoom)
	if _impact_zoom_timer > 0.0:
		effective_distance = maxf(6.0, effective_distance - 0.55)
	var weight: float = 1.0 - exp(-camera_smoothing * maxf(0.0, delta))
	_camera_current_angle = lerpf(_camera_current_angle, _camera_target_angle, weight)
	_camera_current_distance = lerpf(_camera_current_distance, effective_distance, weight)
	_camera_focus_current = _camera_focus_current.lerp(_camera_focus_target, weight)
	_apply_camera_transform()


func _begin_action_camera(source_global: Vector3, target_global: Vector3, duration: float = -1.0, zoom_in: float = -1.0) -> void:
	if not action_camera_enabled:
		return
	var source_local: Vector3 = to_local(source_global)
	var target_local: Vector3 = to_local(target_global)
	var midpoint: Vector3 = (source_local + target_local) * 0.5
	_action_camera_focus = Vector3(midpoint.x, 0.0, midpoint.z)
	_action_camera_timer = action_camera_duration if duration < 0.0 else duration
	_action_camera_zoom = action_camera_zoom_in if zoom_in < 0.0 else zoom_in


func _camera_impact(strength: float = -1.0) -> void:
	var resolved_strength: float = impact_shake_strength if strength < 0.0 else strength
	_camera_shake_strength = maxf(_camera_shake_strength, resolved_strength)
	_impact_zoom_timer = 0.16


func _focus_camera_on_active(immediate: bool = false) -> void:
	if active_actor == null:
		_camera_focus_target = Vector3.ZERO
	else:
		_camera_focus_target = Vector3(active_actor.position.x, 0.0, active_actor.position.z)
	if immediate:
		_camera_focus_current = _camera_focus_target
		_apply_camera_transform()


func _rotate_camera_90(direction: float = 1.0) -> void:
	_camera_target_angle += 90.0 * direction
	camera_angle_degrees = _camera_target_angle


func _set_camera_distance(value: float) -> void:
	_camera_target_distance = clampf(value, 6.0, 22.0)
	camera_distance = _camera_target_distance


func _descendants(node: Node) -> Array[Node]:
	var result: Array[Node] = []
	for child: Node in node.get_children():
		result.append(child)
		var nested: Array[Node] = _descendants(child)
		for entry: Node in nested:
			result.append(entry)
	return result
