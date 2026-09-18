extends SceneTree

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var expected_scene: String = "res://scenes/mission_1_battle_3d.tscn"
	expect(String(ProjectSettings.get_setting("application/run/main_scene", "")) == expected_scene, "F5 doit lancer la mission 1 3D.")
	expect(ResourceLoader.exists(expected_scene), "La scène de mission 1 3D existe.")
	if not ResourceLoader.exists(expected_scene):
		_finish()
		return

	var packed: PackedScene = load(expected_scene) as PackedScene
	expect(packed != null, "La scène de mission 1 3D charge.")
	if packed == null:
		_finish()
		return

	var board: SporeBattleBoard3D = packed.instantiate() as SporeBattleBoard3D
	expect(board != null, "Le runtime SporeBattleBoard3D s'instancie.")
	if board == null:
		_finish()
		return
	root.add_child(board)

	expect(board.map_root != null, "La map 3D est chargée.")
	expect(board.mission_objective == "crown", "La mission 1 conserve l'objectif Couronne.")
	expect(board.crown_cell == Vector2i(9, 0), "La Couronne démarre en 9,0.")
	expect(board.extraction_cells.size() == 3, "Les trois cases d'extraction sont actives.")
	expect(board.bonus_target_total == 2, "Les deux vinyles optionnels sont actifs.")
	expect(board._closed_mission_door_at(Vector2i(5, 6)), "La porte du jardin démarre fermée.")

	board._toggle_mission_switch("garden_switch")
	expect(not board._closed_mission_door_at(Vector2i(5, 6)), "L'interrupteur ouvre réellement la porte.")

	if not board.player_actors.is_empty():
		var carrier: SporeUnitActor3D = board.player_actors[0]
		carrier.place_on_map(board.map_root, board.crown_cell)
		board._handle_mission_cell_entry(carrier)
		expect(board.crown_carrier_id == carrier.unit_id, "Un héros peut récupérer la Couronne en 3D.")
		carrier.place_on_map(board.map_root, board.extraction_cells[0])
		board._handle_mission_cell_entry(carrier)
		board._check_battle_end()
		expect(board.battle_finished and board.mission_victory, "Ramener la Couronne dans l'extraction termine la mission en victoire.")
	else:
		expect(false, "Au moins un héros doit être instancié.")

	board.queue_free()
	await process_frame
	_finish()


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _finish() -> void:
	if failures.is_empty():
		print("[MISSION 1 3D] Playable objective smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)
