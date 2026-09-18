@tool
class_name SporeSkillDefinition
extends Resource

## Data-driven skill definition. V1.2 executes `effects` directly for player skills.

@export_group("Identity")
@export var id: String = "skill"
@export var display_name: String = "Skill"
@export_multiline var description: String = ""

@export_group("MP Economy")
## Serialized as focus_cost for backward compatibility; runtime/UI treat it as MP.
@export_range(0, 10, 1) var focus_cost: int = 1
@export_range(0, 12, 1) var range: int = 1
@export_enum("self", "ally", "enemy", "unit", "ground") var target_mode: String = "enemy"

@export_group("FFT Timing")
@export var uses_accuracy: bool = false
@export_range(5, 100, 1) var accuracy: int = 90
@export_enum("auto", "physical", "magical") var accuracy_kind: String = "auto"
@export_range(0, 30, 1) var cast_time_ticks: int = 0
@export var interrupt_on_damage: bool = false
@export var silence_affected: bool = false
## When > 0, status effects use FFT's Faith/MA success formula: CFa * TFa * (MA + modifier).
@export_range(0, 255, 1) var fft_status_modifier: int = 0

@export_group("Legacy Compatibility")
## Kept so older .tres files still load. The FFT turn loop never gates a skill by cooldown.
@export_range(0, 10, 1) var cooldown_rounds: int = 0

@export_group("Effects")
@export var effects: Array[Resource] = []
@export var effect_tags: PackedStringArray = PackedStringArray()

@export_group("Presentation")
@export var vfx_id: String = "default_hit"


func effect_summaries() -> PackedStringArray:
	var result := PackedStringArray()
	for effect in effects:
		if effect != null:
			result.append(effect.summary())
	return result
