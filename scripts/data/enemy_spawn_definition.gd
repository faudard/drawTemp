@tool
class_name SporeEnemySpawnDefinition
extends Resource

## A mission spawn referencing a reusable UnitDefinition.

@export var unit_id: String = "baveux"
@export var position: Vector2i = Vector2i.ZERO
@export var role_override: String = ""
@export_range(-1, 99, 1) var hp_override: int = -1
@export_range(-1, 20, 1) var attack_override: int = -1
@export_range(-1, 12, 1) var move_override: int = -1
@export_range(-1, 12, 1) var range_override: int = -1
