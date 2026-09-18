@tool
class_name SporeSkillDefinition
extends Resource

## Data-driven skill definition. V1.2 executes `effects` directly for player skills.

@export_group("Identity")
@export var id: String = "skill"
@export var display_name: String = "Skill"
@export_multiline var description: String = ""

@export_group("Economy")
@export_range(0, 10, 1) var focus_cost: int = 1
@export_range(0, 10, 1) var cooldown_rounds: int = 2
@export_range(0, 12, 1) var range: int = 1
@export_enum("self", "ally", "enemy", "unit", "ground") var target_mode: String = "enemy"

@export_group("Effects")
@export var effects: Array[Resource] = []
@export var effect_tags: PackedStringArray = PackedStringArray()

@export_group("Tactical Resolution")
## Existing skills preserve their previous guaranteed-hit behavior unless enabled explicitly.
@export var uses_accuracy: bool = false
@export_range(5, 100, 1) var accuracy: int = 100
@export_range(0, 20, 1) var cast_time_ticks: int = 0
@export var interrupt_on_damage: bool = true

@export_group("Presentation")
@export var vfx_id: String = "default_hit"


func effect_summaries() -> PackedStringArray:
	var result := PackedStringArray()
	for effect in effects:
		if effect != null:
			result.append(effect.summary())
	return result
