@tool
class_name SporeMissionDefinition
extends Resource

## Data-driven tactical map + mission metadata.
## Parallel enemy arrays and V1.4 mission logic are edited through Sporebound Studio.

@export_group("Identity")
@export var id: String = "mission"
@export var display_name: String = "Mission"
@export_multiline var brief: String = ""
@export_multiline var secondary_objective: String = ""

@export_group("Rules")
@export_enum("crown", "survive", "eliminate") var objective: String = "eliminate"
@export_range(0, 20, 1) var survival_rounds: int = 0
@export_range(1, 30, 1) var grid_width: int = 10
@export_range(1, 30, 1) var grid_height: int = 8
@export_file("*.tscn") var map_scene_path: String = ""

@export_group("Cinematics")
@export var intro_cinematic_id: String = ""
@export var victory_cinematic_id: String = ""
@export var defeat_cinematic_id: String = ""

@export_group("Mission Logic")
@export_enum("any", "all") var victory_rule_mode: String = "any"
@export var victory_rules: Array[Resource] = []
@export_enum("any", "all") var defeat_rule_mode: String = "any"
@export var defeat_rules: Array[Resource] = []
@export var battle_triggers: Array[Resource] = []
@export var interactables: Array[Resource] = []

@export_group("Map")
@export var obstacles: Array[Vector2i] = []
@export var cover: Array[Vector2i] = []
@export var hazards: Array[Vector2i] = []
@export var extraction: Array[Vector2i] = []
@export var bonus: Array[Vector2i] = []
@export var crown: Vector2i = Vector2i(-9, -9)
@export var height_level_1: Array[Vector2i] = []
@export var height_level_2: Array[Vector2i] = []

@export_group("Deployment")
@export var hero_starts: Array[Vector2i] = []
@export var enemy_ids: PackedStringArray = PackedStringArray()
@export var enemy_positions: Array[Vector2i] = []
@export var enemy_roles: PackedStringArray = PackedStringArray()
@export var enemy_hp_overrides: PackedInt32Array = PackedInt32Array()
@export var enemy_attack_overrides: PackedInt32Array = PackedInt32Array()
@export var enemy_move_overrides: PackedInt32Array = PackedInt32Array()
@export var enemy_range_overrides: PackedInt32Array = PackedInt32Array()


func terrain_heights() -> Dictionary:
	var heights: Dictionary = {}
	for cell in height_level_1:
		heights[cell] = 1
	for cell in height_level_2:
		heights[cell] = 2
	return heights


func enemy_count() -> int:
	return min(enemy_ids.size(), enemy_positions.size())
