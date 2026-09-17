@tool
class_name SporeJobSkillUnlock
extends Resource

## One skill unlocked by a job at a given mastery level.

@export var skill_id: String = ""
@export_range(1, 20, 1) var required_level: int = 1


func summary() -> String:
	return "%s • niv. %d" % [skill_id if not skill_id.is_empty() else "—", required_level]
