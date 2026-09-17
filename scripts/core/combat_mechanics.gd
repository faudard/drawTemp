class_name SporeCombatMechanics
extends RefCounted

## Shared tactical rules used by both battle runtimes.
## Keep this file scene-agnostic so the 2D and 3D controllers cannot drift apart.

const CT_THRESHOLD: int = 100
const CT_AFTER_FULL_TURN: int = 0
const CT_AFTER_SINGLE_ACTION: int = 20
const CT_AFTER_WAIT: int = 40

const BASIC_ATTACK_ACCURACY: int = 85
const SIDE_HIT_BONUS: int = 10
const BACK_HIT_BONUS: int = 20
const HEIGHT_HIT_BONUS: int = 10
const COVER_HIT_PENALTY: int = 15

const DOWNED_COUNTDOWN_ACTIVATIONS: int = 3
const REVIVE_BASE_HP: int = 3


static func speed_from_initiative(initiative: int) -> int:
	return maxi(1, initiative)


static func action_end_ct(moved: bool, acted: bool, forced_skip: bool = false) -> int:
	if forced_skip:
		return CT_AFTER_FULL_TURN
	if moved and acted:
		return CT_AFTER_FULL_TURN
	if moved or acted:
		return CT_AFTER_SINGLE_ACTION
	return CT_AFTER_WAIT


static func ticks_until_ready(ct: int, speed: int) -> int:
	if ct >= CT_THRESHOLD:
		return 0
	var safe_speed: int = maxi(1, speed)
	return int(ceil(float(CT_THRESHOLD - ct) / float(safe_speed)))


static func positional_hit_bonus(arc: String) -> int:
	match arc:
		"back":
			return BACK_HIT_BONUS
		"side":
			return SIDE_HIT_BONUS
	return 0


static func hit_chance(
	base_accuracy: int,
	attacker_accuracy: int,
	target_evasion: int,
	arc: String = "front",
	height_advantage: bool = false,
	covered: bool = false
) -> int:
	var result: int = base_accuracy + attacker_accuracy - target_evasion
	result += positional_hit_bonus(arc)
	if height_advantage:
		result += HEIGHT_HIT_BONUS
	if covered:
		result -= COVER_HIT_PENALTY
	return clampi(result, 5, 100)


static func apply_end_ct_bonus(base_ct: int, bonus: int) -> int:
	return clampi(base_ct + bonus, 0, CT_THRESHOLD - 1)


static func revive_hp(max_hp: int, flat_bonus: int = 0) -> int:
	return clampi(REVIVE_BASE_HP + flat_bonus, 1, maxi(1, max_hp))


static func downed_tick_remaining(current: int) -> int:
	return maxi(0, current - 1)

static func range_allowed(distance: int, min_range: int, max_range: int) -> bool:
	var safe_min: int = maxi(0, min_range)
	var safe_max: int = maxi(safe_min, max_range)
	return distance >= safe_min and distance <= safe_max


static func defense_for_damage_type(physical_defense: int, magic_defense: int, damage_type: String) -> int:
	return maxi(0, physical_defense if damage_type == "physical" else magic_defense)


static func damage_after_defense(raw_damage: int, defense: int, minimum_damage: int = 1) -> int:
	if raw_damage <= 0:
		return 0
	return maxi(minimum_damage, raw_damage - maxi(0, defense))


static func default_threat_max_range(weapon_family: String, attack_max_range: int) -> int:
	match weapon_family:
		"spear":
			return mini(2, maxi(1, attack_max_range))
		"ranged", "focus":
			return 1
	return 1

