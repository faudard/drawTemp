extends SceneTree

const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")
const EquipmentCatalog = preload("res://scripts/catalogs/equipment_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const UnitActorScript = preload("res://scripts/maps/spore_unit_actor_3d.gd")
const BoardScript = preload("res://scripts/prototypes/spore_battle_board_3d.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	_test_weapon_ranges()
	_test_physical_magic_stats()
	_test_equipment_profiles()
	_test_actor_contract()
	if failures.is_empty():
		print("[V1.22.0] Weapon / defense mechanics smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _test_weapon_ranges() -> void:
	_expect(CombatMechanics.range_allowed(2, 2, 4), "Une arme 2-4 doit toucher à distance 2.")
	_expect(not CombatMechanics.range_allowed(1, 2, 4), "Une arme 2-4 doit avoir un angle mort au contact.")
	_expect(CombatMechanics.range_allowed(2, 1, 2), "Une lance 1-2 doit menacer à deux cases.")
	var luma: Resource = UnitCatalog.definition("luma")
	_expect(luma != null and String(luma.get("weapon_family")) == "ranged", "Luma doit utiliser un profil d'arme à distance.")
	_expect(luma != null and int(luma.get("attack_min_range")) == 2, "Luma doit avoir une portée minimale de 2.")
	var ziggy: Resource = UnitCatalog.definition("ziggy")
	_expect(ziggy != null and String(ziggy.get("basic_attack_damage_type")) == "spore", "Ziggy doit avoir une attaque de base sporale.")


func _test_physical_magic_stats() -> void:
	_expect(CombatMechanics.damage_after_defense(7, 2, 1) == 5, "7 dégâts contre 2 DEF doivent produire 5 dégâts.")
	_expect(CombatMechanics.damage_after_defense(1, 9, 1) == 1, "Une attaque positive doit conserver le minimum de 1 dégât.")
	var momo: Resource = UnitCatalog.definition("momo")
	var luma: Resource = UnitCatalog.definition("luma")
	_expect(momo != null and int(momo.get("physical_defense")) == 1, "Momo doit exposer DEF.P 1.")
	_expect(luma != null and int(luma.get("magic_power")) == 3, "Luma doit exposer PUI.M 3.")


func _test_equipment_profiles() -> void:
	var ranged: Dictionary = {
		"hp": 10, "max_hp": 10, "attack": 2, "physical_power": 2, "magic_power": 1,
		"physical_defense": 0, "magic_defense": 0, "move": 4, "range": 1,
		"attack_min_range": 1, "attack_max_range": 1, "threat_min_range": 1, "threat_max_range": 1,
		"initiative": 5, "accuracy": 0, "evasion": 0, "max_focus": 2, "focus": 2,
		"resistances": {}, "shield_block_chance": 0, "shield_block_reduction": 0
	}
	EquipmentCatalog.apply_to_unit(ranged, "echo_lens")
	_expect(String(ranged.get("weapon_family")) == "ranged", "Lentille écho doit équiper un profil ranged.")
	_expect(int(ranged.get("attack_min_range")) == 2 and int(ranged.get("attack_max_range")) == 4, "Lentille écho doit utiliser une portée 2-4.")
	_expect(not bool(ranged.get("can_opportunity_attack", true)), "Lentille écho ne doit pas déclencher d'opportunité.")

	var tank: Dictionary = ranged.duplicate(true)
	EquipmentCatalog.apply_to_unit(tank, "mycelium_plate")
	_expect(int(tank.get("physical_defense", 0)) >= 1, "Plaque mycélienne doit ajouter de la DEF.P.")
	_expect(int(tank.get("magic_defense", 0)) >= 1, "Plaque mycélienne doit ajouter de la DEF.M.")
	_expect(int(tank.get("shield_block_chance", 0)) == 25, "Plaque mycélienne doit avoir 25% de blocage.")
	_expect(int(tank.get("shield_block_reduction", 0)) == 2, "Plaque mycélienne doit bloquer 2 dégâts.")

	var spear: Dictionary = ranged.duplicate(true)
	EquipmentCatalog.apply_to_unit(spear, "crown_core")
	_expect(String(spear.get("weapon_family")) == "spear", "Cœur de couronne doit utiliser le profil lance.")
	_expect(int(spear.get("threat_max_range")) == 2, "La lance doit contrôler jusqu'à deux cases.")


func _test_actor_contract() -> void:
	var actor: SporeUnitActor3D = UnitActorScript.new() as SporeUnitActor3D
	get_root().add_child(actor)
	actor.attack_power = 4
	actor.magic_power = 6
	actor.physical_defense = 2
	actor.magic_defense = 3
	actor.basic_attack_damage_type = "spore"
	_expect(actor.effective_basic_attack_power() == 6, "Une attaque sporale 3D doit employer PUI.M.")
	_expect(actor.effective_defense_for_damage_type("physical") == 2, "DEF.P 3D incorrecte.")
	_expect(actor.effective_defense_for_damage_type("spore") == 3, "DEF.M 3D incorrecte.")
	actor.free()
	var board: Node = BoardScript.new()
	_expect(board.has_method("_is_in_attack_range"), "Le runtime 3D doit exposer le contrôle de portée min/max.")
	_expect(board.has_method("_attack_damage_details"), "Le runtime 3D doit centraliser PUI/DEF dans le forecast.")
	board.free()
