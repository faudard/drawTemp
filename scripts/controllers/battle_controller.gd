class_name SporeBattleController
extends Node2D

signal cinematic_advance_requested

const CampaignState = preload("res://scripts/campaign/campaign_state.gd")
const SaveManager = preload("res://scripts/campaign/save_manager.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const JobCatalog = preload("res://scripts/catalogs/job_catalog.gd")
const ProgressionTreeCanvas = preload("res://scripts/ui/progression_tree_canvas.gd")
const MissionCatalog = preload("res://scripts/catalogs/mission_catalog.gd")
const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")
const CampaignCatalog = preload("res://scripts/catalogs/campaign_catalog.gd")
const AiCatalog = preload("res://scripts/catalogs/ai_catalog.gd")
const CinematicCatalog = preload("res://scripts/catalogs/cinematic_catalog.gd")
const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")
const VfxCatalog = preload("res://scripts/catalogs/vfx_catalog.gd")
const BattleRules = preload("res://scripts/core/battle_rules.gd")
const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")
const MissionRule = preload("res://scripts/data/mission_rule.gd")

## Sporebound Tactics - gameplay-first tactical battle prototype.
## V1.9 data-driven battle controller + visual job trees, node purchases and persistent branches.
## Battle orchestration/UI/FX live here; campaign state, persistence, missions, units, skills
## and deterministic battle helpers are isolated behind dedicated modules.

var grid_width := 10
var grid_height := 8
var cell_size := 70.0
const BOARD_ORIGIN := Vector2(46.0, 142.0)

const BG := Color("#101827")
const PANEL := Color("#1b2941")
const PANEL_EDGE := Color("#38516b")
const GRID_A := Color("#263950")
const GRID_B := Color("#2b4259")
const GRID_LINE := Color("#46657b")
const TEXT := Color("#f4f0dc")
const TEXT_SOFT := Color("#a9bdd0")
const GOLD := Color("#ffd166")
const MINT := Color("#7be0ad")
const CORAL := Color("#ff7b72")
const SKY := Color("#6cc5e8")
const VIOLET := Color("#c996ff")
const MOVE_HIGHLIGHT := Color(0.482, 0.878, 0.678, 0.25)
const ATTACK_HIGHLIGHT := Color(1.0, 0.482, 0.447, 0.32)
const HOVER_HIGHLIGHT := Color(1.0, 0.941, 0.659, 0.20)
const HAZARD := Color("#b86bdb")
const EXTRACTION := Color("#64d9b3")
const CROWN := Color("#ffd166")

var units: Array = []
var obstacles: Array = []
var cover_cells: Array = []
var hazard_cells: Array = []
var extraction_cells: Array = []
var bonus_cells: Array = []
var bonus_collected := 0
var special_targeting := false
var special_target_cells: Array = []
var special_target_skill_id := ""
var terrain_heights: Dictionary = {}
var mission_zones: Array[Dictionary] = []
var crown_cell := Vector2i(9, 0)
var crown_carrier_id := ""
var enemies_cleared_logged := false
var mission_victory := false

var selected_id := ""
var hovered_cell := Vector2i(-1, -1)
var move_cells: Array = []
var attack_cells: Array = []
var move_costs: Dictionary = {}
var move_parents: Dictionary = {}
var message_log: Array = []
var current_turn := 1
var rounds_completed := 0
var enemy_phase := false
var game_over := false
var timeline_order: Array = []
var timeline_index := -1
var active_unit_id := ""
var activation_count_in_round := 0
var round_activation_budget := 0
var activated_this_round: Dictionary = {}
var battle_clock_ticks := 0
var battle_rng := RandomNumberGenerator.new()
var battle_serial := 0
var animation_time := 0.0

# V0.6 presentation FX. Logical positions/actions remain immediate; these only affect rendering.
var visual_paths: Dictionary = {}
var attack_fx: Dictionary = {}
var hit_fx: Dictionary = {}
var ko_fx: Dictionary = {}
var floating_text_fx: Array = []
var projectile_fx: Array = []
var particle_fx: Array = []
var custom_vfx: Array = []
var visual_texture_cache: Dictionary = {}
var shake_strength := 0.0
var sound_enabled := true
var timeline_bar: HBoxContainer

# Campaign UI references. Persistent data now lives in SporeCampaignState.
var mission_objective := "crown"
var survival_rounds := 0
var mission_reward_granted := false
var enemies_total_initial := 0
var bonus_target_total := 0
var campaign := CampaignState.new()
var editor_test_mode: bool = false
var editor_test_autostart: bool = false
var active_mission_definition: Resource = null
var fired_trigger_ids: Dictionary = {}
var evaluating_triggers := false
var pending_trigger_sequences: Array = []
var event_sequence_running := false
var battle_sequence_serial := 0
var interactable_states: Dictionary = {}
var runtime_objective_text := ""
var runtime_phase := ""
var runtime_victory_rules: Array = []
var runtime_defeat_rules: Array = []
var runtime_victory_rule_mode := "any"
var runtime_defeat_rule_mode := "any"

# V1.6 cinematic presentation state. Battle logic remains in grid coordinates.
var cinematic_camera_offset := Vector2.ZERO
var cinematic_camera_zoom := 1.0
var cinematic_dialogue_waiting := false
var cinematic_overlay: Control
var cinematic_letterbox_top: ColorRect
var cinematic_letterbox_bottom: ColorRect
var cinematic_dialogue_panel: Panel
var cinematic_speaker_label: Label
var cinematic_message_label: Label
var cinematic_portrait: TextureRect
var cinematic_continue_button: Button
var cinematic_fade_rect: ColorRect
var cinematic_music_player: AudioStreamPlayer
var cinematic_sfx_player: AudioStreamPlayer

var prep_overlay: Control
var prep_mission_label: Label
var prep_status_label: Label
var prep_start_button: Button
var prep_hero_buttons: Dictionary = {}
var prep_module_buttons: Dictionary = {}
var prep_tree_buttons: Dictionary = {}
var talent_overlay: Control
var talent_tree_view: SporeProgressionTreeCanvas
var talent_title_label: Label
var talent_points_label: Label
var talent_detail_label: Label
var talent_buy_button: Button
var talent_reset_button: Button
var talent_hero_id := ""
var talent_selected_node_id := ""
var debrief_overlay: Control
var debrief_title_label: Label
var debrief_text_label: Label
var debrief_continue_button: Button
var mission_description_label: Label

# Active skills / equipment / reward layer inherited from V0.8.
var prep_gear_buttons: Dictionary = {}
var prep_gear_cycle_cursor: Dictionary = {}
var reward_options: Array = []
var reward_selected := false
var debrief_reward_label: Label
var debrief_reward_buttons: Array = []
var secondary_button: Button

# V0.9 persistent campaign / mission-select / contract layer.
var prep_mission_button: Button
var prep_difficulty_button: Button
var prep_save_label: Label
var prep_reset_button: Button
var reset_save_armed := false
var event_overlay: Control
var event_title_label: Label
var event_text_label: Label
var event_choice_a: Button
var event_choice_b: Button
var event_source_mission := -1
var event_current_node_id := ""

var turn_label: Label
var selected_label: Label
var status_label: Label
var preview_label: Label
var timeline_label: Label
var log_label: Label
var special_button: Button
var end_turn_button: Button


func _ready() -> void:
	load_campaign_save()
	var editor_test_index: int = consume_editor_test_request()
	if editor_test_index >= 0:
		campaign.mission_index = editor_test_index
		campaign.max_unlocked = maxi(campaign.max_unlocked, editor_test_index)
	build_ui()
	build_campaign_ui()
	var resume_node := CampaignCatalog.node(campaign.campaign_node_id)
	if editor_test_index < 0 and campaign.mode == "event" and resume_node != null and String(resume_node.node_type) == "event":
		show_campaign_event(campaign.campaign_node_id)
	else:
		show_prep_screen()
	if editor_test_index >= 0:
		if editor_test_autostart:
			prep_status_label.text = "MODE PLAYTEST MAP • lancement direct • sauvegarde campagne protégée"
			call_deferred("_start_editor_map_playtest")
		else:
			prep_status_label.text = "MODE TEST STUDIO • mission chargée depuis Sporebound Studio • choisis l'escouade puis LANCER"
	queue_redraw()


func consume_editor_test_request() -> int:
	const TEST_PATH: String = "user://sporebound_editor_test.json"
	if not FileAccess.file_exists(TEST_PATH):
		return -1
	editor_test_mode = true
	var file: FileAccess = FileAccess.open(TEST_PATH, FileAccess.READ)
	var mission_index: int = -1
	if file != null:
		var parsed: Variant = JSON.parse_string(file.get_as_text())
		file.close()
		if parsed is Dictionary:
			var request: Dictionary = parsed as Dictionary
			var mission_path: String = String(request.get("mission_path", ""))
			var mission_id: String = String(request.get("mission_id", ""))
			editor_test_autostart = bool(request.get("autostart", false))
			if not mission_path.is_empty():
				mission_index = MissionCatalog.index_for_path(mission_path)
			if mission_index < 0 and not mission_id.is_empty():
				mission_index = MissionCatalog.index_for_id(mission_id)
			if mission_index < 0 and request.has("mission_index"):
				mission_index = int(request.get("mission_index", -1))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_PATH))
	return clampi(mission_index, -1, maxi(-1, mission_count() - 1))


func _start_editor_map_playtest() -> void:
	# Keep playtesting frictionless even if the user's persistent squad currently has
	# fewer/more than three selected heroes. Nothing is persisted in editor_test_mode.
	if selected_hero_count() != 3:
		var preferred: PackedStringArray = PackedStringArray(["momo", "pipo", "ziggy", "luma"])
		for hero_id: String in preferred:
			campaign.hero_selected[hero_id] = false
		for index: int in range(mini(3, preferred.size())):
			campaign.hero_selected[preferred[index]] = true
	_on_start_mission_pressed()


func _process(delta: float) -> void:
	animation_time += delta
	shake_strength = max(0.0, shake_strength - delta * 18.0)
	prune_presentation_fx()
	queue_redraw()


func build_ui() -> void:
	var ui_layer := CanvasLayer.new()
	ui_layer.name = "UILayer"
	add_child(ui_layer)

	var root := Control.new()
	root.name = "UI"
	root.position = Vector2.ZERO
	root.size = Vector2(1280.0, 760.0)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui_layer.add_child(root)

	add_label(root, "SPOREBOUND TACTICS", Vector2(46.0, 27.0), Vector2(650.0, 40.0), 30, TEXT)
	add_label(
		root,
		"V1.9 • Arbres de progression visuels, branches et choix data-driven",
		Vector2(48.0, 70.0),
		Vector2(700.0, 28.0),
		15,
		TEXT_SOFT
	)
	status_label = add_label(root, "", Vector2(48.0, 105.0), Vector2(730.0, 30.0), 14, GOLD)

	var panel := Panel.new()
	panel.name = "CommandPanel"
	panel.position = Vector2(804.0, 112.0)
	panel.size = Vector2(430.0, 610.0)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", make_style(PANEL, 22, PANEL_EDGE))
	root.add_child(panel)

	add_label(panel, "POSTE DE COMMANDE", Vector2(24.0, 18.0), Vector2(380.0, 35.0), 22, TEXT)
	mission_description_label = add_label(
		panel,
		"",
		Vector2(24.0, 56.0),
		Vector2(380.0, 58.0),
		14,
		TEXT_SOFT
	)
	mission_description_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	turn_label = add_label(panel, "", Vector2(24.0, 119.0), Vector2(380.0, 30.0), 20, GOLD)
	timeline_label = add_label(panel, "INITIATIVE", Vector2(24.0, 151.0), Vector2(380.0, 18.0), 11, TEXT_SOFT)
	timeline_bar = HBoxContainer.new()
	timeline_bar.position = Vector2(24.0, 171.0)
	timeline_bar.size = Vector2(382.0, 44.0)
	timeline_bar.add_theme_constant_override("separation", 4)
	panel.add_child(timeline_bar)
	selected_label = add_label(panel, "", Vector2(24.0, 219.0), Vector2(380.0, 77.0), 14, TEXT)
	preview_label = add_label(panel, "", Vector2(24.0, 296.0), Vector2(380.0, 50.0), 13, GOLD)
	preview_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	special_button = add_button(
		panel, "Compétence I", Vector2(24.0, 346.0), Vector2(382.0, 39.0)
	)
	special_button.pressed.connect(_on_special_pressed)

	secondary_button = add_button(
		panel, "Compétence II", Vector2(24.0, 390.0), Vector2(382.0, 39.0)
	)
	secondary_button.pressed.connect(_on_secondary_pressed)

	end_turn_button = add_button(panel, "Terminer l'activation", Vector2(24.0, 434.0), Vector2(382.0, 39.0))
	end_turn_button.pressed.connect(_on_end_turn_pressed)

	var restart_button := add_button(
		panel, "Recommencer la mission", Vector2(24.0, 478.0), Vector2(382.0, 35.0)
	)
	restart_button.pressed.connect(reset_battle)

	add_label(
		panel, "JOURNAL DU NARRATEUR", Vector2(24.0, 520.0), Vector2(382.0, 22.0), 11, TEXT_SOFT
	)
	log_label = add_label(panel, "", Vector2(24.0, 542.0), Vector2(382.0, 45.0), 11, TEXT)
	log_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	add_label(
		root,
		(
			"L'unité active est imposée par la timeline. Marche et action peuvent être faites dans l'ordre voulu.\n"
			+ "▲ hauteur • ♛ objectif • ◉ bonus • spores = 1 dégât • clic droit = orientation • M = sons"
		),
		Vector2(48.0, 711.0),
		Vector2(730.0, 43.0),
		13,
		TEXT_SOFT
	)

	_build_cinematic_ui(root)


func _build_cinematic_ui(root: Control) -> void:
	cinematic_overlay = Control.new()
	cinematic_overlay.name = "CinematicOverlay"
	cinematic_overlay.position = Vector2.ZERO
	cinematic_overlay.size = Vector2(1280.0, 760.0)
	cinematic_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cinematic_overlay.z_index = 80
	root.add_child(cinematic_overlay)

	cinematic_letterbox_top = ColorRect.new()
	cinematic_letterbox_top.color = Color(0.0, 0.0, 0.0, 0.92)
	cinematic_letterbox_top.position = Vector2.ZERO
	cinematic_letterbox_top.size = Vector2(1280.0, 62.0)
	cinematic_letterbox_top.visible = false
	cinematic_letterbox_top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cinematic_overlay.add_child(cinematic_letterbox_top)

	cinematic_letterbox_bottom = ColorRect.new()
	cinematic_letterbox_bottom.color = Color(0.0, 0.0, 0.0, 0.92)
	cinematic_letterbox_bottom.position = Vector2(0.0, 698.0)
	cinematic_letterbox_bottom.size = Vector2(1280.0, 62.0)
	cinematic_letterbox_bottom.visible = false
	cinematic_letterbox_bottom.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cinematic_overlay.add_child(cinematic_letterbox_bottom)

	cinematic_dialogue_panel = Panel.new()
	cinematic_dialogue_panel.position = Vector2(100.0, 500.0)
	cinematic_dialogue_panel.size = Vector2(1080.0, 170.0)
	cinematic_dialogue_panel.add_theme_stylebox_override("panel", make_style(Color(0.045, 0.071, 0.11, 0.97), 18, VIOLET))
	cinematic_dialogue_panel.visible = false
	cinematic_dialogue_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	cinematic_dialogue_panel.gui_input.connect(_on_cinematic_dialogue_gui_input)
	cinematic_overlay.add_child(cinematic_dialogue_panel)

	cinematic_portrait = TextureRect.new()
	cinematic_portrait.position = Vector2(18.0, 16.0)
	cinematic_portrait.size = Vector2(126.0, 138.0)
	cinematic_portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	cinematic_portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	cinematic_portrait.visible = false
	cinematic_portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cinematic_dialogue_panel.add_child(cinematic_portrait)

	cinematic_speaker_label = add_label(cinematic_dialogue_panel, "", Vector2(164.0, 16.0), Vector2(730.0, 30.0), 19, GOLD)
	cinematic_message_label = add_label(cinematic_dialogue_panel, "", Vector2(164.0, 48.0), Vector2(875.0, 83.0), 17, TEXT)
	cinematic_message_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	cinematic_continue_button = add_button(cinematic_dialogue_panel, "CONTINUER  ▸", Vector2(860.0, 128.0), Vector2(180.0, 32.0))
	cinematic_continue_button.pressed.connect(_on_cinematic_continue_pressed)

	cinematic_fade_rect = ColorRect.new()
	cinematic_fade_rect.color = Color(0.0, 0.0, 0.0, 0.0)
	cinematic_fade_rect.position = Vector2.ZERO
	cinematic_fade_rect.size = Vector2(1280.0, 760.0)
	cinematic_fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cinematic_fade_rect.z_index = 95
	root.add_child(cinematic_fade_rect)

	cinematic_music_player = AudioStreamPlayer.new()
	cinematic_music_player.name = "CinematicMusic"
	add_child(cinematic_music_player)
	cinematic_sfx_player = AudioStreamPlayer.new()
	cinematic_sfx_player.name = "CinematicSfx"
	add_child(cinematic_sfx_player)


func _on_cinematic_continue_pressed() -> void:
	if not cinematic_dialogue_waiting:
		return
	cinematic_dialogue_waiting = false
	cinematic_advance_requested.emit()


func _on_cinematic_dialogue_gui_input(event: InputEvent) -> void:
	if not cinematic_dialogue_waiting:
		return
	if event is InputEventMouseButton:
		var mouse_event := event as InputEventMouseButton
		if mouse_event.pressed and mouse_event.button_index == MOUSE_BUTTON_LEFT:
			_on_cinematic_continue_pressed()


func _hide_cinematic_dialogue() -> void:
	if cinematic_dialogue_panel != null:
		cinematic_dialogue_panel.visible = false
	if cinematic_letterbox_top != null:
		cinematic_letterbox_top.visible = false
	if cinematic_letterbox_bottom != null:
		cinematic_letterbox_bottom.visible = false
	cinematic_dialogue_waiting = false



func add_label(
	parent: Control, value: String, position: Vector2, size: Vector2, font_size: int, color: Color
) -> Label:
	var label := Label.new()
	label.text = value
	label.position = position
	label.size = size
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label


func add_button(parent: Control, value: String, position: Vector2, size: Vector2) -> Button:
	var button := Button.new()
	button.text = value
	button.position = position
	button.size = size
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", 15)
	button.add_theme_color_override("font_color", TEXT)
	button.add_theme_color_override("font_hover_color", BG)
	button.add_theme_color_override("font_pressed_color", BG)
	button.add_theme_color_override(
		"font_disabled_color", Color(TEXT_SOFT.r, TEXT_SOFT.g, TEXT_SOFT.b, 0.48)
	)
	button.add_theme_stylebox_override("normal", make_style(Color("#2d4860"), 12, Color("#52728b")))
	button.add_theme_stylebox_override("hover", make_style(Color("#7be0ad"), 12, Color("#b5f2d0")))
	button.add_theme_stylebox_override(
		"pressed", make_style(Color("#ffd166"), 12, Color("#fff0a8"))
	)
	button.add_theme_stylebox_override(
		"disabled", make_style(Color("#263344"), 12, Color("#33485e"))
	)
	parent.add_child(button)
	return button


func make_style(fill: Color, radius: int, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.corner_radius_top_left = radius
	style.corner_radius_top_right = radius
	style.corner_radius_bottom_left = radius
	style.corner_radius_bottom_right = radius
	style.border_width_left = 1
	style.border_width_top = 1
	style.border_width_right = 1
	style.border_width_bottom = 1
	style.border_color = border
	style.content_margin_left = 14.0
	style.content_margin_right = 14.0
	return style


func build_campaign_ui() -> void:
	var layer := CanvasLayer.new()
	layer.name = "CampaignLayer"
	layer.layer = 20
	add_child(layer)

	prep_overlay = Control.new()
	prep_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	prep_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	layer.add_child(prep_overlay)

	var shade := ColorRect.new()
	shade.color = Color(0.035, 0.055, 0.085, 0.97)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	prep_overlay.add_child(shade)

	var card := Panel.new()
	card.position = Vector2(120.0, 50.0)
	card.size = Vector2(1040.0, 660.0)
	card.add_theme_stylebox_override("panel", make_style(PANEL, 24, PANEL_EDGE))
	prep_overlay.add_child(card)
	add_label(card, "SERRE TACTIQUE", Vector2(38.0, 28.0), Vector2(470.0, 40.0), 30, TEXT)
	prep_mission_label = add_label(card, "", Vector2(40.0, 79.0), Vector2(950.0, 76.0), 17, GOLD)
	prep_mission_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_label(card, "Choisis 3 héros, leur JOB, leur ARBRE et équipe les reliques débloquées par slot.", Vector2(40.0, 157.0), Vector2(950.0, 28.0), 14, TEXT_SOFT)

	prep_mission_button = add_button(card, "", Vector2(40.0, 187.0), Vector2(462.0, 42.0))
	prep_mission_button.pressed.connect(_on_mission_cycle_pressed)
	prep_difficulty_button = add_button(card, "", Vector2(516.0, 187.0), Vector2(476.0, 42.0))
	prep_difficulty_button.pressed.connect(_on_difficulty_cycle_pressed)

	var hero_ids := ["momo", "pipo", "ziggy", "luma"]
	for index in range(hero_ids.size()):
		var hero_id: String = hero_ids[index]
		var y := 239.0 + float(index) * 70.0
		var hero_button := add_button(card, "", Vector2(40.0, y), Vector2(200.0, 54.0))
		hero_button.pressed.connect(_on_hero_toggle.bind(hero_id))
		prep_hero_buttons[hero_id] = hero_button
		var module_button := add_button(card, "", Vector2(252.0, y), Vector2(252.0, 54.0))
		module_button.pressed.connect(_on_module_cycle.bind(hero_id))
		prep_module_buttons[hero_id] = module_button
		var tree_button := add_button(card, "", Vector2(516.0, y), Vector2(148.0, 54.0))
		tree_button.pressed.connect(_on_tree_open.bind(hero_id))
		prep_tree_buttons[hero_id] = tree_button
		var gear_button := add_button(card, "", Vector2(676.0, y), Vector2(316.0, 54.0))
		gear_button.pressed.connect(_on_gear_cycle.bind(hero_id))
		prep_gear_buttons[hero_id] = gear_button

	prep_status_label = add_label(card, "", Vector2(40.0, 528.0), Vector2(620.0, 66.0), 14, TEXT)
	prep_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	prep_start_button = add_button(card, "LANCER LA MISSION", Vector2(690.0, 535.0), Vector2(302.0, 52.0))
	prep_start_button.pressed.connect(_on_start_mission_pressed)
	prep_save_label = add_label(card, "", Vector2(40.0, 606.0), Vector2(735.0, 24.0), 12, TEXT_SOFT)
	prep_reset_button = add_button(card, "NOUVELLE CAMPAGNE", Vector2(790.0, 598.0), Vector2(202.0, 34.0))
	prep_reset_button.pressed.connect(_on_reset_save_pressed)

	# V1.9 runtime progression tree overlay.
	talent_overlay = Control.new()
	talent_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	talent_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	talent_overlay.visible = false
	layer.add_child(talent_overlay)
	var talent_shade := ColorRect.new()
	talent_shade.color = Color(0.025, 0.045, 0.07, 0.98)
	talent_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	talent_overlay.add_child(talent_shade)
	var talent_card := Panel.new()
	talent_card.position = Vector2(90.0, 55.0)
	talent_card.size = Vector2(1100.0, 650.0)
	talent_card.add_theme_stylebox_override("panel", make_style(PANEL, 24, PANEL_EDGE))
	talent_overlay.add_child(talent_card)
	talent_title_label = add_label(talent_card, "ARBRE DE PROGRESSION", Vector2(28.0, 20.0), Vector2(760.0, 38.0), 26, GOLD)
	talent_points_label = add_label(talent_card, "", Vector2(30.0, 62.0), Vector2(720.0, 28.0), 14, MINT)
	var talent_scroll := ScrollContainer.new()
	talent_scroll.position = Vector2(26.0, 98.0)
	talent_scroll.size = Vector2(760.0, 500.0)
	talent_card.add_child(talent_scroll)
	talent_tree_view = ProgressionTreeCanvas.new()
	talent_tree_view.editable_positions = false
	talent_tree_view.node_selected.connect(_on_talent_node_selected)
	talent_scroll.add_child(talent_tree_view)
	talent_detail_label = add_label(talent_card, "Sélectionne un nœud.", Vector2(812.0, 112.0), Vector2(258.0, 255.0), 14, TEXT)
	talent_detail_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	talent_buy_button = add_button(talent_card, "ACQUÉRIR", Vector2(812.0, 390.0), Vector2(258.0, 48.0))
	talent_buy_button.pressed.connect(_on_talent_buy_pressed)
	talent_reset_button = add_button(talent_card, "RÉINITIALISER ARBRE", Vector2(812.0, 450.0), Vector2(258.0, 42.0))
	talent_reset_button.pressed.connect(_on_talent_reset_pressed)
	var talent_close := add_button(talent_card, "FERMER", Vector2(812.0, 548.0), Vector2(258.0, 42.0))
	talent_close.pressed.connect(_on_talent_close_pressed)

	debrief_overlay = Control.new()
	debrief_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	debrief_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	debrief_overlay.visible = false
	layer.add_child(debrief_overlay)
	var debrief_shade := ColorRect.new()
	debrief_shade.color = Color(0.035, 0.055, 0.085, 0.92)
	debrief_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	debrief_shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	debrief_overlay.add_child(debrief_shade)
	var debrief_card := Panel.new()
	debrief_card.position = Vector2(230.0, 105.0)
	debrief_card.size = Vector2(820.0, 550.0)
	debrief_card.add_theme_stylebox_override("panel", make_style(PANEL, 24, PANEL_EDGE))
	debrief_overlay.add_child(debrief_card)
	debrief_title_label = add_label(debrief_card, "", Vector2(34.0, 28.0), Vector2(750.0, 44.0), 29, GOLD)
	debrief_text_label = add_label(debrief_card, "", Vector2(34.0, 84.0), Vector2(750.0, 155.0), 15, TEXT)
	debrief_text_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	debrief_reward_label = add_label(debrief_card, "", Vector2(34.0, 245.0), Vector2(750.0, 30.0), 14, GOLD)
	for i in range(3):
		var reward_button := add_button(debrief_card, "", Vector2(34.0, 282.0 + i * 58.0), Vector2(750.0, 48.0))
		reward_button.pressed.connect(_on_reward_selected.bind(i))
		debrief_reward_buttons.append(reward_button)
	debrief_continue_button = add_button(debrief_card, "CONTINUER", Vector2(34.0, 470.0), Vector2(750.0, 48.0))
	debrief_continue_button.pressed.connect(_on_continue_campaign_pressed)

	event_overlay = Control.new()
	event_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	event_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	event_overlay.visible = false
	layer.add_child(event_overlay)
	var event_shade := ColorRect.new()
	event_shade.color = Color(0.035, 0.055, 0.085, 0.94)
	event_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	event_shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	event_overlay.add_child(event_shade)
	var event_card := Panel.new()
	event_card.position = Vector2(260.0, 155.0)
	event_card.size = Vector2(760.0, 450.0)
	event_card.add_theme_stylebox_override("panel", make_style(PANEL, 24, PANEL_EDGE))
	event_overlay.add_child(event_card)
	event_title_label = add_label(event_card, "INTERMISSION", Vector2(34.0, 30.0), Vector2(690.0, 44.0), 28, GOLD)
	event_text_label = add_label(event_card, "", Vector2(34.0, 92.0), Vector2(690.0, 140.0), 16, TEXT)
	event_text_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	event_choice_a = add_button(event_card, "", Vector2(34.0, 260.0), Vector2(690.0, 56.0))
	event_choice_b = add_button(event_card, "", Vector2(34.0, 330.0), Vector2(690.0, 56.0))
	event_choice_a.pressed.connect(_on_event_choice.bind(0))
	event_choice_b.pressed.connect(_on_event_choice.bind(1))


func show_prep_screen() -> void:
	campaign.mode = "prep"
	game_over = true
	enemy_phase = false
	selected_id = ""
	active_unit_id = ""
	prep_overlay.visible = true
	debrief_overlay.visible = false
	if is_instance_valid(talent_overlay):
		talent_overlay.visible = false
	if is_instance_valid(event_overlay):
		event_overlay.visible = false
	update_prep_ui()
	queue_redraw()


func update_prep_ui() -> void:
	if not is_instance_valid(prep_overlay):
		return
	if reset_save_armed:
		reset_save_armed = false
		if is_instance_valid(prep_reset_button):
			prep_reset_button.text = "NOUVELLE CAMPAGNE"
	var mission := mission_meta(campaign.mission_index)
	prep_mission_label.text = "MISSION %d/%d — %s\n%s" % [campaign.mission_index + 1, mission_count(), mission["name"], mission["brief"]]
	for hero_id in prep_hero_buttons.keys():
		var button: Button = prep_hero_buttons[hero_id]
		var selected := bool(campaign.hero_selected.get(hero_id, false))
		button.text = "%s  %s\n%s" % ["✓" if selected else "○", hero_name(hero_id), hero_role(hero_id)]
		var module_button: Button = prep_module_buttons[hero_id]
		var job_id := String(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id)))
		var job_xp: Dictionary = campaign.hero_job_xp.get(hero_id, {})
		var job_level := UnitCatalog.job_level(job_id, job_xp)
		var to_next := UnitCatalog.job_xp_to_next(job_id, job_xp)
		module_button.text = "JOB : %s • Niv.%d\n%s" % [UnitCatalog.job_name(job_id), job_level, "MAX" if to_next <= 0 else "%d XP → niv. suivant" % to_next]
		var purchased_nodes := campaign.job_nodes(hero_id, job_id)
		var tree_info := UnitCatalog.job_tree_points(job_id, job_xp, purchased_nodes)
		var tree_button: Button = prep_tree_buttons[hero_id]
		tree_button.text = "ARBRE\n%d pt dispo" % int(tree_info.get("available", 0))
		var gear_button: Button = prep_gear_buttons[hero_id]
		var slots: Dictionary = campaign.hero_equipment_slots.get(hero_id, {})
		gear_button.text = "ÉQUIP : %s | %s | %s\nClique : prochaine relique débloquée" % [equipment_name(String(slots.get("weapon", "none"))), equipment_name(String(slots.get("armor", "none"))), equipment_name(String(slots.get("accessory", "none")))]
	var count := selected_hero_count()
	var rank := campaign_rank()
	prep_status_label.text = "Escouade %d/3 • Spores XP %d • Rang %d • Tournée %d • Reliques %d\nBonus de rang : +%d PV max • Prochain bonus : %s" % [count, campaign.spores, rank, campaign.loop + 1, campaign.unlocked_equipment.size(), rank - 1, mission_buff_name(campaign.next_mission_buff)]
	prep_mission_button.text = "MISSION : %d/%d — %s  [débloquées %d/%d]" % [campaign.mission_index + 1, mission_count(), mission["name"], campaign.max_unlocked + 1, mission_count()]
	prep_difficulty_button.text = "DIFFICULTÉ : %s — %s" % [difficulty_name(), difficulty_description()]
	prep_save_label.text = "Sauvegarde auto : %s • Contrat : %s" % [SaveManager.SAVE_PATH, secondary_objective_text(campaign.mission_index)]
	prep_start_button.disabled = count != 3
	prep_start_button.text = "LANCER — %s" % str(mission["name"]).to_upper()


func _on_hero_toggle(hero_id: String) -> void:
	var selected := bool(campaign.hero_selected.get(hero_id, false))
	if selected:
		campaign.hero_selected[hero_id] = false
	elif selected_hero_count() < 3:
		campaign.hero_selected[hero_id] = true
	else:
		prep_status_label.text = "Il faut rester à 3 héros : désélectionne d'abord un membre de l'escouade."
		return
	save_campaign()
	update_prep_ui()


func _on_module_cycle(hero_id: String) -> void:
	var xp_by_job: Dictionary = campaign.hero_job_xp.get(hero_id, {})
	var choices := UnitCatalog.unlocked_jobs(hero_id, xp_by_job)
	if choices.is_empty():
		return
	var current := String(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id)))
	var index := choices.find(current)
	if index < 0:
		index = 0
	campaign.hero_jobs[hero_id] = String(choices[(index + 1) % choices.size()])
	save_campaign()
	update_prep_ui()


func _on_tree_open(hero_id: String) -> void:
	talent_hero_id = hero_id
	talent_selected_node_id = ""
	prep_overlay.visible = false
	talent_overlay.visible = true
	_refresh_talent_overlay()


func _on_talent_close_pressed() -> void:
	talent_overlay.visible = false
	prep_overlay.visible = true
	talent_hero_id = ""
	talent_selected_node_id = ""
	update_prep_ui()


func _refresh_talent_overlay() -> void:
	if talent_hero_id.is_empty() or not is_instance_valid(talent_tree_view):
		return
	var job_id := String(campaign.hero_jobs.get(talent_hero_id, UnitCatalog.default_job(talent_hero_id)))
	var job_xp: Dictionary = campaign.hero_job_xp.get(talent_hero_id, {})
	var level := UnitCatalog.job_level(job_id, job_xp)
	var purchased := campaign.job_nodes(talent_hero_id, job_id)
	var info := UnitCatalog.job_tree_points(job_id, job_xp, purchased)
	var job_def := JobCatalog.definition(job_id)
	talent_title_label.text = "%s — %s • Niv.%d" % [hero_name(talent_hero_id), UnitCatalog.job_name(job_id), level]
	talent_points_label.text = "Points : %d disponibles • %d dépensés / %d • nœuds manuels %d" % [int(info.get("available", 0)), int(info.get("spent", 0)), int(info.get("budget", 0)), purchased.size()]
	talent_tree_view.set_job(job_def)
	talent_tree_view.set_runtime_state(level, purchased, int(info.get("available", 0)))
	if talent_selected_node_id.is_empty() and job_def != null and not job_def.progression_nodes.is_empty():
		talent_selected_node_id = String(job_def.progression_nodes[0].id)
		talent_tree_view.set_selected_node(talent_selected_node_id)
	_update_talent_detail()


func _on_talent_node_selected(node_id: String) -> void:
	talent_selected_node_id = node_id
	_update_talent_detail()


func _update_talent_detail() -> void:
	if talent_hero_id.is_empty():
		return
	var job_id := String(campaign.hero_jobs.get(talent_hero_id, UnitCatalog.default_job(talent_hero_id)))
	var node: SporeProgressionNodeDefinition = JobCatalog.progression_node(job_id, talent_selected_node_id)
	if node == null:
		talent_detail_label.text = "Sélectionne un nœud."
		talent_buy_button.disabled = true
		return
	var job_xp: Dictionary = campaign.hero_job_xp.get(talent_hero_id, {})
	var level := UnitCatalog.job_level(job_id, job_xp)
	var purchased := campaign.job_nodes(talent_hero_id, job_id)
	var check := JobCatalog.can_purchase_node(job_id, String(node.id), level, purchased)
	var state := "AUTO" if bool(node.auto_unlock) else ("ACQUIS" if purchased.has(String(node.id)) else String(check.get("reason", "")))
	var effect := ""
	match String(node.node_type):
		"skill":
			effect = "Compétence : %s" % skill_name(String(node.skill_id))
		"stat":
			effect = "%s %+d" % [String(node.stat_type).to_upper(), int(node.stat_value)]
		"passive":
			effect = "%s • %s %+d" % [String(node.passive_type), String(node.passive_target), int(node.passive_value)]
	talent_detail_label.text = "%s\n%s\n\n%s\nCoût : %d pt • niv.%d\n%s" % [String(node.display_name), String(node.description), effect, int(node.cost), int(node.required_level), state]
	talent_buy_button.disabled = not bool(check.get("ok", false))
	talent_buy_button.text = "ACQUÉRIR — %d PT" % int(node.cost)


func _on_talent_buy_pressed() -> void:
	if talent_hero_id.is_empty() or talent_selected_node_id.is_empty():
		return
	var job_id := String(campaign.hero_jobs.get(talent_hero_id, UnitCatalog.default_job(talent_hero_id)))
	var job_xp: Dictionary = campaign.hero_job_xp.get(talent_hero_id, {})
	var purchased := campaign.job_nodes(talent_hero_id, job_id)
	var check := JobCatalog.can_purchase_node(job_id, talent_selected_node_id, UnitCatalog.job_level(job_id, job_xp), purchased)
	if not bool(check.get("ok", false)):
		talent_detail_label.text += "\n\n⚠ %s" % String(check.get("reason", "Indisponible."))
		return
	if campaign.purchase_job_node(talent_hero_id, job_id, talent_selected_node_id):
		save_campaign()
		_refresh_talent_overlay()


func _on_talent_reset_pressed() -> void:
	if talent_hero_id.is_empty():
		return
	var job_id := String(campaign.hero_jobs.get(talent_hero_id, UnitCatalog.default_job(talent_hero_id)))
	campaign.reset_job_nodes(talent_hero_id, job_id)
	save_campaign()
	_refresh_talent_overlay()


func _on_gear_cycle(hero_id: String) -> void:
	var choices: Array = ["none"]
	for equipment_id in campaign.unlocked_equipment:
		choices.append(String(equipment_id))
	if choices.size() <= 1:
		prep_status_label.text = "Aucune relique débloquée pour l'instant."
		return
	var cursor := int(prep_gear_cycle_cursor.get(hero_id, 0))
	cursor = (cursor + 1) % choices.size()
	prep_gear_cycle_cursor[hero_id] = cursor
	var equipment_id := String(choices[cursor])
	if equipment_id == "none":
		for slot in ["weapon", "armor", "accessory"]:
			campaign.set_equipment(hero_id, slot, "none")
	else:
		campaign.set_equipment(hero_id, UnitCatalog.equipment_slot(equipment_id), equipment_id)
	save_campaign()
	update_prep_ui()


func equipment_name(equipment_id: String) -> String:
	return UnitCatalog.equipment_name(equipment_id)


func equipment_description(equipment_id: String) -> String:
	return UnitCatalog.equipment_description(equipment_id)


func reward_pool(index: int) -> Array:
	var mission_id := MissionCatalog.mission_id(index)
	var override := CampaignCatalog.reward_pool_override(mission_id)
	if not override.is_empty():
		return Array(override)
	return UnitCatalog.reward_pool(index)


func _on_reward_selected(index: int) -> void:
	if reward_selected or index < 0 or index >= reward_options.size():
		return
	var gear_id := str(reward_options[index])
	var duplicate := campaign.unlocked_equipment.has(gear_id)
	if duplicate:
		campaign.spores += 2
	else:
		campaign.unlocked_equipment.append(gear_id)
	reward_selected = true
	debrief_reward_label.text = (
		"RELIQUE DÉJÀ CONNUE : +2 Spores XP • Total %d • Rang %d" % [campaign.spores, campaign_rank()]
		if duplicate
		else "RÉCOMPENSE CHOISIE : %s" % equipment_name(gear_id)
	)
	for i in range(debrief_reward_buttons.size()):
		var button: Button = debrief_reward_buttons[i]
		button.disabled = true
		if i == index:
			button.text = "✓ %s — %s" % [equipment_name(gear_id), equipment_description(gear_id)]
	debrief_continue_button.disabled = false
	save_campaign()



func _on_start_mission_pressed() -> void:
	if selected_hero_count() != 3:
		return
	prep_overlay.visible = false
	debrief_overlay.visible = false
	campaign.mode = "battle"
	var mission_node := CampaignCatalog.node_for_mission_id(MissionCatalog.mission_id(campaign.mission_index))
	if mission_node != null:
		campaign.campaign_node_id = String(mission_node.id)
	save_campaign()
	reset_battle()


func _on_continue_campaign_pressed() -> void:
	debrief_overlay.visible = false
	if not mission_victory:
		save_campaign()
		show_prep_screen()
		return
	var mission_id := MissionCatalog.mission_id(campaign.mission_index)
	var next_node_id := CampaignCatalog.next_after_mission(
		mission_id, campaign.spores, campaign.loop, campaign.unlocked_equipment
	)
	if next_node_id.is_empty():
		progress_after_victory()
		return
	campaign.campaign_node_id = next_node_id
	_enter_campaign_node(next_node_id)


func show_debrief_screen() -> void:
	if campaign.mode != "battle":
		return
	campaign.mode = "debrief"
	debrief_overlay.visible = true
	prep_overlay.visible = false
	for button in debrief_reward_buttons:
		button.visible = mission_victory
		button.disabled = false
	if mission_victory:
		var contract_complete: bool = secondary_objective_completed()
		var contract_reward: int = 2 if contract_complete else 0
		var reward: int = maxi(1, 3 + bonus_collected + alive_count("player") + difficulty_xp_bonus() + contract_reward + CampaignCatalog.victory_spores_bonus(MissionCatalog.mission_id(campaign.mission_index)))
		var mastery_reward: int = 2 + int(campaign.difficulty_index)
		if not mission_reward_granted:
			campaign.spores += reward
			_grant_job_mastery_to_survivors(mastery_reward)
			mission_reward_granted = true
			campaign.max_unlocked = max(campaign.max_unlocked, min(mission_count() - 1, campaign.mission_index + 1))
			campaign.next_mission_buff = ""
		debrief_title_label.text = "MISSION RÉUSSIE"
		debrief_text_label.text = "Spores XP : +%d • Total %d • Rang %d\nMaîtrise job : +%d XP par survivant\nContrat : %s %s • difficulté %s (%s)\nBonus : %d/%d • Survivants : %d/%d\n\nChoisis un équipement permanent pour la Serre tactique." % [reward, campaign.spores, campaign_rank(), mastery_reward, "RÉUSSI" if contract_complete else "MANQUÉ", "+2 XP" if contract_complete else "+0 XP", difficulty_name(), difficulty_xp_label(), bonus_collected, bonus_target_total, alive_count("player"), selected_hero_count()]
		reward_options = reward_pool(campaign.mission_index)
		reward_selected = false
		debrief_reward_label.text = "RÉCOMPENSE — choisis 1 relique"
		for i in range(debrief_reward_buttons.size()):
			var button: Button = debrief_reward_buttons[i]
			if i < reward_options.size():
				var gear_id := str(reward_options[i])
				button.visible = true
				button.text = "%s — %s" % [equipment_name(gear_id), equipment_description(gear_id)]
			else:
				button.visible = false
		debrief_continue_button.disabled = not reward_options.is_empty()
		reward_selected = reward_options.is_empty()
		debrief_continue_button.text = "MISSION SUIVANTE" if campaign.mission_index < mission_count() - 1 else "NOUVELLE TOURNÉE+"
	else:
		debrief_title_label.text = "MISSION ÉCHOUÉE"
		debrief_text_label.text = "Aucune Spores XP perdue.\nTu peux modifier escouade, jobs et équipement avant de retenter.\n\nTotal : %d XP • Rang %d" % [campaign.spores, campaign_rank()]
		debrief_reward_label.text = ""
		reward_options.clear()
		reward_selected = true
		debrief_continue_button.disabled = false
		debrief_continue_button.text = "RETOUR À LA PRÉPARATION"


func _grant_job_mastery_to_survivors(amount: int) -> void:
	for unit in units:
		if String(unit.get("team", "")) != "player" or int(unit.get("hp", 0)) <= 0:
			continue
		var hero_id := String(unit.get("template_id", unit.get("id", "")))
		var job_id := String(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id)))
		var old_level := UnitCatalog.job_level(job_id, campaign.hero_job_xp.get(hero_id, {}))
		campaign.add_job_xp(hero_id, job_id, amount)
		var level := UnitCatalog.job_level(job_id, campaign.hero_job_xp.get(hero_id, {}))
		var level_note := " • +%d point(s) d'arbre" % (level - old_level) if level > old_level else ""
		log_message("%s gagne +%d maîtrise %s (niv.%d)%s." % [unit.get("name", hero_id), amount, UnitCatalog.job_name(job_id), level, level_note])


func _on_reset_save_pressed() -> void:
	if not reset_save_armed:
		reset_save_armed = true
		prep_reset_button.text = "CONFIRMER RESET"
		prep_status_label.text = "Un second clic efface la progression de campagne et recrée une sauvegarde neuve."
		return
	reset_save_armed = false
	campaign.reset_progress()
	prep_reset_button.text = "NOUVELLE CAMPAGNE"
	save_campaign()
	update_prep_ui()


func _on_mission_cycle_pressed() -> void:
	reset_save_armed = false
	prep_reset_button.text = "NOUVELLE CAMPAGNE"
	var available: int = clampi(int(campaign.max_unlocked), 0, mission_count() - 1)
	campaign.mission_index = (campaign.mission_index + 1) % (available + 1)
	var mission_node := CampaignCatalog.node_for_mission_id(MissionCatalog.mission_id(campaign.mission_index))
	if mission_node != null:
		campaign.campaign_node_id = String(mission_node.id)
	save_campaign()
	update_prep_ui()


func _on_difficulty_cycle_pressed() -> void:
	reset_save_armed = false
	prep_reset_button.text = "NOUVELLE CAMPAGNE"
	campaign.difficulty_index = (campaign.difficulty_index + 1) % 3
	save_campaign()
	update_prep_ui()


func difficulty_name() -> String:
	match campaign.difficulty_index:
		0:
			return "Détente"
		2:
			return "Tempête de spores"
		_:
			return "Groove"


func difficulty_description() -> String:
	match campaign.difficulty_index:
		0:
			return "ennemis -1 PV/-1 ATQ • -1 XP"
		2:
			return "ennemis +2 PV/+1 ATQ • +2 XP"
		_:
			return "équilibrée"


func difficulty_xp_bonus() -> int:
	match campaign.difficulty_index:
		0:
			return -1
		2:
			return 2
		_:
			return 0


func difficulty_xp_label() -> String:
	var value := difficulty_xp_bonus()
	if value >= 0:
		return "+%d XP" % value
	return "%d XP" % value


func apply_difficulty_to_enemies() -> void:
	for unit in units:
		if unit["team"] == "enemy":
			apply_difficulty_to_enemy(unit)


func apply_difficulty_to_enemy(unit: Dictionary) -> void:
	if campaign.loop > 0:
		unit["hp"] = int(unit["hp"]) + campaign.loop
		unit["max_hp"] = int(unit["max_hp"]) + campaign.loop
		unit["attack"] = int(unit["attack"]) + int(campaign.loop / 2)
	if campaign.difficulty_index == 0:
		unit["hp"] = max(1, int(unit["hp"]) - 1)
		unit["max_hp"] = int(unit["hp"])
		unit["attack"] = max(1, int(unit["attack"]) - 1)
	elif campaign.difficulty_index == 2:
		unit["hp"] = int(unit["hp"]) + 2
		unit["max_hp"] = int(unit["max_hp"]) + 2
		unit["attack"] = int(unit["attack"]) + 1
		unit["max_focus"] = int(unit.get("max_focus", 2)) + 1
		unit["focus"] = int(unit["max_focus"])


func mission_buff_name(buff_id: String) -> String:
	match buff_id:
		"focus":
			return "+1 Focus max au prochain combat"
		"guard":
			return "GARDE au déploiement"
		_:
			return "aucun"


func apply_pending_mission_buff() -> void:
	if campaign.next_mission_buff.is_empty():
		return
	for unit in units:
		if unit["team"] != "player":
			continue
		if campaign.next_mission_buff == "focus":
			unit["max_focus"] = int(unit.get("max_focus", 2)) + 1
			unit["focus"] = int(unit["max_focus"])
		elif campaign.next_mission_buff == "guard":
			add_status(unit, "guarded")
	log_message("BONUS D'INTERMISSION : %s." % mission_buff_name(campaign.next_mission_buff))


func secondary_objective_text(index: int) -> String:
	return MissionCatalog.secondary_objective_text(index)


func secondary_objective_progress_text() -> String:
	match campaign.mission_index:
		0:
			return "CONTRAT %d/%d vinyles" % [bonus_collected, bonus_target_total]
		1:
			return "CONTRAT %d/%d héros debout" % [alive_count("player"), selected_hero_count()]
		_:
			return "CONTRAT manche %d/4" % current_turn


func secondary_objective_completed() -> bool:
	match campaign.mission_index:
		0:
			return bonus_target_total > 0 and bonus_collected >= bonus_target_total
		1:
			return alive_count("player") == selected_hero_count()
		_:
			return current_turn <= 4


func _apply_campaign_event_reward(reward_type: String, reward_value: int) -> void:
	match reward_type:
		"xp":
			campaign.spores += max(0, reward_value)
		"focus_buff":
			campaign.next_mission_buff = "focus"
		"guard_buff":
			campaign.next_mission_buff = "guard"


func _enter_campaign_node(node_id: String) -> void:
	var resolved := CampaignCatalog.resolve_node_id(
		node_id, campaign.spores, campaign.loop, campaign.unlocked_equipment
	)
	if resolved.is_empty():
		progress_after_victory()
		return
	var node := CampaignCatalog.node(resolved)
	if node == null:
		progress_after_victory()
		return
	campaign.campaign_node_id = resolved
	match String(node.node_type):
		"event":
			show_campaign_event(resolved)
		"mission":
			var index := MissionCatalog.index_for_id(String(node.mission_id))
			if index >= 0:
				campaign.mission_index = index
				campaign.max_unlocked = max(campaign.max_unlocked, index)
				campaign.mode = "prep"
				save_campaign()
				show_prep_screen()
			else:
				log_message("Campagne : mission inconnue %s." % String(node.mission_id))
				show_prep_screen()
		"end":
			_complete_campaign_tour()
		_:
			show_prep_screen()


func show_campaign_event(node_id: String) -> void:
	var node := CampaignCatalog.node(node_id)
	if node == null or String(node.node_type) != "event":
		return
	campaign.mode = "event"
	event_current_node_id = node_id
	event_source_mission = campaign.mission_index
	prep_overlay.visible = false
	debrief_overlay.visible = false
	event_overlay.visible = true
	event_title_label.text = String(node.title).to_upper()
	event_text_label.text = String(node.body)
	event_choice_a.text = String(node.choice_a_label)
	event_choice_b.text = String(node.choice_b_label)
	event_choice_a.visible = not String(node.choice_a_label).is_empty()
	event_choice_b.visible = not String(node.choice_b_label).is_empty()
	save_campaign()


func show_intermission_event(source_mission: int) -> void:
	# Compatibility shim for V0.9/V1.2 callers: resolve the next graph node from the mission.
	var next_id := CampaignCatalog.next_after_mission(
		MissionCatalog.mission_id(source_mission), campaign.spores, campaign.loop, campaign.unlocked_equipment
	)
	if not next_id.is_empty():
		_enter_campaign_node(next_id)


func _on_event_choice(choice: int) -> void:
	if event_current_node_id.is_empty():
		return
	var node := CampaignCatalog.node(event_current_node_id)
	if node == null:
		return
	var reward_type := String(node.choice_a_reward_type) if choice == 0 else String(node.choice_b_reward_type)
	var reward_value := int(node.choice_a_reward_value) if choice == 0 else int(node.choice_b_reward_value)
	var next_id := String(node.choice_a_next_node_id) if choice == 0 else String(node.choice_b_next_node_id)
	_apply_campaign_event_reward(reward_type, reward_value)
	event_overlay.visible = false
	event_current_node_id = ""
	event_source_mission = -1
	save_campaign()
	_enter_campaign_node(next_id)


func _complete_campaign_tour() -> void:
	campaign.mode = "prep"
	campaign.completed = true
	campaign.loop += 1
	campaign.wins = 0
	var start_id := CampaignCatalog.start_node_id()
	if start_id.is_empty():
		campaign.mission_index = 0
		campaign.campaign_node_id = ""
	else:
		campaign.campaign_node_id = start_id
		var index := CampaignCatalog.mission_index_for_node(start_id)
		campaign.mission_index = max(0, index)
	save_campaign()
	show_prep_screen()


func progress_after_victory() -> void:
	# Fallback path for custom missions that are not connected to the campaign graph.
	campaign.mode = "prep"
	campaign.wins += 1
	var completed_index := campaign.mission_index
	campaign.max_unlocked = max(campaign.max_unlocked, min(mission_count() - 1, completed_index + 1))
	if completed_index >= mission_count() - 1:
		_complete_campaign_tour()
		return
	campaign.mission_index = min(completed_index + 1, campaign.max_unlocked)
	var mission_node := CampaignCatalog.node_for_mission_id(MissionCatalog.mission_id(campaign.mission_index))
	if mission_node != null:
		campaign.campaign_node_id = String(mission_node.id)
	save_campaign()
	show_prep_screen()


func save_campaign() -> void:
	if editor_test_mode:
		return
	SaveManager.save_campaign(campaign)


func load_campaign_save() -> void:
	SaveManager.load_campaign(campaign)
	_normalize_v18_progression()
	var last_index: int = maxi(0, mission_count() - 1)
	campaign.mission_index = clamp(campaign.mission_index, 0, last_index)
	campaign.max_unlocked = clamp(max(campaign.max_unlocked, campaign.mission_index), 0, last_index)
	if campaign.campaign_node_id.is_empty() or CampaignCatalog.node(campaign.campaign_node_id) == null:
		var mission_node := CampaignCatalog.node_for_mission_id(MissionCatalog.mission_id(campaign.mission_index))
		campaign.campaign_node_id = String(mission_node.id) if mission_node != null else CampaignCatalog.start_node_id()


func _normalize_v18_progression() -> void:
	for hero_id in ["momo", "pipo", "ziggy", "luma"]:
		var default_job := UnitCatalog.default_job(hero_id)
		var current_job := String(campaign.hero_jobs.get(hero_id, default_job))
		var available := UnitCatalog.available_jobs(hero_id)
		if current_job.is_empty() or not available.has(current_job):
			campaign.hero_jobs[hero_id] = default_job
		var old_slots: Dictionary = campaign.hero_equipment_slots.get(hero_id, {})
		var normalized := {"weapon": "none", "armor": "none", "accessory": "none"}
		for slot in ["weapon", "armor", "accessory"]:
			var equipment_id := String(old_slots.get(slot, "none"))
			if equipment_id == "none" or not campaign.unlocked_equipment.has(equipment_id):
				continue
			normalized[UnitCatalog.equipment_slot(equipment_id)] = equipment_id
		campaign.hero_equipment_slots[hero_id] = normalized
		campaign.hero_equipment[hero_id] = String(normalized["accessory"])


func selected_hero_count() -> int:
	return campaign.selected_hero_count()


func campaign_rank() -> int:
	return campaign.rank()


func hero_name(hero_id: String) -> String:
	return UnitCatalog.hero_name(hero_id)


func hero_role(hero_id: String) -> String:
	return UnitCatalog.hero_role(hero_id)


func hero_module_name(hero_id: String) -> String:
	return UnitCatalog.module_name(hero_id, int(campaign.hero_modules.get(hero_id, 0)))


func hero_module_description(hero_id: String) -> String:
	return UnitCatalog.module_description(hero_id, int(campaign.hero_modules.get(hero_id, 0)))


func mission_count() -> int:
	return max(1, MissionCatalog.count())


func mission_meta(index: int) -> Dictionary:
	return MissionCatalog.meta(index)


func reset_battle() -> void:
	battle_serial += 1
	units.clear()
	visual_paths.clear()
	attack_fx.clear()
	hit_fx.clear()
	floating_text_fx.clear()
	projectile_fx.clear()
	particle_fx.clear()
	shake_strength = 0.0
	special_targeting = false
	special_target_skill_id = ""
	special_target_cells.clear()
	crown_carrier_id = ""
	enemies_cleared_logged = false
	mission_victory = false
	mission_reward_granted = false
	reward_selected = false
	reward_options.clear()
	timeline_order.clear()
	timeline_index = -1
	active_unit_id = ""
	activation_count_in_round = 0
	round_activation_budget = 0
	activated_this_round.clear()
	battle_clock_ticks = 0
	battle_rng.seed = 0x5F0A0000 + battle_serial
	terrain_heights.clear()
	bonus_collected = 0
	current_turn = 1
	rounds_completed = 0
	enemy_phase = false
	game_over = false
	message_log.clear()
	fired_trigger_ids.clear()
	evaluating_triggers = false
	pending_trigger_sequences.clear()
	event_sequence_running = false
	battle_sequence_serial += 1
	interactable_states.clear()
	runtime_objective_text = ""
	runtime_phase = ""
	runtime_victory_rules.clear()
	runtime_defeat_rules.clear()
	runtime_victory_rule_mode = "any"
	runtime_defeat_rule_mode = "any"
	cinematic_camera_offset = Vector2.ZERO
	cinematic_camera_zoom = 1.0
	_hide_cinematic_dialogue()
	_set_cinematic_fade_alpha(0.0)

	setup_mission_environment(campaign.mission_index)
	append_selected_squad(campaign.mission_index)
	apply_pending_mission_buff()
	append_mission_enemies(campaign.mission_index)
	apply_difficulty_to_enemies()
	enemies_total_initial = alive_count("enemy")
	bonus_target_total = bonus_cells.size()
	selected_id = ""
	var mission := mission_meta(campaign.mission_index)
	mission_description_label.text = "MISSION %d/%d : %s\n%s" % [campaign.mission_index + 1, mission_count(), mission["name"], mission["brief"]]
	log_message("Déploiement : %s. Rang %d • %s." % [mission["name"], campaign_rank(), difficulty_name()])
	log_message("CONTRAT : %s" % secondary_objective_text(campaign.mission_index))
	if campaign.mission_index == 0:
		log_message("Récupère la Couronne Beatbox puis reviens dans la zone verte.")
	elif campaign.mission_index == 1:
		log_message("Tiens 3 manches. Les vinyles donnent toujours un petit soin.")
	else:
		log_message("Dernier rappel : élimine tous les ennemis d'élite.")
	call_deferred("_start_battle_with_intro")


func _start_battle_with_intro() -> void:
	var serial := battle_sequence_serial
	var cinematic_id := ""
	if active_mission_definition != null:
		cinematic_id = String(active_mission_definition.intro_cinematic_id)
	if not cinematic_id.is_empty() and CinematicCatalog.definition(cinematic_id) != null:
		event_sequence_running = true
		await _run_action_sequence(_cinematic_actions(cinematic_id), serial, false, 0)
		event_sequence_running = false
	if serial != battle_sequence_serial or game_over or campaign.mode != "battle":
		return
	start_round()


func setup_mission_environment(index: int) -> void:
	active_mission_definition = MissionCatalog.definition(index)
	if active_mission_definition != null:
		active_mission_definition.interactables = MissionCatalog.interactables(index)
	var data := MissionCatalog.environment(index)
	mission_objective = str(data["objective"])
	survival_rounds = int(data["survival_rounds"])
	obstacles = data["obstacles"].duplicate()
	cover_cells = data["cover"].duplicate()
	hazard_cells = data["hazards"].duplicate()
	extraction_cells = data["extraction"].duplicate()
	bonus_cells = data["bonus"].duplicate()
	crown_cell = data["crown"]
	terrain_heights = data["heights"].duplicate()
	mission_zones.clear()
	var raw_zones: Variant = data.get("zones", [])
	if raw_zones is Array:
		for raw_zone: Variant in raw_zones:
			if raw_zone is Dictionary:
				mission_zones.append((raw_zone as Dictionary).duplicate(true))
	grid_width = maxi(4, int(data.get("grid_width", 10)))
	grid_height = maxi(4, int(data.get("grid_height", 8)))
	cell_size = minf(70.0, minf(700.0 / float(grid_width), 560.0 / float(grid_height)))
	_setup_runtime_mission_logic()
	_setup_interactables()


func append_selected_squad(index: int) -> void:
	var starts := MissionCatalog.hero_starts(index)
	var selected_ids: Array = []
	for hero_id in ["momo", "pipo", "ziggy", "luma"]:
		if bool(campaign.hero_selected.get(hero_id, false)):
			selected_ids.append(hero_id)
	for i in range(selected_ids.size()):
		var start := Vector2i(i, grid_height - 1)
		if i < starts.size():
			start = starts[i]
		units.append(make_hero(str(selected_ids[i]), start))


func make_hero(hero_id: String, position: Vector2i) -> Dictionary:
	return UnitCatalog.make_hero(
		hero_id,
		position,
		campaign_rank(),
		String(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id))),
		campaign.hero_job_xp.get(hero_id, {}),
		campaign.hero_equipment_slots.get(hero_id, {}),
		campaign.job_nodes(hero_id, String(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id))))
	)


func apply_equipment_to_hero(unit: Dictionary, equipment_id: String) -> void:
	UnitCatalog.apply_equipment(unit, equipment_id)


func append_mission_enemies(index: int) -> void:
	for spec in MissionCatalog.enemy_specs(index):
		units.append(
			make_unit(
				str(spec["id"]), str(spec["name"]), str(spec["role"]), "enemy",
				spec["position"], int(spec["hp"]), int(spec["attack"]), int(spec["move"]),
				int(spec["range"]), spec["color"], str(spec["special"])
			)
		)


func set_height(cells: Array, value: int) -> void:
	for cell in cells:
		terrain_heights[cell] = value


func make_unit(
	id: String,
	unit_name: String,
	role: String,
	team: String,
	position: Vector2i,
	hp: int,
	attack: int,
	move_range: int,
	attack_range: int,
	color: Color,
	special: String
) -> Dictionary:
	return UnitCatalog.make_unit(
		id, unit_name, role, team, position, hp, attack, move_range, attack_range, color, special
	)


func secondary_skill_for_id(id: String) -> String:
	return SkillCatalog.secondary_for_unit(id)


func skill_name(skill_id: String) -> String:
	return SkillCatalog.display_name(skill_id)


func skill_cost(skill_id: String) -> int:
	return SkillCatalog.focus_cost(skill_id)


func skill_cooldown(skill_id: String) -> int:
	return SkillCatalog.cooldown_rounds(skill_id)


func cooldown_left(unit: Dictionary, skill_id: String) -> int:
	return SkillCatalog.cooldown_left(unit, skill_id)


func can_use_skill(unit: Dictionary, skill_id: String) -> bool:
	return SkillCatalog.can_use(unit, skill_id)


func spend_skill(unit: Dictionary, skill_id: String) -> void:
	SkillCatalog.spend(unit, skill_id)


func tick_round_resources(unit: Dictionary) -> void:
	SkillCatalog.tick_round(unit)


func _unhandled_input(event: InputEvent) -> void:
	if cinematic_dialogue_waiting:
		if event is InputEventKey:
			var dialogue_key := event as InputEventKey
			if dialogue_key.pressed and not dialogue_key.echo and dialogue_key.keycode in [KEY_ENTER, KEY_SPACE, KEY_ESCAPE]:
				_on_cinematic_continue_pressed()
				return
		elif event is InputEventMouseButton:
			var dialogue_mouse := event as InputEventMouseButton
			if dialogue_mouse.pressed and dialogue_mouse.button_index == MOUSE_BUTTON_LEFT:
				_on_cinematic_continue_pressed()
				return
	if campaign.mode != "battle":
		return
	if _battle_sequences_pending():
		return
	if event is InputEventMouseMotion:
		var motion_event := event as InputEventMouseMotion
		hovered_cell = world_to_cell(motion_event.position)
		update_preview()
		queue_redraw()
	elif event is InputEventMouseButton:
		var mouse_event := event as InputEventMouseButton
		if mouse_event.button_index == MOUSE_BUTTON_LEFT and mouse_event.pressed:
			var clicked_cell := world_to_cell(mouse_event.position)
			if special_targeting:
				handle_special_target_click(clicked_cell)
			else:
				handle_board_click(clicked_cell)
		elif mouse_event.button_index == MOUSE_BUTTON_RIGHT and mouse_event.pressed:
			if special_targeting:
				cancel_special_targeting()
			else:
				orient_selected_toward(world_to_cell(mouse_event.position))
	elif event is InputEventKey:
		var key_event := event as InputEventKey
		if key_event.pressed and not key_event.echo:
			if key_event.keycode == KEY_R:
				reset_battle()
			elif key_event.keycode == KEY_ENTER:
				_on_end_turn_pressed()
			elif key_event.keycode == KEY_M:
				sound_enabled = not sound_enabled
				log_message("Sons de feedback : %s." % ("ON" if sound_enabled else "OFF"))
				update_ui()
			elif key_event.keycode == KEY_ESCAPE:
				selected_id = ""
				update_selection()
				update_ui()
				update_preview()
				queue_redraw()


func orient_selected_toward(cell: Vector2i) -> void:
	if game_over or enemy_phase or not is_inside(cell):
		return
	var unit := selected_unit()
	if unit.is_empty() or unit["id"] != active_unit_id or cell == unit["pos"]:
		return
	unit["facing"] = direction_from_to(unit["pos"], cell)
	log_message("%s ajuste son orientation. Très dramatique, très tactique." % unit["name"])
	update_ui()
	update_preview()
	queue_redraw()


func handle_board_click(cell: Vector2i) -> void:
	if game_over or enemy_phase or not is_inside(cell):
		return

	var clicked := unit_at(cell)
	if not clicked.is_empty() and clicked["team"] == "player":
		if clicked["id"] == active_unit_id:
			selected_id = clicked["id"]
			refresh_all()
		else:
			log_message("Pas son activation : la timeline est une petite dictature très organisée.")
			update_ui()
		return

	var unit := selected_unit()
	if unit.is_empty() or unit["id"] != active_unit_id:
		return

	if clicked.is_empty() and not unit["has_moved"] and move_cells.has(cell):
		perform_move(unit, cell)
	elif (
		not clicked.is_empty()
		and clicked["team"] == "enemy"
		and not unit["has_acted"]
		and attack_cells.has(cell)
	):
		perform_attack(unit, clicked)
	else:
		log_message("Cette case n'est pas disponible. Même le narrateur ne peut pas tricher.")
		update_ui()
		update_preview()


func perform_move(unit: Dictionary, destination: Vector2i) -> void:
	var movement_cost := int(move_costs.get(destination, manhattan(unit["pos"], destination)))
	var origin: Vector2i = unit["pos"]
	var visual_path := movement_path_for(unit, destination)
	unit["facing"] = direction_from_to(origin, destination)
	unit["pos"] = destination
	unit["has_moved"] = true
	start_move_animation(str(unit["id"]), visual_path)
	play_feedback_tone("move")
	resolve_reactions_on_move(unit, origin, destination)
	if int(unit["hp"]) <= 0:
		log_message("%s est K.O. pendant son déplacement : réaction ennemie !" % unit["name"])
		check_mission_end()
		refresh_all()
		return
	check_crown_pickup(unit)
	check_bonus_pickup(unit)
	_handle_interactable_entry(unit)
	_evaluate_battle_triggers("unit_moved", unit)
	var terrain_note := ""
	if terrain_height(destination) > 0:
		terrain_note = " et grimpe à hauteur %d" % terrain_height(destination)
	if cover_cells.has(destination):
		terrain_note += " sous couverture"
	log_message(
		(
			"%s dépense %d point(s) de déplacement%s. La démarche reste fabuleuse."
			% [unit["name"], movement_cost, terrain_note]
		)
	)
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func _reaction_available(unit: Dictionary, expected_type: String = "") -> bool:
	if unit.is_empty() or int(unit.get("hp", 0)) <= 0:
		return false
	var reaction_type := String(unit.get("reaction_type", "none"))
	if reaction_type == "none" or (not expected_type.is_empty() and reaction_type != expected_type):
		return false
	return not bool(unit.get("reaction_used", false))


func _find_interceptor(attacker: Dictionary, protected_target: Dictionary) -> Dictionary:
	var best: Dictionary = {}
	var best_hp := -1
	for candidate in units:
		if candidate.get("team", "") != protected_target.get("team", "") or candidate.get("id", "") == protected_target.get("id", ""):
			continue
		if not _reaction_available(candidate, "intercept"):
			continue
		if manhattan(candidate["pos"], protected_target["pos"]) > int(candidate.get("reaction_range", 1)):
			continue
		if int(candidate.get("hp", 0)) > best_hp:
			best_hp = int(candidate["hp"])
			best = candidate
	return best


func _try_counter_reaction(reactor: Dictionary, attacker: Dictionary) -> void:
	if not _reaction_available(reactor, "counter") or int(attacker.get("hp", 0)) <= 0:
		return
	var counter_distance: int = manhattan(reactor["pos"], attacker["pos"])
	var counter_max: int = mini(int(reactor.get("reaction_range", effective_range(reactor))), effective_range(reactor))
	if not CombatMechanics.range_allowed(counter_distance, effective_min_range(reactor), counter_max):
		return
	if not has_line_of_sight(reactor["pos"], attacker["pos"], String(reactor["id"]), String(attacker["id"])):
		return
	reactor["reaction_used"] = true
	reactor["facing"] = direction_from_to(reactor["pos"], attacker["pos"])
	StatusCatalog.remove_on_attack(reactor)
	var counter_hit := hit_profile(reactor, attacker, 80)
	if not _roll_hit(int(counter_hit["chance"])):
		spawn_floating_text(attacker["pos"], "CONTRE MISS", TEXT_SOFT)
		log_message("CONTRE : %s rate %s (%d%%)." % [reactor["name"], attacker["name"], int(counter_hit["chance"])])
		return
	var counter_damage := maxi(1, status_adjusted_direct_damage(effective_basic_attack_power(reactor) + int(reactor.get("reaction_damage_bonus", 0)), attacker, reactor, String(reactor.get("basic_attack_damage_type", "physical"))))
	var counter_block: Dictionary = _apply_shield_block(attacker, counter_damage)
	counter_damage = int(counter_block["damage"])
	spawn_damage_feedback(reactor, attacker, counter_damage, GOLD)
	apply_damage(attacker, counter_damage)
	log_message("CONTRE : %s riposte sur %s pour %d dégât(s)." % [reactor["name"], attacker["name"], counter_damage])


func perform_attack(attacker: Dictionary, target: Dictionary) -> void:
	var chance_profile := hit_profile(attacker, target)
	attacker["facing"] = direction_from_to(attacker["pos"], target["pos"])
	attacker["has_acted"] = true
	StatusCatalog.remove_on_attack(attacker)
	if not _roll_hit(int(chance_profile["chance"])):
		spawn_floating_text(target["pos"], "MISS", TEXT_SOFT)
		log_message("%s rate %s • %d%% HIT • %s." % [attacker["name"], target["name"], int(chance_profile["chance"]), String(chance_profile["arc"]).to_upper()])
		update_selection()
		update_ui()
		update_preview()
		queue_redraw()
		return

	var recipient := target
	var interceptor := _find_interceptor(attacker, target)
	var intercept_note := ""
	if not interceptor.is_empty():
		interceptor["reaction_used"] = true
		interceptor["facing"] = direction_from_to(interceptor["pos"], attacker["pos"])
		recipient = interceptor
		intercept_note = " • INTERCEPTION %s" % interceptor["name"]
		spawn_floating_text(interceptor["pos"], "INTERCEPTION", SKY)
	var profile := damage_profile(attacker, recipient)
	var damage := int(profile["damage"])
	if not interceptor.is_empty():
		damage = maxi(1, damage - 1)
	var block: Dictionary = _apply_shield_block(recipient, damage)
	damage = int(block["damage"])
	if bool(block["blocked"]):
		spawn_floating_text(recipient["pos"], "BLOC -%d" % int(block["reduction"]), SKY)
	spawn_damage_feedback(attacker, recipient, damage)
	apply_damage(recipient, damage)
	if int(profile["guard_penalty"]) > 0:
		remove_status(recipient, "guarded")
	log_message("%s frappe %s : %d dégâts • HIT %d%%%s%s." % [attacker["name"], recipient["name"], damage, int(chance_profile["chance"]), profile["summary"], intercept_note])
	if int(recipient["hp"]) <= 0:
		log_message("%s est K.O. et dépose une réclamation en trois exemplaires." % recipient["name"])
	else:
		_try_counter_reaction(recipient, attacker)
	check_mission_end()
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func _on_special_pressed() -> void:
	if game_over or enemy_phase or campaign.mode != "battle" or _battle_sequences_pending():
		return
	var unit := selected_unit()
	if unit.is_empty() or unit["id"] != active_unit_id or unit["has_acted"]:
		return
	_activate_player_skill(unit, str(unit["special"]))


func _on_secondary_pressed() -> void:
	if game_over or enemy_phase or campaign.mode != "battle" or _battle_sequences_pending():
		return
	var unit := selected_unit()
	if unit.is_empty() or unit["id"] != active_unit_id or bool(unit["has_acted"]):
		return
	_activate_player_skill(unit, str(unit.get("secondary", "")))


func _activate_player_skill(unit: Dictionary, skill_id: String) -> void:
	if not can_use_skill(unit, skill_id):
		log_message("%s indisponible : Focus %d/%d • cooldown %d." % [skill_name(skill_id), int(unit.get("focus", 0)), skill_cost(skill_id), cooldown_left(unit, skill_id)])
		update_ui()
		return
	if not SkillCatalog.has_effects(skill_id):
		log_message("%s n'a aucun bloc d'effet dans Sporebound Studio." % skill_name(skill_id))
		return
	var target_mode := SkillCatalog.target_mode(skill_id)
	if target_mode == "ground":
		if special_targeting and special_target_skill_id == skill_id:
			cancel_special_targeting()
			return
		special_targeting = true
		special_target_skill_id = skill_id
		special_target_cells = special_targetable_cells(unit, SkillCatalog.skill_range(skill_id), skill_id)
		log_message("%s armé : choisis une case violette, clic droit pour annuler." % skill_name(skill_id))
		refresh_all()
		return
	var target := _choose_skill_target(unit, skill_id)
	if target.is_empty():
		log_message("%s : aucune cible valide à portée." % skill_name(skill_id))
		update_ui()
		return
	_commit_skill(unit, skill_id, target, target["pos"])


func _choose_skill_target(source: Dictionary, skill_id: String) -> Dictionary:
	var target_mode := SkillCatalog.target_mode(skill_id)
	if target_mode == "self":
		return source
	var wanted_team: String = String(source["team"]) if target_mode == "ally" else ("enemy" if String(source["team"]) == "player" else "player")
	var skill_range_value := SkillCatalog.skill_range(skill_id)
	var best: Dictionary = {}
	var best_score := 999999
	var can_revive: bool = SkillCatalog.has_tag(skill_id, "revive") and wanted_team == source["team"]
	for candidate in units:
		if candidate["team"] != wanted_team:
			continue
		if int(candidate["hp"]) <= 0 and not (can_revive and _unit_is_downed(candidate)):
			continue
		var distance := manhattan(source["pos"], candidate["pos"])
		if distance > skill_range_value:
			continue
		if distance > 1 and not has_line_of_sight(source["pos"], candidate["pos"], source["id"], candidate["id"]):
			continue
		var score := distance
		if wanted_team == source["team"]:
			if _unit_is_downed(candidate):
				score = -100000 + distance
			else:
				score = int(candidate["hp"]) * 10 - (int(candidate["max_hp"]) - int(candidate["hp"])) * 20 + distance
		else:
			score = int(candidate["hp"]) * 10 + distance
		if score < best_score:
			best_score = score
			best = candidate
	return best


func cancel_special_targeting() -> void:
	special_targeting = false
	special_target_skill_id = ""
	special_target_cells.clear()
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func handle_special_target_click(cell: Vector2i) -> void:
	if not special_targeting or not special_target_cells.has(cell):
		log_message("Choisis une case violette valide, ou clic droit pour annuler.")
		update_preview()
		return
	var unit := selected_unit()
	var skill_id := special_target_skill_id
	if unit.is_empty() or unit["id"] != active_unit_id or unit["has_acted"] or skill_id.is_empty():
		cancel_special_targeting()
		return
	_commit_skill(unit, skill_id, {}, cell)


func _commit_skill(source: Dictionary, skill_id: String, primary_target: Dictionary, anchor_cell: Vector2i) -> void:
	if skill_id.is_empty() or not SkillCatalog.has_effects(skill_id):
		return
	var cast_ticks: int = SkillCatalog.cast_time_ticks(skill_id)
	if cast_ticks <= 0:
		_execute_composed_skill(source, skill_id, primary_target, anchor_cell, true)
		return
	var target_id := ""
	if not primary_target.is_empty():
		target_id = String(primary_target.get("id", ""))
	if not primary_target.is_empty():
		source["facing"] = direction_from_to(source["pos"], primary_target["pos"])
	elif anchor_cell != source["pos"]:
		source["facing"] = direction_from_to(source["pos"], anchor_cell)
	source["casting"] = {
		"skill_id": skill_id,
		"target_id": target_id,
		"anchor_cell": anchor_cell,
		"remaining_ticks": cast_ticks,
		"interrupt_on_damage": SkillCatalog.interrupt_on_damage(skill_id),
	}
	spend_skill(source, skill_id)
	StatusCatalog.remove_on_attack(source)
	special_targeting = false
	special_target_skill_id = ""
	special_target_cells.clear()
	log_message("%s prépare %s • lancement dans %d tick(s) CT." % [source["name"], skill_name(skill_id), cast_ticks])
	spawn_floating_text(source["pos"], "CAST %d" % cast_ticks, VIOLET)
	refresh_all()


func _resolve_due_cast(caster_id: String) -> void:
	var source := unit_by_id(caster_id)
	if source.is_empty() or int(source.get("hp", 0)) <= 0 or not _unit_is_casting(source):
		return
	var casting: Dictionary = source.get("casting", {}).duplicate(true)
	var skill_id := String(casting.get("skill_id", ""))
	var target_id := String(casting.get("target_id", ""))
	var anchor_value: Variant = casting.get("anchor_cell", source.get("pos", Vector2i.ZERO))
	var source_pos: Vector2i = source.get("pos", Vector2i.ZERO)
	var anchor_cell: Vector2i = anchor_value if anchor_value is Vector2i else source_pos
	source["casting"] = {}
	if skill_id.is_empty() or int(source.get("hp", 0)) <= 0:
		return
	var target: Dictionary = {}
	if not target_id.is_empty():
		target = unit_by_id(target_id)
		var revive_target_valid: bool = SkillCatalog.has_tag(skill_id, "revive") and _unit_is_downed(target)
		if target.is_empty() or (int(target.get("hp", 0)) <= 0 and not revive_target_valid):
			log_message("%s : %s se dissipe, la cible n'est plus valide." % [source["name"], skill_name(skill_id)])
			spawn_floating_text(source["pos"], "CAST PERDU", CORAL)
			return
		anchor_cell = target["pos"]
	log_message("CAST : %s libère %s." % [source["name"], skill_name(skill_id)])
	_execute_composed_skill(source, skill_id, target, anchor_cell, false)


func _interrupt_cast_if_needed(target: Dictionary, damage: int) -> void:
	if damage <= 0 or target.is_empty() or not _unit_is_casting(target):
		return
	var casting: Dictionary = target.get("casting", {})
	if not bool(casting.get("interrupt_on_damage", true)):
		return
	var skill_id := String(casting.get("skill_id", ""))
	target["casting"] = {}
	spawn_floating_text(target["pos"], "INTERROMPU", CORAL)
	log_message("INTERRUPTION : %s perd %s après avoir subi des dégâts." % [target["name"], skill_name(skill_id)])


func _execute_composed_skill(source: Dictionary, skill_id: String, primary_target: Dictionary, anchor_cell: Vector2i, spend_cost: bool = true) -> void:
	if skill_id.is_empty() or not SkillCatalog.has_effects(skill_id):
		return
	if not primary_target.is_empty():
		source["facing"] = direction_from_to(source["pos"], primary_target["pos"])
	elif anchor_cell != source["pos"]:
		source["facing"] = direction_from_to(source["pos"], anchor_cell)
	var skill_vfx_id := SkillCatalog.vfx_id(skill_id)
	if not skill_vfx_id.is_empty():
		spawn_visual_effect(skill_vfx_id, anchor_cell, source["pos"], anchor_cell)
	var touched := 0
	var missed_targets: Dictionary = {}
	var hit_results: Dictionary = {}
	for effect in SkillCatalog.effects(skill_id):
		if effect == null:
			continue
		var targets := _targets_for_skill_effect(source, primary_target, anchor_cell, effect)
		for target in targets:
			var target_id := String(target.get("id", ""))
			if SkillCatalog.uses_accuracy(skill_id) and target.get("team", "") != source.get("team", ""):
				if not hit_results.has(target_id):
					var profile := hit_profile(source, target, SkillCatalog.accuracy(skill_id), SkillCatalog.has_tag(skill_id, "ignore_cover"))
					hit_results[target_id] = _roll_hit(int(profile["chance"]))
					if not bool(hit_results[target_id]):
						missed_targets[target_id] = true
						spawn_floating_text(target["pos"], "MISS", TEXT_SOFT)
						log_message("%s rate %s avec %s (%d%%)." % [source["name"], target["name"], skill_name(skill_id), int(profile["chance"])])
				if not bool(hit_results[target_id]):
					continue
			_apply_skill_effect(source, target, anchor_cell, skill_id, effect)
			touched += 1
	if _has_guard_after_skill(source, skill_id):
		add_status(source, "guarded")
	if spend_cost:
		spend_skill(source, skill_id)
		StatusCatalog.remove_on_attack(source)
	special_targeting = false
	special_target_skill_id = ""
	special_target_cells.clear()
	log_message("%s lance %s : %d application(s)%s." % [source["name"], skill_name(skill_id), touched, " • %d cible(s) esquivent" % missed_targets.size() if not missed_targets.is_empty() else ""])
	check_mission_end()
	refresh_all()


func _targets_for_skill_effect(source: Dictionary, primary_target: Dictionary, anchor_cell: Vector2i, effect: Resource) -> Array:
	var scope := String(effect.target_scope)
	if scope == "self":
		return [source]
	if scope == "target":
		if not primary_target.is_empty():
			return [primary_target]
		var on_cell := unit_at(anchor_cell)
		return [] if on_cell.is_empty() else [on_cell]
	var wanted_team: String = String(source["team"]) if scope == "allies" else ("enemy" if String(source["team"]) == "player" else "player")
	var source_cell: Vector2i = anchor_cell
	var source_position_value: Variant = source.get("pos", anchor_cell)
	if source_position_value is Vector2i:
		source_cell = source_position_value
	var result: Array = []
	for candidate in units:
		if candidate["team"] != wanted_team or int(candidate["hp"]) <= 0:
			continue
		if _cell_in_effect_area(candidate["pos"], anchor_cell, int(effect.radius), String(effect.area_shape), source_cell):
			result.append(candidate)
	return result


func _cell_in_effect_area(cell: Vector2i, center: Vector2i, radius: int, shape: String, source_cell: Vector2i = Vector2i(-999, -999)) -> bool:
	if radius <= 0 or shape == "single":
		return cell == center
	var delta: Vector2i = cell - center
	if shape == "cross":
		return (delta.x == 0 or delta.y == 0) and absi(delta.x) + absi(delta.y) <= radius
	if shape == "circle":
		return delta.x * delta.x + delta.y * delta.y <= radius * radius
	if shape == "line" and source_cell != Vector2i(-999, -999):
		var direction: Vector2i = direction_from_to(source_cell, center)
		if direction == Vector2i.ZERO:
			direction = Vector2i.DOWN
		var source_delta: Vector2i = cell - source_cell
		var forward: int = source_delta.x * direction.x + source_delta.y * direction.y
		var perpendicular: int = source_delta.x * direction.y - source_delta.y * direction.x
		var length: int = maxi(radius, manhattan(source_cell, center))
		return perpendicular == 0 and forward >= 1 and forward <= length
	return manhattan(cell, center) <= radius


func _skill_effect_amount(source: Dictionary, skill_id: String, effect: Resource) -> int:
	var amount := int(effect.amount)
	if bool(effect.use_attack_stat):
		amount += effective_physical_power(source) if String(effect.damage_type) == "physical" else effective_magic_power(source)
	amount += _skill_power_bonus(source, skill_id)
	return amount


func _skill_power_bonus(unit: Dictionary, skill_id: String) -> int:
	var bonuses: Dictionary = unit.get("skill_power_bonuses", {})
	if bonuses.has(skill_id):
		return int(bonuses[skill_id])
	return int(unit.get("skill_power_bonus", 0)) if String(unit.get("skill_power_skill_id", "")) == skill_id else 0


func _has_guard_after_skill(unit: Dictionary, skill_id: String) -> bool:
	var guards: Array = unit.get("guard_after_skill_ids", [])
	return guards.has(skill_id) or String(unit.get("guard_after_skill_id", "")) == skill_id


func _skill_feedback_color(skill_id: String, effect_type: String) -> Color:
	var vfx := VfxCatalog.definition(SkillCatalog.vfx_id(skill_id))
	if vfx != null:
		return vfx.primary_color
	if effect_type == "heal" or effect_type == "guard":
		return MINT
	if skill_id == "flare" or skill_id == "mark":
		return SKY
	if skill_id in ["funk", "corrode", "mist"]:
		return VIOLET
	return CORAL


func _apply_skill_effect(source: Dictionary, target: Dictionary, anchor_cell: Vector2i, skill_id: String, effect: Resource) -> void:
	if target.is_empty():
		return
	var effect_type := String(effect.effect_type)
	if int(target.get("hp", 0)) <= 0 and not (effect_type == "revive" and _unit_is_downed(target)):
		return
	var amount := _skill_effect_amount(source, skill_id, effect)
	var feedback_color := _skill_feedback_color(skill_id, effect_type)
	match effect_type:
		"damage":
			var damage := status_adjusted_direct_damage(amount, target, source, String(effect.damage_type))
			var block: Dictionary = _apply_shield_block(target, damage)
			damage = int(block["damage"])
			if bool(block["blocked"]):
				spawn_floating_text(target["pos"], "BLOC -%d" % int(block["reduction"]), SKY)
			spawn_damage_feedback(source, target, damage, feedback_color, "", false)
			apply_damage(target, damage)
		"revive":
			var restored: int = _revive_unit(target, int(source.get("revive_hp_bonus", 0)) + maxi(0, amount))
			if restored > 0:
				spawn_floating_text(target["pos"], "RELEVÉ +%d" % restored, MINT)
				spawn_particles(target["pos"], MINT, 10)
				log_message("%s relève %s avec %d PV." % [source["name"], target["name"], restored])
		"heal":
			var healed: int = mini(maxi(0, amount), int(target["max_hp"]) - int(target["hp"]))
			target["hp"] = int(target["hp"]) + healed
			if healed > 0:
				spawn_floating_text(target["pos"], "+%d" % healed, MINT)
				spawn_particles(target["pos"], MINT, 7)
				play_feedback_tone("heal")
		"status":
			if not String(effect.status_id).is_empty():
				add_status(target, String(effect.status_id))
				spawn_particles(target["pos"], feedback_color, 6)
		"guard":
			add_status(target, "guarded")
			spawn_particles(target["pos"], MINT, 5)
		"reaction":
			target["reaction_used"] = false
		"focus":
			target["focus"] = clamp(int(target.get("focus", 0)) + amount, 0, int(target.get("max_focus", 0)))
			spawn_floating_text(target["pos"], "%s%d FOCUS" % ["+" if amount >= 0 else "", amount], SKY)
		"push":
			if int(target["hp"]) > 0 and amount > 0:
				var push_source: Vector2i = anchor_cell if SkillCatalog.target_mode(skill_id) == "ground" else Vector2i(source["pos"])
				push_away(push_source, target, amount, skill_name(skill_id))
		"pull":
			if int(target["hp"]) > 0 and amount > 0 and target["id"] != source["id"]:
				pull_toward(source["pos"], target, amount, skill_name(skill_id))


func best_special_target(source: Dictionary) -> Dictionary:
	var skill_id := str(source.get("special", ""))
	return _choose_skill_target(source, skill_id)


func _on_end_turn_pressed() -> void:
	if game_over or enemy_phase or _battle_sequences_pending():
		return
	if special_targeting:
		cancel_special_targeting()
	var unit := selected_unit()
	if unit.is_empty() or unit["id"] != active_unit_id:
		return
	log_message("%s valide son orientation finale vers %s." % [unit["name"], facing_label(unit)])
	finish_active_player_activation(unit)


func finish_active_player_activation(unit: Dictionary) -> void:
	resolve_end_of_activation(unit)
	if check_mission_end():
		return
	_finalize_activation_timing(unit)


func run_enemy_activation(enemy: Dictionary) -> void:
	if game_over or int(enemy["hp"]) <= 0:
		return
	log_message("%s entre dans la timeline. Personne n'avait demandé ça." % enemy["name"])
	apply_enemy_archetype_start(enemy)
	var destination := choose_enemy_destination(enemy)
	if destination != enemy["pos"]:
		var origin: Vector2i = enemy["pos"]
		var visual_path := movement_path_for(enemy, destination)
		enemy["facing"] = direction_from_to(origin, destination)
		enemy["pos"] = destination
		enemy["has_moved"] = true
		start_move_animation(str(enemy["id"]), visual_path)
		play_feedback_tone("move")
		resolve_reactions_on_move(enemy, origin, destination)
		if int(enemy["hp"]) <= 0:
			log_message("%s est stoppé net par une réaction de mêlée." % enemy["name"])
			check_mission_end()
			return
		_evaluate_battle_triggers("unit_moved", enemy)
		var position_note := ""
		if terrain_height(destination) > 0:
			position_note = " en hauteur"
		if cover_cells.has(destination):
			position_note += " sous couverture"
		if hazard_cells.has(destination):
			position_note += " dans des spores douteuses"
		log_message("%s se repositionne%s." % [enemy["name"], position_note])

	var used_enemy_skill := try_enemy_skill(enemy)
	var target := best_attackable_player(enemy)
	if not used_enemy_skill and not target.is_empty():
		var chance_profile := hit_profile(enemy, target)
		enemy["facing"] = direction_from_to(enemy["pos"], target["pos"])
		enemy["has_acted"] = true
		StatusCatalog.remove_on_attack(enemy)
		if not _roll_hit(int(chance_profile["chance"])):
			spawn_floating_text(target["pos"], "MISS", TEXT_SOFT)
			log_message("%s rate %s • %d%% HIT." % [enemy["name"], target["name"], int(chance_profile["chance"])])
		else:
			var recipient := target
			var interceptor := _find_interceptor(enemy, target)
			if not interceptor.is_empty():
				interceptor["reaction_used"] = true
				interceptor["facing"] = direction_from_to(interceptor["pos"], enemy["pos"])
				recipient = interceptor
				spawn_floating_text(interceptor["pos"], "INTERCEPTION", SKY)
			var profile := damage_profile(enemy, recipient)
			var damage := int(profile["damage"])
			if not interceptor.is_empty():
				damage = maxi(1, damage - 1)
			spawn_damage_feedback(enemy, recipient, damage)
			apply_damage(recipient, damage)
			apply_enemy_attack_trait(enemy, recipient)
			if int(profile["guard_penalty"]) > 0:
				remove_status(recipient, "guarded")
			log_message("%s attaque %s : -%d PV • HIT %d%%%s." % [enemy["name"], recipient["name"], damage, int(chance_profile["chance"]), profile["summary"]])
			if int(recipient["hp"]) <= 0:
				log_message("%s est K.O. et réclame une pause goûter." % recipient["name"])
			else:
				_try_counter_reaction(recipient, enemy)

	resolve_end_of_activation(enemy)
	check_mission_end()


func apply_enemy_archetype_start(enemy: Dictionary) -> void:
	match str(enemy.get("template_id", enemy["id"])):
		"grincheux":
			add_status(enemy, "guarded")
			log_message("ARCHÉTYPE GARDE : Grincheux commence son activation sous GARDE.")
		"choriste":
			var ally := most_injured_enemy()
			if not ally.is_empty() and manhattan(enemy["pos"], ally["pos"]) <= 3:
				var heal: int = mini(1, int(ally["max_hp"]) - int(ally["hp"]))
				if heal > 0:
					ally["hp"] = int(ally["hp"]) + heal
					spawn_floating_text(ally["pos"], "+1 CHŒUR", MINT)
					log_message("ARCHÉTYPE CHORISTE : %s rend 1 PV à %s." % [enemy["name"], ally["name"]])


func apply_enemy_attack_trait(enemy: Dictionary, target: Dictionary) -> void:
	if int(target["hp"]) <= 0:
		return
	match str(enemy.get("template_id", enemy["id"])):
		"baveux":
			add_status(target, "slowed")
			log_message("ARCHÉTYPE GLUANT : %s est RALENTI." % target["name"])
		"comptable":
			if int(target.get("focus", 0)) > 0:
				target["focus"] = int(target["focus"]) - 1
				log_message("ARCHÉTYPE FISCAL : 1 Focus est taxé à %s." % target["name"])


func enemy_skill_ready(enemy: Dictionary, skill_id: String, cost: int = 1) -> bool:
	var cooldowns: Dictionary = enemy.get("cooldowns", {})
	return int(enemy.get("focus", 0)) >= cost and int(cooldowns.get(skill_id, 0)) <= 0


func spend_enemy_skill(enemy: Dictionary, skill_id: String, cost: int = 1, cooldown: int = 2) -> void:
	enemy["focus"] = max(0, int(enemy.get("focus", 0)) - cost)
	var cooldowns: Dictionary = enemy.get("cooldowns", {})
	cooldowns[skill_id] = cooldown
	enemy["cooldowns"] = cooldowns
	enemy["has_acted"] = true


func try_enemy_skill(enemy: Dictionary) -> bool:
	if int(enemy["hp"]) <= 0:
		return false
	if str(enemy.get("template_id", enemy["id"])) == "dj_morille" and enemy_skill_ready(enemy, "bass_drop"):
		var target := closest_player_to(enemy["pos"], 2)
		if not target.is_empty():
			var bass_damage := status_adjusted_direct_damage(2, target, enemy)
			spawn_impact_feedback(target, bass_damage, CORAL, true)
			apply_damage(target, bass_damage)
			if int(target["hp"]) > 0:
				add_status(target, "slowed")
			spend_enemy_skill(enemy, "bass_drop")
			log_message("DJ MORILLE — BASS DROP : %s subit %d dégât(s) et RALENTI." % [target["name"], bass_damage])
			return true
	if str(enemy.get("template_id", enemy["id"])) == "archiviste" and int(enemy.get("boss_phase", 1)) >= 2 and enemy_skill_ready(enemy, "archive_pulse"):
		var victims: Array = []
		for player in units:
			if player["team"] == "player" and int(player["hp"]) > 0 and manhattan(enemy["pos"], player["pos"]) <= 2:
				victims.append(player)
		if not victims.is_empty():
			var pulse_damage := 3 if int(enemy.get("boss_phase", 1)) >= 3 else 2
			for victim in victims:
				var adjusted_pulse := status_adjusted_direct_damage(pulse_damage, victim, enemy)
				spawn_impact_feedback(victim, adjusted_pulse, VIOLET, true)
				apply_damage(victim, adjusted_pulse)
			spend_enemy_skill(enemy, "archive_pulse", 1, 2)
			log_message("L'ARCHIVISTE — ONDE D'INDEX : %d cible(s), %d dégâts." % [victims.size(), pulse_damage])
			return true

	# Studio: any enemy template can reference a composed player-style skill.
	var ai_profile := AiCatalog.definition(str(enemy.get("ai_profile", "default")))
	var composed_skill_id := str(enemy.get("special", ""))
	var skill_allowed := ai_profile == null or bool(ai_profile.prefer_skills)
	if skill_allowed and ai_profile != null and float(ai_profile.skill_bias) < 1.0 and not best_attackable_player(enemy).is_empty():
		skill_allowed = false
	if skill_allowed and not composed_skill_id.is_empty() and SkillCatalog.has_effects(composed_skill_id) and can_use_skill(enemy, composed_skill_id):
		if SkillCatalog.target_mode(composed_skill_id) == "ground":
			var ground_target := closest_player_to(enemy["pos"], SkillCatalog.skill_range(composed_skill_id))
			if not ground_target.is_empty():
				_commit_skill(enemy, composed_skill_id, {}, ground_target["pos"])
				return true
		else:
			var composed_target := _choose_skill_target(enemy, composed_skill_id)
			if not composed_target.is_empty():
				_commit_skill(enemy, composed_skill_id, composed_target, composed_target["pos"])
				return true
	return false


func closest_player_to(cell: Vector2i, max_range: int) -> Dictionary:
	var best: Dictionary = {}
	var best_distance := 999
	for player in units:
		if player["team"] != "player" or int(player["hp"]) <= 0:
			continue
		var distance := manhattan(cell, player["pos"])
		if distance <= max_range and distance < best_distance:
			best = player
			best_distance = distance
	return best


func most_injured_enemy() -> Dictionary:
	var best: Dictionary = {}
	var missing := 0
	for enemy in units:
		if enemy["team"] != "enemy" or int(enemy["hp"]) <= 0:
			continue
		var current_missing := int(enemy["max_hp"]) - int(enemy["hp"])
		if current_missing > missing:
			missing = current_missing
			best = enemy
	return best


func choose_enemy_destination(enemy: Dictionary) -> Vector2i:
	var navigation := movement_data(enemy)
	var candidates: Array = navigation["cells"].duplicate()
	candidates.append(enemy["pos"])
	var best_cell: Vector2i = enemy["pos"]
	var best_score := 999999.0
	var profile := AiCatalog.definition(str(enemy.get("ai_profile", "default")))
	var preferred_range := int(profile.preferred_range) if profile != null else 1
	var distance_weight := float(profile.distance_weight) if profile != null else 10.0
	var attack_bonus := float(profile.attack_position_bonus) if profile != null else 100.0
	var cover_weight := float(profile.cover_weight) if profile != null else 2.0
	var height_weight := float(profile.height_weight) if profile != null else 3.0
	var hazard_penalty := float(profile.hazard_penalty) if profile != null else 18.0
	var reaction_penalty := float(profile.reaction_penalty) if profile != null else 22.0
	var movement_weight := float(profile.movement_cost_weight) if profile != null else 0.15
	var crown_priority := float(profile.crown_carrier_priority) if profile != null else 100.0

	for candidate in candidates:
		var nearest_distance := 999
		var can_attack_target := false
		for player in units:
			if player["team"] != "player" or int(player["hp"]) <= 0:
				continue
			var distance := manhattan(candidate, player["pos"])
			nearest_distance = min(nearest_distance, distance)
			if can_attack_from(enemy, candidate, player):
				can_attack_target = true
		var score := float(abs(nearest_distance - preferred_range)) * distance_weight
		if can_attack_target:
			score -= attack_bonus
		score -= float(terrain_height(candidate)) * height_weight
		if cover_cells.has(candidate) and (profile == null or bool(profile.seek_cover)):
			score -= cover_weight
		if hazard_cells.has(candidate):
			score += hazard_penalty
		if profile == null or bool(profile.avoid_reactions):
			score += float(reaction_risk_for_move(enemy, enemy["pos"], candidate)) * reaction_penalty
		if not crown_carrier_id.is_empty():
			var carrier := unit_by_id(crown_carrier_id)
			if not carrier.is_empty() and int(carrier["hp"]) > 0:
				score += float(manhattan(candidate, carrier["pos"])) * min(4.0, crown_priority / 50.0)
				if can_attack_from(enemy, candidate, carrier):
					score -= crown_priority * 0.35
		score += float(navigation["costs"].get(candidate, 0)) * movement_weight
		if score < best_score:
			best_score = score
			best_cell = candidate
	return best_cell


func reaction_risk_for_move(mover: Dictionary, origin: Vector2i, destination: Vector2i) -> int:
	var risk := 0
	for reactor in units:
		if reactor["team"] == mover["team"] or int(reactor["hp"]) <= 0:
			continue
		if not _reaction_available(reactor, "opportunity"):
			continue
		var origin_distance: int = manhattan(reactor["pos"], origin)
		var destination_distance: int = manhattan(reactor["pos"], destination)
		if threatens_distance(reactor, origin_distance) and not threatens_distance(reactor, destination_distance):
			risk += 1
	return risk


func best_attackable_player(enemy: Dictionary) -> Dictionary:
	var best: Dictionary = {}
	var best_score := 999999.0
	var profile := AiCatalog.definition(str(enemy.get("ai_profile", "default")))
	var hp_weight := float(profile.target_hp_weight) if profile != null else 3.0
	var distance_weight := float(profile.target_distance_weight) if profile != null else 1.0
	var crown_priority := float(profile.crown_carrier_priority) if profile != null else 100.0
	var marked_priority := float(profile.marked_target_priority) if profile != null else 12.0
	for player in units:
		if player["team"] != "player" or int(player["hp"]) <= 0 or not can_attack(enemy, player):
			continue
		var score := float(int(player["hp"])) * hp_weight + float(manhattan(enemy["pos"], player["pos"])) * distance_weight
		if player["id"] == crown_carrier_id:
			score -= crown_priority
		if has_status(player, "marked"):
			score -= marked_priority
		if score < best_score:
			best_score = score
			best = player
	return best


func _unit_by_template_or_id(wanted_id: String) -> Dictionary:
	if wanted_id.is_empty():
		return {}
	for unit in units:
		if str(unit.get("id", "")) == wanted_id or str(unit.get("template_id", "")) == wanted_id:
			return unit
	return {}


func _mission_rule_matches(rule: Resource) -> bool:
	if rule == null:
		return false
	var result := false
	match String(rule.rule_type):
		"all_enemies_defeated":
			result = alive_count("enemy") == 0
		"all_players_defeated":
			result = alive_count("player") == 0
		"survive_rounds":
			result = rounds_completed >= max(1, int(rule.amount))
		"crown_extracted":
			if not crown_carrier_id.is_empty():
				var carrier := unit_by_id(crown_carrier_id)
				result = not carrier.is_empty() and int(carrier["hp"]) > 0 and extraction_cells.has(carrier["pos"])
		"round_at_least":
			result = current_turn >= max(1, int(rule.amount))
		"bonus_collected":
			result = bonus_collected >= max(0, int(rule.amount))
		"unit_defeated":
			var defeated := _unit_by_template_or_id(String(rule.unit_id))
			result = defeated.is_empty() or int(defeated.get("hp", 0)) <= 0
		"unit_alive":
			var alive_unit := _unit_by_template_or_id(String(rule.unit_id))
			result = not alive_unit.is_empty() and int(alive_unit.get("hp", 0)) > 0
		"unit_on_extraction":
			var zone_unit := _unit_by_template_or_id(String(rule.unit_id))
			result = not zone_unit.is_empty() and int(zone_unit.get("hp", 0)) > 0 and extraction_cells.has(zone_unit["pos"])
	if bool(rule.invert):
		return not result
	return result


func _mission_rules_satisfied(rules: Array, mode: String) -> bool:
	if rules.is_empty():
		return false
	if mode == "all":
		for rule in rules:
			if not _mission_rule_matches(rule):
				return false
		return true
	for rule in rules:
		if _mission_rule_matches(rule):
			return true
	return false


func _setup_runtime_mission_logic() -> void:
	if active_mission_definition == null:
		return
	runtime_victory_rules = active_mission_definition.victory_rules.duplicate(true)
	runtime_defeat_rules = active_mission_definition.defeat_rules.duplicate(true)
	runtime_victory_rule_mode = String(active_mission_definition.victory_rule_mode)
	runtime_defeat_rule_mode = String(active_mission_definition.defeat_rule_mode)


func _has_data_driven_mission_logic() -> bool:
	return not runtime_victory_rules.is_empty() or not runtime_defeat_rules.is_empty()


func _data_driven_result_message(victory: bool) -> String:
	if victory:
		return "VICTOIRE ! Les conditions configurées dans Sporebound Studio sont remplies."
	return "DÉFAITE ! Une condition d'échec configurée dans Sporebound Studio est remplie."


func _trigger_condition_matches(trigger: Resource, event_name: String, event_unit: Dictionary) -> bool:
	match String(trigger.condition_type):
		"round_start":
			return event_name == "round_start" and current_turn == max(1, int(trigger.condition_value))
		"round_end":
			return event_name == "round_end" and rounds_completed == max(1, int(trigger.condition_value))
		"enemy_count_at_most":
			return alive_count("enemy") <= max(0, int(trigger.condition_value))
		"player_count_at_most":
			return alive_count("player") <= max(0, int(trigger.condition_value))
		"unit_hp_at_most":
			var target := _unit_by_template_or_id(String(trigger.condition_unit_id))
			return not target.is_empty() and int(target.get("hp", 0)) > 0 and int(target.get("hp", 0)) <= int(trigger.condition_value)
		"unit_defeated":
			var defeated := _unit_by_template_or_id(String(trigger.condition_unit_id))
			return defeated.is_empty() or int(defeated.get("hp", 0)) <= 0
		"player_enters_cell":
			return event_name == "unit_moved" and not event_unit.is_empty() and event_unit.get("team", "") == "player" and event_unit.get("pos", Vector2i(-9, -9)) == trigger.condition_cell
		"enemy_enters_cell":
			return event_name == "unit_moved" and not event_unit.is_empty() and event_unit.get("team", "") == "enemy" and event_unit.get("pos", Vector2i(-9, -9)) == trigger.condition_cell
		"player_enters_zone":
			return event_name == "unit_moved" and not event_unit.is_empty() and String(event_unit.get("team", "")) == "player" and _unit_is_in_zone(event_unit, String(trigger.condition_zone_id))
		"enemy_enters_zone":
			return event_name == "unit_moved" and not event_unit.is_empty() and String(event_unit.get("team", "")) == "enemy" and _unit_is_in_zone(event_unit, String(trigger.condition_zone_id))
	return false


func _unit_is_in_zone(unit: Dictionary, zone_id: String) -> bool:
	if zone_id.is_empty():
		return false
	var position_value: Variant = unit.get("pos", Vector2i(-999, -999))
	if not (position_value is Vector2i):
		return false
	var cell: Vector2i = position_value
	var unit_team: String = String(unit.get("team", ""))
	for zone: Dictionary in mission_zones:
		if String(zone.get("id", "")) != zone_id or not bool(zone.get("enabled", true)):
			continue
		var zone_team: String = String(zone.get("team", "any"))
		if zone_team != "any" and zone_team != unit_team:
			return false
		var raw_cells: Variant = zone.get("cells", [])
		if raw_cells is Array and (raw_cells as Array).has(cell):
			return true
	return false


func _unique_runtime_unit_id(base_id: String) -> String:
	if unit_by_id(base_id).is_empty():
		return base_id
	var suffix := 2
	while not unit_by_id("%s_%d" % [base_id, suffix]).is_empty():
		suffix += 1
	return "%s_%d" % [base_id, suffix]


func _legacy_trigger_action(trigger: Resource) -> Dictionary:
	return {
		"action_type": String(trigger.action_type),
		"message": String(trigger.message),
		"unit_id": String(trigger.action_unit_id),
		"status_id": String(trigger.action_status_id),
		"object_id": "",
		"cell": trigger.action_cell,
		"value": int(trigger.action_value),
		"delay_seconds": 0.0,
		"team": String(trigger.action_team),
		"rule_type": "all_enemies_defeated",
		"rule_amount": 1,
		"rule_unit_id": "",
		"rule_invert": false,
		"rule_mode": "any",
	}


func _action_data(action) -> Dictionary:
	if typeof(action) == TYPE_DICTIONARY:
		return action
	return {
		"action_type": String(action.action_type),
		"message": String(action.message),
		"unit_id": String(action.unit_id),
		"status_id": String(action.status_id),
		"object_id": String(action.object_id),
		"cell": action.cell,
		"value": int(action.value),
		"delay_seconds": float(action.delay_seconds),
		"team": String(action.team),
		"rule_type": String(action.rule_type),
		"rule_amount": int(action.rule_amount),
		"rule_unit_id": String(action.rule_unit_id),
		"rule_invert": bool(action.rule_invert),
		"rule_mode": String(action.rule_mode),
		"cinematic_id": String(action.cinematic_id),
		"speaker": String(action.speaker),
		"portrait_path": String(action.portrait_path),
		"portrait_side": String(action.portrait_side),
		"wait_for_input": bool(action.wait_for_input),
		"auto_advance_seconds": float(action.auto_advance_seconds),
		"camera_zoom": float(action.camera_zoom),
		"camera_duration": float(action.camera_duration),
		"audio_path": String(action.audio_path),
		"volume_db": float(action.volume_db),
	}


func _trigger_action_list(trigger: Resource) -> Array:
	var result: Array = []
	if not trigger.actions.is_empty():
		for action in trigger.actions:
			if action != null:
				result.append(_action_data(action))
	else:
		result.append(_legacy_trigger_action(trigger))
	return result


func _queue_battle_sequence(trigger: Resource) -> void:
	pending_trigger_sequences.append({
		"id": String(trigger.id),
		"actions": _trigger_action_list(trigger),
		"serial": battle_sequence_serial,
	})
	if not event_sequence_running:
		call_deferred("_pump_battle_sequences")


func _pump_battle_sequences() -> void:
	if event_sequence_running:
		return
	event_sequence_running = true
	while not pending_trigger_sequences.is_empty():
		var sequence: Dictionary = pending_trigger_sequences.pop_front()
		if int(sequence.get("serial", -1)) != battle_sequence_serial or game_over:
			continue
		await _run_action_sequence(sequence.get("actions", []), int(sequence.get("serial", -1)), false, 0)
	event_sequence_running = false
	check_mission_end()


func _cinematic_actions(cinematic_id: String) -> Array:
	var definition := CinematicCatalog.definition(cinematic_id)
	var result: Array = []
	if definition == null:
		return result
	for action in definition.actions:
		if action != null:
			result.append(_action_data(action))
	return result


func _run_action_sequence(actions: Array, serial: int, allow_game_over: bool = false, depth: int = 0) -> void:
	if depth > 6:
		log_message("CINÉMATIQUE : profondeur maximale atteinte (boucle probable).")
		return
	for raw_action in actions:
		if serial != battle_sequence_serial or (game_over and not allow_game_over):
			return
		var action: Dictionary = raw_action if typeof(raw_action) == TYPE_DICTIONARY else _action_data(raw_action)
		var pause := float(action.get("delay_seconds", 0.0))
		if String(action.get("action_type", "")) == "wait":
			pause = max(pause, 0.1)
		if pause > 0.0:
			await get_tree().create_timer(pause).timeout
			if serial != battle_sequence_serial:
				return
		var action_type := String(action.get("action_type", "message"))
		match action_type:
			"wait":
				pass
			"play_cinematic":
				var nested_id := String(action.get("cinematic_id", ""))
				if not nested_id.is_empty():
					await _run_action_sequence(_cinematic_actions(nested_id), serial, allow_game_over, depth + 1)
			"dialogue":
				await _play_dialogue_action(action, serial)
			"camera_focus_cell", "camera_focus_unit", "camera_zoom", "camera_reset":
				await _play_camera_action(action)
			"camera_shake":
				shake_strength = max(shake_strength, float(max(1, int(action.get("value", 5)))))
			"fade_out":
				await _tween_fade(1.0, float(action.get("camera_duration", 0.35)))
			"fade_in":
				await _tween_fade(0.0, float(action.get("camera_duration", 0.35)))
			"play_music":
				_play_cinematic_audio(action, true)
			"stop_music":
				if cinematic_music_player != null:
					cinematic_music_player.stop()
			"play_sfx":
				_play_cinematic_audio(action, false)
			_:
				_execute_battle_action(action)
		refresh_all()


func _portrait_path_for_dialogue(action: Dictionary, speaker: String) -> String:
	var unit_id := String(action.get("unit_id", ""))
	if not unit_id.is_empty():
		var unit_def := UnitCatalog.definition(unit_id)
		var visual_id := unit_id
		if unit_def != null and not String(unit_def.visual_id).is_empty():
			visual_id = String(unit_def.visual_id)
		var visual := VisualCatalog.definition(visual_id)
		if visual != null:
			return String(visual.portrait_path)
	for candidate_id in UnitCatalog.all_unit_ids():
		var candidate := UnitCatalog.definition(String(candidate_id))
		if candidate == null or String(candidate.display_name).to_lower() != speaker.to_lower():
			continue
		var candidate_visual_id := String(candidate.visual_id) if not String(candidate.visual_id).is_empty() else String(candidate.id)
		var candidate_visual := VisualCatalog.definition(candidate_visual_id)
		if candidate_visual != null:
			return String(candidate_visual.portrait_path)
	return ""


func _play_dialogue_action(action: Dictionary, serial: int) -> void:
	if cinematic_dialogue_panel == null:
		return
	var speaker := String(action.get("speaker", ""))
	if speaker.is_empty() and not String(action.get("unit_id", "")).is_empty():
		var speaker_unit := _unit_by_template_or_id(String(action.get("unit_id", "")))
		if not speaker_unit.is_empty():
			speaker = String(speaker_unit.get("name", ""))
	if speaker.is_empty():
		speaker = "Narrateur"
	cinematic_speaker_label.text = speaker
	cinematic_message_label.text = String(action.get("message", ""))
	var portrait_path := String(action.get("portrait_path", ""))
	if portrait_path.is_empty():
		portrait_path = _portrait_path_for_dialogue(action, speaker)
	cinematic_portrait.texture = null
	cinematic_portrait.visible = false
	if not portrait_path.is_empty() and ResourceLoader.exists(portrait_path):
		var portrait_resource := load(portrait_path)
		if portrait_resource is Texture2D:
			cinematic_portrait.texture = portrait_resource
			cinematic_portrait.visible = true
	var portrait_right := String(action.get("portrait_side", "left")) == "right"
	cinematic_portrait.position = Vector2(936.0, 16.0) if portrait_right else Vector2(18.0, 16.0)
	var text_x := 28.0 if portrait_right else 164.0
	cinematic_speaker_label.position.x = text_x
	cinematic_message_label.position.x = text_x
	cinematic_message_label.size.x = 875.0 if not portrait_right else 880.0
	cinematic_continue_button.position.x = 40.0 if portrait_right else 860.0
	cinematic_letterbox_top.visible = true
	cinematic_letterbox_bottom.visible = true
	cinematic_dialogue_panel.visible = true
	cinematic_dialogue_waiting = true
	var wait_for_input := bool(action.get("wait_for_input", true))
	var auto_seconds := float(action.get("auto_advance_seconds", 0.0))
	if wait_for_input or auto_seconds <= 0.0:
		await cinematic_advance_requested
	else:
		await get_tree().create_timer(max(0.1, auto_seconds)).timeout
	if serial != battle_sequence_serial:
		return
	_hide_cinematic_dialogue()


func _play_camera_action(action: Dictionary) -> void:
	var action_type := String(action.get("action_type", "camera_reset"))
	var target_zoom: float = maxf(0.25, float(action.get("camera_zoom", cinematic_camera_zoom)))
	var target_offset := cinematic_camera_offset
	var board_size := Vector2(float(grid_width) * cell_size, float(grid_height) * cell_size)
	var board_center := BOARD_ORIGIN + board_size * 0.5
	match action_type:
		"camera_reset":
			target_zoom = 1.0
			target_offset = Vector2.ZERO
		"camera_zoom":
			target_offset = board_center - board_center * target_zoom
		"camera_focus_cell":
			var cell: Vector2i = action.get("cell", Vector2i(-1, -1))
			if is_inside(cell):
				var focus_world := cell_to_world(cell) + Vector2(cell_size, cell_size) * 0.5
				target_offset = board_center - focus_world * target_zoom
		"camera_focus_unit":
			var unit := _unit_by_template_or_id(String(action.get("unit_id", "")))
			if not unit.is_empty():
				var focus_world := cell_to_world(unit["pos"]) + Vector2(cell_size, cell_size) * 0.5
				target_offset = board_center - focus_world * target_zoom
			else:
				target_zoom = cinematic_camera_zoom
	var duration: float = maxf(0.0, float(action.get("camera_duration", 0.35)))
	if duration <= 0.0:
		cinematic_camera_offset = target_offset
		cinematic_camera_zoom = target_zoom
		queue_redraw()
		return
	var tween := create_tween().set_parallel(true)
	tween.tween_property(self, "cinematic_camera_offset", target_offset, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tween.tween_property(self, "cinematic_camera_zoom", target_zoom, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tween.finished


func _set_cinematic_fade_alpha(alpha: float) -> void:
	if cinematic_fade_rect == null:
		return
	var color := cinematic_fade_rect.color
	color.a = clampf(alpha, 0.0, 1.0)
	cinematic_fade_rect.color = color


func _tween_fade(target_alpha: float, duration: float) -> void:
	if cinematic_fade_rect == null:
		return
	var start_alpha := cinematic_fade_rect.color.a
	if duration <= 0.0:
		_set_cinematic_fade_alpha(target_alpha)
		return
	var tween := create_tween()
	tween.tween_method(Callable(self, "_set_cinematic_fade_alpha"), start_alpha, target_alpha, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tween.finished


func _play_cinematic_audio(action: Dictionary, music: bool) -> void:
	var player := cinematic_music_player if music else cinematic_sfx_player
	if player == null:
		return
	var audio_path := String(action.get("audio_path", ""))
	if audio_path.is_empty() or not ResourceLoader.exists(audio_path):
		if not music:
			play_feedback_tone("heavy")
		return
	var stream_resource := load(audio_path)
	if stream_resource is AudioStream:
		player.stream = stream_resource
		player.volume_db = float(action.get("volume_db", -6.0))
		player.play()


func _execute_battle_action(action: Dictionary) -> void:
	var action_type := String(action.get("action_type", "message"))
	var action_cell: Vector2i = action.get("cell", Vector2i(-1, -1))
	var action_value := int(action.get("value", 1))
	var action_team := String(action.get("team", "enemy"))
	match action_type:
		"wait":
			pass
		"message":
			if not String(action.get("message", "")).is_empty():
				log_message("ÉVÉNEMENT : %s" % String(action.get("message", "")))
		"spawn_enemy":
			var unit_def := UnitCatalog.definition(String(action.get("unit_id", "")))
			if unit_def != null and is_inside(action_cell) and is_walkable(action_cell, ""):
				var spawned: Dictionary = unit_def.to_runtime_dict(action_cell, "enemy")
				spawned["id"] = _unique_runtime_unit_id(String(unit_def.id))
				spawned["template_id"] = String(unit_def.id)
				apply_difficulty_to_enemy(spawned)
				units.append(spawned)
				enemies_total_initial += 1
				spawn_particles(action_cell, CORAL, 12)
				log_message("RENFORT : %s rejoint le combat en (%d,%d)." % [spawned["name"], action_cell.x + 1, action_cell.y + 1])
		"apply_status_to_unit":
			var status_target := _unit_by_template_or_id(String(action.get("unit_id", "")))
			var status_id := String(action.get("status_id", ""))
			if not status_target.is_empty() and not status_id.is_empty():
				add_status(status_target, status_id)
				var status_def := StatusCatalog.definition(status_id)
				var status_name := String(status_def.display_name) if status_def != null else status_id
				log_message("ÉVÉNEMENT : %s reçoit %s." % [status_target["name"], status_name])
		"add_hazard":
			if is_inside(action_cell) and not hazard_cells.has(action_cell):
				hazard_cells.append(action_cell)
				spawn_particles(action_cell, VIOLET, 8)
		"remove_hazard":
			hazard_cells.erase(action_cell)
		"heal_team":
			for unit in units:
				if unit["team"] == action_team and int(unit["hp"]) > 0:
					var heal: int = mini(maxi(0, action_value), int(unit["max_hp"]) - int(unit["hp"]))
					unit["hp"] = int(unit["hp"]) + heal
					if heal > 0:
						spawn_floating_text(unit["pos"], "+%d" % heal, MINT)
		"damage_team":
			for unit in units:
				if unit["team"] == action_team and int(unit["hp"]) > 0:
					var damage: int = maxi(0, action_value)
					spawn_impact_feedback(unit, damage, CORAL, false)
					apply_damage(unit, damage)
		"grant_focus_team":
			for unit in units:
				if unit["team"] == action_team and int(unit["hp"]) > 0:
					unit["focus"] = clamp(int(unit.get("focus", 0)) + action_value, 0, int(unit.get("max_focus", 0)))
		"set_objective_text":
			runtime_objective_text = String(action.get("message", ""))
			if not runtime_objective_text.is_empty():
				log_message("NOUVEL OBJECTIF : %s" % runtime_objective_text)
		"set_victory_rule":
			_set_runtime_rule(action, true)
		"set_defeat_rule":
			_set_runtime_rule(action, false)
		"open_door":
			_set_interactable_active(String(action.get("object_id", "")), true)
		"close_door":
			_set_interactable_active(String(action.get("object_id", "")), false)
		"toggle_switch":
			_toggle_switch(String(action.get("object_id", "")))
		"open_chest":
			_open_chest(String(action.get("object_id", "")))
		"set_phase":
			runtime_phase = String(action.get("message", ""))
			if runtime_phase.is_empty():
				runtime_phase = str(action_value)
			log_message("PHASE : %s" % runtime_phase)


func _set_runtime_rule(action: Dictionary, victory: bool) -> void:
	var rule: Resource = MissionRule.new()
	rule.rule_type = String(action.get("rule_type", "all_enemies_defeated"))
	rule.amount = int(action.get("rule_amount", 1))
	rule.unit_id = String(action.get("rule_unit_id", ""))
	rule.invert = bool(action.get("rule_invert", false))
	rule.description = String(action.get("message", ""))
	if victory:
		runtime_victory_rules = [rule]
		runtime_victory_rule_mode = String(action.get("rule_mode", "any"))
		log_message("OBJECTIF DE VICTOIRE MODIFIÉ : %s" % rule.summary())
	else:
		runtime_defeat_rules = [rule]
		runtime_defeat_rule_mode = String(action.get("rule_mode", "any"))
		log_message("CONDITION D'ÉCHEC MODIFIÉE : %s" % rule.summary())


func _setup_interactables() -> void:
	interactable_states.clear()
	if active_mission_definition == null:
		return
	for object_def in active_mission_definition.interactables:
		if object_def == null:
			continue
		interactable_states[String(object_def.id)] = {
			"definition": object_def,
			"active": bool(object_def.starts_active),
			"used": false,
		}


func _interactable_state(object_id: String) -> Dictionary:
	return interactable_states.get(object_id, {})


func _closed_door_at(cell: Vector2i) -> bool:
	for state in interactable_states.values():
		var definition = state.get("definition", null)
		if definition != null and String(definition.object_type) == "door" and definition.cell == cell:
			return not bool(state.get("active", false))
	return false


func _set_interactable_active(object_id: String, active: bool) -> void:
	var state := _interactable_state(object_id)
	if state.is_empty():
		return
	state["active"] = active
	var definition = state.get("definition", null)
	if definition != null:
		var verb := "OUVERT" if active else "FERMÉ"
		log_message("%s : %s." % [String(definition.display_name).to_upper(), verb])


func _toggle_switch(object_id: String) -> void:
	var state := _interactable_state(object_id)
	if state.is_empty():
		return
	var definition = state.get("definition", null)
	if definition == null or String(definition.object_type) != "switch":
		return
	state["active"] = not bool(state.get("active", false))
	log_message("INTERRUPTEUR : %s." % ("ACTIVÉ" if bool(state["active"]) else "DÉSACTIVÉ"))
	var linked_id := String(definition.linked_object_id)
	if not linked_id.is_empty():
		_set_interactable_active(linked_id, bool(state["active"]))


func _open_chest(object_id: String) -> void:
	var state := _interactable_state(object_id)
	if state.is_empty() or bool(state.get("used", false)):
		return
	var definition = state.get("definition", null)
	if definition == null or String(definition.object_type) != "chest":
		return
	state["used"] = true
	state["active"] = true
	var reward_type := String(definition.reward_type)
	var reward_value := int(definition.reward_value)
	var reward_team := String(definition.reward_team)
	if reward_type == "heal_team":
		_execute_battle_action({"action_type": "heal_team", "team": reward_team, "value": reward_value, "cell": Vector2i(-1, -1)})
	elif reward_type == "focus_team":
		_execute_battle_action({"action_type": "grant_focus_team", "team": reward_team, "value": reward_value, "cell": Vector2i(-1, -1)})
	log_message("COFFRE : %s ouvert." % String(definition.display_name))


func _handle_interactable_entry(unit: Dictionary) -> void:
	if unit.is_empty() or unit.get("team", "") != "player":
		return
	for object_id in interactable_states.keys():
		var state: Dictionary = interactable_states[object_id]
		var definition = state.get("definition", null)
		if definition == null or definition.cell != unit.get("pos", Vector2i(-9, -9)):
			continue
		if String(definition.object_type) == "switch":
			if not bool(definition.one_shot) or not bool(state.get("used", false)):
				state["used"] = true
				_toggle_switch(String(object_id))
		elif String(definition.object_type) == "chest":
			_open_chest(String(object_id))


func _draw_interactables() -> void:
	for state in interactable_states.values():
		var definition = state.get("definition", null)
		if definition == null or not is_inside(definition.cell):
			continue
		var rect := Rect2(cell_to_world(definition.cell), Vector2(cell_size - 1.0, cell_size - 1.0))
		var center := rect.position + rect.size * 0.5
		match String(definition.object_type):
			"door":
				var open := bool(state.get("active", false))
				var door_color := MINT if open else GOLD
				draw_rect(rect.grow(-11.0), Color(door_color.r, door_color.g, door_color.b, 0.18), true)
				draw_rect(rect.grow(-13.0), door_color, false, 4.0)
				draw_string(ThemeDB.fallback_font, rect.position + Vector2(12.0, 20.0), "PORTE", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 10, door_color)
			"switch":
				var switch_color := MINT if bool(state.get("active", false)) else SKY
				draw_circle(center, max(8.0, cell_size * 0.16), switch_color)
				draw_circle(center, max(4.0, cell_size * 0.08), BG)
			"chest":
				var opened := bool(state.get("used", false))
				var chest_color := TEXT_SOFT if opened else GOLD
				draw_rect(Rect2(center - Vector2(14.0, 9.0), Vector2(28.0, 18.0)), chest_color, false, 3.0)
				draw_string(ThemeDB.fallback_font, center + Vector2(-5.0, 5.0), "◆", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 12, chest_color)


func _evaluate_battle_triggers(event_name: String, event_unit: Dictionary = {}) -> void:
	if evaluating_triggers or active_mission_definition == null or active_mission_definition.battle_triggers.is_empty():
		return
	evaluating_triggers = true
	for trigger in active_mission_definition.battle_triggers:
		if trigger == null or not bool(trigger.enabled):
			continue
		var trigger_id := String(trigger.id)
		if bool(trigger.once) and bool(fired_trigger_ids.get(trigger_id, false)):
			continue
		if not _trigger_condition_matches(trigger, event_name, event_unit):
			continue
		if bool(trigger.once):
			fired_trigger_ids[trigger_id] = true
		_queue_battle_sequence(trigger)
	evaluating_triggers = false
	refresh_all()


func check_mission_end() -> bool:
	if game_over:
		return true
	_evaluate_battle_triggers("state")
	if _has_data_driven_mission_logic():
		if _mission_rules_satisfied(runtime_defeat_rules, runtime_defeat_rule_mode):
			finish_mission_result(false, _data_driven_result_message(false))
			return true
		if _mission_rules_satisfied(runtime_victory_rules, runtime_victory_rule_mode):
			finish_mission_result(true, _data_driven_result_message(true))
			return true
		return false

	# Legacy fallback for V1.2/custom resources without Mission Logic rules.
	var living_players := alive_count("player")
	var living_enemies := alive_count("enemy")
	if living_players == 0:
		finish_mission_result(false, "DÉFAITE ! L'escouade est K.O. avant d'avoir fini le morceau.")
		return true
	if mission_objective == "crown":
		if not crown_carrier_id.is_empty():
			var carrier := unit_by_id(crown_carrier_id)
			if not carrier.is_empty() and int(carrier["hp"]) > 0 and extraction_cells.has(carrier["pos"]):
				finish_mission_result(true, "VICTOIRE ! La Couronne Beatbox est extraite. Bonus : %d/%d." % [bonus_collected, bonus_target_total])
				return true
		if living_enemies == 0 and not enemies_cleared_logged:
			enemies_cleared_logged = true
			log_message("Tous les ennemis sont K.O. Il faut quand même ramener la couronne !")
	elif mission_objective == "survive":
		if living_enemies == 0:
			finish_mission_result(true, "VICTOIRE ! La scène est sécurisée avant même la fin de la troisième manche.")
			return true
	elif mission_objective == "eliminate" and living_enemies == 0:
		finish_mission_result(true, "VICTOIRE ! La troupe d'élite est K.O. Dernier rappel réussi.")
		return true
	return false


func finish_mission_result(victory: bool, message: String) -> void:
	if game_over:
		return
	game_over = true
	enemy_phase = false
	mission_victory = victory
	selected_id = ""
	active_unit_id = ""
	event_sequence_running = true
	log_message(message)
	refresh_all()
	call_deferred("_finish_mission_with_cinematic", victory, battle_serial, battle_sequence_serial)


func _finish_mission_with_cinematic(victory: bool, serial: int, sequence_serial: int) -> void:
	var cinematic_id := ""
	if active_mission_definition != null:
		cinematic_id = String(active_mission_definition.victory_cinematic_id if victory else active_mission_definition.defeat_cinematic_id)
	if not cinematic_id.is_empty() and CinematicCatalog.definition(cinematic_id) != null:
		await _run_action_sequence(_cinematic_actions(cinematic_id), sequence_serial, true, 0)
	event_sequence_running = false
	if serial != battle_serial or sequence_serial != battle_sequence_serial or campaign.mode != "battle" or not game_over:
		return
	await get_tree().create_timer(0.45).timeout
	if serial == battle_serial and campaign.mode == "battle" and game_over:
		show_debrief_screen()


func _open_debrief_if_current(serial: int) -> void:
	# Kept for backwards compatibility with older deferred calls.
	if serial != battle_serial or campaign.mode != "battle" or not game_over:
		return
	show_debrief_screen()


func refresh_all() -> void:
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func check_crown_pickup(unit: Dictionary) -> void:
	if mission_objective != "crown":
		return
	if unit["team"] != "player" or not crown_carrier_id.is_empty() or unit["pos"] != crown_cell:
		return
	crown_carrier_id = unit["id"]
	spawn_particles(unit["pos"], GOLD, 12)
	spawn_floating_text(unit["pos"], "COURONNE !", GOLD)
	play_feedback_tone("heal")
	log_message("%s récupère la COURONNE BEATBOX. Retourne dans la zone verte !" % unit["name"] )


func check_bonus_pickup(unit: Dictionary) -> void:
	if unit["team"] != "player" or not bonus_cells.has(unit["pos"]):
		return
	bonus_cells.erase(unit["pos"])
	bonus_collected += 1
	unit["hp"] = min(int(unit["max_hp"]), int(unit["hp"]) + 1)
	spawn_particles(unit["pos"], VIOLET, 10)
	spawn_floating_text(unit["pos"], "+1 VINYLE", GOLD)
	play_feedback_tone("heal")
	log_message("%s récupère un VINYLE VOLÉ (%d/2) et regagne 1 PV." % [unit["name"], bonus_collected])


func special_targetable_cells(unit: Dictionary, max_range: int, skill_id: String = "") -> Array:
	var result: Array = []
	var line_shape: bool = false
	if not skill_id.is_empty():
		for effect: Resource in SkillCatalog.effects(skill_id):
			if effect != null and String(effect.area_shape) == "line":
				line_shape = true
				break
	var origin_value: Variant = unit.get("pos", Vector2i.ZERO)
	var origin: Vector2i = Vector2i.ZERO
	if origin_value is Vector2i:
		origin = origin_value
	for y in range(grid_height):
		for x in range(grid_width):
			var cell := Vector2i(x, y)
			if line_shape and cell.x != origin.x and cell.y != origin.y:
				continue
			if manhattan(origin, cell) <= max_range and has_line_of_sight(origin, cell, String(unit.get("id", "")), ""):
				result.append(cell)
	return result


func push_away(source_cell: Vector2i, target: Dictionary, distance: int, reason: String) -> void:
	var direction := direction_from_to(source_cell, target["pos"])
	if target["pos"] == source_cell:
		return
	force_move(target, direction, distance, reason)


func pull_toward(source_cell: Vector2i, target: Dictionary, distance: int, reason: String) -> void:
	var direction := direction_from_to(target["pos"], source_cell)
	force_move(target, direction, distance, reason)


func force_move(target: Dictionary, direction: Vector2i, distance: int, reason: String) -> void:
	for _step in range(distance):
		var origin: Vector2i = target["pos"]
		var next_cell: Vector2i = origin + direction
		if not is_walkable(next_cell, target["id"]):
			var impact_damage := status_adjusted_direct_damage(1, target)
			spawn_impact_feedback(target, impact_damage, CORAL, true)
			apply_damage(target, impact_damage)
			log_message("%s percute un obstacle pendant %s : %d dégât(s) d'impact." % [target["name"], reason, impact_damage])
			return
		target["pos"] = next_cell
		start_move_animation(str(target["id"]), [origin, next_cell], 0.09)
		spawn_particles(next_cell, VIOLET, 4)
		if target["team"] == "player":
			check_crown_pickup(target)
			check_bonus_pickup(target)
		_evaluate_battle_triggers("unit_moved", target)
	log_message("%s est déplacé de force par %s." % [target["name"], reason])


func resolve_reactions_on_move(mover: Dictionary, origin: Vector2i, destination: Vector2i) -> void:
	if bool(mover.get("ignore_opportunity", false)):
		return
	for reactor in units:
		if int(mover["hp"]) <= 0:
			return
		if reactor["team"] == mover["team"] or int(reactor["hp"]) <= 0:
			continue
		if not _reaction_available(reactor, "opportunity"):
			continue
		var origin_distance: int = manhattan(reactor["pos"], origin)
		var destination_distance: int = manhattan(reactor["pos"], destination)
		if not threatens_distance(reactor, origin_distance) or threatens_distance(reactor, destination_distance):
			continue
		reactor["reaction_used"] = true
		reactor["facing"] = direction_from_to(reactor["pos"], destination)
		var reaction_hit := hit_profile(reactor, mover, 80)
		StatusCatalog.remove_on_attack(reactor)
		if not _roll_hit(int(reaction_hit["chance"])):
			spawn_floating_text(mover["pos"], "RÉACTION MISS", TEXT_SOFT)
			log_message("RÉACTION : %s rate %s en désengagement (%d%%)." % [reactor["name"], mover["name"], int(reaction_hit["chance"])])
			continue
		var reaction_damage: int = maxi(1, status_adjusted_direct_damage(effective_basic_attack_power(reactor) - 1, mover, reactor, String(reactor.get("basic_attack_damage_type", "physical"))))
		var reaction_block: Dictionary = _apply_shield_block(mover, reaction_damage)
		reaction_damage = int(reaction_block["damage"])
		spawn_damage_feedback(reactor, mover, reaction_damage, GOLD)
		apply_damage(mover, reaction_damage)
		log_message("RÉACTION : %s frappe %s en désengagement pour %d dégât(s) • HIT %d%%." % [reactor["name"], mover["name"], reaction_damage, int(reaction_hit["chance"])])


func _process_status_phase(unit: Dictionary, phase: String) -> void:
	if int(unit.get("hp", 0)) <= 0:
		return
	for event in StatusCatalog.phase_events(unit, phase):
		var status_id := String(event.get("status_id", "status"))
		var status_def := StatusCatalog.definition(status_id)
		var label := String(status_def.display_name) if status_def != null else status_id
		var amount := int(event.get("amount", 0))
		var color: Color = event.get("color", VIOLET)
		if String(event.get("type", "")) == "damage" and amount > 0:
			var tick_damage := status_adjusted_direct_damage(amount, unit, {}, String(event.get("damage_type", "physical")))
			spawn_impact_feedback(unit, tick_damage, color, false)
			apply_damage(unit, tick_damage)
			log_message("%s — %s : -%d PV." % [unit["name"], label, tick_damage])
		elif String(event.get("type", "")) == "heal" and amount > 0:
			var healed: int = mini(amount, int(unit["max_hp"]) - int(unit["hp"]))
			unit["hp"] = int(unit["hp"]) + healed
			if healed > 0:
				spawn_floating_text(unit["pos"], "+%d %s" % [healed, label], color)
		if int(unit["hp"]) <= 0:
			break


func resolve_end_of_activation(unit: Dictionary) -> void:
	if int(unit["hp"]) <= 0:
		return
	if hazard_cells.has(unit["pos"]):
		var hazard_damage := status_adjusted_direct_damage(1, unit, {}, "spore")
		spawn_impact_feedback(unit, hazard_damage, VIOLET, false)
		apply_damage(unit, hazard_damage)
		log_message("%s subit %d dégât(s) de spores en fin d'activation." % [unit["name"], hazard_damage])
		if int(unit["hp"]) <= 0:
			log_message("%s est K.O. par une flaque. Le rapport sera humiliant." % unit["name"] )
			return
	_process_status_phase(unit, "activation_end")
	if int(unit["hp"]) <= 0:
		log_message("%s est K.O. par un effet de statut." % unit["name"] )
		return
	var expired := StatusCatalog.finish_activation(unit)
	for status_id in expired:
		var data := StatusCatalog.definition(status_id)
		var label := String(data.display_name) if data != null else String(status_id)
		log_message("%s : %s se dissipe." % [unit["name"], label])


func _battle_sequences_pending() -> bool:
	return event_sequence_running or not pending_trigger_sequences.is_empty()


func start_round() -> void:
	if game_over:
		return
	_evaluate_battle_triggers("round_start")
	if _battle_sequences_pending():
		call_deferred("_resume_round_start_after_sequences", current_turn, battle_sequence_serial)
		return
	_begin_round_timeline()


func _resume_round_start_after_sequences(round_number: int, serial: int) -> void:
	while _battle_sequences_pending():
		await get_tree().process_frame
	if serial != battle_sequence_serial or game_over or round_number != current_turn:
		return
	_begin_round_timeline()


func _begin_round_timeline() -> void:
	if check_mission_end():
		return
	activation_count_in_round = 0
	round_activation_budget = maxi(1, alive_count("player") + alive_count("enemy"))
	activated_this_round.clear()
	for unit in units:
		if int(unit["hp"]) <= 0:
			continue
		tick_round_resources(unit)
		unit["reaction_used"] = false
		unit["has_moved"] = false
		unit["has_acted"] = false
		if not unit.has("ct"):
			unit["ct"] = 0
		if not unit.has("casting"):
			unit["casting"] = {}
		# Seed the opening timeline once. Later rounds keep their real CT state.
		if battle_clock_ticks == 0 and int(unit.get("ct", 0)) <= 0:
			unit["ct"] = mini(90, effective_initiative(unit) * 8)
	log_message("MANCHE %d : CT dynamique actif • Move+Act=0 • action seule=20 • Wait=40." % current_turn)
	advance_activation()


func _unit_is_casting(unit: Dictionary) -> bool:
	var casting: Variant = unit.get("casting", {})
	return casting is Dictionary and not (casting as Dictionary).is_empty()


func _next_unit_ready_ticks() -> int:
	var best: int = 999999
	for unit in units:
		if not _unit_is_battle_present(unit) or _unit_is_casting(unit):
			continue
		best = mini(best, CombatMechanics.ticks_until_ready(int(unit.get("ct", 0)), effective_initiative(unit)))
	return best


func _next_cast_ready_ticks() -> int:
	var best: int = 999999
	for unit in units:
		if int(unit.get("hp", 0)) <= 0 or not _unit_is_casting(unit):
			continue
		var casting: Dictionary = unit.get("casting", {})
		best = mini(best, maxi(0, int(casting.get("remaining_ticks", 0))))
	return best


func _advance_battle_clock(step_ticks: int) -> void:
	if step_ticks <= 0:
		return
	battle_clock_ticks += step_ticks
	var due_casts: PackedStringArray = PackedStringArray()
	for unit in units:
		if not _unit_is_battle_present(unit):
			continue
		unit["ct"] = mini(199, int(unit.get("ct", 0)) + effective_initiative(unit) * step_ticks)
		if _unit_is_casting(unit):
			var casting: Dictionary = unit.get("casting", {}).duplicate(true)
			casting["remaining_ticks"] = int(casting.get("remaining_ticks", 0)) - step_ticks
			unit["casting"] = casting
			if int(casting["remaining_ticks"]) <= 0:
				due_casts.append(String(unit["id"]))
	for caster_id: String in due_casts:
		_resolve_due_cast(caster_id)


func _advance_clock_until_unit_ready() -> bool:
	for _guard in range(256):
		if check_mission_end():
			return false
		if _resolve_ready_downed_units():
			if check_mission_end():
				return false
			continue
		var has_ready := false
		for unit in units:
			if int(unit.get("hp", 0)) > 0 and not _unit_is_casting(unit) and int(unit.get("ct", 0)) >= CombatMechanics.CT_THRESHOLD:
				has_ready = true
				break
		if has_ready:
			return true
		var unit_ticks := _next_unit_ready_ticks()
		var cast_ticks := _next_cast_ready_ticks()
		var step_ticks: int = mini(unit_ticks, cast_ticks)
		if step_ticks == 999999:
			return false
		if step_ticks <= 0:
			# A cast can become due without a unit being ready; resolve it before continuing.
			var resolved_any := false
			for unit in units:
				if not _unit_is_casting(unit):
					continue
				var casting: Dictionary = unit.get("casting", {})
				if int(casting.get("remaining_ticks", 0)) <= 0:
					_resolve_due_cast(String(unit["id"]))
					resolved_any = true
			if not resolved_any:
				return false
			continue
		_advance_battle_clock(step_ticks)
	return false


func _ready_unit_before(a: Dictionary, b: Dictionary) -> bool:
	var a_ct := int(a.get("ct", 0))
	var b_ct := int(b.get("ct", 0))
	if a_ct != b_ct:
		return a_ct > b_ct
	var a_speed := effective_initiative(a)
	var b_speed := effective_initiative(b)
	if a_speed != b_speed:
		return a_speed > b_speed
	if a["team"] != b["team"]:
		return a["team"] == "player"
	return String(a["name"]) < String(b["name"])


func _select_ready_unit() -> Dictionary:
	var ready: Array = []
	for unit in units:
		if int(unit.get("hp", 0)) <= 0 or _unit_is_casting(unit):
			continue
		if int(unit.get("ct", 0)) >= CombatMechanics.CT_THRESHOLD:
			ready.append(unit)
	if ready.is_empty():
		return {}
	ready.sort_custom(Callable(self, "_ready_unit_before"))
	return ready[0]


func _predict_dynamic_timeline(limit: int = 7) -> Array:
	var result: Array = []
	var sim: Dictionary = {}
	for unit in units:
		if int(unit.get("hp", 0)) <= 0:
			continue
		var casting: Dictionary = unit.get("casting", {}) if _unit_is_casting(unit) else {}
		sim[String(unit["id"])] = {
			"ct": int(unit.get("ct", 0)),
			"speed": effective_initiative(unit),
			"casting": not casting.is_empty(),
			"cast_ticks": maxi(0, int(casting.get("remaining_ticks", 0))) if not casting.is_empty() else 0,
			"team": String(unit["team"]),
			"name": String(unit["name"]),
		}
	if not active_unit_id.is_empty() and sim.has(active_unit_id):
		result.append(active_unit_id)
		var current: Dictionary = sim[active_unit_id]
		current["ct"] = CombatMechanics.CT_AFTER_FULL_TURN
		sim[active_unit_id] = current
	for _guard: int in range(64):
		if result.size() >= limit or sim.is_empty():
			break
		var best_ticks: int = 999999
		for id in sim.keys():
			var state: Dictionary = sim[id]
			if bool(state.get("casting", false)):
				best_ticks = mini(best_ticks, int(state.get("cast_ticks", 0)))
			else:
				best_ticks = mini(best_ticks, CombatMechanics.ticks_until_ready(int(state["ct"]), int(state["speed"])))
		if best_ticks == 999999:
			break
		for id in sim.keys():
			var state: Dictionary = sim[id]
			state["ct"] = mini(199, int(state["ct"]) + int(state["speed"]) * best_ticks)
			if bool(state.get("casting", false)):
				state["cast_ticks"] = maxi(0, int(state.get("cast_ticks", 0)) - best_ticks)
				if int(state["cast_ticks"]) <= 0:
					state["casting"] = false
			sim[id] = state
		var ready_ids: Array = []
		for id in sim.keys():
			var state: Dictionary = sim[id]
			if not bool(state.get("casting", false)) and int(state["ct"]) >= CombatMechanics.CT_THRESHOLD:
				ready_ids.append(String(id))
		if ready_ids.is_empty():
			continue
		ready_ids.sort_custom(func(a_id: String, b_id: String) -> bool:
			var a: Dictionary = sim[a_id]
			var b: Dictionary = sim[b_id]
			if int(a["ct"]) != int(b["ct"]):
				return int(a["ct"]) > int(b["ct"])
			if int(a["speed"]) != int(b["speed"]):
				return int(a["speed"]) > int(b["speed"])
			if String(a["team"]) != String(b["team"]):
				return String(a["team"]) == "player"
			return String(a["name"]) < String(b["name"])
		)
		var chosen_id: String = String(ready_ids[0])
		result.append(chosen_id)
		var chosen: Dictionary = sim[chosen_id]
		chosen["ct"] = CombatMechanics.CT_AFTER_FULL_TURN
		sim[chosen_id] = chosen
	return result


func _refresh_dynamic_timeline_prediction() -> void:
	timeline_order = _predict_dynamic_timeline(7)
	timeline_index = 0


func advance_activation() -> void:
	if game_over:
		return
	special_targeting = false
	special_target_skill_id = ""
	special_target_cells.clear()
	if not _advance_clock_until_unit_ready():
		return
	var unit := _select_ready_unit()
	if unit.is_empty():
		return
	active_unit_id = String(unit["id"])
	unit["has_moved"] = false
	unit["has_acted"] = false
	_refresh_dynamic_timeline_prediction()
	_process_status_phase(unit, "activation_start")
	if int(unit["hp"]) <= 0:
		check_mission_end()
		if not game_over:
			_finalize_activation_timing(unit, true)
		return
	if StatusCatalog.prevents_action(unit):
		log_message("%s est bloqué par un statut et perd son activation." % unit["name"] )
		spawn_floating_text(unit["pos"], "ÉTOURDI", GOLD)
		resolve_end_of_activation(unit)
		refresh_all()
		check_mission_end()
		if not game_over:
			_finalize_activation_timing(unit, true)
		return
	if unit["team"] == "player":
		enemy_phase = false
		selected_id = unit["id"]
		log_message("Activation de %s • CT %d • VIT %d. Déplacement/action dans l'ordre voulu." % [unit["name"], int(unit.get("ct", 0)), effective_initiative(unit)])
		refresh_all()
	else:
		enemy_phase = true
		selected_id = ""
		refresh_all()
		call_deferred("run_enemy_activation_deferred", str(unit["id"]), battle_serial)


func _all_alive_units_activated_this_round() -> bool:
	for candidate in units:
		if int(candidate.get("hp", 0)) <= 0:
			continue
		if not activated_this_round.has(String(candidate.get("id", ""))):
			return false
	return true


func _finalize_activation_timing(unit: Dictionary, forced_skip: bool = false) -> void:
	if unit.is_empty():
		return
	var end_ct: int = CombatMechanics.action_end_ct(bool(unit.get("has_moved", false)), bool(unit.get("has_acted", false)), forced_skip)
	end_ct = CombatMechanics.apply_end_ct_bonus(end_ct, int(unit.get("end_ct_bonus", 0)))
	unit["ct"] = end_ct
	activation_count_in_round += 1
	activated_this_round[String(unit.get("id", ""))] = true
	_refresh_dynamic_timeline_prediction()
	if check_mission_end():
		return
	if _all_alive_units_activated_this_round():
		rounds_completed = current_turn
		_evaluate_battle_triggers("round_end")
		if _battle_sequences_pending():
			call_deferred("_resume_round_end_after_sequences", current_turn, battle_sequence_serial)
			return
		_complete_round_transition()
		return
	advance_activation()


func run_enemy_activation_deferred(enemy_id: String, serial: int) -> void:
	if serial != battle_serial or game_over or active_unit_id != enemy_id:
		return
	var enemy := unit_by_id(enemy_id)
	if enemy.is_empty() or int(enemy["hp"]) <= 0:
		advance_activation()
		return
	run_enemy_activation(enemy)
	refresh_all()
	if not game_over and serial == battle_serial:
		var timer := get_tree().create_timer(0.42)
		timer.timeout.connect(_finish_enemy_presentation.bind(enemy_id, serial))


func _finish_enemy_presentation(enemy_id: String, serial: int) -> void:
	if serial != battle_serial or game_over or active_unit_id != enemy_id:
		return
	var enemy := unit_by_id(enemy_id)
	if enemy.is_empty():
		advance_activation()
		return
	_finalize_activation_timing(enemy)


func timeline_id_before(a_id: Variant, b_id: Variant) -> bool:
	var a := unit_by_id(str(a_id))
	var b := unit_by_id(str(b_id))
	if effective_initiative(a) == effective_initiative(b):
		if a["team"] != b["team"]:
			return a["team"] == "player"
		return str(a["name"]) < str(b["name"])
	return effective_initiative(a) > effective_initiative(b)


func unit_by_id(id: String) -> Dictionary:
	for unit in units:
		if unit["id"] == id:
			return unit
	return {}


func alive_count(team: String) -> int:
	var count := 0
	for unit in units:
		if unit["team"] == team and int(unit["hp"]) > 0:
			count += 1
	return count


func _resume_round_end_after_sequences(round_number: int, serial: int) -> void:
	while _battle_sequences_pending():
		await get_tree().process_frame
	if serial != battle_sequence_serial or game_over or round_number != current_turn:
		return
	_complete_round_transition()


func _complete_round_transition() -> void:
	if check_mission_end():
		return
	if not _has_data_driven_mission_logic() and mission_objective == "survive" and current_turn >= survival_rounds:
		finish_mission_result(true, "VICTOIRE ! %d manches tenues. La scène tient encore debout." % survival_rounds)
		return
	current_turn += 1
	start_round()


func selected_unit() -> Dictionary:
	if selected_id.is_empty():
		return {}
	for unit in units:
		if unit["id"] == selected_id and int(unit["hp"]) > 0:
			return unit
	return {}


func unit_at(cell: Vector2i) -> Dictionary:
	for unit in units:
		if int(unit["hp"]) > 0 and unit["pos"] == cell:
			return unit
	return {}


func update_selection() -> void:
	move_cells.clear()
	attack_cells.clear()
	move_costs.clear()
	move_parents.clear()
	var unit := selected_unit()
	if unit.is_empty() or enemy_phase or unit["id"] != active_unit_id:
		return
	if special_targeting:
		special_target_cells = special_targetable_cells(unit, SkillCatalog.skill_range(special_target_skill_id), special_target_skill_id)
		return
	if not unit["has_moved"]:
		var navigation := movement_data(unit)
		move_cells = navigation["cells"]
		move_costs = navigation["costs"]
		move_parents = navigation["parents"]
	if not unit["has_acted"]:
		for candidate in units:
			if (
				candidate["team"] == "enemy"
				and int(candidate["hp"]) > 0
				and can_attack(unit, candidate)
			):
				attack_cells.append(candidate["pos"])


func update_ui() -> void:
	if not is_instance_valid(turn_label):
		return
	if game_over:
		turn_label.text = "MISSION RÉUSSIE" if mission_victory else "MISSION ÉCHOUÉE"
		turn_label.add_theme_color_override("font_color", GOLD if mission_victory else CORAL)
	elif enemy_phase:
		var enemy := unit_by_id(active_unit_id)
		turn_label.text = "MANCHE %d • %s JOUE" % [current_turn, enemy["name"]]
		turn_label.add_theme_color_override("font_color", CORAL)
	else:
		var active := selected_unit()
		turn_label.text = "MANCHE %d • %s JOUE" % [current_turn, active["name"] if not active.is_empty() else "À TOI"]
		turn_label.add_theme_color_override("font_color", MINT)

	status_label.text = objective_status_text()
	timeline_label.text = "CT DYNAMIQUE • chiffre = CT / VIT"
	rebuild_timeline_bar()
	var unit := selected_unit()
	if unit.is_empty():
		selected_label.text = "Activation ennemie en cours.\nLa timeline décide qui joue ensuite."
		special_button.text = "Compétence I"
		special_button.disabled = true
		secondary_button.text = "Compétence II"
		secondary_button.disabled = true
	else:
		var terrain_text := "Hauteur %d" % terrain_height(unit["pos"])
		if cover_cells.has(unit["pos"]):
			terrain_text += " • Couvert"
		if hazard_cells.has(unit["pos"]):
			terrain_text += " • SPORES !"
		var move_text := "MVT fait" if unit["has_moved"] else "MVT prêt"
		var act_text := "ACT faite" if unit["has_acted"] else "ACT prête"
		var state_text := status_text(unit)
		if unit["id"] == crown_carrier_id:
			state_text = (state_text + ", " if not state_text.is_empty() else "") + "COURONNE"
		var role_text := String(unit["role"])
		if String(unit.get("job_id", "")).is_empty() == false:
			role_text += " • %s niv.%d" % [UnitCatalog.job_name(String(unit["job_id"])), int(unit.get("job_level", 1))]
		var cast_text := ""
		if _unit_is_casting(unit):
			var casting: Dictionary = unit.get("casting", {})
			cast_text = " • CAST %s (%dt)" % [skill_name(String(casting.get("skill_id", ""))), maxi(0, int(casting.get("remaining_ticks", 0)))]
		selected_label.text = (
			"%s — %s\nPV %d/%d • Focus %d/%d • MVT %d • Portée %d%s • VIT %d • CT %d\nPRÉC %+d • ESQ %+d • %s • face %s • %s / %s%s%s"
			% [
				unit["name"], role_text, int(unit["hp"]), int(unit["max_hp"]), int(unit["focus"]), int(unit["max_focus"]), effective_move(unit),
				effective_range(unit), range_bonus_label(unit), effective_initiative(unit), int(unit.get("ct", 0)), effective_accuracy(unit), effective_evasion(unit), terrain_text,
				facing_label(unit), move_text, act_text, (" • " + state_text) if not state_text.is_empty() else "", cast_text
			]
		)
		var primary_id := str(unit["special"])
		var secondary_id := str(unit.get("secondary", ""))
		var primary_cd := cooldown_left(unit, primary_id)
		var secondary_cd := cooldown_left(unit, secondary_id)
		var primary_cast: int = SkillCatalog.cast_time_ticks(primary_id)
		var secondary_cast: int = SkillCatalog.cast_time_ticks(secondary_id)
		var primary_cast_text := " • CAST %d" % primary_cast if primary_cast > 0 else ""
		var secondary_cast_text := " • CAST %d" % secondary_cast if secondary_cast > 0 else ""
		special_button.text = "%s • F%d • CD %s%s" % [skill_name(primary_id), skill_cost(primary_id), ("prêt" if primary_cd <= 0 else str(primary_cd)), primary_cast_text]
		secondary_button.text = "%s • F%d • CD %s%s" % [skill_name(secondary_id), skill_cost(secondary_id), ("prêt" if secondary_cd <= 0 else str(secondary_cd)), secondary_cast_text]
		if special_targeting:
			special_button.text = "Annuler Spore Funk"
		special_button.disabled = not can_use_skill(unit, primary_id) and not special_targeting
		secondary_button.disabled = not can_use_skill(unit, secondary_id)
	end_turn_button.disabled = game_over or enemy_phase
	log_label.text = visible_log()


func rebuild_timeline_bar() -> void:
	if not is_instance_valid(timeline_bar):
		return
	for child in timeline_bar.get_children():
		timeline_bar.remove_child(child)
		child.queue_free()
	var shown: int = 0
	var start_index: int = maxi(0, timeline_index)
	for offset in range(timeline_order.size()):
		var index: int = (start_index + offset) % maxi(1, timeline_order.size())
		var unit := unit_by_id(str(timeline_order[index]))
		if unit.is_empty() or int(unit["hp"]) <= 0:
			continue
		var card := PanelContainer.new()
		card.custom_minimum_size = Vector2(49.0, 42.0)
		var active: bool = String(unit["id"]) == active_unit_id
		var fill: Color = unit["color"]
		fill.a = 0.28 if not active else 0.62
		card.add_theme_stylebox_override(
			"panel", make_style(fill, 8, GOLD if active else PANEL_EDGE)
		)
		var label := Label.new()
		var initial := str(unit["name"]).substr(0, 1).to_upper()
		label.text = "%s\n%d/%d" % [initial, int(unit.get("ct", 0)), effective_initiative(unit)]
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		label.add_theme_font_size_override("font_size", 12)
		label.add_theme_color_override("font_color", TEXT)
		var cast_tip := ""
		if _unit_is_casting(unit):
			var casting: Dictionary = unit.get("casting", {})
			cast_tip = " • CAST %s %dt" % [skill_name(String(casting.get("skill_id", ""))), maxi(0, int(casting.get("remaining_ticks", 0)))]
		label.tooltip_text = "%s • %s • CT %d • VIT %d%s" % [unit["name"], unit["role"], int(unit.get("ct", 0)), effective_initiative(unit), cast_tip]
		card.add_child(label)
		timeline_bar.add_child(card)
		shown += 1
		if shown >= 7:
			break


func update_preview() -> void:
	if not is_instance_valid(preview_label):
		return
	if game_over:
		preview_label.text = "Résultat verrouillé : le débrief arrive, puis retour à la préparation."
		return
	if enemy_phase:
		preview_label.text = "Activation ennemie : la prochaine unité est déjà visible dans la timeline."
		return
	var unit := selected_unit()
	if unit.is_empty():
		preview_label.text = "La timeline choisit automatiquement l'unité active."
		return
	if special_targeting:
		if special_target_cells.has(hovered_cell):
			var victims := 0
			for candidate in units:
				if candidate["team"] == "enemy" and int(candidate["hp"]) > 0 and manhattan(hovered_cell, candidate["pos"]) <= 1:
					victims += 1
			var funk_preview_damage := 2 + _skill_power_bonus(unit, "funk")
			preview_label.text = "SPORE FUNK : zone croix rayon 1 • %d cible(s)\n%d dégâts + RALENTI + poussée" % [victims, funk_preview_damage]
		else:
			preview_label.text = "SPORE FUNK : survole puis clique une case violette. Clic droit pour annuler."
		return
	var hovered_unit := unit_at(hovered_cell)
	if (
		not hovered_unit.is_empty()
		and hovered_unit["team"] == "enemy"
		and can_attack(unit, hovered_unit)
	):
		var profile := damage_profile(unit, hovered_unit)
		var hit := hit_profile(unit, hovered_unit, CombatMechanics.BASIC_ATTACK_ACCURACY, false)
		var shield_note: String = ""
		if int(hovered_unit.get("shield_block_chance", 0)) > 0 and int(hovered_unit.get("shield_block_reduction", 0)) > 0:
			shield_note = " • BLOC %d%% (-%d)" % [int(hovered_unit.get("shield_block_chance", 0)), int(hovered_unit.get("shield_block_reduction", 0))]
		preview_label.text = (
			"PRÉVISION : %s → %s = %d dégâts • %d%% HIT%s\nbase %d%s • %s"
			% [
				unit["name"],
				hovered_unit["name"],
				int(profile["damage"]),
				int(hit["chance"]),
				shield_note,
				int(profile["base"]),
				profile["details"],
				String(hit["arc"]).to_upper()
			]
		)
	elif (
		not hovered_unit.is_empty()
		and hovered_unit["team"] == "enemy"
		and manhattan(unit["pos"], hovered_unit["pos"]) <= effective_range(unit)
		and int(unit["range"]) > 1
		and not has_line_of_sight(unit["pos"], hovered_unit["pos"], unit["id"], hovered_unit["id"])
	):
		preview_label.text = "LIGNE DE VUE BLOQUÉE : déplace-toi pour ouvrir un angle de tir."
	elif move_cells.has(hovered_cell):
		var terrain_text := "hauteur %d" % terrain_height(hovered_cell)
		if cover_cells.has(hovered_cell):
			terrain_text += " • couverture"
		if hazard_cells.has(hovered_cell):
			terrain_text += " • SPORES : -1 PV fin activation"
		if mission_objective == "crown" and hovered_cell == crown_cell and crown_carrier_id.is_empty():
			terrain_text += " • COURONNE"
		if extraction_cells.has(hovered_cell):
			terrain_text += " • EXTRACTION"
		preview_label.text = (
			"TRAJET : %d point(s) de déplacement\n%s"
			% [int(move_costs.get(hovered_cell, 0)), terrain_text]
		)
	else:
		preview_label.text = "Déplacement et action sont indépendants. Oriente-toi puis termine l'activation."


func visible_log() -> String:
	var visible: Array = []
	var first: int = maxi(0, message_log.size() - 5)
	for index in range(first, message_log.size()):
		visible.append("• " + str(message_log[index]))
	return "\n".join(visible)


func log_message(message: String) -> void:
	message_log.append(message)
	if message_log.size() > 14:
		message_log.pop_front()
	if is_instance_valid(log_label):
		log_label.text = visible_log()


func movement_data(unit: Dictionary) -> Dictionary:
	var start: Vector2i = unit["pos"]
	var move_budget := effective_move(unit)
	var costs: Dictionary = {}
	var parents: Dictionary = {}
	var frontier: Array = [{"cell": start, "cost": 0}]
	costs[start] = 0

	while not frontier.is_empty():
		var cheapest_index := 0
		for index in range(1, frontier.size()):
			if int(frontier[index]["cost"]) < int(frontier[cheapest_index]["cost"]):
				cheapest_index = index
		var current: Dictionary = frontier.pop_at(cheapest_index)
		var current_cell: Vector2i = current["cell"]
		var current_cost := int(current["cost"])
		if current_cost > int(costs.get(current_cell, move_budget + 1)):
			continue
		for next_cell in neighbours(current_cell):
			if not is_walkable(next_cell, unit["id"]):
				continue
			if not can_step_height(unit, current_cell, next_cell):
				continue
			var next_cost := current_cost + movement_cost(current_cell, next_cell)
			if next_cost > move_budget:
				continue
			if costs.has(next_cell) and int(costs[next_cell]) <= next_cost:
				continue
			costs[next_cell] = next_cost
			parents[next_cell] = current_cell
			frontier.append({"cell": next_cell, "cost": next_cost})

	var cells: Array = []
	for cell in costs.keys():
		if cell != start:
			cells.append(cell)
	return {"cells": cells, "costs": costs, "parents": parents}


func movement_cost(from_cell: Vector2i, to_cell: Vector2i) -> int:
	var climb: int = maxi(0, terrain_height(to_cell) - terrain_height(from_cell))
	return 1 + climb


func can_step_height(unit: Dictionary, from_cell: Vector2i, to_cell: Vector2i) -> bool:
	var delta: int = terrain_height(to_cell) - terrain_height(from_cell)
	var jump_up: int = 1 + maxi(0, int(unit.get("jump_up_bonus", 0)))
	var jump_down: int = 2 + maxi(0, int(unit.get("jump_down_bonus", 0)))
	if delta > 0:
		return delta <= jump_up
	if delta < 0:
		return absi(delta) <= jump_down
	return true


func neighbours(cell: Vector2i) -> Array:
	return BattleRules.neighbours(cell)


func is_walkable(cell: Vector2i, ignored_id: String) -> bool:
	if not is_inside(cell) or obstacles.has(cell) or _closed_door_at(cell):
		return false
	for unit in units:
		if unit["id"] != ignored_id and _unit_is_battle_present(unit) and unit["pos"] == cell:
			return false
	return true


func is_inside(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.x < grid_width and cell.y >= 0 and cell.y < grid_height


func terrain_height(cell: Vector2i) -> int:
	return int(terrain_heights.get(cell, 0))


func effective_range(unit: Dictionary) -> int:
	return effective_range_at(unit, unit["pos"])


func effective_min_range(unit: Dictionary) -> int:
	return maxi(1, int(unit.get("attack_min_range", 1)))


func effective_range_at(unit: Dictionary, position: Vector2i) -> int:
	var result := int(unit.get("attack_max_range", unit.get("range", 1))) + StatusCatalog.modifier(unit, "range_delta")
	if result > 1 and terrain_height(position) >= 2:
		result += 1
	return maxi(effective_min_range(unit), result)


func threat_min_range(unit: Dictionary) -> int:
	return maxi(1, int(unit.get("threat_min_range", 1)))


func threat_max_range(unit: Dictionary) -> int:
	return maxi(threat_min_range(unit), int(unit.get("threat_max_range", 1)))


func threatens_distance(unit: Dictionary, distance: int) -> bool:
	if not bool(unit.get("can_opportunity_attack", true)):
		return false
	return CombatMechanics.range_allowed(distance, threat_min_range(unit), threat_max_range(unit))


func range_bonus_label(unit: Dictionary) -> String:
	var delta := effective_range(unit) - int(unit["range"])
	if delta > 0:
		return " (+%d bonus)" % delta
	if delta < 0:
		return " (%d malus)" % delta
	return ""


func initiative_for_id(id: String) -> int:
	return UnitCatalog.initiative_for(id)


func initiative_before(a: Dictionary, b: Dictionary) -> bool:
	if effective_initiative(a) == effective_initiative(b):
		return str(a["name"]) < str(b["name"])
	return effective_initiative(a) > effective_initiative(b)


func living_enemies_by_initiative() -> Array:
	var result: Array = []
	for unit in units:
		if unit["team"] == "enemy" and int(unit["hp"]) > 0:
			result.append(unit)
	result.sort_custom(Callable(self, "initiative_before"))
	return result


func enemy_initiative_summary() -> String:
	var labels: Array = []
	for unit in living_enemies_by_initiative():
		labels.append("%s %d" % [short_name(str(unit["name"])), effective_initiative(unit)])
	if labels.is_empty():
		return "—"
	return " > ".join(labels)


func timeline_summary() -> String:
	if timeline_order.is_empty():
		return "—"
	var labels: Array = []
	for index in range(timeline_order.size()):
		var unit := unit_by_id(str(timeline_order[index]))
		if unit.is_empty() or int(unit["hp"]) <= 0:
			continue
		var marker := "▶" if index == timeline_index else ""
		labels.append("%s%s %d" % [marker, short_name(str(unit["name"])), effective_initiative(unit)])
	return " > ".join(labels)


func objective_status_text() -> String:
	if not runtime_objective_text.is_empty():
		var phase_suffix := " • Phase %s" % runtime_phase if not runtime_phase.is_empty() else ""
		return runtime_objective_text + phase_suffix
	if game_over:
		return "Mission accomplie" if mission_victory else "Escouade K.O. • mission échouée"
	var squad_total := selected_hero_count()
	var contract := secondary_objective_progress_text()
	if mission_objective == "crown":
		if crown_carrier_id.is_empty():
			return "OBJECTIF : atteindre ♛ (%d,%d) • Bonus %d/%d • Équipe %d/%d • Ennemis %d/%d • %s" % [crown_cell.x + 1, crown_cell.y + 1, bonus_collected, bonus_target_total, alive_count("player"), squad_total, alive_count("enemy"), enemies_total_initial, contract]
		var carrier := unit_by_id(crown_carrier_id)
		return "COURONNE : %s • sortie verte • Bonus %d/%d • Équipe %d/%d • Ennemis %d/%d • %s" % [carrier["name"], bonus_collected, bonus_target_total, alive_count("player"), squad_total, alive_count("enemy"), enemies_total_initial, contract]
	if mission_objective == "survive":
		return "TENIR : manche %d/%d • Bonus %d/%d • Équipe %d/%d • Ennemis %d/%d • %s" % [current_turn, survival_rounds, bonus_collected, bonus_target_total, alive_count("player"), squad_total, alive_count("enemy"), enemies_total_initial, contract]
	return "ÉLIMINATION : Bonus %d/%d • Équipe %d/%d • Ennemis %d/%d • Rang %d • %s" % [bonus_collected, bonus_target_total, alive_count("player"), squad_total, alive_count("enemy"), enemies_total_initial, campaign_rank(), contract]


func short_name(value: String) -> String:
	if value == "Le Comptable":
		return "Compta"
	if value == "DJ Morille":
		return "DJ"
	return value


func effective_move(unit: Dictionary) -> int:
	if StatusCatalog.prevents_movement(unit):
		return 0
	return max(0, int(unit["move"]) + StatusCatalog.modifier(unit, "movement_delta"))


func effective_physical_power(unit: Dictionary) -> int:
	return maxi(0, int(unit.get("physical_power", unit.get("attack", 0))) + StatusCatalog.modifier(unit, "attack_delta"))


func effective_magic_power(unit: Dictionary) -> int:
	return maxi(0, int(unit.get("magic_power", 0)) + StatusCatalog.modifier(unit, "magic_power_delta"))


func effective_physical_defense(unit: Dictionary) -> int:
	return maxi(0, int(unit.get("physical_defense", 0)) + StatusCatalog.modifier(unit, "physical_defense_delta"))


func effective_magic_defense(unit: Dictionary) -> int:
	return maxi(0, int(unit.get("magic_defense", 0)) + StatusCatalog.modifier(unit, "magic_defense_delta"))


func effective_attack(unit: Dictionary) -> int:
	return effective_physical_power(unit)


func effective_basic_attack_power(unit: Dictionary) -> int:
	return effective_physical_power(unit) if String(unit.get("basic_attack_damage_type", "physical")) == "physical" else effective_magic_power(unit)


func effective_initiative(unit: Dictionary) -> int:
	return CombatMechanics.speed_from_initiative(max(0, int(unit["initiative"]) + StatusCatalog.modifier(unit, "initiative_delta")))


func effective_accuracy(unit: Dictionary) -> int:
	return int(unit.get("accuracy", 0)) + StatusCatalog.modifier(unit, "accuracy_delta")


func effective_evasion(unit: Dictionary) -> int:
	return int(unit.get("evasion", 0)) + StatusCatalog.modifier(unit, "evasion_delta")


func attack_arc(attacker: Dictionary, target: Dictionary) -> String:
	if is_back_attack(attacker, target):
		return "back"
	if is_side_attack(attacker, target):
		return "side"
	return "front"


func hit_profile(attacker: Dictionary, target: Dictionary, base_accuracy: int = CombatMechanics.BASIC_ATTACK_ACCURACY, ignore_cover: bool = false) -> Dictionary:
	var arc := attack_arc(attacker, target)
	var height_advantage := terrain_height(Vector2i(attacker["pos"])) > terrain_height(Vector2i(target["pos"]))
	var covered := not ignore_cover and int(attacker.get("range", 1)) > 1 and cover_cells.has(target["pos"])
	var adjusted_base_accuracy: int = base_accuracy
	if base_accuracy == CombatMechanics.BASIC_ATTACK_ACCURACY:
		adjusted_base_accuracy += int(attacker.get("basic_attack_accuracy_bonus", 0))
	var chance := CombatMechanics.hit_chance(adjusted_base_accuracy, effective_accuracy(attacker), effective_evasion(target), arc, height_advantage, covered)
	return {
		"chance": chance,
		"arc": arc,
		"height_advantage": height_advantage,
		"covered": covered,
	}


func _roll_hit(chance: int) -> bool:
	return battle_rng.randi_range(1, 100) <= clampi(chance, 5, 100)


func add_status(unit: Dictionary, status_id: String) -> void:
	StatusCatalog.apply(unit, status_id)
	var status_vfx_id := StatusCatalog.vfx_id(status_id)
	if not status_vfx_id.is_empty() and unit.has("pos"):
		spawn_visual_effect(status_vfx_id, unit["pos"])


func remove_status(unit: Dictionary, status_id: String) -> void:
	StatusCatalog.remove(unit, status_id)


func has_status(unit: Dictionary, status_id: String) -> bool:
	return StatusCatalog.has(unit, status_id)


func status_text(unit: Dictionary) -> String:
	var labels: Array[String] = []
	var from_catalog := StatusCatalog.display_text(unit)
	if not from_catalog.is_empty():
		labels.append(from_catalog)
	var reaction_type := String(unit.get("reaction_type", "none"))
	if reaction_type != "none" and _reaction_available(unit):
		labels.append("RÉACTION %s PRÊTE" % reaction_type.to_upper())
	return ", ".join(labels)


func facing_label(unit: Dictionary) -> String:
	return BattleRules.facing_label(unit)


func direction_from_to(from_cell: Vector2i, to_cell: Vector2i) -> Vector2i:
	return BattleRules.direction_from_to(from_cell, to_cell)


func is_back_attack(attacker: Dictionary, target: Dictionary) -> bool:
	return BattleRules.is_back_attack(attacker, target)


func is_side_attack(attacker: Dictionary, target: Dictionary) -> bool:
	return BattleRules.is_side_attack(attacker, target)


func line_cells(from_cell: Vector2i, to_cell: Vector2i) -> Array:
	return BattleRules.line_cells(from_cell, to_cell)


func has_line_of_sight(
	from_cell: Vector2i, to_cell: Vector2i, source_id: String = "", target_id: String = ""
) -> bool:
	if manhattan(from_cell, to_cell) <= 1:
		return true
	var cells := line_cells(from_cell, to_cell)
	for index in range(1, cells.size() - 1):
		var cell: Vector2i = cells[index]
		if obstacles.has(cell) or _closed_door_at(cell):
			return false
		var blocker := unit_at(cell)
		if (
			not blocker.is_empty()
			and blocker["id"] != source_id
			and blocker["id"] != target_id
		):
			return false
	return true


func can_attack_from(attacker: Dictionary, from_cell: Vector2i, target: Dictionary) -> bool:
	var distance: int = manhattan(from_cell, target["pos"])
	if not CombatMechanics.range_allowed(distance, effective_min_range(attacker), effective_range_at(attacker, from_cell)):
		return false
	if effective_range_at(attacker, from_cell) <= 1:
		return true
	return has_line_of_sight(from_cell, target["pos"], attacker["id"], target["id"])


func can_attack(attacker: Dictionary, target: Dictionary) -> bool:
	return can_attack_from(attacker, attacker["pos"], target)


func resistance_percent(target: Dictionary, damage_type: String = "physical") -> int:
	var resistances: Dictionary = target.get("resistances", {})
	return clamp(int(resistances.get(damage_type, 0)), -100, 100)


func apply_resistance(raw_amount: int, target: Dictionary, damage_type: String = "physical") -> int:
	var percent := resistance_percent(target, damage_type)
	return max(0, int(round(float(raw_amount) * (100.0 - float(percent)) / 100.0)))


func status_adjusted_direct_damage(raw_amount: int, target: Dictionary, source: Dictionary = {}, damage_type: String = "physical") -> int:
	var delta := StatusCatalog.modifier(target, "incoming_damage_delta")
	if not source.is_empty():
		delta += StatusCatalog.modifier(source, "outgoing_damage_delta")
	var defense: int = 0
	if not source.is_empty():
		defense = effective_physical_defense(target) if damage_type == "physical" else effective_magic_defense(target)
	var after_defense: int = CombatMechanics.damage_after_defense(maxi(0, raw_amount + delta), defense, 1)
	var resisted: int = apply_resistance(after_defense, target, damage_type)
	return maxi(0, resisted - int(target.get("flat_damage_reduction", 0)))


func damage_profile(
	attacker: Dictionary, target: Dictionary, base_override: int = -1, ignore_cover: bool = false
) -> Dictionary:
	var base_damage: int = effective_basic_attack_power(attacker) if base_override < 0 else base_override
	if base_override < 0:
		base_damage += int(attacker.get("basic_attack_damage_bonus", 0))
	var height_bonus: int = 1 if terrain_height(Vector2i(attacker["pos"])) > terrain_height(Vector2i(target["pos"])) else 0
	var back_bonus: int = 2 if is_back_attack(attacker, target) else 0
	var side_bonus: int = 1 if not is_back_attack(attacker, target) and is_side_attack(attacker, target) else 0
	var cover_penalty: int = 0
	if not ignore_cover and int(attacker["range"]) > 1 and cover_cells.has(target["pos"]):
		cover_penalty = 1
	var outgoing_status: int = StatusCatalog.modifier(attacker, "outgoing_damage_delta")
	var incoming_status: int = StatusCatalog.modifier(target, "incoming_damage_delta")
	var guard_penalty: int = maxi(0, -StatusCatalog.status_modifier(target, "guarded", "incoming_damage_delta"))
	var weakened_penalty: int = maxi(0, -StatusCatalog.status_modifier(attacker, "weakened", "outgoing_damage_delta"))
	var marked_bonus: int = maxi(0, StatusCatalog.status_modifier(target, "marked", "incoming_damage_delta"))
	var known_status_total: int = -guard_penalty - weakened_penalty + marked_bonus
	var other_status_delta: int = outgoing_status + incoming_status - known_status_total
	var raw_damage: int = maxi(1, base_damage + height_bonus + back_bonus + side_bonus - cover_penalty + outgoing_status + incoming_status)
	var damage_type: String = String(attacker.get("basic_attack_damage_type", "physical"))
	var defense: int = effective_physical_defense(target) if damage_type == "physical" else effective_magic_defense(target)
	var after_defense: int = CombatMechanics.damage_after_defense(raw_damage, defense, 1)
	var resistance: int = resistance_percent(target, damage_type)
	var armor_reduction: int = maxi(0, int(target.get("flat_damage_reduction", 0)))
	var damage: int = maxi(1, apply_resistance(after_defense, target, damage_type) - armor_reduction)
	var summary := ""
	var details := ""
	if height_bonus > 0:
		summary += " (+1 hauteur)"
		details += " +1 hauteur"
	if back_bonus > 0:
		summary += " (+2 dos)"
		details += " +2 dos"
	elif side_bonus > 0:
		summary += " (+1 flanc)"
		details += " +1 flanc"
	if cover_penalty > 0:
		summary += " (-1 couvert)"
		details += " -1 couvert"
	if guard_penalty > 0:
		summary += " (-%d garde)" % guard_penalty
		details += " -%d garde" % guard_penalty
	if weakened_penalty > 0:
		summary += " (-%d affaibli)" % weakened_penalty
		details += " -%d affaibli" % weakened_penalty
	if marked_bonus > 0:
		summary += " (+%d balise)" % marked_bonus
		details += " +%d balise" % marked_bonus
	if other_status_delta != 0:
		summary += " (%+d statuts)" % other_status_delta
		details += " %+d statuts" % other_status_delta
	if defense > 0:
		summary += " (-%d %s)" % [defense, "DEF.P" if damage_type == "physical" else "DEF.M"]
		details += " -%d %s" % [defense, "DEF.P" if damage_type == "physical" else "DEF.M"]
	if resistance != 0:
		summary += " (%+d%% rés. %s)" % [resistance, damage_type]
		details += " %+d%% rés. %s" % [resistance, damage_type]
	if armor_reduction > 0:
		summary += " (-%d armure)" % armor_reduction
		details += " -%d armure" % armor_reduction
	return {
		"base": base_damage,
		"height_bonus": height_bonus,
		"back_bonus": back_bonus,
		"side_bonus": side_bonus,
		"cover_penalty": cover_penalty,
		"guard_penalty": guard_penalty,
		"weakened_penalty": weakened_penalty,
		"marked_bonus": marked_bonus,
		"status_delta": outgoing_status + incoming_status,
		"damage_type": damage_type,
		"defense": defense,
		"resistance": resistance,
		"armor_reduction": armor_reduction,
		"damage": damage,
		"summary": summary,
		"details": details
	}


func _unit_is_downed(unit: Dictionary) -> bool:
	return not unit.is_empty() and bool(unit.get("downed", false)) and not bool(unit.get("removed_from_battle", false))


func _unit_is_battle_present(unit: Dictionary) -> bool:
	return not unit.is_empty() and (int(unit.get("hp", 0)) > 0 or _unit_is_downed(unit))


func _enter_downed(unit: Dictionary) -> void:
	unit["hp"] = 0
	unit["downed"] = true
	unit["downed_countdown"] = CombatMechanics.DOWNED_COUNTDOWN_ACTIVATIONS
	unit["removed_from_battle"] = false
	unit["casting"] = {}
	unit["ct"] = 0
	unit["has_moved"] = true
	unit["has_acted"] = true


func _revive_unit(unit: Dictionary, bonus_hp: int = 0) -> int:
	if not _unit_is_downed(unit):
		return 0
	var restored: int = CombatMechanics.revive_hp(int(unit.get("max_hp", 1)), bonus_hp)
	unit["hp"] = restored
	unit["downed"] = false
	unit["downed_countdown"] = 0
	unit["removed_from_battle"] = false
	unit["ct"] = 0
	unit["reaction_used"] = false
	ko_fx.erase(String(unit.get("id", "")))
	return restored


func _resolve_ready_downed_units() -> bool:
	var resolved := false
	for unit in units:
		if not _unit_is_downed(unit) or int(unit.get("ct", 0)) < CombatMechanics.CT_THRESHOLD:
			continue
		resolved = true
		unit["ct"] = 0
		unit["downed_countdown"] = CombatMechanics.downed_tick_remaining(int(unit.get("downed_countdown", CombatMechanics.DOWNED_COUNTDOWN_ACTIVATIONS)))
		var remaining: int = int(unit["downed_countdown"])
		if remaining <= 0:
			unit["removed_from_battle"] = true
			unit["downed"] = false
			log_message("%s quitte définitivement la bataille faute de réanimation." % unit["name"])
		else:
			spawn_floating_text(unit["pos"], "K.O. %d" % remaining, CORAL)
			log_message("%s est toujours K.O. • %d compte(s) avant retrait." % [unit["name"], remaining])
	return resolved


func _apply_shield_block(target: Dictionary, damage: int) -> Dictionary:
	var result: Dictionary = {"damage": maxi(0, damage), "blocked": false, "reduction": 0}
	var chance: int = clampi(int(target.get("shield_block_chance", 0)), 0, 100)
	var reduction: int = maxi(0, int(target.get("shield_block_reduction", 0)))
	if damage <= 0 or chance <= 0 or reduction <= 0:
		return result
	if battle_rng.randi_range(1, 100) > chance:
		return result
	result["blocked"] = true
	result["reduction"] = mini(damage, reduction)
	result["damage"] = maxi(0, damage - reduction)
	return result


func apply_damage(target: Dictionary, amount: int) -> void:
	var was_alive := int(target["hp"]) > 0
	target["hp"] = max(0, int(target["hp"]) - amount)
	_interrupt_cast_if_needed(target, amount)
	# A zero-damage hit can still consume one-hit statuses such as GARDE/BALISÉ.
	StatusCatalog.remove_on_damage_taken(target)
	if str(target.get("template_id", target["id"])) == "archiviste" and int(target["hp"]) > 0:
		update_archivist_phase(target)
	if was_alive and int(target["hp"]) <= 0:
		_enter_downed(target)
		ko_fx[String(target["id"])] = animation_time + 0.65
	if was_alive and int(target["hp"]) <= 0 and target["id"] == crown_carrier_id:
		crown_carrier_id = ""
		crown_cell = target["pos"]
		log_message("La COURONNE tombe en (%d,%d) !" % [crown_cell.x + 1, crown_cell.y + 1])


func update_archivist_phase(boss: Dictionary) -> void:
	var phase := int(boss.get("boss_phase", 1))
	if int(boss["hp"]) <= 10 and phase < 2:
		boss["boss_phase"] = 2
		boss["move"] = int(boss["move"]) + 1
		add_status(boss, "guarded")
		spawn_particles(boss["pos"], VIOLET, 18)
		log_message("BOSS — PHASE 2 : L'Archiviste ouvre ses rayonnages vivants. +1 MVT et GARDE.")
		phase = 2
	if int(boss["hp"]) <= 5 and phase < 3:
		boss["boss_phase"] = 3
		boss["attack"] = int(boss["attack"]) + 1
		boss["physical_power"] = int(boss.get("physical_power", boss["attack"] - 1)) + 1
		boss["range"] = int(boss["range"]) + 1
		boss["attack_max_range"] = int(boss.get("attack_max_range", boss["range"] - 1)) + 1
		boss["focus"] = int(boss.get("max_focus", 2))
		spawn_particles(boss["pos"], GOLD, 22)
		log_message("BOSS — PHASE 3 : INDEX INTERDIT. +1 ATQ, +1 portée, Focus restauré.")


func closest_enemy_in_range(source: Dictionary, range_value: int) -> Dictionary:
	var best: Dictionary = {}
	var best_distance := 999
	for unit in units:
		if unit["team"] == "enemy" and int(unit["hp"]) > 0:
			var distance := manhattan(source["pos"], unit["pos"])
			if distance <= range_value and distance < best_distance:
				best = unit
				best_distance = distance
	return best


func enemies_in_radius(center: Vector2i, radius: int) -> Array:
	var result: Array = []
	for unit in units:
		if (
			unit["team"] == "enemy"
			and int(unit["hp"]) > 0
			and manhattan(center, unit["pos"]) <= radius
		):
			result.append(unit)
	return result


func most_injured_ally() -> Dictionary:
	var best: Dictionary = {}
	var lowest_ratio := 1.1
	for unit in units:
		if (
			unit["team"] != "player"
			or int(unit["hp"]) <= 0
			or int(unit["hp"]) >= int(unit["max_hp"])
		):
			continue
		var ratio := float(unit["hp"]) / float(unit["max_hp"])
		if ratio < lowest_ratio:
			best = unit
			lowest_ratio = ratio
	return best


func first_available_player_id() -> String:
	for unit in units:
		if unit["team"] == "player" and int(unit["hp"]) > 0 and not unit["has_acted"]:
			return unit["id"]
	return ""


func manhattan(a: Vector2i, b: Vector2i) -> int:
	return BattleRules.manhattan(a, b)


func cell_to_world(cell: Vector2i) -> Vector2:
	return BOARD_ORIGIN + Vector2(float(cell.x) * cell_size, float(cell.y) * cell_size)


func world_to_cell(point: Vector2) -> Vector2i:
	var zoom: float = maxf(0.001, cinematic_camera_zoom)
	var untransformed: Vector2 = (point - cinematic_camera_offset) / zoom
	var local_point: Vector2 = untransformed - BOARD_ORIGIN
	return Vector2i(floor(local_point.x / cell_size), floor(local_point.y / cell_size))


func hover_path() -> Array:
	var unit := selected_unit()
	if unit.is_empty() or not move_cells.has(hovered_cell):
		return []
	var path: Array = [hovered_cell]
	var current := hovered_cell
	while current != unit["pos"]:
		if not move_parents.has(current):
			return []
		current = move_parents[current]
		path.push_front(current)
	return path


func movement_path_for(unit: Dictionary, destination: Vector2i) -> Array:
	var start: Vector2i = unit["pos"]
	if destination == start:
		return [start]
	var navigation := movement_data(unit)
	var parents: Dictionary = navigation["parents"]
	if not parents.has(destination):
		return [start, destination]
	var path: Array = [destination]
	var current := destination
	var safety := grid_width * grid_height + 2
	while current != start and safety > 0:
		if not parents.has(current):
			return [start, destination]
		current = parents[current]
		path.push_front(current)
		safety -= 1
	return path


func start_move_animation(unit_id: String, path: Array, step_duration: float = 0.11) -> void:
	if path.size() < 2:
		return
	visual_paths[unit_id] = {
		"path": path.duplicate(),
		"started": animation_time,
		"step_duration": step_duration,
		"duration": step_duration * float(path.size() - 1)
	}


func visual_center_for_cell(cell: Vector2i) -> Vector2:
	return (
		cell_to_world(cell)
		+ Vector2(cell_size * 0.5, cell_size * 0.5)
		+ Vector2(0.0, -float(terrain_height(cell) * 3))
	)


func unit_visual_center(unit: Dictionary) -> Vector2:
	var unit_id := str(unit["id"])
	if not visual_paths.has(unit_id):
		return visual_center_for_cell(unit["pos"])
	var fx: Dictionary = visual_paths[unit_id]
	var path: Array = fx["path"]
	if path.size() < 2:
		return visual_center_for_cell(unit["pos"])
	var step_duration: float = maxf(0.01, float(fx["step_duration"]))
	var step_value: float = maxf(0.0, animation_time - float(fx["started"])) / step_duration
	var segment_count := path.size() - 1
	if step_value >= float(segment_count):
		return visual_center_for_cell(path[path.size() - 1])
	var segment := clampi(int(floor(step_value)), 0, segment_count - 1)
	var local_progress := clampf(step_value - float(segment), 0.0, 1.0)
	local_progress = local_progress * local_progress * (3.0 - 2.0 * local_progress)
	var from_position := visual_center_for_cell(path[segment])
	var to_position := visual_center_for_cell(path[segment + 1])
	return from_position.lerp(to_position, local_progress)


func start_attack_dash(attacker: Dictionary, target: Dictionary, distance: float = 13.0) -> void:
	var attacker_pos: Vector2i = attacker["pos"]
	var target_pos: Vector2i = target["pos"]
	var direction := Vector2(
		float(target_pos.x - attacker_pos.x),
		float(target_pos.y - attacker_pos.y)
	).normalized()
	attack_fx[str(attacker["id"])] = {
		"started": animation_time,
		"duration": 0.22,
		"direction": direction,
		"distance": distance
	}


func attack_offset_for_unit(unit_id: String) -> Vector2:
	if not attack_fx.has(unit_id):
		return Vector2.ZERO
	var fx: Dictionary = attack_fx[unit_id]
	var progress := clampf(
		(animation_time - float(fx["started"])) / max(0.01, float(fx["duration"])), 0.0, 1.0
	)
	return fx["direction"] * sin(progress * PI) * float(fx["distance"])


func hit_flash_amount(unit_id: String) -> float:
	if not hit_fx.has(unit_id):
		return 0.0
	var remaining := float(hit_fx[unit_id]) - animation_time
	return clampf(remaining / 0.18, 0.0, 1.0)


func spawn_damage_feedback(
	attacker: Dictionary,
	target: Dictionary,
	amount: int,
	accent: Color = CORAL,
	vfx_id_override: String = "",
	emit_attack_vfx: bool = true
) -> void:
	if emit_attack_vfx:
		var visual := VisualCatalog.definition_for_unit(attacker)
		var attack_vfx_id := vfx_id_override
		if attack_vfx_id.is_empty() and visual != null:
			attack_vfx_id = String(visual.basic_attack_vfx_id)
		var vfx := VfxCatalog.definition(attack_vfx_id)
		if int(attacker["range"]) <= 1:
			start_attack_dash(attacker, target)
			if not attack_vfx_id.is_empty():
				spawn_visual_effect(attack_vfx_id, target["pos"], attacker["pos"], target["pos"])
		elif vfx != null and String(vfx.kind) == "projectile":
			spawn_visual_effect(attack_vfx_id, target["pos"], attacker["pos"], target["pos"])
		else:
			projectile_fx.append(
				{
					"from": visual_center_for_cell(attacker["pos"]),
					"to": visual_center_for_cell(target["pos"]),
					"started": animation_time,
					"duration": 0.24,
					"color": attacker["color"]
				}
			)
	spawn_impact_feedback(target, amount, accent, int(attacker["range"]) <= 1)


func spawn_impact_feedback(
	target: Dictionary, amount: int, accent: Color = CORAL, strong: bool = false
) -> void:
	hit_fx[str(target["id"])] = animation_time + 0.18
	spawn_floating_text(target["pos"], "-%d" % amount, accent)
	spawn_particles(target["pos"], accent, 9 if strong else 6)
	shake_strength = max(shake_strength, 5.0 if strong else 2.5)
	play_feedback_tone("heavy" if strong else "hit")


func spawn_floating_text(cell: Vector2i, value: String, color: Color) -> void:
	floating_text_fx.append(
		{
			"position": visual_center_for_cell(cell) + Vector2(0.0, -24.0),
			"text": value,
			"color": color,
			"started": animation_time,
			"duration": 0.72
		}
	)


func spawn_particles(cell: Vector2i, color: Color, count: int) -> void:
	var origin := visual_center_for_cell(cell)
	for index in range(count):
		var angle: float = float(index) * TAU / float(maxi(1, count)) + float(cell.x + cell.y) * 0.31
		var speed := 30.0 + float((index * 17) % 42)
		particle_fx.append(
			{
				"origin": origin,
				"velocity": Vector2(cos(angle), sin(angle)) * speed,
				"color": color,
				"started": animation_time,
				"duration": 0.55,
				"radius": 2.0 + float(index % 3)
			}
		)


func prune_presentation_fx() -> void:
	for unit_id in visual_paths.keys():
		var fx: Dictionary = visual_paths[unit_id]
		if animation_time - float(fx["started"]) >= float(fx["duration"]):
			visual_paths.erase(unit_id)
	for unit_id in attack_fx.keys():
		var fx: Dictionary = attack_fx[unit_id]
		if animation_time - float(fx["started"]) >= float(fx["duration"]):
			attack_fx.erase(unit_id)
	for unit_id in hit_fx.keys():
		if animation_time >= float(hit_fx[unit_id]):
			hit_fx.erase(unit_id)
	for unit_id in ko_fx.keys():
		if animation_time >= float(ko_fx[unit_id]):
			ko_fx.erase(unit_id)
	prune_fx_array(floating_text_fx)
	prune_fx_array(projectile_fx)
	prune_fx_array(particle_fx)
	prune_fx_array(custom_vfx)


func prune_fx_array(fx_array: Array) -> void:
	for index in range(fx_array.size() - 1, -1, -1):
		var fx: Dictionary = fx_array[index]
		if animation_time - float(fx["started"]) >= float(fx["duration"]):
			fx_array.remove_at(index)


func battlefield_shake_offset() -> Vector2:
	if shake_strength <= 0.01:
		return Vector2.ZERO
	return Vector2(
		sin(animation_time * 91.0) * shake_strength,
		cos(animation_time * 77.0) * shake_strength * 0.65
	)


func _texture_from_path(path: String) -> Texture2D:
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	if visual_texture_cache.has(path):
		return visual_texture_cache[path]
	var loaded = load(path)
	if loaded is Texture2D:
		visual_texture_cache[path] = loaded
		return loaded
	return null


func spawn_visual_effect(
	vfx_id: String,
	cell: Vector2i,
	from_cell: Vector2i = Vector2i(-999, -999),
	to_cell: Vector2i = Vector2i(-999, -999)
) -> void:
	var data := VfxCatalog.definition(vfx_id)
	if data == null:
		return
	var position := visual_center_for_cell(cell)
	var from_position := position if from_cell.x < -100 else visual_center_for_cell(from_cell)
	var to_position := position if to_cell.x < -100 else visual_center_for_cell(to_cell)
	custom_vfx.append({
		"id": vfx_id,
		"position": position,
		"from": from_position,
		"to": to_position,
		"started": animation_time,
		"duration": max(0.05, float(data.duration)),
	})
	shake_strength = max(shake_strength, float(data.shake_strength))
	if int(data.particle_count) > 0:
		spawn_particles(cell, data.primary_color, int(data.particle_count))


func _draw_vfx_texture(data: Resource, center: Vector2, age: float) -> void:
	var texture := _texture_from_path(String(data.texture_path))
	if texture == null:
		return
	var fw := int(data.frame_width)
	var fh := int(data.frame_height)
	if fw <= 0 or fh <= 0:
		fw = int(texture.get_size().x)
		fh = int(texture.get_size().y)
	var per_row: int = maxi(1, int(texture.get_size().x) / maxi(1, fw))
	var frame := int(data.frame_index(age))
	var source := Rect2((frame % per_row) * fw, int(frame / per_row) * fh, fw, fh)
	var draw_size := Vector2(fw, fh) * float(data.texture_scale)
	var dest := Rect2(center - draw_size * 0.5, draw_size)
	draw_texture_rect_region(texture, dest, source, Color.WHITE)


func draw_custom_visual_fx() -> void:
	for fx_value in custom_vfx:
		var fx: Dictionary = fx_value
		var data := VfxCatalog.definition(String(fx.get("id", "")))
		if data == null:
			continue
		var age: float = maxf(0.0, animation_time - float(fx["started"]))
		var duration: float = maxf(0.05, float(fx["duration"]))
		var progress: float = clampf(age / duration, 0.0, 1.0)
		var primary: Color = data.primary_color
		var secondary: Color = data.secondary_color
		var radius := float(data.radius)
		var center: Vector2 = fx["position"]
		match String(data.kind):
			"projectile":
				var from: Vector2 = fx["from"]
				var to: Vector2 = fx["to"]
				center = from.lerp(to, 1.0 - pow(1.0 - progress, 2.0))
				var trail_start: Vector2 = from.lerp(to, maxf(0.0, progress - 0.2))
				draw_line(trail_start, center, Color(primary.r, primary.g, primary.b, 0.55), float(data.trail_width), true)
				draw_circle(center, 6.0, primary)
				draw_circle(center, 2.5, secondary)
			"aura":
				draw_arc(center, radius + sin(progress * TAU) * 4.0, 0.0, TAU, 36, Color(primary.r, primary.g, primary.b, 0.75 * (1.0 - progress * 0.4)), 4.0, true)
			"ring":
				draw_arc(center, radius * (0.45 + progress * 0.75), 0.0, TAU, 40, Color(primary.r, primary.g, primary.b, 1.0 - progress), 4.0, true)
			"cross":
				var extent := radius * (0.45 + progress * 0.55)
				draw_line(center - Vector2(extent, 0), center + Vector2(extent, 0), Color(primary.r, primary.g, primary.b, 1.0 - progress * 0.5), 6.0, true)
				draw_line(center - Vector2(0, extent), center + Vector2(0, extent), Color(secondary.r, secondary.g, secondary.b, 1.0 - progress * 0.5), 4.0, true)
			"slash":
				var angle := -1.0 + progress * 2.0
				draw_arc(center, radius, angle - 0.55, angle + 0.55, 14, Color(primary.r, primary.g, primary.b, 1.0 - progress), 6.0, true)
			_:
				draw_circle(center, radius * (0.35 + progress * 0.75), Color(primary.r, primary.g, primary.b, 0.38 * (1.0 - progress)))
				draw_arc(center, radius * (0.45 + progress * 0.65), 0.0, TAU, 32, Color(primary.r, primary.g, primary.b, 1.0 - progress), 3.0, true)
		_draw_vfx_texture(data, center, age)


func draw_presentation_fx() -> void:
	draw_custom_visual_fx()
	for fx_value in projectile_fx:
		var fx: Dictionary = fx_value
		var progress := clampf(
			(animation_time - float(fx["started"])) / max(0.01, float(fx["duration"])), 0.0, 1.0
		)
		var eased := 1.0 - pow(1.0 - progress, 2.0)
		var start: Vector2 = fx["from"]
		var finish: Vector2 = fx["to"]
		var current := start.lerp(finish, eased)
		var trail_start: Vector2 = start.lerp(finish, maxf(0.0, eased - 0.18))
		var color: Color = fx["color"]
		draw_line(trail_start, current, Color(color.r, color.g, color.b, 0.55), 5.0, true)
		draw_circle(current, 6.0, color)
		draw_circle(current, 2.5, Color.WHITE)
	for fx_value in particle_fx:
		var fx: Dictionary = fx_value
		var age: float = maxf(0.0, animation_time - float(fx["started"]))
		var duration: float = maxf(0.01, float(fx["duration"]))
		var progress: float = clampf(age / duration, 0.0, 1.0)
		var position: Vector2 = fx["origin"] + fx["velocity"] * age + Vector2(0.0, 55.0 * age * age)
		var color: Color = fx["color"]
		color.a = 1.0 - progress
		draw_circle(position, float(fx["radius"]) * (1.0 - progress * 0.35), color)
	for fx_value in floating_text_fx:
		var fx: Dictionary = fx_value
		var age: float = maxf(0.0, animation_time - float(fx["started"]))
		var duration: float = maxf(0.01, float(fx["duration"]))
		var progress: float = clampf(age / duration, 0.0, 1.0)
		var color: Color = fx["color"]
		color.a = 1.0 - progress
		var position: Vector2 = fx["position"] + Vector2(0.0, -34.0 * progress)
		draw_string(
			ThemeDB.fallback_font,
			position,
			str(fx["text"]),
			HORIZONTAL_ALIGNMENT_CENTER,
			46.0,
			18,
			color
		)


func play_feedback_tone(kind: String) -> void:
	if not sound_enabled:
		return
	var frequency := 330.0
	var duration := 0.055
	var volume := 0.12
	match kind:
		"move":
			frequency = 235.0
			duration = 0.025
			volume = 0.035
		"heal":
			frequency = 660.0
			duration = 0.11
			volume = 0.07
		"heavy":
			frequency = 115.0
			duration = 0.09
			volume = 0.11
		"hit":
			frequency = 175.0
			duration = 0.055
			volume = 0.08
	var stream := make_tone_stream(frequency, duration, volume)
	if stream == null:
		return
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.volume_db = -4.0
	add_child(player)
	player.finished.connect(Callable(player, "queue_free"))
	player.play()


func make_tone_stream(frequency: float, duration: float, volume: float) -> AudioStreamWAV:
	var mix_rate: int = 22050
	var sample_count: int = maxi(1, int(float(mix_rate) * duration))
	var bytes := PackedByteArray()
	bytes.resize(sample_count * 2)
	for sample_index in range(sample_count):
		var t := float(sample_index) / float(mix_rate)
		var envelope := 1.0 - float(sample_index) / float(sample_count)
		var value := int(sin(TAU * frequency * t) * 32767.0 * volume * envelope)
		bytes.encode_s16(sample_index * 2, clampi(value, -32768, 32767))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = mix_rate
	stream.stereo = false
	stream.data = bytes
	return stream


func _draw() -> void:
	var viewport_size := get_viewport_rect().size
	draw_rect(Rect2(Vector2.ZERO, viewport_size), BG, true)

	for index in range(14):
		var x := 18.0 + float((index * 113) % 1260)
		var y := 18.0 + float((index * 67) % 735)
		var radius := 2.0 + float(index % 3)
		draw_circle(Vector2(x, y), radius, Color(0.45, 0.82, 0.72, 0.12))

	draw_set_transform(cinematic_camera_offset + battlefield_shake_offset(), 0.0, Vector2.ONE * cinematic_camera_zoom)
	var board_size := Vector2(float(grid_width) * cell_size, float(grid_height) * cell_size)
	draw_rect(
		Rect2(BOARD_ORIGIN - Vector2(10.0, 10.0), board_size + Vector2(20.0, 20.0)),
		Color("#0a111e"),
		true
	)
	draw_rect(
		Rect2(BOARD_ORIGIN - Vector2(5.0, 5.0), board_size + Vector2(10.0, 10.0)),
		Color("#496879"),
		true
	)

	for y in range(grid_height):
		for x in range(grid_width):
			var cell := Vector2i(x, y)
			var rect := Rect2(cell_to_world(cell), Vector2(cell_size - 1.0, cell_size - 1.0))
			var fill := GRID_A if (x + y) % 2 == 0 else GRID_B
			if terrain_height(cell) > 0:
				fill = fill.lerp(Color("#668197"), 0.11 * float(terrain_height(cell)))
			draw_rect(rect, fill, true)
			draw_rect(rect, GRID_LINE, false, 1.0)
			if move_cells.has(cell):
				draw_rect(rect, MOVE_HIGHLIGHT, true)
				draw_string(
					ThemeDB.fallback_font,
					rect.position + Vector2(7.0, 17.0),
					str(move_costs.get(cell, 0)),
					HORIZONTAL_ALIGNMENT_LEFT,
					-1.0,
					11,
					MINT
				)
			if attack_cells.has(cell):
				draw_rect(rect, ATTACK_HIGHLIGHT, true)
			if hovered_cell == cell and is_inside(cell):
				draw_rect(rect, HOVER_HIGHLIGHT, true)
			draw_terrain_details(cell, rect)

	_draw_interactables()
	draw_hover_path()
	draw_special_telegraph()
	draw_targeting_preview()

	for obstacle in obstacles:
		draw_obstacle(obstacle)

	if mission_objective == "crown" and crown_carrier_id.is_empty():
		draw_crown(crown_cell)
	for bonus_cell in bonus_cells:
		draw_bonus_vinyl(bonus_cell)

	for unit in units:
		if _unit_is_battle_present(unit) or ko_fx.has(String(unit["id"])):
			draw_unit(unit)
	draw_presentation_fx()
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	if game_over and not event_sequence_running:
		var banner_color := (
			Color(0.145, 0.294, 0.271, 0.94)
			if mission_victory
			else Color(0.357, 0.188, 0.220, 0.94)
		)
		draw_rect(
			Rect2(BOARD_ORIGIN + Vector2(95.0, 232.0), Vector2(510.0, 92.0)), banner_color, true
		)
		var banner := "MISSION RÉUSSIE !" if mission_victory else "MISSION ÉCHOUÉE !"
		draw_string(
			ThemeDB.fallback_font,
			BOARD_ORIGIN + Vector2(250.0, 290.0),
			banner,
			HORIZONTAL_ALIGNMENT_CENTER,
			200.0,
			30,
			TEXT
		)


func draw_terrain_details(cell: Vector2i, rect: Rect2) -> void:
	if extraction_cells.has(cell):
		draw_rect(rect.grow(-4.0), Color(EXTRACTION.r, EXTRACTION.g, EXTRACTION.b, 0.13), true)
		draw_rect(rect.grow(-5.0), EXTRACTION, false, 2.0)
		draw_string(ThemeDB.fallback_font, rect.position + Vector2(7.0, 63.0), "SORTIE", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 9, EXTRACTION)
	if hazard_cells.has(cell):
		for index in range(4):
			var offset := Vector2(14.0 + float((index * 13) % 43), 22.0 + float((index * 17) % 31))
			draw_circle(rect.position + offset, 8.0 + float(index % 2) * 3.0, Color(HAZARD.r, HAZARD.g, HAZARD.b, 0.38))
			draw_circle(rect.position + offset + Vector2(2.0, -2.0), 2.0, Color(0.92, 0.78, 1.0, 0.65))
	var height := terrain_height(cell)
	if height > 0:
		draw_rect(
			Rect2(rect.position + Vector2(5.0, 5.0), rect.size - Vector2(10.0, 10.0)),
			Color(0.65, 0.82, 0.92, 0.10),
			false,
			2.0
		)
		draw_string(
			ThemeDB.fallback_font,
			rect.position + Vector2(47.0, 18.0),
			"▲%d" % height,
			HORIZONTAL_ALIGNMENT_LEFT,
			-1.0,
			11,
			SKY
		)
	if cover_cells.has(cell):
		var base := rect.position + Vector2(12.0, 57.0)
		for index in range(3):
			var leaf_position := base + Vector2(float(index * 12), -float((index % 2) * 5))
			draw_circle(leaf_position, 7.0, Color("#477d69"))
			draw_circle(leaf_position + Vector2(5.0, -2.0), 5.0, Color("#70a36f"))


func draw_hover_path() -> void:
	var path := hover_path()
	if path.size() < 2:
		return
	for index in range(path.size() - 1):
		var from_position := cell_to_world(path[index]) + Vector2(cell_size * 0.5, cell_size * 0.5)
		var to_position := (
			cell_to_world(path[index + 1]) + Vector2(cell_size * 0.5, cell_size * 0.5)
		)
		draw_line(from_position, to_position, Color(1.0, 0.82, 0.35, 0.80), 4.0, true)
		draw_circle(to_position, 4.0, GOLD)


func draw_special_telegraph() -> void:
	if not special_targeting:
		return
	for cell in special_target_cells:
		var rect := Rect2(cell_to_world(cell) + Vector2(4.0, 4.0), Vector2(cell_size - 9.0, cell_size - 9.0))
		draw_rect(rect, Color(VIOLET.r, VIOLET.g, VIOLET.b, 0.10), true)
	if special_target_cells.has(hovered_cell):
		for cell in _skill_area_preview_cells(hovered_cell, special_target_skill_id):
			var rect := Rect2(cell_to_world(cell) + Vector2(5.0, 5.0), Vector2(cell_size - 11.0, cell_size - 11.0))
			draw_rect(rect, Color(VIOLET.r, VIOLET.g, VIOLET.b, 0.30), true)
			draw_rect(rect, VIOLET, false, 2.0)


func _skill_area_preview_cells(center: Vector2i, skill_id: String) -> Array:
	var cells: Array = []
	var seen: Dictionary = {}
	var source: Dictionary = selected_unit()
	var source_cell: Vector2i = center
	if not source.is_empty():
		var source_position_value: Variant = source.get("pos", center)
		if source_position_value is Vector2i:
			source_cell = source_position_value
	for effect in SkillCatalog.effects(skill_id):
		if effect == null:
			continue
		var radius := int(effect.radius)
		var shape := String(effect.area_shape)
		for y in range(grid_height):
			for x in range(grid_width):
				var cell := Vector2i(x, y)
				if _cell_in_effect_area(cell, center, radius, shape, source_cell) and not seen.has(cell):
					seen[cell] = true
					cells.append(cell)
	if cells.is_empty():
		cells.append(center)
	return cells


func draw_bonus_vinyl(cell: Vector2i) -> void:
	var center := cell_to_world(cell) + Vector2(cell_size * 0.5, cell_size * 0.5)
	var pulse := 1.0 + sin(animation_time * 4.5 + float(cell.x)) * 0.06
	draw_circle(center, 17.0 * pulse, Color(0.08, 0.08, 0.11, 0.95))
	draw_circle(center, 9.0 * pulse, VIOLET)
	draw_circle(center, 3.0, GOLD)
	draw_arc(center, 21.0, 0.0, TAU, 24, Color(VIOLET.r, VIOLET.g, VIOLET.b, 0.45), 2.0, true)
	draw_string(ThemeDB.fallback_font, center + Vector2(-20.0, 31.0), "VINYLE", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 9, GOLD)


func draw_targeting_preview() -> void:
	var attacker := selected_unit()
	var target := unit_at(hovered_cell)
	if attacker.is_empty() or target.is_empty() or target["team"] != "enemy":
		return
	if manhattan(attacker["pos"], target["pos"]) > effective_range(attacker):
		return
	var start := cell_to_world(attacker["pos"]) + Vector2(cell_size * 0.5, cell_size * 0.5)
	var finish := cell_to_world(target["pos"]) + Vector2(cell_size * 0.5, cell_size * 0.5)
	var clear := can_attack(attacker, target)
	var line_color := MINT if clear else CORAL
	draw_line(start, finish, Color(line_color.r, line_color.g, line_color.b, 0.68), 3.0, true)


func draw_crown(cell: Vector2i) -> void:
	var center := cell_to_world(cell) + Vector2(cell_size * 0.5, cell_size * 0.5)
	draw_circle(center, 20.0 + sin(animation_time * 4.0) * 2.0, Color(CROWN.r, CROWN.g, CROWN.b, 0.17))
	var points := PackedVector2Array([
		center + Vector2(-18.0, 8.0), center + Vector2(-15.0, -10.0), center + Vector2(-5.0, 0.0),
		center + Vector2(0.0, -15.0), center + Vector2(7.0, 0.0), center + Vector2(16.0, -10.0),
		center + Vector2(18.0, 8.0)
	])
	draw_polyline(points, CROWN, 4.0, true)
	draw_line(center + Vector2(-18.0, 8.0), center + Vector2(18.0, 8.0), CROWN, 4.0, true)
	draw_string(ThemeDB.fallback_font, center + Vector2(-8.0, 29.0), "♛", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 18, CROWN)


func draw_obstacle(cell: Vector2i) -> void:
	var rect := Rect2(
		cell_to_world(cell) + Vector2(8.0, 8.0), Vector2(cell_size - 17.0, cell_size - 17.0)
	)
	draw_rect(rect, Color("#1b2b3d"), true)
	var center := rect.position + rect.size * 0.5
	draw_circle(center + Vector2(-13.0, 8.0), 13.0, Color("#56726f"))
	draw_circle(center + Vector2(12.0, 7.0), 16.0, Color("#6f8c7b"))
	draw_circle(center + Vector2(0.0, -9.0), 19.0, Color("#9ab58d"))
	draw_circle(center + Vector2(-6.0, -13.0), 3.0, Color("#dce8bc"))
	draw_circle(center + Vector2(7.0, -8.0), 3.0, Color("#dce8bc"))


func _unit_visual_state(unit: Dictionary) -> String:
	var unit_id := String(unit.get("id", ""))
	if int(unit.get("hp", 0)) <= 0:
		return "ko"
	if hit_fx.has(unit_id):
		return "hit"
	if attack_fx.has(unit_id):
		return "attack"
	if visual_paths.has(unit_id):
		return "move"
	return "idle"


func _unit_visual_elapsed(unit: Dictionary, state: String) -> float:
	var unit_id := String(unit.get("id", ""))
	match state:
		"ko":
			if _unit_is_downed(unit) and not ko_fx.has(unit_id):
				return 99.0
			return max(0.0, animation_time - (float(ko_fx.get(unit_id, animation_time)) - 0.65))
		"hit":
			return max(0.0, animation_time - (float(hit_fx.get(unit_id, animation_time)) - 0.18))
		"attack":
			var attack_data: Dictionary = attack_fx.get(unit_id, {})
			return max(0.0, animation_time - float(attack_data.get("started", animation_time)))
		"move":
			var move_data: Dictionary = visual_paths.get(unit_id, {})
			return max(0.0, animation_time - float(move_data.get("started", animation_time)))
		_:
			return animation_time


func _draw_unit_sprite(visual: Resource, unit: Dictionary, center: Vector2, flash: float) -> bool:
	if visual == null or not bool(visual.use_sprite_sheet):
		return false
	var texture := _texture_from_path(String(visual.sprite_sheet_path))
	if texture == null:
		return false
	var fw := int(visual.frame_width)
	var fh := int(visual.frame_height)
	if fw <= 0 or fh <= 0:
		fw = int(texture.get_size().x)
		fh = int(texture.get_size().y)
	var per_row: int = maxi(1, int(texture.get_size().x) / maxi(1, fw))
	var state := _unit_visual_state(unit)
	var frame := int(visual.frame_index(state, _unit_visual_elapsed(unit, state)))
	var source := Rect2((frame % per_row) * fw, int(frame / per_row) * fh, fw, fh)
	var draw_size := Vector2(fw, fh) * float(visual.sprite_scale)
	var dest := Rect2(center - draw_size * 0.5 + Vector2(visual.sprite_offset), draw_size)
	var sprite_modulate: Color = visual.primary_color if bool(visual.tint_sprite_with_primary) else Color.WHITE
	if flash > 0.0:
		sprite_modulate = sprite_modulate.lerp(Color.WHITE, flash * 0.75)
	draw_circle(center + Vector2(0, 24), min(24.0, draw_size.x * 0.28), Color(0.02, 0.03, 0.05, 0.35))
	draw_texture_rect_region(texture, dest, source, sprite_modulate)
	return true


func _draw_procedural_unit(visual: Resource, unit: Dictionary, center: Vector2, unit_color: Color, is_player: bool) -> void:
	var primary := unit_color
	var secondary := Color("#f3e5c0")
	var accent := GOLD
	var outline := Color("#251c32")
	var shape := "mushroom"
	if visual != null:
		primary = visual.primary_color.lerp(Color.WHITE, hit_flash_amount(String(unit["id"])) * 0.78)
		secondary = visual.secondary_color
		accent = visual.accent_color
		outline = visual.outline_color
		shape = String(visual.fallback_shape)
	match shape:
		"slime":
			draw_circle(center + Vector2(0, 11), 28, outline)
			draw_circle(center + Vector2(0, 9), 24, primary)
			draw_circle(center + Vector2(-8, 2), 4, secondary)
			draw_circle(center + Vector2(8, 2), 4, secondary)
			draw_circle(center + Vector2(-7, 3), 2.5, outline)
			draw_circle(center + Vector2(7, 3), 2.5, outline)
		"armored":
			draw_rect(Rect2(center + Vector2(-20, -9), Vector2(40, 38)), outline, true)
			draw_rect(Rect2(center + Vector2(-17, -6), Vector2(34, 33)), primary, true)
			draw_circle(center + Vector2(0, -10), 23, outline)
			draw_circle(center + Vector2(0, -12), 19, secondary)
			draw_line(center + Vector2(-18, 3), center + Vector2(18, 3), accent, 4)
		"orb":
			draw_circle(center, 31 + sin(animation_time * 3.0) * 2.0, Color(primary.r, primary.g, primary.b, 0.16))
			draw_circle(center, 24, outline)
			draw_circle(center, 20, primary)
			draw_circle(center + Vector2(-7, -5), 4, secondary)
			draw_circle(center + Vector2(7, -5), 4, secondary)
			draw_circle(center + Vector2(-6, -4), 2.5, outline)
			draw_circle(center + Vector2(6, -4), 2.5, outline)
		_:
			draw_rect(Rect2(center + Vector2(-13.0, 3.0), Vector2(26.0, 24.0)), secondary, true)
			draw_circle(center + Vector2(0.0, 26.0), 13.0, secondary)
			draw_circle(center + Vector2(0.0, -3.0), 25.0, outline)
			draw_circle(center + Vector2(0.0, -7.0), 22.0, primary)
			draw_circle(center + Vector2(-8.0, -11.0), 4.0, Color(1.0, 1.0, 1.0, 0.7))
			draw_circle(center + Vector2(8.0, -11.0), 4.0, Color(1.0, 1.0, 1.0, 0.7))
			draw_circle(center + Vector2(-7.0, -4.0), 3.0, outline)
			draw_circle(center + Vector2(7.0, -4.0), 3.0, outline)
			draw_arc(center + Vector2(0.0, 1.0), 7.0, 0.15, PI - 0.15, 12, outline, 2.0, true)
	if String(unit.get("template_id", unit["id"])) == "ziggy":
		draw_arc(center + Vector2(20.0, -17.0), 5.0, 0.0, TAU, 10, accent, 2.0, true)
	elif String(unit.get("template_id", unit["id"])) == "pipo":
		draw_line(center + Vector2(19.0, -26.0), center + Vector2(19.0, -14.0), Color.WHITE, 3.0, true)
		draw_line(center + Vector2(13.0, -20.0), center + Vector2(25.0, -20.0), Color.WHITE, 3.0, true)
	elif String(unit.get("template_id", unit["id"])) == "luma":
		draw_circle(center + Vector2(20.0, -20.0), 8.0, Color(0.45, 0.85, 1.0, 0.28))
		draw_line(center + Vector2(14.0, -20.0), center + Vector2(26.0, -20.0), SKY, 2.0, true)
		draw_line(center + Vector2(20.0, -26.0), center + Vector2(20.0, -14.0), SKY, 2.0, true)
	if shape != "orb":
		if is_player:
			draw_line(center + Vector2(-17.0, 18.0), center + Vector2(-29.0, 8.0), primary, 4.0, true)
			draw_line(center + Vector2(17.0, 18.0), center + Vector2(29.0, 8.0), primary, 4.0, true)
		else:
			draw_line(center + Vector2(-18.0, 18.0), center + Vector2(-27.0, 25.0), primary, 4.0, true)
			draw_line(center + Vector2(18.0, 18.0), center + Vector2(27.0, 25.0), primary, 4.0, true)


func _draw_status_visual_aura(unit: Dictionary, center: Vector2) -> void:
	var aura_index := 0
	for status_id in StatusCatalog.active_ids(unit):
		var vfx_id := StatusCatalog.vfx_id(String(status_id))
		var data := VfxCatalog.definition(vfx_id)
		if data == null or String(data.kind) not in ["aura", "ring"]:
			continue
		var color: Color = data.primary_color
		var radius := 29.0 + float(aura_index) * 4.0 + sin(animation_time * 3.0 + aura_index) * 1.5
		draw_arc(center, radius, 0.0, TAU, 32, Color(color.r, color.g, color.b, 0.32), 2.0, true)
		aura_index += 1
		if aura_index >= 2:
			break


func draw_unit(unit: Dictionary) -> void:
	var cell: Vector2i = unit["pos"]
	var center := unit_visual_center(unit) + attack_offset_for_unit(str(unit["id"]))
	var bob := sin(animation_time * 3.0 + float(cell.x)) * 1.5
	center.y += bob
	var unit_color: Color = unit["color"]
	var flash := hit_flash_amount(str(unit["id"]))
	if flash > 0.0:
		unit_color = unit_color.lerp(Color.WHITE, flash * 0.78)
	var is_player: bool = String(unit["team"]) == "player"
	var selected: bool = String(unit["id"]) == selected_id
	var visual := VisualCatalog.definition_for_unit(unit)
	_draw_status_visual_aura(unit, center)

	if str(unit.get("template_id", unit["id"])) == "archiviste":
		var phase := int(unit.get("boss_phase", 1))
		if phase >= 2:
			draw_arc(center, 34.0 + sin(animation_time * 3.0) * 2.0, 0.0, TAU, 32, VIOLET, 3.0, true)
		if phase >= 3:
			draw_arc(center, 39.0 + cos(animation_time * 4.0) * 2.0, 0.0, TAU, 32, GOLD, 2.0, true)

	if selected or unit["id"] == active_unit_id:
		draw_arc(center + Vector2(0.0, 2.0), 29.0, 0.0, TAU, 32, GOLD, 3.0, true)
	if unit["has_acted"] and is_player:
		draw_circle(center + Vector2(25.0, -25.0), 7.0, Color("#64788a"))
	if String(unit.get("reaction_type", "none")) != "none" and _reaction_available(unit):
		draw_arc(center, 31.0, -0.55, 0.55, 10, Color(GOLD.r, GOLD.g, GOLD.b, 0.55), 2.0, true)

	var facing: Vector2i = unit.get("facing", Vector2i(0, 1))
	var facing_vector := Vector2(float(facing.x), float(facing.y))
	var arrow_start := center + facing_vector * 28.0
	var arrow_end := center + facing_vector * 35.0
	draw_line(arrow_start, arrow_end, GOLD, 3.0, true)
	draw_circle(arrow_end, 3.5, GOLD)

	var used_sprite := _draw_unit_sprite(visual, unit, center, flash)
	if not used_sprite:
		_draw_procedural_unit(visual, unit, center, unit_color, is_player)

	var status_ids := StatusCatalog.active_ids(unit)
	for status_index in range(min(4, status_ids.size())):
		var status_id := String(status_ids[status_index])
		var status_def := StatusCatalog.definition(status_id)
		var status_color: Color = status_def.color if status_def != null else VIOLET
		var status_label_short := status_id.substr(0, 1).to_upper()
		if status_def != null and not String(status_def.display_name).is_empty():
			status_label_short = String(status_def.display_name).substr(0, 1).to_upper()
		var status_pos := center + Vector2(-25.0 + float(status_index % 2) * 16.0, -28.0 + float(status_index / 2) * 16.0)
		draw_circle(status_pos, 7.0, status_color)
		draw_string(ThemeDB.fallback_font, status_pos + Vector2(-3.5, 3.5), status_label_short, HORIZONTAL_ALIGNMENT_LEFT, -1.0, 9, BG)

	if unit["id"] == crown_carrier_id:
		var crown_center := center + Vector2(0.0, -42.0)
		draw_line(crown_center + Vector2(-9.0, 5.0), crown_center + Vector2(-7.0, -5.0), CROWN, 2.0, true)
		draw_line(crown_center + Vector2(-7.0, -5.0), crown_center, CROWN, 2.0, true)
		draw_line(crown_center, crown_center + Vector2(6.0, -5.0), CROWN, 2.0, true)
		draw_line(crown_center + Vector2(6.0, -5.0), crown_center + Vector2(9.0, 5.0), CROWN, 2.0, true)
		draw_line(crown_center + Vector2(-9.0, 5.0), crown_center + Vector2(9.0, 5.0), CROWN, 2.0, true)

	if _unit_is_downed(unit):
		draw_string(ThemeDB.fallback_font, center + Vector2(-24.0, -38.0), "K.O. %d" % int(unit.get("downed_countdown", 0)), HORIZONTAL_ALIGNMENT_CENTER, 48.0, 12, CORAL)

	if is_player:
		for focus_index in range(int(unit.get("max_focus", 2))):
			var pip_color := GOLD if focus_index < int(unit.get("focus", 0)) else Color(0.25, 0.31, 0.39, 0.8)
			draw_circle(center + Vector2(-8.0 + focus_index * 8.0, 34.0), 2.8, pip_color)

	var bar_position := center + Vector2(-27.0, 38.0)
	draw_rect(Rect2(bar_position, Vector2(54.0, 6.0)), Color("#111722"), true)
	var hp_ratio := float(unit["hp"]) / float(unit["max_hp"])
	var hp_color := MINT if is_player else CORAL
	draw_rect(Rect2(bar_position, Vector2(54.0 * hp_ratio, 6.0)), hp_color, true)
	draw_string(
		ThemeDB.fallback_font,
		center + Vector2(-33.0, 57.0),
		str(unit["name"]),
		HORIZONTAL_ALIGNMENT_CENTER,
		66.0,
		11,
		TEXT
	)
