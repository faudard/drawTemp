extends SceneTree

const VfxCatalog = preload("res://scripts/catalogs/vfx_catalog.gd")
const ActionVfxScript = preload("res://scripts/prototypes/spore_action_vfx_3d.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	_test_vfx_runtime()
	_test_attack_vfx_bindings()
	_test_battle_board_hooks()
	if failures.is_empty():
		print("[V1.16] Action VFX 3D smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _test_vfx_runtime() -> void:
	var expected: Dictionary = {
		"default_hit": "burst",
		"prism_projectile": "projectile",
		"spore_projectile": "projectile",
		"heal_bloom": "ring",
		"spore_burst": "cross",
		"guard_aura": "aura",
		"corrode_wave": "slash",
	}
	for vfx_id: String in expected.keys():
		var definition: Resource = VfxCatalog.definition(vfx_id)
		_expect(definition != null, "VFX manquant: %s" % vfx_id)
		if definition != null:
			_expect(String(definition.get("kind")) == String(expected[vfx_id]), "Type VFX inattendu pour %s" % vfx_id)
	var runtime: SporeActionVfx3D = ActionVfxScript.new() as SporeActionVfx3D
	_expect(runtime != null, "SporeActionVfx3D ne s'instancie pas")
	if runtime != null:
		get_root().add_child(runtime)
		var projectile: Resource = VfxCatalog.definition("prism_projectile")
		runtime.configure(projectile, Vector3.ZERO, Vector3(3.0, 0.5, 2.0))
		_expect(runtime.kind == "projectile", "Le runtime ne reprend pas le kind du VFX")
		_expect(runtime.duration > 0.0, "La durée VFX doit être positive")
		runtime.free()


func _test_attack_vfx_bindings() -> void:
	for unit_id: String in ["momo", "luma", "comptable", "dj_morille"]:
		var unit: Resource = UnitCatalog.definition(unit_id)
		_expect(unit != null, "Unité manquante: %s" % unit_id)
		if unit == null:
			continue
		var visual_id: String = String(unit.get("visual_id"))
		var visual: Resource = VisualCatalog.definition(visual_id)
		_expect(visual != null, "Visual manquant pour %s" % unit_id)
		if visual != null:
			var attack_vfx: String = String(visual.get("basic_attack_vfx_id"))
			_expect(not attack_vfx.is_empty(), "basic_attack_vfx_id vide pour %s" % unit_id)
			_expect(VfxCatalog.definition(attack_vfx) != null, "VFX d'attaque inexistant pour %s: %s" % [unit_id, attack_vfx])


func _test_battle_board_hooks() -> void:
	var script_text: String = FileAccess.get_file_as_string("res://scripts/prototypes/spore_battle_board_3d.gd")
	_expect(script_text.contains("_play_action_vfx_to_impact"), "Le battle board ne synchronise pas le VFX avec l'impact")
	_expect(script_text.contains("projectile_camera_follow"), "Le suivi caméra projectile est absent")
	_expect(script_text.contains("basic_attack_vfx_id"), "Les attaques de base n'utilisent pas leur VFX data-driven")
	_expect(script_text.contains('String(skill.get("vfx_id"))'), "Les skills n'utilisent pas SkillDefinition.vfx_id")
