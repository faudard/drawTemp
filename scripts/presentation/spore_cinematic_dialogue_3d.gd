@tool
class_name SporeCinematicDialogue3D
extends Control

signal advance_requested

@export_group("Typewriter")
@export_range(10.0, 120.0, 1.0) var default_chars_per_second: float = 46.0
@export_range(1, 8, 1) var default_blip_every: int = 2
@export_range(0.0, 1.0, 0.01) var punctuation_pause_seconds: float = 0.08
@export_range(-40.0, 0.0, 0.5) var blip_volume_db: float = -16.0
@export var blip_stream: AudioStream

@export_group("Animation")
@export_range(0.05, 0.6, 0.05) var panel_enter_seconds: float = 0.18
@export_range(0.05, 0.6, 0.05) var panel_exit_seconds: float = 0.14

@onready var dimmer: ColorRect = $Dimmer
@onready var letterbox_top: ColorRect = $LetterboxTop
@onready var letterbox_bottom: ColorRect = $LetterboxBottom
@onready var dialogue_panel: Panel = $DialoguePanel
@onready var portrait_left: TextureRect = $DialoguePanel/Margin/Row/PortraitLeft
@onready var portrait_right: TextureRect = $DialoguePanel/Margin/Row/PortraitRight
@onready var speaker_label: Label = $DialoguePanel/Margin/Row/TextColumn/SpeakerName
@onready var message_label: Label = $DialoguePanel/Margin/Row/TextColumn/Message
@onready var hint_label: Label = $DialoguePanel/Margin/Row/TextColumn/Footer/Hint
@onready var continue_button: Button = $DialoguePanel/Margin/Row/TextColumn/Footer/Continue
@onready var advance_pulse: Label = $DialoguePanel/Margin/Row/TextColumn/Footer/AdvancePulse
@onready var fade_rect: ColorRect = $FadeRect
@onready var typewriter_audio: AudioStreamPlayer = $TypewriterAudio

var _full_text: String = ""
var _char_index: int = 0
var _char_accumulator: float = 0.0
var _chars_per_second: float = 46.0
var _blip_every: int = 2
var _voice_pitch: float = 1.0
var _typing: bool = false
var _waiting: bool = false
var _punctuation_delay: float = 0.0
var _generator_playback: AudioStreamGeneratorPlayback = null
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _base_panel_style: StyleBoxFlat = null
var _profile_accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
var _profile_name_color: Color = Color(0.76, 0.92, 1.0, 1.0)
var _line_blip_volume_db: float = -16.0
var _editor_preview_audio_enabled: bool = true


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	continue_button.pressed.connect(_advance_or_reveal)
	_rng.seed = 0xC1E3A
	var source_style: StyleBox = dialogue_panel.get_theme_stylebox("panel")
	if source_style is StyleBoxFlat:
		_base_panel_style = (source_style as StyleBoxFlat).duplicate()
	_setup_blip_audio()
	set_process_unhandled_key_input(true)


func _process(delta: float) -> void:
	if not visible:
		return
	advance_pulse.modulate.a = 0.55 + sin(Time.get_ticks_msec() * 0.008) * 0.35
	if not _typing:
		return

	if _punctuation_delay > 0.0:
		_punctuation_delay = maxf(0.0, _punctuation_delay - delta)
		return

	_char_accumulator += delta
	var seconds_per_char: float = 1.0 / maxf(1.0, _chars_per_second)
	while _char_accumulator >= seconds_per_char and _char_index < _full_text.length():
		_char_accumulator -= seconds_per_char
		_char_index += 1
		message_label.text = _full_text.substr(0, _char_index)

		var character: String = _full_text.substr(_char_index - 1, 1)
		if _should_blip(character) and (_char_index % maxi(1, _blip_every) == 0):
			_play_blip()
		if character in [".", "!", "?", ";", ":"]:
			_punctuation_delay = punctuation_pause_seconds
			break

	if _char_index >= _full_text.length():
		_finish_typing()


func set_line_profile(
	accent_color: Color,
	name_color: Color,
	blip_volume: float
) -> void:
	_profile_accent_color = accent_color
	_profile_name_color = name_color
	_line_blip_volume_db = clampf(blip_volume, -40.0, 0.0)


func present_line(
	speaker: String,
	text_value: String,
	portrait: Texture2D,
	portrait_side: String,
	wait_for_input: bool,
	auto_advance_seconds: float,
	chars_per_second: float,
	voice_pitch: float,
	blip_every: int,
	accent: String = "neutral"
) -> void:
	_editor_preview_audio_enabled = true
	visible = true
	dimmer.visible = true
	letterbox_top.visible = true
	letterbox_bottom.visible = true
	dialogue_panel.visible = true
	_apply_accent(accent)
	_set_portrait(portrait, portrait_side)

	speaker_label.text = speaker if not speaker.is_empty() else "Narrateur"
	_full_text = text_value
	_char_index = 0
	_char_accumulator = 0.0
	_punctuation_delay = 0.0
	_chars_per_second = chars_per_second if chars_per_second > 0.0 else default_chars_per_second
	_voice_pitch = clampf(voice_pitch, 0.55, 1.75)
	typewriter_audio.volume_db = _line_blip_volume_db
	_blip_every = maxi(1, blip_every)
	message_label.text = ""
	_typing = true
	_waiting = true
	continue_button.text = "AFFICHER TOUT"
	advance_pulse.visible = false
	hint_label.text = "Entrée / Espace / clic • 1× affiche tout • 2× continue"

	dialogue_panel.modulate = Color(1.0, 1.0, 1.0, 0.0)
	dialogue_panel.scale = Vector2(0.985, 0.94)
	var enter_tween: Tween = create_tween().set_parallel(true)
	enter_tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	enter_tween.tween_property(dialogue_panel, "modulate", Color.WHITE, panel_enter_seconds)
	enter_tween.tween_property(dialogue_panel, "scale", Vector2.ONE, panel_enter_seconds)

	if wait_for_input or auto_advance_seconds <= 0.0:
		await advance_requested
	else:
		while _typing:
			await get_tree().process_frame
		await get_tree().create_timer(maxf(0.1, auto_advance_seconds)).timeout

	_waiting = false
	await _hide_dialogue_panel()


func editor_preview_line(
	speaker: String,
	text_value: String,
	portrait: Texture2D,
	portrait_side: String,
	chars_per_second: float,
	voice_pitch: float,
	blip_every: int,
	accent: String,
	animate_typewriter: bool,
	enable_audio: bool
) -> void:
	visible = true
	dimmer.visible = true
	letterbox_top.visible = true
	letterbox_bottom.visible = true
	dialogue_panel.visible = true
	fade_rect.color.a = 0.0
	dialogue_panel.modulate = Color.WHITE
	dialogue_panel.scale = Vector2.ONE

	_editor_preview_audio_enabled = enable_audio
	_apply_accent(accent)
	_set_portrait(portrait, portrait_side)

	speaker_label.text = speaker if not speaker.is_empty() else "Narrateur"
	_full_text = text_value
	_char_index = 0
	_char_accumulator = 0.0
	_punctuation_delay = 0.0
	_chars_per_second = chars_per_second if chars_per_second > 0.0 else default_chars_per_second
	_voice_pitch = clampf(voice_pitch, 0.55, 1.75)
	_blip_every = maxi(1, blip_every)
	_waiting = false
	hint_label.text = "APERÇU ÉDITEUR • même scène que le runtime"

	if animate_typewriter:
		message_label.text = ""
		_typing = true
		continue_button.text = "APERÇU..."
		advance_pulse.visible = false
	else:
		message_label.text = _full_text
		_char_index = _full_text.length()
		_typing = false
		continue_button.text = "CONTINUER  ▸"
		advance_pulse.visible = true


func editor_clear_preview() -> void:
	_editor_preview_audio_enabled = false
	hide_all()


func set_fade_alpha(alpha: float, duration: float) -> void:
	var target: Color = fade_rect.color
	target.a = clampf(alpha, 0.0, 1.0)
	if duration <= 0.0:
		fade_rect.color = target
		return
	var tween: Tween = create_tween()
	tween.tween_property(fade_rect, "color", target, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tween.finished


func hide_all() -> void:
	_typing = false
	_waiting = false
	dialogue_panel.visible = false
	letterbox_top.visible = false
	letterbox_bottom.visible = false
	dimmer.visible = false
	if fade_rect.color.a <= 0.001:
		visible = false


func _hide_dialogue_panel() -> void:
	var tween: Tween = create_tween().set_parallel(true)
	tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tween.tween_property(dialogue_panel, "modulate", Color(1.0, 1.0, 1.0, 0.0), panel_exit_seconds)
	tween.tween_property(dialogue_panel, "scale", Vector2(0.99, 0.96), panel_exit_seconds)
	await tween.finished
	dialogue_panel.visible = false
	letterbox_top.visible = false
	letterbox_bottom.visible = false
	dimmer.visible = false
	if fade_rect.color.a <= 0.001:
		visible = false


func _unhandled_key_input(event: InputEvent) -> void:
	if not visible or not _waiting or not event.pressed:
		return
	var key_event: InputEventKey = event as InputEventKey
	if key_event.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
		get_viewport().set_input_as_handled()
		_advance_or_reveal()


func _gui_input(event: InputEvent) -> void:
	if not visible or not _waiting:
		return
	if event is InputEventMouseButton:
		var mouse_event: InputEventMouseButton = event as InputEventMouseButton
		if mouse_event.pressed and mouse_event.button_index == MOUSE_BUTTON_LEFT:
			accept_event()
			_advance_or_reveal()


func _advance_or_reveal() -> void:
	if not _waiting:
		return
	if _typing:
		_char_index = _full_text.length()
		message_label.text = _full_text
		_finish_typing()
		return
	_waiting = false
	advance_requested.emit()


func _finish_typing() -> void:
	_typing = false
	message_label.text = _full_text
	continue_button.text = "CONTINUER  ▸"
	advance_pulse.visible = true


func _set_portrait(texture: Texture2D, side: String) -> void:
	portrait_left.texture = null
	portrait_right.texture = null
	portrait_left.visible = false
	portrait_right.visible = false
	if texture == null:
		return
	if side == "right":
		portrait_right.texture = texture
		portrait_right.visible = true
	else:
		portrait_left.texture = texture
		portrait_left.visible = true


func _apply_accent(accent: String) -> void:
	var accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
	var resolved_name_color: Color = accent_color.lightened(0.18)
	if accent == "profile":
		accent_color = _profile_accent_color
		resolved_name_color = _profile_name_color
	elif accent == "enemy":
		accent_color = Color(1.0, 0.46, 0.40, 1.0)
		resolved_name_color = accent_color.lightened(0.18)
	elif accent == "narrator":
		accent_color = Color(0.86, 0.72, 1.0, 1.0)
		resolved_name_color = accent_color.lightened(0.18)

	speaker_label.add_theme_color_override("font_color", resolved_name_color)
	var style: StyleBoxFlat = StyleBoxFlat.new()
	if _base_panel_style != null:
		style = _base_panel_style.duplicate()
	else:
		style.bg_color = Color(0.035, 0.050, 0.080, 0.98)
		style.corner_radius_top_left = 18
		style.corner_radius_top_right = 18
		style.corner_radius_bottom_left = 18
		style.corner_radius_bottom_right = 18
	style.border_color = accent_color
	style.border_width_left = 2
	style.border_width_top = 2
	style.border_width_right = 2
	style.border_width_bottom = 2
	dialogue_panel.add_theme_stylebox_override("panel", style)


func _setup_blip_audio() -> void:
	typewriter_audio.volume_db = blip_volume_db
	if blip_stream != null:
		typewriter_audio.stream = blip_stream
		return
	var generator: AudioStreamGenerator = AudioStreamGenerator.new()
	generator.mix_rate = 22050.0
	generator.buffer_length = 0.10
	typewriter_audio.stream = generator
	typewriter_audio.play()
	_generator_playback = typewriter_audio.get_stream_playback() as AudioStreamGeneratorPlayback


func _play_blip() -> void:
	if not _editor_preview_audio_enabled:
		return
	var random_pitch: float = _voice_pitch * _rng.randf_range(0.95, 1.05)
	if blip_stream != null:
		typewriter_audio.pitch_scale = random_pitch
		typewriter_audio.play()
		return
	if _generator_playback == null:
		return

	var frames: int = 180
	if _generator_playback.get_frames_available() < frames:
		return
	var mix_rate: float = 22050.0
	var frequency: float = 520.0 * random_pitch
	for index: int in range(frames):
		var t: float = float(index) / mix_rate
		var envelope: float = 1.0 - float(index) / float(frames)
		var sample: float = sin(TAU * frequency * t) * 0.045 * envelope
		_generator_playback.push_frame(Vector2(sample, sample))


func _should_blip(character: String) -> bool:
	return not character.is_empty() and character != " " and character != "\n" and not [".", ",", "!", "?", ";", ":"].has(character)
