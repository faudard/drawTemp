@tool
class_name SporeSkillEffect
extends Resource

## Composable effect block used by Sporebound Studio.
## V1.2 supports these blocks directly at runtime for player skills.

@export_enum("damage", "heal", "status", "push", "pull", "focus", "guard", "reaction", "zone") var effect_type: String = "damage"
@export_range(-20, 20, 1) var amount: int = 1
@export var use_attack_stat: bool = false
@export var damage_type: String = "physical"
@export var status_id: String = ""
@export_range(0, 8, 1) var radius: int = 0
@export_enum("single", "cross", "diamond", "line", "circle") var area_shape: String = "single"
@export_enum("target", "self", "allies", "enemies") var target_scope: String = "target"

@export_group("Persistent zone")
@export_enum("damage", "heal", "status") var zone_tick_type: String = "damage"
@export_enum("activation_start", "activation_end") var zone_tick_phase: String = "activation_start"
@export_range(1, 8, 1) var zone_duration_rounds: int = 2


func summary() -> String:
	var amount_text := ""
	if effect_type in ["damage", "heal", "push", "pull", "focus", "zone"]:
		amount_text = " %s%d" % ["+" if amount >= 0 else "", amount]
	if effect_type == "damage" and use_attack_stat:
		amount_text = " ATQ%s%d" % ["+" if amount >= 0 else "", amount]
	var status_text := ""
	if (effect_type == "status" or (effect_type == "zone" and zone_tick_type == "status")) and not status_id.is_empty():
		status_text = " [%s]" % status_id
	var area_text := ""
	if radius > 0:
		area_text = " • %s r%d" % [area_shape, radius]
	var type_text := ""
	if effect_type == "damage" and not damage_type.is_empty():
		type_text = " {%s}" % damage_type
	var zone_text := ""
	if effect_type == "zone":
		zone_text = " {%s/%s %dr}" % [zone_tick_type, zone_tick_phase, zone_duration_rounds]
	return "%s%s%s%s%s → %s%s" % [effect_type.to_upper(), amount_text, type_text, status_text, zone_text, target_scope, area_text]
