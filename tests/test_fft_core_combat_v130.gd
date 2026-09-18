extends SceneTree

const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")
const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")

func _init() -> void:
	assert(CombatMechanics.reaction_chance(70) == 70)
	assert(CombatMechanics.zodiac_adjust(8, "good") == 10)
	assert(CombatMechanics.zodiac_adjust(8, "bad") == 6)
	assert(CombatMechanics.zodiac_adjust(8, "best") == 12)
	assert(CombatMechanics.zodiac_adjust(8, "worst") == 4)
	assert(CombatMechanics.zodiac_compatibility("aries", "leo", "male", "male") == "good")
	assert(CombatMechanics.zodiac_compatibility("aries", "cancer", "male", "female") == "bad")
	assert(CombatMechanics.zodiac_compatibility("aries", "libra", "male", "female") == "best")
	assert(CombatMechanics.zodiac_compatibility("aries", "libra", "male", "male") == "worst")
	assert(CombatMechanics.ct_gain_per_tick(8, true, false) == 12)
	assert(CombatMechanics.ct_gain_per_tick(8, false, true) == 4)
	assert(CombatMechanics.fft_weapon_damage(3, 2, 6, 70, 2, "melee") == 6)
	assert(CombatMechanics.fft_weapon_damage(2, 2, 6, 70, 2, "ranged") == 8)
	assert(CombatMechanics.fft_magic_damage(4, 4, 75, 60) == 7)
	var unit := {"statuses": {}, "max_hp": 16}
	StatusCatalog.apply(unit, "slowed")
	assert(StatusCatalog.remaining_clockticks(unit, "slowed") == 24)
	StatusCatalog.tick_clock(unit, 23)
	assert(StatusCatalog.has(unit, "slowed"))
	StatusCatalog.tick_clock(unit, 1)
	assert(not StatusCatalog.has(unit, "slowed"))
	print("V1.30 FFT core combat smoke test: OK")
	quit(0)
