extends Node2D

## Sporebound Tactics - gameplay-first tactical battle prototype.
## V0.6 adds a presentation/feedback layer without changing the deterministic combat rules.
## Movement, attacks, projectiles, impacts and initiative now read like a small finished game.
## Everything is still drawn procedurally so the rules can be tested first.

const GRID_WIDTH := 10
const GRID_HEIGHT := 8
const CELL_SIZE := 70.0
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
var bonus_collected = 0
var special_targeting = false
var special_target_cells: Array = []
var terrain_heights: Dictionary = {}
var crown_cell = Vector2i(9, 0)
var crown_carrier_id = ""
var enemies_cleared_logged = false
var mission_victory = false

var selected_id = ""
var hovered_cell = Vector2i(-1, -1)
var move_cells: Array = []
var attack_cells: Array = []
var move_costs: Dictionary = {}
var move_parents: Dictionary = {}
var message_log: Array = []
var current_turn = 1
var enemy_phase = false
var game_over = false
var timeline_order: Array = []
var timeline_index = -1
var active_unit_id = ""
var battle_serial = 0
var animation_time = 0.0

# V0.6 presentation FX. Logical positions/actions remain immediate; these only affect rendering.
var visual_paths: Dictionary = {}
var attack_fx: Dictionary = {}
var hit_fx: Dictionary = {}
var floating_text_fx: Array = []
var projectile_fx: Array = []
var particle_fx: Array = []
var shake_strength = 0.0
var sound_enabled = true
var timeline_bar: HBoxContainer

var turn_label: Label
var selected_label: Label
var status_label: Label
var preview_label: Label
var timeline_label: Label
var log_label: Label
var special_button: Button
var end_turn_button: Button


func _ready() -> void:
	build_ui()
	reset_battle()
	queue_redraw()


func _process(delta: float) -> void:
	animation_time += delta
	shake_strength = max(0.0, shake_strength - delta * 18.0)
	prune_presentation_fx()
	queue_redraw()


func build_ui() -> void:
	var ui_layer = CanvasLayer.new()
	ui_layer.name = "UILayer"
	add_child(ui_layer)

	var root = Control.new()
	root.name = "UI"
	root.position = Vector2.ZERO
	root.size = Vector2(1280.0, 760.0)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui_layer.add_child(root)

	add_label(root, "SPOREBOUND TACTICS", Vector2(46.0, 27.0), Vector2(650.0, 40.0), 30, TEXT)
	add_label(
		root,
		"MVP 0.6 • animations tactiques, impacts, projectiles et initiative visuelle",
		Vector2(48.0, 70.0),
		Vector2(700.0, 28.0),
		15,
		TEXT_SOFT
	)
	status_label = add_label(root, "", Vector2(48.0, 105.0), Vector2(730.0, 30.0), 14, GOLD)

	var panel = Panel.new()
	panel.name = "CommandPanel"
	panel.position = Vector2(804.0, 112.0)
	panel.size = Vector2(430.0, 610.0)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", make_style(PANEL, 22, PANEL_EDGE))
	root.add_child(panel)

	add_label(panel, "POSTE DE COMMANDE", Vector2(24.0, 18.0), Vector2(380.0, 35.0), 22, TEXT)
	add_label(
		panel,
		"MISSION : récupérer la Couronne Beatbox puis revenir dans la zone verte.\nLes ennemis s'intercalent selon l'initiative ; flanc +1, dos +2.",
		Vector2(24.0, 56.0),
		Vector2(380.0, 58.0),
		14,
		TEXT_SOFT
	)
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
		panel, "Action spéciale", Vector2(24.0, 351.0), Vector2(382.0, 44.0)
	)
	special_button.pressed.connect(_on_special_pressed)

	end_turn_button = add_button(panel, "Terminer l'activation", Vector2(24.0, 401.0), Vector2(382.0, 44.0))
	end_turn_button.pressed.connect(_on_end_turn_pressed)

	var restart_button = add_button(
		panel, "Recommencer la mission", Vector2(24.0, 451.0), Vector2(382.0, 39.0)
	)
	restart_button.pressed.connect(reset_battle)

	add_label(
		panel, "JOURNAL DU NARRATEUR", Vector2(24.0, 499.0), Vector2(382.0, 24.0), 12, TEXT_SOFT
	)
	log_label = add_label(panel, "", Vector2(24.0, 523.0), Vector2(382.0, 64.0), 12, TEXT)
	log_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	add_label(
		root,
		(
			"L'unité active est imposée par la timeline. Marche et action peuvent être faites dans l'ordre voulu.\n"
			+ "▲ hauteur • ♛ objectif • ◉ vinyle • spores = 1 dégât • clic droit = orientation • M = sons"
		),
		Vector2(48.0, 711.0),
		Vector2(730.0, 43.0),
		13,
		TEXT_SOFT
	)


func add_label(
	parent: Control, value: String, position: Vector2, size: Vector2, font_size: int, color: Color
) -> Label:
	var label = Label.new()
	label.text = value
	label.position = position
	label.size = size
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label


func add_button(parent: Control, value: String, position: Vector2, size: Vector2) -> Button:
	var button = Button.new()
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
	var style = StyleBoxFlat.new()
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


func reset_battle() -> void:
	battle_serial += 1
	units.clear()
	obstacles = [
		Vector2i(4, 2),
		Vector2i(5, 2),
		Vector2i(4, 5),
		Vector2i(5, 5),
		Vector2i(7, 3),
		Vector2i(2, 3)
	]
	cover_cells = [Vector2i(1, 2), Vector2i(3, 4), Vector2i(6, 4), Vector2i(6, 6), Vector2i(8, 5)]
	hazard_cells = [Vector2i(3, 2), Vector2i(5, 3), Vector2i(6, 5), Vector2i(7, 6)]
	extraction_cells = [Vector2i(0, 7), Vector2i(0, 6), Vector2i(1, 7)]
	bonus_cells = [Vector2i(3, 0), Vector2i(7, 7)]
	bonus_collected = 0
	visual_paths.clear()
	attack_fx.clear()
	hit_fx.clear()
	floating_text_fx.clear()
	projectile_fx.clear()
	particle_fx.clear()
	shake_strength = 0.0
	special_targeting = false
	special_target_cells.clear()
	crown_cell = Vector2i(9, 0)
	crown_carrier_id = ""
	enemies_cleared_logged = false
	mission_victory = false
	timeline_order.clear()
	timeline_index = -1
	active_unit_id = ""
	terrain_heights.clear()
	set_height(
		[
			Vector2i(1, 1),
			Vector2i(2, 1),
			Vector2i(3, 5),
			Vector2i(3, 6),
			Vector2i(6, 1),
			Vector2i(6, 2),
			Vector2i(8, 4)
		],
		1
	)
	set_height([Vector2i(8, 5)], 2)

	units.append(
		make_unit(
			"momo", "Momo", "Brave", "player", Vector2i(1, 6), 13, 3, 4, 1, Color("#f27b72"), "hat"
		)
	)
	units.append(
		make_unit(
			"pipo",
			"Pipo",
			"Soutien",
			"player",
			Vector2i(2, 7),
			10,
			2,
			4,
			1,
			Color("#6cc5c9"),
			"heal"
		)
	)
	units.append(
		make_unit(
			"ziggy",
			"Ziggy",
			"Sporeur funky",
			"player",
			Vector2i(0, 6),
			8,
			2,
			3,
			3,
			Color("#c27be0"),
			"funk"
		)
	)

	units.append(
		make_unit(
			"grincheux",
			"Grincheux",
			"Garde",
			"enemy",
			Vector2i(8, 1),
			8,
			2,
			3,
			1,
			Color("#9a7be0"),
			""
		)
	)
	units.append(
		make_unit(
			"baveux", "Baveux", "Gluant", "enemy", Vector2i(8, 6), 7, 2, 3, 1, Color("#f3a65a"), ""
		)
	)
	units.append(
		make_unit(
			"comptable",
			"Le Comptable",
			"Archer fiscal",
			"enemy",
			Vector2i(6, 0),
			10,
			2,
			2,
			3,
			Color("#e2cf63"),
			""
		)
	)
	units.append(
		make_unit(
			"dj_morille",
			"DJ Morille",
			"Disc-jockey hostile",
			"enemy",
			Vector2i(9, 4),
			7,
			2,
			3,
			2,
			Color("#db6f91"),
			""
		)
	)

	selected_id = ""
	current_turn = 1
	enemy_phase = false
	game_over = false
	message_log.clear()
	log_message("Le roi a encore perdu sa Couronne Beatbox. Elle est au nord-est, évidemment.")
	log_message("MISSION : la récupérer puis revenir dans la zone verte. Éliminer les ennemis est facultatif.")
	start_round()


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
	return {
		"id": id,
		"name": unit_name,
		"role": role,
		"team": team,
		"pos": position,
		"hp": hp,
		"max_hp": hp,
		"attack": attack,
		"move": move_range,
		"range": attack_range,
		"color": color,
		"special": special,
		"initiative": initiative_for_id(id),
		"facing": Vector2i(0, -1) if team == "player" else Vector2i(0, 1),
		"statuses": {},
		"has_moved": false,
		"has_acted": false,
		"reaction_used": false
	}


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var motion_event = event as InputEventMouseMotion
		hovered_cell = world_to_cell(motion_event.position)
		update_preview()
		queue_redraw()
	elif event is InputEventMouseButton:
		var mouse_event = event as InputEventMouseButton
		if mouse_event.button_index == MOUSE_BUTTON_LEFT and mouse_event.pressed:
			var clicked_cell = world_to_cell(mouse_event.position)
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
		var key_event = event as InputEventKey
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
	var unit = selected_unit()
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

	var clicked = unit_at(cell)
	if not clicked.is_empty() and clicked["team"] == "player":
		if clicked["id"] == active_unit_id:
			selected_id = clicked["id"]
			refresh_all()
		else:
			log_message("Pas son activation : la timeline est une petite dictature très organisée.")
			update_ui()
		return

	var unit = selected_unit()
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
	var movement_cost = int(move_costs.get(destination, manhattan(unit["pos"], destination)))
	var origin: Vector2i = unit["pos"]
	var visual_path = movement_path_for(unit, destination)
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
	var terrain_note = ""
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


func perform_attack(attacker: Dictionary, target: Dictionary) -> void:
	var profile = damage_profile(attacker, target)
	attacker["facing"] = direction_from_to(attacker["pos"], target["pos"])
	spawn_damage_feedback(attacker, target, int(profile["damage"]))
	apply_damage(target, int(profile["damage"]))
	if int(profile["guard_penalty"]) > 0:
		remove_status(target, "guarded")
	attacker["has_acted"] = true
	log_message(
		(
			"%s frappe %s : %d dégâts%s."
			% [attacker["name"], target["name"], int(profile["damage"]), profile["summary"]]
		)
	)
	if int(target["hp"]) <= 0:
		log_message("%s est K.O. et dépose une réclamation en trois exemplaires." % target["name"])
	check_mission_end()
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func _on_special_pressed() -> void:
	if game_over or enemy_phase:
		return
	var unit = selected_unit()
	if unit.is_empty() or unit["id"] != active_unit_id or unit["has_acted"]:
		return

	match str(unit["special"]):
		"hat":
			var target = closest_enemy_in_range(unit, 1)
			if target.is_empty():
				log_message("Coup de chapeau impossible : le chapeau refuse le télétravail.")
				update_ui()
				return
			var profile = damage_profile(unit, target, 4, true)
			unit["facing"] = direction_from_to(unit["pos"], target["pos"])
			spawn_damage_feedback(unit, target, int(profile["damage"]), CORAL)
			apply_damage(target, int(profile["damage"]))
			unit["has_acted"] = true
			log_message("Momo déclenche COUP DE CHAPEAU : %d dégâts + poussée." % int(profile["damage"]))
			if int(target["hp"]) > 0:
				push_away(unit["pos"], target, 1, "Coup de chapeau")
			else:
				log_message("%s tombe sous une pluie de confettis administrativement imaginaires." % target["name"])
		"heal":
			var ally = most_injured_ally()
			if ally.is_empty():
				log_message("Pipo ne soigne personne : tout le monde va bien, c'est louche.")
				update_ui()
				return
			var healed = min(4, int(ally["max_hp"]) - int(ally["hp"]))
			ally["hp"] = int(ally["hp"]) + healed
			spawn_floating_text(ally["pos"], "+%d" % healed, MINT)
			spawn_particles(ally["pos"], MINT, 7)
			play_feedback_tone("heal")
			add_status(ally, "guarded")
			unit["has_acted"] = true
			log_message("Pipo lance SAUVETAGE ÉLASTIQUE sur %s : +%d PV, GARDE et traction." % [ally["name"], healed])
			if ally["id"] != unit["id"] and manhattan(unit["pos"], ally["pos"]) > 1:
				pull_toward(unit["pos"], ally, 1, "Sauvetage élastique")
		"funk":
			if special_targeting:
				cancel_special_targeting()
				return
			special_targeting = true
			special_target_cells = special_targetable_cells(unit, 3)
			log_message("SPORE FUNK armé : choisis une case violette. Zone en croix, dégâts + ralenti + poussée.")
			refresh_all()
			return
		_:
			return

	check_mission_end()
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func cancel_special_targeting() -> void:
	special_targeting = false
	special_target_cells.clear()
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func handle_special_target_click(cell: Vector2i) -> void:
	if not special_targeting or not special_target_cells.has(cell):
		log_message("Spore Funk : choisis une case violette valide, ou clic droit pour annuler.")
		update_preview()
		return
	var unit = selected_unit()
	if unit.is_empty() or unit["id"] != active_unit_id or unit["has_acted"] or unit["special"] != "funk":
		cancel_special_targeting()
		return
	execute_spore_funk(unit, cell)


func execute_spore_funk(unit: Dictionary, center: Vector2i) -> void:
	var targets: Array = []
	for target in units:
		if target["team"] == "enemy" and int(target["hp"]) > 0 and manhattan(center, target["pos"]) <= 1:
			targets.append(target)
	unit["facing"] = direction_from_to(unit["pos"], center)
	unit["has_acted"] = true
	special_targeting = false
	special_target_cells.clear()
	if targets.is_empty():
		log_message("Ziggy lâche SPORE FUNK dans le vide. C'était au moins très photogénique.")
	else:
		log_message("Ziggy lâche SPORE FUNK : %d cible(s), 2 dégâts, RALENTI et onde de choc." % targets.size())
	for target in targets:
		spawn_impact_feedback(target, 2, VIOLET, true)
		apply_damage(target, 2)
		if int(target["hp"]) > 0:
			add_status(target, "slowed")
			if target["pos"] != center:
				push_away(center, target, 1, "Onde Spore Funk")
		else:
			log_message("%s est K.O. mais affirme que c'était une figure de danse." % target["name"])
	check_mission_end()
	refresh_all()


func _on_end_turn_pressed() -> void:
	if game_over or enemy_phase:
		return
	if special_targeting:
		cancel_special_targeting()
	var unit = selected_unit()
	if unit.is_empty() or unit["id"] != active_unit_id:
		return
	log_message("%s valide son orientation finale vers %s." % [unit["name"], facing_label(unit)])
	finish_active_player_activation(unit)


func finish_active_player_activation(unit: Dictionary) -> void:
	resolve_end_of_activation(unit)
	if check_mission_end():
		return
	advance_activation()


func run_enemy_activation(enemy: Dictionary) -> void:
	if game_over or int(enemy["hp"]) <= 0:
		return
	log_message("%s entre dans la timeline. Personne n'avait demandé ça." % enemy["name"])
	var destination = choose_enemy_destination(enemy)
	if destination != enemy["pos"]:
		var origin: Vector2i = enemy["pos"]
		var visual_path = movement_path_for(enemy, destination)
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
		var position_note = ""
		if terrain_height(destination) > 0:
			position_note = " en hauteur"
		if cover_cells.has(destination):
			position_note += " sous couverture"
		if hazard_cells.has(destination):
			position_note += " dans des spores douteuses"
		log_message("%s se repositionne%s." % [enemy["name"], position_note])

	var target = best_attackable_player(enemy)
	if not target.is_empty():
		var profile = damage_profile(enemy, target)
		enemy["facing"] = direction_from_to(enemy["pos"], target["pos"])
		spawn_damage_feedback(enemy, target, int(profile["damage"]))
		apply_damage(target, int(profile["damage"]))
		enemy["has_acted"] = true
		if int(profile["guard_penalty"]) > 0:
			remove_status(target, "guarded")
		log_message(
			"%s attaque %s : -%d PV%s."
			% [enemy["name"], target["name"], int(profile["damage"]), profile["summary"]]
		)
		if int(target["hp"]) <= 0:
			log_message("%s est K.O. et réclame une pause goûter." % target["name"])

	resolve_end_of_activation(enemy)
	check_mission_end()


func choose_enemy_destination(enemy: Dictionary) -> Vector2i:
	var navigation = movement_data(enemy)
	var candidates: Array = navigation["cells"].duplicate()
	candidates.append(enemy["pos"])
	var best_cell: Vector2i = enemy["pos"]
	var best_score = 999999.0

	for candidate in candidates:
		var nearest_distance = 999
		var can_attack_target = false
		for player in units:
			if player["team"] != "player" or int(player["hp"]) <= 0:
				continue
			var distance = manhattan(candidate, player["pos"])
			nearest_distance = min(nearest_distance, distance)
			if can_attack_from(enemy, candidate, player):
				can_attack_target = true
		var score = float(nearest_distance * 10)
		if can_attack_target:
			score -= 100.0
		score -= float(terrain_height(candidate) * 3)
		if cover_cells.has(candidate):
			score -= 2.0
		if hazard_cells.has(candidate):
			score += 18.0
		score += float(reaction_risk_for_move(enemy, enemy["pos"], candidate) * 22)
		if not crown_carrier_id.is_empty():
			var carrier = unit_by_id(crown_carrier_id)
			if not carrier.is_empty() and int(carrier["hp"]) > 0:
				score += float(manhattan(candidate, carrier["pos"]) * 2)
				if can_attack_from(enemy, candidate, carrier):
					score -= 35.0
		score += float(navigation["costs"].get(candidate, 0)) * 0.15
		if score < best_score:
			best_score = score
			best_cell = candidate
	return best_cell


func reaction_risk_for_move(mover: Dictionary, origin: Vector2i, destination: Vector2i) -> int:
	var risk = 0
	for reactor in units:
		if reactor["team"] == mover["team"] or int(reactor["hp"]) <= 0:
			continue
		if int(reactor["range"]) != 1 or bool(reactor.get("reaction_used", false)):
			continue
		if manhattan(reactor["pos"], origin) == 1 and manhattan(reactor["pos"], destination) > 1:
			risk += 1
	return risk


func best_attackable_player(enemy: Dictionary) -> Dictionary:
	var best: Dictionary = {}
	var best_score = 999999
	for player in units:
		if player["team"] != "player" or int(player["hp"]) <= 0 or not can_attack(enemy, player):
			continue
		var score = int(player["hp"]) * 3 + manhattan(enemy["pos"], player["pos"])
		if player["id"] == crown_carrier_id:
			score -= 100
		if score < best_score:
			best_score = score
			best = player
	return best


func check_mission_end() -> bool:
	var living_players = alive_count("player")
	var living_enemies = alive_count("enemy")
	if living_players == 0:
		game_over = true
		enemy_phase = false
		mission_victory = false
		selected_id = ""
		active_unit_id = ""
		log_message("DÉFAITE ! La couronne reste libre de poursuivre sa carrière solo.")
		refresh_all()
		return true

	if not crown_carrier_id.is_empty():
		var carrier = unit_by_id(crown_carrier_id)
		if not carrier.is_empty() and int(carrier["hp"]) > 0 and extraction_cells.has(carrier["pos"]):
			game_over = true
			enemy_phase = false
			mission_victory = true
			selected_id = ""
			active_unit_id = ""
			log_message("VICTOIRE ! La Couronne Beatbox est extraite. Bonus vinyles : %d/2." % bonus_collected)
			refresh_all()
			return true

	if living_enemies == 0 and not enemies_cleared_logged:
		enemies_cleared_logged = true
		log_message("Tous les ennemis sont K.O. Bien. Il faut quand même ramener la couronne !")
	return false


func refresh_all() -> void:
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func check_crown_pickup(unit: Dictionary) -> void:
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


func special_targetable_cells(unit: Dictionary, max_range: int) -> Array:
	var result: Array = []
	for y in range(GRID_HEIGHT):
		for x in range(GRID_WIDTH):
			var cell = Vector2i(x, y)
			if manhattan(unit["pos"], cell) <= max_range and has_line_of_sight(unit["pos"], cell, unit["id"], ""):
				result.append(cell)
	return result


func push_away(source_cell: Vector2i, target: Dictionary, distance: int, reason: String) -> void:
	var direction = direction_from_to(source_cell, target["pos"])
	if target["pos"] == source_cell:
		return
	force_move(target, direction, distance, reason)


func pull_toward(source_cell: Vector2i, target: Dictionary, distance: int, reason: String) -> void:
	var direction = direction_from_to(target["pos"], source_cell)
	force_move(target, direction, distance, reason)


func force_move(target: Dictionary, direction: Vector2i, distance: int, reason: String) -> void:
	for _step in range(distance):
		var origin: Vector2i = target["pos"]
		var next_cell: Vector2i = origin + direction
		if not is_walkable(next_cell, target["id"]):
			spawn_impact_feedback(target, 1, CORAL, true)
			apply_damage(target, 1)
			log_message("%s percute un obstacle pendant %s : 1 dégât d'impact." % [target["name"], reason])
			return
		target["pos"] = next_cell
		start_move_animation(str(target["id"]), [origin, next_cell], 0.09)
		spawn_particles(next_cell, VIOLET, 4)
		if target["team"] == "player":
			check_crown_pickup(target)
			check_bonus_pickup(target)
	log_message("%s est déplacé de force par %s." % [target["name"], reason])


func resolve_reactions_on_move(mover: Dictionary, origin: Vector2i, destination: Vector2i) -> void:
	for reactor in units:
		if int(mover["hp"]) <= 0:
			return
		if reactor["team"] == mover["team"] or int(reactor["hp"]) <= 0:
			continue
		if int(reactor["range"]) != 1 or bool(reactor.get("reaction_used", false)):
			continue
		if manhattan(reactor["pos"], origin) != 1 or manhattan(reactor["pos"], destination) <= 1:
			continue
		reactor["reaction_used"] = true
		reactor["facing"] = direction_from_to(reactor["pos"], destination)
		var reaction_damage = max(1, int(reactor["attack"]) - 1)
		spawn_damage_feedback(reactor, mover, reaction_damage, GOLD)
		apply_damage(mover, reaction_damage)
		log_message("RÉACTION : %s frappe %s en désengagement pour %d dégât(s)." % [reactor["name"], mover["name"], reaction_damage])


func resolve_end_of_activation(unit: Dictionary) -> void:
	if int(unit["hp"]) <= 0:
		return
	if hazard_cells.has(unit["pos"]):
		spawn_impact_feedback(unit, 1, VIOLET, false)
		apply_damage(unit, 1)
		log_message("%s subit 1 dégât de spores en fin d'activation." % unit["name"] )
		if int(unit["hp"]) <= 0:
			log_message("%s est K.O. par une flaque. Le rapport sera humiliant." % unit["name"] )
	if has_status(unit, "slowed"):
		remove_status(unit, "slowed")


func start_round() -> void:
	if game_over:
		return
	timeline_order.clear()
	for unit in units:
		if int(unit["hp"]) > 0:
			unit["has_moved"] = false
			unit["has_acted"] = false
			unit["reaction_used"] = false
			timeline_order.append(unit["id"] )
	timeline_order.sort_custom(Callable(self, "timeline_id_before"))
	timeline_index = -1
	log_message("MANCHE %d : initiative recalculée. Les champignons font semblant de comprendre." % current_turn)
	advance_activation()


func advance_activation() -> void:
	if game_over:
		return
	special_targeting = false
	special_target_cells.clear()
	timeline_index += 1
	while timeline_index < timeline_order.size():
		var candidate = unit_by_id(str(timeline_order[timeline_index]))
		if not candidate.is_empty() and int(candidate["hp"]) > 0:
			break
		timeline_index += 1

	if timeline_index >= timeline_order.size():
		current_turn += 1
		start_round()
		return

	var unit = unit_by_id(str(timeline_order[timeline_index]))
	active_unit_id = unit["id"]
	unit["has_moved"] = false
	unit["has_acted"] = false
	if unit["team"] == "player":
		enemy_phase = false
		selected_id = unit["id"]
		log_message("Activation de %s. Déplacement/action dans l'ordre que tu veux." % unit["name"] )
		refresh_all()
	else:
		enemy_phase = true
		selected_id = ""
		refresh_all()
		call_deferred("run_enemy_activation_deferred", str(unit["id"]), battle_serial)


func run_enemy_activation_deferred(enemy_id: String, serial: int) -> void:
	if serial != battle_serial or game_over or active_unit_id != enemy_id:
		return
	var enemy = unit_by_id(enemy_id)
	if enemy.is_empty() or int(enemy["hp"]) <= 0:
		advance_activation()
		return
	run_enemy_activation(enemy)
	refresh_all()
	if not game_over and serial == battle_serial:
		var timer = get_tree().create_timer(0.42)
		timer.timeout.connect(_finish_enemy_presentation.bind(enemy_id, serial))


func _finish_enemy_presentation(enemy_id: String, serial: int) -> void:
	if serial != battle_serial or game_over or active_unit_id != enemy_id:
		return
	advance_activation()


func timeline_id_before(a_id: Variant, b_id: Variant) -> bool:
	var a = unit_by_id(str(a_id))
	var b = unit_by_id(str(b_id))
	if int(a["initiative"]) == int(b["initiative"]):
		if a["team"] != b["team"]:
			return a["team"] == "player"
		return str(a["name"]) < str(b["name"])
	return int(a["initiative"]) > int(b["initiative"])


func unit_by_id(id: String) -> Dictionary:
	for unit in units:
		if unit["id"] == id:
			return unit
	return {}


func alive_count(team: String) -> int:
	var count = 0
	for unit in units:
		if unit["team"] == team and int(unit["hp"]) > 0:
			count += 1
	return count


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
	var unit = selected_unit()
	if unit.is_empty() or enemy_phase or unit["id"] != active_unit_id:
		return
	if special_targeting:
		special_target_cells = special_targetable_cells(unit, 3)
		return
	if not unit["has_moved"]:
		var navigation = movement_data(unit)
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
		var enemy = unit_by_id(active_unit_id)
		turn_label.text = "MANCHE %d • %s JOUE" % [current_turn, enemy["name"]]
		turn_label.add_theme_color_override("font_color", CORAL)
	else:
		var active = selected_unit()
		turn_label.text = "MANCHE %d • %s JOUE" % [current_turn, active["name"] if not active.is_empty() else "À TOI"]
		turn_label.add_theme_color_override("font_color", MINT)

	status_label.text = objective_status_text()
	timeline_label.text = "INITIATIVE • portraits = ordre de jeu"
	rebuild_timeline_bar()
	var unit = selected_unit()
	if unit.is_empty():
		selected_label.text = "Activation ennemie en cours.\nLa timeline décide qui joue ensuite."
		special_button.text = "Action spéciale"
		special_button.disabled = true
	else:
		var terrain_text = "Hauteur %d" % terrain_height(unit["pos"])
		if cover_cells.has(unit["pos"]):
			terrain_text += " • Couvert"
		if hazard_cells.has(unit["pos"]):
			terrain_text += " • SPORES !"
		var move_text = "MVT fait" if unit["has_moved"] else "MVT prêt"
		var act_text = "ACT faite" if unit["has_acted"] else "ACT prête"
		var state_text = status_text(unit)
		if unit["id"] == crown_carrier_id:
			state_text = (state_text + ", " if not state_text.is_empty() else "") + "COURONNE"
		selected_label.text = (
			"%s — %s\nPV %d/%d • MVT %d • Portée %d%s • INIT %d\n%s • face %s • %s / %s%s"
			% [
				unit["name"], unit["role"], int(unit["hp"]), int(unit["max_hp"]), effective_move(unit),
				effective_range(unit), range_bonus_label(unit), int(unit["initiative"]), terrain_text,
				facing_label(unit), move_text, act_text, (" • " + state_text) if not state_text.is_empty() else ""
			]
		)
		match str(unit["special"]):
			"hat": special_button.text = "Coup de chapeau — 4 dégâts + poussée"
			"heal": special_button.text = "Sauvetage élastique — +4 PV + Garde + traction"
			"funk": special_button.text = "Annuler Spore Funk" if special_targeting else "Spore Funk — cibler une zone"
			_: special_button.text = "Action spéciale"
		special_button.disabled = bool(unit["has_acted"])
	end_turn_button.disabled = game_over or enemy_phase
	log_label.text = visible_log()


func rebuild_timeline_bar() -> void:
	if not is_instance_valid(timeline_bar):
		return
	for child in timeline_bar.get_children():
		timeline_bar.remove_child(child)
		child.queue_free()
	var shown = 0
	var start_index = max(0, timeline_index)
	for offset in range(timeline_order.size()):
		var index = (start_index + offset) % max(1, timeline_order.size())
		var unit = unit_by_id(str(timeline_order[index]))
		if unit.is_empty() or int(unit["hp"]) <= 0:
			continue
		var card = PanelContainer.new()
		card.custom_minimum_size = Vector2(49.0, 42.0)
		var active = unit["id"] == active_unit_id
		var fill: Color = unit["color"]
		fill.a = 0.28 if not active else 0.62
		card.add_theme_stylebox_override(
			"panel", make_style(fill, 8, GOLD if active else PANEL_EDGE)
		)
		var label = Label.new()
		var initial = str(unit["name"]).substr(0, 1).to_upper()
		label.text = "%s\n%d" % [initial, int(unit["initiative"])]
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		label.add_theme_font_size_override("font_size", 12)
		label.add_theme_color_override("font_color", TEXT)
		label.tooltip_text = "%s • %s • INIT %d" % [unit["name"], unit["role"], int(unit["initiative"])]
		card.add_child(label)
		timeline_bar.add_child(card)
		shown += 1
		if shown >= 7:
			break


func update_preview() -> void:
	if not is_instance_valid(preview_label):
		return
	if game_over:
		preview_label.text = "R pour relancer une bataille et sauver la couronne autrement."
		return
	if enemy_phase:
		preview_label.text = "Activation ennemie : la prochaine unité est déjà visible dans la timeline."
		return
	var unit = selected_unit()
	if unit.is_empty():
		preview_label.text = "La timeline choisit automatiquement l'unité active."
		return
	if special_targeting:
		if special_target_cells.has(hovered_cell):
			var victims = 0
			for candidate in units:
				if candidate["team"] == "enemy" and int(candidate["hp"]) > 0 and manhattan(hovered_cell, candidate["pos"]) <= 1:
					victims += 1
			preview_label.text = "SPORE FUNK : zone croix rayon 1 • %d cible(s)
2 dégâts + RALENTI + poussée" % victims
		else:
			preview_label.text = "SPORE FUNK : survole puis clique une case violette. Clic droit pour annuler."
		return
	var hovered_unit = unit_at(hovered_cell)
	if (
		not hovered_unit.is_empty()
		and hovered_unit["team"] == "enemy"
		and can_attack(unit, hovered_unit)
	):
		var profile = damage_profile(unit, hovered_unit)
		preview_label.text = (
			"PRÉVISION : %s → %s = %d dégâts\nbase %d%s"
			% [
				unit["name"],
				hovered_unit["name"],
				int(profile["damage"]),
				int(profile["base"]),
				profile["details"]
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
		var terrain_text = "hauteur %d" % terrain_height(hovered_cell)
		if cover_cells.has(hovered_cell):
			terrain_text += " • couverture"
		if hazard_cells.has(hovered_cell):
			terrain_text += " • SPORES : -1 PV fin activation"
		if hovered_cell == crown_cell and crown_carrier_id.is_empty():
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
	var first = max(0, message_log.size() - 5)
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
	var move_budget = effective_move(unit)
	var costs: Dictionary = {}
	var parents: Dictionary = {}
	var frontier: Array = [{"cell": start, "cost": 0}]
	costs[start] = 0

	while not frontier.is_empty():
		var cheapest_index = 0
		for index in range(1, frontier.size()):
			if int(frontier[index]["cost"]) < int(frontier[cheapest_index]["cost"]):
				cheapest_index = index
		var current: Dictionary = frontier.pop_at(cheapest_index)
		var current_cell: Vector2i = current["cell"]
		var current_cost = int(current["cost"])
		if current_cost > int(costs.get(current_cell, move_budget + 1)):
			continue
		for next_cell in neighbours(current_cell):
			if not is_walkable(next_cell, unit["id"]):
				continue
			var next_cost = current_cost + movement_cost(current_cell, next_cell)
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
	var climb = max(0, terrain_height(to_cell) - terrain_height(from_cell))
	return 1 + climb


func neighbours(cell: Vector2i) -> Array:
	return [
		cell + Vector2i(1, 0), cell + Vector2i(-1, 0), cell + Vector2i(0, 1), cell + Vector2i(0, -1)
	]


func is_walkable(cell: Vector2i, ignored_id: String) -> bool:
	if not is_inside(cell) or obstacles.has(cell):
		return false
	for unit in units:
		if unit["id"] != ignored_id and int(unit["hp"]) > 0 and unit["pos"] == cell:
			return false
	return true


func is_inside(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.x < GRID_WIDTH and cell.y >= 0 and cell.y < GRID_HEIGHT


func terrain_height(cell: Vector2i) -> int:
	return int(terrain_heights.get(cell, 0))


func effective_range(unit: Dictionary) -> int:
	return effective_range_at(unit, unit["pos"])


func effective_range_at(unit: Dictionary, position: Vector2i) -> int:
	var result = int(unit["range"])
	if result > 1 and terrain_height(position) >= 2:
		result += 1
	return result


func range_bonus_label(unit: Dictionary) -> String:
	if effective_range(unit) > int(unit["range"]):
		return " (+1 hauteur)"
	return ""


func initiative_for_id(id: String) -> int:
	match id:
		"ziggy":
			return 8
		"dj_morille":
			return 7
		"pipo":
			return 6
		"baveux":
			return 6
		"momo":
			return 5
		"grincheux":
			return 5
		"comptable":
			return 4
		_:
			return 5


func initiative_before(a: Dictionary, b: Dictionary) -> bool:
	if int(a["initiative"]) == int(b["initiative"]):
		return str(a["name"]) < str(b["name"])
	return int(a["initiative"]) > int(b["initiative"])


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
		labels.append("%s %d" % [short_name(str(unit["name"])), int(unit["initiative"])])
	if labels.is_empty():
		return "—"
	return " > ".join(labels)


func timeline_summary() -> String:
	if timeline_order.is_empty():
		return "—"
	var labels: Array = []
	for index in range(timeline_order.size()):
		var unit = unit_by_id(str(timeline_order[index]))
		if unit.is_empty() or int(unit["hp"]) <= 0:
			continue
		var marker = "▶" if index == timeline_index else ""
		labels.append("%s%s %d" % [marker, short_name(str(unit["name"])), int(unit["initiative"])])
	return " > ".join(labels)


func objective_status_text() -> String:
	if game_over:
		return "Couronne extraite • mission accomplie" if mission_victory else "Escouade K.O. • mission échouée"
	if crown_carrier_id.is_empty():
		return (
			"OBJECTIF : atteindre ♛ (%d,%d) • Vinyles %d/2 • Équipe %d/3 • Ennemis %d/4"
			% [crown_cell.x + 1, crown_cell.y + 1, bonus_collected, alive_count("player"), alive_count("enemy")]
		)
	var carrier = unit_by_id(crown_carrier_id)
	return "COURONNE : %s • sortie verte • Vinyles %d/2 • Équipe %d/3 • Ennemis %d/4" % [carrier["name"], bonus_collected, alive_count("player"), alive_count("enemy")]


func short_name(value: String) -> String:
	if value == "Le Comptable":
		return "Compta"
	if value == "DJ Morille":
		return "DJ"
	return value


func effective_move(unit: Dictionary) -> int:
	var value = int(unit["move"])
	if has_status(unit, "slowed"):
		value -= 1
	return max(1, value)


func add_status(unit: Dictionary, status_id: String) -> void:
	var statuses: Dictionary = unit.get("statuses", {})
	statuses[status_id] = true
	unit["statuses"] = statuses


func remove_status(unit: Dictionary, status_id: String) -> void:
	var statuses: Dictionary = unit.get("statuses", {})
	statuses.erase(status_id)
	unit["statuses"] = statuses


func has_status(unit: Dictionary, status_id: String) -> bool:
	var statuses: Dictionary = unit.get("statuses", {})
	return bool(statuses.get(status_id, false))


func status_text(unit: Dictionary) -> String:
	var labels: Array = []
	if has_status(unit, "guarded"):
		labels.append("GARDE")
	if has_status(unit, "slowed"):
		labels.append("RALENTI")
	if int(unit["range"]) == 1 and not bool(unit.get("reaction_used", false)):
		labels.append("RÉACTION PRÊTE")
	return ", ".join(labels)


func facing_label(unit: Dictionary) -> String:
	var facing: Vector2i = unit.get("facing", Vector2i(0, 1))
	if facing == Vector2i(0, -1):
		return "N"
	if facing == Vector2i(1, 0):
		return "E"
	if facing == Vector2i(0, 1):
		return "S"
	return "O"


func direction_from_to(from_cell: Vector2i, to_cell: Vector2i) -> Vector2i:
	var delta = to_cell - from_cell
	if delta == Vector2i.ZERO:
		return Vector2i(0, 1)
	if abs(delta.x) >= abs(delta.y):
		return Vector2i(1 if delta.x > 0 else -1, 0)
	return Vector2i(0, 1 if delta.y > 0 else -1)


func is_back_attack(attacker: Dictionary, target: Dictionary) -> bool:
	var target_facing: Vector2i = target.get("facing", Vector2i(0, 1))
	var attack_side = direction_from_to(target["pos"], attacker["pos"])
	return attack_side == -target_facing


func is_side_attack(attacker: Dictionary, target: Dictionary) -> bool:
	var target_facing: Vector2i = target.get("facing", Vector2i(0, 1))
	var attack_side = direction_from_to(target["pos"], attacker["pos"])
	return attack_side != target_facing and attack_side != -target_facing


func line_cells(from_cell: Vector2i, to_cell: Vector2i) -> Array:
	var result: Array = []
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


func has_line_of_sight(
	from_cell: Vector2i, to_cell: Vector2i, source_id: String = "", target_id: String = ""
) -> bool:
	if manhattan(from_cell, to_cell) <= 1:
		return true
	var cells = line_cells(from_cell, to_cell)
	for index in range(1, cells.size() - 1):
		var cell: Vector2i = cells[index]
		if obstacles.has(cell):
			return false
		var blocker = unit_at(cell)
		if (
			not blocker.is_empty()
			and blocker["id"] != source_id
			and blocker["id"] != target_id
		):
			return false
	return true


func can_attack_from(attacker: Dictionary, from_cell: Vector2i, target: Dictionary) -> bool:
	if manhattan(from_cell, target["pos"]) > effective_range_at(attacker, from_cell):
		return false
	if int(attacker["range"]) <= 1:
		return true
	return has_line_of_sight(from_cell, target["pos"], attacker["id"], target["id"])


func can_attack(attacker: Dictionary, target: Dictionary) -> bool:
	return can_attack_from(attacker, attacker["pos"], target)


func damage_profile(
	attacker: Dictionary, target: Dictionary, base_override: int = -1, ignore_cover: bool = false
) -> Dictionary:
	var base_damage = int(attacker["attack"]) if base_override < 0 else base_override
	var height_bonus = 1 if terrain_height(attacker["pos"]) > terrain_height(target["pos"]) else 0
	var back_bonus = 2 if is_back_attack(attacker, target) else 0
	var side_bonus = 1 if not is_back_attack(attacker, target) and is_side_attack(attacker, target) else 0
	var cover_penalty = 0
	if not ignore_cover and int(attacker["range"]) > 1 and cover_cells.has(target["pos"]):
		cover_penalty = 1
	var guard_penalty = 1 if has_status(target, "guarded") else 0
	var damage = max(1, base_damage + height_bonus + back_bonus + side_bonus - cover_penalty - guard_penalty)
	var summary = ""
	var details = ""
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
		summary += " (-1 garde)"
		details += " -1 garde"
	return {
		"base": base_damage,
		"height_bonus": height_bonus,
		"back_bonus": back_bonus,
		"side_bonus": side_bonus,
		"cover_penalty": cover_penalty,
		"guard_penalty": guard_penalty,
		"damage": damage,
		"summary": summary,
		"details": details
	}


func apply_damage(target: Dictionary, amount: int) -> void:
	var was_alive = int(target["hp"]) > 0
	target["hp"] = max(0, int(target["hp"]) - amount)
	if was_alive and int(target["hp"]) <= 0 and target["id"] == crown_carrier_id:
		crown_carrier_id = ""
		crown_cell = target["pos"]
		log_message("La COURONNE tombe en (%d,%d) !" % [crown_cell.x + 1, crown_cell.y + 1])


func closest_enemy_in_range(source: Dictionary, range_value: int) -> Dictionary:
	var best: Dictionary = {}
	var best_distance = 999
	for unit in units:
		if unit["team"] == "enemy" and int(unit["hp"]) > 0:
			var distance = manhattan(source["pos"], unit["pos"])
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
	var lowest_ratio = 1.1
	for unit in units:
		if (
			unit["team"] != "player"
			or int(unit["hp"]) <= 0
			or int(unit["hp"]) >= int(unit["max_hp"])
		):
			continue
		var ratio = float(unit["hp"]) / float(unit["max_hp"])
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
	return abs(a.x - b.x) + abs(a.y - b.y)


func cell_to_world(cell: Vector2i) -> Vector2:
	return BOARD_ORIGIN + Vector2(float(cell.x) * CELL_SIZE, float(cell.y) * CELL_SIZE)


func world_to_cell(point: Vector2) -> Vector2i:
	var local = point - BOARD_ORIGIN
	return Vector2i(floor(local.x / CELL_SIZE), floor(local.y / CELL_SIZE))


func hover_path() -> Array:
	var unit = selected_unit()
	if unit.is_empty() or not move_cells.has(hovered_cell):
		return []
	var path: Array = [hovered_cell]
	var current = hovered_cell
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
	var navigation = movement_data(unit)
	var parents: Dictionary = navigation["parents"]
	if not parents.has(destination):
		return [start, destination]
	var path: Array = [destination]
	var current = destination
	var safety = GRID_WIDTH * GRID_HEIGHT + 2
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
		+ Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
		+ Vector2(0.0, -float(terrain_height(cell) * 3))
	)


func unit_visual_center(unit: Dictionary) -> Vector2:
	var unit_id = str(unit["id"])
	if not visual_paths.has(unit_id):
		return visual_center_for_cell(unit["pos"])
	var fx: Dictionary = visual_paths[unit_id]
	var path: Array = fx["path"]
	if path.size() < 2:
		return visual_center_for_cell(unit["pos"])
	var step_duration = max(0.01, float(fx["step_duration"]))
	var step_value = max(0.0, animation_time - float(fx["started"])) / step_duration
	var segment_count = path.size() - 1
	if step_value >= float(segment_count):
		return visual_center_for_cell(path[path.size() - 1])
	var segment = clampi(int(floor(step_value)), 0, segment_count - 1)
	var local_progress = clampf(step_value - float(segment), 0.0, 1.0)
	local_progress = local_progress * local_progress * (3.0 - 2.0 * local_progress)
	var from_position = visual_center_for_cell(path[segment])
	var to_position = visual_center_for_cell(path[segment + 1])
	return from_position.lerp(to_position, local_progress)


func start_attack_dash(attacker: Dictionary, target: Dictionary, distance: float = 13.0) -> void:
	var attacker_pos: Vector2i = attacker["pos"]
	var target_pos: Vector2i = target["pos"]
	var direction = Vector2(
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
	var progress = clampf(
		(animation_time - float(fx["started"])) / max(0.01, float(fx["duration"])), 0.0, 1.0
	)
	return fx["direction"] * sin(progress * PI) * float(fx["distance"])


func hit_flash_amount(unit_id: String) -> float:
	if not hit_fx.has(unit_id):
		return 0.0
	var remaining = float(hit_fx[unit_id]) - animation_time
	return clampf(remaining / 0.18, 0.0, 1.0)


func spawn_damage_feedback(
	attacker: Dictionary, target: Dictionary, amount: int, accent: Color = CORAL
) -> void:
	if int(attacker["range"]) <= 1:
		start_attack_dash(attacker, target)
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
	var origin = visual_center_for_cell(cell)
	for index in range(count):
		var angle = float(index) * TAU / float(max(1, count)) + float(cell.x + cell.y) * 0.31
		var speed = 30.0 + float((index * 17) % 42)
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
	prune_fx_array(floating_text_fx)
	prune_fx_array(projectile_fx)
	prune_fx_array(particle_fx)


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


func draw_presentation_fx() -> void:
	for fx_value in projectile_fx:
		var fx: Dictionary = fx_value
		var progress = clampf(
			(animation_time - float(fx["started"])) / max(0.01, float(fx["duration"])), 0.0, 1.0
		)
		var eased = 1.0 - pow(1.0 - progress, 2.0)
		var start: Vector2 = fx["from"]
		var finish: Vector2 = fx["to"]
		var current = start.lerp(finish, eased)
		var trail_start = start.lerp(finish, max(0.0, eased - 0.18))
		var color: Color = fx["color"]
		draw_line(trail_start, current, Color(color.r, color.g, color.b, 0.55), 5.0, true)
		draw_circle(current, 6.0, color)
		draw_circle(current, 2.5, Color.WHITE)
	for fx_value in particle_fx:
		var fx: Dictionary = fx_value
		var age = max(0.0, animation_time - float(fx["started"]))
		var duration = max(0.01, float(fx["duration"]))
		var progress = clampf(age / duration, 0.0, 1.0)
		var position: Vector2 = fx["origin"] + fx["velocity"] * age + Vector2(0.0, 55.0 * age * age)
		var color: Color = fx["color"]
		color.a = 1.0 - progress
		draw_circle(position, float(fx["radius"]) * (1.0 - progress * 0.35), color)
	for fx_value in floating_text_fx:
		var fx: Dictionary = fx_value
		var age = max(0.0, animation_time - float(fx["started"]))
		var duration = max(0.01, float(fx["duration"]))
		var progress = clampf(age / duration, 0.0, 1.0)
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
	var frequency = 330.0
	var duration = 0.055
	var volume = 0.12
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
	var stream = make_tone_stream(frequency, duration, volume)
	if stream == null:
		return
	var player = AudioStreamPlayer.new()
	player.stream = stream
	player.volume_db = -4.0
	add_child(player)
	player.finished.connect(Callable(player, "queue_free"))
	player.play()


func make_tone_stream(frequency: float, duration: float, volume: float) -> AudioStreamWAV:
	var mix_rate = 22050
	var sample_count = max(1, int(float(mix_rate) * duration))
	var bytes = PackedByteArray()
	bytes.resize(sample_count * 2)
	for sample_index in range(sample_count):
		var t = float(sample_index) / float(mix_rate)
		var envelope = 1.0 - float(sample_index) / float(sample_count)
		var value = int(sin(TAU * frequency * t) * 32767.0 * volume * envelope)
		bytes.encode_s16(sample_index * 2, clampi(value, -32768, 32767))
	var stream = AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = mix_rate
	stream.stereo = false
	stream.data = bytes
	return stream


func _draw() -> void:
	var viewport_size = get_viewport_rect().size
	draw_rect(Rect2(Vector2.ZERO, viewport_size), BG, true)

	for index in range(14):
		var x = 18.0 + float((index * 113) % 1260)
		var y = 18.0 + float((index * 67) % 735)
		var radius = 2.0 + float(index % 3)
		draw_circle(Vector2(x, y), radius, Color(0.45, 0.82, 0.72, 0.12))

	draw_set_transform(battlefield_shake_offset(), 0.0, Vector2.ONE)
	var board_size = Vector2(float(GRID_WIDTH) * CELL_SIZE, float(GRID_HEIGHT) * CELL_SIZE)
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

	for y in range(GRID_HEIGHT):
		for x in range(GRID_WIDTH):
			var cell = Vector2i(x, y)
			var rect = Rect2(cell_to_world(cell), Vector2(CELL_SIZE - 1.0, CELL_SIZE - 1.0))
			var fill = GRID_A if (x + y) % 2 == 0 else GRID_B
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

	draw_hover_path()
	draw_special_telegraph()
	draw_targeting_preview()

	for obstacle in obstacles:
		draw_obstacle(obstacle)

	if crown_carrier_id.is_empty():
		draw_crown(crown_cell)
	for bonus_cell in bonus_cells:
		draw_bonus_vinyl(bonus_cell)

	for unit in units:
		if int(unit["hp"]) > 0:
			draw_unit(unit)
	draw_presentation_fx()
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	if game_over:
		var banner_color = (
			Color(0.145, 0.294, 0.271, 0.94)
			if mission_victory
			else Color(0.357, 0.188, 0.220, 0.94)
		)
		draw_rect(
			Rect2(BOARD_ORIGIN + Vector2(95.0, 232.0), Vector2(510.0, 92.0)), banner_color, true
		)
		var banner = "MISSION RÉUSSIE !" if mission_victory else "MISSION ÉCHOUÉE !"
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
			var offset = Vector2(14.0 + float((index * 13) % 43), 22.0 + float((index * 17) % 31))
			draw_circle(rect.position + offset, 8.0 + float(index % 2) * 3.0, Color(HAZARD.r, HAZARD.g, HAZARD.b, 0.38))
			draw_circle(rect.position + offset + Vector2(2.0, -2.0), 2.0, Color(0.92, 0.78, 1.0, 0.65))
	var height = terrain_height(cell)
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
		var base = rect.position + Vector2(12.0, 57.0)
		for index in range(3):
			var leaf_position = base + Vector2(float(index * 12), -float((index % 2) * 5))
			draw_circle(leaf_position, 7.0, Color("#477d69"))
			draw_circle(leaf_position + Vector2(5.0, -2.0), 5.0, Color("#70a36f"))


func draw_hover_path() -> void:
	var path = hover_path()
	if path.size() < 2:
		return
	for index in range(path.size() - 1):
		var from_position = cell_to_world(path[index]) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
		var to_position = (
			cell_to_world(path[index + 1]) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
		)
		draw_line(from_position, to_position, Color(1.0, 0.82, 0.35, 0.80), 4.0, true)
		draw_circle(to_position, 4.0, GOLD)


func draw_special_telegraph() -> void:
	if not special_targeting:
		return
	for cell in special_target_cells:
		var rect = Rect2(cell_to_world(cell) + Vector2(4.0, 4.0), Vector2(CELL_SIZE - 9.0, CELL_SIZE - 9.0))
		draw_rect(rect, Color(VIOLET.r, VIOLET.g, VIOLET.b, 0.10), true)
	if special_target_cells.has(hovered_cell):
		for y in range(GRID_HEIGHT):
			for x in range(GRID_WIDTH):
				var cell = Vector2i(x, y)
				if manhattan(hovered_cell, cell) <= 1:
					var rect = Rect2(cell_to_world(cell) + Vector2(5.0, 5.0), Vector2(CELL_SIZE - 11.0, CELL_SIZE - 11.0))
					draw_rect(rect, Color(VIOLET.r, VIOLET.g, VIOLET.b, 0.30), true)
					draw_rect(rect, VIOLET, false, 2.0)


func draw_bonus_vinyl(cell: Vector2i) -> void:
	var center = cell_to_world(cell) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
	var pulse = 1.0 + sin(animation_time * 4.5 + float(cell.x)) * 0.06
	draw_circle(center, 17.0 * pulse, Color(0.08, 0.08, 0.11, 0.95))
	draw_circle(center, 9.0 * pulse, VIOLET)
	draw_circle(center, 3.0, GOLD)
	draw_arc(center, 21.0, 0.0, TAU, 24, Color(VIOLET.r, VIOLET.g, VIOLET.b, 0.45), 2.0, true)
	draw_string(ThemeDB.fallback_font, center + Vector2(-20.0, 31.0), "VINYLE", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 9, GOLD)


func draw_targeting_preview() -> void:
	var attacker = selected_unit()
	var target = unit_at(hovered_cell)
	if attacker.is_empty() or target.is_empty() or target["team"] != "enemy":
		return
	if manhattan(attacker["pos"], target["pos"]) > effective_range(attacker):
		return
	var start = cell_to_world(attacker["pos"]) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
	var finish = cell_to_world(target["pos"]) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
	var clear = can_attack(attacker, target)
	var line_color = MINT if clear else CORAL
	draw_line(start, finish, Color(line_color.r, line_color.g, line_color.b, 0.68), 3.0, true)


func draw_crown(cell: Vector2i) -> void:
	var center = cell_to_world(cell) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
	draw_circle(center, 20.0 + sin(animation_time * 4.0) * 2.0, Color(CROWN.r, CROWN.g, CROWN.b, 0.17))
	var points = PackedVector2Array([
		center + Vector2(-18.0, 8.0), center + Vector2(-15.0, -10.0), center + Vector2(-5.0, 0.0),
		center + Vector2(0.0, -15.0), center + Vector2(7.0, 0.0), center + Vector2(16.0, -10.0),
		center + Vector2(18.0, 8.0)
	])
	draw_polyline(points, CROWN, 4.0, true)
	draw_line(center + Vector2(-18.0, 8.0), center + Vector2(18.0, 8.0), CROWN, 4.0, true)
	draw_string(ThemeDB.fallback_font, center + Vector2(-8.0, 29.0), "♛", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 18, CROWN)


func draw_obstacle(cell: Vector2i) -> void:
	var rect = Rect2(
		cell_to_world(cell) + Vector2(8.0, 8.0), Vector2(CELL_SIZE - 17.0, CELL_SIZE - 17.0)
	)
	draw_rect(rect, Color("#1b2b3d"), true)
	var center = rect.position + rect.size * 0.5
	draw_circle(center + Vector2(-13.0, 8.0), 13.0, Color("#56726f"))
	draw_circle(center + Vector2(12.0, 7.0), 16.0, Color("#6f8c7b"))
	draw_circle(center + Vector2(0.0, -9.0), 19.0, Color("#9ab58d"))
	draw_circle(center + Vector2(-6.0, -13.0), 3.0, Color("#dce8bc"))
	draw_circle(center + Vector2(7.0, -8.0), 3.0, Color("#dce8bc"))


func draw_unit(unit: Dictionary) -> void:
	var cell: Vector2i = unit["pos"]
	var center = unit_visual_center(unit) + attack_offset_for_unit(str(unit["id"]))
	var bob = sin(animation_time * 3.0 + float(cell.x)) * 1.5
	center.y += bob
	var unit_color: Color = unit["color"]
	var flash = hit_flash_amount(str(unit["id"]))
	if flash > 0.0:
		unit_color = unit_color.lerp(Color.WHITE, flash * 0.78)
	var is_player = unit["team"] == "player"
	var selected = unit["id"] == selected_id

	if selected or unit["id"] == active_unit_id:
		draw_arc(center + Vector2(0.0, 2.0), 29.0, 0.0, TAU, 32, GOLD, 3.0, true)
	if unit["has_acted"] and is_player:
		draw_circle(center + Vector2(25.0, -25.0), 7.0, Color("#64788a"))
	if int(unit["range"]) == 1 and not bool(unit.get("reaction_used", false)):
		draw_arc(center, 31.0, -0.55, 0.55, 10, Color(GOLD.r, GOLD.g, GOLD.b, 0.55), 2.0, true)

	var facing: Vector2i = unit.get("facing", Vector2i(0, 1))
	var facing_vector = Vector2(float(facing.x), float(facing.y))
	var arrow_start = center + facing_vector * 28.0
	var arrow_end = center + facing_vector * 35.0
	draw_line(arrow_start, arrow_end, GOLD, 3.0, true)
	draw_circle(arrow_end, 3.5, GOLD)

	draw_rect(Rect2(center + Vector2(-13.0, 3.0), Vector2(26.0, 24.0)), Color("#f3e5c0"), true)
	draw_circle(center + Vector2(0.0, 26.0), 13.0, Color("#f3e5c0"))
	draw_circle(center + Vector2(0.0, -3.0), 25.0, Color("#251c32"))
	draw_circle(center + Vector2(0.0, -7.0), 22.0, unit_color)
	draw_circle(center + Vector2(-8.0, -11.0), 4.0, Color(1.0, 1.0, 1.0, 0.7))
	draw_circle(center + Vector2(8.0, -11.0), 4.0, Color(1.0, 1.0, 1.0, 0.7))
	draw_circle(center + Vector2(-7.0, -4.0), 3.0, Color("#251c32"))
	draw_circle(center + Vector2(7.0, -4.0), 3.0, Color("#251c32"))
	draw_arc(center + Vector2(0.0, 1.0), 7.0, 0.15, PI - 0.15, 12, Color("#251c32"), 2.0, true)

	if unit["id"] == "ziggy":
		draw_arc(center + Vector2(20.0, -17.0), 5.0, 0.0, TAU, 10, GOLD, 2.0, true)
		draw_line(center + Vector2(24.0, -20.0), center + Vector2(24.0, -31.0), GOLD, 2.0, true)
	elif unit["id"] == "pipo":
		draw_line(
			center + Vector2(19.0, -26.0), center + Vector2(19.0, -14.0), Color.WHITE, 3.0, true
		)
		draw_line(
			center + Vector2(13.0, -20.0), center + Vector2(25.0, -20.0), Color.WHITE, 3.0, true
		)

	if is_player:
		draw_line(
			center + Vector2(-17.0, 18.0), center + Vector2(-29.0, 8.0), unit_color, 4.0, true
		)
		draw_line(center + Vector2(17.0, 18.0), center + Vector2(29.0, 8.0), unit_color, 4.0, true)
	else:
		draw_line(
			center + Vector2(-18.0, 18.0), center + Vector2(-27.0, 25.0), unit_color, 4.0, true
		)
		draw_line(center + Vector2(18.0, 18.0), center + Vector2(27.0, 25.0), unit_color, 4.0, true)

	if has_status(unit, "guarded"):
		draw_circle(center + Vector2(-24.0, -27.0), 8.0, SKY)
		draw_string(ThemeDB.fallback_font, center + Vector2(-28.0, -23.0), "G", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 10, BG)
	if has_status(unit, "slowed"):
		draw_circle(center + Vector2(-24.0, -27.0), 8.0, VIOLET)
		draw_string(ThemeDB.fallback_font, center + Vector2(-28.0, -23.0), "R", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 10, BG)

	if unit["id"] == crown_carrier_id:
		var crown_center = center + Vector2(0.0, -42.0)
		draw_line(crown_center + Vector2(-9.0, 5.0), crown_center + Vector2(-7.0, -5.0), CROWN, 2.0, true)
		draw_line(crown_center + Vector2(-7.0, -5.0), crown_center, CROWN, 2.0, true)
		draw_line(crown_center, crown_center + Vector2(6.0, -5.0), CROWN, 2.0, true)
		draw_line(crown_center + Vector2(6.0, -5.0), crown_center + Vector2(9.0, 5.0), CROWN, 2.0, true)
		draw_line(crown_center + Vector2(-9.0, 5.0), crown_center + Vector2(9.0, 5.0), CROWN, 2.0, true)

	var bar_position = center + Vector2(-27.0, 38.0)
	draw_rect(Rect2(bar_position, Vector2(54.0, 6.0)), Color("#111722"), true)
	var hp_ratio = float(unit["hp"]) / float(unit["max_hp"])
	var hp_color = MINT if is_player else CORAL
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
