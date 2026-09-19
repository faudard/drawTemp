extends Node2D

## Sporebound Tactics - gameplay-first tactical battle prototype.
## Everything is drawn procedurally so the rules can be tested before final art.

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
const MOVE_HIGHLIGHT := Color(0.482, 0.878, 0.678, 0.28)
const ATTACK_HIGHLIGHT := Color(1.0, 0.482, 0.447, 0.30)
const HOVER_HIGHLIGHT := Color(1.0, 0.941, 0.659, 0.18)

var units: Array = []
var obstacles: Array = []
var selected_id = ""
var hovered_cell = Vector2i(-1, -1)
var move_cells: Array = []
var attack_cells: Array = []
var message_log: Array = []
var current_turn = 1
var enemy_phase = false
var game_over = false
var animation_time = 0.0

var turn_label: Label
var selected_label: Label
var status_label: Label
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
	add_label(root, "prototype de combat • le royaume a besoin d'un champignon", Vector2(48.0, 70.0), Vector2(700.0, 28.0), 15, TEXT_SOFT)
	status_label = add_label(root, "", Vector2(48.0, 105.0), Vector2(720.0, 30.0), 17, GOLD)

	var panel = Panel.new()
	panel.name = "CommandPanel"
	panel.position = Vector2(804.0, 112.0)
	panel.size = Vector2(430.0, 610.0)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", make_style(PANEL, 22, PANEL_EDGE))
	root.add_child(panel)

	add_label(panel, "POSTE DE COMMANDE", Vector2(24.0, 20.0), Vector2(380.0, 35.0), 22, TEXT)
	add_label(panel, "Objectif : mettre les trois adversaires\nK.O. sans perdre toute l'équipe.", Vector2(24.0, 58.0), Vector2(380.0, 52.0), 15, TEXT_SOFT)
	turn_label = add_label(panel, "", Vector2(24.0, 124.0), Vector2(380.0, 32.0), 20, GOLD)
	selected_label = add_label(panel, "", Vector2(24.0, 166.0), Vector2(380.0, 70.0), 16, TEXT)

	special_button = add_button(panel, "Action spéciale", Vector2(24.0, 250.0), Vector2(382.0, 48.0))
	special_button.pressed.connect(_on_special_pressed)

	end_turn_button = add_button(panel, "Fin du tour", Vector2(24.0, 307.0), Vector2(382.0, 48.0))
	end_turn_button.pressed.connect(_on_end_turn_pressed)

	var restart_button = add_button(panel, "Recommencer la bataille", Vector2(24.0, 364.0), Vector2(382.0, 42.0))
	restart_button.pressed.connect(reset_battle)

	add_label(panel, "JOURNAL DU NARRATEUR", Vector2(24.0, 427.0), Vector2(382.0, 28.0), 13, TEXT_SOFT)
	log_label = add_label(panel, "", Vector2(24.0, 457.0), Vector2(382.0, 113.0), 14, TEXT)
	log_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	add_label(root, "CLIQUE une unité alliée, puis une case verte pour marcher ou un ennemi rouge pour frapper.\nUne unité peut marcher puis agir une fois. R = recommencer • Entrée = fin du tour • Échap = désélectionner", Vector2(48.0, 712.0), Vector2(730.0, 42.0), 13, TEXT_SOFT)


func add_label(parent: Control, value: String, position: Vector2, size: Vector2, font_size: int, color: Color) -> Label:
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
	button.add_theme_font_size_override("font_size", 16)
	button.add_theme_color_override("font_color", TEXT)
	button.add_theme_color_override("font_hover_color", BG)
	button.add_theme_color_override("font_pressed_color", BG)
	button.add_theme_color_override("font_disabled_color", Color(TEXT_SOFT.r, TEXT_SOFT.g, TEXT_SOFT.b, 0.48))
	button.add_theme_stylebox_override("normal", make_style(Color("#2d4860"), 12, Color("#52728b")))
	button.add_theme_stylebox_override("hover", make_style(Color("#7be0ad"), 12, Color("#b5f2d0")))
	button.add_theme_stylebox_override("pressed", make_style(Color("#ffd166"), 12, Color("#fff0a8")))
	button.add_theme_stylebox_override("disabled", make_style(Color("#263344"), 12, Color("#33485e")))
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
	units.clear()
	obstacles = [
		Vector2i(4, 2), Vector2i(5, 2),
		Vector2i(4, 5), Vector2i(5, 5),
		Vector2i(7, 3), Vector2i(7, 4),
		Vector2i(2, 3)
	]

	units.append(make_unit("momo", "Momo", "Héros", "player", Vector2i(1, 6), 12, 3, 4, Color("#f27b72")))
	units.append(make_unit("pipo", "Pipo", "Soutien", "player", Vector2i(2, 6), 9, 2, 4, Color("#6cc5c9")))
	units.append(make_unit("grincheux", "Grincheux", "Garde", "enemy", Vector2i(8, 1), 7, 2, 3, Color("#a87be0")))
	units.append(make_unit("baveux", "Baveux", "Gluant", "enemy", Vector2i(8, 6), 6, 2, 3, Color("#f3a65a")))
	units.append(make_unit("comptable", "Le Comptable", "Boss administratif", "enemy", Vector2i(6, 0), 10, 1, 2, Color("#e2cf63")))

	selected_id = "momo"
	current_turn = 1
	enemy_phase = false
	game_over = false
	message_log.clear()
	log_message("Le roi a perdu sa couronne. Elle est sous un tabouret.")
	log_message("Momo : on récupère la couronne et on évite les réunions.")
	update_selection()
	update_ui()
	queue_redraw()


func make_unit(id: String, unit_name: String, role: String, team: String, position: Vector2i, hp: int, attack: int, move_range: int, color: Color) -> Dictionary:
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
		"range": 1,
		"color": color,
		"has_moved": false,
		"has_acted": false
	}


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var motion_event = event as InputEventMouseMotion
		hovered_cell = world_to_cell(motion_event.position)
		queue_redraw()
	elif event is InputEventMouseButton:
		var mouse_event = event as InputEventMouseButton
		if mouse_event.button_index == MOUSE_BUTTON_LEFT and mouse_event.pressed:
			handle_board_click(world_to_cell(mouse_event.position))
	elif event is InputEventKey:
		var key_event = event as InputEventKey
		if key_event.pressed and not key_event.echo:
			if key_event.keycode == KEY_R:
				reset_battle()
			elif key_event.keycode == KEY_ENTER:
				_on_end_turn_pressed()
			elif key_event.keycode == KEY_ESCAPE:
				selected_id = ""
				update_selection()
				update_ui()
				queue_redraw()


func handle_board_click(cell: Vector2i) -> void:
	if game_over or enemy_phase or not is_inside(cell):
		return

	var clicked = unit_at(cell)
	if not clicked.is_empty():
		if clicked["team"] == "player":
			if not clicked["has_acted"]:
				selected_id = clicked["id"]
				log_message("%s prend la pose héroïque. Elle dure trois secondes." % clicked["name"])
			else:
				log_message("%s a déjà joué. Même les héros ont besoin d'une pause." % clicked["name"])
			update_selection()
			update_ui()
			queue_redraw()
			return

	var unit = selected_unit()
	if unit.is_empty() or unit["has_acted"]:
		return

	if clicked.is_empty() and not unit["has_moved"] and move_cells.has(cell):
		perform_move(unit, cell)
	elif not clicked.is_empty() and clicked["team"] == "enemy" and attack_cells.has(cell):
		perform_attack(unit, clicked)
	else:
		log_message("Cette case n'est pas dans le menu du jour.")


func perform_move(unit: Dictionary, destination: Vector2i) -> void:
	var old_position = unit["pos"]
	unit["pos"] = destination
	unit["has_moved"] = true
	log_message("%s avance de %d cases. La démarche est héroïque, la trajectoire moins." % [unit["name"], manhattan(old_position, destination)])
	finish_player_action()


func perform_attack(attacker: Dictionary, target: Dictionary) -> void:
	var damage = int(attacker["attack"])
	target["hp"] = max(0, int(target["hp"]) - damage)
	attacker["has_acted"] = true
	log_message("%s frappe %s pour %d dégâts. Le service réclamation est fermé." % [attacker["name"], target["name"], damage])
	if int(target["hp"]) <= 0:
		log_message("%s est K.O. Il demande un replay au ralenti." % target["name"])
	finish_player_action()


func _on_special_pressed() -> void:
	if game_over or enemy_phase:
		return
	var unit = selected_unit()
	if unit.is_empty() or unit["has_acted"]:
		return

	if unit["id"] == "momo":
		var target = closest_enemy_in_range(unit, 1)
		if target.is_empty():
			log_message("Coup de chapeau impossible : Momo doit être au contact. Le chapeau refuse le télétravail.")
			update_ui()
			return
		target["hp"] = max(0, int(target["hp"]) - 5)
		unit["has_acted"] = true
		log_message("Momo déclenche COUP DE CHAPEAU : 5 dégâts. Élégance discutable, efficacité correcte.")
		if int(target["hp"]) <= 0:
			log_message("%s tombe sous une pluie de confettis imaginaires." % target["name"])
	else:
		var ally = most_injured_ally()
		if ally.is_empty():
			log_message("Pipo ne soigne personne : tout le monde va bien, c'est suspect.")
			update_ui()
			return
		var healed = min(3, int(ally["max_hp"]) - int(ally["hp"]))
		ally["hp"] = int(ally["hp"]) + healed
		unit["has_acted"] = true
		log_message("Pipo lance SOIN D'URGENCE sur %s : +%d PV. Pansement homologué par personne." % [ally["name"], healed])

	finish_player_action()


func _on_end_turn_pressed() -> void:
	if game_over or enemy_phase:
		return
	log_message("L'équipe termine son tour. Les ennemis ont probablement un plan.")
	run_enemy_phase()


func finish_player_action() -> void:
	update_selection()
	update_ui()
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
	queue_redraw()

	log_message("Phase ennemie : ils ont tenu une réunion de 4 secondes.")
	for enemy in units:
		if enemy["team"] != "enemy" or int(enemy["hp"]) <= 0:
			continue
		var target = closest_player(enemy)
		if target.is_empty():
			break
		var step = enemy_step(enemy, target)
		if step != enemy["pos"]:
			enemy["pos"] = step
			log_message("%s avance. Personne ne sait pourquoi, mais il semble sûr de lui." % enemy["name"])
		if manhattan(enemy["pos"], target["pos"]) <= int(enemy["range"]):
			var damage = int(enemy["attack"])
			target["hp"] = max(0, int(target["hp"]) - damage)
			log_message("%s attaque %s : -%d PV. C'était légal dans leur royaume." % [enemy["name"], target["name"], damage])
			if int(target["hp"]) <= 0:
				log_message("%s est K.O. et réclame une pause goûter." % target["name"])
			if check_battle_end():
				return

	enemy_phase = false
	current_turn += 1
	for unit in units:
		if unit["team"] == "player" and int(unit["hp"]) > 0:
			unit["has_moved"] = false
			unit["has_acted"] = false
	selected_id = first_available_player_id()
	log_message("À toi ! Les champignons ennemis font semblant d'être surpris.")
	update_selection()
	update_ui()
	queue_redraw()


func check_battle_end() -> bool:
	var living_players = alive_count("player")
	var living_enemies = alive_count("enemy")
	if living_enemies == 0:
		game_over = true
		enemy_phase = false
		selected_id = ""
		log_message("VICTOIRE ! La couronne est retrouvée. Elle était bien sous le tabouret.")
		update_selection()
		update_ui()
		queue_redraw()
		return true
	if living_players == 0:
		game_over = true
		enemy_phase = false
		selected_id = ""
		log_message("DÉFAITE ! Le narrateur affirme que c'était un exercice pédagogique.")
		update_selection()
		update_ui()
		queue_redraw()
		return true
	return false


func all_players_acted() -> bool:
	for unit in units:
		if unit["team"] == "player" and int(unit["hp"]) > 0 and not unit["has_acted"]:
			return false
	return true


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
	var unit = selected_unit()
	if unit.is_empty() or enemy_phase or unit["has_acted"]:
		return
	if not unit["has_moved"]:
		move_cells = reachable_cells(unit)
	for candidate in units:
		if candidate["team"] == "enemy" and int(candidate["hp"]) > 0 and manhattan(unit["pos"], candidate["pos"]) <= int(unit["range"]):
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

	status_label.text = "Équipe %d/%d   •   Adversaires %d/%d" % [alive_count("player"), 2, alive_count("enemy"), 3]
	var unit = selected_unit()
	if unit.is_empty():
		selected_label.text = "Aucune unité sélectionnée.\nClique Momo ou Pipo sur la grille."
		special_button.text = "Action spéciale"
		special_button.disabled = true
	else:
		selected_label.text = "%s — %s\nPV %d/%d   •   Déplacement %d   •   Attaque %d" % [unit["name"], unit["role"], int(unit["hp"]), int(unit["max_hp"]), int(unit["move"]), int(unit["attack"])]
		if unit["id"] == "momo":
			special_button.text = "Coup de chapeau — 5 dégâts au contact"
		else:
			special_button.text = "Soin d'urgence — +3 PV au plus blessé"
		special_button.disabled = bool(unit["has_acted"])
	end_turn_button.disabled = game_over or enemy_phase
	log_label.text = visible_log()


func visible_log() -> String:
	var visible: Array = []
	var first = max(0, message_log.size() - 7)
	for index in range(first, message_log.size()):
		visible.append("• " + str(message_log[index]))
	return "\n".join(visible)


func log_message(message: String) -> void:
	message_log.append(message)
	if message_log.size() > 14:
		message_log.pop_front()
	if is_instance_valid(log_label):
		log_label.text = visible_log()


func reachable_cells(unit: Dictionary) -> Array:
	var result: Array = []
	var start: Vector2i = unit["pos"]
	var visited = {start: true}
	var queue: Array = [{"cell": start, "distance": 0}]
	while not queue.is_empty():
		var current: Dictionary = queue.pop_front()
		var current_cell: Vector2i = current["cell"]
		var distance: int = current["distance"]
		if distance >= int(unit["move"]):
			continue
		for next_cell in neighbours(current_cell):
			if visited.has(next_cell) or not is_inside(next_cell) or not is_walkable(next_cell, unit["id"]):
				continue
			visited[next_cell] = true
			result.append(next_cell)
			queue.append({"cell": next_cell, "distance": distance + 1})
	return result


func neighbours(cell: Vector2i) -> Array:
	return [
		cell + Vector2i(1, 0),
		cell + Vector2i(-1, 0),
		cell + Vector2i(0, 1),
		cell + Vector2i(0, -1)
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


func closest_player(source: Dictionary) -> Dictionary:
	var best: Dictionary = {}
	var best_distance = 999
	for unit in units:
		if unit["team"] == "player" and int(unit["hp"]) > 0:
			var distance = manhattan(source["pos"], unit["pos"])
			if distance < best_distance:
				best = unit
				best_distance = distance
	return best


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


func most_injured_ally() -> Dictionary:
	var best: Dictionary = {}
	var lowest_ratio = 1.1
	for unit in units:
		if unit["team"] != "player" or int(unit["hp"]) <= 0 or int(unit["hp"]) >= int(unit["max_hp"]):
			continue
		var ratio = float(unit["hp"]) / float(unit["max_hp"])
		if ratio < lowest_ratio:
			best = unit
			lowest_ratio = ratio
	return best


func enemy_step(enemy: Dictionary, target: Dictionary) -> Vector2i:
	var current: Vector2i = enemy["pos"]
	var candidates = neighbours(current)
	var best = current
	var best_distance = manhattan(current, target["pos"])
	for candidate in candidates:
		if not is_walkable(candidate, enemy["id"]):
			continue
		var distance = manhattan(candidate, target["pos"])
		if distance < best_distance:
			best = candidate
			best_distance = distance
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


func _draw() -> void:
	var viewport_size = get_viewport_rect().size
	draw_rect(Rect2(Vector2.ZERO, viewport_size), BG, true)

	# Quiet decorative spores in the background.
	for index in range(14):
		var x = 18.0 + float((index * 113) % 1260)
		var y = 18.0 + float((index * 67) % 735)
		var radius = 2.0 + float(index % 3)
		draw_circle(Vector2(x, y), radius, Color(0.45, 0.82, 0.72, 0.12))

	var board_size = Vector2(float(GRID_WIDTH) * CELL_SIZE, float(GRID_HEIGHT) * CELL_SIZE)
	draw_rect(Rect2(BOARD_ORIGIN - Vector2(10.0, 10.0), board_size + Vector2(20.0, 20.0)), Color("#0a111e"), true)
	draw_rect(Rect2(BOARD_ORIGIN - Vector2(5.0, 5.0), board_size + Vector2(10.0, 10.0)), Color("#496879"), true)

	for y in range(GRID_HEIGHT):
		for x in range(GRID_WIDTH):
			var cell = Vector2i(x, y)
			var rect = Rect2(cell_to_world(cell), Vector2(CELL_SIZE - 1.0, CELL_SIZE - 1.0))
			var fill = GRID_A if (x + y) % 2 == 0 else GRID_B
			draw_rect(rect, fill, true)
			draw_rect(rect, GRID_LINE, false, 1.0)
			if move_cells.has(cell):
				draw_rect(rect, MOVE_HIGHLIGHT, true)
			if attack_cells.has(cell):
				draw_rect(rect, ATTACK_HIGHLIGHT, true)
			if hovered_cell == cell and is_inside(cell):
				draw_rect(rect, HOVER_HIGHLIGHT, true)

	for obstacle in obstacles:
		draw_obstacle(obstacle)

	for unit in units:
		if int(unit["hp"]) > 0:
			draw_unit(unit)

	if game_over:
		var banner_color = Color(0.145, 0.294, 0.271, 0.94) if alive_count("enemy") == 0 else Color(0.357, 0.188, 0.220, 0.94)
		draw_rect(Rect2(BOARD_ORIGIN + Vector2(95.0, 232.0), Vector2(510.0, 92.0)), banner_color, true)
		var banner = "VICTOIRE !" if alive_count("enemy") == 0 else "DÉFAITE !"
		draw_string(ThemeDB.fallback_font, BOARD_ORIGIN + Vector2(250.0, 290.0), banner, HORIZONTAL_ALIGNMENT_CENTER, 200.0, 30, TEXT)


func draw_obstacle(cell: Vector2i) -> void:
	var rect = Rect2(cell_to_world(cell) + Vector2(8.0, 8.0), Vector2(CELL_SIZE - 17.0, CELL_SIZE - 17.0))
	draw_rect(rect, Color("#1b2b3d"), true)
	var center = rect.position + rect.size * 0.5
	draw_circle(center + Vector2(-13.0, 8.0), 13.0, Color("#56726f"))
	draw_circle(center + Vector2(12.0, 7.0), 16.0, Color("#6f8c7b"))
	draw_circle(center + Vector2(0.0, -9.0), 19.0, Color("#9ab58d"))
	draw_circle(center + Vector2(-6.0, -13.0), 3.0, Color("#dce8bc"))
	draw_circle(center + Vector2(7.0, -8.0), 3.0, Color("#dce8bc"))


func draw_unit(unit: Dictionary) -> void:
	var cell: Vector2i = unit["pos"]
	var center = cell_to_world(cell) + Vector2(CELL_SIZE * 0.5, CELL_SIZE * 0.5)
	var bob = sin(animation_time * 3.0 + float(cell.x)) * 1.5
	center.y += bob
	var unit_color: Color = unit["color"]
	var is_player = unit["team"] == "player"
	var selected = unit["id"] == selected_id

	if selected:
		draw_arc(center + Vector2(0.0, 2.0), 29.0, 0.0, TAU, 32, GOLD, 3.0, true)
	if unit["has_acted"] and is_player:
		draw_circle(center + Vector2(25.0, -25.0), 7.0, Color("#64788a"))

	# Stem/body.
	draw_rect(Rect2(center + Vector2(-13.0, 3.0), Vector2(26.0, 24.0)), Color("#f3e5c0"), true)
	draw_circle(center + Vector2(0.0, 26.0), 13.0, Color("#f3e5c0"))
	# Cap, face and a small expressive accessory.
	draw_circle(center + Vector2(0.0, -3.0), 25.0, Color("#251c32"))
	draw_circle(center + Vector2(0.0, -7.0), 22.0, unit_color)
	draw_circle(center + Vector2(-8.0, -11.0), 4.0, Color(1.0, 1.0, 1.0, 0.7))
	draw_circle(center + Vector2(8.0, -11.0), 4.0, Color(1.0, 1.0, 1.0, 0.7))
	draw_circle(center + Vector2(-7.0, -4.0), 3.0, Color("#251c32"))
	draw_circle(center + Vector2(7.0, -4.0), 3.0, Color("#251c32"))
	draw_arc(center + Vector2(0.0, 1.0), 7.0, 0.15, PI - 0.15, 12, Color("#251c32"), 2.0, true)
	if is_player:
		draw_line(center + Vector2(-17.0, 18.0), center + Vector2(-29.0, 8.0), unit_color, 4.0, true)
		draw_line(center + Vector2(17.0, 18.0), center + Vector2(29.0, 8.0), unit_color, 4.0, true)
	else:
		draw_line(center + Vector2(-18.0, 18.0), center + Vector2(-27.0, 25.0), unit_color, 4.0, true)
		draw_line(center + Vector2(18.0, 18.0), center + Vector2(27.0, 25.0), unit_color, 4.0, true)

	# Health bar.
	var bar_position = center + Vector2(-27.0, 38.0)
	draw_rect(Rect2(bar_position, Vector2(54.0, 6.0)), Color("#111722"), true)
	var hp_ratio = float(unit["hp"]) / float(unit["max_hp"])
	var hp_color = MINT if is_player else CORAL
	draw_rect(Rect2(bar_position, Vector2(54.0 * hp_ratio, 6.0)), hp_color, true)
	draw_string(ThemeDB.fallback_font, center + Vector2(-31.0, 57.0), str(unit["name"]), HORIZONTAL_ALIGNMENT_CENTER, 62.0, 12, TEXT)
