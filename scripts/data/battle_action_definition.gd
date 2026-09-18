@tool
class_name SporeBattleActionDefinition
extends Resource

## One ordered action shared by V1.6 combat-event and cinematic timelines.

@export var id: String = "action"
@export_enum(
	"message",
	"wait",
	"spawn_enemy",
	"apply_status_to_unit",
	"add_hazard",
	"remove_hazard",
	"heal_team",
	"damage_team",
	"grant_focus_team",
	"set_objective_text",
	"set_victory_rule",
	"set_defeat_rule",
	"open_door",
	"close_door",
	"toggle_switch",
	"open_chest",
	"set_phase",
	"play_cinematic",
	"dialogue",
	"camera_focus_cell",
	"camera_focus_unit",
	"camera_shot",
	"camera_zoom",
	"camera_reset",
	"camera_shake",
	"play_music",
	"stop_music",
	"play_sfx",
	"fade_out",
	"fade_in"
) var action_type: String = "message"

@export_multiline var message: String = ""
@export var unit_id: String = ""
@export var status_id: String = ""
@export var object_id: String = ""
@export var cell: Vector2i = Vector2i(-1, -1)
@export_range(-99, 99, 1) var value: int = 1
@export_range(0.0, 10.0, 0.1) var delay_seconds: float = 0.0
@export_enum("player", "enemy") var team: String = "enemy"


@export_group("Cinematic")
@export var cinematic_id: String = ""
@export var speaker: String = ""
@export_file("*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg") var portrait_path: String = ""
@export_enum("left", "right") var portrait_side: String = "left"
@export var wait_for_input: bool = true
@export_range(0.0, 30.0, 0.1) var auto_advance_seconds: float = 0.0

@export_group("Dialogue Presentation")
@export var dialogue_profile_id: String = ""
@export var override_dialogue_profile: bool = false
@export_range(10.0, 120.0, 1.0) var text_speed: float = 46.0
@export_range(0.55, 1.75, 0.05) var voice_pitch: float = 1.0
@export_range(1, 8, 1) var blip_every: int = 2
@export var shot_preset_id: String = "auto"

@export_group("Cinematic Camera")
@export_range(0.25, 3.0, 0.05) var camera_zoom: float = 1.0
@export_range(0.0, 5.0, 0.05) var camera_duration: float = 0.35
@export_file("*.ogg", "*.wav", "*.mp3") var audio_path: String = ""
@export_range(-40.0, 6.0, 0.5) var volume_db: float = -6.0

@export_group("Mission Rule")
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
@export_range(0, 99, 1) var rule_amount: int = 1
@export var rule_unit_id: String = ""
@export var rule_invert: bool = false
@export_enum("any", "all") var rule_mode: String = "any"


func summary() -> String:
	match action_type:
		"message":
			return "message • %s" % message.left(28)
		"wait":
			return "wait • %.1fs" % delay_seconds
		"spawn_enemy":
			return "spawn %s @ %s" % [unit_id, cell]
		"apply_status_to_unit":
			return "%s → %s" % [status_id, unit_id]
		"set_objective_text":
			return "objectif → %s" % message.left(28)
		"set_victory_rule", "set_defeat_rule":
			return "%s → %s" % [action_type, rule_type]
		"open_door", "close_door", "toggle_switch", "open_chest":
			return "%s • %s" % [action_type, object_id]
		"set_phase":
			return "phase → %s" % message
		"play_cinematic":
			return "cinématique → %s" % cinematic_id
		"dialogue":
			return "%s : %s" % [speaker if not speaker.is_empty() else "Dialogue", message.left(28)]
		"camera_focus_cell":
			return "caméra → %s ×%.2f" % [cell, camera_zoom]
		"camera_focus_unit":
			return "caméra → %s ×%.2f" % [unit_id, camera_zoom]
		"camera_zoom":
			return "zoom ×%.2f" % camera_zoom
		"camera_reset":
			return "caméra reset"
		"camera_shake":
			return "secousse • %d" % value
		"play_music":
			return "musique → %s" % audio_path.get_file()
		"stop_music":
			return "stop musique"
		"play_sfx":
			return "SFX → %s" % audio_path.get_file()
		"fade_out", "fade_in":
			return "%s • %.1fs" % [action_type, camera_duration]
	return "%s • %d" % [action_type, value]
