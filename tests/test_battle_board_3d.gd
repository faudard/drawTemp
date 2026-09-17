extends SceneTree

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var path: String = "res://scenes/mission_1_battle_3d.tscn"
	expect(ResourceLoader.exists(path), "La scène de battle 3D existe.")
	if not ResourceLoader.exists(path):
		_finish()
		return
	var packed: PackedScene = load(path) as PackedScene
	expect(packed != null, "La scène de battle 3D charge en PackedScene.")
	if packed == null:
		_finish()
		return
	var battle: Node = packed.instantiate()
	root.add_child(battle)
	await process_frame
	await process_frame

	var map_node: Node = battle.get_node_or_null("MapRoot/Mission1Map3D")
	expect(map_node is SporeMap3D, "Le prototype instancie la vraie map 3D de mission 1.")
	var actors: Node = battle.get_node_or_null("Actors")
	expect(actors != null, "Le conteneur Actors existe.")
	if actors != null:
		var tactical_actor_count: int = 0
		for child: Node in actors.get_children():
			if child is SporeUnitActor3D:
				tactical_actor_count += 1
		expect(tactical_actor_count >= 7, "Au moins 3 héros et 4 ennemis sont instanciés.")
	var camera: Node = battle.get_node_or_null("CameraRig/Camera3D")
	expect(camera is Camera3D, "La caméra isométrique existe.")
	var board: SporeBattleBoard3D = battle as SporeBattleBoard3D
	if board != null:
		expect(board.turn_order.size() >= 7, "La timeline d'initiative contient les unités.")
		expect(board.active_actor != null, "Une première activation est démarrée.")
		expect(board.map_root != null, "La map runtime est connectée au contrôleur 3D.")

	battle.queue_free()
	await process_frame
	_finish()


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _finish() -> void:
	if failures.is_empty():
		print("[V1.9.8] 3D tactical combat smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)
