@tool
class_name SporeVisualPreview
extends Control

var visual: Resource = null
var state: String = "idle"
var direction: String = "front"
var elapsed: float = 0.0
var _cached_path: String = ""
var _cached_texture: Texture2D = null
var _cached_portrait_path: String = ""
var _cached_portrait: Texture2D = null


func _ready() -> void:
	custom_minimum_size = Vector2(430, 330)
	set_process(true)


func set_visual(value: Resource) -> void:
	visual = value
	elapsed = 0.0
	_cached_path = ""
	_cached_texture = null
	_cached_portrait_path = ""
	_cached_portrait = null
	queue_redraw()


func set_state(value: String) -> void:
	state = value
	elapsed = 0.0
	queue_redraw()


func set_direction(value: String) -> void:
	direction = value
	queue_redraw()


func _process(delta: float) -> void:
	elapsed += delta
	queue_redraw()


func _texture(path: String, portrait: bool = false) -> Texture2D:
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	if portrait:
		if _cached_portrait_path == path and _cached_portrait != null:
			return _cached_portrait
		var portrait_loaded: Resource = load(path)
		_cached_portrait_path = path
		_cached_portrait = null
		if portrait_loaded is Texture2D:
			_cached_portrait = portrait_loaded as Texture2D
		return _cached_portrait
	if _cached_path == path and _cached_texture != null:
		return _cached_texture
	var sprite_loaded: Resource = load(path)
	_cached_path = path
	_cached_texture = null
	if sprite_loaded is Texture2D:
		_cached_texture = sprite_loaded as Texture2D
	return _cached_texture


func _draw() -> void:
	var background: Rect2 = Rect2(Vector2.ZERO, size)
	draw_rect(background, Color("#121a28"), true)
	for y: int in range(0, int(size.y), 24):
		for x: int in range(0, int(size.x), 24):
			if (int(x / 24) + int(y / 24)) % 2 == 0:
				draw_rect(Rect2(x, y, 24, 24), Color(1, 1, 1, 0.025), true)
	if visual == null:
		draw_string(ThemeDB.fallback_font, Vector2(18, 30), "Aucun visuel sélectionné", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color.WHITE)
		return
	var center: Vector2 = Vector2(size.x * 0.42, size.y * 0.52)
	var current_render_mode: String = String(visual.get("render_mode"))
	if current_render_mode.is_empty():
		current_render_mode = "auto"
	var texture: Texture2D = _texture(String(visual.get("sprite_sheet_path")))
	var portrait_path: String = String(visual.get("portrait_path"))
	if current_render_mode == "portrait_billboard" and state == "attack" and not String(visual.get("attack_pose_path")).is_empty():
		portrait_path = String(visual.get("attack_pose_path"))
	elif current_render_mode == "portrait_billboard" and state == "cast" and not String(visual.get("cast_pose_path")).is_empty():
		portrait_path = String(visual.get("cast_pose_path"))
	var portrait_texture: Texture2D = _texture(portrait_path, true)
	if current_render_mode == "portrait_billboard" and portrait_texture != null:
		_draw_portrait_billboard_preview(portrait_texture, center)
	elif current_render_mode in ["auto", "sprite_sheet"] and bool(visual.get("use_sprite_sheet")) and texture != null:
		_draw_sprite_preview(texture, center)
	else:
		_draw_fallback(center)
	_draw_portrait_preview()
	draw_string(
		ThemeDB.fallback_font,
		Vector2(14, size.y - 16),
		"%s • %s • %s" % [String(visual.get("display_name")), state.to_upper(), direction.to_upper()],
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		14,
		Color("#dce8f5")
	)


func _draw_portrait_billboard_preview(texture: Texture2D, center: Vector2) -> void:
	var source_size: Vector2 = texture.get_size()
	if source_size.x <= 0.0 or source_size.y <= 0.0:
		return
	var max_size: Vector2 = Vector2(270.0, 270.0)
	var ratio: float = minf(max_size.x / source_size.x, max_size.y / source_size.y)
	var dest_size: Vector2 = source_size * ratio
	var raw_offset: Variant = visual.get("sprite_offset")
	var offset: Vector2 = raw_offset if raw_offset is Vector2 else Vector2.ZERO
	# Runtime offsets are authored for 192px tactical cells. Keep only a
	# softened preview offset so the editor remains easy to read.
	offset *= 0.35
	var dest: Rect2 = Rect2(center - dest_size * 0.5 + offset, dest_size)
	draw_texture_rect(texture, dest, false)
	draw_rect(dest, Color(1, 1, 1, 0.18), false, 1.0)


func _draw_sprite_preview(texture: Texture2D, center: Vector2) -> void:
	var fw: int = int(visual.get("frame_width"))
	var fh: int = int(visual.get("frame_height"))
	if fw <= 0 or fh <= 0:
		fw = int(texture.get_size().x)
		fh = int(texture.get_size().y)
	var coords: Vector2i = Vector2i.ZERO
	if visual.has_method("atlas_frame_coordinates"):
		var coords_value: Variant = visual.call(
			"atlas_frame_coordinates",
			state,
			elapsed,
			direction,
			Vector2i(roundi(texture.get_size().x), roundi(texture.get_size().y))
		)
		if coords_value is Vector2i:
			coords = coords_value
	else:
		var per_row: int = maxi(1, floori(texture.get_size().x / float(maxi(1, fw))))
		var frame: int = int(visual.call("frame_index", state, elapsed))
		coords = Vector2i(frame % per_row, floori(float(frame) / float(per_row)))
	var src: Rect2 = Rect2(coords.x * fw, coords.y * fh, fw, fh)
	var scale_value: float = float(visual.get("sprite_scale"))
	var dest_size: Vector2 = Vector2(fw, fh) * scale_value
	var raw_offset: Variant = visual.get("sprite_offset")
	var offset: Vector2 = raw_offset if raw_offset is Vector2 else Vector2.ZERO
	var dest: Rect2 = Rect2(center - dest_size * 0.5 + offset, dest_size)
	var sprite_modulate: Color = visual.get("primary_color") if bool(visual.get("tint_sprite_with_primary")) else Color.WHITE
	var flip: bool = bool(visual.get("flip_with_facing")) and direction in ["left", "front_left", "back_left"]
	if flip:
		var flipped_src: Rect2 = Rect2(src.position.x + src.size.x, src.position.y, -src.size.x, src.size.y)
		draw_texture_rect_region(texture, dest, flipped_src, sprite_modulate)
	else:
		draw_texture_rect_region(texture, dest, src, sprite_modulate)
	draw_rect(dest, Color(1, 1, 1, 0.18), false, 1.0)


func _draw_fallback(center: Vector2) -> void:
	var primary: Color = visual.get("primary_color")
	var secondary: Color = visual.get("secondary_color")
	var accent: Color = visual.get("accent_color")
	var outline: Color = visual.get("outline_color")
	var pulse: float = sin(elapsed * 3.0) * 2.0 if state == "idle" else 0.0
	var attack_shift: Vector2 = Vector2(18.0 * sin(minf(1.0, elapsed * 5.0) * PI), 0.0) if state == "attack" else Vector2.ZERO
	var cast_lift: Vector2 = Vector2(0.0, -8.0 * sin(minf(1.0, elapsed * 4.0) * PI)) if state == "cast" else Vector2.ZERO
	center += attack_shift + cast_lift
	match String(visual.get("fallback_shape")):
		"slime":
			draw_circle(center + Vector2(0, 12), 32 + pulse, outline)
			draw_circle(center + Vector2(0, 10), 28 + pulse, primary)
		"armored":
			draw_circle(center, 35 + pulse, outline)
			draw_rect(Rect2(center + Vector2(-27, -18), Vector2(54, 52)), primary, true)
			draw_circle(center + Vector2(0, -20), 27, secondary)
		"orb":
			draw_circle(center, 38 + pulse, Color(primary.r, primary.g, primary.b, 0.18))
			draw_circle(center, 28 + pulse, outline)
			draw_circle(center, 23 + pulse, primary)
		_:
			draw_rect(Rect2(center + Vector2(-15, 2), Vector2(30, 38)), secondary, true)
			draw_circle(center + Vector2(0, 36), 15, secondary)
			draw_circle(center + Vector2(0, -7), 34 + pulse, outline)
			draw_circle(center + Vector2(0, -11), 30 + pulse, primary)
	if direction == "back":
		draw_circle(center + Vector2(-10, -13), 4, accent)
		draw_circle(center + Vector2(10, -13), 4, accent)
	elif direction in ["left", "front_left", "back_left"]:
		draw_circle(center + Vector2(-8, -5), 4, outline)
	elif direction in ["right", "front_right", "back_right"]:
		draw_circle(center + Vector2(8, -5), 4, outline)
	else:
		draw_circle(center + Vector2(-9, -7), 3, outline)
		draw_circle(center + Vector2(9, -7), 3, outline)
	if state == "hit":
		draw_circle(center, 45, Color(1, 1, 1, 0.22))
	if state == "ko":
		draw_line(center + Vector2(-25, -25), center + Vector2(25, 25), accent, 5)
		draw_line(center + Vector2(25, -25), center + Vector2(-25, 25), accent, 5)


func _draw_portrait_preview() -> void:
	var portrait: Texture2D = _texture(String(visual.get("portrait_path")), true)
	var rect: Rect2 = Rect2(size.x - 126, 18, 108, 108)
	draw_rect(rect, Color("#202d42"), true)
	draw_rect(rect, Color("#506a84"), false, 2.0)
	if portrait != null:
		draw_texture_rect(portrait, rect.grow(-5), false)
	else:
		draw_string(ThemeDB.fallback_font, rect.position + Vector2(18, 58), "PORTRAIT", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color("#90a4b8"))
