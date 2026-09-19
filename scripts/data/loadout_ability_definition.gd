class_name SporeLoadoutAbilityDefinition
extends Resource

@export_group("Identity")
@export var id: String = ""
@export var display_name: String = "Ability"
@export_multiline var description: String = ""
@export_enum("reaction", "support", "movement") var slot: String = "support"

@export_group("Unlock")
@export var unlock_job_id: String = ""
@export_range(1, 99, 1) var required_job_level: int = 1

@export_group("Reaction")
@export var reaction_type: String = "none"
@export_range(1, 8, 1) var reaction_range: int = 1
@export_range(0, 20, 1) var reaction_damage_bonus: int = 0

@export_group("Support bonuses")
@export var hp_bonus: int = 0
@export var attack_bonus: int = 0
@export var initiative_bonus: int = 0
@export var accuracy_bonus: int = 0
@export var evasion_bonus: int = 0
@export var focus_bonus: int = 0
@export var focus_regen_bonus: int = 0
@export var end_ct_bonus: int = 0
@export var revive_hp_bonus: int = 0

@export_group("Movement bonuses")
@export var movement_bonus: int = 0
@export var jump_up_bonus: int = 0
@export var jump_down_bonus: int = 0
@export var ignore_opportunity: bool = false
