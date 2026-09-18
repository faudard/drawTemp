class_name SporeCinematicPlayer3D
extends Node

signal action_started(action_id: String)
signal playback_finished

const CinematicCatalog = preload("res://scripts/catalogs/cinematic_catalog.gd")
const UnitCatalog = preload("res://scripts/catalogs/unit_catalog.gd")
const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")
const DialogueSpeakerCatalog = preload("res://scripts/catalogs/dialogue_speaker_catalog.gd")

@export var dialogue_scene: PackedScene = preload("res://scenes/ui/cinematic_dialogue_3d.tscn")
@export_range(0, 8, 1) var max_nested_depth: int = 6

var _host: Node = null
var _ui_parent: Control = null
var _dialogue: SporeCinematicDialogue3D = null
var _music_player: AudioStreamPlayer = null
var _sfx_player: AudioStreamPlayer = null
var _running: bool = false


func configure(host: Node, ui_parent: Control) -> void:
	_host = host
	_ui_parent = ui_parent
	_ensure_runtime()


func is_running() -> bool:
	return _running


func play(cinematic_id: String) -> bool:
	return await play_from(cinematic_id, 0)


func play_from(cinematic_id: String, start_index: int = 0) -> bool:
	if cinematic_id.is_empty():
		return false
	_ensure_runtime()
	var definition: Resource = CinematicCatalog.definition(cinematic_id)
	if definition == null:
		return false

	var raw_actions: Variant = definition.get("actions")
	if not (raw_actions is Array):
		return false

	var source: Array = raw_actions as Array
	var selected_actions: Array = []
	var first_index: int = clampi(start_index, 0, source.size())
	for index: int in range(first_index, source.size()):
		selected_actions.append(source[index])

	return await play_actions(selected_actions)


func play_actions(actions: Array) -> bool:
	_ensure_runtime()
	if _running:
		return false

	_running = true
	await _run_actions(actions, 0)

	if _host != null and _host.has_method("cinematic_3d_reset_camera"):
		_host.call("cinematic_3d_reset_camera", 0.20)
		await get_tree().create_timer(0.20).timeout
		if _host.has_method("cinematic_3d_release_camera_override"):
			_host.call("cinematic_3d_release_camera_override")

	if _dialogue != null:
		_dialogue.hide_all()

	_running = false
	playback_finished.emit()
	return true


func _ensure_runtime() -> void:
	if _ui_parent != null and (_dialogue == null or not is_instance_valid(_dialogue)):
		var instance: Node = dialogue_scene.instantiate()
		if instance is SporeCinematicDialogue3D:
			_dialogue = instance as SporeCinematicDialogue3D
			_ui_parent.add_child(_dialogue)

	if _music_player == null:
		_music_player = AudioStreamPlayer.new()
		_music_player.name = "CinematicMusic3D"
		add_child(_music_player)
	if _sfx_player == null:
		_sfx_player = AudioStreamPlayer.new()
		_sfx_player.name = "CinematicSfx3D"
		add_child(_sfx_player)


func _run_actions(raw_actions: Variant, depth: int) -> void:
	if depth > max_nested_depth or not (raw_actions is Array):
		return
	for action_var: Variant in raw_actions:
		if action_var == null:
			continue
		var action: Resource = action_var as Resource
		if action == null:
			continue

		action_started.emit(String(action.get("id")))
		var action_type: String = String(action.get("action_type"))
		var delay: float = float(action.get("delay_seconds"))
		if action_type == "wait":
			await get_tree().create_timer(maxf(0.1, delay)).timeout
			continue
		if delay > 0.0:
			await get_tree().create_timer(delay).timeout

		match action_type:
			"play_cinematic":
				var nested_id: String = String(action.get("cinematic_id"))
				var nested: Resource = CinematicCatalog.definition(nested_id)
				if nested != null:
					await _run_actions(nested.get("actions"), depth + 1)
			"dialogue":
				await _play_dialogue(action)
			"camera_focus_cell":
				var cell_duration: float = float(action.get("camera_duration"))
				_call_host("cinematic_3d_focus_cell", [action.get("cell"), float(action.get("camera_zoom")), cell_duration])
				if cell_duration > 0.0:
					await get_tree().create_timer(cell_duration).timeout
			"camera_focus_unit":
				var unit_duration: float = float(action.get("camera_duration"))
				_call_host("cinematic_3d_focus_unit", [String(action.get("unit_id")), float(action.get("camera_zoom")), unit_duration])
				if unit_duration > 0.0:
					await get_tree().create_timer(unit_duration).timeout
			"camera_zoom":
				var zoom_duration: float = float(action.get("camera_duration"))
				_call_host("cinematic_3d_zoom", [float(action.get("camera_zoom")), zoom_duration])
				if zoom_duration > 0.0:
					await get_tree().create_timer(zoom_duration).timeout
			"camera_reset":
				var reset_duration: float = float(action.get("camera_duration"))
				_call_host("cinematic_3d_reset_camera", [reset_duration])
				if reset_duration > 0.0:
					await get_tree().create_timer(reset_duration).timeout
				_call_host("cinematic_3d_release_camera_override", [])
			"camera_shake":
				_call_host("cinematic_3d_camera_shake", [float(maxi(1, int(action.get("value"))))])
				await get_tree().create_timer(0.18).timeout
			"fade_out":
				if _dialogue != null:
					_dialogue.visible = true
					await _dialogue.set_fade_alpha(1.0, float(action.get("camera_duration")))
			"fade_in":
				if _dialogue != null:
					_dialogue.visible = true
					await _dialogue.set_fade_alpha(0.0, float(action.get("camera_duration")))
			"play_music":
				_play_audio(action, _music_player)
			"stop_music":
				_music_player.stop()
			"play_sfx":
				_play_audio(action, _sfx_player)
			_:
				if _host != null and _host.has_method("cinematic_3d_execute_action"):
					_host.call("cinematic_3d_execute_action", action)


func _play_dialogue(action: Resource) -> void:
	if _dialogue == null:
		return

	var speaker: String = String(action.get("speaker"))
	var unit_id: String = String(action.get("unit_id"))
	if speaker.is_empty() and not unit_id.is_empty():
		var unit: Resource = UnitCatalog.definition(unit_id)
		if unit != null:
			speaker = String(unit.get("display_name"))
	if speaker.is_empty():
		speaker = "Narrateur"

	var profile_id: String = String(action.get("dialogue_profile_id"))
	var profile: Resource = DialogueSpeakerCatalog.resolve(
		profile_id,
		unit_id,
		speaker
	)
	var override_profile: bool = bool(action.get("override_dialogue_profile"))

	var portrait: Texture2D = _resolve_portrait(action, speaker, profile)
	var portrait_side: String = String(action.get("portrait_side"))
	var accent: String = _speaker_accent(unit_id, speaker)
	var chars_per_second: float = float(action.get("text_speed"))
	var voice_pitch: float = float(action.get("voice_pitch"))
	var blip_every: int = int(action.get("blip_every"))

	if profile != null and not override_profile:
		portrait_side = String(profile.get("portrait_side"))
		chars_per_second = float(profile.get("text_speed"))
		voice_pitch = float(profile.get("voice_pitch"))
		blip_every = int(profile.get("blip_every"))
		accent = "profile"
		var profile_accent: Color = Color(profile.get("accent_color"))
		var profile_name: Color = Color(profile.get("name_color"))
		_dialogue.set_line_profile(
			profile_accent,
			profile_name,
			float(profile.get("blip_volume_db"))
		)
	else:
		_dialogue.set_line_profile(
			Color(0.48, 0.82, 1.0, 1.0),
			Color(0.76, 0.92, 1.0, 1.0),
			-16.0
		)

	await _dialogue.present_line(
		speaker,
		String(action.get("message")),
		portrait,
		portrait_side,
		bool(action.get("wait_for_input")),
		float(action.get("auto_advance_seconds")),
		chars_per_second,
		voice_pitch,
		blip_every,
		accent
	)


func _resolve_portrait(action: Resource, speaker: String, profile: Resource = null) -> Texture2D:
	var explicit_path: String = String(action.get("portrait_path"))
	if not explicit_path.is_empty() and ResourceLoader.exists(explicit_path):
		return load(explicit_path) as Texture2D

	if profile != null:
		var profile_path: String = String(profile.get("portrait_path"))
		if not profile_path.is_empty() and ResourceLoader.exists(profile_path):
			return load(profile_path) as Texture2D

	var unit_id: String = String(action.get("unit_id"))
	if not unit_id.is_empty():
		var unit: Resource = UnitCatalog.definition(unit_id)
		if unit != null:
			var visual_id: String = String(unit.get("visual_id"))
			if visual_id.is_empty():
				visual_id = unit_id
			var visual: Resource = VisualCatalog.definition(visual_id)
			if visual != null:
				var path: String = String(visual.get("portrait_path"))
				if not path.is_empty() and ResourceLoader.exists(path):
					return load(path) as Texture2D

	for candidate_id: String in UnitCatalog.all_unit_ids():
		var candidate: Resource = UnitCatalog.definition(candidate_id)
		if candidate == null or String(candidate.get("display_name")).to_lower() != speaker.to_lower():
			continue
		var candidate_visual_id: String = String(candidate.get("visual_id"))
		if candidate_visual_id.is_empty():
			candidate_visual_id = candidate_id
		var candidate_visual: Resource = VisualCatalog.definition(candidate_visual_id)
		if candidate_visual != null:
			var candidate_path: String = String(candidate_visual.get("portrait_path"))
			if not candidate_path.is_empty() and ResourceLoader.exists(candidate_path):
				return load(candidate_path) as Texture2D
	return null


func _speaker_accent(unit_id: String, speaker: String) -> String:
	if speaker.to_lower() == "narrateur":
		return "narrator"
	if _host != null and _host.has_method("cinematic_3d_unit_team"):
		var team: String = String(_host.call("cinematic_3d_unit_team", unit_id))
		if team == "enemy":
			return "enemy"
		if team == "player":
			return "player"
	return "neutral"


func _play_audio(action: Resource, player: AudioStreamPlayer) -> void:
	if player == null:
		return
	var audio_path: String = String(action.get("audio_path"))
	if audio_path.is_empty() or not ResourceLoader.exists(audio_path):
		return
	var stream: AudioStream = load(audio_path) as AudioStream
	if stream == null:
		return
	player.stream = stream
	player.volume_db = float(action.get("volume_db"))
	player.play()


func _call_host(method_name: String, args: Array) -> void:
	if _host == null or not _host.has_method(method_name):
		return
	_host.callv(method_name, args)
