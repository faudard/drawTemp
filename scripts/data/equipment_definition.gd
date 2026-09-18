@tool
class_name SporeEquipmentDefinition
extends Resource

## Reusable item/relic. Equipment is separated from jobs and can be restricted by slot.

@export_group("Identity")
@export var id: String = "equipment"
@export var display_name: String = "Equipment"
@export_multiline var description: String = ""
@export_enum("weapon", "armor", "accessory") var slot: String = "accessory"
@export var icon_path: String = ""

@export_group("Stat modifiers")
@export_range(-30, 30, 1) var hp_bonus: int = 0
@export_range(-20, 20, 1) var attack_bonus: int = 0
@export_range(-20, 20, 1) var magic_power_bonus: int = 0
@export_range(-20, 20, 1) var physical_defense_bonus: int = 0
@export_range(-20, 20, 1) var magic_defense_bonus: int = 0
@export_range(-8, 8, 1) var movement_bonus: int = 0
@export_range(-8, 8, 1) var range_bonus: int = 0
@export_range(-20, 20, 1) var initiative_bonus: int = 0
@export_range(-30, 30, 1) var accuracy_bonus: int = 0
@export_range(-30, 30, 1) var evasion_bonus: int = 0
@export_range(-10, 10, 1) var focus_bonus: int = 0

@export_group("Weapon profile")
@export_enum("none", "melee", "spear", "ranged", "focus") var weapon_family: String = "none"
@export_range(0, 40, 1) var weapon_power: int = 0
@export_range(0, 8, 1) var attack_min_range: int = 0
@export_range(0, 12, 1) var attack_max_range: int = 0
@export_range(0, 8, 1) var threat_min_range: int = 0
@export_range(0, 8, 1) var threat_max_range: int = 0
@export var can_opportunity_attack: bool = true
@export var basic_attack_damage_type: String = "physical"
@export_range(0, 100, 1) var shield_block_chance: int = 0
@export_range(0, 8, 1) var shield_block_reduction: int = 0
@export_group("FFT Evasion")
@export_range(0, 100, 1) var physical_shield_evasion: int = 0
@export_range(0, 100, 1) var magic_shield_evasion: int = 0
@export_range(0, 100, 1) var physical_accessory_evasion: int = 0
@export_range(0, 100, 1) var magic_accessory_evasion: int = 0
@export_range(0, 100, 1) var physical_weapon_evasion: int = 0

@export_group("Tactical modifiers")
@export_range(-6, 6, 1) var basic_attack_damage_bonus: int = 0
@export_range(-40, 40, 1) var basic_attack_accuracy_bonus: int = 0
@export_range(0, 6, 1) var flat_damage_reduction: int = 0
@export_range(-5, 5, 1) var focus_regen_bonus: int = 0
@export_range(-30, 30, 1) var end_ct_bonus: int = 0
@export_range(-6, 6, 1) var revive_hp_bonus: int = 0

@export_group("Extras")
@export var resistances: Array[Resource] = []
@export var granted_skill_id: String = ""
@export var start_status_id: String = ""


func short_description() -> String:
	var parts: Array[String] = []
	if hp_bonus != 0:
		parts.append("%+d PV" % hp_bonus)
	if attack_bonus != 0:
		parts.append("%+d PUI.P" % attack_bonus)
	if magic_power_bonus != 0:
		parts.append("%+d PUI.M" % magic_power_bonus)
	if physical_defense_bonus != 0:
		parts.append("%+d DEF.P" % physical_defense_bonus)
	if magic_defense_bonus != 0:
		parts.append("%+d DEF.M" % magic_defense_bonus)
	if movement_bonus != 0:
		parts.append("%+d MVT" % movement_bonus)
	if range_bonus != 0:
		parts.append("%+d POR" % range_bonus)
	if initiative_bonus != 0:
		parts.append("%+d INIT" % initiative_bonus)
	if accuracy_bonus != 0:
		parts.append("%+d PRÉC" % accuracy_bonus)
	if evasion_bonus != 0:
		parts.append("%+d ESQ" % evasion_bonus)
	if focus_bonus != 0:
		parts.append("%+d FOCUS" % focus_bonus)
	if basic_attack_damage_bonus != 0:
		parts.append("%+d DGT attaque" % basic_attack_damage_bonus)
	if basic_attack_accuracy_bonus != 0:
		parts.append("%+d%% HIT attaque" % basic_attack_accuracy_bonus)
	if flat_damage_reduction != 0:
		parts.append("-%d DGT reçus" % flat_damage_reduction)
	if focus_regen_bonus != 0:
		parts.append("%+d Focus/tour" % focus_regen_bonus)
	if end_ct_bonus != 0:
		parts.append("%+d CT conservé" % end_ct_bonus)
	if revive_hp_bonus != 0:
		parts.append("%+d PV réanimation" % revive_hp_bonus)
	if weapon_family != "none":
		if weapon_power > 0:
			parts.append("WP %d" % weapon_power)
		var min_text: int = attack_min_range if attack_min_range > 0 else 1
		var max_text: int = attack_max_range if attack_max_range > 0 else min_text
		parts.append("%s %d-%d" % [weapon_family.to_upper(), min_text, max_text])
	if shield_block_chance > 0 and shield_block_reduction > 0:
		parts.append("BLOC %d%% -%d" % [shield_block_chance, shield_block_reduction])
	if not start_status_id.is_empty():
		parts.append("départ: %s" % start_status_id)
	return description if parts.is_empty() else ", ".join(parts)
