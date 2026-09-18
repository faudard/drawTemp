extends SceneTree

const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")

func _init() -> void:
	assert(CombatMechanics.BASIC_ATTACK_ACCURACY == 100)
	assert(CombatMechanics.fft_physical_hit_chance(100, 0, 20, 0, 0, 0, "front", false) == 80)
	assert(CombatMechanics.fft_physical_hit_chance(100, 0, 20, 0, 0, 0, "side", false) == 100)
	assert(CombatMechanics.fft_physical_hit_chance(100, 0, 20, 0, 0, 0, "back", false) == 100)
	assert(CombatMechanics.fft_physical_hit_chance(100, 0, 40, 40, 40, 40, "front", true) == 100)
	assert(CombatMechanics.fft_magic_hit_chance(100, 0, 20, 25, false) == 60)
	assert(CombatMechanics.fft_magic_hit_chance(100, 0, 20, 25, true) == 100)
	assert(CombatMechanics.apply_charging_physical_vulnerability(10, true) == 15)
	assert(CombatMechanics.apply_charging_physical_vulnerability(10, false) == 10)
	var unit := {"focus": 1, "max_focus": 3, "focus_regen_bonus": 0, "cooldowns": {"x": 2}, "has_acted": false}
	assert(not SkillCatalog.interrupt_on_damage("mist"))
	unit["focus"] = 0
	assert(SkillCatalog.can_use(unit, "mist")) # slow action: MP is resolved at SR
	unit["focus"] = 1
	SkillCatalog.tick_round(unit)
	assert(int(unit["focus"]) == 1)
	assert((unit["cooldowns"] as Dictionary).is_empty())
	unit["focus_regen_bonus"] = 1
	SkillCatalog.tick_round(unit)
	assert(int(unit["focus"]) == 2)
	print("V1.29 FFT magic/charge mechanics: OK")
	quit(0)
