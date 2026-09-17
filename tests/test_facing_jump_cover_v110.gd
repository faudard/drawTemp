extends SceneTree

const BoardScript = preload("res://scripts/prototypes/spore_battle_board_3d.gd")
const ActorScript = preload("res://scripts/maps/spore_unit_actor_3d.gd")
const MapScript = preload("res://scripts/maps/spore_map_3d.gd")
const TileScript = preload("res://scripts/maps/spore_tactical_tile_3d.gd")

var failures: Array[String] = []


func _init() -> void:
	test_facing_arcs()
	test_directional_cover()
	test_jump_rules()
	if failures.is_empty():
		print("[V1.10.0] Facing / jump / directional cover smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_facing_arcs() -> void:
	var board: SporeBattleBoard3D = BoardScript.new() as SporeBattleBoard3D
	var target: SporeUnitActor3D = ActorScript.new() as SporeUnitActor3D
	target.cell = Vector2i(2, 2)
	target.set_facing(Vector2i.UP)
	expect(board._relative_attack_arc(Vector2i(2, 1), target) == "front", "une attaque venant du nord doit être de face")
	expect(board._relative_attack_arc(Vector2i(2, 3), target) == "back", "une attaque venant du sud doit être de dos")
	expect(board._relative_attack_arc(Vector2i(3, 2), target) == "side", "une attaque venant de l'est doit être de flanc")
	target.rotate_facing_quarter(1)
	expect(target.facing == Vector2i.RIGHT, "la rotation d'un quart doit orienter vers l'est")
	target.free()
	board.free()


func test_directional_cover() -> void:
	var map: SporeMap3D = MapScript.new() as SporeMap3D
	map.grid_width = 4
	map.grid_height = 4
	var cover: SporeTacticalTile3D = TileScript.new() as SporeTacticalTile3D
	cover.cell = Vector2i(1, 1)
	cover.terrain_type = "cover"
	cover.cover_facing = "east"
	map.add_child(cover)
	var board: SporeBattleBoard3D = BoardScript.new() as SporeBattleBoard3D
	board.map_root = map
	expect(board._cover_protects_from(Vector2i(3, 1), Vector2i(1, 1)), "un couvert orienté est doit protéger d'un tir venant de l'est")
	expect(not board._cover_protects_from(Vector2i(0, 1), Vector2i(1, 1)), "le même couvert ne doit pas protéger d'un tir venant de l'ouest")
	var environment: Dictionary = map.to_environment()
	var directions_value: Variant = environment.get("cover_directions", {})
	expect(directions_value is Dictionary, "la map doit exporter les orientations de couvert")
	if directions_value is Dictionary:
		var directions: Dictionary = directions_value as Dictionary
		expect(directions.get(Vector2i(1, 1), Vector2i.ZERO) == Vector2i.RIGHT, "l'orientation de couvert doit être exportée")
	board.free()
	map.free()


func test_jump_rules() -> void:
	var map: SporeMap3D = MapScript.new() as SporeMap3D
	map.grid_width = 2
	map.grid_height = 2
	var low: SporeTacticalTile3D = TileScript.new() as SporeTacticalTile3D
	low.cell = Vector2i(0, 0)
	low.elevation = 0
	map.add_child(low)
	var high: SporeTacticalTile3D = TileScript.new() as SporeTacticalTile3D
	high.cell = Vector2i(0, 1)
	high.elevation = 2
	map.add_child(high)
	var board: SporeBattleBoard3D = BoardScript.new() as SporeBattleBoard3D
	board.map_root = map
	board.max_jump_up = 1
	board.max_jump_down = 2
	expect(not board._can_step_between(Vector2i(0, 0), Vector2i(0, 1)), "un saut de +2 doit être refusé avec jump_up=1")
	expect(board._can_step_between(Vector2i(0, 1), Vector2i(0, 0)), "une descente de 2 doit être autorisée avec jump_down=2")
	board.max_jump_up = 2
	expect(board._can_step_between(Vector2i(0, 0), Vector2i(0, 1)), "le même saut doit être autorisé avec jump_up=2")
	board.free()
	map.free()
