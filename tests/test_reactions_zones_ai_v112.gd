extends SceneTree

const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const BoardScript = preload("res://scripts/prototypes/spore_battle_board_3d.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	_test_reaction_data()
	_test_persistent_zone_skill()
	_test_board_contract()
	if failures.is_empty():
		print("[V1.12.0] Reactions / AI / persistent zones smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _test_reaction_data() -> void:
	var momo: Resource = UnitCatalog.definition("momo")
	var luma: Resource = UnitCatalog.definition("luma")
	var baveux: Resource = UnitCatalog.definition("baveux")
	var comptable: Resource = UnitCatalog.definition("comptable")
	_expect(momo != null and String(momo.get("reaction_type")) == "intercept", "Momo doit démontrer l'interception.")
	_expect(luma != null and String(luma.get("reaction_type")) == "counter", "Luma doit démontrer la contre-attaque.")
	_expect(luma != null and int(luma.get("reaction_range")) == 3, "La contre de Luma doit être à portée 3.")
	_expect(baveux != null and String(baveux.get("reaction_type")) == "opportunity", "Baveux doit démontrer l'opportunité.")
	_expect(baveux != null and String(baveux.get("secondary_skill")) == "spore_field", "Baveux doit avoir Flaque corrosive.")
	_expect(comptable != null and String(comptable.get("reaction_type")) == "counter", "Le Comptable doit pouvoir contre-attaquer.")


func _test_persistent_zone_skill() -> void:
	var skill: Resource = SkillCatalog.definition("spore_field")
	_expect(skill != null, "Le skill spore_field doit charger.")
	if skill == null:
		return
	_expect(String(skill.get("target_mode")) == "ground", "Flaque corrosive doit cibler le sol.")
	var effects_value: Variant = skill.get("effects")
	_expect(effects_value is Array and not (effects_value as Array).is_empty(), "Flaque corrosive doit avoir un bloc d'effet.")
	if effects_value is Array and not (effects_value as Array).is_empty():
		var effect_value: Variant = (effects_value as Array)[0]
		_expect(effect_value is Resource, "Le bloc de zone doit être une Resource.")
		if effect_value is Resource:
			var effect: Resource = effect_value as Resource
			_expect(String(effect.get("effect_type")) == "zone", "Le bloc doit être de type zone.")
			_expect(String(effect.get("zone_tick_type")) == "damage", "La zone de démo doit infliger des dégâts.")
			_expect(int(effect.get("zone_duration_rounds")) == 3, "La zone de démo doit durer 3 rounds.")
			_expect(String(effect.get("area_shape")) == "circle" and int(effect.get("radius")) == 1, "La zone doit être un cercle de rayon 1.")


func _test_board_contract() -> void:
	var board: Node = BoardScript.new()
	_expect(board.has_method("_apply_damage_with_reactions"), "Le board doit centraliser les dégâts/réactions.")
	_expect(board.has_method("_check_opportunity_reactions"), "Le board doit gérer les opportunités pendant le mouvement.")
	_expect(board.has_method("_best_ai_skill_action"), "Le board doit scorer les skills IA.")
	_expect(board.has_method("_create_persistent_zone"), "Le board doit créer des zones persistantes.")
	board.free()
