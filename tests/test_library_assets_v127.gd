extends SceneTree

const LibraryCatalog = preload("res://scripts/catalogs/library_asset_catalog.gd")
const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	test_library_inventory()
	test_runtime_bindings()
	test_status_icons()
	test_action_poses()
	if failures.is_empty():
		print("[V1.27] Library assets runtime smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_library_inventory() -> void:
	var character_ids: PackedStringArray = LibraryCatalog.character_ids()
	expect(character_ids.size() >= 39, "39 library character portraits are indexed")
	for asset_id: String in character_ids:
		var path: String = LibraryCatalog.portrait_path(asset_id)
		expect(not path.is_empty(), "portrait path for %s" % asset_id)
		expect(ResourceLoader.exists(path), "portrait resource exists for %s" % asset_id)
		var library_visual_id: String = "lib_" + asset_id
		var visual: Resource = VisualCatalog.definition(library_visual_id)
		expect(visual != null, "library visual exists for %s" % asset_id)
		if visual != null:
			expect(String(visual.get("render_mode")) == "portrait_billboard", "%s uses portrait billboard" % library_visual_id)


func test_runtime_bindings() -> void:
	var expected_units: PackedStringArray = PackedStringArray([
		"momo", "pipo", "luma", "ziggy", "grincheux",
		"baveux", "comptable", "dj_morille", "choriste", "archiviste"
	])
	for unit_id: String in expected_units:
		var binding: Dictionary = LibraryCatalog.unit_binding(unit_id)
		expect(not binding.is_empty(), "library binding for %s" % unit_id)
		var portrait_path: String = LibraryCatalog.portrait_path_for_unit(unit_id)
		expect(ResourceLoader.exists(portrait_path), "bound portrait exists for %s" % unit_id)
		var visual: Resource = VisualCatalog.definition(unit_id)
		expect(visual != null, "unit visual exists for %s" % unit_id)
		if visual != null:
			expect(String(visual.get("render_mode")) == "portrait_billboard", "%s renders library portrait" % unit_id)
			expect(String(visual.get("portrait_path")) == portrait_path, "%s portrait matches binding" % unit_id)


func test_status_icons() -> void:
	for status_id: String in ["sick", "electrified", "burning", "cursed", "controlled", "poisoned", "frozen", "sleep"]:
		var path: String = LibraryCatalog.status_icon_path(status_id)
		expect(not path.is_empty(), "status icon path for %s" % status_id)
		expect(ResourceLoader.exists(path), "status icon exists for %s" % status_id)


func test_action_poses() -> void:
	var catalog: Dictionary = LibraryCatalog.load_catalog()
	var raw_entries: Variant = catalog.get("action_strips", [])
	if not raw_entries is Array:
		failures.append("action strip catalog is an array")
		return
	var entries: Array = raw_entries as Array
	var ready_count: int = 0
	for entry_variant: Variant in entries:
		if not entry_variant is Dictionary:
			continue
		var entry: Dictionary = entry_variant as Dictionary
		var pose_path: String = String(entry.get("runtime_attack_pose_path", ""))
		if pose_path.is_empty():
			continue
		ready_count += 1
		expect(ResourceLoader.exists(pose_path), "runtime action pose exists: %s" % pose_path)
	expect(ready_count >= 12, "12 runtime attack poses are ready")
