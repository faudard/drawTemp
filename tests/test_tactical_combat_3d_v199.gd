extends SceneTree

const BoardScript = preload("res://scripts/prototypes/spore_battle_board_3d.gd")


func _init() -> void:
	var failures: PackedStringArray = PackedStringArray()
	var board: SporeBattleBoard3D = BoardScript.new() as SporeBattleBoard3D
	if board == null:
		failures.append("SporeBattleBoard3D ne s'instancie pas.")
	else:
		if not board.has_method("_reconstruct_path"):
			failures.append("Le plateau 3D n'expose pas la reconstruction de chemin.")
		if not board.has_method("_move_actor_along_path"):
			failures.append("Le plateau 3D n'expose pas le déplacement pas à pas.")
		if not board.has_method("_has_line_of_sight"):
			failures.append("Le plateau 3D n'expose pas la ligne de vue.")
		if not board.has_method("_grid_line_cells"):
			failures.append("Le plateau 3D n'expose pas le tracé de grille.")
		var diagonal: Array[Vector2i] = board._grid_line_cells(Vector2i(0, 0), Vector2i(3, 3))
		if diagonal.size() != 4 or diagonal[0] != Vector2i(0, 0) or diagonal[3] != Vector2i(3, 3):
			failures.append("Le tracé Bresenham diagonal est incorrect.")
		var horizontal: Array[Vector2i] = board._grid_line_cells(Vector2i(1, 2), Vector2i(4, 2))
		if horizontal.size() != 4 or horizontal[0] != Vector2i(1, 2) or horizontal[3] != Vector2i(4, 2):
			failures.append("Le tracé Bresenham horizontal est incorrect.")
		board.free()
	if failures.is_empty():
		print("[V1.9.9] Tactical combat 3D path/LOS smoke test OK")
		quit(0)
	else:
		for failure: String in failures:
			push_error(failure)
		quit(1)
