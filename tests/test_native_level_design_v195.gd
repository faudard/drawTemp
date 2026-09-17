extends SceneTree

const MapScript = preload("res://scripts/maps/spore_map_2d.gd")
const ZoneScript = preload("res://scripts/maps/spore_map_zone_2d.gd")


func _init() -> void:
	var failures: PackedStringArray = PackedStringArray()
	var map: SporeMap2D = MapScript.new() as SporeMap2D
	map.grid_width = 6
	map.grid_height = 6
	map.cell_size = 64.0
	map._ensure_native_layers()
	map.sync_legacy_to_native_layers(true)

	var zone: SporeMapZone2D = ZoneScript.new() as SporeMapZone2D
	zone.zone_id = "test_zone"
	zone.display_name = "Test Zone"
	zone.position = map.cell_to_local(Vector2i(2, 2))
	zone.polygon = PackedVector2Array([
		Vector2(-64.0, -64.0),
		Vector2(64.0, -64.0),
		Vector2(64.0, 64.0),
		Vector2(-64.0, 64.0),
	])
	map.add_child(zone)

	var occupied: Array[Vector2i] = zone.occupied_cells(map)
	if occupied.is_empty():
		failures.append("La zone polygonale ne couvre aucune case.")
	var environment: Dictionary = map.to_environment()
	var raw_zones: Variant = environment.get("zones", [])
	if not (raw_zones is Array) or (raw_zones as Array).is_empty():
		failures.append("La map n'exporte pas ses zones vers le runtime.")
	var issues: Array[Dictionary] = map.validation_issues()
	for issue: Dictionary in issues:
		if String(issue.get("severity", "")) == "error":
			failures.append("Validation map: %s" % String(issue.get("message", "erreur")))

	map.free()
	if failures.is_empty():
		print("[V1.9.5] Native level design smoke test OK")
		quit(0)
	else:
		for failure: String in failures:
			push_error(failure)
		quit(1)
