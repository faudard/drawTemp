@tool
class_name SporeUnitDefinition
extends Resource

## Data-driven unit template edited by Sporebound Studio.

@export_group("Identity")
@export var id: String = "unit"
@export var display_name: String = "Unit"
@export var role: String = "Role"
@export_enum("player", "enemy") var team: String = "enemy"
@export var color: Color = Color.WHITE
@export var visual_id: String = ""

@export_group("Stats")
@export_range(1, 99, 1) var max_hp: int = 8
@export_range(0, 20, 1) var attack: int = 2
@export_range(0, 20, 1) var magic_power: int = 1
@export_range(0, 20, 1) var physical_defense: int = 0
@export_range(0, 20, 1) var magic_defense: int = 0
@export_range(1, 12, 1) var movement: int = 3
@export_range(1, 12, 1) var attack_range: int = 1
@export_range(0, 30, 1) var initiative: int = 5
@export_range(-50, 50, 1) var accuracy: int = 0
@export_range(-50, 50, 1) var evasion: int = 0

@export_group("FFT Character")
@export_range(1, 100, 1) var brave: int = 70
@export_range(0, 100, 1) var faith: int = 60
@export_enum("none", "aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces", "serpentarius") var zodiac_sign: String = "none"
@export_enum("male", "female", "monster") var sex: String = "monster"

@export_group("FFT Evasion")
## When left at 0, physical_class_evasion falls back to the legacy `evasion` stat.
@export_range(0, 100, 1) var physical_class_evasion: int = 0
@export_range(0, 100, 1) var physical_shield_evasion: int = 0
@export_range(0, 100, 1) var physical_accessory_evasion: int = 0
@export_range(0, 100, 1) var physical_weapon_evasion: int = 0
@export_range(0, 100, 1) var magic_shield_evasion: int = 0
@export_range(0, 100, 1) var magic_accessory_evasion: int = 0

@export_group("MP (legacy storage: Focus)")
@export_range(0, 20, 1) var max_focus: int = 2

@export_group("Basic weapon")
@export_enum("unarmed", "melee", "spear", "ranged", "focus") var weapon_family: String = "unarmed"
@export_range(1, 40, 1) var weapon_power: int = 1
@export_range(1, 8, 1) var attack_min_range: int = 1
@export_range(1, 8, 1) var threat_min_range: int = 1
@export_range(1, 8, 1) var threat_max_range: int = 1
@export var can_opportunity_attack: bool = true
@export var basic_attack_damage_type: String = "physical"

@export_group("Actions")
@export var primary_skill: String = ""
@export var secondary_skill: String = ""
@export var ai_profile: String = "default"

@export_group("FFT Ability Slots")
@export_enum("none", "counter", "opportunity", "intercept", "blade_grasp", "auto_potion", "mp_switch") var reaction_type: String = "none"
@export_enum("none", "attack_up", "magic_attack_up", "defense_up", "magic_defense_up", "concentrate", "short_charge") var support_ability: String = "none"
@export_enum("none", "move_plus_1", "move_plus_2", "ignore_height", "teleport", "move_mp_up") var movement_ability: String = "none"
@export_range(1, 6, 1) var reaction_range: int = 1
@export_range(0, 6, 1) var reaction_damage_bonus: int = 0

@export_group("Progression")
@export var default_job_id: String = ""
@export var available_job_ids: PackedStringArray = PackedStringArray()
@export_range(1, 20, 1) var starting_level: int = 1


func to_runtime_dict(position: Vector2i, team_override: String = "") -> Dictionary:
	var runtime_team := team if team_override.is_empty() else team_override
	return {
		"id": id,
		"name": display_name,
		"role": role,
		"team": runtime_team,
		"pos": position,
		"hp": max_hp,
		"max_hp": max_hp,
		"attack": attack,
		"physical_power": attack,
		"magic_power": magic_power,
		"physical_defense": physical_defense,
		"magic_defense": magic_defense,
		"move": movement,
		"range": attack_range,
		"attack_min_range": attack_min_range,
		"attack_max_range": attack_range,
		"threat_min_range": threat_min_range,
		"threat_max_range": threat_max_range,
		"weapon_family": weapon_family,
		"weapon_power": weapon_power,
		"can_opportunity_attack": can_opportunity_attack,
		"basic_attack_damage_type": basic_attack_damage_type,
		"shield_block_chance": 0,
		"shield_block_reduction": 0,
		"color": color,
		"visual_id": visual_id if not visual_id.is_empty() else id,
		"special": primary_skill,
		"initiative": initiative,
		"accuracy": accuracy,
		"evasion": evasion,
		"brave": brave,
		"faith": faith,
		"zodiac_sign": zodiac_sign,
		"sex": sex,
		"physical_class_evasion": physical_class_evasion if physical_class_evasion > 0 else maxi(0, evasion),
		"physical_shield_evasion": physical_shield_evasion,
		"physical_accessory_evasion": physical_accessory_evasion,
		"physical_weapon_evasion": physical_weapon_evasion,
		"magic_shield_evasion": magic_shield_evasion,
		"magic_accessory_evasion": magic_accessory_evasion,
		"ct": 0,
		"casting": {},
		"downed": false,
		"downed_countdown": 0,
		"removed_from_battle": false,
		"end_ct_bonus": 0,
		"basic_attack_damage_bonus": 0,
		"basic_attack_accuracy_bonus": 0,
		"flat_damage_reduction": 0,
		"focus_regen_bonus": 0,
		"revive_hp_bonus": 0,
		"jump_up_bonus": 0,
		"jump_down_bonus": 0,
		"ignore_opportunity": false,
		"facing": Vector2i(0, -1) if runtime_team == "player" else Vector2i(0, 1),
		"statuses": {},
		"has_moved": false,
		"has_acted": false,
		"reaction_used": false,
		"reaction_type": reaction_type,
		"support_ability": support_ability,
		"movement_ability": movement_ability,
		"reaction_range": reaction_range,
		"reaction_damage_bonus": reaction_damage_bonus,
		"reaction_ready": false,
		"max_focus": max_focus,
		"focus": max_focus,
		"cooldowns": {},
		"secondary": secondary_skill,
		"boss_phase": 1,
		"ai_profile": ai_profile,
		"template_id": id,
		"job_id": default_job_id,
		"job_level": starting_level,
		"resistances": {},
	}
