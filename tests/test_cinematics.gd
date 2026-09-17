extends SceneTree

const CinematicCatalog = preload("res://scripts/catalogs/cinematic_catalog.gd")
const MissionCatalog = preload("res://scripts/catalogs/mission_catalog.gd")

var failures: Array[String] = []


func _init() -> void:
	if CinematicCatalog.ids().size() < 8:
		failures.append("Expected the V1.6 cinematic starter library.")
	for cinematic_id in CinematicCatalog.ids():
		var cinematic := CinematicCatalog.definition(cinematic_id)
		if cinematic == null:
			failures.append("Cannot load cinematic %s" % cinematic_id)
			continue
		if cinematic.actions.is_empty():
			failures.append("Cinematic %s has no actions" % cinematic_id)
		for action in cinematic.actions:
			if action == null:
				failures.append("Cinematic %s contains null action" % cinematic_id)
				continue
			if String(action.action_type) == "play_cinematic":
				if CinematicCatalog.definition(String(action.cinematic_id)) == null:
					failures.append("Nested cinematic missing: %s" % action.cinematic_id)
	for index in range(MissionCatalog.count()):
		var mission := MissionCatalog.definition(index)
		if mission == null:
			continue
		for cinematic_id in [String(mission.intro_cinematic_id), String(mission.victory_cinematic_id), String(mission.defeat_cinematic_id)]:
			if not cinematic_id.is_empty() and CinematicCatalog.definition(cinematic_id) == null:
				failures.append("Mission %s references missing cinematic %s" % [mission.id, cinematic_id])
	if failures.is_empty():
		print("Sporebound V1.6 cinematic smoke test: OK")
		quit(0)
		return
	for failure in failures:
		push_error(failure)
	quit(1)
