@tool
class_name SporeboundStudioDock
extends VBoxContainer

const MapCanvas = preload("res://addons/sporebound_studio/map_canvas.gd")
const MissionDefinition = preload("res://scripts/data/mission_definition.gd")
const UnitDefinition = preload("res://scripts/data/unit_definition.gd")
const SkillDefinition = preload("res://scripts/data/skill_definition.gd")
const SkillEffect = preload("res://scripts/data/skill_effect.gd")
const StatusDefinition = preload("res://scripts/data/status_definition.gd")
const CampaignDefinition = preload("res://scripts/data/campaign_definition.gd")
const CampaignNodeDefinition = preload("res://scripts/data/campaign_node_definition.gd")
const CampaignCanvas = preload("res://addons/sporebound_studio/campaign_canvas.gd")
const AIProfileDefinition = preload("res://scripts/data/ai_profile_definition.gd")
const MissionRule = preload("res://scripts/data/mission_rule.gd")
const BattleTriggerDefinition = preload("res://scripts/data/battle_trigger_definition.gd")
const BattleActionDefinition = preload("res://scripts/data/battle_action_definition.gd")
const MapInteractableDefinition = preload("res://scripts/data/map_interactable_definition.gd")
const CinematicEditor = preload("res://addons/sporebound_studio/cinematic_editor.gd")
const VisualEditor = preload("res://addons/sporebound_studio/visual_editor.gd")
const HeroCustomizerEditor = preload("res://addons/sporebound_studio/hero_customizer_editor.gd")
const VfxEditor = preload("res://addons/sporebound_studio/vfx_editor.gd")
const ProgressionEditor = preload("res://addons/sporebound_studio/progression_editor.gd")
const Map2DDefinition = preload("res://scripts/maps/spore_map_2d.gd")
const HeroSpawn2DDefinition = preload("res://scripts/maps/spore_hero_spawn_2d.gd")
const EnemySpawn2DDefinition = preload("res://scripts/maps/spore_enemy_spawn_2d.gd")
const Interactable2DDefinition = preload("res://scripts/maps/spore_map_interactable_2d.gd")
const Zone2DDefinition = preload("res://scripts/maps/spore_map_zone_2d.gd")

const UNIT_DIR := "res://data/units/"
const SKILL_DIR := "res://data/skills/"
const MISSION_DIR := "res://data/missions/"
const STATUS_DIR := "res://data/statuses/"
const CAMPAIGN_PATH := "res://data/campaigns/main_campaign.tres"
const AI_DIR := "res://data/ai/"
const CINEMATIC_DIR := "res://data/cinematics/"
const VISUAL_DIR := "res://data/visuals/units/"
const VFX_DIR := "res://data/vfx/"
const JOB_DIR := "res://data/jobs/"
const MAP_SCENE_DIR := "res://maps/"

const MAP_TOOLS := [
	["Obstacle", "obstacle"],
	["Couverture", "cover"],
	["Spores dangereuses", "hazard"],
	["Extraction", "extraction"],
	["Bonus / Vinyle", "bonus"],
	["Couronne", "crown"],
	["Hauteur 0", "height0"],
	["Hauteur 1", "height1"],
	["Hauteur 2", "height2"],
	["Spawn héros", "hero"],
	["Spawn ennemi", "enemy"],
	["Porte", "door"],
	["Interrupteur", "switch"],
	["Coffre", "chest"],
	["Inspecter spawn", "spawn_select"],
	["Sol / Nettoyer terrain", "ground"],
	["Gomme totale", "erase"],
]

const MAP_MODES := [
	["Pinceau", "brush"],
	["Rectangle", "rectangle"],
	["Remplir", "fill"],
	["Copier zone", "copy"],
	["Coller", "paste"],
]

const EFFECT_TYPES := ["damage", "heal", "status", "push", "pull", "focus", "guard", "reaction", "zone"]
const EFFECT_SCOPES := ["target", "self", "allies", "enemies"]
const EFFECT_SHAPES := ["single", "cross", "diamond", "line", "circle"]
const TARGET_MODES := ["self", "ally", "enemy", "unit", "ground"]
const STATUS_TICK_PHASES := ["none", "activation_start", "activation_end"]
const STATUS_STACK_MODES := ["refresh", "stack", "replace"]
const CAMPAIGN_NODE_TYPES := ["mission", "event", "end"]
const CAMPAIGN_REWARD_TYPES := ["none", "xp", "focus_buff", "guard_buff"]
const MISSION_RULE_TYPES := ["all_enemies_defeated", "all_players_defeated", "survive_rounds", "crown_extracted", "round_at_least", "bonus_collected", "unit_defeated", "unit_alive", "unit_on_extraction"]
const TRIGGER_CONDITIONS := ["round_start", "round_end", "enemy_count_at_most", "player_count_at_most", "unit_hp_at_most", "unit_defeated", "player_enters_cell", "enemy_enters_cell", "player_enters_zone", "enemy_enters_zone"]
const TRIGGER_ACTIONS := ["message", "wait", "spawn_enemy", "apply_status_to_unit", "add_hazard", "remove_hazard", "heal_team", "damage_team", "grant_focus_team", "set_objective_text", "set_victory_rule", "set_defeat_rule", "open_door", "close_door", "toggle_switch", "open_chest", "set_phase", "play_cinematic"]
const INTERACTABLE_TYPES := ["door", "switch", "chest"]
const INTERACTABLE_REWARDS := ["none", "heal_team", "focus_team"]

var editor_plugin
var status_label: Label
var dirty_mission := false
var dirty_skill := false
var dirty_status := false
var dirty_campaign := false
var dirty_ai := false
var dirty_logic_mission := false

# Map / mission editor
var mission_select: OptionButton
var mission_template_select: OptionButton
var mission_current: Resource
var mission_path := ""
var mission_name: LineEdit
var mission_brief: TextEdit
var mission_secondary: LineEdit
var mission_objective: OptionButton
var mission_survival: SpinBox
var mission_width: SpinBox
var mission_height: SpinBox
var tool_select: OptionButton
var map_mode_select: OptionButton
var enemy_select: OptionButton
var map_canvas: SporeMapCanvas
var map_validation: Label
var undo_button: Button
var redo_button: Button
var map_history: Array[Dictionary] = []
var map_redo: Array[Dictionary] = []
var stroke_before: Dictionary = {}
var stroke_active := false
var gesture_anchor := Vector2i(-1, -1)
var clipboard: Dictionary = {}
var selected_spawn_index := -1
var spawn_unit: OptionButton
var spawn_role: LineEdit
var spawn_hp: SpinBox
var spawn_attack: SpinBox
var spawn_move: SpinBox
var spawn_range: SpinBox
var spawn_panel: VBoxContainer

# Unit editor
var unit_select: OptionButton
var unit_current: Resource
var unit_path := ""
var unit_name: LineEdit
var unit_role: LineEdit
var unit_team: OptionButton
var unit_hp: SpinBox
var unit_attack: SpinBox
var unit_move: SpinBox
var unit_range: SpinBox
var unit_init: SpinBox
var unit_focus: SpinBox
var unit_color: ColorPickerButton
var unit_visual: OptionButton
var unit_primary: OptionButton
var unit_secondary: OptionButton
var unit_ai: OptionButton
var unit_reaction: OptionButton
var unit_reaction_range: SpinBox
var unit_reaction_bonus: SpinBox
var unit_default_job: OptionButton
var unit_available_jobs: ItemList
var unit_start_level: SpinBox
var unit_validation: Label

# Skill editor
var skill_select: OptionButton
var skill_current: Resource
var skill_path := ""
var skill_name: LineEdit
var skill_desc: TextEdit
var skill_cost: SpinBox
var skill_cd: SpinBox
var skill_range: SpinBox
var skill_target: OptionButton
var skill_tags: LineEdit
var skill_vfx: OptionButton
var effect_list: ItemList
var effect_type: OptionButton
var effect_amount: SpinBox
var effect_use_attack: CheckBox
var effect_damage_type: LineEdit
var effect_status: OptionButton
var effect_radius: SpinBox
var effect_shape: OptionButton
var effect_scope: OptionButton
var effect_zone_tick_type: OptionButton
var effect_zone_tick_phase: OptionButton
var effect_zone_duration: SpinBox
var skill_validation: Label


# Status editor
var status_select: OptionButton
var status_current: Resource
var status_path := ""
var status_name: LineEdit
var status_desc: TextEdit
var status_color: ColorPickerButton
var status_vfx: OptionButton
var status_duration: SpinBox
var status_max_stacks: SpinBox
var status_stack_mode: OptionButton
var status_tick_phase: OptionButton
var status_tick_damage: SpinBox
var status_tick_damage_type: LineEdit
var status_tick_heal: SpinBox
var status_attack: SpinBox
var status_move: SpinBox
var status_range: SpinBox
var status_init: SpinBox
var status_outgoing: SpinBox
var status_incoming: SpinBox
var status_prevent_move: CheckBox
var status_prevent_action: CheckBox
var status_remove_damage: CheckBox
var status_remove_attack: CheckBox
var status_validation: Label

# AI profile editor
var ai_select: OptionButton
var ai_current: Resource
var ai_path := ""
var ai_name: LineEdit
var ai_desc: TextEdit
var ai_preferred_range: SpinBox
var ai_distance_weight: SpinBox
var ai_attack_bonus: SpinBox
var ai_cover_weight: SpinBox
var ai_height_weight: SpinBox
var ai_hazard_penalty: SpinBox
var ai_reaction_penalty: SpinBox
var ai_movement_weight: SpinBox
var ai_hp_weight: SpinBox
var ai_target_distance: SpinBox
var ai_crown_priority: SpinBox
var ai_marked_priority: SpinBox
var ai_skill_bias: SpinBox
var ai_prefer_skills: CheckBox
var ai_avoid_reactions: CheckBox
var ai_seek_cover: CheckBox
var ai_validation: Label

# Mission Logic editor
var logic_mission_select: OptionButton
var logic_mission_current: Resource
var logic_mission_path := ""
var logic_victory_mode: OptionButton
var logic_defeat_mode: OptionButton
var logic_victory_list: ItemList
var logic_defeat_list: ItemList
var logic_rule_side := "victory"
var logic_rule_index := -1
var logic_rule_type: OptionButton
var logic_rule_amount: SpinBox
var logic_rule_unit: LineEdit
var logic_rule_invert: CheckBox
var logic_rule_desc: LineEdit
var logic_trigger_list: ItemList
var logic_trigger_index := -1
var logic_trigger_id: LineEdit
var logic_trigger_enabled: CheckBox
var logic_trigger_once: CheckBox
var logic_trigger_condition: OptionButton
var logic_trigger_condition_value: SpinBox
var logic_trigger_condition_unit: LineEdit
var logic_trigger_condition_zone: LineEdit
var logic_trigger_condition_x: SpinBox
var logic_trigger_condition_y: SpinBox
var logic_trigger_action: OptionButton
var logic_trigger_message: TextEdit
var logic_trigger_action_unit: OptionButton
var logic_trigger_status: OptionButton
var logic_trigger_action_x: SpinBox
var logic_trigger_action_y: SpinBox
var logic_trigger_action_value: SpinBox
var logic_trigger_team: OptionButton
var logic_action_list: ItemList
var logic_action_index := -1
var logic_action_delay: SpinBox
var logic_action_object: OptionButton
var logic_action_cinematic: OptionButton
var logic_action_rule_type: OptionButton
var logic_action_rule_amount: SpinBox
var logic_action_rule_unit: LineEdit
var logic_action_rule_invert: CheckBox
var logic_action_rule_mode: OptionButton
var logic_interactable_list: ItemList
var logic_interactable_index := -1
var logic_interactable_id: LineEdit
var logic_interactable_name: LineEdit
var logic_interactable_type: OptionButton
var logic_interactable_x: SpinBox
var logic_interactable_y: SpinBox
var logic_interactable_link: OptionButton
var logic_interactable_active: CheckBox
var logic_interactable_one_shot: CheckBox
var logic_interactable_reward: OptionButton
var logic_interactable_reward_value: SpinBox
var logic_interactable_reward_team: OptionButton
var logic_validation: Label

# Campaign editor
var campaign_current: Resource
var campaign_canvas: SporeCampaignCanvas
var campaign_node_select: OptionButton
var campaign_node_current: Resource
var campaign_title: LineEdit
var campaign_body: TextEdit
var campaign_type: OptionButton
var campaign_mission: OptionButton
var campaign_next: OptionButton
var campaign_min_spores: SpinBox
var campaign_min_loop: SpinBox
var campaign_required_equipment: LineEdit
var campaign_fallback: OptionButton
var campaign_victory_bonus: SpinBox
var campaign_reward_pool: LineEdit
var campaign_choice_a_label: LineEdit
var campaign_choice_a_next: OptionButton
var campaign_choice_a_reward: OptionButton
var campaign_choice_a_value: SpinBox
var campaign_choice_b_label: LineEdit
var campaign_choice_b_next: OptionButton
var campaign_choice_b_reward: OptionButton
var campaign_choice_b_value: SpinBox
var campaign_start_node: OptionButton
var campaign_validation: Label
var cinematic_editor: SporeCinematicEditor
var visual_editor: SporeVisualEditor
var hero_customizer_editor
var vfx_editor: SporeVfxEditor
var progression_editor: SporeProgressionEditor


func _ready() -> void:
	custom_minimum_size = Vector2(1120.0, 580.0)
	_build_header()
	var tabs := TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tabs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_child(tabs)
	_build_map_tab(tabs)
	_build_mission_logic_tab(tabs)
	_build_cinematic_tab(tabs)
	_build_unit_tab(tabs)
	_build_progression_tab(tabs)
	_build_hero_customizer_tab(tabs)
	_build_visual_tab(tabs)
	_build_ai_tab(tabs)
	_build_skill_tab(tabs)
	_build_status_tab(tabs)
	_build_vfx_tab(tabs)
	_build_campaign_tab(tabs)
	_refresh_all()


func _shortcut_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.ctrl_pressed:
		if event.keycode == KEY_Z and not event.shift_pressed:
			_undo_map()
			accept_event()
		elif event.keycode == KEY_Y or (event.keycode == KEY_Z and event.shift_pressed):
			_redo_map()
			accept_event()


func has_unsaved_data() -> bool:
	return dirty_mission or dirty_skill or dirty_status or dirty_campaign or dirty_ai or dirty_logic_mission or (cinematic_editor != null and cinematic_editor.has_unsaved_data()) or (visual_editor != null and visual_editor.has_unsaved_data()) or (hero_customizer_editor != null and hero_customizer_editor.has_unsaved_data()) or (vfx_editor != null and vfx_editor.has_unsaved_data()) or (progression_editor != null and progression_editor.has_unsaved_data())


func save_external_data() -> void:
	if dirty_mission and mission_current != null and not mission_path.is_empty():
		ResourceSaver.save(mission_current, mission_path)
	if dirty_skill and skill_current != null and not skill_path.is_empty():
		ResourceSaver.save(skill_current, skill_path)
	if dirty_status and status_current != null and not status_path.is_empty():
		ResourceSaver.save(status_current, status_path)
	if dirty_campaign and campaign_current != null:
		ResourceSaver.save(campaign_current, CAMPAIGN_PATH)
	if dirty_ai and ai_current != null and not ai_path.is_empty():
		_write_ai_editor_to_current()
		ResourceSaver.save(ai_current, ai_path)
	if dirty_logic_mission and logic_mission_current != null and not logic_mission_path.is_empty():
		ResourceSaver.save(logic_mission_current, logic_mission_path)
	dirty_mission = false
	dirty_skill = false
	dirty_status = false
	dirty_campaign = false
	dirty_ai = false
	dirty_logic_mission = false
	if cinematic_editor != null:
		cinematic_editor.save_external_data()
	if visual_editor != null:
		visual_editor.save_external_data()
	if hero_customizer_editor != null:
		hero_customizer_editor.save_external_data()
	if vfx_editor != null:
		vfx_editor.save_external_data()
	if progression_editor != null:
		progression_editor.save_external_data()


func _mark_mission_dirty() -> void:
	dirty_mission = true


func _mark_skill_dirty() -> void:
	dirty_skill = true


func _mark_status_dirty() -> void:
	dirty_status = true


func _mark_campaign_dirty() -> void:
	dirty_campaign = true


func _mark_ai_dirty() -> void:
	dirty_ai = true


func _build_header() -> void:
	var row := HBoxContainer.new()
	add_child(row)
	var title := Label.new()
	title.text = "SPOREBOUND STUDIO  •  V1.26.1 Hero Creator Plugin Fix"
	title.add_theme_font_size_override("font_size", 18)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(title)
	var refresh := Button.new()
	refresh.text = "↻ Recharger"
	refresh.pressed.connect(_refresh_all)
	row.add_child(refresh)
	status_label = Label.new()
	status_label.text = "Les .tres sont la source de vérité du jeu."
	status_label.add_theme_color_override("font_color", Color("#8fd9ba"))
	add_child(status_label)


func _build_map_tab(tabs: TabContainer) -> void:
	var root := HSplitContainer.new()
	root.name = "Maps"
	tabs.add_child(root)

	var left := VBoxContainer.new()
	left.custom_minimum_size = Vector2(760.0, 510.0)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_child(left)

	var mission_bar := HBoxContainer.new()
	left.add_child(mission_bar)
	var native_actions: HBoxContainer = HBoxContainer.new()
	left.add_child(native_actions)
	mission_select = OptionButton.new()
	mission_select.custom_minimum_size.x = 250
	mission_select.item_selected.connect(_on_mission_selected)
	mission_bar.add_child(mission_select)
	mission_template_select = OptionButton.new()
	mission_template_select.custom_minimum_size.x = 155.0
	for template_info: Array in [
		["Template vide", "blank"],
		["Escarmouche 8×8", "skirmish"],
		["Objectif 10×8", "objective"],
		["Grande 12×10", "large"],
	]:
		mission_template_select.add_item(String(template_info[0]))
		mission_template_select.set_item_metadata(mission_template_select.item_count - 1, String(template_info[1]))
	mission_bar.add_child(mission_template_select)
	var new_mission := Button.new()
	new_mission.text = "+ Mission"
	new_mission.pressed.connect(_new_mission)
	mission_bar.add_child(new_mission)
	var duplicate_mission := Button.new()
	duplicate_mission.text = "Dupliquer"
	duplicate_mission.pressed.connect(_duplicate_mission)
	mission_bar.add_child(duplicate_mission)
	var save := Button.new()
	save.text = "Enregistrer"
	save.pressed.connect(_save_mission)
	mission_bar.add_child(save)
	var open_native := Button.new()
	open_native.text = "🗺 ÉDITER LA MAP EN 2D"
	open_native.tooltip_text = "Ouvre la scène .tscn dans la vraie viewport 2D Godot. Le terrain se peint avec les TileMapLayer natifs."
	open_native.pressed.connect(_open_current_native_map)
	native_actions.add_child(open_native)
	var play_native: Button = Button.new()
	play_native.text = "▶ Tester direct"
	play_native.tooltip_text = "Sauvegarde la scène native et lance immédiatement la mission sans modifier la sauvegarde campagne."
	play_native.pressed.connect(_test_current_mission_direct)
	native_actions.add_child(play_native)
	undo_button = Button.new()
	undo_button.text = "↶"
	undo_button.tooltip_text = "Annuler (Ctrl+Z)"
	undo_button.pressed.connect(_undo_map)
	mission_bar.add_child(undo_button)
	redo_button = Button.new()
	redo_button.text = "↷"
	redo_button.tooltip_text = "Rétablir (Ctrl+Y)"
	redo_button.pressed.connect(_redo_map)
	mission_bar.add_child(redo_button)

	var tool_bar := HBoxContainer.new()
	left.add_child(tool_bar)
	tool_bar.visible = false # V1.9.2: édition de map dans la viewport 2D native.
	tool_select = OptionButton.new()
	tool_select.custom_minimum_size.x = 190
	for tool in MAP_TOOLS:
		tool_select.add_item(String(tool[0]))
		tool_select.set_item_metadata(tool_select.item_count - 1, String(tool[1]))
	tool_select.item_selected.connect(_on_tool_selected)
	tool_bar.add_child(tool_select)
	map_mode_select = OptionButton.new()
	map_mode_select.custom_minimum_size.x = 140
	for mode in MAP_MODES:
		map_mode_select.add_item(String(mode[0]))
		map_mode_select.set_item_metadata(map_mode_select.item_count - 1, String(mode[1]))
	map_mode_select.item_selected.connect(_on_map_mode_selected)
	tool_bar.add_child(map_mode_select)
	enemy_select = OptionButton.new()
	enemy_select.custom_minimum_size.x = 190
	tool_bar.add_child(enemy_select)
	var validate := Button.new()
	validate.text = "✓ Valider"
	validate.pressed.connect(_validate_current_mission)
	tool_bar.add_child(validate)
	var test := Button.new()
	test.text = "▶ Tester"
	test.pressed.connect(_test_current_mission)
	tool_bar.add_child(test)

	var native_hint := Label.new()
	native_hint.text = "LEVEL DESIGN : clique sur ‘ÉDITER LA MAP EN 2D’. Dans Godot, sélectionne Ground / Height / Terrain / Objectives et peins avec la palette TileMap native. Les spawns et objets se déplacent directement dans la viewport."
	native_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	native_hint.add_theme_color_override("font_color", Color("#8fd9ba"))
	left.add_child(native_hint)

	map_canvas = MapCanvas.new()
	map_canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	map_canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	map_canvas.cell_pressed.connect(_on_map_cell_pressed)
	map_canvas.cell_dragged.connect(_on_map_cell_dragged)
	map_canvas.cell_released.connect(_on_map_cell_released)
	left.add_child(map_canvas)
	map_canvas.visible = false # Aperçu legacy conservé uniquement pour compatibilité de code.

	var legend := Label.new()
	legend.text = "Pinceau = glisser • Rectangle = 2 clics • Remplir = zone contiguë • Copier zone = 2 clics puis Coller • clic droit = gomme"
	legend.add_theme_font_size_override("font_size", 12)
	legend.visible = false
	left.add_child(legend)

	var side_scroll := ScrollContainer.new()
	side_scroll.custom_minimum_size = Vector2(350.0, 500.0)
	root.add_child(side_scroll)
	var side := VBoxContainer.new()
	side.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	side_scroll.add_child(side)

	mission_name = _line_field(side, "Nom")
	mission_brief = _text_field(side, "Brief", 72)
	mission_secondary = _line_field(side, "Objectif secondaire")
	_add_label(side, "Objectif principal")
	mission_objective = OptionButton.new()
	for objective in ["crown", "survive", "eliminate"]:
		mission_objective.add_item(objective)
	side.add_child(mission_objective)
	mission_survival = _spin_field(side, "Manches de survie", 0, 20)
	var dimensions := HBoxContainer.new()
	side.add_child(dimensions)
	mission_width = _compact_spin(dimensions, "Largeur", 4, 30)
	mission_height = _compact_spin(dimensions, "Hauteur", 4, 30)
	var resize := Button.new()
	resize.text = "Redimensionner"
	resize.pressed.connect(_resize_mission)
	dimensions.add_child(resize)

	_add_separator(side, "Spawn ennemi sélectionné")
	spawn_panel = VBoxContainer.new()
	side.add_child(spawn_panel)
	spawn_unit = OptionButton.new()
	spawn_panel.add_child(spawn_unit)
	spawn_role = _line_field(spawn_panel, "Rôle override (vide = global)")
	spawn_hp = _spin_field(spawn_panel, "PV override (-1 = global)", -1, 99)
	spawn_attack = _spin_field(spawn_panel, "ATQ override (-1 = global)", -1, 20)
	spawn_move = _spin_field(spawn_panel, "MVT override (-1 = global)", -1, 12)
	spawn_range = _spin_field(spawn_panel, "Portée override (-1 = global)", -1, 12)
	var spawn_buttons := HBoxContainer.new()
	spawn_panel.add_child(spawn_buttons)
	var apply_spawn := Button.new()
	apply_spawn.text = "Appliquer"
	apply_spawn.pressed.connect(_apply_spawn_inspector)
	spawn_buttons.add_child(apply_spawn)
	var delete_spawn := Button.new()
	delete_spawn.text = "Supprimer"
	delete_spawn.pressed.connect(_delete_selected_spawn)
	spawn_buttons.add_child(delete_spawn)
	_set_spawn_panel_enabled(false)

	_add_separator(side, "Validation")
	map_validation = Label.new()
	map_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	map_validation.custom_minimum_size.y = 140
	side.add_child(map_validation)


func _build_mission_logic_tab(tabs: TabContainer) -> void:
	var root := HSplitContainer.new()
	root.name = "Mission Logic"
	tabs.add_child(root)

	var left_scroll := ScrollContainer.new()
	left_scroll.custom_minimum_size.x = 550
	root.add_child(left_scroll)
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_scroll.add_child(left)
	var toolbar := HBoxContainer.new()
	left.add_child(toolbar)
	logic_mission_select = OptionButton.new()
	logic_mission_select.custom_minimum_size.x = 330
	logic_mission_select.item_selected.connect(_on_logic_mission_selected)
	toolbar.add_child(logic_mission_select)
	var save := Button.new()
	save.text = "Enregistrer logique"
	save.pressed.connect(_save_logic_mission)
	toolbar.add_child(save)

	_add_separator(left, "Conditions de victoire")
	var victory_bar := HBoxContainer.new()
	left.add_child(victory_bar)
	logic_victory_mode = OptionButton.new()
	logic_victory_mode.add_item("any")
	logic_victory_mode.add_item("all")
	logic_victory_mode.item_selected.connect(_on_logic_mode_changed)
	victory_bar.add_child(logic_victory_mode)
	var add_victory := Button.new()
	add_victory.text = "+ Victoire"
	add_victory.pressed.connect(_add_logic_rule.bind("victory"))
	victory_bar.add_child(add_victory)
	var remove_victory := Button.new()
	remove_victory.text = "Supprimer"
	remove_victory.pressed.connect(_remove_logic_rule.bind("victory"))
	victory_bar.add_child(remove_victory)
	logic_victory_list = ItemList.new()
	logic_victory_list.custom_minimum_size.y = 110
	logic_victory_list.item_selected.connect(_on_logic_rule_selected.bind("victory"))
	left.add_child(logic_victory_list)

	_add_separator(left, "Conditions de défaite")
	var defeat_bar := HBoxContainer.new()
	left.add_child(defeat_bar)
	logic_defeat_mode = OptionButton.new()
	logic_defeat_mode.add_item("any")
	logic_defeat_mode.add_item("all")
	logic_defeat_mode.item_selected.connect(_on_logic_mode_changed)
	defeat_bar.add_child(logic_defeat_mode)
	var add_defeat := Button.new()
	add_defeat.text = "+ Défaite"
	add_defeat.pressed.connect(_add_logic_rule.bind("defeat"))
	defeat_bar.add_child(add_defeat)
	var remove_defeat := Button.new()
	remove_defeat.text = "Supprimer"
	remove_defeat.pressed.connect(_remove_logic_rule.bind("defeat"))
	defeat_bar.add_child(remove_defeat)
	logic_defeat_list = ItemList.new()
	logic_defeat_list.custom_minimum_size.y = 110
	logic_defeat_list.item_selected.connect(_on_logic_rule_selected.bind("defeat"))
	left.add_child(logic_defeat_list)

	_add_separator(left, "Triggers de combat")
	var trigger_bar := HBoxContainer.new()
	left.add_child(trigger_bar)
	var add_trigger := Button.new()
	add_trigger.text = "+ Trigger"
	add_trigger.pressed.connect(_add_logic_trigger)
	trigger_bar.add_child(add_trigger)
	var remove_trigger := Button.new()
	remove_trigger.text = "Supprimer"
	remove_trigger.pressed.connect(_remove_logic_trigger)
	trigger_bar.add_child(remove_trigger)
	logic_trigger_list = ItemList.new()
	logic_trigger_list.custom_minimum_size.y = 130
	logic_trigger_list.item_selected.connect(_on_logic_trigger_selected)
	left.add_child(logic_trigger_list)

	_add_separator(left, "Objets de carte")
	var object_bar := HBoxContainer.new()
	left.add_child(object_bar)
	for object_type in INTERACTABLE_TYPES:
		var add_object := Button.new()
		add_object.text = "+ %s" % object_type.capitalize()
		add_object.pressed.connect(_add_logic_interactable.bind(object_type))
		object_bar.add_child(add_object)
	var remove_object := Button.new()
	remove_object.text = "Supprimer"
	remove_object.pressed.connect(_remove_logic_interactable)
	object_bar.add_child(remove_object)
	logic_interactable_list = ItemList.new()
	logic_interactable_list.custom_minimum_size.y = 120
	logic_interactable_list.item_selected.connect(_on_logic_interactable_selected)
	left.add_child(logic_interactable_list)
	logic_validation = Label.new()
	logic_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	logic_validation.custom_minimum_size.y = 90
	left.add_child(logic_validation)

	var right_scroll := ScrollContainer.new()
	root.add_child(right_scroll)
	var right := VBoxContainer.new()
	right.custom_minimum_size.x = 410
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_scroll.add_child(right)

	_add_separator(right, "Règle sélectionnée")
	_add_label(right, "Type")
	logic_rule_type = OptionButton.new()
	for value in MISSION_RULE_TYPES:
		logic_rule_type.add_item(value)
	right.add_child(logic_rule_type)
	logic_rule_amount = _spin_field(right, "Valeur", 0, 99)
	logic_rule_unit = _line_field(right, "Unit ID / template ID")
	logic_rule_invert = CheckBox.new()
	logic_rule_invert.text = "Inverser la condition"
	right.add_child(logic_rule_invert)
	logic_rule_desc = _line_field(right, "Description")
	var apply_rule := Button.new()
	apply_rule.text = "Appliquer à la règle"
	apply_rule.pressed.connect(_apply_logic_rule_editor)
	right.add_child(apply_rule)

	_add_separator(right, "Trigger sélectionné")
	logic_trigger_id = _line_field(right, "ID unique")
	logic_trigger_enabled = CheckBox.new()
	logic_trigger_enabled.text = "Activé"
	right.add_child(logic_trigger_enabled)
	logic_trigger_once = CheckBox.new()
	logic_trigger_once.text = "Une seule fois"
	right.add_child(logic_trigger_once)
	_add_label(right, "Condition")
	logic_trigger_condition = OptionButton.new()
	for value in TRIGGER_CONDITIONS:
		logic_trigger_condition.add_item(value)
	right.add_child(logic_trigger_condition)
	logic_trigger_condition_value = _spin_field(right, "Valeur condition", 0, 99)
	logic_trigger_condition_unit = _line_field(right, "Unit ID condition")
	logic_trigger_condition_zone = _line_field(right, "Zone ID condition")
	var cpos := HBoxContainer.new()
	right.add_child(cpos)
	logic_trigger_condition_x = _compact_spin(cpos, "Cell X", -1, 29)
	logic_trigger_condition_y = _compact_spin(cpos, "Y", -1, 29)
	_add_separator(right, "Séquence d'actions")
	var action_bar := HBoxContainer.new()
	right.add_child(action_bar)
	var add_action := Button.new()
	add_action.text = "+ Action"
	add_action.pressed.connect(_add_logic_action)
	action_bar.add_child(add_action)
	var duplicate_action := Button.new()
	duplicate_action.text = "Dupliquer"
	duplicate_action.pressed.connect(_duplicate_logic_action)
	action_bar.add_child(duplicate_action)
	var up_action := Button.new()
	up_action.text = "↑"
	up_action.pressed.connect(_move_logic_action.bind(-1))
	action_bar.add_child(up_action)
	var down_action := Button.new()
	down_action.text = "↓"
	down_action.pressed.connect(_move_logic_action.bind(1))
	action_bar.add_child(down_action)
	var remove_action := Button.new()
	remove_action.text = "Suppr."
	remove_action.pressed.connect(_remove_logic_action)
	action_bar.add_child(remove_action)
	logic_action_list = ItemList.new()
	logic_action_list.custom_minimum_size.y = 120
	logic_action_list.item_selected.connect(_on_logic_action_selected)
	right.add_child(logic_action_list)

	_add_label(right, "Type d'action")
	logic_trigger_action = OptionButton.new()
	for value in TRIGGER_ACTIONS:
		logic_trigger_action.add_item(value)
	right.add_child(logic_trigger_action)
	logic_action_delay = _spin_field(right, "Délai avant action (s)", 0, 10)
	logic_action_delay.step = 0.1
	logic_trigger_message = _text_field(right, "Message / phase / objectif", 70)
	_add_label(right, "Unité action")
	logic_trigger_action_unit = OptionButton.new()
	right.add_child(logic_trigger_action_unit)
	_add_label(right, "Statut action")
	logic_trigger_status = OptionButton.new()
	right.add_child(logic_trigger_status)
	var apos := HBoxContainer.new()
	right.add_child(apos)
	logic_trigger_action_x = _compact_spin(apos, "Cell X", -1, 29)
	logic_trigger_action_y = _compact_spin(apos, "Y", -1, 29)
	logic_trigger_action_value = _spin_field(right, "Valeur action", -99, 99)
	_add_label(right, "Équipe action")
	logic_trigger_team = OptionButton.new()
	logic_trigger_team.add_item("player")
	logic_trigger_team.add_item("enemy")
	right.add_child(logic_trigger_team)
	_add_label(right, "Objet de carte ciblé")
	logic_action_object = OptionButton.new()
	right.add_child(logic_action_object)
	_add_label(right, "Cinématique (play_cinematic)")
	logic_action_cinematic = OptionButton.new()
	right.add_child(logic_action_cinematic)
	_add_label(right, "Règle dynamique")
	logic_action_rule_type = OptionButton.new()
	for value in MISSION_RULE_TYPES:
		logic_action_rule_type.add_item(value)
	right.add_child(logic_action_rule_type)
	logic_action_rule_amount = _spin_field(right, "Valeur règle", 0, 99)
	logic_action_rule_unit = _line_field(right, "Unit ID règle")
	logic_action_rule_invert = CheckBox.new()
	logic_action_rule_invert.text = "Inverser la règle"
	right.add_child(logic_action_rule_invert)
	logic_action_rule_mode = OptionButton.new()
	logic_action_rule_mode.add_item("any")
	logic_action_rule_mode.add_item("all")
	right.add_child(logic_action_rule_mode)
	var apply_trigger := Button.new()
	apply_trigger.text = "Appliquer condition + action"
	apply_trigger.pressed.connect(_apply_logic_trigger_editor)
	right.add_child(apply_trigger)

	_add_separator(right, "Objet de carte sélectionné")
	logic_interactable_id = _line_field(right, "ID objet")
	logic_interactable_name = _line_field(right, "Nom")
	logic_interactable_type = OptionButton.new()
	for value in INTERACTABLE_TYPES:
		logic_interactable_type.add_item(value)
	right.add_child(logic_interactable_type)
	var object_pos := HBoxContainer.new()
	right.add_child(object_pos)
	logic_interactable_x = _compact_spin(object_pos, "Cell X", 0, 29)
	logic_interactable_y = _compact_spin(object_pos, "Y", 0, 29)
	_add_label(right, "Objet lié")
	logic_interactable_link = OptionButton.new()
	right.add_child(logic_interactable_link)
	logic_interactable_active = CheckBox.new()
	logic_interactable_active.text = "Actif/ouvert au départ"
	right.add_child(logic_interactable_active)
	logic_interactable_one_shot = CheckBox.new()
	logic_interactable_one_shot.text = "Activation unique"
	right.add_child(logic_interactable_one_shot)
	logic_interactable_reward = OptionButton.new()
	for value in INTERACTABLE_REWARDS:
		logic_interactable_reward.add_item(value)
	right.add_child(logic_interactable_reward)
	logic_interactable_reward_value = _spin_field(right, "Valeur récompense", 0, 99)
	logic_interactable_reward_team = OptionButton.new()
	logic_interactable_reward_team.add_item("player")
	logic_interactable_reward_team.add_item("enemy")
	right.add_child(logic_interactable_reward_team)
	var apply_object := Button.new()
	apply_object.text = "Appliquer à l'objet"
	apply_object.pressed.connect(_apply_logic_interactable_editor)
	right.add_child(apply_object)
	var help := Label.new()
	help.text = "V1.7 : condition → actions ordonnées, avec play_cinematic pour appeler une timeline réutilisable. Utilise wait pour temporiser. Une switch peut piloter une porte ; un coffre s'ouvre quand un héros entre sur sa case."
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(help)


func _build_cinematic_tab(tabs: TabContainer) -> void:
	cinematic_editor = CinematicEditor.new()
	cinematic_editor.name = "Cinematics"
	tabs.add_child(cinematic_editor)



func _build_progression_tab(tabs: TabContainer) -> void:
	progression_editor = ProgressionEditor.new()
	progression_editor.name = "Progression"
	progression_editor.library_changed.connect(_on_progression_library_changed)
	tabs.add_child(progression_editor)


func _on_progression_library_changed() -> void:
	_refresh_unit_job_selectors()
	if unit_select != null and unit_select.item_count > 0:
		_on_unit_selected(unit_select.selected)


func _build_hero_customizer_tab(tabs: TabContainer) -> void:
	hero_customizer_editor = HeroCustomizerEditor.new()
	hero_customizer_editor.name = "Hero Creator Pro"
	hero_customizer_editor.library_changed.connect(_on_hero_customizer_library_changed)
	tabs.add_child(hero_customizer_editor)


func _on_hero_customizer_library_changed() -> void:
	_refresh_visual_selector()
	if visual_editor != null:
		visual_editor.refresh()


func _build_visual_tab(tabs: TabContainer) -> void:
	visual_editor = VisualEditor.new()
	visual_editor.name = "Visuals"
	visual_editor.library_changed.connect(_on_visual_library_changed)
	tabs.add_child(visual_editor)


func _build_vfx_tab(tabs: TabContainer) -> void:
	vfx_editor = VfxEditor.new()
	vfx_editor.name = "VFX"
	vfx_editor.library_changed.connect(_on_vfx_library_changed)
	tabs.add_child(vfx_editor)


func _on_visual_library_changed() -> void:
	_refresh_visual_selector()


func _on_vfx_library_changed() -> void:
	_refresh_vfx_selectors()
	if visual_editor != null:
		visual_editor.refresh()


func _build_ai_tab(tabs: TabContainer) -> void:
	var scroll := ScrollContainer.new()
	scroll.name = "AI"
	tabs.add_child(scroll)
	var root := VBoxContainer.new()
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(root)
	var toolbar := HBoxContainer.new()
	root.add_child(toolbar)
	ai_select = OptionButton.new()
	ai_select.custom_minimum_size.x = 320
	ai_select.item_selected.connect(_on_ai_selected)
	toolbar.add_child(ai_select)
	var new_ai := Button.new()
	new_ai.text = "+ Profil IA"
	new_ai.pressed.connect(_new_ai_profile)
	toolbar.add_child(new_ai)
	var duplicate := Button.new()
	duplicate.text = "Dupliquer"
	duplicate.pressed.connect(_duplicate_ai_profile)
	toolbar.add_child(duplicate)
	var save := Button.new()
	save.text = "Enregistrer"
	save.pressed.connect(_save_ai_profile)
	toolbar.add_child(save)

	var grid := GridContainer.new()
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_child(grid)
	ai_name = _grid_line(grid, "Nom")
	_add_grid_label(grid, "Description")
	ai_desc = TextEdit.new()
	ai_desc.custom_minimum_size = Vector2(440, 70)
	grid.add_child(ai_desc)
	ai_preferred_range = _grid_spin(grid, "Distance préférée", 0, 12)
	ai_distance_weight = _grid_spin(grid, "Poids distance", -20, 20)
	ai_distance_weight.step = 0.5
	ai_attack_bonus = _grid_spin(grid, "Bonus position d'attaque", -200, 200)
	ai_attack_bonus.step = 0.5
	ai_cover_weight = _grid_spin(grid, "Poids couverture", -30, 30)
	ai_cover_weight.step = 0.5
	ai_height_weight = _grid_spin(grid, "Poids hauteur", -30, 30)
	ai_height_weight.step = 0.5
	ai_hazard_penalty = _grid_spin(grid, "Pénalité danger", 0, 100)
	ai_hazard_penalty.step = 0.5
	ai_reaction_penalty = _grid_spin(grid, "Pénalité réaction", 0, 100)
	ai_reaction_penalty.step = 0.5
	ai_movement_weight = _grid_spin(grid, "Poids coût déplacement", 0, 10)
	ai_movement_weight.step = 0.05
	ai_hp_weight = _grid_spin(grid, "Priorité cible faible PV", 0, 20)
	ai_hp_weight.step = 0.5
	ai_target_distance = _grid_spin(grid, "Poids distance cible", 0, 20)
	ai_target_distance.step = 0.5
	ai_crown_priority = _grid_spin(grid, "Priorité porteur Couronne", 0, 250)
	ai_crown_priority.step = 5
	ai_marked_priority = _grid_spin(grid, "Priorité cible BALISÉE", 0, 100)
	ai_marked_priority.step = 1
	ai_skill_bias = _grid_spin(grid, "Préférence compétences", 0, 5)
	ai_skill_bias.step = 0.1
	_add_grid_label(grid, "Comportement")
	var checks := HBoxContainer.new()
	grid.add_child(checks)
	ai_prefer_skills = CheckBox.new()
	ai_prefer_skills.text = "Skills"
	checks.add_child(ai_prefer_skills)
	ai_avoid_reactions = CheckBox.new()
	ai_avoid_reactions.text = "Éviter réactions"
	checks.add_child(ai_avoid_reactions)
	ai_seek_cover = CheckBox.new()
	ai_seek_cover.text = "Couverture"
	checks.add_child(ai_seek_cover)
	ai_validation = Label.new()
	ai_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(ai_validation)
	for edit in [ai_name, ai_desc]:
		edit.text_changed.connect(_on_ai_field_changed)
	for spin in [ai_preferred_range, ai_distance_weight, ai_attack_bonus, ai_cover_weight, ai_height_weight, ai_hazard_penalty, ai_reaction_penalty, ai_movement_weight, ai_hp_weight, ai_target_distance, ai_crown_priority, ai_marked_priority, ai_skill_bias]:
		spin.value_changed.connect(_on_ai_field_changed)
	for check in [ai_prefer_skills, ai_avoid_reactions, ai_seek_cover]:
		check.toggled.connect(_on_ai_field_changed)


func _build_unit_tab(tabs: TabContainer) -> void:
	var scroll := ScrollContainer.new()
	scroll.name = "Units"
	tabs.add_child(scroll)
	var root := VBoxContainer.new()
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(root)

	var toolbar := HBoxContainer.new()
	root.add_child(toolbar)
	unit_select = OptionButton.new()
	unit_select.custom_minimum_size.x = 320
	unit_select.item_selected.connect(_on_unit_selected)
	toolbar.add_child(unit_select)
	var new_unit := Button.new()
	new_unit.text = "+ Unité"
	new_unit.pressed.connect(_new_unit)
	toolbar.add_child(new_unit)
	var duplicate := Button.new()
	duplicate.text = "Dupliquer"
	duplicate.pressed.connect(_duplicate_unit)
	toolbar.add_child(duplicate)
	var save := Button.new()
	save.text = "Enregistrer"
	save.pressed.connect(_save_unit)
	toolbar.add_child(save)

	var grid := GridContainer.new()
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_child(grid)
	unit_name = _grid_line(grid, "Nom")
	unit_role = _grid_line(grid, "Rôle")
	_add_grid_label(grid, "Équipe")
	unit_team = OptionButton.new()
	unit_team.add_item("player")
	unit_team.add_item("enemy")
	grid.add_child(unit_team)
	unit_hp = _grid_spin(grid, "PV max", 1, 99)
	unit_attack = _grid_spin(grid, "ATQ", 0, 20)
	unit_move = _grid_spin(grid, "MVT", 1, 12)
	unit_range = _grid_spin(grid, "Portée", 1, 12)
	unit_init = _grid_spin(grid, "Initiative", 0, 30)
	unit_focus = _grid_spin(grid, "Focus max", 0, 20)
	_add_grid_label(grid, "Couleur")
	unit_color = ColorPickerButton.new()
	grid.add_child(unit_color)
	_add_grid_label(grid, "Apparence / Skin")
	unit_visual = OptionButton.new()
	grid.add_child(unit_visual)
	_add_grid_label(grid, "Compétence principale")
	unit_primary = OptionButton.new()
	grid.add_child(unit_primary)
	_add_grid_label(grid, "Compétence secondaire")
	unit_secondary = OptionButton.new()
	grid.add_child(unit_secondary)
	_add_grid_label(grid, "Profil IA")
	unit_ai = OptionButton.new()
	grid.add_child(unit_ai)
	_add_grid_label(grid, "Réaction")
	unit_reaction = OptionButton.new()
	for reaction_value: String in ["none", "counter", "opportunity", "intercept"]:
		unit_reaction.add_item(reaction_value)
	grid.add_child(unit_reaction)
	unit_reaction_range = _grid_spin(grid, "Portée réaction", 1, 6)
	unit_reaction_bonus = _grid_spin(grid, "Bonus dégâts réaction", 0, 6)
	_add_grid_label(grid, "Job par défaut")
	unit_default_job = OptionButton.new()
	grid.add_child(unit_default_job)
	unit_start_level = _grid_spin(grid, "Niveau de départ", 1, 20)
	_add_grid_label(grid, "Jobs disponibles")
	unit_available_jobs = ItemList.new()
	unit_available_jobs.select_mode = ItemList.SELECT_MULTI
	unit_available_jobs.custom_minimum_size = Vector2(360, 95)
	grid.add_child(unit_available_jobs)
	unit_validation = Label.new()
	unit_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(unit_validation)


func _build_skill_tab(tabs: TabContainer) -> void:
	var root := HSplitContainer.new()
	root.name = "Skills"
	tabs.add_child(root)

	var left_scroll := ScrollContainer.new()
	left_scroll.custom_minimum_size.x = 550
	root.add_child(left_scroll)
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_scroll.add_child(left)
	var toolbar := HBoxContainer.new()
	left.add_child(toolbar)
	skill_select = OptionButton.new()
	skill_select.custom_minimum_size.x = 280
	skill_select.item_selected.connect(_on_skill_selected)
	toolbar.add_child(skill_select)
	var new_skill := Button.new()
	new_skill.text = "+ Compétence"
	new_skill.pressed.connect(_new_skill)
	toolbar.add_child(new_skill)
	var duplicate := Button.new()
	duplicate.text = "Dupliquer"
	duplicate.pressed.connect(_duplicate_skill)
	toolbar.add_child(duplicate)
	var save := Button.new()
	save.text = "Enregistrer"
	save.pressed.connect(_save_skill)
	toolbar.add_child(save)

	var grid := GridContainer.new()
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_child(grid)
	skill_name = _grid_line(grid, "Nom")
	_add_grid_label(grid, "Description")
	skill_desc = TextEdit.new()
	skill_desc.custom_minimum_size = Vector2(360, 74)
	grid.add_child(skill_desc)
	skill_cost = _grid_spin(grid, "Coût Focus", 0, 10)
	skill_cd = _grid_spin(grid, "Cooldown", 0, 10)
	skill_range = _grid_spin(grid, "Portée", 0, 12)
	_add_grid_label(grid, "Cible")
	skill_target = OptionButton.new()
	for target in TARGET_MODES:
		skill_target.add_item(target)
	grid.add_child(skill_target)
	skill_tags = _grid_line(grid, "Tags")
	_add_grid_label(grid, "VFX")
	skill_vfx = OptionButton.new()
	grid.add_child(skill_vfx)

	_add_separator(left, "Blocs d'effets")
	effect_list = ItemList.new()
	effect_list.custom_minimum_size.y = 190
	effect_list.item_selected.connect(_on_effect_selected)
	left.add_child(effect_list)
	var effect_toolbar := HBoxContainer.new()
	left.add_child(effect_toolbar)
	var add_effect := Button.new()
	add_effect.text = "+ Effet"
	add_effect.pressed.connect(_add_effect)
	effect_toolbar.add_child(add_effect)
	var remove_effect := Button.new()
	remove_effect.text = "Supprimer"
	remove_effect.pressed.connect(_remove_effect)
	effect_toolbar.add_child(remove_effect)
	var up_effect := Button.new()
	up_effect.text = "↑"
	up_effect.pressed.connect(_move_effect.bind(-1))
	effect_toolbar.add_child(up_effect)
	var down_effect := Button.new()
	down_effect.text = "↓"
	down_effect.pressed.connect(_move_effect.bind(1))
	effect_toolbar.add_child(down_effect)

	var right_scroll := ScrollContainer.new()
	root.add_child(right_scroll)
	var right := VBoxContainer.new()
	right.custom_minimum_size.x = 380
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_scroll.add_child(right)
	_add_separator(right, "Effet sélectionné")
	_add_label(right, "Type")
	effect_type = OptionButton.new()
	for value in EFFECT_TYPES:
		effect_type.add_item(value)
	right.add_child(effect_type)
	effect_amount = _spin_field(right, "Valeur", -20, 20)
	effect_use_attack = CheckBox.new()
	effect_use_attack.text = "Ajouter la statistique ATQ à la valeur"
	right.add_child(effect_use_attack)
	effect_damage_type = _line_field(right, "Type de dégâts (physical/spore/fire/prism...)")
	_add_label(right, "Statut appliqué")
	effect_status = OptionButton.new()
	right.add_child(effect_status)
	effect_radius = _spin_field(right, "Rayon", 0, 8)
	_add_label(right, "Forme de zone")
	effect_shape = OptionButton.new()
	for value in EFFECT_SHAPES:
		effect_shape.add_item(value)
	right.add_child(effect_shape)
	_add_label(right, "Cibles affectées")
	effect_scope = OptionButton.new()
	for value in EFFECT_SCOPES:
		effect_scope.add_item(value)
	right.add_child(effect_scope)
	_add_separator(right, "Zone persistante (type = zone)")
	_add_label(right, "Effet périodique")
	effect_zone_tick_type = OptionButton.new()
	for zone_type: String in ["damage", "heal", "status"]:
		effect_zone_tick_type.add_item(zone_type)
	right.add_child(effect_zone_tick_type)
	_add_label(right, "Phase de tick")
	effect_zone_tick_phase = OptionButton.new()
	for zone_phase: String in ["activation_start", "activation_end"]:
		effect_zone_tick_phase.add_item(zone_phase)
	right.add_child(effect_zone_tick_phase)
	effect_zone_duration = _spin_field(right, "Durée (rounds)", 1, 8)
	var apply_effect := Button.new()
	apply_effect.text = "Appliquer au bloc"
	apply_effect.pressed.connect(_apply_effect_editor)
	right.add_child(apply_effect)
	var help := Label.new()
	help.text = "Ces blocs sont exécutés au runtime. Un skill peut combiner dégâts, soin, statut, poussée/traction, Focus, Garde, recharge de réaction et zone persistante."
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(help)
	skill_validation = Label.new()
	skill_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(skill_validation)


func _build_status_tab(tabs: TabContainer) -> void:
	var scroll := ScrollContainer.new()
	scroll.name = "Statuses"
	tabs.add_child(scroll)
	var root := VBoxContainer.new()
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(root)

	var toolbar := HBoxContainer.new()
	root.add_child(toolbar)
	status_select = OptionButton.new()
	status_select.custom_minimum_size.x = 320
	status_select.item_selected.connect(_on_status_selected)
	toolbar.add_child(status_select)
	var new_status := Button.new()
	new_status.text = "+ Statut"
	new_status.pressed.connect(_new_status)
	toolbar.add_child(new_status)
	var duplicate := Button.new()
	duplicate.text = "Dupliquer"
	duplicate.pressed.connect(_duplicate_status)
	toolbar.add_child(duplicate)
	var save := Button.new()
	save.text = "Enregistrer"
	save.pressed.connect(_save_status)
	toolbar.add_child(save)

	var grid := GridContainer.new()
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_child(grid)
	status_name = _grid_line(grid, "Nom")
	_add_grid_label(grid, "Description")
	status_desc = TextEdit.new()
	status_desc.custom_minimum_size = Vector2(420, 72)
	grid.add_child(status_desc)
	_add_grid_label(grid, "Couleur")
	status_color = ColorPickerButton.new()
	grid.add_child(status_color)
	_add_grid_label(grid, "VFX actif")
	status_vfx = OptionButton.new()
	grid.add_child(status_vfx)
	status_duration = _grid_spin(grid, "Durée en activations (0 = persistant)", 0, 20)
	status_max_stacks = _grid_spin(grid, "Stacks max", 1, 8)
	_add_grid_label(grid, "Empilement")
	status_stack_mode = OptionButton.new()
	for value in STATUS_STACK_MODES:
		status_stack_mode.add_item(value)
	grid.add_child(status_stack_mode)
	_add_grid_label(grid, "Tick")
	status_tick_phase = OptionButton.new()
	for value in STATUS_TICK_PHASES:
		status_tick_phase.add_item(value)
	grid.add_child(status_tick_phase)
	status_tick_damage = _grid_spin(grid, "Dégâts par tick", 0, 20)
	status_tick_damage_type = _grid_line(grid, "Type dégâts tick")
	status_tick_heal = _grid_spin(grid, "Soin par tick", 0, 20)
	status_attack = _grid_spin(grid, "Δ ATQ", -10, 10)
	status_move = _grid_spin(grid, "Δ MVT", -10, 10)
	status_range = _grid_spin(grid, "Δ portée", -10, 10)
	status_init = _grid_spin(grid, "Δ initiative", -20, 20)
	status_outgoing = _grid_spin(grid, "Δ dégâts infligés", -10, 10)
	status_incoming = _grid_spin(grid, "Δ dégâts reçus", -10, 10)

	var flags := HBoxContainer.new()
	root.add_child(flags)
	status_prevent_move = CheckBox.new()
	status_prevent_move.text = "Bloque déplacement"
	flags.add_child(status_prevent_move)
	status_prevent_action = CheckBox.new()
	status_prevent_action.text = "Bloque activation"
	flags.add_child(status_prevent_action)
	status_remove_damage = CheckBox.new()
	status_remove_damage.text = "Retirer après dégâts reçus"
	flags.add_child(status_remove_damage)
	status_remove_attack = CheckBox.new()
	status_remove_attack.text = "Retirer après attaque"
	flags.add_child(status_remove_attack)

	status_validation = Label.new()
	status_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(status_validation)


func _build_campaign_tab(tabs: TabContainer) -> void:
	var root := HSplitContainer.new()
	root.name = "Campaign"
	tabs.add_child(root)

	var left := VBoxContainer.new()
	left.custom_minimum_size.x = 720
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_child(left)
	var toolbar := HBoxContainer.new()
	left.add_child(toolbar)
	_add_label(toolbar, "Départ")
	campaign_start_node = OptionButton.new()
	campaign_start_node.custom_minimum_size.x = 190
	toolbar.add_child(campaign_start_node)
	var save_campaign := Button.new()
	save_campaign.text = "Enregistrer campagne"
	save_campaign.pressed.connect(_save_campaign_resource)
	toolbar.add_child(save_campaign)
	var validate := Button.new()
	validate.text = "✓ Valider graphe"
	validate.pressed.connect(_validate_campaign)
	toolbar.add_child(validate)

	var graph_scroll := ScrollContainer.new()
	graph_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	graph_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_child(graph_scroll)
	campaign_canvas = CampaignCanvas.new()
	campaign_canvas.node_selected.connect(_on_campaign_canvas_node_selected)
	campaign_canvas.node_moved.connect(_on_campaign_node_moved)
	graph_scroll.add_child(campaign_canvas)
	var graph_help := Label.new()
	graph_help.text = "Clique un nœud pour l'éditer • Glisse-le pour organiser le graphe • les flèches suivent les transitions."
	left.add_child(graph_help)

	var right_scroll := ScrollContainer.new()
	right_scroll.custom_minimum_size.x = 410
	root.add_child(right_scroll)
	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_scroll.add_child(right)
	var node_toolbar := HBoxContainer.new()
	right.add_child(node_toolbar)
	campaign_node_select = OptionButton.new()
	campaign_node_select.custom_minimum_size.x = 180
	campaign_node_select.item_selected.connect(_on_campaign_node_selected)
	node_toolbar.add_child(campaign_node_select)
	var add_mission := Button.new()
	add_mission.text = "+ Mission"
	add_mission.pressed.connect(_new_campaign_node.bind("mission"))
	node_toolbar.add_child(add_mission)
	var add_event := Button.new()
	add_event.text = "+ Event"
	add_event.pressed.connect(_new_campaign_node.bind("event"))
	node_toolbar.add_child(add_event)
	var add_end := Button.new()
	add_end.text = "+ Fin"
	add_end.pressed.connect(_new_campaign_node.bind("end"))
	node_toolbar.add_child(add_end)
	var duplicate := Button.new()
	duplicate.text = "Dupliquer"
	duplicate.pressed.connect(_duplicate_campaign_node)
	node_toolbar.add_child(duplicate)
	var delete_node := Button.new()
	delete_node.text = "Supprimer"
	delete_node.pressed.connect(_delete_campaign_node)
	node_toolbar.add_child(delete_node)

	campaign_title = _line_field(right, "Titre")
	campaign_body = _text_field(right, "Texte / dialogue", 90)
	_add_label(right, "Type")
	campaign_type = OptionButton.new()
	for value in CAMPAIGN_NODE_TYPES:
		campaign_type.add_item(value)
	right.add_child(campaign_type)
	_add_label(right, "Mission liée")
	campaign_mission = OptionButton.new()
	right.add_child(campaign_mission)
	_add_label(right, "Nœud suivant (mission)")
	campaign_next = OptionButton.new()
	right.add_child(campaign_next)
	campaign_victory_bonus = _spin_field(right, "Bonus Spores XP victoire", 0, 20)
	campaign_reward_pool = _line_field(right, "Relique(s) override, IDs séparés par virgules")

	_add_separator(right, "Conditions du nœud")
	campaign_min_spores = _spin_field(right, "Spores XP minimum", 0, 999)
	campaign_min_loop = _spin_field(right, "Tournée minimum", 0, 99)
	campaign_required_equipment = _line_field(right, "Relique requise (ID, vide = aucune)")
	_add_label(right, "Fallback si condition non remplie")
	campaign_fallback = OptionButton.new()
	right.add_child(campaign_fallback)

	_add_separator(right, "Choix A (Event)")
	campaign_choice_a_label = _line_field(right, "Texte du choix A")
	_add_label(right, "Destination A")
	campaign_choice_a_next = OptionButton.new()
	right.add_child(campaign_choice_a_next)
	_add_label(right, "Récompense A")
	campaign_choice_a_reward = OptionButton.new()
	for value in CAMPAIGN_REWARD_TYPES:
		campaign_choice_a_reward.add_item(value)
	right.add_child(campaign_choice_a_reward)
	campaign_choice_a_value = _spin_field(right, "Valeur A", 0, 20)

	_add_separator(right, "Choix B (Event)")
	campaign_choice_b_label = _line_field(right, "Texte du choix B")
	_add_label(right, "Destination B")
	campaign_choice_b_next = OptionButton.new()
	right.add_child(campaign_choice_b_next)
	_add_label(right, "Récompense B")
	campaign_choice_b_reward = OptionButton.new()
	for value in CAMPAIGN_REWARD_TYPES:
		campaign_choice_b_reward.add_item(value)
	right.add_child(campaign_choice_b_reward)
	campaign_choice_b_value = _spin_field(right, "Valeur B", 0, 20)

	var apply := Button.new()
	apply.text = "Appliquer au nœud"
	apply.pressed.connect(_apply_campaign_node_editor)
	right.add_child(apply)
	campaign_validation = Label.new()
	campaign_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	campaign_validation.custom_minimum_size.y = 120
	right.add_child(campaign_validation)


func _refresh_all() -> void:
	if dirty_mission or dirty_skill or dirty_status or dirty_campaign or dirty_ai or dirty_logic_mission:
		save_external_data()
	_refresh_ai_profiles()
	_refresh_vfx_selectors()
	_refresh_visual_selector()
	_refresh_statuses()
	_refresh_skills()
	_refresh_units()
	_refresh_missions()
	_refresh_campaign()
	_refresh_mission_logic_selector()
	if cinematic_editor != null:
		cinematic_editor.refresh()
	if visual_editor != null:
		visual_editor.refresh()
	if hero_customizer_editor != null:
		hero_customizer_editor.refresh()
	if vfx_editor != null:
		vfx_editor.refresh()
	if progression_editor != null:
		progression_editor.refresh()
	status_label.text = "Contenu V1.19 rechargé depuis res://data/."


func _resource_files(directory: String) -> Array[String]:
	var result: Array[String] = []
	var dir := DirAccess.open(directory)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(directory + file_name)
	result.sort()
	return result


# -----------------------------------------------------------------------------
# MAPS / MISSIONS
# -----------------------------------------------------------------------------

func _refresh_missions() -> void:
	var wanted := mission_path
	mission_select.clear()
	for path in _resource_files(MISSION_DIR):
		var data := load(path)
		mission_select.add_item("%s  [%s]" % [String(data.display_name), String(data.id)])
		mission_select.set_item_metadata(mission_select.item_count - 1, path)
	if mission_select.item_count > 0:
		var index := _metadata_index(mission_select, wanted)
		if index < 0:
			index = 0
		mission_select.select(index)
		_on_mission_selected(index)


func _on_mission_selected(index: int) -> void:
	if dirty_mission and mission_current != null and not mission_path.is_empty():
		ResourceSaver.save(mission_current, mission_path)
		dirty_mission = false
	if index < 0 or index >= mission_select.item_count:
		return
	mission_path = String(mission_select.get_item_metadata(index))
	mission_current = load(mission_path)
	mission_name.text = String(mission_current.display_name)
	mission_brief.text = String(mission_current.brief)
	mission_secondary.text = String(mission_current.secondary_objective)
	_select_text(mission_objective, String(mission_current.objective))
	mission_survival.value = int(mission_current.survival_rounds)
	mission_width.value = int(mission_current.grid_width)
	mission_height.value = int(mission_current.grid_height)
	var native_path: String = String(mission_current.get("map_scene_path"))
	if not native_path.is_empty() and ResourceLoader.exists(native_path):
		var native_scene: PackedScene = load(native_path) as PackedScene
		if native_scene != null:
			var native_root: Node = native_scene.instantiate()
			if native_root is SporeMap2D:
				mission_width.value = (native_root as SporeMap2D).grid_width
				mission_height.value = (native_root as SporeMap2D).grid_height
			elif native_root is SporeMap3D:
				mission_width.value = (native_root as SporeMap3D).grid_width
				mission_height.value = (native_root as SporeMap3D).grid_height
			native_root.free()
	map_history.clear()
	map_redo.clear()
	gesture_anchor = Vector2i(-1, -1)
	selected_spawn_index = -1
	_set_spawn_panel_enabled(false)
	map_canvas.set_mission(mission_current)
	map_canvas.clear_overlay()
	_validate_current_mission()
	_update_history_buttons()


func _new_mission() -> void:
	var new_id := _unique_resource_id(MISSION_DIR, "mission_new")
	var data: Resource = MissionDefinition.new()
	data.id = new_id
	data.display_name = "Nouvelle mission"
	data.brief = "Décris ici l'objectif de la mission."
	data.secondary_objective = "Objectif secondaire optionnel"
	data.objective = "eliminate"
	var template_id: String = "blank"
	if mission_template_select != null and mission_template_select.selected >= 0:
		template_id = String(mission_template_select.get_item_metadata(mission_template_select.selected))
	_apply_new_mission_template(data, template_id)
	var victory_rule: Resource = MissionRule.new()
	victory_rule.rule_type = "crown_extracted" if String(data.objective) == "crown" else "all_enemies_defeated"
	data.victory_rules.append(victory_rule)
	var defeat_rule: Resource = MissionRule.new()
	defeat_rule.rule_type = "all_players_defeated"
	data.defeat_rules.append(defeat_rule)
	var map_path: String = MAP_SCENE_DIR + new_id + "_map.tscn"
	data.map_scene_path = map_path
	_create_native_map_scene(data, map_path)
	var path: String = MISSION_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	_rescan_filesystem()
	mission_path = path
	_refresh_missions()
	status_label.text = "✓ Mission + scène 2D créées : %s" % new_id


func _apply_new_mission_template(data: Resource, template_id: String) -> void:
	data.obstacles.clear()
	data.cover.clear()
	data.hazards.clear()
	data.extraction.clear()
	data.bonus.clear()
	data.height_level_1.clear()
	data.height_level_2.clear()
	data.enemy_ids = PackedStringArray()
	data.enemy_positions.clear()
	data.enemy_roles = PackedStringArray()
	data.crown = Vector2i(-9, -9)
	match template_id:
		"skirmish":
			data.grid_width = 8
			data.grid_height = 8
			data.hero_starts = [Vector2i(0, 6), Vector2i(1, 6), Vector2i(0, 7)]
			data.cover = [Vector2i(2, 5), Vector2i(3, 3), Vector2i(5, 4)]
			data.obstacles = [Vector2i(3, 4), Vector2i(4, 3)]
			data.enemy_ids = PackedStringArray(["baveux", "grincheux"])
			data.enemy_positions = [Vector2i(6, 1), Vector2i(7, 2)]
		"objective":
			data.grid_width = 10
			data.grid_height = 8
			data.objective = "crown"
			data.hero_starts = [Vector2i(0, 6), Vector2i(1, 6), Vector2i(0, 7)]
			data.extraction = [Vector2i(0, 6), Vector2i(0, 7), Vector2i(1, 7)]
			data.crown = Vector2i(9, 0)
			data.cover = [Vector2i(2, 4), Vector2i(5, 3), Vector2i(7, 5)]
			data.enemy_ids = PackedStringArray(["baveux", "comptable", "grincheux"])
			data.enemy_positions = [Vector2i(7, 1), Vector2i(8, 3), Vector2i(6, 5)]
		"large":
			data.grid_width = 12
			data.grid_height = 10
			data.hero_starts = [Vector2i(0, 8), Vector2i(1, 8), Vector2i(0, 9)]
			data.cover = [Vector2i(3, 7), Vector2i(5, 5), Vector2i(7, 3), Vector2i(9, 6)]
			data.obstacles = [Vector2i(5, 4), Vector2i(6, 4), Vector2i(5, 6), Vector2i(6, 6)]
		_:
			data.grid_width = 10
			data.grid_height = 8
			data.hero_starts = [Vector2i(0, 6), Vector2i(1, 6), Vector2i(0, 7)]


func _duplicate_mission() -> void:
	if mission_current == null:
		return
	var new_id := _unique_resource_id(MISSION_DIR, String(mission_current.id) + "_copy")
	var copy: Resource = mission_current.duplicate(true)
	copy.id = new_id
	copy.display_name = String(mission_current.display_name) + " Copie"
	var new_map_path: String = MAP_SCENE_DIR + new_id + "_map.tscn"
	var source_map_path: String = String(mission_current.get("map_scene_path"))
	if not source_map_path.is_empty() and ResourceLoader.exists(source_map_path):
		_duplicate_native_map_scene(source_map_path, new_map_path, new_id)
	else:
		_create_native_map_scene(copy, new_map_path)
	copy.map_scene_path = new_map_path
	var path: String = MISSION_DIR + new_id + ".tres"
	ResourceSaver.save(copy, path)
	_rescan_filesystem()
	mission_path = path
	_refresh_missions()
	status_label.text = "✓ Mission + scène 2D dupliquées : %s" % new_id


func _open_current_native_map() -> void:
	if mission_current == null:
		return
	var map_path: String = String(mission_current.get("map_scene_path"))
	if map_path.is_empty() or not ResourceLoader.exists(map_path):
		map_path = MAP_SCENE_DIR + String(mission_current.id) + "_map.tscn"
		mission_current.map_scene_path = map_path
		_create_native_map_scene(mission_current, map_path)
		ResourceSaver.save(mission_current, mission_path)
		_rescan_filesystem()
	EditorInterface.open_scene_from_path(map_path)
	var workspace: String = _native_map_workspace(map_path)
	EditorInterface.set_main_screen_editor(workspace)
	status_label.text = "↗ Map ouverte dans l'éditeur %s natif : %s" % [workspace, map_path]


func _native_map_workspace(map_path: String) -> String:
	var packed: PackedScene = load(map_path) as PackedScene
	if packed == null:
		return "2D"
	var root: Node = packed.instantiate()
	if root == null:
		return "2D"
	var workspace: String = "3D" if root is Node3D else "2D"
	root.free()
	return workspace


func _create_native_map_scene(data: Resource, map_path: String) -> void:
	var map_root: SporeMap2D = Map2DDefinition.new() as SporeMap2D
	map_root.name = "%sMap" % String(data.id).to_pascal_case()
	map_root.grid_width = int(data.grid_width)
	map_root.grid_height = int(data.grid_height)
	map_root.cell_size = 64.0
	map_root.obstacles = data.obstacles.duplicate()
	map_root.cover = data.cover.duplicate()
	map_root.hazards = data.hazards.duplicate()
	map_root.extraction = data.extraction.duplicate()
	map_root.bonus = data.bonus.duplicate()
	map_root.crown = data.crown
	map_root.height_level_1 = data.height_level_1.duplicate()
	map_root.height_level_2 = data.height_level_2.duplicate()
	map_root.sync_legacy_to_native_layers(true)
	for index: int in range(data.hero_starts.size()):
		var hero_spawn: SporeHeroSpawn2D = HeroSpawn2DDefinition.new() as SporeHeroSpawn2D
		hero_spawn.name = "HeroSpawn%d" % (index + 1)
		hero_spawn.position = map_root.cell_to_local(data.hero_starts[index])
		hero_spawn.order = index
		map_root.add_child(hero_spawn)
		hero_spawn.owner = map_root
	var enemy_count: int = mini(data.enemy_ids.size(), data.enemy_positions.size())
	for index: int in range(enemy_count):
		var enemy_spawn: SporeEnemySpawn2D = EnemySpawn2DDefinition.new() as SporeEnemySpawn2D
		var unit_id: String = String(data.enemy_ids[index])
		enemy_spawn.name = "EnemySpawn_%s_%d" % [unit_id, index + 1]
		enemy_spawn.position = map_root.cell_to_local(data.enemy_positions[index])
		enemy_spawn.unit_id = unit_id
		if index < data.enemy_roles.size():
			enemy_spawn.role_override = String(data.enemy_roles[index])
		if index < data.enemy_hp_overrides.size():
			enemy_spawn.hp_override = int(data.enemy_hp_overrides[index])
		if index < data.enemy_attack_overrides.size():
			enemy_spawn.attack_override = int(data.enemy_attack_overrides[index])
		if index < data.enemy_move_overrides.size():
			enemy_spawn.move_override = int(data.enemy_move_overrides[index])
		if index < data.enemy_range_overrides.size():
			enemy_spawn.range_override = int(data.enemy_range_overrides[index])
		map_root.add_child(enemy_spawn)
		enemy_spawn.owner = map_root
	for raw_object: Variant in data.interactables:
		if not (raw_object is Resource):
			continue
		var object_def: Resource = raw_object as Resource
		var map_object: SporeMapInteractable2D = Interactable2DDefinition.new() as SporeMapInteractable2D
		map_object.name = String(object_def.id).to_pascal_case()
		map_object.position = map_root.cell_to_local(object_def.cell)
		map_object.object_id = String(object_def.id)
		map_object.display_name = String(object_def.display_name)
		map_object.object_type = String(object_def.object_type)
		map_object.linked_object_id = String(object_def.linked_object_id)
		map_object.starts_active = bool(object_def.starts_active)
		map_object.one_shot = bool(object_def.one_shot)
		map_object.reward_type = String(object_def.reward_type)
		map_object.reward_value = int(object_def.reward_value)
		map_object.reward_team = String(object_def.reward_team)
		map_root.add_child(map_object)
		map_object.owner = map_root
	var packed: PackedScene = PackedScene.new()
	var error: Error = packed.pack(map_root)
	if error == OK:
		ResourceSaver.save(packed, map_path)
	else:
		push_error("Impossible de créer la scène de map %s : %s" % [map_path, error])
	map_root.free()


func _duplicate_native_map_scene(source_path: String, target_path: String, new_id: String) -> void:
	var packed_source: PackedScene = load(source_path) as PackedScene
	if packed_source == null:
		return
	var root: Node = packed_source.instantiate()
	if root == null:
		return
	root.name = "%sMap" % new_id.to_pascal_case()
	var packed_target: PackedScene = PackedScene.new()
	var error: Error = packed_target.pack(root)
	if error == OK:
		ResourceSaver.save(packed_target, target_path)
	else:
		push_error("Impossible de dupliquer la scène de map : %s" % error)
	root.free()


func _save_mission() -> void:
	if mission_current == null:
		return
	mission_current.display_name = mission_name.text.strip_edges()
	mission_current.brief = mission_brief.text.strip_edges()
	mission_current.secondary_objective = mission_secondary.text.strip_edges()
	mission_current.objective = mission_objective.get_item_text(mission_objective.selected)
	mission_current.survival_rounds = int(mission_survival.value)
	var error := ResourceSaver.save(mission_current, mission_path)
	dirty_mission = false
	_validate_current_mission()
	status_label.text = "✓ Mission enregistrée : %s" % mission_path if error == OK else "⚠ Erreur de sauvegarde : %s" % error


func _resize_mission() -> void:
	if mission_current == null:
		return
	var native_path: String = String(mission_current.get("map_scene_path"))
	if not native_path.is_empty() and ResourceLoader.exists(native_path):
		status_label.text = "La taille se modifie sur le nœud racine de la map dans l'Inspecteur Godot."
		_open_current_native_map()
		return
	var before := _mission_snapshot()
	mission_current.grid_width = int(mission_width.value)
	mission_current.grid_height = int(mission_height.value)
	_prune_out_of_bounds()
	_commit_map_action("Redimensionner la map", before)
	map_canvas.queue_redraw()
	_validate_current_mission()


func _on_tool_selected(index: int) -> void:
	if index < 0:
		return
	var tool := String(tool_select.get_item_metadata(index))
	map_canvas.set_tool(tool)
	enemy_select.visible = tool == "enemy"
	gesture_anchor = Vector2i(-1, -1)
	map_canvas.clear_overlay()


func _on_map_mode_selected(_index: int) -> void:
	gesture_anchor = Vector2i(-1, -1)
	map_canvas.clear_overlay()


func _map_tool() -> String:
	return String(tool_select.get_item_metadata(tool_select.selected))


func _map_mode() -> String:
	return String(map_mode_select.get_item_metadata(map_mode_select.selected))


func _on_map_cell_pressed(cell: Vector2i, mouse_button: int) -> void:
	if mission_current == null:
		return
	if mouse_button == MOUSE_BUTTON_RIGHT:
		var before := _mission_snapshot()
		_apply_map_tool("erase", cell)
		_commit_map_action("Effacer case", before)
		map_canvas.queue_redraw()
		return

	var mode := _map_mode()
	if mode == "brush":
		if _map_tool() == "spawn_select":
			_select_spawn_at(cell)
			return
		stroke_before = _mission_snapshot()
		stroke_active = true
		_apply_map_tool(_map_tool(), cell)
		mission_current.emit_changed()
		map_canvas.queue_redraw()
	elif mode == "rectangle":
		_handle_rectangle_click(cell)
	elif mode == "fill":
		_handle_fill(cell)
	elif mode == "copy":
		_handle_copy_click(cell)
	elif mode == "paste":
		_paste_clipboard(cell)


func _on_map_cell_dragged(cell: Vector2i, mouse_button: int) -> void:
	if not stroke_active or _map_mode() != "brush" or mouse_button != MOUSE_BUTTON_LEFT:
		return
	if _map_tool() == "spawn_select":
		return
	_apply_map_tool(_map_tool(), cell)
	mission_current.emit_changed()
	map_canvas.queue_redraw()


func _on_map_cell_released(_cell: Vector2i, mouse_button: int) -> void:
	if mouse_button != MOUSE_BUTTON_LEFT or not stroke_active:
		return
	stroke_active = false
	_commit_map_action("Peindre la map", stroke_before)
	stroke_before = {}


func _handle_rectangle_click(cell: Vector2i) -> void:
	if gesture_anchor.x < 0:
		gesture_anchor = cell
		map_canvas.set_overlay([cell])
		status_label.text = "Rectangle : choisis le coin opposé."
		return
	var cells := _rect_cells(gesture_anchor, cell)
	var before := _mission_snapshot()
	for target in cells:
		_apply_map_tool(_map_tool(), target)
	_commit_map_action("Peindre rectangle", before)
	gesture_anchor = Vector2i(-1, -1)
	map_canvas.clear_overlay()
	map_canvas.queue_redraw()


func _handle_fill(cell: Vector2i) -> void:
	var tool := _map_tool()
	if tool not in ["obstacle", "cover", "hazard", "ground", "erase", "height0", "height1", "height2"]:
		status_label.text = "⚠ Remplir fonctionne avec terrain, hauteur, sol ou gomme."
		return
	var source_kind := _tile_kind(cell)
	var pending: Array[Vector2i] = [cell]
	var visited: Dictionary = {}
	var region: Array[Vector2i] = []
	while not pending.is_empty():
		var current: Vector2i = pending.pop_back()
		if visited.has(current) or not _cell_in_bounds(current):
			continue
		visited[current] = true
		if _tile_kind(current) != source_kind:
			continue
		region.append(current)
		pending.append(current + Vector2i(1, 0))
		pending.append(current + Vector2i(-1, 0))
		pending.append(current + Vector2i(0, 1))
		pending.append(current + Vector2i(0, -1))
	var before := _mission_snapshot()
	for target in region:
		_apply_map_tool(tool, target)
	_commit_map_action("Remplir zone", before)
	map_canvas.queue_redraw()
	status_label.text = "✓ Remplissage : %d cases." % region.size()


func _handle_copy_click(cell: Vector2i) -> void:
	if gesture_anchor.x < 0:
		gesture_anchor = cell
		map_canvas.set_overlay([cell], Color(0.38, 0.75, 1.0, 0.22))
		status_label.text = "Copier zone : choisis le coin opposé."
		return
	var cells := _rect_cells(gesture_anchor, cell)
	clipboard = _build_clipboard(gesture_anchor, cell)
	map_canvas.set_overlay(cells, Color(0.38, 0.75, 1.0, 0.22))
	gesture_anchor = Vector2i(-1, -1)
	_select_metadata(map_mode_select, "paste")
	status_label.text = "✓ Zone copiée (%dx%d). Clique pour la coller." % [int(clipboard.get("width", 0)), int(clipboard.get("height", 0))]


func _paste_clipboard(origin: Vector2i) -> void:
	if clipboard.is_empty():
		status_label.text = "⚠ Rien à coller. Utilise d'abord Copier zone."
		return
	var before := _mission_snapshot()
	var width := int(clipboard.get("width", 0))
	var height := int(clipboard.get("height", 0))
	for y in range(height):
		for x in range(width):
			var target := origin + Vector2i(x, y)
			if _cell_in_bounds(target):
				_clear_cell(target)
	for entry in clipboard.get("cells", []):
		var target: Vector2i = origin + entry["offset"]
		if not _cell_in_bounds(target):
			continue
		_restore_clipboard_cell(target, entry)
	_commit_map_action("Coller zone", before)
	map_canvas.queue_redraw()


func _build_clipboard(a: Vector2i, b: Vector2i) -> Dictionary:
	var min_x: int = mini(a.x, b.x)
	var min_y: int = mini(a.y, b.y)
	var max_x: int = maxi(a.x, b.x)
	var max_y: int = maxi(a.y, b.y)
	var cells: Array = []
	for y in range(min_y, max_y + 1):
		for x in range(min_x, max_x + 1):
			var cell := Vector2i(x, y)
			var entry := {
				"offset": Vector2i(x - min_x, y - min_y),
				"obstacle": mission_current.obstacles.has(cell),
				"cover": mission_current.cover.has(cell),
				"hazard": mission_current.hazards.has(cell),
				"extraction": mission_current.extraction.has(cell),
				"bonus": mission_current.bonus.has(cell),
				"crown": mission_current.crown == cell,
				"height": 2 if mission_current.height_level_2.has(cell) else (1 if mission_current.height_level_1.has(cell) else 0),
				"hero": mission_current.hero_starts.has(cell),
				"enemy": _enemy_spawn_at(cell),
			}
			cells.append(entry)
	return {"width": max_x - min_x + 1, "height": max_y - min_y + 1, "cells": cells}


func _restore_clipboard_cell(cell: Vector2i, entry: Dictionary) -> void:
	if bool(entry.get("obstacle", false)):
		mission_current.obstacles.append(cell)
	elif bool(entry.get("cover", false)):
		mission_current.cover.append(cell)
	elif bool(entry.get("hazard", false)):
		mission_current.hazards.append(cell)
	if bool(entry.get("extraction", false)):
		mission_current.extraction.append(cell)
	if bool(entry.get("bonus", false)):
		mission_current.bonus.append(cell)
	if bool(entry.get("crown", false)):
		mission_current.crown = cell
	var height := int(entry.get("height", 0))
	if height == 1:
		mission_current.height_level_1.append(cell)
	elif height == 2:
		mission_current.height_level_2.append(cell)
	if bool(entry.get("hero", false)):
		mission_current.hero_starts.append(cell)
	var enemy: Dictionary = entry.get("enemy", {})
	if not enemy.is_empty():
		_append_enemy_spawn(cell, enemy)


func _rect_cells(a: Vector2i, b: Vector2i) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	for y in range(min(a.y, b.y), max(a.y, b.y) + 1):
		for x in range(min(a.x, b.x), max(a.x, b.x) + 1):
			result.append(Vector2i(x, y))
	return result


func _tile_kind(cell: Vector2i) -> String:
	if mission_current.obstacles.has(cell):
		return "obstacle"
	if mission_current.cover.has(cell):
		return "cover"
	if mission_current.hazards.has(cell):
		return "hazard"
	return "ground"


func _apply_map_tool(tool: String, cell: Vector2i) -> void:
	match tool:
		"obstacle", "cover", "hazard":
			_remove_from_array(mission_current.obstacles, cell)
			_remove_from_array(mission_current.cover, cell)
			_remove_from_array(mission_current.hazards, cell)
			if tool == "obstacle":
				mission_current.obstacles.append(cell)
			elif tool == "cover":
				mission_current.cover.append(cell)
			else:
				mission_current.hazards.append(cell)
		"extraction":
			_toggle_cell(mission_current.extraction, cell, true)
		"bonus":
			_toggle_cell(mission_current.bonus, cell, true)
		"crown":
			mission_current.crown = cell
		"height0":
			_remove_from_array(mission_current.height_level_1, cell)
			_remove_from_array(mission_current.height_level_2, cell)
		"height1":
			_remove_from_array(mission_current.height_level_2, cell)
			if not mission_current.height_level_1.has(cell):
				mission_current.height_level_1.append(cell)
		"height2":
			_remove_from_array(mission_current.height_level_1, cell)
			if not mission_current.height_level_2.has(cell):
				mission_current.height_level_2.append(cell)
		"hero":
			if not mission_current.hero_starts.has(cell):
				mission_current.hero_starts.append(cell)
		"enemy":
			_remove_enemy_at(cell)
			if enemy_select.item_count > 0:
				_append_enemy_spawn(cell, {"id": String(enemy_select.get_item_metadata(enemy_select.selected)), "role": "", "hp": -1, "attack": -1, "move": -1, "range": -1})
		"door", "switch", "chest":
			_remove_interactable_at(cell)
			_add_interactable_at(cell, tool)
		"spawn_select":
			_select_spawn_at(cell)
		"ground":
			_remove_from_array(mission_current.obstacles, cell)
			_remove_from_array(mission_current.cover, cell)
			_remove_from_array(mission_current.hazards, cell)
		"erase":
			_clear_cell(cell)


func _clear_cell(cell: Vector2i) -> void:
	_remove_from_array(mission_current.obstacles, cell)
	_remove_from_array(mission_current.cover, cell)
	_remove_from_array(mission_current.hazards, cell)
	_remove_from_array(mission_current.extraction, cell)
	_remove_from_array(mission_current.bonus, cell)
	_remove_from_array(mission_current.height_level_1, cell)
	_remove_from_array(mission_current.height_level_2, cell)
	_remove_from_array(mission_current.hero_starts, cell)
	_remove_enemy_at(cell)
	_remove_interactable_at(cell)
	if mission_current.crown == cell:
		mission_current.crown = Vector2i(-9, -9)


func _add_interactable_at(cell: Vector2i, object_type: String) -> void:
	var object_def: Resource = MapInteractableDefinition.new()
	var used: Dictionary = {}
	for existing in mission_current.interactables:
		if existing != null:
			used[String(existing.id)] = true
	var base := object_type
	var candidate := base
	var suffix := 2
	while used.has(candidate):
		candidate = "%s_%d" % [base, suffix]
		suffix += 1
	object_def.id = candidate
	object_def.display_name = object_type.capitalize()
	object_def.object_type = object_type
	object_def.cell = cell
	if object_type == "chest":
		object_def.reward_type = "focus_team"
		object_def.reward_value = 1
	mission_current.interactables.append(object_def)


func _remove_interactable_at(cell: Vector2i) -> void:
	for index in range(mission_current.interactables.size() - 1, -1, -1):
		var object_def = mission_current.interactables[index]
		if object_def != null and object_def.cell == cell:
			mission_current.interactables.remove_at(index)


func _select_spawn_at(cell: Vector2i) -> void:
	selected_spawn_index = -1
	for index in range(mission_current.enemy_positions.size()):
		if mission_current.enemy_positions[index] == cell:
			selected_spawn_index = index
			break
	if selected_spawn_index < 0:
		_set_spawn_panel_enabled(false)
		map_canvas.set_selected_spawn(Vector2i(-999, -999))
		status_label.text = "Aucun spawn ennemi sur cette case."
		return
	_set_spawn_panel_enabled(true)
	map_canvas.set_selected_spawn(cell)
	var unit_id := String(mission_current.enemy_ids[selected_spawn_index])
	_select_metadata(spawn_unit, unit_id)
	spawn_role.text = String(mission_current.enemy_roles[selected_spawn_index]) if selected_spawn_index < mission_current.enemy_roles.size() else ""
	spawn_hp.value = int(mission_current.enemy_hp_overrides[selected_spawn_index]) if selected_spawn_index < mission_current.enemy_hp_overrides.size() else -1
	spawn_attack.value = int(mission_current.enemy_attack_overrides[selected_spawn_index]) if selected_spawn_index < mission_current.enemy_attack_overrides.size() else -1
	spawn_move.value = int(mission_current.enemy_move_overrides[selected_spawn_index]) if selected_spawn_index < mission_current.enemy_move_overrides.size() else -1
	spawn_range.value = int(mission_current.enemy_range_overrides[selected_spawn_index]) if selected_spawn_index < mission_current.enemy_range_overrides.size() else -1
	status_label.text = "Spawn sélectionné : %s" % unit_id


func _apply_spawn_inspector() -> void:
	if selected_spawn_index < 0 or selected_spawn_index >= mission_current.enemy_positions.size():
		return
	var before := _mission_snapshot()
	_ensure_spawn_parallel_arrays()
	mission_current.enemy_ids[selected_spawn_index] = String(spawn_unit.get_item_metadata(spawn_unit.selected))
	mission_current.enemy_roles[selected_spawn_index] = spawn_role.text.strip_edges()
	mission_current.enemy_hp_overrides[selected_spawn_index] = int(spawn_hp.value)
	mission_current.enemy_attack_overrides[selected_spawn_index] = int(spawn_attack.value)
	mission_current.enemy_move_overrides[selected_spawn_index] = int(spawn_move.value)
	mission_current.enemy_range_overrides[selected_spawn_index] = int(spawn_range.value)
	_commit_map_action("Modifier spawn ennemi", before)
	map_canvas.queue_redraw()
	_validate_current_mission()


func _delete_selected_spawn() -> void:
	if selected_spawn_index < 0 or selected_spawn_index >= mission_current.enemy_positions.size():
		return
	var before := _mission_snapshot()
	_remove_enemy_index(selected_spawn_index)
	selected_spawn_index = -1
	_set_spawn_panel_enabled(false)
	map_canvas.set_selected_spawn(Vector2i(-999, -999))
	_commit_map_action("Supprimer spawn ennemi", before)
	map_canvas.queue_redraw()


func _set_spawn_panel_enabled(enabled: bool) -> void:
	if spawn_panel == null:
		return
	for child in spawn_panel.get_children():
		if child is Control:
			child.mouse_filter = Control.MOUSE_FILTER_STOP if enabled else Control.MOUSE_FILTER_IGNORE
			child.modulate = Color.WHITE if enabled else Color(1, 1, 1, 0.45)


func _enemy_spawn_at(cell: Vector2i) -> Dictionary:
	for index in range(mission_current.enemy_positions.size()):
		if mission_current.enemy_positions[index] == cell:
			_ensure_spawn_parallel_arrays()
			return {
				"id": String(mission_current.enemy_ids[index]),
				"role": String(mission_current.enemy_roles[index]),
				"hp": int(mission_current.enemy_hp_overrides[index]),
				"attack": int(mission_current.enemy_attack_overrides[index]),
				"move": int(mission_current.enemy_move_overrides[index]),
				"range": int(mission_current.enemy_range_overrides[index]),
			}
	return {}


func _append_enemy_spawn(cell: Vector2i, data: Dictionary) -> void:
	mission_current.enemy_ids.append(String(data.get("id", "baveux")))
	mission_current.enemy_positions.append(cell)
	mission_current.enemy_roles.append(String(data.get("role", "")))
	mission_current.enemy_hp_overrides.append(int(data.get("hp", -1)))
	mission_current.enemy_attack_overrides.append(int(data.get("attack", -1)))
	mission_current.enemy_move_overrides.append(int(data.get("move", -1)))
	mission_current.enemy_range_overrides.append(int(data.get("range", -1)))


func _ensure_spawn_parallel_arrays() -> void:
	var count := mission_current.enemy_positions.size()
	while mission_current.enemy_ids.size() < count:
		mission_current.enemy_ids.append("baveux")
	while mission_current.enemy_roles.size() < count:
		mission_current.enemy_roles.append("")
	while mission_current.enemy_hp_overrides.size() < count:
		mission_current.enemy_hp_overrides.append(-1)
	while mission_current.enemy_attack_overrides.size() < count:
		mission_current.enemy_attack_overrides.append(-1)
	while mission_current.enemy_move_overrides.size() < count:
		mission_current.enemy_move_overrides.append(-1)
	while mission_current.enemy_range_overrides.size() < count:
		mission_current.enemy_range_overrides.append(-1)


func _remove_enemy_at(cell: Vector2i) -> void:
	for index in range(mission_current.enemy_positions.size() - 1, -1, -1):
		if mission_current.enemy_positions[index] == cell:
			_remove_enemy_index(index)


func _remove_enemy_index(index: int) -> void:
	if index < mission_current.enemy_positions.size():
		mission_current.enemy_positions.remove_at(index)
	if index < mission_current.enemy_ids.size():
		mission_current.enemy_ids.remove_at(index)
	if index < mission_current.enemy_roles.size():
		mission_current.enemy_roles.remove_at(index)
	if index < mission_current.enemy_hp_overrides.size():
		mission_current.enemy_hp_overrides.remove_at(index)
	if index < mission_current.enemy_attack_overrides.size():
		mission_current.enemy_attack_overrides.remove_at(index)
	if index < mission_current.enemy_move_overrides.size():
		mission_current.enemy_move_overrides.remove_at(index)
	if index < mission_current.enemy_range_overrides.size():
		mission_current.enemy_range_overrides.remove_at(index)


func _interactable_snapshots() -> Array:
	var result: Array = []
	for object_def in mission_current.interactables:
		if object_def == null:
			continue
		result.append({
			"id": String(object_def.id),
			"display_name": String(object_def.display_name),
			"object_type": String(object_def.object_type),
			"cell": object_def.cell,
			"linked_object_id": String(object_def.linked_object_id),
			"starts_active": bool(object_def.starts_active),
			"one_shot": bool(object_def.one_shot),
			"reward_type": String(object_def.reward_type),
			"reward_value": int(object_def.reward_value),
			"reward_team": String(object_def.reward_team),
		})
	return result


func _restore_interactable_snapshots(values: Array) -> void:
	var restored: Array[Resource] = []
	for data in values:
		var object_def: Resource = MapInteractableDefinition.new()
		object_def.id = String(data.get("id", "object"))
		object_def.display_name = String(data.get("display_name", "Objet"))
		object_def.object_type = String(data.get("object_type", "door"))
		object_def.cell = data.get("cell", Vector2i.ZERO)
		object_def.linked_object_id = String(data.get("linked_object_id", ""))
		object_def.starts_active = bool(data.get("starts_active", false))
		object_def.one_shot = bool(data.get("one_shot", true))
		object_def.reward_type = String(data.get("reward_type", "none"))
		object_def.reward_value = int(data.get("reward_value", 1))
		object_def.reward_team = String(data.get("reward_team", "player"))
		restored.append(object_def)
	mission_current.interactables = restored


func _mission_snapshot() -> Dictionary:
	if mission_current == null:
		return {}
	return {
		"grid_width": int(mission_current.grid_width),
		"grid_height": int(mission_current.grid_height),
		"obstacles": mission_current.obstacles.duplicate(),
		"cover": mission_current.cover.duplicate(),
		"hazards": mission_current.hazards.duplicate(),
		"extraction": mission_current.extraction.duplicate(),
		"bonus": mission_current.bonus.duplicate(),
		"crown": mission_current.crown,
		"height1": mission_current.height_level_1.duplicate(),
		"height2": mission_current.height_level_2.duplicate(),
		"heroes": mission_current.hero_starts.duplicate(),
		"enemy_ids": mission_current.enemy_ids.duplicate(),
		"enemy_positions": mission_current.enemy_positions.duplicate(),
		"enemy_roles": mission_current.enemy_roles.duplicate(),
		"enemy_hp": mission_current.enemy_hp_overrides.duplicate(),
		"enemy_attack": mission_current.enemy_attack_overrides.duplicate(),
		"enemy_move": mission_current.enemy_move_overrides.duplicate(),
		"enemy_range": mission_current.enemy_range_overrides.duplicate(),
		"interactables": _interactable_snapshots(),
	}


func _restore_mission_snapshot(snapshot: Dictionary) -> void:
	if mission_current == null or snapshot.is_empty():
		return
	mission_current.grid_width = int(snapshot["grid_width"])
	mission_current.grid_height = int(snapshot["grid_height"])
	mission_current.obstacles = snapshot["obstacles"].duplicate()
	mission_current.cover = snapshot["cover"].duplicate()
	mission_current.hazards = snapshot["hazards"].duplicate()
	mission_current.extraction = snapshot["extraction"].duplicate()
	mission_current.bonus = snapshot["bonus"].duplicate()
	mission_current.crown = snapshot["crown"]
	mission_current.height_level_1 = snapshot["height1"].duplicate()
	mission_current.height_level_2 = snapshot["height2"].duplicate()
	mission_current.hero_starts = snapshot["heroes"].duplicate()
	mission_current.enemy_ids = snapshot["enemy_ids"].duplicate()
	mission_current.enemy_positions = snapshot["enemy_positions"].duplicate()
	mission_current.enemy_roles = snapshot["enemy_roles"].duplicate()
	mission_current.enemy_hp_overrides = snapshot["enemy_hp"].duplicate()
	mission_current.enemy_attack_overrides = snapshot["enemy_attack"].duplicate()
	mission_current.enemy_move_overrides = snapshot["enemy_move"].duplicate()
	mission_current.enemy_range_overrides = snapshot["enemy_range"].duplicate()
	_restore_interactable_snapshots(snapshot.get("interactables", []))
	mission_width.value = int(mission_current.grid_width)
	mission_height.value = int(mission_current.grid_height)
	selected_spawn_index = -1
	_set_spawn_panel_enabled(false)
	map_canvas.set_selected_spawn(Vector2i(-999, -999))
	mission_current.emit_changed()
	map_canvas.queue_redraw()
	_validate_current_mission()


func _commit_map_action(label: String, before: Dictionary) -> void:
	var after := _mission_snapshot()
	if before == after:
		return
	map_history.append({"label": label, "before": before, "after": after})
	if map_history.size() > 80:
		map_history.pop_front()
	map_redo.clear()
	_mark_mission_dirty()
	_update_history_buttons()
	_validate_current_mission()


func _undo_map() -> void:
	if mission_current == null or map_history.is_empty():
		return
	var action: Dictionary = map_history.pop_back()
	map_redo.append(action)
	_restore_mission_snapshot(action["before"])
	_mark_mission_dirty()
	status_label.text = "↶ %s" % String(action["label"])
	_update_history_buttons()


func _redo_map() -> void:
	if mission_current == null or map_redo.is_empty():
		return
	var action: Dictionary = map_redo.pop_back()
	map_history.append(action)
	_restore_mission_snapshot(action["after"])
	_mark_mission_dirty()
	status_label.text = "↷ %s" % String(action["label"])
	_update_history_buttons()


func _update_history_buttons() -> void:
	if undo_button != null:
		undo_button.disabled = map_history.is_empty()
		undo_button.tooltip_text = "Annuler" if map_history.is_empty() else "Annuler : %s" % String(map_history[-1]["label"])
	if redo_button != null:
		redo_button.disabled = map_redo.is_empty()
		redo_button.tooltip_text = "Rétablir" if map_redo.is_empty() else "Rétablir : %s" % String(map_redo[-1]["label"])


func _prune_out_of_bounds() -> void:
	for property_name in ["obstacles", "cover", "hazards", "extraction", "bonus", "height_level_1", "height_level_2", "hero_starts"]:
		var cells: Array = mission_current.get(property_name)
		for index in range(cells.size() - 1, -1, -1):
			if not _cell_in_bounds(cells[index]):
				cells.remove_at(index)
	for index in range(mission_current.enemy_positions.size() - 1, -1, -1):
		if not _cell_in_bounds(mission_current.enemy_positions[index]):
			_remove_enemy_index(index)
	for index in range(mission_current.interactables.size() - 1, -1, -1):
		var object_def = mission_current.interactables[index]
		if object_def == null or not _cell_in_bounds(object_def.cell):
			mission_current.interactables.remove_at(index)
	if not _cell_in_bounds(mission_current.crown):
		mission_current.crown = Vector2i(-9, -9)


func _validate_current_mission() -> void:
	if mission_current == null:
		return
	var native_path: String = String(mission_current.get("map_scene_path"))
	if not native_path.is_empty() and ResourceLoader.exists(native_path):
		var packed: PackedScene = load(native_path) as PackedScene
		if packed == null:
			map_validation.text = "⚠ Impossible de charger la scène de map native."
			return
		var root: Node = packed.instantiate()
		if not (root is SporeMap2D):
			map_validation.text = "⚠ La scène doit avoir un SporeMap2D en racine."
			root.free()
			return
		var native_map: SporeMap2D = root as SporeMap2D
		var issues: PackedStringArray = native_map.validate_map()
		var hero_cells: Array[Vector2i] = native_map.hero_start_cells()
		var enemy_data: Array[Dictionary] = native_map.enemy_spawn_data()
		var native_environment: Dictionary = native_map.to_environment()
		if hero_cells.size() < 3:
			issues.append("Il faut au moins 3 spawns héros.")
		if enemy_data.is_empty():
			issues.append("Aucun ennemi placé.")
		if String(mission_current.objective) == "crown":
			var native_crown: Vector2i = native_environment.get("crown", Vector2i(-9, -9))
			var native_extraction: Array = native_environment.get("extraction", [])
			if not native_map.is_cell_valid(native_crown):
				issues.append("La Couronne doit être placée sur la grille.")
			if native_extraction.is_empty():
				issues.append("Une mission Couronne nécessite une zone d'extraction.")
		for spawn: Dictionary in enemy_data:
			var unit_id: String = String(spawn.get("unit_id", ""))
			if not ResourceLoader.exists(UNIT_DIR + unit_id + ".tres"):
				issues.append("Spawn vers unité inconnue : %s" % unit_id)
		var object_count: int = native_map.interactable_definitions().size()
		var zone_count: int = native_map.zone_definitions().size()
		if issues.is_empty():
			var native_obstacles: Array = native_environment.get("obstacles", [])
			var native_cover: Array = native_environment.get("cover", [])
			map_validation.text = "✓ MAP TILEMAP OK\n%d héros • %d ennemis • %d obstacles • %d couvertures • %d objets • %d zones\n%s" % [hero_cells.size(), enemy_data.size(), native_obstacles.size(), native_cover.size(), object_count, zone_count, native_path]
			map_validation.add_theme_color_override("font_color", Color("#8fe0ad"))
		else:
			map_validation.text = "⚠ VALIDATION MAP NATIVE\n• " + "\n• ".join(issues)
			map_validation.add_theme_color_override("font_color", Color("#ffb36b"))
		root.free()
		return

	# Fallback pour les anciennes missions sans scène native.
	var legacy_issues: Array[String] = []
	if mission_current.hero_starts.size() < 3:
		legacy_issues.append("Il faut au moins 3 spawns héros.")
	if mission_current.enemy_positions.is_empty():
		legacy_issues.append("Aucun ennemi placé.")
	if legacy_issues.is_empty():
		map_validation.text = "✓ Mission legacy valide — ouvre-la en 2D pour la migrer en scène native."
		map_validation.add_theme_color_override("font_color", Color("#8fe0ad"))
	else:
		map_validation.text = "⚠ VALIDATION LEGACY\n• " + "\n• ".join(legacy_issues)
		map_validation.add_theme_color_override("font_color", Color("#ffb36b"))


func _test_current_mission() -> void:
	if mission_current == null:
		return
	_save_mission()
	# La scène native est la source de vérité : sauvegarder les scènes ouvertes avant le playtest.
	EditorInterface.save_all_scenes()
	var file: FileAccess = FileAccess.open("user://sporebound_editor_test.json", FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify({"mission_id": String(mission_current.id), "mission_path": mission_path}))
		file.close()
	status_label.text = "▶ Lancement de %s en mode test…" % String(mission_current.display_name)
	if editor_plugin != null:
		editor_plugin.get_editor_interface().play_main_scene()


func _test_current_mission_direct() -> void:
	if mission_current == null:
		return
	_save_mission()
	EditorInterface.save_all_scenes()
	var file: FileAccess = FileAccess.open("user://sporebound_editor_test.json", FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify({
			"mission_id": String(mission_current.id),
			"mission_path": mission_path,
			"autostart": true,
		}))
		file.close()
	status_label.text = "▶ Playtest direct : %s" % String(mission_current.display_name)
	if editor_plugin != null:
		editor_plugin.get_editor_interface().play_main_scene()


func _refresh_visual_selector() -> void:
	if unit_visual == null:
		return
	var wanted = unit_visual.get_item_metadata(unit_visual.selected) if unit_visual.item_count > 0 else ""
	unit_visual.clear()
	unit_visual.add_item("— auto / id unité —")
	unit_visual.set_item_metadata(0, "")
	for path in _resource_files(VISUAL_DIR):
		var data := load(path)
		unit_visual.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		unit_visual.set_item_metadata(unit_visual.item_count - 1, String(data.id))
	_select_metadata(unit_visual, wanted)


func _refresh_vfx_selectors() -> void:
	for option in [skill_vfx, status_vfx]:
		if option == null:
			continue
		var wanted = option.get_item_metadata(option.selected) if option.item_count > 0 else ""
		option.clear()
		option.add_item("— aucun / défaut —")
		option.set_item_metadata(0, "")
		for path in _resource_files(VFX_DIR):
			var data := load(path)
			option.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
			option.set_item_metadata(option.item_count - 1, String(data.id))
		_select_metadata(option, wanted)


# -----------------------------------------------------------------------------
# UNITS
# -----------------------------------------------------------------------------

func _refresh_units() -> void:
	var wanted := unit_path
	unit_select.clear()
	for path in _resource_files(UNIT_DIR):
		var data := load(path)
		unit_select.add_item("%s  [%s]" % [String(data.display_name), String(data.id)])
		unit_select.set_item_metadata(unit_select.item_count - 1, path)
	_refresh_enemy_selectors()
	_refresh_unit_skill_selectors()
	_refresh_unit_ai_selector()
	_refresh_unit_job_selectors()
	_refresh_visual_selector()
	if unit_select.item_count > 0:
		var index := _metadata_index(unit_select, wanted)
		if index < 0:
			index = 0
		unit_select.select(index)
		_on_unit_selected(index)


func _refresh_enemy_selectors() -> void:
	for option in [enemy_select, spawn_unit]:
		if option == null:
			continue
		var wanted = option.get_item_metadata(option.selected) if option.item_count > 0 else ""
		option.clear()
		for path in _resource_files(UNIT_DIR):
			var data := load(path)
			if String(data.team) != "enemy":
				continue
			option.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
			option.set_item_metadata(option.item_count - 1, String(data.id))
		_select_metadata(option, wanted)


func _refresh_unit_skill_selectors() -> void:
	for option in [unit_primary, unit_secondary]:
		if option == null:
			continue
		var wanted = option.get_item_metadata(option.selected) if option.item_count > 0 else ""
		option.clear()
		option.add_item("— aucune —")
		option.set_item_metadata(0, "")
		for path in _resource_files(SKILL_DIR):
			var data := load(path)
			option.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
			option.set_item_metadata(option.item_count - 1, String(data.id))
		_select_metadata(option, wanted)


func _refresh_unit_ai_selector() -> void:
	if unit_ai == null:
		return
	var wanted = unit_ai.get_item_metadata(unit_ai.selected) if unit_ai.item_count > 0 else ""
	unit_ai.clear()
	for path in _resource_files(AI_DIR):
		var data := load(path)
		unit_ai.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		unit_ai.set_item_metadata(unit_ai.item_count - 1, String(data.id))
	_select_metadata(unit_ai, wanted)


func _refresh_unit_job_selectors() -> void:
	if unit_default_job == null or unit_available_jobs == null:
		return
	var wanted_default = unit_default_job.get_item_metadata(unit_default_job.selected) if unit_default_job.item_count > 0 else ""
	unit_default_job.clear()
	unit_default_job.add_item("— aucun —")
	unit_default_job.set_item_metadata(0, "")
	unit_available_jobs.clear()
	for path in _resource_files(JOB_DIR):
		var data := load(path)
		unit_default_job.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		unit_default_job.set_item_metadata(unit_default_job.item_count - 1, String(data.id))
		unit_available_jobs.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		unit_available_jobs.set_item_metadata(unit_available_jobs.item_count - 1, String(data.id))
	_select_metadata(unit_default_job, wanted_default)


func _on_unit_selected(index: int) -> void:
	if index < 0 or index >= unit_select.item_count:
		return
	unit_path = String(unit_select.get_item_metadata(index))
	unit_current = load(unit_path)
	unit_name.text = String(unit_current.display_name)
	unit_role.text = String(unit_current.role)
	unit_team.select(0 if String(unit_current.team) == "player" else 1)
	unit_hp.value = int(unit_current.max_hp)
	unit_attack.value = int(unit_current.attack)
	unit_move.value = int(unit_current.movement)
	unit_range.value = int(unit_current.attack_range)
	unit_init.value = int(unit_current.initiative)
	unit_focus.value = int(unit_current.max_focus)
	unit_color.color = unit_current.color
	_select_metadata(unit_visual, String(unit_current.visual_id) if not String(unit_current.visual_id).is_empty() else String(unit_current.id))
	_select_metadata(unit_primary, String(unit_current.primary_skill))
	_select_metadata(unit_secondary, String(unit_current.secondary_skill))
	_select_metadata(unit_ai, String(unit_current.ai_profile))
	_select_text(unit_reaction, String(unit_current.reaction_type))
	unit_reaction_range.value = int(unit_current.reaction_range)
	unit_reaction_bonus.value = int(unit_current.reaction_damage_bonus)
	_select_metadata(unit_default_job, String(unit_current.default_job_id))
	unit_start_level.value = int(unit_current.starting_level)
	for job_index in range(unit_available_jobs.item_count):
		var job_id := String(unit_available_jobs.get_item_metadata(job_index))
		if unit_current.available_job_ids.has(job_id):
			unit_available_jobs.select(job_index, false)
		else:
			unit_available_jobs.deselect(job_index)
	_validate_unit()


func _new_unit() -> void:
	var new_id := _unique_resource_id(UNIT_DIR, "new_unit")
	var data: Resource = UnitDefinition.new()
	data.id = new_id
	data.display_name = "Nouvelle unité"
	data.role = "À définir"
	data.team = "enemy"
	data.color = Color("#e08b72")
	var path := UNIT_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	_rescan_filesystem()
	unit_path = path
	_refresh_units()
	status_label.text = "✓ Nouvelle unité créée : %s" % new_id


func _save_unit() -> void:
	if unit_current == null:
		return
	unit_current.display_name = unit_name.text.strip_edges()
	unit_current.role = unit_role.text.strip_edges()
	unit_current.team = unit_team.get_item_text(unit_team.selected)
	unit_current.max_hp = int(unit_hp.value)
	unit_current.attack = int(unit_attack.value)
	unit_current.movement = int(unit_move.value)
	unit_current.attack_range = int(unit_range.value)
	unit_current.initiative = int(unit_init.value)
	unit_current.max_focus = int(unit_focus.value)
	unit_current.color = unit_color.color
	unit_current.visual_id = String(unit_visual.get_item_metadata(unit_visual.selected)) if unit_visual != null and unit_visual.item_count > 0 else ""
	unit_current.primary_skill = String(unit_primary.get_item_metadata(unit_primary.selected))
	unit_current.secondary_skill = String(unit_secondary.get_item_metadata(unit_secondary.selected))
	unit_current.ai_profile = String(unit_ai.get_item_metadata(unit_ai.selected))
	unit_current.reaction_type = unit_reaction.get_item_text(unit_reaction.selected)
	unit_current.reaction_range = int(unit_reaction_range.value)
	unit_current.reaction_damage_bonus = int(unit_reaction_bonus.value)
	unit_current.default_job_id = String(unit_default_job.get_item_metadata(unit_default_job.selected))
	unit_current.starting_level = int(unit_start_level.value)
	var available_jobs := PackedStringArray()
	for selected_index in unit_available_jobs.get_selected_items():
		available_jobs.append(String(unit_available_jobs.get_item_metadata(int(selected_index))))
	unit_current.available_job_ids = available_jobs
	ResourceSaver.save(unit_current, unit_path)
	status_label.text = "✓ Unité enregistrée : %s" % unit_path
	_validate_unit()
	_refresh_enemy_selectors()


func _duplicate_unit() -> void:
	if unit_current == null:
		return
	var new_id := _unique_resource_id(UNIT_DIR, String(unit_current.id) + "_copy")
	var copy: Resource = unit_current.duplicate(true)
	copy.id = new_id
	copy.display_name = String(unit_current.display_name) + " Copie"
	var path := UNIT_DIR + new_id + ".tres"
	ResourceSaver.save(copy, path)
	_rescan_filesystem()
	unit_path = path
	_refresh_units()
	status_label.text = "✓ Nouvelle unité : %s" % new_id


func _validate_unit() -> void:
	if unit_current == null:
		return
	var issues: Array[String] = []
	for skill_id in [String(unit_current.primary_skill), String(unit_current.secondary_skill)]:
		if not skill_id.is_empty() and not ResourceLoader.exists(SKILL_DIR + skill_id + ".tres"):
			issues.append("Compétence inconnue : %s" % skill_id)
	if not String(unit_current.visual_id).is_empty() and not ResourceLoader.exists(VISUAL_DIR + String(unit_current.visual_id) + ".tres"):
		issues.append("Apparence inconnue : %s" % String(unit_current.visual_id))
	if String(unit_current.reaction_type) not in ["none", "counter", "opportunity", "intercept"]:
		issues.append("Type de réaction invalide : %s" % String(unit_current.reaction_type))
	if int(unit_current.reaction_range) < 1:
		issues.append("La portée de réaction doit être >= 1.")
	if String(unit_current.team) == "enemy" and String(unit_current.ai_profile).is_empty():
		issues.append("Profil IA vide.")
	elif not String(unit_current.ai_profile).is_empty() and not ResourceLoader.exists(AI_DIR + String(unit_current.ai_profile) + ".tres"):
		issues.append("Profil IA inconnu : %s" % String(unit_current.ai_profile))
	if String(unit_current.team) == "player":
		if String(unit_current.default_job_id).is_empty():
			issues.append("Job par défaut vide.")
		elif not ResourceLoader.exists(JOB_DIR + String(unit_current.default_job_id) + ".tres"):
			issues.append("Job par défaut inconnu : %s" % String(unit_current.default_job_id))
		for job_id in unit_current.available_job_ids:
			if not ResourceLoader.exists(JOB_DIR + String(job_id) + ".tres"):
				issues.append("Job disponible inconnu : %s" % String(job_id))
		if not String(unit_current.default_job_id).is_empty() and not unit_current.available_job_ids.has(String(unit_current.default_job_id)):
			issues.append("Le job par défaut doit être dans Jobs disponibles.")
	if issues.is_empty():
		unit_validation.text = "✓ Unité valide."
		unit_validation.add_theme_color_override("font_color", Color("#8fe0ad"))
	else:
		unit_validation.text = "⚠ " + " • ".join(issues)
		unit_validation.add_theme_color_override("font_color", Color("#ffb36b"))


# -----------------------------------------------------------------------------
# SKILLS + EFFECT BLOCKS
# -----------------------------------------------------------------------------

func _refresh_skills() -> void:
	var wanted := skill_path
	skill_select.clear()
	for path in _resource_files(SKILL_DIR):
		var data := load(path)
		skill_select.add_item("%s  [%s]" % [String(data.display_name), String(data.id)])
		skill_select.set_item_metadata(skill_select.item_count - 1, path)
	if skill_select.item_count > 0:
		var index := _metadata_index(skill_select, wanted)
		if index < 0:
			index = 0
		skill_select.select(index)
		_on_skill_selected(index)


func _on_skill_selected(index: int) -> void:
	if dirty_skill and skill_current != null and not skill_path.is_empty():
		ResourceSaver.save(skill_current, skill_path)
		dirty_skill = false
	if index < 0 or index >= skill_select.item_count:
		return
	skill_path = String(skill_select.get_item_metadata(index))
	skill_current = load(skill_path)
	skill_name.text = String(skill_current.display_name)
	skill_desc.text = String(skill_current.description)
	skill_cost.value = int(skill_current.focus_cost)
	skill_cd.value = int(skill_current.cooldown_rounds)
	skill_range.value = int(skill_current.range)
	_select_text(skill_target, String(skill_current.target_mode))
	var tag_parts: Array[String] = []
	for tag in skill_current.effect_tags:
		tag_parts.append(String(tag))
	skill_tags.text = ", ".join(tag_parts)
	_select_metadata(skill_vfx, String(skill_current.vfx_id))
	_refresh_effect_list()
	_validate_skill()


func _new_skill() -> void:
	var new_id := _unique_resource_id(SKILL_DIR, "new_skill")
	var data: Resource = SkillDefinition.new()
	data.id = new_id
	data.display_name = "Nouvelle compétence"
	data.description = "Compose ses effets dans Sporebound Studio."
	data.target_mode = "enemy"
	var effect: Resource = SkillEffect.new()
	effect.effect_type = "damage"
	effect.amount = 2
	data.effects.clear()
	data.effects.append(effect)
	var path := SKILL_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	_rescan_filesystem()
	skill_path = path
	_refresh_skills()
	_refresh_unit_skill_selectors()
	status_label.text = "✓ Nouvelle compétence créée : %s" % new_id


func _save_skill() -> void:
	if skill_current == null:
		return
	skill_current.display_name = skill_name.text.strip_edges()
	skill_current.description = skill_desc.text.strip_edges()
	skill_current.focus_cost = int(skill_cost.value)
	skill_current.cooldown_rounds = int(skill_cd.value)
	skill_current.range = int(skill_range.value)
	skill_current.target_mode = skill_target.get_item_text(skill_target.selected)
	var tags := PackedStringArray()
	for tag in skill_tags.text.split(","):
		var clean := tag.strip_edges()
		if not clean.is_empty():
			tags.append(clean)
	skill_current.effect_tags = tags
	skill_current.vfx_id = String(skill_vfx.get_item_metadata(skill_vfx.selected)) if skill_vfx != null and skill_vfx.item_count > 0 else "default_hit"
	var error := ResourceSaver.save(skill_current, skill_path)
	dirty_skill = false
	status_label.text = "✓ Compétence enregistrée : %s" % skill_path if error == OK else "⚠ Erreur de sauvegarde : %s" % error
	_validate_skill()
	_refresh_unit_skill_selectors()


func _duplicate_skill() -> void:
	if skill_current == null:
		return
	var new_id := _unique_resource_id(SKILL_DIR, String(skill_current.id) + "_copy")
	var copy: Resource = skill_current.duplicate(true)
	copy.id = new_id
	copy.display_name = String(skill_current.display_name) + " Copie"
	var path := SKILL_DIR + new_id + ".tres"
	ResourceSaver.save(copy, path)
	_rescan_filesystem()
	skill_path = path
	_refresh_skills()
	_refresh_unit_skill_selectors()
	status_label.text = "✓ Nouvelle compétence : %s" % new_id


func _refresh_effect_list() -> void:
	effect_list.clear()
	if skill_current == null:
		return
	for index in range(skill_current.effects.size()):
		var effect: Resource = skill_current.effects[index]
		var label := "%d. %s" % [index + 1, effect.summary() if effect != null and effect.has_method("summary") else "Effet invalide"]
		effect_list.add_item(label)
	if effect_list.item_count > 0:
		effect_list.select(0)
		_on_effect_selected(0)


func _on_effect_selected(index: int) -> void:
	if skill_current == null or index < 0 or index >= skill_current.effects.size():
		return
	var effect: Resource = skill_current.effects[index]
	_select_text(effect_type, String(effect.effect_type))
	effect_amount.value = int(effect.amount)
	effect_use_attack.button_pressed = bool(effect.use_attack_stat)
	effect_damage_type.text = String(effect.damage_type)
	_select_metadata(effect_status, String(effect.status_id))
	effect_radius.value = int(effect.radius)
	_select_text(effect_shape, String(effect.area_shape))
	_select_text(effect_scope, String(effect.target_scope))
	_select_text(effect_zone_tick_type, String(effect.zone_tick_type))
	_select_text(effect_zone_tick_phase, String(effect.zone_tick_phase))
	effect_zone_duration.value = int(effect.zone_duration_rounds)


func _add_effect() -> void:
	if skill_current == null:
		return
	var effect: Resource = SkillEffect.new()
	effect.effect_type = "damage"
	effect.amount = 1
	effect.target_scope = "target"
	skill_current.effects.append(effect)
	_mark_skill_dirty()
	_refresh_effect_list()
	var index := skill_current.effects.size() - 1
	effect_list.select(index)
	_on_effect_selected(index)
	status_label.text = "Bloc d'effet ajouté. Pense à enregistrer la compétence."


func _remove_effect() -> void:
	if skill_current == null or effect_list.get_selected_items().is_empty():
		return
	var index := int(effect_list.get_selected_items()[0])
	if index >= 0 and index < skill_current.effects.size():
		skill_current.effects.remove_at(index)
	_mark_skill_dirty()
	_refresh_effect_list()
	_validate_skill()


func _move_effect(direction: int) -> void:
	if skill_current == null or effect_list.get_selected_items().is_empty():
		return
	var index := int(effect_list.get_selected_items()[0])
	var target := index + direction
	if target < 0 or target >= skill_current.effects.size():
		return
	var effect = skill_current.effects[index]
	skill_current.effects.remove_at(index)
	skill_current.effects.insert(target, effect)
	_mark_skill_dirty()
	_refresh_effect_list()
	effect_list.select(target)
	_on_effect_selected(target)


func _apply_effect_editor() -> void:
	if skill_current == null or effect_list.get_selected_items().is_empty():
		return
	var index := int(effect_list.get_selected_items()[0])
	if index < 0 or index >= skill_current.effects.size():
		return
	var effect: Resource = skill_current.effects[index]
	effect.effect_type = effect_type.get_item_text(effect_type.selected)
	effect.amount = int(effect_amount.value)
	effect.use_attack_stat = effect_use_attack.button_pressed
	effect.damage_type = effect_damage_type.text.strip_edges() if not effect_damage_type.text.strip_edges().is_empty() else "physical"
	effect.status_id = String(effect_status.get_item_metadata(effect_status.selected))
	effect.radius = int(effect_radius.value)
	effect.area_shape = effect_shape.get_item_text(effect_shape.selected)
	effect.target_scope = effect_scope.get_item_text(effect_scope.selected)
	effect.zone_tick_type = effect_zone_tick_type.get_item_text(effect_zone_tick_type.selected)
	effect.zone_tick_phase = effect_zone_tick_phase.get_item_text(effect_zone_tick_phase.selected)
	effect.zone_duration_rounds = int(effect_zone_duration.value)
	_mark_skill_dirty()
	_refresh_effect_list()
	effect_list.select(index)
	_validate_skill()
	status_label.text = "✓ Bloc mis à jour. Enregistre la compétence pour écrire le .tres."


func _validate_skill() -> void:
	if skill_current == null:
		return
	var issues: Array[String] = []
	if skill_current.effects.is_empty():
		issues.append("Aucun bloc d'effet : la compétence ne fera rien.")
	for index in range(skill_current.effects.size()):
		var effect: Resource = skill_current.effects[index]
		if effect == null:
			issues.append("Bloc %d invalide." % (index + 1))
			continue
		if String(effect.effect_type) == "status" or (String(effect.effect_type) == "zone" and String(effect.zone_tick_type) == "status"):
			if String(effect.status_id).is_empty():
				issues.append("Bloc %d : status_id manquant." % (index + 1))
			elif not ResourceLoader.exists(STATUS_DIR + String(effect.status_id) + ".tres"):
				issues.append("Bloc %d : statut inconnu %s." % [index + 1, String(effect.status_id)])
		if String(effect.effect_type) == "zone" and int(effect.zone_duration_rounds) <= 0:
			issues.append("Bloc %d : durée de zone invalide." % (index + 1))
		if int(effect.radius) > 0 and String(effect.area_shape) == "single":
			issues.append("Bloc %d : rayon > 0 mais forme single." % (index + 1))
	if not String(skill_current.vfx_id).is_empty() and not ResourceLoader.exists(VFX_DIR + String(skill_current.vfx_id) + ".tres"):
		issues.append("VFX inconnu : %s" % String(skill_current.vfx_id))
	if issues.is_empty():
		skill_validation.text = "✓ Skill Graph valide et exécutable."
		skill_validation.add_theme_color_override("font_color", Color("#8fe0ad"))
	else:
		skill_validation.text = "⚠ " + "\n• ".join(issues)
		skill_validation.add_theme_color_override("font_color", Color("#ffb36b"))


# -----------------------------------------------------------------------------
# STATUSES
# -----------------------------------------------------------------------------

func _refresh_statuses() -> void:
	var wanted := status_path
	status_select.clear()
	for path in _resource_files(STATUS_DIR):
		var data := load(path)
		status_select.add_item("%s  [%s]" % [String(data.display_name), String(data.id)])
		status_select.set_item_metadata(status_select.item_count - 1, path)
	_refresh_effect_status_selector()
	if status_select.item_count > 0:
		var index := _metadata_index(status_select, wanted)
		if index < 0:
			index = 0
		status_select.select(index)
		_on_status_selected(index)


func _refresh_effect_status_selector() -> void:
	if effect_status == null:
		return
	var wanted = effect_status.get_item_metadata(effect_status.selected) if effect_status.item_count > 0 else ""
	effect_status.clear()
	effect_status.add_item("— aucun —")
	effect_status.set_item_metadata(0, "")
	for path in _resource_files(STATUS_DIR):
		var data := load(path)
		effect_status.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		effect_status.set_item_metadata(effect_status.item_count - 1, String(data.id))
	_select_metadata(effect_status, wanted)


func _on_status_selected(index: int) -> void:
	if dirty_status and status_current != null and not status_path.is_empty():
		ResourceSaver.save(status_current, status_path)
		dirty_status = false
	if index < 0 or index >= status_select.item_count:
		return
	status_path = String(status_select.get_item_metadata(index))
	status_current = load(status_path)
	status_name.text = String(status_current.display_name)
	status_desc.text = String(status_current.description)
	status_color.color = status_current.color
	_select_metadata(status_vfx, String(status_current.vfx_id))
	status_duration.value = int(status_current.duration_activations)
	status_max_stacks.value = int(status_current.max_stacks)
	_select_text(status_stack_mode, String(status_current.stack_mode))
	_select_text(status_tick_phase, String(status_current.tick_phase))
	status_tick_damage.value = int(status_current.tick_damage)
	status_tick_damage_type.text = String(status_current.tick_damage_type)
	status_tick_heal.value = int(status_current.tick_heal)
	status_attack.value = int(status_current.attack_delta)
	status_move.value = int(status_current.movement_delta)
	status_range.value = int(status_current.range_delta)
	status_init.value = int(status_current.initiative_delta)
	status_outgoing.value = int(status_current.outgoing_damage_delta)
	status_incoming.value = int(status_current.incoming_damage_delta)
	status_prevent_move.button_pressed = bool(status_current.prevents_movement)
	status_prevent_action.button_pressed = bool(status_current.prevents_action)
	status_remove_damage.button_pressed = bool(status_current.remove_on_damage_taken)
	status_remove_attack.button_pressed = bool(status_current.remove_on_attack)
	_validate_status()


func _new_status() -> void:
	var new_id := _unique_resource_id(STATUS_DIR, "new_status")
	var data: Resource = StatusDefinition.new()
	data.id = new_id
	data.display_name = "Nouveau statut"
	data.description = "Décris son effet."
	data.color = Color("#d7b6ff")
	var path := STATUS_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	_rescan_filesystem()
	status_path = path
	_refresh_statuses()
	status_label.text = "✓ Nouveau statut : %s" % new_id


func _duplicate_status() -> void:
	if status_current == null:
		return
	var new_id := _unique_resource_id(STATUS_DIR, String(status_current.id) + "_copy")
	var copy: Resource = status_current.duplicate(true)
	copy.id = new_id
	copy.display_name = String(status_current.display_name) + " Copie"
	var path := STATUS_DIR + new_id + ".tres"
	ResourceSaver.save(copy, path)
	_rescan_filesystem()
	status_path = path
	_refresh_statuses()
	status_label.text = "✓ Statut dupliqué : %s" % new_id


func _save_status() -> void:
	if status_current == null:
		return
	status_current.display_name = status_name.text.strip_edges()
	status_current.description = status_desc.text.strip_edges()
	status_current.color = status_color.color
	status_current.vfx_id = String(status_vfx.get_item_metadata(status_vfx.selected)) if status_vfx != null and status_vfx.item_count > 0 else ""
	status_current.duration_activations = int(status_duration.value)
	status_current.max_stacks = int(status_max_stacks.value)
	status_current.stack_mode = status_stack_mode.get_item_text(status_stack_mode.selected)
	status_current.tick_phase = status_tick_phase.get_item_text(status_tick_phase.selected)
	status_current.tick_damage = int(status_tick_damage.value)
	status_current.tick_damage_type = status_tick_damage_type.text.strip_edges() if not status_tick_damage_type.text.strip_edges().is_empty() else "physical"
	status_current.tick_heal = int(status_tick_heal.value)
	status_current.attack_delta = int(status_attack.value)
	status_current.movement_delta = int(status_move.value)
	status_current.range_delta = int(status_range.value)
	status_current.initiative_delta = int(status_init.value)
	status_current.outgoing_damage_delta = int(status_outgoing.value)
	status_current.incoming_damage_delta = int(status_incoming.value)
	status_current.prevents_movement = status_prevent_move.button_pressed
	status_current.prevents_action = status_prevent_action.button_pressed
	status_current.remove_on_damage_taken = status_remove_damage.button_pressed
	status_current.remove_on_attack = status_remove_attack.button_pressed
	var error := ResourceSaver.save(status_current, status_path)
	dirty_status = false
	status_label.text = "✓ Statut enregistré : %s" % status_path if error == OK else "⚠ Erreur statut : %s" % error
	_validate_status()
	_refresh_effect_status_selector()


func _validate_status() -> void:
	if status_current == null:
		return
	var issues: Array[String] = []
	if String(status_current.display_name).is_empty():
		issues.append("Nom vide.")
	if String(status_current.tick_phase) == "none" and (int(status_current.tick_damage) > 0 or int(status_current.tick_heal) > 0):
		issues.append("Le statut a un tick mais sa phase est 'none'.")
	if int(status_current.tick_damage) > 0 and int(status_current.tick_heal) > 0:
		issues.append("Dégâts ET soin périodiques : autorisé mais à vérifier.")
	if bool(status_current.prevents_action) and not bool(status_current.prevents_movement):
		issues.append("Bloque l'action mais pas le déplacement : l'activation sera tout de même sautée.")
	if not String(status_current.vfx_id).is_empty() and not ResourceLoader.exists(VFX_DIR + String(status_current.vfx_id) + ".tres"):
		issues.append("VFX inconnu : %s" % String(status_current.vfx_id))
	if issues.is_empty():
		status_validation.text = "✓ Statut valide • " + String(status_current.summary())
		status_validation.add_theme_color_override("font_color", Color("#8fe0ad"))
	else:
		status_validation.text = "⚠ " + "\n• ".join(issues)
		status_validation.add_theme_color_override("font_color", Color("#ffb36b"))


# -----------------------------------------------------------------------------
# CAMPAIGN GRAPH
# -----------------------------------------------------------------------------

func _refresh_campaign() -> void:
	if not ResourceLoader.exists(CAMPAIGN_PATH):
		campaign_current = CampaignDefinition.new()
		ResourceSaver.save(campaign_current, CAMPAIGN_PATH)
	else:
		campaign_current = load(CAMPAIGN_PATH)
	_refresh_campaign_selectors()
	campaign_canvas.set_campaign(campaign_current)
	if campaign_current.nodes.is_empty():
		campaign_node_current = null
		_validate_campaign()
		return
	var wanted := ""
	if campaign_node_current != null:
		wanted = String(campaign_node_current.id)
	if wanted.is_empty() or campaign_current.node_by_id(wanted) == null:
		wanted = String(campaign_current.start_node_id)
	if wanted.is_empty() or campaign_current.node_by_id(wanted) == null:
		wanted = String(campaign_current.nodes[0].id)
	_select_campaign_node_by_id(wanted)
	_validate_campaign()


func _refresh_campaign_selectors() -> void:
	if campaign_current == null:
		return
	var node_options := [campaign_node_select, campaign_start_node, campaign_next, campaign_fallback, campaign_choice_a_next, campaign_choice_b_next]
	for option in node_options:
		if option == null:
			continue
		var wanted = option.get_item_metadata(option.selected) if option.item_count > 0 else ""
		option.clear()
		if option != campaign_node_select:
			option.add_item("— aucun —")
			option.set_item_metadata(0, "")
		for node in campaign_current.nodes:
			if node == null:
				continue
			option.add_item("%s [%s]" % [String(node.title), String(node.id)])
			option.set_item_metadata(option.item_count - 1, String(node.id))
		_select_metadata(option, wanted)
	_select_metadata(campaign_start_node, String(campaign_current.start_node_id))

	campaign_mission.clear()
	campaign_mission.add_item("— aucune —")
	campaign_mission.set_item_metadata(0, "")
	for path in _resource_files(MISSION_DIR):
		var mission := load(path)
		campaign_mission.add_item("%s [%s]" % [String(mission.display_name), String(mission.id)])
		campaign_mission.set_item_metadata(campaign_mission.item_count - 1, String(mission.id))


func _on_campaign_node_selected(index: int) -> void:
	if index < 0 or index >= campaign_node_select.item_count:
		return
	_select_campaign_node_by_id(String(campaign_node_select.get_item_metadata(index)))


func _on_campaign_canvas_node_selected(node_id: String) -> void:
	_select_campaign_node_by_id(node_id)


func _select_campaign_node_by_id(node_id: String) -> void:
	if campaign_current == null:
		return
	var node := campaign_current.node_by_id(node_id)
	if node == null:
		return
	campaign_node_current = node
	_select_metadata(campaign_node_select, node_id)
	campaign_canvas.set_selected_node(node_id)
	campaign_title.text = String(node.title)
	campaign_body.text = String(node.body)
	_select_text(campaign_type, String(node.node_type))
	_select_metadata(campaign_mission, String(node.mission_id))
	_select_metadata(campaign_next, String(node.next_node_id))
	campaign_min_spores.value = int(node.minimum_spores)
	campaign_min_loop.value = int(node.minimum_loop)
	campaign_required_equipment.text = String(node.required_equipment)
	_select_metadata(campaign_fallback, String(node.fallback_node_id))
	campaign_victory_bonus.value = int(node.victory_spores_bonus)
	var reward_parts: Array[String] = []
	for reward_id in node.reward_pool_override:
		reward_parts.append(String(reward_id))
	campaign_reward_pool.text = ", ".join(reward_parts)
	campaign_choice_a_label.text = String(node.choice_a_label)
	_select_metadata(campaign_choice_a_next, String(node.choice_a_next_node_id))
	_select_text(campaign_choice_a_reward, String(node.choice_a_reward_type))
	campaign_choice_a_value.value = int(node.choice_a_reward_value)
	campaign_choice_b_label.text = String(node.choice_b_label)
	_select_metadata(campaign_choice_b_next, String(node.choice_b_next_node_id))
	_select_text(campaign_choice_b_reward, String(node.choice_b_reward_type))
	campaign_choice_b_value.value = int(node.choice_b_reward_value)


func _new_campaign_node(node_type: String) -> void:
	if campaign_current == null:
		return
	var node: Resource = CampaignNodeDefinition.new()
	node.id = _unique_campaign_node_id(node_type)
	node.node_type = node_type
	node.title = "Nouvelle mission" if node_type == "mission" else ("Nouvel événement" if node_type == "event" else "Fin de campagne")
	node.body = "Décris ce nœud."
	node.editor_position = Vector2(60.0 + campaign_current.nodes.size() * 210.0, 240.0)
	if node_type == "event":
		node.choice_a_label = "Continuer"
	campaign_current.nodes.append(node)
	_mark_campaign_dirty()
	_refresh_campaign_selectors()
	campaign_canvas.set_campaign(campaign_current)
	_select_campaign_node_by_id(String(node.id))
	status_label.text = "✓ Nœud créé : %s" % String(node.id)


func _duplicate_campaign_node() -> void:
	if campaign_current == null or campaign_node_current == null:
		return
	var copy: Resource = campaign_node_current.duplicate(true)
	copy.id = _unique_campaign_node_id(String(campaign_node_current.id) + "_copy")
	copy.title = String(campaign_node_current.title) + " Copie"
	copy.editor_position = campaign_node_current.editor_position + Vector2(40, 120)
	campaign_current.nodes.append(copy)
	_mark_campaign_dirty()
	_refresh_campaign_selectors()
	campaign_canvas.set_campaign(campaign_current)
	_select_campaign_node_by_id(String(copy.id))


func _delete_campaign_node() -> void:
	if campaign_current == null or campaign_node_current == null:
		return
	var removed_id := String(campaign_node_current.id)
	campaign_current.nodes.erase(campaign_node_current)
	for node in campaign_current.nodes:
		if node == null:
			continue
		if String(node.next_node_id) == removed_id:
			node.next_node_id = ""
		if String(node.fallback_node_id) == removed_id:
			node.fallback_node_id = ""
		if String(node.choice_a_next_node_id) == removed_id:
			node.choice_a_next_node_id = ""
		if String(node.choice_b_next_node_id) == removed_id:
			node.choice_b_next_node_id = ""
	if String(campaign_current.start_node_id) == removed_id:
		campaign_current.start_node_id = String(campaign_current.nodes[0].id) if not campaign_current.nodes.is_empty() else ""
	campaign_node_current = null
	_mark_campaign_dirty()
	_refresh_campaign_selectors()
	campaign_canvas.set_campaign(campaign_current)
	if not campaign_current.nodes.is_empty():
		_select_campaign_node_by_id(String(campaign_current.start_node_id))
	_validate_campaign()
	status_label.text = "✓ Nœud supprimé : %s" % removed_id


func _unique_campaign_node_id(base: String) -> String:
	var clean := base.to_lower().replace(" ", "_")
	var candidate := clean
	var suffix := 2
	while campaign_current != null and campaign_current.node_by_id(candidate) != null:
		candidate = clean + "_%d" % suffix
		suffix += 1
	return candidate


func _apply_campaign_node_editor() -> void:
	if campaign_node_current == null:
		return
	campaign_node_current.title = campaign_title.text.strip_edges()
	campaign_node_current.body = campaign_body.text.strip_edges()
	campaign_node_current.node_type = campaign_type.get_item_text(campaign_type.selected)
	campaign_node_current.mission_id = String(campaign_mission.get_item_metadata(campaign_mission.selected))
	campaign_node_current.next_node_id = String(campaign_next.get_item_metadata(campaign_next.selected))
	campaign_node_current.minimum_spores = int(campaign_min_spores.value)
	campaign_node_current.minimum_loop = int(campaign_min_loop.value)
	campaign_node_current.required_equipment = campaign_required_equipment.text.strip_edges()
	campaign_node_current.fallback_node_id = String(campaign_fallback.get_item_metadata(campaign_fallback.selected))
	campaign_node_current.victory_spores_bonus = int(campaign_victory_bonus.value)
	var pool := PackedStringArray()
	for reward_id in campaign_reward_pool.text.split(","):
		var clean := reward_id.strip_edges()
		if not clean.is_empty():
			pool.append(clean)
	campaign_node_current.reward_pool_override = pool
	campaign_node_current.choice_a_label = campaign_choice_a_label.text.strip_edges()
	campaign_node_current.choice_a_next_node_id = String(campaign_choice_a_next.get_item_metadata(campaign_choice_a_next.selected))
	campaign_node_current.choice_a_reward_type = campaign_choice_a_reward.get_item_text(campaign_choice_a_reward.selected)
	campaign_node_current.choice_a_reward_value = int(campaign_choice_a_value.value)
	campaign_node_current.choice_b_label = campaign_choice_b_label.text.strip_edges()
	campaign_node_current.choice_b_next_node_id = String(campaign_choice_b_next.get_item_metadata(campaign_choice_b_next.selected))
	campaign_node_current.choice_b_reward_type = campaign_choice_b_reward.get_item_text(campaign_choice_b_reward.selected)
	campaign_node_current.choice_b_reward_value = int(campaign_choice_b_value.value)
	campaign_node_current.emit_changed()
	_mark_campaign_dirty()
	_refresh_campaign_selectors()
	campaign_canvas.queue_redraw()
	_select_campaign_node_by_id(String(campaign_node_current.id))
	_validate_campaign()
	status_label.text = "✓ Nœud campagne mis à jour."


func _on_campaign_node_moved(_node_id: String, _position: Vector2) -> void:
	_mark_campaign_dirty()


func _save_campaign_resource() -> void:
	if campaign_current == null:
		return
	var selected_start := String(campaign_start_node.get_item_metadata(campaign_start_node.selected))
	if campaign_node_current != null:
		_apply_campaign_node_editor()
	campaign_current.start_node_id = selected_start
	_select_metadata(campaign_start_node, selected_start)
	var error := ResourceSaver.save(campaign_current, CAMPAIGN_PATH)
	dirty_campaign = false
	status_label.text = "✓ Campagne enregistrée : %s" % CAMPAIGN_PATH if error == OK else "⚠ Erreur campagne : %s" % error
	_validate_campaign()


func _validate_campaign() -> void:
	if campaign_current == null:
		return
	var issues: Array[String] = []
	var warnings: Array[String] = []
	var ids: Dictionary = {}
	for node in campaign_current.nodes:
		if node == null:
			issues.append("Nœud nul.")
			continue
		var node_id := String(node.id)
		if node_id.is_empty():
			issues.append("Un nœud a un ID vide.")
		elif ids.has(node_id):
			issues.append("ID dupliqué : %s" % node_id)
		ids[node_id] = true
	if String(campaign_current.start_node_id).is_empty() or not ids.has(String(campaign_current.start_node_id)):
		issues.append("Nœud de départ invalide.")
	for node in campaign_current.nodes:
		if node == null:
			continue
		var node_id := String(node.id)
		if String(node.node_type) == "mission":
			if String(node.mission_id).is_empty() or not _mission_id_exists(String(node.mission_id)):
				issues.append("%s : mission inconnue %s" % [node_id, String(node.mission_id)])
			if String(node.next_node_id).is_empty():
				warnings.append("%s : aucune suite." % node_id)
		elif String(node.node_type) == "event":
			if String(node.choice_a_next_node_id).is_empty():
				issues.append("%s : choix A sans destination." % node_id)
		for target_id in node.outgoing_node_ids():
			if not ids.has(String(target_id)):
				issues.append("%s → destination inconnue %s" % [node_id, String(target_id)])
		if not String(node.fallback_node_id).is_empty() and not ids.has(String(node.fallback_node_id)):
			issues.append("%s : fallback inconnu %s" % [node_id, String(node.fallback_node_id)])

	# Reachability helps catch orphan content without blocking experimentation.
	var reachable: Dictionary = {}
	var queue: Array[String] = [String(campaign_current.start_node_id)]
	while not queue.is_empty():
		var current_id := queue.pop_front()
		if current_id.is_empty() or reachable.has(current_id):
			continue
		reachable[current_id] = true
		var current := campaign_current.node_by_id(current_id)
		if current == null:
			continue
		for target_id in current.outgoing_node_ids():
			queue.append(String(target_id))
		if not String(current.fallback_node_id).is_empty():
			queue.append(String(current.fallback_node_id))
	for node in campaign_current.nodes:
		if node != null and not reachable.has(String(node.id)):
			warnings.append("Nœud orphelin : %s" % String(node.id))

	if issues.is_empty():
		campaign_validation.text = "✓ GRAPHE VALIDE — %d nœuds" % campaign_current.nodes.size()
		if not warnings.is_empty():
			campaign_validation.text += "\n⚠ " + "\n• ".join(warnings)
		campaign_validation.add_theme_color_override("font_color", Color("#8fe0ad") if warnings.is_empty() else Color("#ffd27d"))
	else:
		campaign_validation.text = "⚠ ERREURS\n• " + "\n• ".join(issues)
		if not warnings.is_empty():
			campaign_validation.text += "\nAVERTISSEMENTS\n• " + "\n• ".join(warnings)
		campaign_validation.add_theme_color_override("font_color", Color("#ff8d7a"))


func _mission_id_exists(mission_id: String) -> bool:
	for path in _resource_files(MISSION_DIR):
		var mission := load(path)
		if String(mission.id) == mission_id:
			return true
	return false


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

func _remove_from_array(array: Array, cell: Vector2i) -> void:
	while array.has(cell):
		array.erase(cell)


func _toggle_cell(array: Array, cell: Vector2i, add_only: bool = false) -> void:
	if array.has(cell):
		if not add_only:
			array.erase(cell)
	else:
		array.append(cell)


func _cell_in_bounds(cell: Vector2i) -> bool:
	return mission_current != null and cell.x >= 0 and cell.y >= 0 and cell.x < int(mission_current.grid_width) and cell.y < int(mission_current.grid_height)


func _unique_resource_id(directory: String, base: String) -> String:
	var clean_base := base.to_lower().replace(" ", "_")
	var candidate := clean_base
	var suffix := 2
	while ResourceLoader.exists(directory + candidate + ".tres"):
		candidate = clean_base + "_%d" % suffix
		suffix += 1
	return candidate


func _rescan_filesystem() -> void:
	if editor_plugin != null:
		editor_plugin.get_editor_interface().get_resource_filesystem().scan()


func _metadata_index(option: OptionButton, metadata: Variant) -> int:
	for i in range(option.item_count):
		if option.get_item_metadata(i) == metadata:
			return i
	return -1


func _select_metadata(option: OptionButton, metadata: Variant) -> void:
	if option == null:
		return
	var index := _metadata_index(option, metadata)
	if index >= 0:
		option.select(index)


func _select_text(option: OptionButton, text: String) -> void:
	if option == null:
		return
	for i in range(option.item_count):
		if option.get_item_text(i) == text:
			option.select(i)
			return
	if option.item_count > 0:
		option.select(0)


func _add_label(parent: Control, text: String) -> Label:
	var label := Label.new()
	label.text = text
	parent.add_child(label)
	return label


func _add_separator(parent: Control, title: String) -> void:
	var separator := HSeparator.new()
	parent.add_child(separator)
	var label := Label.new()
	label.text = title
	label.add_theme_font_size_override("font_size", 14)
	parent.add_child(label)


func _line_field(parent: Control, label_text: String) -> LineEdit:
	_add_label(parent, label_text)
	var edit := LineEdit.new()
	parent.add_child(edit)
	return edit


func _text_field(parent: Control, label_text: String, height: float) -> TextEdit:
	_add_label(parent, label_text)
	var edit := TextEdit.new()
	edit.custom_minimum_size.y = height
	parent.add_child(edit)
	return edit


func _spin_field(parent: Control, label_text: String, min_value: float, max_value: float) -> SpinBox:
	_add_label(parent, label_text)
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = 1
	parent.add_child(spin)
	return spin


func _compact_spin(parent: Control, label_text: String, min_value: float, max_value: float) -> SpinBox:
	var label := Label.new()
	label.text = label_text
	parent.add_child(label)
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = 1
	spin.custom_minimum_size.x = 70
	parent.add_child(spin)
	return spin


func _add_grid_label(grid: GridContainer, text: String) -> void:
	var label := Label.new()
	label.text = text
	grid.add_child(label)


func _grid_line(grid: GridContainer, label_text: String) -> LineEdit:
	_add_grid_label(grid, label_text)
	var edit := LineEdit.new()
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_child(edit)
	return edit


func _grid_spin(grid: GridContainer, label_text: String, min_value: float, max_value: float) -> SpinBox:
	_add_grid_label(grid, label_text)
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = 1
	grid.add_child(spin)
	return spin

# -----------------------------------------------------------------------------
# V1.4 AI PROFILES
# -----------------------------------------------------------------------------

func _on_ai_field_changed(_value: Variant = null) -> void:
	if ai_current != null:
		dirty_ai = true


func _refresh_ai_profiles() -> void:
	if ai_select == null:
		return
	var wanted := ai_path
	ai_select.clear()
	for path in _resource_files(AI_DIR):
		var data := load(path)
		ai_select.add_item("%s  [%s]" % [String(data.display_name), String(data.id)])
		ai_select.set_item_metadata(ai_select.item_count - 1, path)
	if ai_select.item_count > 0:
		var index := _metadata_index(ai_select, wanted)
		if index < 0:
			index = 0
		ai_select.select(index)
		_on_ai_selected(index)
	_refresh_unit_ai_selector()


func _on_ai_selected(index: int) -> void:
	if dirty_ai and ai_current != null and not ai_path.is_empty():
		_write_ai_editor_to_current()
		ResourceSaver.save(ai_current, ai_path)
		dirty_ai = false
	if index < 0 or index >= ai_select.item_count:
		return
	ai_path = String(ai_select.get_item_metadata(index))
	ai_current = load(ai_path)
	ai_name.text = String(ai_current.display_name)
	ai_desc.text = String(ai_current.description)
	ai_preferred_range.value = int(ai_current.preferred_range)
	ai_distance_weight.value = float(ai_current.distance_weight)
	ai_attack_bonus.value = float(ai_current.attack_position_bonus)
	ai_cover_weight.value = float(ai_current.cover_weight)
	ai_height_weight.value = float(ai_current.height_weight)
	ai_hazard_penalty.value = float(ai_current.hazard_penalty)
	ai_reaction_penalty.value = float(ai_current.reaction_penalty)
	ai_movement_weight.value = float(ai_current.movement_cost_weight)
	ai_hp_weight.value = float(ai_current.target_hp_weight)
	ai_target_distance.value = float(ai_current.target_distance_weight)
	ai_crown_priority.value = float(ai_current.crown_carrier_priority)
	ai_marked_priority.value = float(ai_current.marked_target_priority)
	ai_skill_bias.value = float(ai_current.skill_bias)
	ai_prefer_skills.button_pressed = bool(ai_current.prefer_skills)
	ai_avoid_reactions.button_pressed = bool(ai_current.avoid_reactions)
	ai_seek_cover.button_pressed = bool(ai_current.seek_cover)
	dirty_ai = false
	_validate_ai_profile()


func _new_ai_profile() -> void:
	var new_id := _unique_resource_id(AI_DIR, "new_ai")
	var data: Resource = AIProfileDefinition.new()
	data.id = new_id
	data.display_name = "Nouveau profil IA"
	data.description = "Profil créé dans Sporebound Studio."
	var path := AI_DIR + new_id + ".tres"
	ResourceSaver.save(data, path)
	_rescan_filesystem()
	ai_path = path
	_refresh_ai_profiles()
	_refresh_vfx_selectors()
	_refresh_visual_selector()
	status_label.text = "✓ Profil IA créé : %s" % new_id


func _duplicate_ai_profile() -> void:
	if ai_current == null:
		return
	var new_id := _unique_resource_id(AI_DIR, String(ai_current.id) + "_copy")
	var copy: Resource = ai_current.duplicate(true)
	copy.id = new_id
	copy.display_name = String(ai_current.display_name) + " Copie"
	var path := AI_DIR + new_id + ".tres"
	ResourceSaver.save(copy, path)
	_rescan_filesystem()
	ai_path = path
	_refresh_ai_profiles()
	_refresh_vfx_selectors()
	_refresh_visual_selector()
	status_label.text = "✓ Profil IA dupliqué : %s" % new_id


func _write_ai_editor_to_current() -> void:
	if ai_current == null:
		return
	ai_current.display_name = ai_name.text.strip_edges()
	ai_current.description = ai_desc.text.strip_edges()
	ai_current.preferred_range = int(ai_preferred_range.value)
	ai_current.distance_weight = float(ai_distance_weight.value)
	ai_current.attack_position_bonus = float(ai_attack_bonus.value)
	ai_current.cover_weight = float(ai_cover_weight.value)
	ai_current.height_weight = float(ai_height_weight.value)
	ai_current.hazard_penalty = float(ai_hazard_penalty.value)
	ai_current.reaction_penalty = float(ai_reaction_penalty.value)
	ai_current.movement_cost_weight = float(ai_movement_weight.value)
	ai_current.target_hp_weight = float(ai_hp_weight.value)
	ai_current.target_distance_weight = float(ai_target_distance.value)
	ai_current.crown_carrier_priority = float(ai_crown_priority.value)
	ai_current.marked_target_priority = float(ai_marked_priority.value)
	ai_current.skill_bias = float(ai_skill_bias.value)
	ai_current.prefer_skills = ai_prefer_skills.button_pressed
	ai_current.avoid_reactions = ai_avoid_reactions.button_pressed
	ai_current.seek_cover = ai_seek_cover.button_pressed
	ai_current.emit_changed()


func _save_ai_profile() -> void:
	if ai_current == null:
		return
	_write_ai_editor_to_current()
	var error := ResourceSaver.save(ai_current, ai_path)
	dirty_ai = false
	_validate_ai_profile()
	_refresh_unit_ai_selector()
	status_label.text = "✓ Profil IA enregistré : %s" % ai_path if error == OK else "⚠ Erreur IA : %s" % error


func _validate_ai_profile() -> void:
	if ai_current == null or ai_validation == null:
		return
	var users: Array[String] = []
	for path in _resource_files(UNIT_DIR):
		var unit := load(path)
		if String(unit.ai_profile) == String(ai_current.id):
			users.append(String(unit.display_name))
	ai_validation.text = "✓ Profil valide • utilisé par : %s" % (", ".join(users) if not users.is_empty() else "aucune unité")
	ai_validation.add_theme_color_override("font_color", Color("#8fe0ad"))


# -----------------------------------------------------------------------------
# V1.6 MISSION LOGIC / EVENT SEQUENCER / INTERACTABLES
# -----------------------------------------------------------------------------

func _refresh_mission_logic_selector() -> void:
	if logic_mission_select == null:
		return
	var wanted := logic_mission_path
	logic_mission_select.clear()
	for path in _resource_files(MISSION_DIR):
		var data := load(path)
		logic_mission_select.add_item("%s [%s]" % [String(data.display_name), String(data.id)])
		logic_mission_select.set_item_metadata(logic_mission_select.item_count - 1, path)
	if logic_mission_select.item_count > 0:
		var index := _metadata_index(logic_mission_select, wanted)
		if index < 0:
			index = 0
		logic_mission_select.select(index)
		_on_logic_mission_selected(index)
	_refresh_logic_reference_selectors()


func _on_logic_mode_changed(_index: int) -> void:
	if logic_mission_current == null:
		return
	logic_mission_current.victory_rule_mode = logic_victory_mode.get_item_text(logic_victory_mode.selected)
	logic_mission_current.defeat_rule_mode = logic_defeat_mode.get_item_text(logic_defeat_mode.selected)
	dirty_logic_mission = true


func _on_logic_mission_selected(index: int) -> void:
	if dirty_logic_mission and logic_mission_current != null and not logic_mission_path.is_empty():
		ResourceSaver.save(logic_mission_current, logic_mission_path)
		dirty_logic_mission = false
	if index < 0 or index >= logic_mission_select.item_count:
		return
	logic_mission_path = String(logic_mission_select.get_item_metadata(index))
	logic_mission_current = load(logic_mission_path)
	_select_text(logic_victory_mode, String(logic_mission_current.victory_rule_mode))
	_select_text(logic_defeat_mode, String(logic_mission_current.defeat_rule_mode))
	_refresh_logic_reference_selectors()
	_refresh_logic_lists()
	_validate_logic_mission()


func _refresh_logic_reference_selectors() -> void:
	if logic_trigger_action_unit != null:
		var wanted_unit = logic_trigger_action_unit.get_item_metadata(logic_trigger_action_unit.selected) if logic_trigger_action_unit.item_count > 0 else ""
		logic_trigger_action_unit.clear()
		logic_trigger_action_unit.add_item("— aucune —")
		logic_trigger_action_unit.set_item_metadata(0, "")
		for path in _resource_files(UNIT_DIR):
			var unit := load(path)
			logic_trigger_action_unit.add_item("%s [%s]" % [String(unit.display_name), String(unit.id)])
			logic_trigger_action_unit.set_item_metadata(logic_trigger_action_unit.item_count - 1, String(unit.id))
		_select_metadata(logic_trigger_action_unit, wanted_unit)
	if logic_trigger_status != null:
		var wanted_status = logic_trigger_status.get_item_metadata(logic_trigger_status.selected) if logic_trigger_status.item_count > 0 else ""
		logic_trigger_status.clear()
		logic_trigger_status.add_item("— aucun —")
		logic_trigger_status.set_item_metadata(0, "")
		for path in _resource_files(STATUS_DIR):
			var status := load(path)
			logic_trigger_status.add_item("%s [%s]" % [String(status.display_name), String(status.id)])
			logic_trigger_status.set_item_metadata(logic_trigger_status.item_count - 1, String(status.id))
		_select_metadata(logic_trigger_status, wanted_status)
	if logic_action_cinematic != null:
		var wanted_cinematic = logic_action_cinematic.get_item_metadata(logic_action_cinematic.selected) if logic_action_cinematic.item_count > 0 else ""
		logic_action_cinematic.clear()
		logic_action_cinematic.add_item("— aucune —")
		logic_action_cinematic.set_item_metadata(0, "")
		for path in _resource_files(CINEMATIC_DIR):
			var cinematic := load(path)
			logic_action_cinematic.add_item("%s [%s]" % [String(cinematic.display_name), String(cinematic.id)])
			logic_action_cinematic.set_item_metadata(logic_action_cinematic.item_count - 1, String(cinematic.id))
		_select_metadata(logic_action_cinematic, wanted_cinematic)
	_refresh_logic_object_selectors()


func _refresh_logic_object_selectors() -> void:
	var selectors: Array = [logic_action_object, logic_interactable_link]
	for selector in selectors:
		if selector == null:
			continue
		var wanted = selector.get_item_metadata(selector.selected) if selector.item_count > 0 else ""
		selector.clear()
		selector.add_item("— aucun —")
		selector.set_item_metadata(0, "")
		if logic_mission_current != null:
			for object_def in logic_mission_current.interactables:
				if object_def == null:
					continue
				selector.add_item("%s [%s]" % [String(object_def.display_name), String(object_def.id)])
				selector.set_item_metadata(selector.item_count - 1, String(object_def.id))
		_select_metadata(selector, wanted)


func _refresh_logic_lists() -> void:
	if logic_mission_current == null:
		return
	logic_victory_list.clear()
	for rule in logic_mission_current.victory_rules:
		logic_victory_list.add_item(rule.summary() if rule != null else "<null>")
	logic_defeat_list.clear()
	for rule in logic_mission_current.defeat_rules:
		logic_defeat_list.add_item(rule.summary() if rule != null else "<null>")
	logic_trigger_list.clear()
	for trigger in logic_mission_current.battle_triggers:
		logic_trigger_list.add_item("%s • %s" % [String(trigger.id), trigger.summary()] if trigger != null else "<null>")
	logic_interactable_list.clear()
	for object_def in logic_mission_current.interactables:
		logic_interactable_list.add_item(object_def.summary() if object_def != null else "<null>")
	logic_action_list.clear()
	logic_rule_index = -1
	logic_trigger_index = -1
	logic_action_index = -1
	logic_interactable_index = -1
	_refresh_logic_object_selectors()


func _logic_rule_array(side: String) -> Array[Resource]:
	if logic_mission_current == null:
		return []
	return logic_mission_current.victory_rules if side == "victory" else logic_mission_current.defeat_rules


func _set_logic_rule_array(side: String, values: Array[Resource]) -> void:
	if logic_mission_current == null:
		return
	if side == "victory":
		logic_mission_current.victory_rules = values
	else:
		logic_mission_current.defeat_rules = values


func _add_logic_rule(side: String) -> void:
	if logic_mission_current == null:
		return
	var rule: Resource = MissionRule.new()
	rule.rule_type = "all_enemies_defeated" if side == "victory" else "all_players_defeated"
	var values := _logic_rule_array(side)
	values.append(rule)
	_set_logic_rule_array(side, values)
	logic_rule_side = side
	var new_index := values.size() - 1
	dirty_logic_mission = true
	_refresh_logic_lists()
	var list := logic_victory_list if side == "victory" else logic_defeat_list
	list.select(new_index)
	_on_logic_rule_selected(new_index, side)
	_validate_logic_mission()


func _remove_logic_rule(side: String) -> void:
	if logic_mission_current == null:
		return
	var list := logic_victory_list if side == "victory" else logic_defeat_list
	var selected := list.get_selected_items()
	if selected.is_empty():
		return
	var values := _logic_rule_array(side)
	var index := int(selected[0])
	if index >= 0 and index < values.size():
		values.remove_at(index)
		_set_logic_rule_array(side, values)
		dirty_logic_mission = true
	_refresh_logic_lists()
	_validate_logic_mission()


func _on_logic_rule_selected(index: int, side: String) -> void:
	var values := _logic_rule_array(side)
	if index < 0 or index >= values.size():
		return
	var rule: Resource = values[index]
	logic_rule_side = side
	logic_rule_index = index
	_select_text(logic_rule_type, String(rule.rule_type))
	logic_rule_amount.value = int(rule.amount)
	logic_rule_unit.text = String(rule.unit_id)
	logic_rule_invert.button_pressed = bool(rule.invert)
	logic_rule_desc.text = String(rule.description)


func _apply_logic_rule_editor() -> void:
	var values := _logic_rule_array(logic_rule_side)
	if logic_rule_index < 0 or logic_rule_index >= values.size():
		return
	var rule: Resource = values[logic_rule_index]
	rule.rule_type = logic_rule_type.get_item_text(logic_rule_type.selected)
	rule.amount = int(logic_rule_amount.value)
	rule.unit_id = logic_rule_unit.text.strip_edges()
	rule.invert = logic_rule_invert.button_pressed
	rule.description = logic_rule_desc.text.strip_edges()
	rule.emit_changed()
	logic_mission_current.victory_rule_mode = logic_victory_mode.get_item_text(logic_victory_mode.selected)
	logic_mission_current.defeat_rule_mode = logic_defeat_mode.get_item_text(logic_defeat_mode.selected)
	var selected_index := logic_rule_index
	var selected_side := logic_rule_side
	dirty_logic_mission = true
	_refresh_logic_lists()
	var selected_list := logic_victory_list if selected_side == "victory" else logic_defeat_list
	selected_list.select(selected_index)
	_on_logic_rule_selected(selected_index, selected_side)
	_validate_logic_mission()


func _add_logic_trigger() -> void:
	if logic_mission_current == null:
		return
	var trigger: Resource = BattleTriggerDefinition.new()
	trigger.id = _unique_logic_trigger_id("trigger")
	var action: Resource = BattleActionDefinition.new()
	action.id = "action_1"
	trigger.actions.append(action)
	logic_mission_current.battle_triggers.append(trigger)
	var new_index := logic_mission_current.battle_triggers.size() - 1
	dirty_logic_mission = true
	_refresh_logic_lists()
	logic_trigger_list.select(new_index)
	_on_logic_trigger_selected(new_index)
	_validate_logic_mission()


func _remove_logic_trigger() -> void:
	if logic_mission_current == null:
		return
	var selected := logic_trigger_list.get_selected_items()
	if selected.is_empty():
		return
	var index := int(selected[0])
	if index >= 0 and index < logic_mission_current.battle_triggers.size():
		logic_mission_current.battle_triggers.remove_at(index)
		dirty_logic_mission = true
	_refresh_logic_lists()
	_validate_logic_mission()


func _unique_logic_trigger_id(base: String) -> String:
	var used: Dictionary = {}
	if logic_mission_current != null:
		for trigger in logic_mission_current.battle_triggers:
			if trigger != null:
				used[String(trigger.id)] = true
	var candidate := base
	var suffix := 2
	while used.has(candidate):
		candidate = "%s_%d" % [base, suffix]
		suffix += 1
	return candidate


func _current_logic_trigger() -> Resource:
	if logic_mission_current == null or logic_trigger_index < 0 or logic_trigger_index >= logic_mission_current.battle_triggers.size():
		return null
	return logic_mission_current.battle_triggers[logic_trigger_index]


func _ensure_trigger_actions(trigger: Resource) -> void:
	if trigger == null or not trigger.actions.is_empty():
		return
	var action: Resource = BattleActionDefinition.new()
	action.id = "action_1"
	action.action_type = String(trigger.action_type)
	action.message = String(trigger.message)
	action.unit_id = String(trigger.action_unit_id)
	action.status_id = String(trigger.action_status_id)
	action.cell = trigger.action_cell
	action.value = int(trigger.action_value)
	action.team = String(trigger.action_team)
	trigger.actions.append(action)
	dirty_logic_mission = true


func _refresh_logic_action_list(trigger: Resource) -> void:
	logic_action_list.clear()
	if trigger == null:
		return
	_ensure_trigger_actions(trigger)
	for index in range(trigger.actions.size()):
		var action = trigger.actions[index]
		logic_action_list.add_item("%02d • %s" % [index + 1, action.summary()] if action != null else "<null>")


func _on_logic_trigger_selected(index: int) -> void:
	if logic_mission_current == null or index < 0 or index >= logic_mission_current.battle_triggers.size():
		return
	var trigger: Resource = logic_mission_current.battle_triggers[index]
	logic_trigger_index = index
	logic_trigger_id.text = String(trigger.id)
	logic_trigger_enabled.button_pressed = bool(trigger.enabled)
	logic_trigger_once.button_pressed = bool(trigger.once)
	_select_text(logic_trigger_condition, String(trigger.condition_type))
	logic_trigger_condition_value.value = int(trigger.condition_value)
	logic_trigger_condition_unit.text = String(trigger.condition_unit_id)
	logic_trigger_condition_zone.text = String(trigger.condition_zone_id)
	logic_trigger_condition_x.value = int(trigger.condition_cell.x)
	logic_trigger_condition_y.value = int(trigger.condition_cell.y)
	_refresh_logic_action_list(trigger)
	logic_action_index = -1
	if trigger.actions.size() > 0:
		logic_action_list.select(0)
		_on_logic_action_selected(0)


func _add_logic_action() -> void:
	var trigger := _current_logic_trigger()
	if trigger == null:
		return
	_ensure_trigger_actions(trigger)
	var action: Resource = BattleActionDefinition.new()
	action.id = "action_%d" % (trigger.actions.size() + 1)
	trigger.actions.append(action)
	logic_action_index = trigger.actions.size() - 1
	dirty_logic_mission = true
	_refresh_logic_action_list(trigger)
	logic_action_list.select(logic_action_index)
	_on_logic_action_selected(logic_action_index)
	_validate_logic_mission()


func _duplicate_logic_action() -> void:
	var trigger := _current_logic_trigger()
	if trigger == null or logic_action_index < 0 or logic_action_index >= trigger.actions.size():
		return
	var copy: Resource = trigger.actions[logic_action_index].duplicate(true)
	copy.id = "action_%d" % (trigger.actions.size() + 1)
	trigger.actions.insert(logic_action_index + 1, copy)
	logic_action_index += 1
	dirty_logic_mission = true
	_refresh_logic_action_list(trigger)
	logic_action_list.select(logic_action_index)
	_on_logic_action_selected(logic_action_index)


func _move_logic_action(delta: int) -> void:
	var trigger := _current_logic_trigger()
	if trigger == null or logic_action_index < 0:
		return
	var destination := logic_action_index + delta
	if destination < 0 or destination >= trigger.actions.size():
		return
	var action = trigger.actions[logic_action_index]
	trigger.actions.remove_at(logic_action_index)
	trigger.actions.insert(destination, action)
	logic_action_index = destination
	dirty_logic_mission = true
	_refresh_logic_action_list(trigger)
	logic_action_list.select(destination)
	_on_logic_action_selected(destination)


func _remove_logic_action() -> void:
	var trigger := _current_logic_trigger()
	if trigger == null or logic_action_index < 0 or logic_action_index >= trigger.actions.size():
		return
	trigger.actions.remove_at(logic_action_index)
	logic_action_index = -1
	dirty_logic_mission = true
	_refresh_logic_action_list(trigger)
	if trigger.actions.size() > 0:
		logic_action_list.select(0)
		_on_logic_action_selected(0)
	_validate_logic_mission()


func _on_logic_action_selected(index: int) -> void:
	var trigger := _current_logic_trigger()
	if trigger == null or index < 0 or index >= trigger.actions.size():
		return
	var action: Resource = trigger.actions[index]
	logic_action_index = index
	_select_text(logic_trigger_action, String(action.action_type))
	logic_action_delay.value = float(action.delay_seconds)
	logic_trigger_message.text = String(action.message)
	_select_metadata(logic_trigger_action_unit, String(action.unit_id))
	_select_metadata(logic_trigger_status, String(action.status_id))
	logic_trigger_action_x.value = int(action.cell.x)
	logic_trigger_action_y.value = int(action.cell.y)
	logic_trigger_action_value.value = int(action.value)
	_select_text(logic_trigger_team, String(action.team))
	_select_metadata(logic_action_object, String(action.object_id))
	_select_metadata(logic_action_cinematic, String(action.cinematic_id))
	_select_text(logic_action_rule_type, String(action.rule_type))
	logic_action_rule_amount.value = int(action.rule_amount)
	logic_action_rule_unit.text = String(action.rule_unit_id)
	logic_action_rule_invert.button_pressed = bool(action.rule_invert)
	_select_text(logic_action_rule_mode, String(action.rule_mode))


func _write_logic_action_editor() -> void:
	var trigger := _current_logic_trigger()
	if trigger == null or logic_action_index < 0 or logic_action_index >= trigger.actions.size():
		return
	var action: Resource = trigger.actions[logic_action_index]
	action.action_type = logic_trigger_action.get_item_text(logic_trigger_action.selected)
	action.delay_seconds = float(logic_action_delay.value)
	action.message = logic_trigger_message.text.strip_edges()
	action.unit_id = String(logic_trigger_action_unit.get_item_metadata(logic_trigger_action_unit.selected))
	action.status_id = String(logic_trigger_status.get_item_metadata(logic_trigger_status.selected))
	action.cell = Vector2i(int(logic_trigger_action_x.value), int(logic_trigger_action_y.value))
	action.value = int(logic_trigger_action_value.value)
	action.team = logic_trigger_team.get_item_text(logic_trigger_team.selected)
	action.object_id = String(logic_action_object.get_item_metadata(logic_action_object.selected))
	action.cinematic_id = String(logic_action_cinematic.get_item_metadata(logic_action_cinematic.selected))
	action.rule_type = logic_action_rule_type.get_item_text(logic_action_rule_type.selected)
	action.rule_amount = int(logic_action_rule_amount.value)
	action.rule_unit_id = logic_action_rule_unit.text.strip_edges()
	action.rule_invert = logic_action_rule_invert.button_pressed
	action.rule_mode = logic_action_rule_mode.get_item_text(logic_action_rule_mode.selected)
	action.emit_changed()


func _apply_logic_trigger_editor() -> void:
	var trigger := _current_logic_trigger()
	if trigger == null:
		return
	trigger.id = logic_trigger_id.text.strip_edges()
	if trigger.id.is_empty():
		trigger.id = _unique_logic_trigger_id("trigger")
	trigger.enabled = logic_trigger_enabled.button_pressed
	trigger.once = logic_trigger_once.button_pressed
	trigger.condition_type = logic_trigger_condition.get_item_text(logic_trigger_condition.selected)
	trigger.condition_value = int(logic_trigger_condition_value.value)
	trigger.condition_unit_id = logic_trigger_condition_unit.text.strip_edges()
	trigger.condition_zone_id = logic_trigger_condition_zone.text.strip_edges()
	trigger.condition_cell = Vector2i(int(logic_trigger_condition_x.value), int(logic_trigger_condition_y.value))
	_write_logic_action_editor()
	trigger.emit_changed()
	var selected_trigger := logic_trigger_index
	var selected_action := logic_action_index
	dirty_logic_mission = true
	_refresh_logic_lists()
	logic_trigger_list.select(selected_trigger)
	_on_logic_trigger_selected(selected_trigger)
	if selected_action >= 0 and selected_action < trigger.actions.size():
		logic_action_list.select(selected_action)
		_on_logic_action_selected(selected_action)
	_validate_logic_mission()


func _unique_interactable_id(base: String) -> String:
	var used: Dictionary = {}
	if logic_mission_current != null:
		for object_def in logic_mission_current.interactables:
			if object_def != null:
				used[String(object_def.id)] = true
	var candidate := base
	var suffix := 2
	while used.has(candidate):
		candidate = "%s_%d" % [base, suffix]
		suffix += 1
	return candidate


func _add_logic_interactable(object_type: String) -> void:
	if logic_mission_current == null:
		return
	var object_def: Resource = MapInteractableDefinition.new()
	object_def.object_type = object_type
	object_def.id = _unique_interactable_id(object_type)
	object_def.display_name = object_type.capitalize()
	object_def.cell = Vector2i(1 + logic_mission_current.interactables.size(), 1)
	object_def.starts_active = false
	if object_type == "chest":
		object_def.reward_type = "focus_team"
		object_def.reward_value = 1
	logic_mission_current.interactables.append(object_def)
	logic_interactable_index = logic_mission_current.interactables.size() - 1
	dirty_logic_mission = true
	_refresh_logic_lists()
	logic_interactable_list.select(logic_interactable_index)
	_on_logic_interactable_selected(logic_interactable_index)
	_validate_logic_mission()


func _remove_logic_interactable() -> void:
	if logic_mission_current == null:
		return
	var selected := logic_interactable_list.get_selected_items()
	if selected.is_empty():
		return
	var index := int(selected[0])
	if index >= 0 and index < logic_mission_current.interactables.size():
		logic_mission_current.interactables.remove_at(index)
		dirty_logic_mission = true
	_refresh_logic_lists()
	_validate_logic_mission()


func _on_logic_interactable_selected(index: int) -> void:
	if logic_mission_current == null or index < 0 or index >= logic_mission_current.interactables.size():
		return
	var object_def: Resource = logic_mission_current.interactables[index]
	logic_interactable_index = index
	logic_interactable_id.text = String(object_def.id)
	logic_interactable_name.text = String(object_def.display_name)
	_select_text(logic_interactable_type, String(object_def.object_type))
	logic_interactable_x.value = int(object_def.cell.x)
	logic_interactable_y.value = int(object_def.cell.y)
	_select_metadata(logic_interactable_link, String(object_def.linked_object_id))
	logic_interactable_active.button_pressed = bool(object_def.starts_active)
	logic_interactable_one_shot.button_pressed = bool(object_def.one_shot)
	_select_text(logic_interactable_reward, String(object_def.reward_type))
	logic_interactable_reward_value.value = int(object_def.reward_value)
	_select_text(logic_interactable_reward_team, String(object_def.reward_team))


func _apply_logic_interactable_editor() -> void:
	if logic_mission_current == null or logic_interactable_index < 0 or logic_interactable_index >= logic_mission_current.interactables.size():
		return
	var object_def: Resource = logic_mission_current.interactables[logic_interactable_index]
	object_def.id = logic_interactable_id.text.strip_edges()
	if object_def.id.is_empty():
		object_def.id = _unique_interactable_id("object")
	object_def.display_name = logic_interactable_name.text.strip_edges()
	object_def.object_type = logic_interactable_type.get_item_text(logic_interactable_type.selected)
	object_def.cell = Vector2i(int(logic_interactable_x.value), int(logic_interactable_y.value))
	object_def.linked_object_id = String(logic_interactable_link.get_item_metadata(logic_interactable_link.selected))
	if object_def.linked_object_id == String(object_def.id):
		object_def.linked_object_id = ""
	object_def.starts_active = logic_interactable_active.button_pressed
	object_def.one_shot = logic_interactable_one_shot.button_pressed
	object_def.reward_type = logic_interactable_reward.get_item_text(logic_interactable_reward.selected)
	object_def.reward_value = int(logic_interactable_reward_value.value)
	object_def.reward_team = logic_interactable_reward_team.get_item_text(logic_interactable_reward_team.selected)
	object_def.emit_changed()
	var selected_index := logic_interactable_index
	dirty_logic_mission = true
	_refresh_logic_lists()
	logic_interactable_list.select(selected_index)
	_on_logic_interactable_selected(selected_index)
	_validate_logic_mission()


func _save_logic_mission() -> void:
	if logic_mission_current == null:
		return
	logic_mission_current.victory_rule_mode = logic_victory_mode.get_item_text(logic_victory_mode.selected)
	logic_mission_current.defeat_rule_mode = logic_defeat_mode.get_item_text(logic_defeat_mode.selected)
	var error := ResourceSaver.save(logic_mission_current, logic_mission_path)
	dirty_logic_mission = false
	_validate_logic_mission()
	status_label.text = "✓ Logique V1.7 enregistrée : %s" % logic_mission_path if error == OK else "⚠ Erreur logique mission : %s" % error


func _logic_cell_inside(cell: Vector2i) -> bool:
	if logic_mission_current == null:
		return false
	return cell.x >= 0 and cell.x < int(logic_mission_current.grid_width) and cell.y >= 0 and cell.y < int(logic_mission_current.grid_height)


func _validate_logic_action(action: Resource, trigger_id: String, object_ids: Dictionary, issues: Array[String]) -> void:
	if action == null:
		issues.append("Action nulle dans %s" % trigger_id)
		return
	var action_type := String(action.action_type)
	if action_type == "spawn_enemy":
		if String(action.unit_id).is_empty():
			issues.append("%s : spawn_enemy sans unité." % trigger_id)
		elif not ResourceLoader.exists(UNIT_DIR + String(action.unit_id) + ".tres"):
			issues.append("%s : unité de renfort inconnue %s." % [trigger_id, action.unit_id])
	if action_type == "apply_status_to_unit":
		if String(action.unit_id).is_empty() or String(action.status_id).is_empty():
			issues.append("%s : apply_status nécessite unité + statut." % trigger_id)
		elif not ResourceLoader.exists(STATUS_DIR + String(action.status_id) + ".tres"):
			issues.append("%s : statut inconnu %s." % [trigger_id, action.status_id])
	if action_type in ["spawn_enemy", "add_hazard", "remove_hazard"] and not _logic_cell_inside(action.cell):
		issues.append("%s : case hors grille pour %s." % [trigger_id, action_type])
	if action_type in ["open_door", "close_door", "toggle_switch", "open_chest"]:
		if String(action.object_id).is_empty() or not object_ids.has(String(action.object_id)):
			issues.append("%s : objet inconnu pour %s." % [trigger_id, action_type])
	if action_type in ["set_victory_rule", "set_defeat_rule"] and String(action.rule_type).is_empty():
		issues.append("%s : règle dynamique incomplète." % trigger_id)
	if action_type == "play_cinematic":
		if String(action.cinematic_id).is_empty():
			issues.append("%s : play_cinematic sans timeline." % trigger_id)
		elif not ResourceLoader.exists(CINEMATIC_DIR + String(action.cinematic_id) + ".tres"):
			issues.append("%s : cinématique inconnue %s." % [trigger_id, action.cinematic_id])


func _validate_logic_mission() -> void:
	if logic_mission_current == null or logic_validation == null:
		return
	var issues: Array[String] = []
	if logic_mission_current.victory_rules.is_empty():
		issues.append("Aucune condition de victoire initiale : le runtime utilisera l'ancien objectif principal jusqu'à un éventuel set_victory_rule.")
	if logic_mission_current.defeat_rules.is_empty():
		issues.append("Aucune condition de défaite : ajoute au minimum all_players_defeated.")
	var object_ids: Dictionary = {}
	var object_cells: Dictionary = {}
	for object_def in logic_mission_current.interactables:
		if object_def == null:
			issues.append("Objet de carte nul")
			continue
		var oid := String(object_def.id)
		if oid.is_empty():
			issues.append("Un objet de carte n'a pas d'ID")
		elif object_ids.has(oid):
			issues.append("ID objet dupliqué : %s" % oid)
		object_ids[oid] = true
		if not _logic_cell_inside(object_def.cell):
			issues.append("Objet %s hors grille." % oid)
		var cell_key := "%d:%d" % [object_def.cell.x, object_def.cell.y]
		if object_cells.has(cell_key):
			issues.append("Deux objets partagent la case %s." % cell_key)
		object_cells[cell_key] = true
	for object_def in logic_mission_current.interactables:
		if object_def != null and not String(object_def.linked_object_id).is_empty() and not object_ids.has(String(object_def.linked_object_id)):
			issues.append("Objet lié inconnu : %s → %s" % [object_def.id, object_def.linked_object_id])
	var trigger_ids: Dictionary = {}
	for trigger in logic_mission_current.battle_triggers:
		if trigger == null:
			issues.append("Trigger nul")
			continue
		var tid := String(trigger.id)
		if tid.is_empty():
			issues.append("Un trigger n'a pas d'ID")
		elif trigger_ids.has(tid):
			issues.append("ID trigger dupliqué : %s" % tid)
		trigger_ids[tid] = true
		if String(trigger.condition_type) in ["unit_hp_at_most", "unit_defeated"] and String(trigger.condition_unit_id).is_empty():
			issues.append("Le trigger %s nécessite un Unit ID de condition." % tid)
		if String(trigger.condition_type) in ["player_enters_cell", "enemy_enters_cell"] and not _logic_cell_inside(trigger.condition_cell):
			issues.append("Case condition hors grille pour %s." % tid)
		if String(trigger.condition_type) in ["player_enters_zone", "enemy_enters_zone"] and String(trigger.condition_zone_id).is_empty():
			issues.append("Le trigger %s nécessite un Zone ID." % tid)
		if trigger.actions.is_empty():
			issues.append("%s utilise encore l'action legacy V1.4 ; sélectionne-le pour migrer sa séquence." % tid)
		else:
			for action in trigger.actions:
				_validate_logic_action(action, tid, object_ids, issues)
	if issues.is_empty():
		logic_validation.text = "✓ Logique V1.7 valide • %d victoire(s) • %d défaite(s) • %d trigger(s) • %d objet(s)" % [logic_mission_current.victory_rules.size(), logic_mission_current.defeat_rules.size(), logic_mission_current.battle_triggers.size(), logic_mission_current.interactables.size()]
		logic_validation.add_theme_color_override("font_color", Color("#8fe0ad"))
	else:
		logic_validation.text = "⚠ " + "\n• ".join(issues)
		logic_validation.add_theme_color_override("font_color", Color("#ffb36b"))

