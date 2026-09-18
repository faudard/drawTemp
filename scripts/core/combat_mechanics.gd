class_name SporeCombatMechanics
extends RefCounted

## Shared tactical rules used by both battle runtimes.
## Keep this file scene-agnostic so the 2D and 3D controllers cannot drift apart.

const CT_THRESHOLD: int = 100
# FFT Active Turn CT costs. CT can overflow 100 before a turn starts; the cost is
# subtracted from the real CT value, then the remaining CT is capped at 60.
const CT_COST_MOVE_AND_ACT: int = 100
const CT_COST_SINGLE_ACTION: int = 80
const CT_COST_WAIT: int = 60
const CT_POST_TURN_CAP: int = 60

# Reference values when a unit starts its Active Turn at exactly 100 CT.
const CT_AFTER_FULL_TURN: int = 0
const CT_AFTER_SINGLE_ACTION: int = 20
const CT_AFTER_WAIT: int = 40

# FFT ATTACK is normally checked from a 100% base before evasion layers.
const BASIC_ATTACK_ACCURACY: int = 100
const SIDE_HIT_BONUS: int = 0
const BACK_HIT_BONUS: int = 0
const HEIGHT_HIT_BONUS: int = 0
const COVER_HIT_PENALTY: int = 0

# Charging status in FFT: evade percentages become 0 and the attack stat of
# incoming physical attacks is multiplied by 3/2.
const CHARGING_PHYSICAL_DAMAGE_NUMERATOR: int = 3
const CHARGING_PHYSICAL_DAMAGE_DENOMINATOR: int = 2

const DOWNED_COUNTDOWN_ACTIVATIONS: int = 3
const REVIVE_BASE_HP: int = 3


static func speed_from_initiative(initiative: int) -> int:
	return maxi(1, initiative)


static func action_ct_cost(moved: bool, acted: bool, forced_skip: bool = false) -> int:
	if forced_skip or (moved and acted):
		return CT_COST_MOVE_AND_ACT
	if moved or acted:
		return CT_COST_SINGLE_ACTION
	return CT_COST_WAIT


static func action_end_ct(current_ct: int, moved: bool, acted: bool, forced_skip: bool = false) -> int:
	var remaining: int = maxi(0, current_ct - action_ct_cost(moved, acted, forced_skip))
	return mini(CT_POST_TURN_CAP, remaining)


static func ticks_until_ready(ct: int, speed: int) -> int:
	if speed <= 0:
		return 999999
	if ct >= CT_THRESHOLD:
		return 0
	return int(ceil(float(CT_THRESHOLD - ct) / float(speed)))


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


static func fft_physical_hit_chance(
	base_hit: int,
	attacker_accuracy: int,
	class_evade: int,
	shield_evade: int,
	accessory_evade: int,
	weapon_evade: int,
	arc: String = "front",
	charging: bool = false
) -> int:
	var hit: int = clampi(base_hit + attacker_accuracy, 0, 100)
	if charging:
		return hit
	var cev: int = clampi(class_evade, 0, 100)
	var sev: int = clampi(shield_evade, 0, 100)
	var aev: int = clampi(accessory_evade, 0, 100)
	var wev: int = clampi(weapon_evade, 0, 100)
	match arc:
		"back":
			hit = int(floor(float(hit) * float(100 - aev) / 100.0))
		"side":
			hit = int(floor(float(hit) * float(100 - sev) / 100.0))
			hit = int(floor(float(hit) * float(100 - aev) / 100.0))
			hit = int(floor(float(hit) * float(100 - wev) / 100.0))
		_:
			hit = int(floor(float(hit) * float(100 - cev) / 100.0))
			hit = int(floor(float(hit) * float(100 - sev) / 100.0))
			hit = int(floor(float(hit) * float(100 - aev) / 100.0))
			hit = int(floor(float(hit) * float(100 - wev) / 100.0))
	return clampi(hit, 0, 100)


static func fft_magic_hit_chance(
	base_hit: int,
	attacker_accuracy: int,
	shield_evade: int,
	accessory_evade: int,
	charging: bool = false
) -> int:
	var hit: int = clampi(base_hit + attacker_accuracy, 0, 100)
	if charging:
		return hit
	hit = int(floor(float(hit) * float(100 - clampi(shield_evade, 0, 100)) / 100.0))
	hit = int(floor(float(hit) * float(100 - clampi(accessory_evade, 0, 100)) / 100.0))
	return clampi(hit, 0, 100)


static func apply_charging_physical_vulnerability(damage: int, charging: bool) -> int:
	if not charging or damage <= 0:
		return damage
	return maxi(1, int(floor(float(damage * CHARGING_PHYSICAL_DAMAGE_NUMERATOR) / float(CHARGING_PHYSICAL_DAMAGE_DENOMINATOR))))


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

# FFT character mechanics introduced in V1.30. Existing Sporebound content can
# leave Zodiac unset ("none") to get neutral compatibility.
const DEFAULT_BRAVE: int = 70
const DEFAULT_FAITH: int = 60
const DEFAULT_WEAPON_POWER: int = 1


static func brave_value(value: int) -> int:
	return clampi(value, 1, 100)


static func faith_value(value: int) -> int:
	return clampi(value, 0, 100)


static func reaction_chance(brave: int) -> int:
	# Most FFT reaction abilities use the unit's current Brave as their proc %.
	return brave_value(brave)


static func zodiac_compatibility(
	attacker_sign: String,
	target_sign: String,
	attacker_sex: String = "monster",
	target_sex: String = "monster"
) -> String:
	var signs: Array[String] = [
		"aries", "taurus", "gemini", "cancer", "leo", "virgo",
		"libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
	]
	var a: int = signs.find(attacker_sign.to_lower())
	var b: int = signs.find(target_sign.to_lower())
	if a < 0 or b < 0:
		return "neutral"
	var delta: int = posmod(b - a, 12)
	if delta == 4 or delta == 8:
		return "good"
	if delta == 3 or delta == 9:
		return "bad"
	if delta == 6:
		if attacker_sex == "monster" or target_sex == "monster":
			return "bad"
		return "worst" if attacker_sex == target_sex else "best"
	return "neutral"


static func zodiac_adjust(value: int, compatibility: String) -> int:
	var safe: int = maxi(0, value)
	match compatibility:
		"good":
			return safe + int(floor(float(safe) / 4.0))
		"best":
			return safe + int(floor(float(safe) / 2.0))
		"bad":
			return maxi(0, safe - int(floor(float(safe) / 4.0)))
		"worst":
			return maxi(0, safe - int(floor(float(safe) / 2.0)))
	return safe


static func fft_weapon_damage(
	physical_attack: int,
	magic_attack: int,
	speed: int,
	brave: int,
	weapon_power: int,
	weapon_family: String,
	compatibility: String = "neutral"
) -> int:
	var pa: int = maxi(1, physical_attack)
	var ma: int = maxi(1, magic_attack)
	var sp: int = maxi(1, speed)
	var wp: int = maxi(1, weapon_power)
	var xa: int = pa
	match weapon_family:
		"unarmed":
			xa = int(floor(float(pa * brave_value(brave)) / 100.0))
			xa = zodiac_adjust(xa, compatibility)
			return maxi(1, xa * pa)
		"ranged":
			xa = int(floor(float(pa + sp) / 2.0))
		"focus":
			# Sporebound's focus weapon is mapped to an MA-based FFT-style weapon.
			xa = ma
		_:
			# melee/spear use the canonical PA * WP family.
			xa = pa
	xa = zodiac_adjust(xa, compatibility)
	return maxi(1, xa * wp)


static func fft_magic_damage(
	magic_attack: int,
	spell_power_q: int,
	caster_faith: int,
	target_faith: int,
	compatibility: String = "neutral"
) -> int:
	var ma: int = zodiac_adjust(maxi(1, magic_attack), compatibility)
	var q: int = maxi(1, spell_power_q)
	var numerator: int = q * ma * faith_value(caster_faith) * faith_value(target_faith)
	return maxi(1, int(floor(float(numerator) / 10000.0)))


static func ct_gain_per_tick(base_speed: int, haste: bool, slow: bool) -> int:
	var speed: int = maxi(1, base_speed)
	if haste and not slow:
		return maxi(1, int(floor(float(speed * 3) / 2.0)))
	if slow and not haste:
		return maxi(1, int(floor(float(speed) / 2.0)))
	return speed

# FFT R/S/M ability helpers introduced in V1.31.
static func support_attack_multiplier(value: int, support_ability: String, magical: bool = false) -> int:
	var safe: int = maxi(0, value)
	if (not magical and support_ability == "attack_up") or (magical and support_ability == "magic_attack_up"):
		return maxi(1, int(floor(float(safe * 4) / 3.0)))
	return safe


static func defensive_ability_damage(value: int, damage_type: String, has_protect: bool, has_shell: bool, support_ability: String = "none") -> int:
	var result: int = maxi(0, value)
	if damage_type == "physical":
		if has_protect:
			result = int(floor(float(result * 2) / 3.0))
		if support_ability == "defense_up":
			result = int(floor(float(result * 2) / 3.0))
	else:
		if has_shell:
			result = int(floor(float(result * 2) / 3.0))
		if support_ability == "magic_defense_up":
			result = int(floor(float(result * 2) / 3.0))
	return maxi(0, result)


static func movement_bonus(movement_ability: String) -> int:
	match movement_ability:
		"move_plus_1": return 1
		"move_plus_2": return 2
	return 0


static func teleport_success_chance(distance: int, move_stat: int) -> int:
	# FFT: min(100, 100 - 10 * (teleport_distance - Move)).
	return clampi(100 - 10 * maxi(0, distance - maxi(0, move_stat)), 0, 100)


static func short_charge_ticks(base_ticks: int, support_ability: String) -> int:
	if base_ticks <= 0:
		return 0
	if support_ability == "short_charge":
		return maxi(1, int(ceil(float(base_ticks) / 2.0)))
	return base_ticks


static func blade_grasp_hit_chance(current_hit: int, brave: int, enabled: bool) -> int:
	if not enabled:
		return clampi(current_hit, 0, 100)
	return clampi(int(floor(float(current_hit) * float(100 - brave_value(brave)) / 100.0)), 0, 100)


static func fft_status_success_chance(magic_attack: int, formula_modifier: int, caster_faith: int, target_faith: int, compatibility: String = "neutral", shell: bool = false, magic_defend_up: bool = false) -> int:
	var ma: int = maxi(0, magic_attack)
	if magic_defend_up:
		ma = int(floor(float(ma * 2) / 3.0))
	if shell:
		ma = int(floor(float(ma * 2) / 3.0))
	ma = zodiac_adjust(ma, compatibility)
	var base: int = maxi(0, ma + formula_modifier)
	var chance: int = int(floor(float(base * faith_value(caster_faith) * faith_value(target_faith)) / 10000.0))
	return clampi(chance, 0, 100)
