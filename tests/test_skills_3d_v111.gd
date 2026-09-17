extends SceneTree

const BoardScript = preload("res://scripts/prototypes/spore_battle_board_3d.gd")
const ActorScript = preload("res://scripts/maps/spore_unit_actor_3d.gd")
const MapScript = preload("res://scripts/maps/spore_map_3d.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")

var failures: Array[String] = []


func _init() -> void:
	test_area_shapes()
	test_focus_and_cooldown()
	test_status_runtime()
	if failures.is_empty():
		print("[V1.11.0] 3D skills / AOE / status smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_area_shapes() -> void:
	var board: SporeBattleBoard3D = BoardScript.new() as SporeBattleBoard3D
	var map: SporeMap3D = MapScript.new() as SporeMap3D
	map.grid_width = 7
	map.grid_height = 7
	board.map_root = map

	var line_skill: Resource = SkillCatalog.definition("prism_lance")
	expect(line_skill != null, "prism_lance doit exister")
	if line_skill != null:
		var effects_value: Variant = line_skill.get("effects")
		if effects_value is Array and not (effects_value as Array).is_empty():
			var effect: Resource = (effects_value as Array)[0] as Resource
			var line_cells: Array[Vector2i] = board._effect_area_cells(effect, Vector2i(3, 1), Vector2i(3, 5))
			expect(line_cells.has(Vector2i(3, 4)), "la ligne doit partir du lanceur")
			expect(line_cells.has(Vector2i(3, 1)), "la ligne doit inclure la case ciblée")
			expect(not line_cells.has(Vector2i(4, 4)), "la ligne ne doit pas déborder latéralement")

	var circle_skill: Resource = SkillCatalog.definition("spore_orbit")
	expect(circle_skill != null, "spore_orbit doit exister")
	if circle_skill != null:
		var effects_value_circle: Variant = circle_skill.get("effects")
		if effects_value_circle is Array and not (effects_value_circle as Array).is_empty():
			var effect_circle: Resource = (effects_value_circle as Array)[0] as Resource
			var circle_cells: Array[Vector2i] = board._effect_area_cells(effect_circle, Vector2i(3, 3), Vector2i(3, 6))
			expect(circle_cells.has(Vector2i(5, 3)), "le cercle r2 doit inclure une case à distance 2")
			expect(not circle_cells.has(Vector2i(5, 5)), "le cercle r2 ne doit pas inclure la diagonale 2/2")

	board.free()
	map.free()


func test_focus_and_cooldown() -> void:
	var actor: SporeUnitActor3D = ActorScript.new() as SporeUnitActor3D
	actor.max_focus = 2
	actor.focus = 2
	actor.primary_skill = "hat"
	expect(actor.can_use_skill("hat"), "un skill doit être utilisable avec assez de Focus")
	actor.spend_skill("hat")
	expect(actor.focus == 1, "hat doit coûter 1 Focus")
	expect(actor.skill_cooldown("hat") == 2, "hat doit poser son cooldown à 2")
	expect(actor.acted_this_activation, "utiliser un skill doit consommer l'action")
	actor.begin_activation()
	expect(actor.focus == 2, "le Focus doit régénérer d'un point à l'activation")
	expect(actor.skill_cooldown("hat") == 1, "le cooldown doit diminuer à l'activation suivante")
	actor.free()


func test_status_runtime() -> void:
	var actor: SporeUnitActor3D = ActorScript.new() as SporeUnitActor3D
	expect(actor.apply_status("slowed"), "Ralenti doit pouvoir être appliqué")
	expect(actor.status_modifier("movement_delta") == -1, "Ralenti doit enlever 1 MVT")
	var expired: PackedStringArray = actor.finish_status_activation()
	expect(expired.has("slowed"), "Ralenti doit expirer après une activation")
	expect(actor.status_modifier("movement_delta") == 0, "le modificateur doit disparaître à expiration")
	expect(actor.apply_status("guarded"), "Garde doit pouvoir être appliquée")
	expect(actor.status_modifier("incoming_damage_delta") == -1, "Garde doit réduire les dégâts reçus")
	actor.remove_statuses_on_damage_taken()
	expect(actor.status_modifier("incoming_damage_delta") == 0, "Garde doit être consommée après un impact")
	actor.free()
