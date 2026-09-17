extends SceneTree

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	_check_actor_presentation()
	_check_board_presentation()
	if failures.is_empty():
		print("[V1.14.0] Tactical presentation smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _read(path: String) -> String:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	var text: String = file.get_as_text()
	file.close()
	return text


func _check_actor_presentation() -> void:
	var source: String = _read("res://scripts/maps/spore_unit_actor_3d.gd")
	_expect(not source.is_empty(), "Le script SporeUnitActor3D doit être lisible.")
	_expect(source.contains("_build_vitals_texture"), "Les unités doivent générer leurs barres HP/Focus.")
	_expect(source.contains("Vitals"), "Le billboard de vitaux doit exister.")
	_expect(source.contains("portrait_texture"), "La fiche unité doit pouvoir récupérer un portrait runtime.")


func _check_board_presentation() -> void:
	var source: String = _read("res://scripts/prototypes/spore_battle_board_3d.gd")
	_expect(not source.is_empty(), "Le script SporeBattleBoard3D doit être lisible.")
	_expect(source.contains("InitiativeTimeline"), "La timeline d'initiative doit être créée.")
	_expect(source.contains("UnitCard"), "La fiche d'unité doit être créée.")
	_expect(source.contains("_refresh_timeline_ui"), "La timeline doit être rafraîchie depuis le runtime.")
	_expect(source.contains("_refresh_unit_card_ui"), "La fiche unité doit être rafraîchie depuis le runtime.")
	_expect(source.contains("_update_camera_smoothing"), "La caméra doit utiliser une interpolation fluide.")
	_expect(source.contains("camera_follow_active"), "Le suivi de l'unité active doit être configurable.")
	_expect(source.contains("KEY_C"), "Le recentrage caméra doit avoir un raccourci clavier.")
