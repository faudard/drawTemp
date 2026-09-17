@tool
class_name SporeResistanceEntry
extends Resource

## Percentage resistance for one damage family. Positive reduces damage, negative is a weakness.

@export var damage_type: String = "physical"
@export_range(-100, 100, 5) var percent: int = 0


func summary() -> String:
	return "%s %+d%%" % [damage_type, percent]
