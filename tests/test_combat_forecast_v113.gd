extends SceneTree

func _init() -> void:
	var failures: PackedStringArray = PackedStringArray()
	var board_path: String = "res://scripts/prototypes/spore_battle_board_3d.gd"
	if not ResourceLoader.exists(board_path):
		failures.append("Le contrôleur battle 3D manque.")
	else:
		var file: FileAccess = FileAccess.open(board_path, FileAccess.READ)
		var source: String = file.get_as_text() if file != null else ""
		if file != null:
			file.close()
		for token: String in [
			"pending_action",
			"_stage_attack_preview",
			"_stage_skill_preview",
			"_confirm_pending_action",
			"_cancel_pending_action",
			"_attack_preview_text",
			"_skill_preview_text",
			"CONFIRMER [ENTRÉE]",
			"ANNULER [ÉCHAP]",
		]:
			if source.find(token) < 0:
				failures.append("Prévision V1.13 incomplète : %s" % token)
	if failures.is_empty():
		print("[V1.13.0] Combat forecast smoke test OK")
		quit(0)
	else:
		for failure: String in failures:
			push_error(failure)
		quit(1)
