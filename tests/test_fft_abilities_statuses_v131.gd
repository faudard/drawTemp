extends SceneTree

const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")
const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")

func _init() -> void:
	# Frozen CT must wait for a clock event/status expiry instead of behaving as Speed 1.
	assert(CombatMechanics.ticks_until_ready(0, 0) == 999999)
	assert(CombatMechanics.ticks_until_ready(120, 0) == 999999)
	assert(CombatMechanics.movement_bonus("move_plus_1") == 1)
	assert(CombatMechanics.movement_bonus("move_plus_2") == 2)
	assert(CombatMechanics.teleport_success_chance(4, 4) == 100)
	assert(CombatMechanics.teleport_success_chance(7, 4) == 70)
	assert(CombatMechanics.teleport_success_chance(14, 4) == 0)
	assert(CombatMechanics.short_charge_ticks(5, "short_charge") == 3)
	assert(CombatMechanics.support_attack_multiplier(6, "attack_up", false) == 8)
	assert(CombatMechanics.support_attack_multiplier(6, "magic_attack_up", true) == 8)
	assert(CombatMechanics.defensive_ability_damage(12, "physical", true, false) == 8)
	assert(CombatMechanics.defensive_ability_damage(12, "magic", false, true) == 8)
	assert(CombatMechanics.blade_grasp_hit_chance(100, 70, true) == 30)
	assert(CombatMechanics.fft_status_success_chance(4, 180, 60, 60) == 66)

	var unit := {"statuses": {}, "max_hp": 16}
	StatusCatalog.apply(unit, "sleep")
	assert(StatusCatalog.freezes_ct(unit))
	assert(StatusCatalog.prevents_movement(unit))
	assert(StatusCatalog.prevents_action(unit))
	assert(StatusCatalog.prevents_reaction(unit))
	assert(StatusCatalog.prevents_evasion(unit))
	assert(StatusCatalog.next_clock_expiry_ticks(unit) == 60)
	StatusCatalog.tick_clock(unit, 59)
	assert(StatusCatalog.has(unit, "sleep"))
	StatusCatalog.tick_clock(unit, 1)
	assert(not StatusCatalog.has(unit, "sleep"))

	StatusCatalog.apply(unit, "dont_act")
	assert(StatusCatalog.treat_as_acted_for_ct(unit))
	assert(StatusCatalog.prevents_action(unit))
	StatusCatalog.remove(unit, "dont_act")
	StatusCatalog.apply(unit, "dont_move")
	assert(StatusCatalog.treat_as_moved_for_ct(unit))

	assert(SkillCatalog.silence_affected("flare"))
	assert(SkillCatalog.fft_status_modifier("corrode") == 160)
	print("V1.31 FFT abilities/statuses smoke test: OK")
	quit(0)
