@tool
class_name SporeCinematicDirectorProfile
extends Resource

## Reusable cinematic direction rules.
## The runtime runner executes actions; this Resource decides how dialogue is framed.

@export_group("Identity")
@export var id: String = "jrpg_default"
@export var display_name: String = "JRPG — dialogue tactique"
@export_multiline var description: String = ""

@export_group("Dialogue Grammar")
@export var shot_set: Resource
@export var establish_first_exchange: bool = true
@export var establish_new_participant: bool = true
@export var keep_same_speaker_shot: bool = true
@export var alternate_on_speaker_change: bool = true
@export_range(0.0, 1.0, 0.01) var establishing_hold: float = 0.16
@export_range(0.0, 1.0, 0.01) var cut_hold: float = 0.05

@export_group("Pacing")
@export_range(1, 8, 1) var max_consecutive_lines_same_shot: int = 4
@export var return_to_wide_after_exchange: bool = false
@export_range(0.0, 1.5, 0.05) var end_wide_hold: float = 0.15


func summary() -> String:
	return "%s • establish=%s • same-speaker=%s • alternate=%s" % [
		display_name,
		str(establish_first_exchange),
		str(keep_same_speaker_shot),
		str(alternate_on_speaker_change),
	]
