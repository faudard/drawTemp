@tool
class_name SporeCinematicDefinition
extends Resource

## Reusable ordered cinematic/action timeline.
## The same action resource is shared with battle event sequences.

@export_group("Identity")
@export var id: String = "cinematic"
@export var display_name: String = "Cinematic"
@export_multiline var description: String = ""

@export_group("Direction")
@export var director_profile: Resource = preload("res://data/cinematic_directors/jrpg_default.tres")

@export_group("Timeline")
@export var actions: Array[Resource] = []


func summary() -> String:
	return "%s • %d action(s)" % [display_name, actions.size()]
