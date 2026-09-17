extends Node2D

## Sporebound Tactics - gameplay-first tactical battle prototype.
## V0.3 adds line of sight, facing/back attacks, initiative and lightweight statuses.
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

var units: Array = []
var obstacles: Array = []
var cover_cells: Array = []
var terrain_heights: Dictionary = {}

var selected_id := ""
var hovered_cell := Vector2i(-1, -1)
var move_cells: Array = []
var attack_cells: Array = []
var move_costs: Dictionary = {}
var move_parents: Dictionary = {}
var message_log: Array = []
var current_turn := 1
var enemy_phase := false
var game_over := false
var animation_time := 0.0

var turn_label: Label
var selected_label: Label
var status_label: Label
var preview_label: Label
var log_label: Label
var special_button: Button
var end_turn_button: Button


func _ready() -> void:
	build_ui()
	reset_battle()
	queue_redraw()


func _process(delta: float) -> void:
	animation_time += delta
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
		"MVP 0.3 • ligne de vue, orientation, initiative et états",
		Vector2(48.0, 70.0),
		Vector2(700.0, 28.0),
		15,
		TEXT_SOFT
	)
	status_label = add_label(root, "", Vector2(48.0, 105.0), Vector2(720.0, 30.0), 17, GOLD)

	var panel := Panel.new()
	panel.name = "CommandPanel"
	panel.position = Vector2(804.0, 112.0)
	panel.size = Vector2(430.0, 610.0)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", make_style(PANEL, 22, PANEL_EDGE))
	root.add_child(panel)

	add_label(panel, "POSTE DE COMMANDE", Vector2(24.0, 18.0), Vector2(380.0, 35.0), 22, TEXT)
	add_label(
		panel,
		"Objectif : mettre les quatre adversaires K.O.\nLes obstacles bloquent les tirs • attaquer dans le dos donne +1.",
		Vector2(24.0, 56.0),
		Vector2(380.0, 55.0),
		14,
		TEXT_SOFT
	)
	turn_label = add_label(panel, "", Vector2(24.0, 119.0), Vector2(380.0, 32.0), 20, GOLD)
	selected_label = add_label(panel, "", Vector2(24.0, 158.0), Vector2(380.0, 80.0), 15, TEXT)
	preview_label = add_label(panel, "", Vector2(24.0, 237.0), Vector2(380.0, 50.0), 14, GOLD)
	preview_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	special_button = add_button(
		panel, "Action spéciale", Vector2(24.0, 293.0), Vector2(382.0, 47.0)
	)
	special_button.pressed.connect(_on_special_pressed)

	end_turn_button = add_button(panel, "Fin du tour", Vector2(24.0, 348.0), Vector2(382.0, 47.0))
	end_turn_button.pressed.connect(_on_end_turn_pressed)

	var restart_button := add_button(
		panel, "Recommencer la bataille", Vector2(24.0, 403.0), Vector2(382.0, 41.0)
	)
	restart_button.pressed.connect(reset_battle)

	add_label(
		panel, "JOURNAL DU NARRATEUR", Vector2(24.0, 459.0), Vector2(382.0, 26.0), 13, TEXT_SOFT
	)
	log_label = add_label(panel, "", Vector2(24.0, 486.0), Vector2(382.0, 100.0), 13, TEXT)
	log_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	add_label(
		root,
		"CLIQUE un héros, puis une case verte pour marcher ou un ennemi rouge pour frapper.\n▲ hauteur • feuillage = couvert • clic droit = orienter • R = recommencer • Entrée = fin du tour",
		Vector2(48.0, 711.0),
		Vector2(730.0, 43.0),
		13,
		TEXT_SOFT
	)


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


func reset_battle() -> void:
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

	selected_id = "momo"
	current_turn = 1
	enemy_phase = false
	game_over = false
	message_log.clear()
	log_message("Le roi a encore perdu sa couronne. Cette fois, elle fait du beatbox.")
	log_message("Ziggy : je couvre l'arrière. Et probablement les basses.")
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


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
		"has_acted": false
	}


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var motion_event := event as InputEventMouseMotion
		hovered_cell = world_to_cell(motion_event.position)
		update_preview()
		queue_redraw()
	elif event is InputEventMouseButton:
		var mouse_event := event as InputEventMouseButton
		if mouse_event.button_index == MOUSE_BUTTON_LEFT and mouse_event.pressed:
			handle_board_click(world_to_cell(mouse_event.position))
		elif mouse_event.button_index == MOUSE_BUTTON_RIGHT and mouse_event.pressed:
			orient_selected_toward(world_to_cell(mouse_event.position))
	elif event is InputEventKey:
		var key_event := event as InputEventKey
		if key_event.pressed and not key_event.echo:
			if key_event.keycode == KEY_R:
				reset_battle()
			elif key_event.keycode == KEY_ENTER:
				_on_end_turn_pressed()
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
	if unit.is_empty() or unit["has_acted"] or cell == unit["pos"]:
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
		if not clicked["has_acted"]:
			selected_id = clicked["id"]
			log_message("%s prend une pose tactique certifiée très sérieuse." % clicked["name"])
		else:
			log_message("%s a terminé son action. Son syndicat exige une pause." % clicked["name"])
		update_selection()
		update_ui()
		update_preview()
		queue_redraw()
		return

	var unit := selected_unit()
	if unit.is_empty() or unit["has_acted"]:
		return

	if clicked.is_empty() and not unit["has_moved"] and move_cells.has(cell):
		perform_move(unit, cell)
	elif not clicked.is_empty() and clicked["team"] == "enemy" and attack_cells.has(cell):
		perform_attack(unit, clicked)
	else:
		log_message("Cette case n'est pas disponible. Même le narrateur ne peut pas tricher.")
		update_ui()
		update_preview()


func perform_move(unit: Dictionary, destination: Vector2i) -> void:
	var movement_cost := int(move_costs.get(destination, manhattan(unit["pos"], destination)))
	var origin: Vector2i = unit["pos"]
	unit["facing"] = direction_from_to(origin, destination)
	unit["pos"] = destination
	unit["has_moved"] = true
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


func perform_attack(attacker: Dictionary, target: Dictionary) -> void:
	var profile := damage_profile(attacker, target)
	attacker["facing"] = direction_from_to(attacker["pos"], target["pos"])
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
	finish_player_action()


func _on_special_pressed() -> void:
	if game_over or enemy_phase:
		return
	var unit := selected_unit()
	if unit.is_empty() or unit["has_acted"]:
		return

	match str(unit["special"]):
		"hat":
			var target := closest_enemy_in_range(unit, 1)
			if target.is_empty():
				log_message("Coup de chapeau impossible : le chapeau refuse le télétravail.")
				update_ui()
				return
			var profile := damage_profile(unit, target, 5, true)
			unit["facing"] = direction_from_to(unit["pos"], target["pos"])
			apply_damage(target, int(profile["damage"]))
			unit["has_acted"] = true
			log_message(
				(
					"Momo déclenche COUP DE CHAPEAU : %d dégâts. La mode souffre, l'ennemi aussi."
					% int(profile["damage"])
				)
			)
			if int(target["hp"]) <= 0:
				log_message(
					(
						"%s tombe sous une pluie de confettis administrativement imaginaires."
						% target["name"]
					)
				)
		"heal":
			var ally := most_injured_ally()
			if ally.is_empty():
				log_message("Pipo ne soigne personne : tout le monde va bien, c'est louche.")
				update_ui()
				return
			var healed := min(4, int(ally["max_hp"]) - int(ally["hp"]))
			ally["hp"] = int(ally["hp"]) + healed
			add_status(ally, "guarded")
			unit["has_acted"] = true
			log_message(
				(
					"Pipo pose un PANSEMENT PREMIUM sur %s : +%d PV et GARDE (-1 au prochain coup)."
					% [ally["name"], healed]
				)
			)
		"funk":
			var targets := enemies_in_radius(unit["pos"], 3)
			if targets.is_empty():
				log_message("Spore Funk ne touche personne. Ziggy accuse l'acoustique de la salle.")
				update_ui()
				return
			for target in targets:
				apply_damage(target, 2)
				if int(target["hp"]) > 0:
					add_status(target, "slowed")
			unit["has_acted"] = true
			log_message(
				(
					"Ziggy lance SPORE FUNK : %d cible(s), 2 dégâts et RALENTI au prochain déplacement."
					% targets.size()
				)
			)
			for target in targets:
				if int(target["hp"]) <= 0:
					log_message(
						"%s est K.O. mais prétend avoir dansé volontairement." % target["name"]
					)
		_:
			return

	finish_player_action()


func _on_end_turn_pressed() -> void:
	if game_over or enemy_phase:
		return
	log_message("L'équipe termine son tour. Les ennemis ouvrent leur PowerPoint tactique.")
	run_enemy_phase()


func finish_player_action() -> void:
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()
	if check_battle_end():
		return
	if all_players_acted():
		run_enemy_phase()


func run_enemy_phase() -> void:
	if game_over:
		return
	enemy_phase = true
	selected_id = ""
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()

	log_message("Phase ennemie : leur stratégie contient maintenant deux diapositives.")
	for enemy in living_enemies_by_initiative():
		var destination := choose_enemy_destination(enemy)
		if destination != enemy["pos"]:
			var origin: Vector2i = enemy["pos"]
			enemy["facing"] = direction_from_to(origin, destination)
			enemy["pos"] = destination
			var position_note := ""
			if terrain_height(destination) > 0:
				position_note = " en hauteur"
			if cover_cells.has(destination):
				position_note += " sous couverture"
			log_message(
				(
					"%s se repositionne%s et fait comme si c'était prévu."
					% [enemy["name"], position_note]
				)
			)

		var target := best_attackable_player(enemy)
		if not target.is_empty():
			var profile := damage_profile(enemy, target)
			enemy["facing"] = direction_from_to(enemy["pos"], target["pos"])
			apply_damage(target, int(profile["damage"]))
			if int(profile["guard_penalty"]) > 0:
				remove_status(target, "guarded")
			log_message(
				(
					"%s attaque %s : -%d PV%s."
					% [enemy["name"], target["name"], int(profile["damage"]), profile["summary"]]
				)
			)
			if int(target["hp"]) <= 0:
				log_message("%s est K.O. et réclame une pause goûter." % target["name"])
			if check_battle_end():
				return
		if has_status(enemy, "slowed"):
			remove_status(enemy, "slowed")

	enemy_phase = false
	current_turn += 1
	for unit in units:
		if unit["team"] == "player" and int(unit["hp"]) > 0:
			remove_status(unit, "guarded")
			unit["has_moved"] = false
			unit["has_acted"] = false
	selected_id = first_available_player_id()
	log_message("À toi ! Les ennemis prétendent que le lag explique leur performance.")
	update_selection()
	update_ui()
	update_preview()
	queue_redraw()


func choose_enemy_destination(enemy: Dictionary) -> Vector2i:
	var navigation := movement_data(enemy)
	var candidates: Array = navigation["cells"].duplicate()
	candidates.append(enemy["pos"])
	var best_cell: Vector2i = enemy["pos"]
	var best_score := 999999.0

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
		var score := float(nearest_distance * 10)
		if can_attack_target:
			score -= 100.0
		score -= float(terrain_height(candidate) * 3)
		if cover_cells.has(candidate):
			score -= 2.0
		score += float(navigation["costs"].get(candidate, 0)) * 0.15
		if score < best_score:
			best_score = score
			best_cell = candidate
	return best_cell


func best_attackable_player(enemy: Dictionary) -> Dictionary:
	var best: Dictionary = {}
	var best_score := 999999
	for player in units:
		if player["team"] != "player" or int(player["hp"]) <= 0 or not can_attack(enemy, player):
			continue
		var score := int(player["hp"]) * 3 + manhattan(enemy["pos"], player["pos"])
		if score < best_score:
			best_score = score
			best = player
	return best


func check_battle_end() -> bool:
	var living_players := alive_count("player")
	var living_enemies := alive_count("enemy")
	if living_enemies == 0:
		game_over = true
		enemy_phase = false
		selected_id = ""
		log_message(
			"VICTOIRE ! La couronne est sauvée. Elle signe déjà un contrat d'album avec Ziggy."
		)
		update_selection()
		update_ui()
		update_preview()
		queue_redraw()
		return true
	if living_players == 0:
		game_over = true
		enemy_phase = false
		selected_id = ""
		log_message("DÉFAITE ! Le narrateur appelle cela une répétition générale très immersive.")
		update_selection()
		update_ui()
		update_preview()
		queue_redraw()
		return true
	return false


func all_players_acted() -> bool:
	for unit in units:
		if unit["team"] == "player" and int(unit["hp"]) > 0 and not unit["has_acted"]:
			return false
	return true


func alive_count(team: String) -> int:
	var count := 0
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
	var unit := selected_unit()
	if unit.is_empty() or enemy_phase or unit["has_acted"]:
		return
	if not unit["has_moved"]:
		var navigation := movement_data(unit)
		move_cells = navigation["cells"]
		move_costs = navigation["costs"]
		move_parents = navigation["parents"]
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
		turn_label.text = "BATAILLE TERMINÉE"
		turn_label.add_theme_color_override("font_color", GOLD)
	elif enemy_phase:
		turn_label.text = "TOUR %d • PHASE ENNEMIE" % current_turn
		turn_label.add_theme_color_override("font_color", CORAL)
	else:
		turn_label.text = "TOUR %d • À TOI" % current_turn
		turn_label.add_theme_color_override("font_color", MINT)

	status_label.text = (
		"Équipe %d/3 • Adversaires %d/4 • Initiative ennemie : %s"
		% [alive_count("player"), alive_count("enemy"), enemy_initiative_summary()]
	)
	var unit := selected_unit()
	if unit.is_empty():
		selected_label.text = "Aucun héros sélectionné.\nClique Momo, Pipo ou Ziggy sur la grille."
		special_button.text = "Action spéciale"
		special_button.disabled = true
	else:
		var terrain_text := "Hauteur %d" % terrain_height(unit["pos"])
		if cover_cells.has(unit["pos"]):
			terrain_text += " • Couvert"
		var action_text := "déplacement fait" if unit["has_moved"] else "déplacement prêt"
		var state_text := status_text(unit)
		if not state_text.is_empty():
			state_text = " • " + state_text
		selected_label.text = (
			"%s — %s\nPV %d/%d • MVT %d/%d • Portée %d%s • INIT %d\n%s • face %s • %s%s"
			% [
				unit["name"],
				unit["role"],
				int(unit["hp"]),
				int(unit["max_hp"]),
				effective_move(unit),
				int(unit["move"]),
				effective_range(unit),
				range_bonus_label(unit),
				int(unit["initiative"]),
				terrain_text,
				facing_label(unit),
				action_text,
				state_text
			]
		)
		match str(unit["special"]):
			"hat":
				special_button.text = "Coup de chapeau — 5 dégâts au contact"
			"heal":
				special_button.text = "Pansement premium — +4 PV + Garde"
			"funk":
				special_button.text = "Spore Funk — 2 dégâts + Ralenti rayon 3"
			_:
				special_button.text = "Action spéciale"
		special_button.disabled = bool(unit["has_acted"])
	end_turn_button.disabled = game_over or enemy_phase
	log_label.text = visible_log()


func update_preview() -> void:
	if not is_instance_valid(preview_label):
		return
	if game_over:
		preview_label.text = "R pour relancer une bataille et sauver la couronne autrement."
		return
	if enemy_phase:
		preview_label.text = "Les ennemis calculent très fort. Enfin, ils essaient."
		return
	var unit := selected_unit()
	if unit.is_empty():
		preview_label.text = "Sélectionne un héros pour afficher ses options."
		return
	var hovered_unit := unit_at(hovered_cell)
	if (
		not hovered_unit.is_empty()
		and hovered_unit["team"] == "enemy"
		and can_attack(unit, hovered_unit)
	):
		var profile := damage_profile(unit, hovered_unit)
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
		var terrain_text := "hauteur %d" % terrain_height(hovered_cell)
		if cover_cells.has(hovered_cell):
			terrain_text += " • couverture"
		preview_label.text = (
			"TRAJET : %d point(s) de déplacement\n%s"
			% [int(move_costs.get(hovered_cell, 0)), terrain_text]
		)
	else:
		preview_label.text = "Survole une case verte ou une cible rouge pour prévoir l'action."


func visible_log() -> String:
	var visible: Array = []
	var first := max(0, message_log.size() - 5)
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
	var climb := max(0, terrain_height(to_cell) - terrain_height(from_cell))
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
	var result := int(unit["range"])
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


func short_name(value: String) -> String:
	if value == "Le Comptable":
		return "Compta"
	if value == "DJ Morille":
		return "DJ"
	return value


func effective_move(unit: Dictionary) -> int:
	var value := int(unit["move"])
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
	var delta := to_cell - from_cell
	if delta == Vector2i.ZERO:
		return Vector2i(0, 1)
	if abs(delta.x) >= abs(delta.y):
		return Vector2i(1 if delta.x > 0 else -1, 0)
	return Vector2i(0, 1 if delta.y > 0 else -1)


func is_back_attack(attacker: Dictionary, target: Dictionary) -> bool:
	var target_facing: Vector2i = target.get("facing", Vector2i(0, 1))
	var attack_side := direction_from_to(target["pos"], attacker["pos"])
	return attack_side == -target_facing


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
	var cells := line_cells(from_cell, to_cell)
	for index in range(1, cells.size() - 1):
		var cell: Vector2i = cells[index]
		if obstacles.has(cell):
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
	var base_damage := int(attacker["attack"]) if base_override < 0 else base_override
	var height_bonus := 1 if terrain_height(attacker["pos"]) > terrain_height(target["pos"]) else 0
	var back_bonus := 1 if is_back_attack(attacker, target) else 0
	var cover_penalty := 0
	if not ignore_cover and int(attacker["range"]) > 1 and cover_cells.has(target["pos"]):
		cover_penalty = 1
	var guard_penalty := 1 if has_status(target, "guarded") else 0
	var damage := max(1, base_damage + height_bonus + back_bonus - cover_penalty - guard_penalty)
	var summary := ""
	var details := ""
	if height_bonus > 0:
		summary += " (+1 hauteur)"
		details += " +1 hauteur"
	if back_bonus > 0:
		summary += " (+1 dos)"
		details += " +1 dos"
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
		"cover_penalty": cover_penalty,
		"guard_penalty": guard_penalty,
		"damage": damage,
		"summary": summary,
		"details": details
	}


func apply_damage(target: Dictionary, amount: int) -> void:
	target["hp"] = max(0, int(target["hp"]) - amount)


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
	return abs(a.x - b.x) + abs(a.y - b.y)


func cell_to_world(cell: Vector2i) -> Vector2:
	return BOARD_ORIGIN + Vector2(float(cell.x) * CELL_SIZE, float(cell.y) * CELL_SIZE)


func world_to_cell(point: Vector2) -> Vector2i:
	var local := point - BOARD_ORIGIN
	return Vector2i(floor(local.x / CELL_SIZE), floor(local.y / CELL_SIZE))


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


func _draw() -> void:
	var viewport_size := get_viewport_rect().size
	draw_rect(Rect2(Vector2.ZERO, viewport_size), BG, true)

	for index in range(14):
		var x := 18.0 + float((index * 113) % 1260)
		var y := 18.0 + float((index * 67) % 735)
		var radius := 2.0 + float(index % 3)
		draw_circle(Vector2(x, y), radius, Color(0.45, 0.82, 0.72, 0.12))

	var board_size := Vector2(float(GRID_WIDTH) * CELL_SIZE, float(GRID_HEIGHT) * CELL_SIZE)
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
			var cell := Vector2i(x, y)
			var rect := Rect2(cell_to_world(cell), Vector2(CELL_SIZE - 1.0, CELL_SIZE - 1.0))
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

	draw_hover_path()
	draw_targeting_preview()

	for obstacle in obstacles:
		draw_obstacle(obstacle)

	for unit in units:
		if int(unit["hp"]) > 0:
			draw_unit(unit)

	if game_over:
		var banner_color := (
			Color(0.145, 0.294, 0.271, 0.94)
			if alive_count("enemy") == 0
			else Color(0.357, 0.188, 0.220, 0.94)
		)
		draw_rect(
			Rect2(BOARD_ORIGIN + Vector2(95.0, 232.0), Vector2(510.0, 92.0)), banner_color, true
		)
		var banner := "VICTOIRE !" if alive_count("enemy") == 0 else "DÉFAITE !"
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
		var from_position := cell_to_world(path[index]) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
		var to_position := (
			cell_to_world(path[index + 1]) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
		)
		draw_line(from_position, to_position, Color(1.0, 0.82, 0.35, 0.80), 4.0, true)
		draw_circle(to_position, 4.0, GOLD)


func draw_targeting_preview() -> void:
	var attacker := selected_unit()
	var target := unit_at(hovered_cell)
	if attacker.is_empty() or target.is_empty() or target["team"] != "enemy":
		return
	if manhattan(attacker["pos"], target["pos"]) > effective_range(attacker):
		return
	var start := cell_to_world(attacker["pos"]) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
	var finish := cell_to_world(target["pos"]) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
	var clear := can_attack(attacker, target)
	var line_color := MINT if clear else CORAL
	draw_line(start, finish, Color(line_color.r, line_color.g, line_color.b, 0.68), 3.0, true)


func draw_obstacle(cell: Vector2i) -> void:
	var rect := Rect2(
		cell_to_world(cell) + Vector2(8.0, 8.0), Vector2(CELL_SIZE - 17.0, CELL_SIZE - 17.0)
	)
	draw_rect(rect, Color("#1b2b3d"), true)
	var center := rect.position + rect.size * 0.5
	draw_circle(center + Vector2(-13.0, 8.0), 13.0, Color("#56726f"))
	draw_circle(center + Vector2(12.0, 7.0), 16.0, Color("#6f8c7b"))
	draw_circle(center + Vector2(0.0, -9.0), 19.0, Color("#9ab58d"))
	draw_circle(center + Vector2(-6.0, -13.0), 3.0, Color("#dce8bc"))
	draw_circle(center + Vector2(7.0, -8.0), 3.0, Color("#dce8bc"))


func draw_unit(unit: Dictionary) -> void:
	var cell: Vector2i = unit["pos"]
	var center := cell_to_world(cell) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
	var bob := sin(animation_time * 3.0 + float(cell.x)) * 1.5
	center.y += bob - float(terrain_height(cell) * 3)
	var unit_color: Color = unit["color"]
	var is_player := unit["team"] == "player"
	var selected := unit["id"] == selected_id

	if selected:
		draw_arc(center + Vector2(0.0, 2.0), 29.0, 0.0, TAU, 32, GOLD, 3.0, true)
	if unit["has_acted"] and is_player:
		draw_circle(center + Vector2(25.0, -25.0), 7.0, Color("#64788a"))

	var facing: Vector2i = unit.get("facing", Vector2i(0, 1))
	var facing_vector := Vector2(float(facing.x), float(facing.y))
	var arrow_start := center + facing_vector * 28.0
	var arrow_end := center + facing_vector * 35.0
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
