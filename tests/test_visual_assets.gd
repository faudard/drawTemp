extends SceneTree

const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")
const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")
const VfxCatalog = preload("res://scripts/catalogs/vfx_catalog.gd")

var failures: Array[String] = []


func _init() -> void:
	test_unit_visuals()
	test_skill_vfx()
	test_status_vfx()
	test_vfx_library()
	if failures.is_empty():
		print("Sporebound V1.7 visual assets smoke test: OK")
		quit(0)
		return
	for failure in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_unit_visuals() -> void:
	var unit_ids := UnitCatalog.all_unit_ids()
	expect(unit_ids.size() >= 10, "starter unit library")
	for unit_id in unit_ids:
		var unit_def := UnitCatalog.definition(String(unit_id))
		if unit_def == null:
			failures.append("Missing unit definition: %s" % unit_id)
			continue
		var visual_id := String(unit_def.visual_id) if not String(unit_def.visual_id).is_empty() else String(unit_id)
		var visual := VisualCatalog.definition(visual_id)
		if visual == null:
			failures.append("Unit %s references missing visual %s" % [unit_id, visual_id])
			continue
		expect(String(visual.unit_id) == String(unit_id), "visual %s unit binding" % visual_id)
		for state in ["idle", "move", "attack", "hit", "ko"]:
			var clip: Dictionary = visual.clip_data(state)
			expect(int(clip.get("count", 0)) >= 1, "%s clip count for %s" % [state, visual_id])
			expect(float(clip.get("fps", 0.0)) > 0.0, "%s clip fps for %s" % [state, visual_id])
		var basic_vfx := String(visual.basic_attack_vfx_id)
		expect(not basic_vfx.is_empty() and VfxCatalog.definition(basic_vfx) != null, "basic attack VFX for %s" % visual_id)


func test_skill_vfx() -> void:
	for skill_id in _resource_ids("res://data/skills/"):
		var vfx_id := SkillCatalog.vfx_id(String(skill_id))
		expect(not vfx_id.is_empty(), "skill %s has a VFX id" % skill_id)
		expect(VfxCatalog.definition(vfx_id) != null, "skill %s VFX exists" % skill_id)


func test_status_vfx() -> void:
	for status_id in StatusCatalog.all_status_ids():
		var vfx_id := StatusCatalog.vfx_id(String(status_id))
		if vfx_id.is_empty():
			continue
		expect(VfxCatalog.definition(vfx_id) != null, "status %s VFX exists" % status_id)


func test_vfx_library() -> void:
	var ids := VfxCatalog.all_vfx_ids()
	expect(ids.size() >= 10, "starter VFX library")
	for vfx_id in ids:
		var vfx := VfxCatalog.definition(String(vfx_id))
		if vfx == null:
			failures.append("Cannot load VFX %s" % vfx_id)
			continue
		expect(float(vfx.duration) > 0.0, "VFX %s duration" % vfx_id)
		expect(float(vfx.radius) > 0.0, "VFX %s radius" % vfx_id)


func _resource_ids(directory: String) -> PackedStringArray:
	var result := PackedStringArray()
	var dir := DirAccess.open(directory)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(file_name.get_basename())
	result.sort()
	return result
