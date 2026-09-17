extends SceneTree

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	_check_board_presentation()
	_check_actor_animation()
	if failures.is_empty():
		print("[V1.15.0] Action wheel / camera impact smoke test OK")
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
	var content: String = file.get_as_text()
	file.close()
	return content


func _check_board_presentation() -> void:
	var source: String = _read("res://scripts/prototypes/spore_battle_board_3d.gd")
	_expect(source.contains("ActionWheel"), "Le menu contextuel d'action doit exister.")
	_expect(source.contains("_update_action_wheel"), "Le menu contextuel doit suivre l'unité active.")
	_expect(source.contains("_begin_action_camera"), "La caméra doit pouvoir cadrer une action.")
	_expect(source.contains("_camera_impact"), "Un impact caméra doit être disponible.")
	_expect(source.contains("impact_shake_strength"), "Le shake d'impact doit être configurable.")
	_expect(source.contains("_update_cursor_animation"), "Le curseur tactique doit être animé.")
	_expect(source.contains("play_cast"), "Les skills 3D doivent utiliser une animation de cast.")


func _check_actor_animation() -> void:
	var source: String = _read("res://scripts/maps/spore_unit_actor_3d.gd")
	_expect(source.contains("func _process(delta: float)"), "Les acteurs doivent avoir une animation idle runtime.")
	_expect(source.contains("func play_cast"), "Les acteurs doivent exposer une animation de cast.")
	_expect(source.contains("_presentation_locked"), "Idle et animations d'action doivent être synchronisés.")
	_expect(source.contains("selected_pulse"), "La sélection doit pulser visuellement.")
