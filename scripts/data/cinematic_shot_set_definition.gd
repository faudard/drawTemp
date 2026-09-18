@tool
class_name SporeCinematicShotSetDefinition
extends Resource

## A reusable shot/reverse-shot grammar.
## Shot A and Shot B are complementary dialogue framings; Wide is optional.

@export_group("Identity")
@export var id: String = "dialogue_default"
@export var display_name: String = "Dialogue — champ / contrechamp"

@export_group("Shots")
@export var shot_a: Resource
@export var shot_b: Resource
@export var wide_shot: Resource

@export_group("Automatic Dialogue")
@export var alternate_when_speaker_changes: bool = true
@export var use_wide_for_first_line: bool = false
@export_range(0.0, 1.0, 0.05) var pre_dialogue_hold: float = 0.06
