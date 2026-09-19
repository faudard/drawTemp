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
const CinematicPlayerScene = preload("res://scenes/ui/cinematic_player_3d.tscn")

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
@export var camera_follow_active: bool = false
@export_range(1.0, 16.0, 0.5) var camera_pan_speed: float = 5.5
@export_range(1.0, 20.0, 0.5) var camera_smoothing: float = 4.5
@export var action_camera_enabled: bool = true
@export_range(0.15, 2.0, 0.05) var action_camera_duration: float = 0.95
@export_range(0.0, 4.0, 0.1) var action_camera_zoom_in: float = 0.85
@export_range(0.0, 0.35, 0.01) var impact_shake_strength: float = 0.07
@export var show_action_wheel: bool = false

@export_group("Action VFX")
@export var action_vfx_enabled: bool = true
@export var projectile_camera_follow: bool = false
@export_range(0.0, 4.0, 0.1) var projectile_camera_zoom_in: float = 0.60
@export_range(0.0, 1.0, 0.05) var vfx_impact_pause: float = 0.10
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
var mission_objective_3d: String = "eliminate"
var mission_survival_rounds_3d: int = 0
var crown_cell_3d: Vector2i = Vector2i(-9, -9)
var extraction_cells_3d: Array[Vector2i] = []
var bonus_cells_3d: Array[Vector2i] = []
var crown_carrier_id_3d: String = ""
var bonus_collected_3d: int = 0
var bonus_target_total_3d: int = 0
var interactable_states_3d: Dictionary = {}
var _objective_panel_3d: Panel = null
var _objective_title_3d: Label = null
var _objective_body_3d: Label = null
var _objective_signature_3d: String = ""
var _enemies_cleared_objective_hint_3d: bool = false
var _objective_markers_3d: Node3D = null

var _camera_rig: Node3D
var _camera: Camera3D
var _light: DirectionalLight3D
var _map_holder: Node3D
var _actor_holder: Node3D
var _highlight_holder: Node3D
var _zone_holder: Node3D
var _vfx_holder: Node3D
var _enemy_intent_root: Node3D = null
var _cursor_mesh: MeshInstance3D
var _hover_forecast_label: Label3D = null
var _threat_overlay_enabled: bool = false
var _threat_cells_cache: Dictionary = {}
var _ui_layer: CanvasLayer
var _cinematic_player_3d: SporeCinematicPlayer3D = null
var _cinematic_camera_active: bool = false
var _cinematic_camera_saved_focus: Vector3 = Vector3.ZERO
var _cinematic_camera_saved_distance: float = 12.5
var _cinematic_end_started: bool = false
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
var _action_banner_panel: Panel
var _action_banner_title: Label
var _action_banner_subtitle: Label
var _action_banner_tween: Tween
var _comic_stamp_label: Label = null
var _comic_stamp_tween: Tween = null
var _timeline_panel: Panel
var _timeline_bar: HBoxContainer
var _unit_card_panel: Panel
var _unit_card_title: Label
var _unit_card_body: Label
var _unit_portrait: TextureRect
var _unit_hp_bar: ProgressBar
var _unit_focus_bar: ProgressBar
var _unit_hp_text_label: Label
var _unit_mp_text_label: Label
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
var _hazard_cells_3d: Array[Vector2i] = []
var _mission_triggers_3d: Array[Resource] = []
var _fired_trigger_ids_3d: Dictionary = {}
var _trigger_queue_3d: Array[Resource] = []
var _mission_event_busy_3d: bool = false
var _hazard_visual_root_3d: Node3D = null
var _facing_selection_active: bool = false
var _facing_panel: Panel = null
var _battle_end_sequence_started: bool = false
var _cursor_bob: float = 0.0
var _action_camera_timer: float = 0.0
var _action_camera_focus: Vector3 = Vector3.ZERO
var _camera_return_focus: Vector3 = Vector3.ZERO
var _action_camera_zoom: float = 0.0
var _camera_shake_strength: float = 0.0
var _impact_zoom_timer: float = 0.0
var _projectile_follow_vfx: SporeActionVfx3D = null


func _ready() -> void:
	_ensure_runtime_nodes()
	_load_map()
	_setup_mission_state_3d()
	_setup_mission_events_3d()
	_focus_camera_on_map_center(true)
	_spawn_runtime_units()
	_ensure_objective_ui_3d()
	_refresh_objective_ui_3d(true)
	_build_turn_order()
	_ensure_cinematic_player_3d()
	_evaluate_mission_triggers_3d("round_start", null)
	if _mission_event_pending_3d():
		call_deferred("_start_after_initial_mission_events_3d")
	else:
		_update_ui_text()
	call_deferred("_play_mission_intro_3d")


func _unhandled_input(event: InputEvent) -> void:
	if _camera == null or map_root == null:
		return
	if battle_finished:
		if event is InputEventKey and event.pressed and (event as InputEventKey).keycode == KEY_R:
			get_tree().reload_current_scene()
		return
	if _facing_selection_active:
		if event is InputEventKey and event.pressed:
			var facing_key: Key = (event as InputEventKey).keycode
			match facing_key:
				KEY_ENTER, KEY_KP_ENTER, KEY_SPACE:
					_confirm_facing_and_end()
				KEY_ESCAPE:
					_close_facing_selector()
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
			KEY_T:
				_toggle_enemy_threat_overlay()
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
	_update_cinematic_end_flow_3d()
	_update_hazard_visuals_3d()
	_refresh_objective_ui_3d()
	_presentation_time += delta
	_update_action_camera(delta)
	_update_manual_camera_pan(delta)
	_update_camera_smoothing(delta)
	_update_cursor_animation()
	_update_cursor()
	_update_tactical_hover_forecast()
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
		# IMMERSIVE_GARDEN_LIGHTING
		_light.light_color = Color(1.0, 0.90, 0.78, 1.0)
		_light.light_energy = 1.08
		_light.shadow_enabled = true
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
	_ensure_cinematic_player_3d()


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
	# Critical: the full-screen HUD must not swallow board clicks.
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui_layer.add_child(root)

	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.018, 0.020, 0.024, 0.94)
	style.border_color = Color(0.93, 0.91, 0.84, 0.98)
	style.border_width_left = 3
	style.border_width_top = 3
	style.border_width_right = 3
	style.border_width_bottom = 3
	style.corner_radius_top_left = 3
	style.corner_radius_top_right = 3
	style.corner_radius_bottom_left = 3
	style.corner_radius_bottom_right = 3
	style.shadow_color = Color(0.0, 0.0, 0.0, 0.72)
	style.shadow_size = 7

	var panel: Panel = Panel.new()
	panel.name = "CommandPanel"
	panel.position = Vector2(14.0, 14.0)
	panel.size = Vector2(430.0, 174.0)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", style)
	root.add_child(panel)

	_turn_label = _make_label(panel, Vector2(14.0, 8.0), Vector2(402.0, 28.0), 20, Color(1.0, 0.80, 0.16, 1.0))
	_info_label = _make_label(panel, Vector2(14.0, 38.0), Vector2(402.0, 44.0), 12, Color(0.96, 0.95, 0.90, 1.0))
	_info_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	_move_button = _make_button(panel, "MOVE [M]", Vector2(14.0, 87.0), Vector2(94.0, 32.0))
	_attack_button = _make_button(panel, "ATTAQUE [A]", Vector2(114.0, 87.0), Vector2(104.0, 32.0))
	_face_button = _make_button(panel, "ORIENT. [F]", Vector2(224.0, 87.0), Vector2(82.0, 32.0))
	_face_button.tooltip_text = "Orientation : frapper de dos ou de flanc est plus efficace."
	_end_button = _make_button(panel, "FIN [ESPACE]", Vector2(312.0, 87.0), Vector2(104.0, 32.0))
	_move_button.toggle_mode = true
	_attack_button.toggle_mode = true

	_primary_skill_button = _make_button(panel, "I [1]", Vector2(14.0, 126.0), Vector2(198.0, 32.0))
	_secondary_skill_button = _make_button(panel, "II [2]", Vector2(218.0, 126.0), Vector2(198.0, 32.0))

	_move_button.pressed.connect(_on_move_mode_pressed)
	_attack_button.pressed.connect(_on_attack_mode_pressed)
	_face_button.pressed.connect(_on_face_pressed.bind(1))
	_end_button.pressed.connect(_on_end_activation_pressed)
	_primary_skill_button.pressed.connect(_on_skill_pressed.bind(1))
	_secondary_skill_button.pressed.connect(_on_skill_pressed.bind(2))

	_help_label = _make_label(panel, Vector2.ZERO, Vector2.ZERO, 10, Color.WHITE)
	_help_label.visible = false

	_timeline_panel = Panel.new()
	_timeline_panel.name = "InitiativeTimeline"
	_timeline_panel.position = Vector2(458.0, 14.0)
	_timeline_panel.size = Vector2(292.0, 82.0)
	_timeline_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_timeline_panel.add_theme_stylebox_override("panel", style)
	root.add_child(_timeline_panel)
	var timeline_title: Label = _make_label(_timeline_panel, Vector2(10.0, 6.0), Vector2(272.0, 18.0), 11, Color(0.68, 0.79, 0.87, 1.0))
	timeline_title.text = "INITIATIVE"
	timeline_title.add_theme_color_override("font_color", Color(0.98, 0.96, 0.90, 1.0))
	timeline_title.add_theme_font_size_override("font_size", 13)
	_timeline_bar = HBoxContainer.new()
	_timeline_bar.position = Vector2(10.0, 27.0)
	_timeline_bar.size = Vector2(272.0, 48.0)
	_timeline_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_timeline_bar.add_theme_constant_override("separation", 4)
	_timeline_panel.add_child(_timeline_bar)

	var log_panel: Panel = Panel.new()
	log_panel.name = "BattleLog"
	log_panel.position = Vector2(14.0, 650.0)
	log_panel.size = Vector2(420.0, 88.0)
	log_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	log_panel.add_theme_stylebox_override("panel", style)
	root.add_child(log_panel)
	_log_label = _make_label(log_panel, Vector2(12.0, 9.0), Vector2(396.0, 70.0), 11, Color(0.49, 0.87, 1.0, 1.0))
	_log_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	_preview_panel = Panel.new()
	_preview_panel.name = "CombatPreview"
	_preview_panel.position = Vector2(820.0, 14.0)
	_preview_panel.size = Vector2(420.0, 300.0)
	_preview_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_preview_panel.add_theme_stylebox_override("panel", style)
	_preview_panel.visible = false
	root.add_child(_preview_panel)
	_preview_title = _make_label(_preview_panel, Vector2(16.0, 12.0), Vector2(388.0, 28.0), 18, Color(1.0, 0.82, 0.40, 1.0))
	_preview_body = _make_label(_preview_panel, Vector2(16.0, 45.0), Vector2(388.0, 198.0), 12, Color(0.94, 0.94, 0.88, 1.0))
	_preview_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_preview_confirm_button = _make_button(_preview_panel, "CONFIRMER [ENTRÉE]", Vector2(16.0, 252.0), Vector2(220.0, 34.0))
	_preview_cancel_button = _make_button(_preview_panel, "ANNULER [ÉCHAP]", Vector2(244.0, 252.0), Vector2(160.0, 34.0))
	_preview_confirm_button.pressed.connect(_confirm_pending_action)
	_preview_cancel_button.pressed.connect(_cancel_pending_action)

	_unit_card_panel = Panel.new()
	_unit_card_panel.name = "UnitCard"
	_unit_card_panel.position = Vector2(880.0, 568.0)
	_unit_card_panel.size = Vector2(360.0, 170.0)
	_unit_card_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_unit_card_panel.add_theme_stylebox_override("panel", style)
	root.add_child(_unit_card_panel)

	_unit_portrait = TextureRect.new()
	_unit_portrait.position = Vector2(12.0, 12.0)
	_unit_portrait.size = Vector2(82.0, 104.0)
	_unit_portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_unit_portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_unit_portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_unit_card_panel.add_child(_unit_portrait)

	_unit_card_title = _make_label(_unit_card_panel, Vector2(104.0, 10.0), Vector2(244.0, 25.0), 18, Color(1.0, 0.80, 0.16, 1.0))

	_unit_hp_bar = ProgressBar.new()
	_unit_hp_bar.position = Vector2(104.0, 39.0)
	_unit_hp_bar.size = Vector2(244.0, 15.0)
	_unit_hp_bar.show_percentage = false
	_unit_hp_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_unit_hp_bar.add_theme_stylebox_override("background", _progress_style(Color(0.07, 0.08, 0.10, 0.95), 4))
	_unit_hp_bar.add_theme_stylebox_override("fill", _progress_style(Color(0.31, 0.82, 0.42, 1.0), 4))
	_unit_card_panel.add_child(_unit_hp_bar)
	_unit_hp_text_label = _make_label(
		_unit_card_panel,
		_unit_hp_bar.position,
		_unit_hp_bar.size,
		11,
		Color.WHITE
	)
	_unit_hp_text_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_unit_hp_text_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_unit_hp_text_label.mouse_filter = Control.MOUSE_FILTER_IGNORE

	_unit_focus_bar = ProgressBar.new()
	_unit_focus_bar.position = Vector2(104.0, 58.0)
	_unit_focus_bar.size = Vector2(244.0, 12.0)
	_unit_focus_bar.show_percentage = false
	_unit_focus_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_unit_focus_bar.add_theme_stylebox_override("background", _progress_style(Color(0.07, 0.08, 0.10, 0.95), 3))
	_unit_focus_bar.add_theme_stylebox_override("fill", _progress_style(Color(0.34, 0.64, 1.0, 1.0), 3))
	_unit_card_panel.add_child(_unit_focus_bar)
	_unit_mp_text_label = _make_label(
		_unit_card_panel,
		_unit_focus_bar.position,
		_unit_focus_bar.size,
		10,
		Color.WHITE
	)
	_unit_mp_text_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_unit_mp_text_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_unit_mp_text_label.mouse_filter = Control.MOUSE_FILTER_IGNORE

	_unit_card_body = _make_label(_unit_card_panel, Vector2(104.0, 76.0), Vector2(244.0, 82.0), 10, Color(0.92, 0.93, 0.88, 1.0))
	_unit_card_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	# The old floating ActionWheel duplicated commands and covered tactical cells.
	_action_wheel = null
	_action_wheel_label = null
	_wheel_move_button = null
	_wheel_attack_button = null
	_wheel_primary_button = null
	_wheel_secondary_button = null
	_wheel_face_button = null
	_wheel_end_button = null

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
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label


func _make_button(parent: Control, title: String, pos: Vector2, size_value: Vector2) -> Button:
	var button: Button = Button.new()
	button.text = title
	button.position = pos
	button.size = size_value
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", 13)
	button.add_theme_color_override("font_color", Color(0.96, 0.95, 0.90, 1.0))
	button.add_theme_color_override("font_hover_color", Color(0.06, 0.06, 0.06, 1.0))
	button.add_theme_color_override("font_pressed_color", Color(0.06, 0.06, 0.06, 1.0))
	var normal := StyleBoxFlat.new()
	normal.bg_color = Color(0.035, 0.038, 0.045, 0.96)
	normal.border_color = Color(0.88, 0.86, 0.79, 0.95)
	normal.border_width_left = 2
	normal.border_width_top = 2
	normal.border_width_right = 2
	normal.border_width_bottom = 2
	normal.corner_radius_top_left = 2
	normal.corner_radius_top_right = 2
	normal.corner_radius_bottom_left = 2
	normal.corner_radius_bottom_right = 2
	var hover := normal.duplicate() as StyleBoxFlat
	hover.bg_color = Color(1.0, 0.82, 0.18, 1.0)
	hover.border_color = Color(1.0, 0.94, 0.64, 1.0)
	var pressed := normal.duplicate() as StyleBoxFlat
	pressed.bg_color = Color(0.92, 0.18, 0.12, 1.0)
	pressed.border_color = Color(1.0, 0.86, 0.72, 1.0)
	button.add_theme_stylebox_override("normal", normal)
	button.add_theme_stylebox_override("hover", hover)
	button.add_theme_stylebox_override("pressed", pressed)
	button.add_theme_stylebox_override("focus", hover)
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


func _setup_mission_state_3d() -> void:
	mission_objective_3d = "eliminate"
	mission_survival_rounds_3d = 0
	crown_cell_3d = Vector2i(-9, -9)
	extraction_cells_3d.clear()
	bonus_cells_3d.clear()
	crown_carrier_id_3d = ""
	bonus_collected_3d = 0
	bonus_target_total_3d = 0
	interactable_states_3d.clear()
	_objective_signature_3d = ""

	var mission: Resource = MissionCatalog.definition(mission_index)
	if mission != null:
		mission_objective_3d = String(mission.get("objective"))
		mission_survival_rounds_3d = int(mission.get("survival_rounds"))

	if map_root != null:
		var environment: Dictionary = map_root.to_environment()

		var raw_crown: Variant = environment.get(
			"crown",
			Vector2i(-9, -9)
		)
		if raw_crown is Vector2i:
			crown_cell_3d = raw_crown

		var raw_extraction: Variant = environment.get("extraction", [])
		if raw_extraction is Array:
			for value: Variant in raw_extraction:
				if value is Vector2i:
					extraction_cells_3d.append(value)

		var raw_bonus: Variant = environment.get("bonus", [])
		if raw_bonus is Array:
			for value: Variant in raw_bonus:
				if value is Vector2i:
					bonus_cells_3d.append(value)

	bonus_target_total_3d = bonus_cells_3d.size()
	_setup_interactables_3d()
	_rebuild_objective_markers_3d()


func _setup_interactables_3d() -> void:
	interactable_states_3d.clear()

	var definitions: Array[Resource] = MissionCatalog.interactables(
		mission_index
	)
	for definition: Resource in definitions:
		if definition == null:
			continue

		var object_id: String = String(definition.get("id"))
		if object_id.is_empty():
			continue

		interactable_states_3d[object_id] = {
			"definition": definition,
			"active": bool(definition.get("starts_active")),
			"used": false,
		}

	_refresh_interactable_visuals_3d()


func _interactable_state_3d(object_id: String) -> Dictionary:
	var raw_state: Variant = interactable_states_3d.get(object_id, {})
	if raw_state is Dictionary:
		return raw_state as Dictionary
	return {}


func _closed_door_at_3d(cell_value: Vector2i) -> bool:
	for state_var: Variant in interactable_states_3d.values():
		if not (state_var is Dictionary):
			continue
		var state: Dictionary = state_var as Dictionary
		var definition: Resource = state.get("definition", null) as Resource
		if definition == null:
			continue
		if (
			String(definition.get("object_type")) == "door"
			and definition.get("cell") == cell_value
		):
			return not bool(state.get("active", false))
	return false


func _refresh_interactable_visuals_3d() -> void:
	if map_root == null:
		return

	for node: Node in _descendants(map_root):
		if not node.has_method("runtime_object_id"):
			continue

		var object_id: String = String(node.call("runtime_object_id"))
		var state: Dictionary = _interactable_state_3d(object_id)
		if state.is_empty():
			continue

		node.call(
			"apply_runtime_state",
			bool(state.get("active", false)),
			bool(state.get("used", false))
		)


func _handle_mission_cell_entry_3d(actor: SporeUnitActor3D) -> void:
	if actor == null or not actor.alive or actor.team != "player":
		return

	_check_crown_pickup_3d(actor)
	_check_bonus_pickup_3d(actor)
	_handle_interactable_entry_3d(actor)
	_refresh_objective_ui_3d(true)
	_rebuild_objective_markers_3d()


func _check_crown_pickup_3d(actor: SporeUnitActor3D) -> void:
	if mission_objective_3d != "crown":
		return
	if not crown_carrier_id_3d.is_empty():
		return
	if actor.cell != crown_cell_3d:
		return

	crown_carrier_id_3d = actor.unit_id
	_show_floating_text(
		actor.position + Vector3(0.0, 1.46, 0.0),
		"COURONNE !",
		Color(1.0, 0.82, 0.32, 1.0)
	)
	_log(
		"%s récupère la Couronne. "
		+ "Ramène-la maintenant dans la SORTIE."
		% actor.display_name
	)


func _check_bonus_pickup_3d(actor: SporeUnitActor3D) -> void:
	if not bonus_cells_3d.has(actor.cell):
		return

	bonus_cells_3d.erase(actor.cell)
	bonus_collected_3d += 1

	var healed: int = actor.heal(1)
	var heal_suffix: String = (
		" • +%d PV" % healed
		if healed > 0
		else ""
	)

	_show_floating_text(
		actor.position + Vector3(0.0, 1.42, 0.0),
		"VINYLE %d/%d%s"
		% [
			bonus_collected_3d,
			bonus_target_total_3d,
			heal_suffix
		],
		Color(0.82, 0.66, 1.0, 1.0)
	)

	_log(
		"%s récupère un vinyle (%d/%d)%s."
		% [
			actor.display_name,
			bonus_collected_3d,
			bonus_target_total_3d,
			heal_suffix
		]
	)


func _handle_interactable_entry_3d(actor: SporeUnitActor3D) -> void:
	for object_id_var: Variant in interactable_states_3d.keys():
		var object_id: String = String(object_id_var)
		var state: Dictionary = _interactable_state_3d(object_id)
		if state.is_empty():
			continue

		var definition: Resource = state.get("definition", null) as Resource
		if definition == null:
			continue

		var raw_cell: Variant = definition.get("cell")
		if not (raw_cell is Vector2i) or raw_cell != actor.cell:
			continue

		var object_type: String = String(definition.get("object_type"))
		match object_type:
			"switch":
				var one_shot: bool = bool(definition.get("one_shot"))
				if one_shot and bool(state.get("used", false)):
					continue

				state["used"] = true
				state["active"] = not bool(state.get("active", false))

				var linked_id: String = String(
					definition.get("linked_object_id")
				)
				if not linked_id.is_empty():
					var linked_state: Dictionary = _interactable_state_3d(
						linked_id
					)
					if not linked_state.is_empty():
						linked_state["active"] = bool(
							state.get("active", false)
						)

				_show_floating_text(
					actor.position + Vector3(0.0, 1.40, 0.0),
					"INTERRUPTEUR !",
					Color(0.42, 0.82, 1.0, 1.0)
				)
				_log(
					"%s active %s."
					% [
						actor.display_name,
						String(definition.get("display_name"))
					]
				)

			"chest":
				if bool(state.get("used", false)):
					continue
				state["used"] = true
				state["active"] = true

				var reward_type: String = String(
					definition.get("reward_type")
				)
				var reward_value: int = int(
					definition.get("reward_value")
				)
				var reward_team: String = String(
					definition.get("reward_team")
				)

				if reward_type == "focus_team":
					var recipients: Array[SporeUnitActor3D] = (
						player_actors
						if reward_team == "player"
						else enemy_actors
					)
					for recipient: SporeUnitActor3D in recipients:
						if recipient != null and recipient.alive:
							recipient.change_focus(reward_value)

				elif reward_type == "heal_team":
					var heal_recipients: Array[SporeUnitActor3D] = (
						player_actors
						if reward_team == "player"
						else enemy_actors
					)
					for recipient: SporeUnitActor3D in heal_recipients:
						if recipient != null and recipient.alive:
							recipient.heal(reward_value)

				_show_floating_text(
					actor.position + Vector3(0.0, 1.42, 0.0),
					"COFFRE !",
					Color(1.0, 0.80, 0.38, 1.0)
				)
				_log(
					"%s ouvre %s."
					% [
						actor.display_name,
						String(definition.get("display_name"))
					]
				)

	_refresh_interactable_visuals_3d()


func _living_count_3d(team_value: String) -> int:
	var count: int = 0
	var source: Array[SporeUnitActor3D] = (
		player_actors
		if team_value == "player"
		else enemy_actors
	)
	for actor: SporeUnitActor3D in source:
		if actor != null and actor.alive:
			count += 1
	return count


func _crown_carrier_3d() -> SporeUnitActor3D:
	if crown_carrier_id_3d.is_empty():
		return null

	for actor: SporeUnitActor3D in player_actors:
		if actor != null and actor.unit_id == crown_carrier_id_3d:
			return actor
	return null


func _mission_rule_matches_3d(rule: Resource) -> bool:
	if rule == null:
		return false

	var result: bool = false
	var rule_type: String = String(rule.get("rule_type"))
	var amount: int = int(rule.get("amount"))
	var unit_id: String = String(rule.get("unit_id"))

	match rule_type:
		"all_enemies_defeated":
			result = _living_count_3d("enemy") <= 0

		"all_players_defeated":
			result = _living_count_3d("player") <= 0

		"survive_rounds":
			result = round_number > maxi(1, amount)

		"crown_extracted":
			var carrier: SporeUnitActor3D = _crown_carrier_3d()
			result = (
				carrier != null
				and carrier.alive
				and extraction_cells_3d.has(carrier.cell)
			)

		"round_at_least":
			result = round_number >= maxi(1, amount)

		"bonus_collected":
			result = bonus_collected_3d >= maxi(0, amount)

		"unit_defeated":
			var defeated: SporeUnitActor3D = _actor_by_unit_id(unit_id)
			result = defeated == null or not defeated.alive

		"unit_alive":
			var living_unit: SporeUnitActor3D = _actor_by_unit_id(unit_id)
			result = living_unit != null and living_unit.alive

		"unit_on_extraction":
			var zone_unit: SporeUnitActor3D = _actor_by_unit_id(unit_id)
			result = (
				zone_unit != null
				and zone_unit.alive
				and extraction_cells_3d.has(zone_unit.cell)
			)

	if bool(rule.get("invert")):
		return not result
	return result


func _mission_rules_satisfied_3d(
	rules: Array,
	mode: String
) -> bool:
	if rules.is_empty():
		return false

	if mode == "all":
		for rule_var: Variant in rules:
			if not (rule_var is Resource):
				continue
			if not _mission_rule_matches_3d(rule_var as Resource):
				return false
		return true

	for rule_var: Variant in rules:
		if (
			rule_var is Resource
			and _mission_rule_matches_3d(rule_var as Resource)
		):
			return true
	return false


func _mission_result_3d() -> int:
	var mission: Resource = MissionCatalog.definition(mission_index)

	if mission != null:
		var raw_defeat: Variant = mission.get("defeat_rules")
		if raw_defeat is Array:
			var defeat_rules: Array = raw_defeat as Array
			if _mission_rules_satisfied_3d(
				defeat_rules,
				String(mission.get("defeat_rule_mode"))
			):
				return -1

		var raw_victory: Variant = mission.get("victory_rules")
		if raw_victory is Array:
			var victory_rules: Array = raw_victory as Array
			if _mission_rules_satisfied_3d(
				victory_rules,
				String(mission.get("victory_rule_mode"))
			):
				return 1

	if _living_count_3d("player") <= 0:
		return -1

	match mission_objective_3d:
		"crown":
			var carrier: SporeUnitActor3D = _crown_carrier_3d()
			if (
				carrier != null
				and carrier.alive
				and extraction_cells_3d.has(carrier.cell)
			):
				return 1

		"survive":
			if round_number > maxi(1, mission_survival_rounds_3d):
				return 1

		"eliminate":
			if _living_count_3d("enemy") <= 0:
				return 1

	return 0


func _ensure_objective_ui_3d() -> void:
	if _ui_layer == null:
		return

	var root: Control = _ui_layer.get_node_or_null("Root") as Control
	if root == null:
		return

	_objective_panel_3d = root.get_node_or_null(
		"MissionObjectivePanel"
	) as Panel

	if _objective_panel_3d == null:
		_objective_panel_3d = Panel.new()
		_objective_panel_3d.name = "MissionObjectivePanel"
		_objective_panel_3d.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_objective_panel_3d.set_anchors_preset(
			Control.PRESET_TOP_RIGHT
		)
		_objective_panel_3d.offset_left = -382.0
		_objective_panel_3d.offset_top = 14.0
		_objective_panel_3d.offset_right = -14.0
		_objective_panel_3d.offset_bottom = 132.0

		var style: StyleBoxFlat = StyleBoxFlat.new()
		style.bg_color = Color(0.018, 0.020, 0.024, 0.95)
		style.border_color = Color(0.93, 0.91, 0.84, 0.98)
		style.border_width_left = 3
		style.border_width_top = 3
		style.border_width_right = 3
		style.border_width_bottom = 3
		style.corner_radius_top_left = 3
		style.corner_radius_top_right = 3
		style.corner_radius_bottom_left = 3
		style.corner_radius_bottom_right = 3
		_objective_panel_3d.add_theme_stylebox_override(
			"panel",
			style
		)
		root.add_child(_objective_panel_3d)

		_objective_title_3d = Label.new()
		_objective_title_3d.position = Vector2(14.0, 9.0)
		_objective_title_3d.size = Vector2(340.0, 24.0)
		_objective_title_3d.text = "OBJECTIF"
		_objective_title_3d.add_theme_font_size_override(
			"font_size",
			15
		)
		_objective_title_3d.add_theme_color_override(
			"font_color",
			Color(1.0, 0.80, 0.16, 1.0)
		)
		_objective_title_3d.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_objective_panel_3d.add_child(_objective_title_3d)

		_objective_body_3d = Label.new()
		_objective_body_3d.position = Vector2(14.0, 35.0)
		_objective_body_3d.size = Vector2(340.0, 72.0)
		_objective_body_3d.autowrap_mode = (
			TextServer.AUTOWRAP_WORD_SMART
		)
		_objective_body_3d.add_theme_font_size_override(
			"font_size",
			12
		)
		_objective_body_3d.add_theme_color_override(
			"font_color",
			Color(0.91, 0.93, 0.88, 1.0)
		)
		_objective_body_3d.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_objective_panel_3d.add_child(_objective_body_3d)
	else:
		_objective_title_3d = _objective_panel_3d.get_child(0) as Label
		_objective_body_3d = _objective_panel_3d.get_child(1) as Label


func _objective_status_text_3d() -> String:
	var living_players: int = _living_count_3d("player")
	var living_enemies: int = _living_count_3d("enemy")

	match mission_objective_3d:
		"crown":
			if crown_carrier_id_3d.is_empty():
				return (
					"1. Récupérer la COURONNE\n"
					+ "2. La ramener à la SORTIE\n"
					+ "Vinyles : %d/%d • Alliés %d • Ennemis %d"
					% [
						bonus_collected_3d,
						bonus_target_total_3d,
						living_players,
						living_enemies
					]
				)

			var carrier: SporeUnitActor3D = _crown_carrier_3d()
			var carrier_name: String = (
				carrier.display_name
				if carrier != null
				else "?"
			)
			return (
				"✓ Couronne récupérée par %s\n"
				+ "→ Rejoins une case SORTIE\n"
				+ "Vinyles : %d/%d • Alliés %d • Ennemis %d"
				% [
					carrier_name,
					bonus_collected_3d,
					bonus_target_total_3d,
					living_players,
					living_enemies
				]
			)

		"survive":
			return (
				"Tenir jusqu'à la fin de la manche %d\n"
				+ "Manche actuelle : %d • Alliés %d • Ennemis %d"
				% [
					mission_survival_rounds_3d,
					round_number,
					living_players,
					living_enemies
				]
			)

	return (
		"Mettre tous les ennemis K.O.\n"
		+ "Alliés %d • Ennemis %d • Vinyles %d/%d"
		% [
			living_players,
			living_enemies,
			bonus_collected_3d,
			bonus_target_total_3d
		]
	)


func _refresh_objective_ui_3d(force: bool = false) -> void:
	if _objective_panel_3d == null:
		_ensure_objective_ui_3d()

	if _objective_body_3d == null:
		return

	var carrier: SporeUnitActor3D = _crown_carrier_3d()
	var carrier_cell: String = (
		str(carrier.cell)
		if carrier != null
		else "-"
	)

	var signature: String = "%s|%s|%s|%d|%d|%d|%d" % [
		mission_objective_3d,
		crown_carrier_id_3d,
		carrier_cell,
		bonus_collected_3d,
		bonus_cells_3d.size(),
		_living_count_3d("player"),
		_living_count_3d("enemy")
	]

	if not force and signature == _objective_signature_3d:
		return

	_objective_signature_3d = signature
	_objective_body_3d.text = _objective_status_text_3d()


func _rebuild_objective_markers_3d() -> void:
	if map_root == null:
		return

	if _objective_markers_3d == null or not is_instance_valid(
		_objective_markers_3d
	):
		_objective_markers_3d = Node3D.new()
		_objective_markers_3d.name = "MissionObjectiveMarkers"
		add_child(_objective_markers_3d)

	for child: Node in _objective_markers_3d.get_children():
		child.queue_free()

	if (
		mission_objective_3d == "crown"
		and crown_carrier_id_3d.is_empty()
		and map_root.is_cell_valid(crown_cell_3d)
	):
		_add_objective_marker_3d(
			crown_cell_3d,
			"♛ COURONNE",
			Color(1.0, 0.80, 0.28, 1.0)
		)

	for bonus_cell: Vector2i in bonus_cells_3d:
		_add_objective_marker_3d(
			bonus_cell,
			"VINYLE",
			Color(0.76, 0.58, 1.0, 1.0)
		)

	if not crown_carrier_id_3d.is_empty():
		for exit_cell: Vector2i in extraction_cells_3d:
			_add_objective_marker_3d(
				exit_cell,
				"SORTIE",
				Color(0.46, 0.94, 0.62, 1.0)
			)


func _add_objective_marker_3d(
	cell_value: Vector2i,
	text_value: String,
	color: Color
) -> void:
	if (
		_objective_markers_3d == null
		or map_root == null
		or not map_root.is_cell_valid(cell_value)
	):
		return

	var label: Label3D = Label3D.new()
	label.text = text_value
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.font_size = 22
	label.outline_size = 7
	label.modulate = color
	label.position = (
		map_root.cell_top_local(cell_value)
		+ Vector3(0.0, 0.76, 0.0)
	)
	_objective_markers_3d.add_child(label)

	var ring: MeshInstance3D = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = map_root.tile_size * 0.26
	mesh.bottom_radius = map_root.tile_size * 0.26
	mesh.height = 0.025
	ring.mesh = mesh
	ring.position = (
		map_root.cell_top_local(cell_value)
		+ Vector3(0.0, 0.058, 0.0)
	)

	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(
		color.r,
		color.g,
		color.b,
		0.20
	)
	material.emission_enabled = true
	material.emission = Color(color.r, color.g, color.b, 1.0)
	material.emission_energy_multiplier = 0.32
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	ring.material_override = material
	_objective_markers_3d.add_child(ring)


func _ensure_cinematic_player_3d() -> void:
	if _cinematic_player_3d != null and is_instance_valid(_cinematic_player_3d):
		return

	_cinematic_player_3d = get_node_or_null("CinematicPlayer3D") as SporeCinematicPlayer3D
	if _cinematic_player_3d == null:
		var instance: Node = CinematicPlayerScene.instantiate()
		if not (instance is SporeCinematicPlayer3D):
			return
		_cinematic_player_3d = instance as SporeCinematicPlayer3D
		add_child(_cinematic_player_3d)

	var root: Control = null
	if _ui_layer != null:
		root = _ui_layer.get_node_or_null("Root") as Control
	if root != null:
		_cinematic_player_3d.configure(self, root)


func _play_mission_intro_3d() -> void:
	_ensure_cinematic_player_3d()
	var mission: Resource = MissionCatalog.definition(mission_index)
	var cinematic_id: String = String(mission.get("intro_cinematic_id")) if mission != null else ""
	if _cinematic_player_3d != null and not cinematic_id.is_empty():
		player_busy = true
		await _cinematic_player_3d.play(cinematic_id)
		player_busy = false
	_start_next_activation()


func _update_cinematic_end_flow_3d() -> void:
	if not battle_finished or _cinematic_end_started:
		return
	_cinematic_end_started = true
	call_deferred("_play_mission_end_cinematic_3d", _cinematic_victory_state_3d())


func _cinematic_victory_state_3d() -> bool:
	if has_method("_mission_result_3d"):
		var mission_result: int = int(call("_mission_result_3d"))
		if mission_result != 0:
			return mission_result > 0
	var living_players: int = 0
	var living_enemies: int = 0
	for actor: SporeUnitActor3D in player_actors:
		if actor != null and actor.alive:
			living_players += 1
	for actor: SporeUnitActor3D in enemy_actors:
		if actor != null and actor.alive:
			living_enemies += 1
	if living_players <= 0:
		return false
	return living_enemies <= 0 or battle_finished


func _play_mission_end_cinematic_3d(victory: bool) -> void:
	_ensure_cinematic_player_3d()
	var mission: Resource = MissionCatalog.definition(mission_index)
	var cinematic_id: String = ""
	if mission != null:
		cinematic_id = String(
			mission.get("victory_cinematic_id")
			if victory
			else mission.get("defeat_cinematic_id")
		)
	player_busy = true
	enemy_busy = false
	if _cinematic_player_3d != null and not cinematic_id.is_empty():
		await _cinematic_player_3d.play(cinematic_id)
	player_busy = false
	if has_method("_show_battle_result"):
		call("_show_battle_result", victory)


func cinematic_3d_unit_team(unit_id: String) -> String:
	var actor: SporeUnitActor3D = _actor_by_unit_id(unit_id)
	return actor.team if actor != null else ""


func cinematic_3d_focus_cell(cell_value: Vector2i, zoom: float, duration: float) -> void:
	if map_root == null or not map_root.is_cell_valid(cell_value):
		return
	_begin_cinematic_camera_override_3d()
	var local_position: Vector3 = map_root.cell_top_local(cell_value)
	_camera_focus_target = Vector3(local_position.x, 0.0, local_position.z)
	_camera_target_distance = clampf(_cinematic_camera_saved_distance / maxf(0.25, zoom), 6.0, 22.0)


func cinematic_3d_focus_unit(unit_id: String, zoom: float, duration: float) -> void:
	var actor: SporeUnitActor3D = _actor_by_unit_id(unit_id)
	if actor == null:
		return
	_begin_cinematic_camera_override_3d()
	_camera_focus_target = Vector3(actor.position.x, 0.0, actor.position.z)
	_camera_target_distance = clampf(_cinematic_camera_saved_distance / maxf(0.25, zoom), 6.0, 22.0)


func cinematic_3d_zoom(zoom: float, duration: float) -> void:
	_begin_cinematic_camera_override_3d()
	_camera_target_distance = clampf(_cinematic_camera_saved_distance / maxf(0.25, zoom), 6.0, 22.0)


func cinematic_3d_reset_camera(duration: float) -> void:
	if not _cinematic_camera_active:
		return
	_camera_focus_target = _cinematic_camera_saved_focus
	_camera_target_distance = _cinematic_camera_saved_distance


func cinematic_3d_release_camera_override() -> void:
	_cinematic_camera_active = false


func cinematic_3d_camera_shake(intensity: float) -> void:
	_camera_shake_strength = maxf(_camera_shake_strength, clampf(intensity * 0.025, 0.04, 0.28))


func cinematic_3d_execute_action(action: Resource) -> void:
	if action == null:
		return
	var action_type: String = String(action.get("action_type"))
	match action_type:
		"message":
			_log("ÉVÉNEMENT : %s" % String(action.get("message")))
		"set_objective_text":
			_log("OBJECTIF : %s" % String(action.get("message")))
		"set_phase":
			_log("PHASE : %s" % String(action.get("message")))
		_:
			pass


func _begin_cinematic_camera_override_3d() -> void:
	if _cinematic_camera_active:
		return
	_cinematic_camera_active = true
	_cinematic_camera_saved_focus = _camera_focus_target
	_cinematic_camera_saved_distance = _camera_target_distance


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
		_evaluate_mission_triggers_3d("round_end", null)
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
		_show_floating_text(actor.position + Vector3(0.0, 1.30, 0.0), "PRÉPARATION ANNULÉE", Color(1.0, 0.60, 0.34, 1.0))


func _show_turn_transition(actor: SporeUnitActor3D) -> void:
	if actor == null or _ui_layer == null:
		return

	var root: Control = _ui_layer.get_node_or_null("Root") as Control
	if root == null:
		return

	var previous: Node = root.get_node_or_null("TurnTransition")
	if previous != null:
		previous.queue_free()

	var panel: Panel = Panel.new()
	panel.name = "TurnTransition"
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.size = Vector2(390.0, 62.0)

	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	panel.position = Vector2(
		(viewport_size.x - panel.size.x) * 0.5,
		26.0
	)
	panel.modulate = Color(1.0, 1.0, 1.0, 0.0)

	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.045, 0.060, 0.085, 0.94)
	style.corner_radius_top_left = 12
	style.corner_radius_top_right = 12
	style.corner_radius_bottom_left = 12
	style.corner_radius_bottom_right = 12

	if actor.team == "player":
		style.border_color = Color(0.36, 0.82, 1.0, 0.95)
	else:
		style.border_color = Color(1.0, 0.42, 0.38, 0.95)

	style.border_width_left = 2
	style.border_width_top = 2
	style.border_width_right = 2
	style.border_width_bottom = 2

	panel.add_theme_stylebox_override("panel", style)
	root.add_child(panel)

	var label: Label = Label.new()
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 22)

	if actor.team == "player":
		label.text = "À TOI  •  %s" % actor.display_name
		label.add_theme_color_override(
			"font_color",
			Color(0.72, 0.91, 1.0, 1.0)
		)
	else:
		label.text = "ENNEMI  •  %s" % actor.display_name
		label.add_theme_color_override(
			"font_color",
			Color(1.0, 0.70, 0.64, 1.0)
		)

	panel.add_child(label)

	var start_position: Vector2 = panel.position - Vector2(0.0, 12.0)
	var shown_position: Vector2 = panel.position
	panel.position = start_position

	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(panel, "position", shown_position, 0.22)
	tween.tween_property(panel, "modulate", Color.WHITE, 0.18)
	tween.set_parallel(false)
	tween.tween_interval(0.48)
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_SINE)
	tween.tween_property(
		panel,
		"position",
		shown_position + Vector2(0.0, -8.0),
		0.20
	)
	tween.tween_property(
		panel,
		"modulate",
		Color(1.0, 1.0, 1.0, 0.0),
		0.20
	)
	tween.set_parallel(false)
	tween.tween_callback(Callable(panel, "queue_free"))

	_show_floating_text(
		actor.position + Vector3(0.0, 1.52, 0.0),
		"À TOI" if actor.team == "player" else "TOUR ENNEMI",
		Color(0.45, 0.86, 1.0, 1.0)
		if actor.team == "player"
		else Color(1.0, 0.48, 0.42, 1.0)
	)


func _start_next_activation() -> void:
	_clear_enemy_intent_preview()
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
		_apply_terrain_hazard_end_3d(active_actor)
		if active_actor.alive:
			_process_status_phase(active_actor, "activation_end")
		var expired_statuses: PackedStringArray = active_actor.finish_status_activation()
		if not expired_statuses.is_empty():
			_log("%s : fin de %s." % [active_actor.display_name, ", ".join(expired_statuses)])
		active_actor.end_activation()
		_finalize_actor_timing(active_actor)
		if _mission_event_pending_3d():
			active_actor = null
			selected_actor = null
			call_deferred("_resume_after_mission_event_3d")
			return
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
	_log("Tour de %s • Vitesse %d." % [active_actor.display_name, active_actor.effective_speed()])
	_show_action_banner(
		active_actor.display_name,
		"À VOUS" if active_actor.team == "player" else "TOUR ENNEMI",
		"TOUR"
	)
	if active_actor.is_casting():
		_log("Préparation : %s conserve %s en se déplaçant ou en attendant ; une nouvelle action annule la préparation." % [active_actor.display_name, SkillCatalog.display_name(String(active_actor.casting.get("skill_id", "")))])
	if active_actor.moved_this_activation and active_actor.acted_this_activation:
		_log("%s ne peut pas agir pendant cette activation." % active_actor.display_name)
		call_deferred("_start_next_activation")
		return
	_show_turn_transition(active_actor)
	_focus_camera_on_active(false)
	if active_actor.team == "player":
		_refresh_player_overlays()
	else:
		enemy_busy = true
		call_deferred("_execute_enemy_activation")
	_update_ui_text()


func _player_can_input() -> bool:
	if _mission_event_pending_3d():
		return false
	return (
		not battle_finished
		and not enemy_busy
		and not player_busy
		and not _facing_selection_active
		and active_actor != null
		and active_actor.alive
		and active_actor.team == "player"
	)


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
			_play_terrain_feedback_3d(active_actor, start_cell, cell)
			_show_floating_text(active_actor.position + Vector3(0.0, 1.2, 0.0), "TELEPORT", Color(0.70, 0.55, 1.0, 1.0))
		else:
			active_actor.place_on_map(map_root, start_cell)
			_show_floating_text(active_actor.position + Vector3(0.0, 1.2, 0.0), "ÉCHEC %d%%" % chance, Color(1.0, 0.55, 0.40, 1.0))
			_log("%s rate sa téléportation (%d%%)." % [active_actor.display_name, chance])
	else:
		await _move_actor_along_path(active_actor, path, 0.18)
	if active_actor.alive:
		actors_by_cell[active_actor.cell] = active_actor
		_handle_mission_cell_entry_3d(active_actor)
		if _check_battle_end():
			player_busy = false
			return
	active_actor.moved_this_activation = true
	if active_actor.movement_ability == "move_mp_up" and active_actor.cell != start_cell:
		var restored_mp: int = maxi(1, int(ceil(float(active_actor.max_focus) / 10.0)))
		active_actor.change_focus(restored_mp)
	player_busy = false
	if not active_actor.alive:
		_check_battle_end()
		call_deferred("_start_next_activation")
		return
	_log("%s se déplace de %d case(s)." % [active_actor.display_name, path.size() - 1])
	if not active_actor.acted_this_activation:
		input_mode = MODE_ATTACK
	selected_skill_id = ""
	skill_preview_cells.clear()
	preview_path_cells.clear()
	_refresh_player_overlays()
	_update_ui_text()
	_finish_activation_if_complete()


func _basic_attack_vfx_kind(actor: SporeUnitActor3D) -> String:
	if actor == null:
		return ""
	match actor.weapon_family:
		"ranged":
			return "bullet"
		"spear":
			return "slash"
		"focus":
			return "beam"
		"melee", "unarmed":
			return "slash"
	return ""


func _basic_attack_anticipation(actor: SporeUnitActor3D) -> float:
	if actor == null:
		return 0.10
	match actor.weapon_family:
		"ranged":
			return 0.14
		"spear":
			return 0.13
		"focus":
			return 0.18
	return 0.11


func _basic_attack_camera_duration(actor: SporeUnitActor3D) -> float:
	if actor == null:
		return 0.95
	match actor.weapon_family:
		"ranged":
			return 1.12
		"spear":
			return 1.00
		"focus":
			return 1.18
	return 0.98


func _weapon_family_display_name(family: String) -> String:
	match family:
		"ranged":
			return "Tir"
		"spear":
			return "Lance"
		"focus":
			return "Focaliseur"
		"melee":
			return "Mêlée"
		"unarmed":
			return "Corps à corps"
	return family.capitalize() if not family.is_empty() else "Arme inconnue"


func _player_attack(target: SporeUnitActor3D) -> void:
	if active_actor == null or active_actor.acted_this_activation or target == null or not target.alive:
		return

	_cancel_cast_for_command_3d(active_actor, "Attack")
	player_busy = true
	active_actor.acted_this_activation = true
	_show_action_banner(
		active_actor.display_name,
		_weapon_family_display_name(active_actor.weapon_family),
		"ATTAQUE"
	)

	var camera_duration: float = _basic_attack_camera_duration(active_actor)
	var camera_zoom: float = 0.62 if active_actor.weapon_family == "ranged" else 0.78
	_begin_action_camera(
		active_actor.global_position,
		target.global_position,
		camera_duration,
		camera_zoom
	)

	active_actor.play_attack(target.position)

	var anticipation: float = _basic_attack_anticipation(active_actor)
	if anticipation > 0.0:
		await get_tree().create_timer(anticipation).timeout

	var vfx_kind: String = _basic_attack_vfx_kind(active_actor)
	await _play_action_vfx_to_impact(
		active_actor.basic_attack_vfx_id,
		active_actor.global_position + Vector3(0.0, 0.72, 0.0),
		target.global_position + Vector3(0.0, 0.64, 0.0),
		false,
		target,
		Vector3(0.0, 0.64, 0.0),
		vfx_kind
	)

	_resolve_attack(active_actor, target)
	_camera_impact()

	if vfx_impact_pause > 0.0:
		await get_tree().create_timer(vfx_impact_pause).timeout

	# A short readable hold after impact makes the result register visually.
	await get_tree().create_timer(0.14).timeout
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
	_show_floating_text(recipient.position + Vector3(0.0, 1.15, 0.0), "-%d PV" % applied, Color(1.0, 0.42, 0.36, 1.0))
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
	label.font_size = 48
	label.outline_size = 11
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.modulate = color
	label.position = world_position
	label.scale = Vector3(0.82, 0.82, 0.82)
	_actor_holder.add_child(label)

	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(label, "position", world_position + Vector3(0.0, 0.70, 0.0), 0.82)
	tween.tween_property(label, "scale", Vector3(1.10, 1.10, 1.10), 0.20)
	tween.set_parallel(false)
	tween.tween_interval(0.22)
	tween.set_parallel(true)
	tween.tween_property(label, "modulate", Color(color.r, color.g, color.b, 0.0), 0.28)
	tween.tween_property(label, "scale", Vector3(0.92, 0.92, 0.92), 0.28)
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
	_log("MOVE — clique une case verte.")
	_update_ui_text()


func _on_attack_mode_pressed() -> void:
	_clear_pending_action()
	if not _player_can_input() or active_actor.acted_this_activation:
		return
	input_mode = MODE_ATTACK
	preview_path_cells.clear()
	_refresh_player_overlays()
	_log("ATTAQUE — clique un ennemi sur une case rouge.")
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


func _open_facing_selector() -> void:
	if active_actor == null or battle_finished or active_actor.team != "player":
		return
	if _ui_layer == null:
		return

	_clear_pending_action()
	selected_skill_id = ""
	skill_preview_cells.clear()
	preview_path_cells.clear()
	_refresh_player_overlays()

	var root: Control = _ui_layer.get_node_or_null("Root") as Control
	if root == null:
		return

	if _facing_panel == null or not is_instance_valid(_facing_panel):
		_facing_panel = Panel.new()
		_facing_panel.name = "FacingSelector"
		_facing_panel.size = Vector2(430.0, 190.0)
		_facing_panel.mouse_filter = Control.MOUSE_FILTER_STOP

		var style: StyleBoxFlat = StyleBoxFlat.new()
		style.bg_color = Color(0.045, 0.060, 0.085, 0.97)
		style.border_color = Color(1.0, 0.78, 0.30, 0.96)
		style.border_width_left = 2
		style.border_width_top = 2
		style.border_width_right = 2
		style.border_width_bottom = 2
		style.corner_radius_top_left = 14
		style.corner_radius_top_right = 14
		style.corner_radius_bottom_left = 14
		style.corner_radius_bottom_right = 14
		_facing_panel.add_theme_stylebox_override("panel", style)
		root.add_child(_facing_panel)

		var title: Label = Label.new()
		title.name = "Title"
		title.position = Vector2(18.0, 12.0)
		title.size = Vector2(394.0, 26.0)
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		title.add_theme_font_size_override("font_size", 17)
		title.add_theme_color_override("font_color", Color(1.0, 0.84, 0.40, 1.0))
		title.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_facing_panel.add_child(title)

		var help: Label = Label.new()
		help.position = Vector2(18.0, 41.0)
		help.size = Vector2(394.0, 34.0)
		help.text = "Choisis la direction regardée. Le dos et les flancs sont plus vulnérables."
		help.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		help.add_theme_font_size_override("font_size", 11)
		help.add_theme_color_override("font_color", Color(0.82, 0.87, 0.91, 1.0))
		help.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_facing_panel.add_child(help)

		var north: Button = Button.new()
		north.text = "↑ NORD"
		north.position = Vector2(164.0, 78.0)
		north.size = Vector2(102.0, 32.0)
		north.pressed.connect(_choose_facing.bind(Vector2i.UP))
		_facing_panel.add_child(north)

		var west: Button = Button.new()
		west.text = "← OUEST"
		west.position = Vector2(54.0, 112.0)
		west.size = Vector2(102.0, 32.0)
		west.pressed.connect(_choose_facing.bind(Vector2i.LEFT))
		_facing_panel.add_child(west)

		var south: Button = Button.new()
		south.text = "↓ SUD"
		south.position = Vector2(164.0, 112.0)
		south.size = Vector2(102.0, 32.0)
		south.pressed.connect(_choose_facing.bind(Vector2i.DOWN))
		_facing_panel.add_child(south)

		var east: Button = Button.new()
		east.text = "EST →"
		east.position = Vector2(274.0, 112.0)
		east.size = Vector2(102.0, 32.0)
		east.pressed.connect(_choose_facing.bind(Vector2i.RIGHT))
		_facing_panel.add_child(east)

		var cancel: Button = Button.new()
		cancel.text = "RETOUR"
		cancel.position = Vector2(54.0, 151.0)
		cancel.size = Vector2(140.0, 30.0)
		cancel.pressed.connect(_close_facing_selector)
		_facing_panel.add_child(cancel)

		var confirm: Button = Button.new()
		confirm.text = "TERMINER LE TOUR"
		confirm.position = Vector2(202.0, 151.0)
		confirm.size = Vector2(174.0, 30.0)
		confirm.pressed.connect(_confirm_facing_and_end)
		_facing_panel.add_child(confirm)

	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	_facing_panel.position = Vector2(
		(viewport_size.x - _facing_panel.size.x) * 0.5,
		viewport_size.y - _facing_panel.size.y - 24.0
	)
	_facing_panel.visible = true
	_facing_selection_active = true
	player_busy = true
	_update_facing_selector_title()


func _close_facing_selector() -> void:
	if _facing_panel != null and is_instance_valid(_facing_panel):
		_facing_panel.visible = false
	_facing_selection_active = false
	if not battle_finished:
		player_busy = false
	_refresh_player_overlays()
	_update_ui_text()


func _choose_facing(direction: Vector2i) -> void:
	if not _facing_selection_active or active_actor == null:
		return
	active_actor.set_facing(direction)
	_update_facing_selector_title()
	_update_ui_text()


func _update_facing_selector_title() -> void:
	if _facing_panel == null or not is_instance_valid(_facing_panel):
		return
	var title: Label = _facing_panel.get_node_or_null("Title") as Label
	if title == null or active_actor == null:
		return
	title.text = "ORIENTATION : %s" % active_actor.facing_name().to_upper()


func _confirm_facing_and_end() -> void:
	if not _facing_selection_active or active_actor == null:
		return

	if _facing_panel != null and is_instance_valid(_facing_panel):
		_facing_panel.visible = false

	_facing_selection_active = false
	player_busy = false

	active_actor.waited_this_activation = (
		not active_actor.moved_this_activation
		and not active_actor.acted_this_activation
	)

	var wait_note: String = ""
	if active_actor.is_casting() and not active_actor.acted_this_activation:
		wait_note = " • préparation conservée"

	_log(
		"%s termine son tour • orientation %s%s."
		% [active_actor.display_name, active_actor.facing_name(), wait_note]
	)
	_start_next_activation()


func _on_face_pressed(turns: int = 1) -> void:
	if _facing_selection_active:
		return
	if not _player_can_input() or active_actor == null:
		return
	_open_facing_selector()


func _on_end_activation_pressed() -> void:
	if _facing_selection_active:
		_confirm_facing_and_end()
		return
	if not _player_can_input():
		return
	_open_facing_selector()


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
	for y_door: int in range(map_root.grid_height):
		for x_door: int in range(map_root.grid_width):
			var door_cell: Vector2i = Vector2i(x_door, y_door)
			if _closed_door_at_3d(door_cell):
				blocked[door_cell] = true
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


func _show_action_banner(actor_name: String, action_name: String, category: String = "") -> void:
	if _ui_layer == null:
		return

	var root: Control = _ui_layer.get_node_or_null("Root") as Control
	if root == null:
		return

	if _action_banner_panel == null or not is_instance_valid(_action_banner_panel):
		_action_banner_panel = Panel.new()
		_action_banner_panel.name = "ActionBanner"
		_action_banner_panel.size = Vector2(420.0, 64.0)
		_action_banner_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE

		var style: StyleBoxFlat = StyleBoxFlat.new()
		style.bg_color = Color(0.01, 0.01, 0.012, 0.96)
		style.border_color = Color(0.96, 0.94, 0.88, 0.98)
		style.border_width_left = 3
		style.border_width_top = 3
		style.border_width_right = 3
		style.border_width_bottom = 3
		style.corner_radius_top_left = 2
		style.corner_radius_top_right = 2
		style.corner_radius_bottom_left = 2
		style.corner_radius_bottom_right = 2
		_action_banner_panel.add_theme_stylebox_override("panel", style)
		root.add_child(_action_banner_panel)

		_action_banner_title = _make_label(
			_action_banner_panel,
			Vector2(14.0, 7.0),
			Vector2(392.0, 27.0),
			18,
			Color(1.0, 0.84, 0.42, 1.0)
		)
		_action_banner_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

		_action_banner_subtitle = _make_label(
			_action_banner_panel,
			Vector2(14.0, 34.0),
			Vector2(392.0, 20.0),
			11,
			Color(0.82, 0.88, 0.94, 1.0)
		)
		_action_banner_subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	_action_banner_panel.position = Vector2(
		(viewport_size.x - _action_banner_panel.size.x) * 0.5,
		14.0
	)

	if _action_banner_tween != null and _action_banner_tween.is_valid():
		_action_banner_tween.kill()

	_action_banner_panel.visible = true
	_action_banner_panel.modulate = Color(1.0, 1.0, 1.0, 0.0)
	_action_banner_panel.scale = Vector2(0.96, 0.96)
	_action_banner_panel.pivot_offset = _action_banner_panel.size * 0.5

	_action_banner_title.text = action_name
	_action_banner_subtitle.text = (
		actor_name
		if category.is_empty()
		else "%s  •  %s" % [actor_name, category]
	)
	_show_comic_stamp(action_name, category)

	_action_banner_tween = create_tween()
	_action_banner_tween.set_parallel(true)
	_action_banner_tween.tween_property(
		_action_banner_panel,
		"modulate",
		Color.WHITE,
		0.12
	)
	_action_banner_tween.tween_property(
		_action_banner_panel,
		"scale",
		Vector2.ONE,
		0.14
	)
	_action_banner_tween.set_parallel(false)
	_action_banner_tween.tween_interval(0.68)
	_action_banner_tween.tween_property(
		_action_banner_panel,
		"modulate",
		Color(1.0, 1.0, 1.0, 0.0),
		0.20
	)
	_action_banner_tween.tween_callback(
		func() -> void:
			if _action_banner_panel != null:
				_action_banner_panel.visible = false
	)



func _show_comic_stamp(action_name: String, category: String) -> void:
	if category not in ["ATTAQUE", "COMPÉTENCE", "PRÉPARATION"]:
		return
	if _ui_layer == null:
		return
	var root := _ui_layer.get_node_or_null("Root") as Control
	if root == null:
		return

	if _comic_stamp_label == null or not is_instance_valid(_comic_stamp_label):
		_comic_stamp_label = Label.new()
		_comic_stamp_label.name = "ComicActionStamp"
		_comic_stamp_label.size = Vector2(520.0, 100.0)
		_comic_stamp_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_comic_stamp_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_comic_stamp_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_comic_stamp_label.add_theme_font_size_override("font_size", 44)
		_comic_stamp_label.add_theme_color_override("font_outline_color", Color(0.02, 0.02, 0.02, 1.0))
		_comic_stamp_label.add_theme_constant_override("outline_size", 11)
		_comic_stamp_label.rotation = deg_to_rad(-4.0)
		root.add_child(_comic_stamp_label)

	var viewport_size := get_viewport().get_visible_rect().size
	_comic_stamp_label.position = Vector2(
		(viewport_size.x - _comic_stamp_label.size.x) * 0.5 + 42.0,
		viewport_size.y * 0.19
	)
	_comic_stamp_label.text = action_name.to_upper()

	var accent := Color(1.0, 0.80, 0.16, 1.0)
	if category == "ATTAQUE":
		accent = Color(0.96, 0.20, 0.16, 1.0)
	elif category == "COMPÉTENCE":
		accent = Color(0.57, 0.36, 0.94, 1.0)
	_comic_stamp_label.add_theme_color_override("font_color", accent)

	if _comic_stamp_tween != null and _comic_stamp_tween.is_valid():
		_comic_stamp_tween.kill()

	_comic_stamp_label.visible = true
	_comic_stamp_label.modulate = Color(1.0, 1.0, 1.0, 0.0)
	_comic_stamp_label.scale = Vector2(0.72, 0.72)
	_comic_stamp_label.pivot_offset = _comic_stamp_label.size * 0.5

	_comic_stamp_tween = create_tween()
	_comic_stamp_tween.set_parallel(true)
	_comic_stamp_tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_comic_stamp_tween.tween_property(_comic_stamp_label, "modulate", Color.WHITE, 0.10)
	_comic_stamp_tween.tween_property(_comic_stamp_label, "scale", Vector2.ONE, 0.16)
	_comic_stamp_tween.set_parallel(false)
	_comic_stamp_tween.tween_interval(0.38)
	_comic_stamp_tween.tween_property(
		_comic_stamp_label,
		"modulate",
		Color(1.0, 1.0, 1.0, 0.0),
		0.18
	)
	_comic_stamp_tween.tween_callback(
		func() -> void:
			if _comic_stamp_label != null:
				_comic_stamp_label.visible = false
	)

func _spawn_feedback_burst(actor: SporeUnitActor3D, color: Color) -> void:
	if actor == null or _vfx_holder == null:
		return

	var root: Node3D = Node3D.new()
	root.name = "FeedbackBurst"
	_vfx_holder.add_child(root)
	root.global_position = actor.global_position + Vector3(0.0, 0.62, 0.0)

	var particle_count: int = 8
	for index: int in range(particle_count):
		var orb: MeshInstance3D = MeshInstance3D.new()
		var mesh: SphereMesh = SphereMesh.new()
		mesh.radius = 0.045
		mesh.height = 0.09
		orb.mesh = mesh

		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = color
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled = true
		material.emission = Color(color.r, color.g, color.b, 1.0)
		material.emission_energy_multiplier = 1.3
		orb.material_override = material

		var angle: float = TAU * float(index) / float(particle_count)
		var direction: Vector3 = Vector3(
			cos(angle),
			0.45 + 0.10 * float(index % 3),
			sin(angle)
		).normalized()

		root.add_child(orb)
		orb.position = Vector3.ZERO

		var tween: Tween = create_tween()
		tween.set_parallel(true)
		tween.set_trans(Tween.TRANS_SINE)
		tween.tween_property(
			orb,
			"position",
			direction * (0.34 + 0.06 * float(index % 2)),
			0.36
		)
		tween.tween_property(
			orb,
			"scale",
			Vector3(0.12, 0.12, 0.12),
			0.36
		)
		tween.tween_property(
			material,
			"albedo_color",
			Color(color.r, color.g, color.b, 0.0),
			0.36
		)

	var cleanup: Tween = create_tween()
	cleanup.tween_interval(0.40)
	cleanup.tween_callback(Callable(root, "queue_free"))


func _play_victory_celebration() -> void:
	var living: Array[SporeUnitActor3D] = []
	var focus_sum: Vector3 = Vector3.ZERO

	for actor: SporeUnitActor3D in player_actors:
		if actor == null or not actor.alive:
			continue
		living.append(actor)
		focus_sum += actor.position

	if living.is_empty():
		return

	var center: Vector3 = focus_sum / float(living.size())
	camera_follow_active = false
	_camera_focus_target = Vector3(center.x, 0.0, center.z)
	_camera_target_distance = minf(22.0, maxf(_camera_target_distance, 14.0))

	for index: int in range(living.size()):
		var actor: SporeUnitActor3D = living[index]
		var delay: float = 0.08 * float(index)
		var timer: SceneTreeTimer = get_tree().create_timer(delay)
		timer.timeout.connect(
			func() -> void:
				if actor != null and is_instance_valid(actor):
					actor.play_victory()
		)

	_spawn_victory_confetti(center)


func _spawn_victory_confetti(center: Vector3) -> void:
	if _vfx_holder == null:
		return

	var colors: Array[Color] = [
		Color(1.0, 0.78, 0.24, 1.0),
		Color(0.40, 0.86, 1.0, 1.0),
		Color(0.56, 0.94, 0.60, 1.0),
		Color(0.92, 0.54, 1.0, 1.0)
	]

	for index: int in range(18):
		var piece: MeshInstance3D = MeshInstance3D.new()
		var mesh: BoxMesh = BoxMesh.new()
		mesh.size = Vector3(0.07, 0.03, 0.11)
		piece.mesh = mesh

		var color: Color = colors[index % colors.size()]
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = color
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.55
		piece.material_override = material

		_vfx_holder.add_child(piece)

		var angle: float = TAU * float(index) / 18.0
		var radius: float = 0.5 + 0.07 * float(index % 5)
		piece.position = center + Vector3(
			cos(angle) * radius,
			1.2 + 0.08 * float(index % 4),
			sin(angle) * radius
		)

		piece.rotation = Vector3(
			0.15 * float(index % 3),
			angle,
			0.20 * float(index % 4)
		)

		var outward: Vector3 = Vector3(
			cos(angle) * (0.7 + 0.05 * float(index % 4)),
			1.4 + 0.08 * float(index % 3),
			sin(angle) * (0.7 + 0.05 * float(index % 4))
		)

		var tween: Tween = create_tween()
		tween.set_parallel(true)
		tween.set_trans(Tween.TRANS_SINE)
		tween.tween_property(
			piece,
			"position",
			piece.position + outward,
			0.55
		)
		tween.tween_property(
			piece,
			"rotation",
			piece.rotation + Vector3(2.2, 2.8, 1.7),
			0.55
		)
		tween.set_parallel(false)
		tween.set_trans(Tween.TRANS_QUAD)
		tween.set_ease(Tween.EASE_IN)
		tween.tween_property(
			piece,
			"position:y",
			center.y + 0.10,
			0.55
		)
		tween.tween_callback(Callable(piece, "queue_free"))


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
		_show_action_banner(
			active_actor.display_name,
			SkillCatalog.display_name(selected_skill_id),
			"PRÉPARATION"
		)
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
	_show_action_banner(active_actor.display_name, skill_name, "COMPÉTENCE")
	var anchor_global: Vector3 = map_root.to_global(map_root.cell_top_local(anchor_cell))
	active_actor.face_cell(anchor_cell)
	_begin_action_camera(active_actor.global_position, anchor_global, 0.86, action_camera_zoom_in + 0.25)
	active_actor.play_cast(anchor_global)
	await get_tree().create_timer(0.06).timeout
	var tracked_skill_target: SporeUnitActor3D = actors_by_cell.get(anchor_cell, null) as SporeUnitActor3D
	var tracked_skill_offset: Vector3 = Vector3(0.0, 0.64, 0.0) if tracked_skill_target != null else Vector3.ZERO
	_show_skill_name_banner(active_actor, skill)
	var primary_vfx_kind: String = _skill_primary_vfx_kind(String(skill.get("id")))
	await _play_action_vfx_to_impact(
		String(skill.get("vfx_id")),
		active_actor.global_position + Vector3(0.0, 0.78, 0.0),
		anchor_global + Vector3(0.0, 0.18, 0.0),
		false,
		tracked_skill_target,
		tracked_skill_offset,
		primary_vfx_kind
	)
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
					_show_floating_text(target.position + Vector3(0.0, 1.25, 0.0), "RELEVÉ +%d PV" % restored, Color(0.48, 0.90, 0.66, 1.0))
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
					_show_floating_text(target.position + Vector3(0.0, 1.15, 0.0), "+%d PV" % healed, Color(0.48, 0.90, 0.66, 1.0))
					_spawn_feedback_burst(target, Color(0.48, 0.90, 0.66, 1.0))
			"status":
				var status_id: String = String(effect.get("status_id"))
				var formula_modifier: int = int(skill.get("fft_status_modifier"))
				if formula_modifier > 0 and target.team != caster.team:
					var compatibility: String = CombatMechanics.zodiac_compatibility(caster.zodiac_sign, target.zodiac_sign, caster.sex, target.sex)
					var status_chance: int = CombatMechanics.fft_status_success_chance(caster.effective_magic_power(), formula_modifier, caster.faith, target.faith, compatibility, target.statuses.has("shell"), target.support_ability == "magic_defense_up")
					if not _roll_hit_3d(status_chance):
						_show_floating_text(target.position + Vector3(0.0, 1.28, 0.0), "RÉSISTE", Color(0.90, 0.90, 0.95, 1.0))
						continue
				if target.apply_status(status_id):
					var status_data: Resource = StatusCatalog.definition(status_id)
					var status_name: String = String(status_data.get("display_name")) if status_data != null else status_id
					_show_floating_text(target.position + Vector3(0.0, 1.28, 0.0), status_name, Color(0.78, 0.62, 1.0, 1.0))
					_spawn_feedback_burst(target, Color(0.78, 0.62, 1.0, 1.0))
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
				_show_floating_text(actor.position + Vector3(0.0, 1.15, 0.0), "+%d PV" % healed, Color(0.48, 0.90, 0.66, 1.0))
				_spawn_feedback_burst(actor, Color(0.48, 0.90, 0.66, 1.0))


func _setup_mission_events_3d() -> void:
	_hazard_cells_3d.clear()
	_mission_triggers_3d.clear()
	_fired_trigger_ids_3d.clear()
	_trigger_queue_3d.clear()
	_mission_event_busy_3d = false

	if map_root != null:
		var environment: Dictionary = map_root.to_environment()
		var hazards_value: Variant = environment.get("hazards", [])
		if hazards_value is Array:
			for value: Variant in hazards_value:
				if value is Vector2i and not _hazard_cells_3d.has(value):
					_hazard_cells_3d.append(value)

	var mission: Resource = MissionCatalog.definition(mission_index)
	if mission != null:
		var triggers_value: Variant = mission.get("battle_triggers")
		if triggers_value is Array:
			for value: Variant in triggers_value:
				if value is Resource:
					_mission_triggers_3d.append(value as Resource)

	_rebuild_hazard_visuals_3d()


func _mission_event_pending_3d() -> bool:
	return _mission_event_busy_3d or not _trigger_queue_3d.is_empty()


func _wait_for_mission_events_3d() -> void:
	while _mission_event_pending_3d():
		await get_tree().process_frame


func _start_after_initial_mission_events_3d() -> void:
	await _wait_for_mission_events_3d()
	if not battle_finished:
		_start_next_activation()


func _resume_after_mission_event_3d() -> void:
	await _wait_for_mission_events_3d()
	if not battle_finished:
		_start_next_activation()


func _evaluate_mission_triggers_3d(
	event_name: String,
	event_actor: SporeUnitActor3D = null
) -> void:
	if battle_finished:
		return

	for trigger: Resource in _mission_triggers_3d:
		if trigger == null or not bool(trigger.get("enabled")):
			continue

		var trigger_id: String = String(trigger.get("id"))
		var once: bool = bool(trigger.get("once"))
		if once and not trigger_id.is_empty() and bool(_fired_trigger_ids_3d.get(trigger_id, false)):
			continue

		if not _mission_trigger_matches_3d(trigger, event_name, event_actor):
			continue

		if once and not trigger_id.is_empty():
			_fired_trigger_ids_3d[trigger_id] = true
		_trigger_queue_3d.append(trigger)

	if not _trigger_queue_3d.is_empty() and not _mission_event_busy_3d:
		call_deferred("_run_trigger_queue_3d")


func _mission_trigger_matches_3d(
	trigger: Resource,
	event_name: String,
	event_actor: SporeUnitActor3D
) -> bool:
	var condition_type: String = String(trigger.get("condition_type"))
	var condition_value: int = int(trigger.get("condition_value"))
	var condition_unit_id: String = String(trigger.get("condition_unit_id"))
	var raw_cell: Variant = trigger.get("condition_cell")
	var condition_cell: Vector2i = raw_cell if raw_cell is Vector2i else Vector2i(-1, -1)

	match condition_type:
		"round_start":
			return event_name == "round_start" and round_number == maxi(1, condition_value)
		"round_end":
			return event_name == "round_end" and round_number == maxi(1, condition_value)
		"enemy_count_at_most":
			return _event_alive_count_3d("enemy") <= maxi(0, condition_value)
		"player_count_at_most":
			return _event_alive_count_3d("player") <= maxi(0, condition_value)
		"unit_hp_at_most":
			var hp_actor: SporeUnitActor3D = _actor_by_unit_id(condition_unit_id)
			return hp_actor != null and hp_actor.alive and hp_actor.hp <= condition_value
		"unit_defeated":
			var defeated_actor: SporeUnitActor3D = _actor_by_unit_id(condition_unit_id)
			return defeated_actor == null or not defeated_actor.alive
		"player_enters_cell":
			return event_name == "unit_moved" and event_actor != null and event_actor.team == "player" and event_actor.cell == condition_cell
		"enemy_enters_cell":
			return event_name == "unit_moved" and event_actor != null and event_actor.team == "enemy" and event_actor.cell == condition_cell
	return false


func _event_alive_count_3d(team_value: String) -> int:
	var count: int = 0
	var source: Array[SporeUnitActor3D] = player_actors if team_value == "player" else enemy_actors
	for actor: SporeUnitActor3D in source:
		if actor != null and actor.alive:
			count += 1
	return count


func _run_trigger_queue_3d() -> void:
	if _mission_event_busy_3d:
		return
	if _trigger_queue_3d.is_empty():
		return

	var raw_trigger: Variant = _trigger_queue_3d.pop_front()
	if not (raw_trigger is Resource):
		call_deferred("_run_trigger_queue_3d")
		return

	_mission_event_busy_3d = true
	await _run_trigger_actions_3d(raw_trigger as Resource)
	_mission_event_busy_3d = false

	if not _trigger_queue_3d.is_empty():
		call_deferred("_run_trigger_queue_3d")
	elif active_actor != null and active_actor.team == "player" and active_actor.alive and not battle_finished:
		_refresh_player_overlays()
		_update_ui_text()


func _run_trigger_actions_3d(trigger: Resource) -> void:
	var actions_value: Variant = trigger.get("actions")
	if actions_value is Array and not (actions_value as Array).is_empty():
		for raw_action: Variant in actions_value:
			if raw_action is Resource:
				await _execute_mission_action_3d(raw_action as Resource)
		return

	await _execute_legacy_trigger_3d(trigger)


func _execute_legacy_trigger_3d(trigger: Resource) -> void:
	var raw_cell: Variant = trigger.get("action_cell")
	var cell_value: Vector2i = raw_cell if raw_cell is Vector2i else Vector2i(-1, -1)
	await _execute_mission_action_values_3d(
		String(trigger.get("action_type")),
		String(trigger.get("message")),
		cell_value,
		int(trigger.get("action_value")),
		String(trigger.get("action_team")),
		float(0.0)
	)


func _execute_mission_action_3d(action: Resource) -> void:
	var raw_cell: Variant = action.get("cell")
	var cell_value: Vector2i = raw_cell if raw_cell is Vector2i else Vector2i(-1, -1)
	await _execute_mission_action_values_3d(
		String(action.get("action_type")),
		String(action.get("message")),
		cell_value,
		int(action.get("value")),
		String(action.get("team")),
		float(action.get("delay_seconds"))
	)


func _execute_mission_action_values_3d(
	action_type: String,
	message: String,
	cell_value: Vector2i,
	value: int,
	team_value: String,
	delay_seconds: float
) -> void:
	match action_type:
		"message":
			if not message.is_empty():
				_show_mission_event_banner_3d(message)
				_log("ÉVÉNEMENT : %s" % message)

		"wait":
			if delay_seconds > 0.0:
				await get_tree().create_timer(delay_seconds).timeout

		"add_hazard":
			if map_root != null and map_root.is_cell_valid(cell_value) and not _hazard_cells_3d.has(cell_value):
				_hazard_cells_3d.append(cell_value)
				_rebuild_hazard_visuals_3d()
				_show_hazard_spawn_3d(cell_value)
				_log("Le jardin crée une nouvelle zone de spores.")

		"remove_hazard":
			if _hazard_cells_3d.has(cell_value):
				_hazard_cells_3d.erase(cell_value)
				_rebuild_hazard_visuals_3d()

		"heal_team":
			var heal_targets: Array[SporeUnitActor3D] = player_actors if team_value == "player" else enemy_actors
			for target: SporeUnitActor3D in heal_targets:
				if target != null and target.alive:
					var healed: int = target.heal(maxi(0, value))
					if healed > 0:
						_show_floating_text(
							target.position + Vector3(0.0, 1.18, 0.0),
							"+%d PV" % healed,
							Color(0.48, 0.90, 0.66, 1.0)
						)

		"damage_team":
			var damage_targets: Array[SporeUnitActor3D] = player_actors if team_value == "player" else enemy_actors
			for target: SporeUnitActor3D in damage_targets:
				if target != null and target.alive:
					_apply_damage_with_reactions(
						null,
						target,
						maxi(0, value),
						"événement",
						false,
						false,
						"spore"
					)

		"grant_focus_team":
			var focus_targets: Array[SporeUnitActor3D] = player_actors if team_value == "player" else enemy_actors
			for target: SporeUnitActor3D in focus_targets:
				if target != null and target.alive:
					target.change_focus(value)
					_show_floating_text(
						target.position + Vector3(0.0, 1.18, 0.0),
						"%+d MP" % value,
						Color(0.48, 0.76, 1.0, 1.0)
					)

		_:
			if not action_type.is_empty():
				_log("Événement 3D : action '%s' ignorée pour cette passe." % action_type)

	if action_type != "wait" and delay_seconds > 0.0:
		await get_tree().create_timer(delay_seconds).timeout

	_check_battle_end()


func _show_mission_event_banner_3d(message: String) -> void:
	if _ui_layer == null:
		return
	var root: Control = _ui_layer.get_node_or_null("Root") as Control
	if root == null:
		return

	var previous: Node = root.get_node_or_null("MissionEventBanner")
	if previous != null:
		previous.queue_free()

	var panel: Panel = Panel.new()
	panel.name = "MissionEventBanner"
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.size = Vector2(620.0, 92.0)
	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	panel.position = Vector2((viewport_size.x - 620.0) * 0.5, 92.0)
	panel.modulate = Color(1.0, 1.0, 1.0, 0.0)

	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.045, 0.035, 0.070, 0.96)
	style.border_color = Color(0.76, 0.58, 1.0, 1.0)
	style.border_width_left = 2
	style.border_width_top = 2
	style.border_width_right = 2
	style.border_width_bottom = 2
	style.corner_radius_top_left = 14
	style.corner_radius_top_right = 14
	style.corner_radius_bottom_left = 14
	style.corner_radius_bottom_right = 14
	panel.add_theme_stylebox_override("panel", style)
	root.add_child(panel)

	var title: Label = Label.new()
	title.position = Vector2(18.0, 9.0)
	title.size = Vector2(584.0, 22.0)
	title.text = "ÉVÉNEMENT DE MISSION"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 14)
	title.add_theme_color_override("font_color", Color(0.82, 0.70, 1.0, 1.0))
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(title)

	var body: Label = Label.new()
	body.position = Vector2(24.0, 34.0)
	body.size = Vector2(572.0, 46.0)
	body.text = message
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_font_size_override("font_size", 15)
	body.add_theme_color_override("font_color", Color(0.95, 0.93, 1.0, 1.0))
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(body)

	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(panel, "modulate", Color.WHITE, 0.18)
	tween.tween_property(panel, "position:y", 102.0, 0.22)
	tween.set_parallel(false)
	tween.tween_interval(1.05)
	tween.set_parallel(true)
	tween.tween_property(panel, "modulate", Color(1.0, 1.0, 1.0, 0.0), 0.22)
	tween.tween_property(panel, "position:y", 94.0, 0.22)
	tween.set_parallel(false)
	tween.tween_callback(Callable(panel, "queue_free"))


func _rebuild_hazard_visuals_3d() -> void:
	if map_root == null:
		return

	if _hazard_visual_root_3d == null or not is_instance_valid(_hazard_visual_root_3d):
		_hazard_visual_root_3d = Node3D.new()
		_hazard_visual_root_3d.name = "MissionHazards"
		add_child(_hazard_visual_root_3d)

	for child: Node in _hazard_visual_root_3d.get_children():
		child.queue_free()

	for hazard_index: int in range(_hazard_cells_3d.size()):
		var cell_value: Vector2i = _hazard_cells_3d[hazard_index]
		if not map_root.is_cell_valid(cell_value):
			continue

		var root: Node3D = Node3D.new()
		root.name = "Hazard_%02d_%02d" % [cell_value.x, cell_value.y]
		root.position = map_root.cell_top_local(cell_value) + Vector3(0.0, 0.07, 0.0)
		root.set_meta("phase", float(hazard_index) * 0.73)
		_hazard_visual_root_3d.add_child(root)

		var pool: MeshInstance3D = MeshInstance3D.new()
		pool.name = "Pool"
		var pool_mesh: CylinderMesh = CylinderMesh.new()
		pool_mesh.top_radius = map_root.tile_size * 0.31
		pool_mesh.bottom_radius = map_root.tile_size * 0.35
		pool_mesh.height = 0.035
		pool.mesh = pool_mesh

		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = Color(0.58, 0.28, 0.78, 0.28)
		material.emission_enabled = true
		material.emission = Color(0.66, 0.34, 0.86, 1.0)
		material.emission_energy_multiplier = 0.30
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		pool.material_override = material
		root.add_child(pool)

		for spore_index: int in range(5):
			var spore: MeshInstance3D = MeshInstance3D.new()
			spore.name = "Spore_%d" % spore_index
			var spore_mesh: SphereMesh = SphereMesh.new()
			spore_mesh.radius = 0.035 + 0.008 * float(spore_index % 3)
			spore_mesh.height = spore_mesh.radius * 2.0
			spore_mesh.radial_segments = 8
			spore_mesh.rings = 4
			spore.mesh = spore_mesh

			var spore_material: StandardMaterial3D = StandardMaterial3D.new()
			spore_material.albedo_color = Color(0.80, 0.54, 1.0, 0.82)
			spore_material.emission_enabled = true
			spore_material.emission = Color(0.80, 0.54, 1.0, 1.0)
			spore_material.emission_energy_multiplier = 0.50
			spore_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			spore_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			spore.material_override = spore_material

			var angle: float = TAU * float(spore_index) / 5.0
			spore.position = Vector3(
				cos(angle) * map_root.tile_size * 0.19,
				0.05 + 0.035 * float(spore_index % 2),
				sin(angle) * map_root.tile_size * 0.19
			)
			spore.set_meta("base_angle", angle)
			spore.set_meta("spore_index", spore_index)
			root.add_child(spore)

		var label: Label3D = Label3D.new()
		label.text = "SPORES • -1 PV fin de tour"
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.font_size = 18
		label.outline_size = 6
		label.modulate = Color(0.88, 0.72, 1.0, 0.96)
		label.position = Vector3(0.0, 0.32, 0.0)
		root.add_child(label)


func _update_hazard_visuals_3d() -> void:
	if _hazard_visual_root_3d == null or not is_instance_valid(_hazard_visual_root_3d):
		return

	for child: Node in _hazard_visual_root_3d.get_children():
		var root: Node3D = child as Node3D
		if root == null:
			continue

		var phase: float = float(root.get_meta("phase", 0.0))
		var pulse: float = 1.0 + sin(_presentation_time * 2.7 + phase) * 0.055
		var pool: MeshInstance3D = root.get_node_or_null("Pool") as MeshInstance3D
		if pool != null:
			pool.scale = Vector3(pulse, 1.0, pulse)

		for spore_child: Node in root.get_children():
			if not spore_child.name.begins_with("Spore_"):
				continue
			var spore: MeshInstance3D = spore_child as MeshInstance3D
			if spore == null:
				continue

			var base_angle: float = float(spore.get_meta("base_angle", 0.0))
			var spore_index: int = int(spore.get_meta("spore_index", 0))
			var angle: float = base_angle + _presentation_time * (0.22 + float(spore_index) * 0.015)
			var radius: float = map_root.tile_size * (0.17 + 0.012 * float(spore_index % 2))
			spore.position.x = cos(angle) * radius
			spore.position.z = sin(angle) * radius
			spore.position.y = 0.06 + 0.055 * float(spore_index % 2) + sin(_presentation_time * 2.2 + base_angle) * 0.035


func _show_hazard_spawn_3d(cell_value: Vector2i) -> void:
	if map_root == null or not map_root.is_cell_valid(cell_value):
		return
	_show_skill_burst(cell_value, Color(0.70, 0.34, 0.92, 1.0))
	var position_value: Vector3 = map_root.cell_top_local(cell_value)
	_show_floating_text(
		position_value + Vector3(0.0, 0.74, 0.0),
		"NOUVELLES SPORES !",
		Color(0.86, 0.64, 1.0, 1.0)
	)


func _apply_terrain_hazard_end_3d(actor: SporeUnitActor3D) -> void:
	if actor == null or not actor.alive or not _hazard_cells_3d.has(actor.cell):
		return

	_show_skill_burst(actor.cell, Color(0.72, 0.36, 0.92, 1.0))
	var result: Dictionary = _apply_damage_with_reactions(
		null,
		actor,
		1,
		"spores",
		false,
		false,
		"spore"
	)
	var applied: int = int(result.get("applied", 0))
	_show_floating_text(
		actor.position + Vector3(0.0, 1.34, 0.0),
		"SPORES -%d PV" % applied,
		Color(0.86, 0.62, 1.0, 1.0)
	)
	_log(
		"%s subit %d dégât(s) de spores en fin d'activation."
		% [actor.display_name, applied]
	)


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
	_evaluate_mission_triggers_3d("round_start", null)


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
					_show_floating_text(actor.position + Vector3(0.0, 1.15, 0.0), "+%d PV" % healed, Color(0.48, 0.90, 0.66, 1.0))
				_spawn_feedback_burst(actor, Color(0.48, 0.90, 0.66, 1.0))
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


func _ensure_enemy_intent_root() -> Node3D:
	if _enemy_intent_root != null and is_instance_valid(_enemy_intent_root):
		return _enemy_intent_root

	_enemy_intent_root = Node3D.new()
	_enemy_intent_root.name = "EnemyIntentPreview"
	add_child(_enemy_intent_root)
	return _enemy_intent_root


func _clear_enemy_intent_preview() -> void:
	if _enemy_intent_root == null or not is_instance_valid(_enemy_intent_root):
		return
	for child: Node in _enemy_intent_root.get_children():
		child.queue_free()


func _enemy_intent_label(
	actor: SporeUnitActor3D,
	text_value: String,
	color: Color
) -> Label3D:
	var root: Node3D = _ensure_enemy_intent_root()
	var label: Label3D = Label3D.new()
	label.name = "IntentLabel"
	label.text = text_value
	label.font_size = 26
	label.outline_size = 9
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.modulate = color
	label.position = actor.position + Vector3(0.0, 1.72, 0.0)
	label.scale = Vector3(0.78, 0.78, 0.78)
	root.add_child(label)

	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(label, "scale", Vector3.ONE, 0.18)
	tween.tween_property(
		label,
		"position:y",
		label.position.y + 0.10,
		0.18
	)
	return label


func _enemy_intent_ring(
	cell_value: Vector2i,
	color: Color,
	radius_scale: float = 0.30
) -> MeshInstance3D:
	var root: Node3D = _ensure_enemy_intent_root()
	var marker: MeshInstance3D = MeshInstance3D.new()
	marker.name = "IntentRing_%d_%d" % [cell_value.x, cell_value.y]

	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = map_root.tile_size * radius_scale
	mesh.bottom_radius = map_root.tile_size * radius_scale
	mesh.height = 0.035
	marker.mesh = mesh
	marker.position = (
		map_root.cell_top_local(cell_value)
		+ Vector3(0.0, 0.070, 0.0)
	)

	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.emission_enabled = true
	material.emission = Color(color.r, color.g, color.b, 1.0)
	material.emission_energy_multiplier = 0.70
	marker.material_override = material

	root.add_child(marker)

	marker.scale = Vector3(0.55, 1.0, 0.55)
	var tween: Tween = create_tween()
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(
		marker,
		"scale",
		Vector3.ONE,
		0.20
	)
	return marker


func _show_enemy_move_intent(
	actor: SporeUnitActor3D,
	target: SporeUnitActor3D,
	path: Array[Vector2i]
) -> void:
	if actor == null or target == null or map_root == null:
		return

	_clear_enemy_intent_preview()
	_enemy_intent_label(
		actor,
		"SE DÉPLACE  →  %s" % target.display_name,
		Color(1.0, 0.76, 0.34, 1.0)
	)

	for index: int in range(1, path.size()):
		var path_cell: Vector2i = path[index]
		var color: Color = Color(1.0, 0.76, 0.30, 0.42)
		if index == path.size() - 1:
			color = Color(1.0, 0.88, 0.42, 0.78)
		_enemy_intent_ring(
			path_cell,
			color,
			0.14 if index < path.size() - 1 else 0.25
		)

	await get_tree().create_timer(0.46).timeout
	_clear_enemy_intent_preview()


func _show_enemy_attack_intent(
	actor: SporeUnitActor3D,
	target: SporeUnitActor3D
) -> void:
	if actor == null or target == null or not target.alive:
		return

	_clear_enemy_intent_preview()

	var details: Dictionary = _attack_damage_details(actor, target)
	var damage: int = maxi(
		0,
		int(details.get("damage", 0)) - target.flat_damage_reduction
	)
	var chance: int = clampi(
		int(details.get("hit_chance", 100)),
		0,
		100
	)
	var arc_name: String = _arc_display_name(
		String(details.get("arc", "front"))
	).to_upper()

	var intent_text: String = (
		"ATTAQUE  →  %s\n%d%%  •  ~%d dégâts  •  %s"
		% [
			target.display_name,
			chance,
			damage,
			arc_name
		]
	)

	_enemy_intent_label(
		actor,
		intent_text,
		Color(1.0, 0.50, 0.42, 1.0)
	)
	_enemy_intent_ring(
		target.cell,
		Color(1.0, 0.20, 0.16, 0.78),
		0.34
	)

	await get_tree().create_timer(0.50).timeout
	_clear_enemy_intent_preview()


func _show_enemy_skill_intent(
	actor: SporeUnitActor3D,
	action: Dictionary
) -> void:
	if actor == null or action.is_empty() or map_root == null:
		return

	var skill_id: String = String(action.get("skill_id", ""))
	var anchor_value: Variant = action.get("anchor", actor.cell)
	if skill_id.is_empty() or not (anchor_value is Vector2i):
		return

	var skill: Resource = SkillCatalog.definition(skill_id)
	if skill == null:
		return

	var anchor_cell: Vector2i = anchor_value
	_clear_enemy_intent_preview()

	var target_actor: SporeUnitActor3D = (
		actors_by_cell.get(anchor_cell, null)
		as SporeUnitActor3D
	)
	var destination_text: String = "ZONE"
	if target_actor != null:
		destination_text = target_actor.display_name

	var cast_ticks: int = int(skill.get("cast_time_ticks"))
	var timing_text: String = (
		"préparation %d" % cast_ticks
		if cast_ticks > 0
		else "immédiat"
	)

	_enemy_intent_label(
		actor,
		"%s  →  %s\n%s"
		% [
			String(skill.get("display_name")).to_upper(),
			destination_text,
			timing_text
		],
		Color(0.76, 0.58, 1.0, 1.0)
	)

	var area_cells: Array[Vector2i] = _skill_area_cells(
		skill,
		anchor_cell,
		actor.cell
	)
	if area_cells.is_empty():
		area_cells.append(anchor_cell)

	for area_cell: Vector2i in area_cells:
		if not map_root.is_cell_valid(area_cell):
			continue
		var area_actor: SporeUnitActor3D = (
			actors_by_cell.get(area_cell, null)
			as SporeUnitActor3D
		)
		var color: Color = Color(0.72, 0.42, 1.0, 0.34)
		if area_actor != null:
			color = (
				Color(1.0, 0.30, 0.26, 0.68)
				if area_actor.team != actor.team
				else Color(0.42, 0.88, 0.68, 0.58)
			)
		_enemy_intent_ring(area_cell, color, 0.26)

	await get_tree().create_timer(0.54).timeout
	_clear_enemy_intent_preview()


func _execute_enemy_activation() -> void:
	if battle_finished or active_actor == null or not active_actor.alive or active_actor.team != "enemy":
		enemy_busy = false
		return
	await get_tree().create_timer(0.46).timeout
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
		await _show_enemy_skill_intent(active_actor, skill_action)
		await _enemy_use_skill(skill_action)
	elif not active_actor.acted_this_activation and _is_in_attack_range(active_actor, target):
		await _show_enemy_attack_intent(active_actor, target)
		await _enemy_attack(target)

	# FFT allows Act -> Move as well as Move -> Act. Reposition whenever Move is still available.
	if active_actor.alive and not active_actor.moved_this_activation:
		target = _best_target_for(active_actor, player_actors)
		if target != null:
			var destination: Vector2i = _best_enemy_destination(active_actor, target)
			var path: Array[Vector2i] = _reconstruct_path(destination)
			if destination != active_actor.cell and path.size() >= 2:
				await _show_enemy_move_intent(active_actor, target, path)
				var ai_move_start: Vector2i = active_actor.cell
				actors_by_cell.erase(active_actor.cell)
				_log("%s avance vers %s." % [active_actor.display_name, target.display_name])
				await _move_actor_along_path(active_actor, path, 0.17)
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
			await _show_enemy_skill_intent(active_actor, skill_action)
			await _enemy_use_skill(skill_action)
		elif target != null and target.alive and _is_in_attack_range(active_actor, target):
			await _show_enemy_attack_intent(active_actor, target)
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
	var enemy_vfx_kind: String = _basic_attack_vfx_kind(active_actor)
	await _play_action_vfx_to_impact(
		active_actor.basic_attack_vfx_id,
		active_actor.global_position + Vector3(0.0, 0.72, 0.0),
		target.global_position + Vector3(0.0, 0.64, 0.0),
		false,
		target,
		Vector3(0.0, 0.64, 0.0),
		enemy_vfx_kind
	)
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
	_show_skill_name_banner(active_actor, skill)
	var primary_vfx_kind: String = _skill_primary_vfx_kind(String(skill.get("id")))
	await _play_action_vfx_to_impact(
		String(skill.get("vfx_id")),
		active_actor.global_position + Vector3(0.0, 0.78, 0.0),
		anchor_global + Vector3(0.0, 0.18, 0.0),
		false,
		tracked_skill_target,
		tracked_skill_offset,
		primary_vfx_kind
	)
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
			_evaluate_mission_triggers_3d("unit_moved", actor)
			if _mission_event_pending_3d():
				await _wait_for_mission_events_3d()
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
		_play_terrain_feedback_3d(actor, from_cell, step_cell)
	if _threat_overlay_enabled:
		_rebuild_enemy_threat_cache()
		_rebuild_highlights()
	_evaluate_mission_triggers_3d("unit_moved", actor)
	if _mission_event_pending_3d():
		await _wait_for_mission_events_3d()


func _play_terrain_feedback_3d(
	actor: SporeUnitActor3D,
	from_cell: Vector2i,
	to_cell: Vector2i
) -> void:
	if map_root == null or actor == null:
		return
	var tile: Node = map_root.tile_at(to_cell)
	var terrain_type: String = String(tile.get("terrain_type")) if tile != null else "ground"
	var elevation_delta: int = map_root.elevation_at(to_cell) - map_root.elevation_at(from_cell)
	var world_position: Vector3 = map_root.to_global(map_root.cell_top_local(to_cell))
	var candidates: Array[Node] = get_tree().get_nodes_in_group("spore_terrain_feedback")
	for candidate: Node in candidates:
		if candidate == null or not is_instance_valid(candidate):
			continue
		if candidate != map_root and not map_root.is_ancestor_of(candidate):
			continue
		if candidate.has_method("play_step_feedback"):
			candidate.call("play_step_feedback", terrain_type, world_position, elevation_delta, actor.team)
			return


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


func _update_battle_end_presentation() -> void:
	if not battle_finished or _battle_end_sequence_started:
		return
	_battle_end_sequence_started = true
	call_deferred("_run_battle_end_sequence", _infer_battle_victory())


func _infer_battle_victory() -> bool:
	var living_players: int = 0
	var living_enemies: int = 0
	for actor: SporeUnitActor3D in player_actors:
		if actor != null and actor.alive:
			living_players += 1
	for actor: SporeUnitActor3D in enemy_actors:
		if actor != null and actor.alive:
			living_enemies += 1
	if living_players <= 0:
		return false
	if living_enemies <= 0:
		return true
	# Custom mission objective completed while enemies remain.
	return true


func _run_battle_end_sequence(victory: bool) -> void:
	_facing_selection_active = false
	if _facing_panel != null and is_instance_valid(_facing_panel):
		_facing_panel.visible = false

	enemy_busy = false
	player_busy = true
	_clear_overlays()

	var focus_actors: Array[SporeUnitActor3D] = []
	for actor: SporeUnitActor3D in player_actors:
		if actor != null and actor.alive:
			focus_actors.append(actor)

	var focus: Vector3 = Vector3.ZERO
	if not focus_actors.is_empty():
		for actor: SporeUnitActor3D in focus_actors:
			focus += actor.position
		focus /= float(focus_actors.size())
	elif active_actor != null:
		focus = active_actor.position

	_camera_focus_target = Vector3(focus.x, 0.0, focus.z)
	_action_camera_timer = 0.0
	_impact_zoom_timer = 0.0
	_camera_shake_strength = 0.0

	if victory:
		_camera_target_distance = clampf(camera_distance - 1.8, zoom_min, zoom_max)
		for actor: SporeUnitActor3D in focus_actors:
			_spawn_victory_spores(actor.position)
	else:
		_camera_target_distance = clampf(camera_distance + 0.8, zoom_min, zoom_max)

	await get_tree().create_timer(0.42).timeout
	_show_floating_text(
		focus + Vector3(0.0, 1.75, 0.0),
		"VICTOIRE !" if victory else "DÉFAITE",
		Color(1.0, 0.84, 0.34, 1.0) if victory else Color(1.0, 0.42, 0.38, 1.0)
	)
	await get_tree().create_timer(0.72).timeout
	_show_battle_result(victory)


func _spawn_victory_spores(origin: Vector3) -> void:
	if _actor_holder == null:
		return
	var root: Node3D = Node3D.new()
	root.name = "VictorySpores"
	root.position = origin + Vector3(0.0, 0.25, 0.0)
	_actor_holder.add_child(root)

	for index: int in range(12):
		var spark: MeshInstance3D = MeshInstance3D.new()
		var mesh: SphereMesh = SphereMesh.new()
		mesh.radius = 0.045 + 0.010 * float(index % 3)
		mesh.height = mesh.radius * 2.0
		mesh.radial_segments = 8
		mesh.rings = 4
		spark.mesh = mesh

		var color: Color = Color(1.0, 0.82, 0.32, 0.92)
		if index % 3 == 1:
			color = Color(0.44, 0.92, 0.62, 0.92)
		elif index % 3 == 2:
			color = Color(0.42, 0.82, 1.0, 0.92)

		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = color
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled = true
		material.emission = Color(color.r, color.g, color.b, 1.0)
		material.emission_energy_multiplier = 1.4
		spark.material_override = material

		var angle: float = TAU * float(index) / 12.0
		spark.position = Vector3(cos(angle) * 0.18, 0.05, sin(angle) * 0.18)
		root.add_child(spark)

		var target: Vector3 = Vector3(
			cos(angle) * (0.70 + 0.10 * float(index % 4)),
			0.75 + 0.08 * float(index % 5),
			sin(angle) * (0.70 + 0.10 * float(index % 4))
		)
		var tween: Tween = create_tween()
		tween.set_parallel(true)
		tween.set_trans(Tween.TRANS_SINE)
		tween.set_ease(Tween.EASE_OUT)
		tween.tween_property(spark, "position", target, 0.82)
		tween.tween_property(spark, "scale", Vector3.ONE * 1.35, 0.36)
		tween.set_parallel(false)
		tween.tween_callback(Callable(spark, "queue_free"))

	await get_tree().create_timer(0.95).timeout
	if is_instance_valid(root):
		root.queue_free()


func _show_battle_result(victory: bool) -> void:
	if _ui_layer == null:
		return
	var root: Control = _ui_layer.get_node_or_null("Root") as Control
	if root == null:
		return

	var previous: Node = root.get_node_or_null("BattleResult")
	if previous != null:
		previous.queue_free()

	var overlay: ColorRect = ColorRect.new()
	overlay.name = "BattleResult"
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.color = Color(0.015, 0.022, 0.034, 0.84)
	overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	overlay.modulate = Color(1.0, 1.0, 1.0, 0.0)
	root.add_child(overlay)

	var panel: Panel = Panel.new()
	panel.size = Vector2(520.0, 260.0)
	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	panel.position = (viewport_size - panel.size) * 0.5
	panel.pivot_offset = panel.size * 0.5
	panel.scale = Vector2(0.86, 0.86)

	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.045, 0.060, 0.085, 0.985)
	style.border_color = Color(1.0, 0.80, 0.30, 1.0) if victory else Color(1.0, 0.38, 0.34, 1.0)
	style.border_width_left = 2
	style.border_width_top = 2
	style.border_width_right = 2
	style.border_width_bottom = 2
	style.corner_radius_top_left = 18
	style.corner_radius_top_right = 18
	style.corner_radius_bottom_left = 18
	style.corner_radius_bottom_right = 18
	panel.add_theme_stylebox_override("panel", style)
	overlay.add_child(panel)

	var title: Label = Label.new()
	title.position = Vector2(24.0, 24.0)
	title.size = Vector2(472.0, 50.0)
	title.text = "VICTOIRE !" if victory else "DÉFAITE"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 34)
	title.add_theme_color_override(
		"font_color",
		Color(1.0, 0.86, 0.38, 1.0) if victory else Color(1.0, 0.50, 0.46, 1.0)
	)
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(title)

	var survivors: int = 0
	for actor: SporeUnitActor3D in player_actors:
		if actor != null and actor.alive:
			survivors += 1

	var body: Label = Label.new()
	body.position = Vector2(40.0, 88.0)
	body.size = Vector2(440.0, 78.0)
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_font_size_override("font_size", 16)
	body.add_theme_color_override("font_color", Color(0.92, 0.94, 0.90, 1.0))
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.text = (
		"Mission accomplie.\n%d membre(s) de l'escouade encore debout." % survivors
		if victory
		else "L'escouade a été mise hors combat.\nAdapte ton placement et retente la mission."
	)
	panel.add_child(body)

	var replay: Button = Button.new()
	replay.text = "REJOUER  [R]"
	replay.position = Vector2(150.0, 190.0)
	replay.size = Vector2(220.0, 44.0)
	replay.add_theme_font_size_override("font_size", 16)
	replay.pressed.connect(func() -> void: get_tree().reload_current_scene())
	panel.add_child(replay)

	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(overlay, "modulate", Color.WHITE, 0.30)
	tween.tween_property(panel, "scale", Vector2.ONE, 0.42)


func _check_battle_end() -> bool:
	if battle_finished:
		return true

	var result: int = _mission_result_3d()

	if result > 0:
		battle_finished = true

		if mission_objective_3d == "crown":
			_log(
				"VICTOIRE — la Couronne est extraite ! "
				+ "Vinyles %d/%d."
				% [
					bonus_collected_3d,
					bonus_target_total_3d
				]
			)
		else:
			_log("VICTOIRE — objectif de mission accompli !")

	elif result < 0:
		battle_finished = true
		_log("DÉFAITE — l'escouade est K.O.")

	if battle_finished:
		enemy_busy = false
		player_busy = false
		_clear_overlays()

		if active_actor != null:
			active_actor.end_activation()

		_refresh_objective_ui_3d(true)
		_update_ui_text()

	if (
		not battle_finished
		and mission_objective_3d == "crown"
		and _living_count_3d("enemy") <= 0
		and not _enemies_cleared_objective_hint_3d
	):
		_enemies_cleared_objective_hint_3d = true
		_log(
			"Tous les ennemis sont K.O., "
			+ "mais il faut encore extraire la Couronne."
		)

	return battle_finished


func _cell_player_description(cell_value: Vector2i) -> String:
	if map_root == null or not map_root.is_cell_valid(cell_value):
		return "Hors plateau"

	var terrain_name: String = "Forêt"
	var tile: Node = map_root.tile_at(cell_value)
	if tile != null:
		var terrain_type: String = String(tile.get("terrain_type"))
		match terrain_type:
			"obstacle":
				terrain_name = "Obstacle"
			"cover":
				terrain_name = "Couvert"
			"hazard":
				terrain_name = "Spores dangereuses"
			"extraction":
				terrain_name = "Sortie"
			"bonus":
				terrain_name = "Vinyle bonus"
			"crown":
				terrain_name = "Couronne"
			_:
				terrain_name = "Forêt"

	var height_value: int = map_root.elevation_at(cell_value)
	if height_value > 0:
		terrain_name += " • hauteur %d" % height_value

	var occupant: SporeUnitActor3D = actors_by_cell.get(cell_value, null) as SporeUnitActor3D
	if occupant != null and occupant.alive:
		terrain_name += " • %s" % occupant.display_name
	return terrain_name


func _show_battle_result(victory: bool) -> void:
	if _ui_layer == null:
		return
	var root: Control = _ui_layer.get_node_or_null("Root") as Control
	if root == null:
		return

	var previous: Node = root.get_node_or_null("BattleResult")
	if previous != null:
		previous.queue_free()

	var overlay: ColorRect = ColorRect.new()
	overlay.name = "BattleResult"
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.color = Color(0.02, 0.03, 0.045, 0.82)
	overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	overlay.modulate = Color(1.0, 1.0, 1.0, 0.0)
	root.add_child(overlay)

	var panel: Panel = Panel.new()
	panel.size = Vector2(500.0, 240.0)
	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	panel.position = (viewport_size - panel.size) * 0.5
	panel.pivot_offset = panel.size * 0.5
	panel.scale = Vector2(0.84, 0.84)

	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.055, 0.075, 0.105, 0.98)
	style.border_color = Color(1.0, 0.78, 0.30, 1.0) if victory else Color(0.90, 0.30, 0.30, 1.0)
	style.border_width_left = 2
	style.border_width_top = 2
	style.border_width_right = 2
	style.border_width_bottom = 2
	style.corner_radius_top_left = 18
	style.corner_radius_top_right = 18
	style.corner_radius_bottom_left = 18
	style.corner_radius_bottom_right = 18
	panel.add_theme_stylebox_override("panel", style)
	overlay.add_child(panel)

	var title: Label = _make_label(
		panel,
		Vector2(24.0, 24.0),
		Vector2(452.0, 52.0),
		34,
		Color(1.0, 0.84, 0.38, 1.0) if victory else Color(1.0, 0.48, 0.44, 1.0)
	)
	title.text = "VICTOIRE !" if victory else "DÉFAITE"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

	var body: Label = _make_label(
		panel,
		Vector2(32.0, 84.0),
		Vector2(436.0, 62.0),
		16,
		Color(0.92, 0.94, 0.90, 1.0)
	)
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.text = (
		"Mission accomplie. L'escouade contrôle le terrain."
		if victory
		else
		"L'escouade a été mise hors combat."
	)

	var replay: Button = _make_button(
		panel,
		"REJOUER [R]",
		Vector2(150.0, 166.0),
		Vector2(200.0, 44.0)
	)
	replay.pressed.connect(func() -> void: get_tree().reload_current_scene())

	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(overlay, "modulate", Color.WHITE, 0.32)
	tween.tween_property(panel, "scale", Vector2.ONE, 0.42)


func _ensure_hover_forecast_label() -> void:
	if _hover_forecast_label != null and is_instance_valid(_hover_forecast_label):
		return
	if _actor_holder == null:
		return

	_hover_forecast_label = Label3D.new()
	_hover_forecast_label.name = "HoverForecast"
	_hover_forecast_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_hover_forecast_label.no_depth_test = true
	_hover_forecast_label.font_size = 24
	_hover_forecast_label.outline_size = 8
	_hover_forecast_label.modulate = Color(1.0, 0.96, 0.78, 1.0)
	_hover_forecast_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hover_forecast_label.visible = false
	_actor_holder.add_child(_hover_forecast_label)


func _update_tactical_hover_forecast() -> void:
	_ensure_hover_forecast_label()
	if _hover_forecast_label == null:
		return

	if (
		battle_finished
		or map_root == null
		or active_actor == null
		or not map_root.is_cell_valid(hovered_cell)
	):
		_hover_forecast_label.visible = false
		return

	var text_value: String = ""
	var color: Color = Color(1.0, 0.96, 0.78, 1.0)
	var world_position: Vector3 = (
		map_root.cell_top_local(hovered_cell)
		+ Vector3(0.0, 1.05, 0.0)
	)

	if input_mode == MODE_ATTACK and not active_actor.acted_this_activation:
		var target: SporeUnitActor3D = (
			actors_by_cell.get(hovered_cell, null)
			as SporeUnitActor3D
		)
		if (
			target != null
			and target.alive
			and target.team != active_actor.team
			and attack_cells.has(hovered_cell)
		):
			var details: Dictionary = _attack_damage_details(
				active_actor,
				target
			)
			var damage: int = maxi(0, int(details.get("damage", 0)))
			var hit_chance: int = clampi(
				int(details.get("hit_chance", 0)),
				0,
				100
			)
			var hp_after: int = maxi(0, target.hp - damage)
			var arc_text: String = _arc_display_name(
				String(details.get("arc", "front"))
			).to_upper()

			text_value = (
				"%d%%  •  -%d PV  •  %s\n"
				+ "%s  %d → %d PV%s"
			) % [
				hit_chance,
				damage,
				arc_text,
				target.display_name,
				target.hp,
				hp_after,
				"  • K.O." if hp_after <= 0 else ""
			]

			if int(details.get("cover_reduction", 0)) > 0:
				text_value += "\nCouvert : dégâts réduits"

			var interceptor: SporeUnitActor3D = _find_interceptor(
				active_actor,
				target
			)
			if interceptor != null:
				text_value += "\nInterception : %s" % interceptor.display_name

			color = (
				Color(1.0, 0.52, 0.46, 1.0)
				if hp_after > 0
				else Color(1.0, 0.82, 0.34, 1.0)
			)
			world_position = target.position + Vector3(0.0, 1.62, 0.0)

	elif input_mode == MODE_MOVE and not active_actor.moved_this_activation:
		if reachable_cells.has(hovered_cell):
			var path: Array[Vector2i] = _reconstruct_path(hovered_cell)
			var steps: int = maxi(0, path.size() - 1)
			var terrain: String = _hover_terrain_name(hovered_cell)
			text_value = "%d case(s)  •  %s" % [steps, terrain]
			color = Color(0.60, 0.94, 0.72, 1.0)

			if _enemy_threatens_cell(hovered_cell):
				text_value += "\n⚠ case menacée"
				color = Color(1.0, 0.78, 0.42, 1.0)

	elif (
		input_mode == MODE_SKILL
		and not selected_skill_id.is_empty()
		and skill_target_cells.has(hovered_cell)
	):
		var skill: Resource = SkillCatalog.definition(selected_skill_id)
		if skill != null:
			var target_count: int = _skill_preview_actor_count(
				active_actor,
				skill,
				hovered_cell
			)
			var cost: int = int(skill.get("focus_cost"))
			var skill_name: String = String(skill.get("display_name"))
			text_value = (
				"%s\n%d MP  •  %d cible(s)"
				% [skill_name, cost, target_count]
			)
			var cast_ticks: int = int(skill.get("cast_time_ticks"))
			if cast_ticks > 0:
				text_value += "\nPréparation : %d" % cast_ticks
			else:
				text_value += "\nImmédiat"
			color = Color(0.78, 0.66, 1.0, 1.0)

	else:
		var hovered_actor: SporeUnitActor3D = (
			actors_by_cell.get(hovered_cell, null)
			as SporeUnitActor3D
		)
		if hovered_actor != null and hovered_actor.alive:
			text_value = "%s  •  %d/%d PV" % [
				hovered_actor.display_name,
				hovered_actor.hp,
				hovered_actor.max_hp
			]
			color = (
				Color(0.70, 0.90, 1.0, 1.0)
				if hovered_actor.team == "player"
				else Color(1.0, 0.70, 0.62, 1.0)
			)
			world_position = (
				hovered_actor.position
				+ Vector3(0.0, 1.55, 0.0)
			)
		else:
			text_value = _hover_terrain_name(hovered_cell)
			color = Color(0.88, 0.90, 0.78, 1.0)

	_hover_forecast_label.text = text_value
	_hover_forecast_label.modulate = color
	_hover_forecast_label.position = world_position
	_hover_forecast_label.visible = not text_value.is_empty()


func _hover_terrain_name(cell_value: Vector2i) -> String:
	if map_root == null or not map_root.is_cell_valid(cell_value):
		return "Hors plateau"

	var tile: Node = map_root.tile_at(cell_value)
	if tile == null:
		return "Terrain"

	var terrain_type: String = String(tile.get("terrain_type"))
	var result: String = "Forêt"

	match terrain_type:
		"obstacle":
			result = "Obstacle"
		"cover":
			result = "Couvert"
		"hazard":
			result = "Spores dangereuses"
		"extraction":
			result = "Sortie"
		"bonus":
			result = "Vinyle bonus"
		"crown":
			result = "Couronne"
		_:
			result = "Forêt"

	var elevation_value: int = map_root.elevation_at(cell_value)
	if elevation_value > 0:
		result += " • hauteur %d" % elevation_value

	if terrain_type == "cover":
		result += " • protège %s" % _cover_facing_name(cell_value)

	return result


func _toggle_enemy_threat_overlay() -> void:
	_threat_overlay_enabled = not _threat_overlay_enabled
	_rebuild_enemy_threat_cache()
	_rebuild_highlights()

	var text_value: String = (
		"MENACES ENNEMIES : ON"
		if _threat_overlay_enabled
		else "MENACES ENNEMIES : OFF"
	)
	var color: Color = (
		Color(1.0, 0.62, 0.48, 1.0)
		if _threat_overlay_enabled
		else Color(0.78, 0.82, 0.86, 1.0)
	)

	if active_actor != null:
		_show_floating_text(
			active_actor.position + Vector3(0.0, 1.45, 0.0),
			text_value,
			color
		)


func _rebuild_enemy_threat_cache() -> void:
	_threat_cells_cache.clear()

	if not _threat_overlay_enabled or map_root == null:
		return

	for enemy: SporeUnitActor3D in enemy_actors:
		if enemy == null or not enemy.alive:
			continue

		var max_range: int = maxi(
			1,
			enemy.attack_range
			+ enemy.status_modifier("range_delta")
		)

		for y: int in range(map_root.grid_height):
			for x: int in range(map_root.grid_width):
				var cell_value: Vector2i = Vector2i(x, y)
				var distance: int = _cell_distance(
					enemy.cell,
					cell_value
				)

				if not CombatMechanics.range_allowed(
					distance,
					enemy.attack_min_range,
					max_range
				):
					continue

				if (
					absi(
						map_root.elevation_at(enemy.cell)
						- map_root.elevation_at(cell_value)
					)
					> height_attack_tolerance
				):
					continue

				if not _has_line_of_sight(enemy.cell, cell_value):
					continue

				var count: int = int(
					_threat_cells_cache.get(cell_value, 0)
				)
				_threat_cells_cache[cell_value] = count + 1


func _enemy_threatens_cell(cell_value: Vector2i) -> bool:
	# Compute on demand even when the global overlay is hidden.
	if _threat_overlay_enabled:
		return _threat_cells_cache.has(cell_value)

	if map_root == null:
		return false

	for enemy: SporeUnitActor3D in enemy_actors:
		if enemy == null or not enemy.alive:
			continue

		var max_range: int = maxi(
			1,
			enemy.attack_range
			+ enemy.status_modifier("range_delta")
		)
		var distance: int = _cell_distance(enemy.cell, cell_value)

		if not CombatMechanics.range_allowed(
			distance,
			enemy.attack_min_range,
			max_range
		):
			continue

		if not _has_line_of_sight(enemy.cell, cell_value):
			continue

		if (
			absi(
				map_root.elevation_at(enemy.cell)
				- map_root.elevation_at(cell_value)
			)
			> height_attack_tolerance
		):
			continue

		return true

	return false


func _rebuild_highlights() -> void:
	for child: Node in _highlight_holder.get_children():
		child.queue_free()
	if _threat_overlay_enabled:
		if _threat_cells_cache.is_empty():
			_rebuild_enemy_threat_cache()
		for threat_cell_var: Variant in _threat_cells_cache.keys():
			if not (threat_cell_var is Vector2i):
				continue
			var threat_cell: Vector2i = threat_cell_var
			var threat_count: int = int(
				_threat_cells_cache.get(threat_cell, 1)
			)
			var threat_alpha: float = minf(
				0.34,
				0.14 + float(threat_count - 1) * 0.06
			)
			_add_cell_highlight(
				threat_cell,
				Color(1.0, 0.18, 0.14, threat_alpha),
				0.36
			)
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
			cell_text = _cell_player_description(hovered_cell)
			if _is_cover_cell(hovered_cell):
				cell_text += " • protège côté %s" % _cover_facing_name(hovered_cell)
			var zone_count: int = _persistent_zone_count_at(hovered_cell)
			if zone_count > 0:
				cell_text += " • effet au sol x%d" % zone_count
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
				extra_text = " • %s • %d dégâts • réussite %d%%" % [_arc_display_name(arc), int(details.get("damage", 0)), int(details.get("hit_chance", 0))]
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
			_info_label.text = "%s • %d/%d PV • %d/%d MP • Vitesse %d • %s%s\n%s%s" % [active_actor.display_name, active_actor.hp, active_actor.max_hp, active_actor.focus, active_actor.max_focus, active_actor.effective_speed(), mode_text, cast_suffix, cell_text, extra_text]
		else:
			_info_label.text = "Case survolée : %s" % cell_text
	_help_label.text = "Boucle FFT : 1 Move + 1 Act dans l’ordre voulu • F choisit l’orientation • Espace = Wait/Fin • Vert déplacement • Rouge attaque • Violet skill • Entrée confirmer • Échap annuler • Q/E caméra • molette zoom • C recentrer • T menaces • R recommencer"
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
		_log_label.text = _recent_log_text(3)


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

		var card := Panel.new()
		card.custom_minimum_size = Vector2(50.0, 48.0)
		card.mouse_filter = Control.MOUSE_FILTER_IGNORE

		var card_style := StyleBoxFlat.new()
		card_style.bg_color = Color(0.035, 0.038, 0.045, 0.98)
		card_style.border_width_left = 2
		card_style.border_width_top = 2
		card_style.border_width_right = 2
		card_style.border_width_bottom = 2
		card_style.border_color = Color(0.12, 0.58, 0.92, 1.0) if actor.team == "player" else Color(0.88, 0.18, 0.15, 1.0)
		if actor == active_actor:
			card_style.border_width_left = 3
			card_style.border_width_top = 3
			card_style.border_width_right = 3
			card_style.border_width_bottom = 3
			card_style.border_color = Color(1.0, 0.80, 0.16, 1.0)
		card_style.corner_radius_top_left = 2
		card_style.corner_radius_top_right = 2
		card_style.corner_radius_bottom_left = 2
		card_style.corner_radius_bottom_right = 2
		card.add_theme_stylebox_override("panel", card_style)

		var portrait := TextureRect.new()
		portrait.position = Vector2(7.0, 3.0)
		portrait.size = Vector2(36.0, 29.0)
		portrait.texture = actor.portrait_texture()
		portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(portrait)

		var name_label := Label.new()
		name_label.position = Vector2(2.0, 31.0)
		name_label.size = Vector2(46.0, 15.0)
		name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		name_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		name_label.add_theme_font_size_override("font_size", 9)
		name_label.add_theme_color_override("font_color", Color(0.98, 0.97, 0.92, 1.0))
		name_label.text = actor.display_name.substr(0, mini(3, actor.display_name.length())).to_upper()
		name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(name_label)

		card.tooltip_text = "%s • CT %d • VIT %d%s" % [
			actor.display_name,
			actor.ct,
			actor.effective_speed(),
			" • CAST" if actor.is_casting() else ""
		]
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

	_unit_card_title.text = "%s  •  %s" % [
		actor.display_name,
		"ALLIÉ" if actor.team == "player" else "ENNEMI"
	]

	if _unit_portrait != null and actor != _unit_card_last_actor:
		_unit_portrait.texture = actor.portrait_texture()
	_unit_card_last_actor = actor

	if _unit_hp_bar != null:
		_unit_hp_bar.max_value = maxi(1, actor.max_hp)
		_unit_hp_bar.value = actor.hp
		_unit_hp_bar.tooltip_text = "PV %d / %d" % [actor.hp, actor.max_hp]

	if _unit_focus_bar != null:
		_unit_focus_bar.max_value = maxi(1, actor.max_focus)
		_unit_focus_bar.value = actor.focus
		_unit_focus_bar.tooltip_text = "MP %d / %d" % [actor.focus, actor.max_focus]

	if _unit_hp_text_label != null:
		_unit_hp_text_label.text = "PV  %d / %d" % [actor.hp, actor.max_hp]
	if _unit_mp_text_label != null:
		_unit_mp_text_label.text = "MP  %d / %d" % [actor.focus, actor.max_focus]

	var status_text: String = actor.status_display_text()
	if status_text.is_empty():
		status_text = "Aucun statut"

	var casting_text: String = ""
	if actor.is_casting():
		casting_text = "\nPrépare : %s (%d)" % [
			SkillCatalog.display_name(String(actor.casting.get("skill_id", ""))),
			maxi(0, int(actor.casting.get("remaining_ticks", 0)))
		]

	_unit_card_body.text = (
		"ATQ phys. %d • mag. %d\n"
		+ "DEF phys. %d • mag. %d\n"
		+ "Arme %s • Portée %d-%d\nMVT %d • Vitesse %d\n"
		+ "Orientation %s • %s%s"
	) % [
		actor.effective_physical_power(),
		actor.effective_magic_power(),
		actor.effective_physical_defense(),
		actor.effective_magic_defense(),
		_weapon_family_display_name(actor.weapon_family),
		actor.attack_min_range,
		actor.attack_range,
		actor.effective_move_range(),
		actor.effective_speed(),
		actor.facing_name(),
		status_text,
		casting_text
	]


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
	return "%s %s • %d MP" % [
		slot_label,
		String(skill.get("display_name")),
		int(skill.get("focus_cost"))
	]


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
		return "Cible invalide."

	var lines: PackedStringArray = PackedStringArray()
	var description: String = String(skill.get("description"))
	if not description.is_empty():
		lines.append(description)

	lines.append("Coût : %d MP" % int(skill.get("focus_cost")))

	var cast_ticks: int = int(skill.get("cast_time_ticks"))
	if cast_ticks > 0:
		lines.append(
			"Déclenchement : différé — la compétence partira après %d temps de préparation."
			% cast_ticks
		)
	else:
		lines.append("Déclenchement : immédiat.")

	var target_actor: SporeUnitActor3D = actors_by_cell.get(anchor_cell, null) as SporeUnitActor3D
	var area_cells: Array[Vector2i] = _skill_area_cells(skill, anchor_cell, caster.cell)
	if target_actor != null:
		lines.append(
			"Cible : %s (%s)"
			% [
				target_actor.display_name,
				"allié" if target_actor.team == caster.team else "ennemi"
			]
		)
	elif area_cells.size() > 1:
		lines.append("Zone visée : %d cases." % area_cells.size())
	else:
		lines.append("Case visée : %s." % _cell_player_description(anchor_cell))

	# Explain status effects in human language instead of only displaying the ID/name.
	var raw_effects: Variant = skill.get("effects")
	if raw_effects is Array:
		for effect_var: Variant in raw_effects:
			if not (effect_var is Resource):
				continue
			var effect: Resource = effect_var as Resource
			if String(effect.get("effect_type")) != "status":
				continue
			var status_id: String = String(effect.get("status_id"))
			var status: Resource = StatusCatalog.definition(status_id)
			if status == null:
				continue
			var status_name: String = String(status.get("display_name"))
			var status_description: String = String(status.get("description"))
			lines.append(
				"Effet : %s%s"
				% [
					status_name,
					" — " + status_description if not status_description.is_empty() else ""
				]
			)

	var previews: Dictionary = _skill_target_previews(caster, skill, anchor_cell)
	var ordered_targets: Array = previews.keys()
	ordered_targets.sort_custom(
		func(a: Variant, b: Variant) -> bool:
			return String((a as SporeUnitActor3D).display_name) < String((b as SporeUnitActor3D).display_name)
	)

	if ordered_targets.is_empty():
		lines.append("Aucune unité n'est actuellement affectée.")
		return "\n".join(lines)

	for target_var: Variant in ordered_targets:
		var target: SporeUnitActor3D = target_var as SporeUnitActor3D
		if target == null:
			continue
		var data: Dictionary = previews[target]
		var pieces: PackedStringArray = PackedStringArray()

		if target.team != caster.team and bool(skill.get("uses_accuracy")):
			pieces.append("%d%% de réussite" % int(data.get("hit_chance", 100)))

		var recipient: SporeUnitActor3D = data.get("recipient", target) as SporeUnitActor3D
		if recipient == null:
			recipient = target

		var damage: int = int(data.get("damage", 0))
		if damage > 0:
			var after_damage: int = maxi(0, recipient.hp - damage)
			pieces.append(
				"%d dégâts : %d → %d PV%s"
				% [
					damage,
					recipient.hp,
					after_damage,
					" • K.O." if after_damage <= 0 else ""
				]
			)

		var heal_value: int = int(data.get("heal", 0))
		if heal_value > 0:
			var healed_after: int = mini(target.max_hp, target.hp + heal_value)
			pieces.append("+%d PV : %d → %d" % [healed_after - target.hp, target.hp, healed_after])

		var revive_value: int = int(data.get("revive", 0))
		if revive_value > 0 and target.downed:
			pieces.append("relève avec %d PV" % revive_value)

		if bool(data.get("guard", false)):
			pieces.append("donne Garde")
		if bool(data.get("reaction", false)):
			pieces.append("réactive la réaction")

		var displacement: String = String(data.get("displacement", ""))
		if not displacement.is_empty():
			pieces.append(displacement)

		lines.append(
			"• %s : %s"
			% [
				target.display_name,
				", ".join(pieces) if not pieces.is_empty() else "effet appliqué"
			]
		)

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


func _skill_primary_vfx_kind(skill_id: String) -> String:
	match skill_id:
		"heal":
			return "heal_bloom_fx"
		"mist":
			return "mist_field"
		"mark":
			return "mark_target"
		"taunt":
			return "taunt_wave"
		"flare":
			return "prism_shot"
		"prism_lance":
			return "beam"
		"hat":
			return "slash"
	return ""


func _skill_area_vfx_kind(skill_id: String) -> String:
	match skill_id:
		"mist":
			return "mist_field"
		"prism_lance":
			return "cross"
		"taunt":
			return "burst"
	return "burst"


func _show_skill_name_banner(actor: SporeUnitActor3D, skill: Resource) -> void:
	if actor == null or skill == null or _actor_holder == null:
		return

	var label: Label3D = Label3D.new()
	label.text = String(skill.get("display_name"))
	label.font_size = 32
	label.outline_size = 9
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.modulate = Color(1.0, 0.88, 0.50, 1.0)
	label.position = actor.position + Vector3(0.0, 1.72, 0.0)
	label.scale = Vector3(0.74, 0.74, 0.74)
	_actor_holder.add_child(label)

	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(label, "position:y", label.position.y + 0.22, 0.28)
	tween.tween_property(label, "scale", Vector3.ONE, 0.22)
	tween.set_parallel(false)
	tween.tween_interval(0.30)
	tween.set_parallel(true)
	tween.tween_property(label, "position:y", label.position.y + 0.18, 0.26)
	tween.tween_property(
		label,
		"modulate",
		Color(1.0, 0.88, 0.50, 0.0),
		0.26
	)
	tween.set_parallel(false)
	tween.tween_callback(Callable(label, "queue_free"))


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
		var area_vfx_kind: String = _skill_area_vfx_kind(String(skill.get("id")))
		_spawn_action_vfx(
			vfx_id,
			world_position,
			world_position,
			false,
			null,
			Vector3.ZERO,
			area_vfx_kind
		)
		if aoe_cell_impact_stagger > 0.0:
			await get_tree().create_timer(aoe_cell_impact_stagger).timeout


func _on_action_vfx_finished(vfx: SporeActionVfx3D) -> void:
	if _projectile_follow_vfx == vfx:
		_projectile_follow_vfx = null


func _update_manual_camera_pan(delta: float) -> void:
	if _camera_rig == null or map_root == null or battle_finished:
		return
	if _action_camera_timer > 0.0:
		return
	if projectile_camera_follow and _projectile_follow_vfx != null and is_instance_valid(_projectile_follow_vfx):
		return

	var horizontal: float = 0.0
	var vertical: float = 0.0
	if Input.is_key_pressed(KEY_LEFT):
		horizontal -= 1.0
	if Input.is_key_pressed(KEY_RIGHT):
		horizontal += 1.0
	if Input.is_key_pressed(KEY_UP):
		vertical += 1.0
	if Input.is_key_pressed(KEY_DOWN):
		vertical -= 1.0

	if is_zero_approx(horizontal) and is_zero_approx(vertical):
		return

	var yaw: float = deg_to_rad(_camera_target_angle)
	var screen_right: Vector3 = Vector3(cos(yaw), 0.0, -sin(yaw))
	var screen_up: Vector3 = Vector3(-sin(yaw), 0.0, -cos(yaw))
	var movement: Vector3 = screen_right * horizontal + screen_up * vertical
	if movement.length_squared() > 1.0:
		movement = movement.normalized()

	camera_follow_active = false
	_camera_focus_target += movement * camera_pan_speed * delta


func _focus_camera_on_map_center(immediate: bool = false) -> void:
	if map_root == null:
		return

	var center_x: int = maxi(0, map_root.grid_width - 1) / 2
	var center_y: int = maxi(0, map_root.grid_height - 1) / 2
	var center_cell: Vector2i = Vector2i(center_x, center_y)
	var local_center: Vector3 = map_root.cell_top_local(center_cell)
	var world_center: Vector3 = map_root.to_global(local_center)
	var board_center: Vector3 = to_local(world_center)

	_camera_focus_target = Vector3(board_center.x, 0.0, board_center.z)
	if immediate:
		_camera_focus_current = _camera_focus_target
		_apply_camera_transform()


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
	var action_was_active: bool = _action_camera_timer > 0.0
	_action_camera_timer = maxf(0.0, _action_camera_timer - delta)
	_impact_zoom_timer = maxf(0.0, _impact_zoom_timer - delta)
	_camera_shake_strength = maxf(0.0, _camera_shake_strength - delta * 0.62)

	if action_was_active and _action_camera_timer <= 0.0 and not camera_follow_active:
		_camera_focus_target = _camera_return_focus


func _update_camera_smoothing(delta: float) -> void:
	if not _camera_initialized:
		return
	# CINEMATIC_CAMERA_PRIORITY
	if _cinematic_camera_active:
		var cinematic_weight: float = 1.0 - exp(-camera_smoothing * maxf(0.0, delta))
		_camera_current_angle = lerpf(_camera_current_angle, _camera_target_angle, cinematic_weight)
		_camera_current_distance = lerpf(_camera_current_distance, _camera_target_distance, cinematic_weight)
		_camera_focus_current = _camera_focus_current.lerp(_camera_focus_target, cinematic_weight)
		_apply_camera_transform()
		return
	var following_projectile: bool = not _cinematic_camera_active and projectile_camera_follow and _projectile_follow_vfx != null and is_instance_valid(_projectile_follow_vfx)
	if following_projectile:
		var projectile_position: Vector3 = _projectile_follow_vfx.follow_position
		_camera_focus_target = Vector3(projectile_position.x, 0.0, projectile_position.z)
	elif not _cinematic_camera_active and _action_camera_timer > 0.0:
		_camera_focus_target = _action_camera_focus
	elif not _cinematic_camera_active and camera_follow_active and active_actor != null and active_actor.alive:
		_camera_focus_target = Vector3(active_actor.position.x, 0.0, active_actor.position.z)
	var effective_distance: float = _camera_target_distance
	if following_projectile:
		effective_distance = maxf(6.0, effective_distance - projectile_camera_zoom_in)
	elif not _cinematic_camera_active and _action_camera_timer > 0.0:
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

	_camera_return_focus = _camera_focus_target
	_action_camera_focus = Vector3(midpoint.x, 0.0, midpoint.z)
	_action_camera_timer = action_camera_duration if duration < 0.0 else duration
	_action_camera_zoom = action_camera_zoom_in if zoom_in < 0.0 else zoom_in


func _camera_impact(strength: float = -1.0) -> void:
	var resolved_strength: float = impact_shake_strength if strength < 0.0 else strength
	_camera_shake_strength = maxf(_camera_shake_strength, resolved_strength)
	_impact_zoom_timer = 0.16


func _focus_camera_on_active(immediate: bool = false) -> void:
	if active_actor == null:
		return

	camera_follow_active = false
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
