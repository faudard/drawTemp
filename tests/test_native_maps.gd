extends SceneTree

const MissionCatalog = preload("res://scripts/catalogs/mission_catalog.gd")

var failures: Array[String] = []


func _init() -> void:
	test_native_map_scenes()
	if failures.is_empty():
		print("Sporebound native 2D/3D map smoke test: OK")
		quit(0)
		return
	for message: String in failures:
		push_error(message)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_native_map_scenes() -> void:
	var paths: Array[String] = MissionCatalog.mission_paths()
	expect(paths.size() >= 3, "starter missions exist")
	for mission_index: int in range(mini(3, paths.size())):
		var mission: Resource = MissionCatalog.definition(mission_index)
		expect(mission != null, "mission %d resource loads" % mission_index)
		if mission == null:
			continue
		var map_path: String = String(mission.get("map_scene_path"))
		expect(not map_path.is_empty(), "mission %d has native map_scene_path" % mission_index)
		expect(ResourceLoader.exists(map_path), "mission %d native map scene exists" % mission_index)
		if map_path.is_empty() or not ResourceLoader.exists(map_path):
			continue
		var packed: PackedScene = load(map_path) as PackedScene
		expect(packed != null, "mission %d map is a PackedScene" % mission_index)
		if packed == null:
			continue
		var map_root: Node = packed.instantiate()
		expect(map_root != null, "mission %d map instantiates" % mission_index)
		if map_root == null:
			continue
		expect(map_root.has_method("to_environment"), "mission %d map exposes environment contract" % mission_index)
		expect(map_root.has_method("hero_start_cells"), "mission %d map exposes hero spawns" % mission_index)
		expect(map_root.has_method("enemy_spawn_data"), "mission %d map exposes enemy spawns" % mission_index)
		if map_root is SporeMap2D:
			for layer_name: String in ["Ground", "Height", "Terrain", "Objectives"]:
				var layer: Node = map_root.get_node_or_null(NodePath(layer_name))
				expect(layer is TileMapLayer, "mission %d exposes native TileMapLayer %s" % [mission_index, layer_name])
		elif map_root is SporeMap3D:
			var tiles: Node = map_root.get_node_or_null("Tiles")
			expect(tiles != null, "mission %d exposes 3D Tiles container" % mission_index)
			expect(map_root.has_method("elevation_at"), "mission %d exposes 3D elevation lookup" % mission_index)
		else:
			expect(false, "mission %d map root is a supported native map" % mission_index)
		if map_root.has_method("hero_start_cells"):
			var hero_cells: Array = map_root.call("hero_start_cells")
			expect(hero_cells.size() >= 3, "mission %d has at least three hero spawns" % mission_index)
		if map_root.has_method("enemy_spawn_data"):
			var enemy_data: Array = map_root.call("enemy_spawn_data")
			expect(not enemy_data.is_empty(), "mission %d has enemy spawns" % mission_index)
		map_root.free()
