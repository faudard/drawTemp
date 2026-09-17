@tool
class_name SporeMissionRule
extends Resource

## One composable victory/defeat predicate.

@export_enum(
	"all_enemies_defeated",
	"all_players_defeated",
	"survive_rounds",
	"crown_extracted",
	"round_at_least",
	"bonus_collected",
	"unit_defeated",
	"unit_alive",
	"unit_on_extraction"
) var rule_type: String = "all_enemies_defeated"
@export_range(0, 99, 1) var amount: int = 1
@export var unit_id: String = ""
@export var invert: bool = false
@export_multiline var description: String = ""

func summary() -> String:
	var suffix := ""
	if rule_type in ["survive_rounds", "round_at_least", "bonus_collected"]:
		suffix = " ≥ %d" % amount
	elif rule_type in ["unit_defeated", "unit_alive", "unit_on_extraction"]:
		suffix = " • %s" % unit_id
	return ("NON " if invert else "") + rule_type + suffix
