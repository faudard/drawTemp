@tool
class_name SporeVfxPreview
extends Control

var definition: Resource = null
var elapsed := 0.0
var _texture_path := ""
var _texture: Texture2D = null


func _ready() -> void:
	custom_minimum_size = Vector2(420, 260)
	set_process(true)


func set_definition(value: Resource) -> void:
	definition = value
	elapsed = 0.0
	_texture_path = ""
	_texture = null
	queue_redraw()


func _process(delta: float) -> void:
	elapsed += delta
	if definition != null and elapsed > max(0.1, float(definition.duration)):
		elapsed = 0.0
	queue_redraw()


func _load_texture() -> Texture2D:
	if definition == null:
		return null
	var path := String(definition.texture_path)
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	if _texture_path == path and _texture != null:
		return _texture
	var loaded = load(path)
	_texture_path = path
	_texture = loaded if loaded is Texture2D else null
	return _texture


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color("#111925"), true)
	if definition == null:
		return
	var duration: float = maxf(0.05, float(definition.duration))
	var progress := clampf(elapsed / duration, 0.0, 1.0)
	var center := size * 0.5
	var primary: Color = definition.primary_color
	var secondary: Color = definition.secondary_color
	var radius := float(definition.radius)
	var kind := String(definition.kind)
	match kind:
		"projectile":
			var from := Vector2(45, center.y)
			var to := Vector2(size.x - 45, center.y)
			var pos := from.lerp(to, progress)
			draw_line(from.lerp(to, max(0.0, progress - 0.2)), pos, Color(primary.r, primary.g, primary.b, 0.55), float(definition.trail_width), true)
			draw_circle(pos, 8, primary)
			draw_circle(pos, 3, secondary)
		"aura":
			draw_arc(center, radius + sin(progress * TAU) * 5, 0, TAU, 48, Color(primary.r, primary.g, primary.b, 0.75), 4, true)
			draw_circle(center, radius * 0.65, Color(primary.r, primary.g, primary.b, 0.12))
		"ring":
			draw_arc(center, radius * (0.55 + progress * 0.65), 0, TAU, 48, Color(primary.r, primary.g, primary.b, 1.0 - progress), 5, true)
		"cross":
			var extent := radius * (0.5 + progress * 0.5)
			draw_line(center - Vector2(extent, 0), center + Vector2(extent, 0), primary, 7, true)
			draw_line(center - Vector2(0, extent), center + Vector2(0, extent), secondary, 5, true)
		"slash":
			var angle := -1.1 + progress * 2.2
			draw_arc(center, radius, angle - 0.6, angle + 0.6, 16, primary, 7, true)
		_:
			draw_circle(center, radius * (0.4 + progress * 0.7), Color(primary.r, primary.g, primary.b, 0.45 * (1.0 - progress)))
			draw_arc(center, radius * (0.5 + progress * 0.55), 0, TAU, 40, primary, 4, true)
	var texture := _load_texture()
	if texture != null:
		var fw := int(definition.frame_width)
		var fh := int(definition.frame_height)
		if fw <= 0 or fh <= 0:
			fw = int(texture.get_size().x)
			fh = int(texture.get_size().y)
		var per_row: int = maxi(1, int(texture.get_size().x) / maxi(1, fw))
		var frame := int(definition.frame_index(elapsed))
		var src := Rect2((frame % per_row) * fw, int(frame / per_row) * fh, fw, fh)
		var dest_size := Vector2(fw, fh) * float(definition.texture_scale)
		var dest := Rect2(center - dest_size * 0.5, dest_size)
		draw_texture_rect_region(texture, dest, src, Color.WHITE)
	draw_string(ThemeDB.fallback_font, Vector2(14, size.y - 14), "%s • %s" % [String(definition.display_name), kind], HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color("#dce8f5"))
