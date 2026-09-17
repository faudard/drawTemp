@tool
class_name SporeStatusDefinition
extends Resource

## Data-driven status definition edited by Sporebound Studio V1.3.
## Durations are counted in activations of the affected unit. A value of 0 means persistent.

@export_group("Identity")
@export var id: String = "status"
@export var display_name: String = "Status"
@export_multiline var description: String = ""
@export var color: Color = Color.WHITE
@export var vfx_id: String = ""

@export_group("Lifetime")
@export_range(0, 20, 1) var duration_activations: int = 1
@export_range(1, 8, 1) var max_stacks: int = 1
@export_enum("refresh", "stack", "replace") var stack_mode: String = "refresh"
@export var remove_on_damage_taken: bool = false
@export var remove_on_attack: bool = false

@export_group("Periodic")
@export_enum("none", "activation_start", "activation_end") var tick_phase: String = "none"
@export_range(0, 20, 1) var tick_damage: int = 0
@export var tick_damage_type: String = "physical"
@export_range(0, 20, 1) var tick_heal: int = 0

@export_group("Modifiers")
@export_range(-10, 10, 1) var attack_delta: int = 0
@export_range(-10, 10, 1) var magic_power_delta: int = 0
@export_range(-10, 10, 1) var physical_defense_delta: int = 0
@export_range(-10, 10, 1) var magic_defense_delta: int = 0
@export_range(-10, 10, 1) var movement_delta: int = 0
@export_range(-10, 10, 1) var range_delta: int = 0
@export_range(-20, 20, 1) var initiative_delta: int = 0
@export_range(-50, 50, 1) var accuracy_delta: int = 0
@export_range(-50, 50, 1) var evasion_delta: int = 0
@export_range(-10, 10, 1) var outgoing_damage_delta: int = 0
@export_range(-10, 10, 1) var incoming_damage_delta: int = 0

@export_group("Locks")
@export var prevents_movement: bool = false
@export var prevents_action: bool = false


func summary() -> String:
	var parts: Array[String] = []
	if duration_activations > 0:
		parts.append("%d act." % duration_activations)
	else:
		parts.append("persistant")
	if tick_damage > 0:
		parts.append("-%d PV %s/%s" % [tick_damage, tick_damage_type, tick_phase])
	if tick_heal > 0:
		parts.append("+%d PV/%s" % [tick_heal, tick_phase])
	if attack_delta != 0:
		parts.append("PUI.P %+d" % attack_delta)
	if magic_power_delta != 0:
		parts.append("PUI.M %+d" % magic_power_delta)
	if physical_defense_delta != 0:
		parts.append("DEF.P %+d" % physical_defense_delta)
	if magic_defense_delta != 0:
		parts.append("DEF.M %+d" % magic_defense_delta)
	if movement_delta != 0:
		parts.append("MVT %+d" % movement_delta)
	if range_delta != 0:
		parts.append("PORTÉE %+d" % range_delta)
	if accuracy_delta != 0:
		parts.append("PRÉC %+d" % accuracy_delta)
	if evasion_delta != 0:
		parts.append("ESQ %+d" % evasion_delta)
	if incoming_damage_delta != 0:
		parts.append("dégâts reçus %+d" % incoming_damage_delta)
	if outgoing_damage_delta != 0:
		parts.append("dégâts infligés %+d" % outgoing_damage_delta)
	if prevents_movement:
		parts.append("immobilise")
	if prevents_action:
		parts.append("bloque action")
	return " • ".join(parts)
