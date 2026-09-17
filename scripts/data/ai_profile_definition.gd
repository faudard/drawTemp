@tool
class_name SporeAIProfileDefinition
extends Resource

## Data-driven tactical scoring profile used by enemy movement/target selection.

@export_group("Identity")
@export var id: String = "default"
@export var display_name: String = "Équilibré"
@export_multiline var description: String = ""

@export_group("Positioning")
@export_range(0, 12, 1) var preferred_range: int = 1
@export_range(-20.0, 20.0, 0.5) var distance_weight: float = 10.0
@export_range(-30.0, 30.0, 0.5) var attack_position_bonus: float = 100.0
@export_range(-20.0, 20.0, 0.5) var cover_weight: float = 2.0
@export_range(-20.0, 20.0, 0.5) var height_weight: float = 3.0
@export_range(0.0, 100.0, 1.0) var hazard_penalty: float = 18.0
@export_range(0.0, 100.0, 1.0) var reaction_penalty: float = 22.0
@export_range(0.0, 10.0, 0.1) var movement_cost_weight: float = 0.15

@export_group("Targeting")
@export_range(0.0, 20.0, 0.5) var target_hp_weight: float = 3.0
@export_range(0.0, 20.0, 0.5) var target_distance_weight: float = 1.0
@export_range(0.0, 250.0, 5.0) var crown_carrier_priority: float = 100.0
@export_range(0.0, 100.0, 1.0) var marked_target_priority: float = 12.0
@export_range(0.0, 5.0, 0.1) var skill_bias: float = 1.0

@export_group("Behavior")
@export var prefer_skills: bool = true
@export var avoid_reactions: bool = true
@export var seek_cover: bool = true
