extends SceneTree

const VfxCatalog = preload("res://scripts/catalogs/vfx_catalog.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const ActionVfxScript = preload("res://scripts/prototypes/spore_action_vfx_3d.gd")
const UnitActorScript = preload("res://scripts/maps/spore_unit_actor_3d.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	_test_beam_definition()
	_test_moving_target_tracking()
	_test_persistent_status_vfx()
	_test_battle_board_hooks()
	if failures.is_empty():
		print("[V1.17] Advanced combat VFX smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _test_beam_definition() -> void:
	var beam: Resource = VfxCatalog.definition("prism_beam")
	_expect(beam != null, "VFX prism_beam manquant")
	if beam != null:
		_expect(String(beam.get("kind")) == "beam", "prism_beam doit utiliser le kind beam")
	var skill: Resource = SkillCatalog.definition("prism_lance")
	_expect(skill != null, "Skill prism_lance manquant")
	if skill != null:
		_expect(String(skill.get("vfx_id")) == "prism_beam", "Lance prismatique doit utiliser prism_beam")


func _test_moving_target_tracking() -> void:
	var target: Node3D = Node3D.new()
	get_root().add_child(target)
	target.global_position = Vector3(2.0, 0.0, 1.0)
	var runtime: SporeActionVfx3D = ActionVfxScript.new() as SporeActionVfx3D
	get_root().add_child(runtime)
	var projectile: Resource = VfxCatalog.definition("prism_projectile")
	runtime.configure(projectile, Vector3.ZERO, target.global_position, "", target, Vector3(0.0, 0.5, 0.0))
	runtime.start()
	target.global_position = Vector3(4.0, 0.0, 2.0)
	runtime._process(0.01)
	_expect(runtime.target_world.distance_to(Vector3(4.0, 0.5, 2.0)) < 0.001, "Le projectile ne suit pas la nouvelle position de la cible")
	runtime.free()
	target.free()


func _test_persistent_status_vfx() -> void:
	var actor: SporeUnitActor3D = UnitActorScript.new() as SporeUnitActor3D
	get_root().add_child(actor)
	var applied: bool = actor.apply_status("poisoned")
	_expect(applied, "Le statut Poison doit pouvoir être appliqué")
	var holder: Node3D = actor.get_node_or_null("StatusVfx") as Node3D
	_expect(holder != null, "Le conteneur StatusVfx est absent")
	if holder != null:
		_expect(holder.get_child_count() >= 1, "Poison doit créer un VFX persistant")
	actor.remove_status("poisoned")
	_expect(actor.statuses.is_empty(), "Poison doit être retiré de l'acteur")
	actor.free()


func _test_battle_board_hooks() -> void:
	var script_text: String = FileAccess.get_file_as_string("res://scripts/prototypes/spore_battle_board_3d.gd")
	_expect(script_text.contains("_play_skill_area_impacts"), "Les impacts AOE cellule par cellule sont absents")
	_expect(script_text.contains("tracked_skill_target"), "Les skills ne transmettent pas leur cible mobile au VFX")
	_expect(script_text.contains("status_tick_vfx_enabled"), "Les ticks de statut n'utilisent pas leurs VFX")
	var editor_text: String = FileAccess.get_file_as_string("res://addons/sporebound_studio/vfx_editor.gd")
	_expect(editor_text.contains('"beam"'), "Le type beam n'est pas disponible dans l'éditeur VFX")
