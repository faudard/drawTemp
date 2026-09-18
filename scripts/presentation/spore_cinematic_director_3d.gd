class_name SporeCinematicDirector3D
extends Node

const ShotCatalog = preload("res://scripts/catalogs/cinematic_shot_catalog.gd")

var _host: Node = null
var _profile: Resource = null
var _shot_set: Resource = null
var _last_speaker_id: String = ""
var _previous_speaker_id: String = ""
var _last_shot_id: String = ""
var _participants: Dictionary = {}
var _same_shot_line_count: int = 0
var _first_dialogue_line: bool = true


func configure(host: Node, profile: Resource, fallback_shot_set: Resource = null) -> void:
	_host = host
	_profile = profile
	_shot_set = fallback_shot_set
	if _profile != null:
		var profile_set: Resource = _profile.get("shot_set") as Resource
		if profile_set != null:
			_shot_set = profile_set
	reset()


func reset() -> void:
	_last_speaker_id = ""
	_previous_speaker_id = ""
	_last_shot_id = ""
	_participants.clear()
	_same_shot_line_count = 0
	_first_dialogue_line = true


func prepare_dialogue(action: Resource, speaker_unit_id: String) -> float:
	if action == null or speaker_unit_id.is_empty() or _host == null:
		return 0.0
	if not _host.has_method("cinematic_3d_apply_shot"):
		return 0.0

	var requested_id: String = String(action.get("shot_preset_id"))
	if requested_id == "none":
		_track_speaker(speaker_unit_id)
		return 0.0

	var participant_is_new: bool = not _participants.has(speaker_unit_id)
	var speaker_changed: bool = not _last_speaker_id.is_empty() and speaker_unit_id != _last_speaker_id
	var shot: Resource = null
	var hold: float = _profile_float("cut_hold", 0.05)

	if not requested_id.is_empty() and requested_id != "auto":
		shot = ShotCatalog.definition(requested_id)
	elif _should_establish(speaker_unit_id, participant_is_new):
		shot = _wide_shot()
		hold = _profile_float("establishing_hold", 0.16)
	else:
		shot = _dialogue_shot(speaker_unit_id, speaker_changed)

	if shot == null:
		_track_speaker(speaker_unit_id)
		return 0.0

	var counterpart_id: String = _counterpart_for(speaker_unit_id)
	_host.call("cinematic_3d_apply_shot", speaker_unit_id, counterpart_id, shot)
	_last_shot_id = String(shot.get("id"))

	if speaker_unit_id == _last_speaker_id:
		_same_shot_line_count += 1
	else:
		_same_shot_line_count = 1

	_track_speaker(speaker_unit_id)
	_first_dialogue_line = false

	if not bool(shot.get("instant_cut")):
		hold = maxf(hold, float(shot.get("transition_seconds")))
	return hold


func finish_exchange() -> float:
	if _host == null or not _profile_bool("return_to_wide_after_exchange", false):
		return 0.0
	if _last_speaker_id.is_empty():
		return 0.0
	var wide: Resource = _wide_shot()
	if wide == null:
		return 0.0
	_host.call(
		"cinematic_3d_apply_shot",
		_last_speaker_id,
		_previous_speaker_id,
		wide
	)
	return _profile_float("end_wide_hold", 0.15)


func _should_establish(speaker_unit_id: String, participant_is_new: bool) -> bool:
	if _first_dialogue_line and _profile_bool("establish_first_exchange", true):
		return _wide_shot() != null
	if participant_is_new and not _last_speaker_id.is_empty() and _profile_bool("establish_new_participant", true):
		# Do not interrupt the first A/B hand-off. A third participant gets a new establishing beat.
		if _participants.size() >= 2:
			return _wide_shot() != null
	return false


func _dialogue_shot(speaker_unit_id: String, speaker_changed: bool) -> Resource:
	var shot_a: Resource = _shot_from_set("shot_a")
	var shot_b: Resource = _shot_from_set("shot_b")
	if shot_a == null and shot_b == null:
		return ShotCatalog.definition("show_1")

	if speaker_unit_id == _last_speaker_id and _profile_bool("keep_same_speaker_shot", true):
		var max_same: int = _profile_int("max_consecutive_lines_same_shot", 4)
		if _same_shot_line_count < max_same:
			var current: Resource = ShotCatalog.definition(_last_shot_id)
			if current != null:
				return current

	if not speaker_changed or not _profile_bool("alternate_on_speaker_change", true):
		return shot_a if shot_a != null else shot_b

	var shot_a_id: String = String(shot_a.get("id")) if shot_a != null else ""
	if _last_shot_id == shot_a_id:
		return shot_b if shot_b != null else shot_a
	return shot_a if shot_a != null else shot_b


func _counterpart_for(speaker_unit_id: String) -> String:
	if not _last_speaker_id.is_empty() and _last_speaker_id != speaker_unit_id:
		return _last_speaker_id
	if not _previous_speaker_id.is_empty() and _previous_speaker_id != speaker_unit_id:
		return _previous_speaker_id
	for key: Variant in _participants.keys():
		var candidate: String = String(key)
		if candidate != speaker_unit_id:
			return candidate
	return ""


func _track_speaker(speaker_unit_id: String) -> void:
	_participants[speaker_unit_id] = true
	if speaker_unit_id != _last_speaker_id:
		_previous_speaker_id = _last_speaker_id
		_last_speaker_id = speaker_unit_id


func _wide_shot() -> Resource:
	return _shot_from_set("wide_shot")


func _shot_from_set(property_name: String) -> Resource:
	if _shot_set == null:
		return null
	return _shot_set.get(property_name) as Resource


func _profile_bool(property_name: String, fallback: bool) -> bool:
	if _profile == null:
		return fallback
	var value: Variant = _profile.get(property_name)
	return bool(value) if value != null else fallback


func _profile_float(property_name: String, fallback: float) -> float:
	if _profile == null:
		return fallback
	var value: Variant = _profile.get(property_name)
	return float(value) if value != null else fallback


func _profile_int(property_name: String, fallback: int) -> int:
	if _profile == null:
		return fallback
	var value: Variant = _profile.get(property_name)
	return int(value) if value != null else fallback
