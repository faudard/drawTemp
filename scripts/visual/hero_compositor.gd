@tool
class_name SporeHeroCompositor
extends RefCounted

const PART_ROOT := "res://assets/hero_parts/"
const VISUAL_DIR := "res://data/visuals/units/"
const FRAME_SIZE := Vector2i(192, 192)
const DIRECTIONS := ["front", "right", "back", "left"]
const STATES := ["idle", "move", "attack", "cast", "hit", "ko"]
const EDIT_GROUPS := ["body", "head", "face", "accessory", "weapon"]
const LAYER_ORDER := [
	"body",
	"bottom",
	"top",
	"jewelry",
	"ears",
	"head_shape",
	"head_pattern",
	"skin_spots",
	"horns",
	"hair",
	"eyes",
	"iris",
	"pupil",
	"brows",
	"nose",
	"mouth",
	"teeth",
	"facial_hair",
	"mark",
	"mark_2",
	"mark_3",
	"earrings",
	"accessory",
	"accessory_2",
	"accessory_3",
	"weapon",
]
const HEAD_CATEGORIES := ["ears", "head_shape", "head_pattern", "skin_spots", "horns", "hair", "eyes", "iris", "pupil", "brows", "nose", "mouth", "teeth", "facial_hair", "mark", "mark_2", "mark_3", "earrings"]
const FACE_CATEGORIES := ["skin_spots", "eyes", "iris", "pupil", "brows", "nose", "mouth", "teeth", "facial_hair", "mark", "mark_2", "mark_3", "earrings"]
const BODY_CATEGORIES := ["body", "bottom", "top"]
const HEAD_ANCHOR := Vector2(96.0, 86.0)
const BODY_ANCHOR := Vector2(96.0, 145.0)
const ACCESSORY_ANCHOR := Vector2(96.0, 112.0)
const WEAPON_ANCHOR := Vector2(96.0, 128.0)
const GLOBAL_ANCHOR := Vector2(96.0, 126.0)
static var _thumbnail_cache: Dictionary = {}


static func part_path(category: String, part_id: String, direction: String) -> String:
	if part_id.is_empty():
		return ""
	var directional_path: String = "%s%s/%s_%s.png" % [PART_ROOT, category, part_id, direction]
	if FileAccess.file_exists(directional_path):
		return directional_path
	var fallback_path: String = "%s%s/%s.png" % [PART_ROOT, category, part_id]
	if FileAccess.file_exists(fallback_path):
		return fallback_path
	return ""


static func compose_part_thumbnail(category: String, part_id: String, direction: String = "front", tint: Color = Color.WHITE) -> Image:
	var cache_key: String = "%s|%s|%s|%s" % [category, part_id, direction, tint.to_html(true)]
	if _thumbnail_cache.has(cache_key):
		var cached: Variant = _thumbnail_cache[cache_key]
		if cached is Image:
			return (cached as Image).duplicate()
	var thumbnail: Image = Image.create(96, 96, false, Image.FORMAT_RGBA8)
	thumbnail.fill(Color(0.0, 0.0, 0.0, 0.0))
	if part_id.is_empty() or part_id == "none":
		_thumbnail_cache[cache_key] = thumbnail.duplicate()
		return thumbnail
	var path: String = part_path(category, part_id, direction)
	if path.is_empty():
		return thumbnail
	var source: Image = _load_image(path)
	if source == null:
		return thumbnail
	var tinted: Image = _tint_image(source, tint)
	tinted.resize(96, 96, Image.INTERPOLATE_LANCZOS)
	_thumbnail_cache[cache_key] = tinted.duplicate()
	return tinted


static func available_part_ids(category: String) -> PackedStringArray:
	var ids: Dictionary = {}
	var directory_path: String = PART_ROOT + category + "/"
	var directory: DirAccess = DirAccess.open(directory_path)
	if directory == null:
		return PackedStringArray()
	for file_name: String in directory.get_files():
		if not file_name.to_lower().ends_with(".png"):
			continue
		var base_name: String = file_name.get_basename()
		for direction: String in DIRECTIONS:
			var suffix: String = "_" + direction
			if base_name.ends_with(suffix):
				base_name = base_name.left(base_name.length() - suffix.length())
				break
		if not base_name.is_empty():
			ids[base_name] = true
	var result: PackedStringArray = PackedStringArray()
	for key: Variant in ids.keys():
		result.append(String(key))
	result.sort()
	return result


static func compose_frame(appearance: Resource, direction: String = "front", state: String = "idle") -> Image:
	var output: Image = _blank_frame()
	if appearance == null:
		return output
	_prepare_appearance(appearance)
	for category: String in LAYER_ORDER:
		var layer: Image = _compose_category(appearance, category, direction, state)
		if layer == null:
			continue
		output.blend_rect(layer, Rect2i(Vector2i.ZERO, layer.get_size()), Vector2i.ZERO)
	return _apply_global_render(output, appearance)


static func compose_edit_group(appearance: Resource, edit_group: String, direction: String = "front", state: String = "idle") -> Image:
	var output: Image = _blank_frame()
	if appearance == null or not EDIT_GROUPS.has(edit_group):
		return output
	_prepare_appearance(appearance)
	for category: String in LAYER_ORDER:
		if edit_group_for_category(category) != edit_group:
			continue
		var layer: Image = _compose_category(appearance, category, direction, state)
		if layer == null:
			continue
		output.blend_rect(layer, Rect2i(Vector2i.ZERO, layer.get_size()), Vector2i.ZERO)
	return _apply_global_render(output, appearance)


static func edit_group_bounds(appearance: Resource, edit_group: String, direction: String = "front", state: String = "idle") -> Rect2:
	var image: Image = compose_edit_group(appearance, edit_group, direction, state)
	var min_x: int = FRAME_SIZE.x
	var min_y: int = FRAME_SIZE.y
	var max_x: int = -1
	var max_y: int = -1
	for y: int in range(FRAME_SIZE.y):
		for x: int in range(FRAME_SIZE.x):
			if image.get_pixel(x, y).a <= 0.02:
				continue
			min_x = mini(min_x, x)
			min_y = mini(min_y, y)
			max_x = maxi(max_x, x)
			max_y = maxi(max_y, y)
	if max_x < min_x or max_y < min_y:
		return Rect2()
	return Rect2(float(min_x), float(min_y), float(max_x - min_x + 1), float(max_y - min_y + 1))


static func edit_group_for_category(category: String) -> String:
	if BODY_CATEGORIES.has(category):
		return "body"
	if HEAD_CATEGORIES.has(category) and not FACE_CATEGORIES.has(category):
		return "head"
	if FACE_CATEGORIES.has(category):
		return "face"
	if category in ["jewelry", "accessory", "accessory_2", "accessory_3"]:
		return "accessory"
	if category == "weapon":
		return "weapon"
	return ""


static func edit_group_anchor(edit_group: String) -> Vector2:
	match edit_group:
		"body": return BODY_ANCHOR
		"head", "face": return HEAD_ANCHOR
		"accessory": return ACCESSORY_ANCHOR
		"weapon": return WEAPON_ANCHOR
		_: return GLOBAL_ANCHOR


static func compose_atlas(appearance: Resource) -> Image:
	var atlas_size: Vector2i = Vector2i(FRAME_SIZE.x * STATES.size(), FRAME_SIZE.y * DIRECTIONS.size())
	var atlas: Image = Image.create(atlas_size.x, atlas_size.y, false, Image.FORMAT_RGBA8)
	atlas.fill(Color(0.0, 0.0, 0.0, 0.0))
	for row: int in range(DIRECTIONS.size()):
		var direction: String = DIRECTIONS[row]
		for column: int in range(STATES.size()):
			var state: String = STATES[column]
			var state_frame: Image = compose_frame(appearance, direction, state)
			var destination: Vector2i = Vector2i(column * FRAME_SIZE.x, row * FRAME_SIZE.y)
			var offset: Vector2i = _state_offset(state, direction)
			atlas.blend_rect(state_frame, Rect2i(Vector2i.ZERO, FRAME_SIZE), destination + offset)
	return atlas


static func save_generated_assets(appearance: Resource) -> Dictionary:
	var result: Dictionary = {"ok": false, "errors": PackedStringArray()}
	if appearance == null:
		result["errors"] = PackedStringArray(["Apparence absente"])
		return result
	var sheet_path: String = String(appearance.get("generated_sprite_sheet_path"))
	var portrait_path: String = String(appearance.get("generated_portrait_path"))
	if sheet_path.is_empty() or portrait_path.is_empty():
		result["errors"] = PackedStringArray(["Chemins de sortie invalides"])
		return result
	var errors: PackedStringArray = PackedStringArray()
	_ensure_parent_directory(sheet_path)
	_ensure_parent_directory(portrait_path)
	var atlas: Image = compose_atlas(appearance)
	var sheet_error: Error = atlas.save_png(ProjectSettings.globalize_path(sheet_path))
	if sheet_error != OK:
		errors.append("Impossible d'écrire %s (erreur %d)" % [sheet_path, int(sheet_error)])
	var portrait_direction: String = _string_property(appearance, "portrait_direction", "front")
	if not DIRECTIONS.has(portrait_direction):
		portrait_direction = "front"
	var portrait: Image = compose_frame(appearance, portrait_direction, "portrait")
	var portrait_zoom: float = _float_property(appearance, "portrait_zoom", 1.0)
	if not is_equal_approx(portrait_zoom, 1.0):
		portrait = _scale_about_anchor(portrait, Vector2(portrait_zoom, portrait_zoom), HEAD_ANCHOR)
	portrait = _offset_image(portrait, _vector2_property(appearance, "portrait_offset"))
	var portrait_error: Error = portrait.save_png(ProjectSettings.globalize_path(portrait_path))
	if portrait_error != OK:
		errors.append("Impossible d'écrire %s (erreur %d)" % [portrait_path, int(portrait_error)])
	result["ok"] = errors.is_empty()
	result["errors"] = errors
	result["sheet_path"] = sheet_path
	result["portrait_path"] = portrait_path
	return result


static func apply_to_visual(appearance: Resource) -> Dictionary:
	var generated: Dictionary = save_generated_assets(appearance)
	if not bool(generated.get("ok", false)):
		return generated
	var visual_id: String = String(appearance.get("target_visual_id"))
	if visual_id.is_empty():
		visual_id = String(appearance.get("hero_id"))
	var visual_path: String = VISUAL_DIR + visual_id + ".tres"
	if not ResourceLoader.exists(visual_path):
		var errors: PackedStringArray = PackedStringArray(["VisualDefinition introuvable : %s" % visual_path])
		generated["ok"] = false
		generated["errors"] = errors
		return generated
	var visual: Resource = load(visual_path)
	if visual == null:
		var load_errors: PackedStringArray = PackedStringArray(["Impossible de charger %s" % visual_path])
		generated["ok"] = false
		generated["errors"] = load_errors
		return generated
	visual.set("portrait_path", String(generated.get("portrait_path", "")))
	visual.set("sprite_sheet_path", String(generated.get("sheet_path", "")))
	visual.set("use_sprite_sheet", true)
	visual.set("frame_width", FRAME_SIZE.x)
	visual.set("frame_height", FRAME_SIZE.y)
	visual.set("sprite_scale", float(appearance.get("sprite_scale")))
	var raw_offset: Variant = appearance.get("sprite_offset")
	visual.set("sprite_offset", raw_offset if raw_offset is Vector2 else Vector2.ZERO)
	visual.set("flip_with_facing", false)
	visual.set("direction_mode", "4_way")
	visual.set("direction_layout", "rows")
	visual.set("direction_stride_frames", 0)
	visual.set("four_direction_order", "front,right,back,left")
	visual.set("tint_sprite_with_primary", false)
	visual.set("primary_color", appearance.get("head_primary_color"))
	visual.set("secondary_color", appearance.get("skin_color"))
	visual.set("accent_color", appearance.get("head_secondary_color"))
	visual.set("outline_color", appearance.get("outline_color"))
	for index: int in range(STATES.size()):
		var state: String = STATES[index]
		visual.set(state + "_start", index)
		visual.set(state + "_count", 1)
		visual.set(state + "_loop", state in ["idle", "move"])
	var save_error: Error = ResourceSaver.save(visual, visual_path)
	if save_error != OK:
		var save_errors: PackedStringArray = PackedStringArray(["Impossible de sauver %s (erreur %d)" % [visual_path, int(save_error)]])
		generated["ok"] = false
		generated["errors"] = save_errors
		return generated
	generated["visual_path"] = visual_path
	return generated


static func _prepare_appearance(appearance: Resource) -> void:
	if appearance.has_method("migrate_legacy_fields"):
		appearance.call("migrate_legacy_fields")


static func _blank_frame() -> Image:
	var image: Image = Image.create(FRAME_SIZE.x, FRAME_SIZE.y, false, Image.FORMAT_RGBA8)
	image.fill(Color(0.0, 0.0, 0.0, 0.0))
	return image


static func _compose_category(appearance: Resource, category: String, direction: String, state: String = "idle") -> Image:
	var part_id_value: Variant = appearance.call("directional_part_id", category, direction) if appearance.has_method("directional_part_id") else appearance.call("part_id", category)
	var part_id: String = String(part_id_value)
	if FACE_CATEGORIES.has(category) and appearance.has_method("expression_for_state") and appearance.has_method("expression_part_override"):
		var expression: String = String(appearance.call("expression_for_state", state))
		var override_id: String = String(appearance.call("expression_part_override", category, expression))
		if not override_id.is_empty():
			part_id = override_id
	if part_id.is_empty() or part_id == "none":
		return null
	var path: String = part_path(category, part_id, direction)
	if path.is_empty():
		return null
	var source: Image = _load_image(path)
	if source == null:
		return null
	var tint_value: Variant = appearance.call("part_color", category)
	var tint: Color = tint_value if tint_value is Color else Color.WHITE
	return _transform_part(_tint_image(source, tint), category, appearance)


static func _apply_global_render(source: Image, appearance: Resource) -> Image:
	var output: Image = source
	var global_factor: float = _size_preset_factor(String(appearance.get("size_preset"))) * float(appearance.get("global_scale"))
	if not is_equal_approx(global_factor, 1.0):
		output = _scale_about_anchor(output, Vector2(global_factor, global_factor), GLOBAL_ANCHOR)
	var global_tint_value: Variant = appearance.get("global_tint")
	if global_tint_value is Color:
		var global_tint: Color = global_tint_value
		output = _multiply_image(output, global_tint)
	return output


static func _transform_part(source: Image, category: String, appearance: Resource) -> Image:
	var transformed: Image = source
	var scale: Vector2 = Vector2.ONE
	var rotation_degrees: float = 0.0
	var anchor: Vector2 = GLOBAL_ANCHOR
	if HEAD_CATEGORIES.has(category):
		var head_scale: float = float(appearance.get("head_scale"))
		var head_width_scale: float = float(appearance.get("head_width_scale"))
		var head_direct_scale: float = _float_property(appearance, "head_transform_scale", 1.0)
		scale = Vector2(head_scale * head_width_scale * head_direct_scale, head_scale * head_direct_scale)
		rotation_degrees = _float_property(appearance, "head_rotation_degrees", 0.0)
		anchor = HEAD_ANCHOR
		if FACE_CATEGORIES.has(category):
			var face_direct_scale: float = _float_property(appearance, "face_transform_scale", 1.0)
			scale *= face_direct_scale
			rotation_degrees += _float_property(appearance, "face_rotation_degrees", 0.0)
	elif BODY_CATEGORIES.has(category):
		var body_width: float = float(appearance.get("body_width_scale"))
		var body_height: float = float(appearance.get("body_height_scale"))
		var body_direct_scale: float = _float_property(appearance, "body_transform_scale", 1.0)
		scale = Vector2(body_width * body_direct_scale, body_height * body_direct_scale)
		rotation_degrees = _float_property(appearance, "body_rotation_degrees", 0.0)
		anchor = BODY_ANCHOR
	elif category in ["jewelry", "accessory", "accessory_2", "accessory_3"]:
		var accessory_scale: float = _float_property(appearance, "accessory_transform_scale", 1.0)
		scale = Vector2(accessory_scale, accessory_scale)
		rotation_degrees = _float_property(appearance, "accessory_rotation_degrees", 0.0)
		anchor = ACCESSORY_ANCHOR
	elif category == "weapon":
		var weapon_scale: float = _float_property(appearance, "weapon_transform_scale", 1.0)
		scale = Vector2(weapon_scale, weapon_scale)
		rotation_degrees = _float_property(appearance, "weapon_rotation_degrees", 0.0)
		anchor = WEAPON_ANCHOR
	if not scale.is_equal_approx(Vector2.ONE):
		transformed = _scale_about_anchor(transformed, scale, anchor)
	if not is_zero_approx(rotation_degrees):
		transformed = _rotate_about_anchor(transformed, rotation_degrees, anchor)
	return _offset_image(transformed, _category_offset(category, appearance))


static func _category_offset(category: String, appearance: Resource) -> Vector2:
	var body_offset: Vector2 = _vector2_property(appearance, "body_offset")
	var head_offset: Vector2 = _vector2_property(appearance, "head_offset")
	if FACE_CATEGORIES.has(category):
		return head_offset + _vector2_property(appearance, "face_offset")
	if HEAD_CATEGORIES.has(category):
		return head_offset
	if BODY_CATEGORIES.has(category):
		return body_offset
	if category in ["jewelry", "accessory", "accessory_2", "accessory_3"]:
		return _vector2_property(appearance, "accessory_offset")
	if category == "weapon":
		return _vector2_property(appearance, "weapon_offset")
	return Vector2.ZERO


static func _float_property(appearance: Resource, property_name: String, fallback: float) -> float:
	var value: Variant = appearance.get(property_name)
	if value == null:
		return fallback
	return float(value)


static func _string_property(appearance: Resource, property_name: String, fallback: String) -> String:
	var value: Variant = appearance.get(property_name)
	if value == null:
		return fallback
	var result: String = String(value)
	return fallback if result.is_empty() else result


static func _vector2_property(appearance: Resource, property_name: String) -> Vector2:
	var value: Variant = appearance.get(property_name)
	return value if value is Vector2 else Vector2.ZERO


static func _offset_image(source: Image, offset: Vector2) -> Image:
	if offset.is_equal_approx(Vector2.ZERO):
		return source
	var output: Image = _blank_frame()
	var destination: Vector2i = Vector2i(int(round(offset.x)), int(round(offset.y)))
	output.blend_rect(source, Rect2i(Vector2i.ZERO, source.get_size()), destination)
	return output


static func _scale_about_anchor(source: Image, scale: Vector2, anchor: Vector2) -> Image:
	if is_equal_approx(scale.x, 1.0) and is_equal_approx(scale.y, 1.0):
		return source
	var scaled_width: int = maxi(1, int(round(float(FRAME_SIZE.x) * scale.x)))
	var scaled_height: int = maxi(1, int(round(float(FRAME_SIZE.y) * scale.y)))
	var scaled: Image = source.duplicate()
	scaled.resize(scaled_width, scaled_height, Image.INTERPOLATE_LANCZOS)
	var output: Image = _blank_frame()
	var destination_f: Vector2 = anchor - Vector2(anchor.x * scale.x, anchor.y * scale.y)
	var destination: Vector2i = Vector2i(int(round(destination_f.x)), int(round(destination_f.y)))
	output.blend_rect(scaled, Rect2i(Vector2i.ZERO, scaled.get_size()), destination)
	return output


static func _rotate_about_anchor(source: Image, degrees: float, anchor: Vector2) -> Image:
	if is_zero_approx(degrees):
		return source
	var output: Image = _blank_frame()
	var radians: float = deg_to_rad(degrees)
	var cosine: float = cos(radians)
	var sine: float = sin(radians)
	for y: int in range(FRAME_SIZE.y):
		for x: int in range(FRAME_SIZE.x):
			var relative: Vector2 = Vector2(float(x), float(y)) - anchor
			var source_point: Vector2 = Vector2(
				cosine * relative.x + sine * relative.y,
				-sine * relative.x + cosine * relative.y
			) + anchor
			var source_x: int = int(round(source_point.x))
			var source_y: int = int(round(source_point.y))
			if source_x < 0 or source_x >= FRAME_SIZE.x or source_y < 0 or source_y >= FRAME_SIZE.y:
				continue
			var pixel: Color = source.get_pixel(source_x, source_y)
			if pixel.a > 0.001:
				output.set_pixel(x, y, pixel)
	return output


static func _size_preset_factor(size_preset: String) -> float:
	match size_preset:
		"small": return 0.88
		"large": return 1.12
		_: return 1.0


static func _state_offset(state: String, direction: String) -> Vector2i:
	var horizontal_sign: int = -1 if direction == "left" else 1
	match state:
		"move": return Vector2i(0, -3)
		"attack": return Vector2i(5 * horizontal_sign, 0)
		"cast": return Vector2i(0, -6)
		"hit": return Vector2i(-3 * horizontal_sign, 1)
		"ko": return Vector2i(0, 10)
		_: return Vector2i.ZERO


static func _load_image(resource_path: String) -> Image:
	var absolute_path: String = ProjectSettings.globalize_path(resource_path)
	if not FileAccess.file_exists(resource_path) and not FileAccess.file_exists(absolute_path):
		return null
	var loaded: Image = Image.load_from_file(absolute_path)
	if loaded == null or loaded.is_empty():
		return null
	if loaded.get_size() != FRAME_SIZE:
		loaded.resize(FRAME_SIZE.x, FRAME_SIZE.y, Image.INTERPOLATE_LANCZOS)
	loaded.convert(Image.FORMAT_RGBA8)
	return loaded


static func _tint_image(source: Image, tint: Color) -> Image:
	var image: Image = source.duplicate()
	image.convert(Image.FORMAT_RGBA8)
	var width: int = image.get_width()
	var height: int = image.get_height()
	for y: int in range(height):
		for x: int in range(width):
			var pixel: Color = image.get_pixel(x, y)
			if pixel.a <= 0.001:
				continue
			var luminance: float = maxf(pixel.r, maxf(pixel.g, pixel.b))
			var tinted: Color = Color(tint.r * luminance, tint.g * luminance, tint.b * luminance, pixel.a * tint.a)
			image.set_pixel(x, y, tinted)
	return image


static func _multiply_image(source: Image, tint: Color) -> Image:
	if tint.is_equal_approx(Color.WHITE):
		return source
	var image: Image = source.duplicate()
	image.convert(Image.FORMAT_RGBA8)
	var width: int = image.get_width()
	var height: int = image.get_height()
	for y: int in range(height):
		for x: int in range(width):
			var pixel: Color = image.get_pixel(x, y)
			if pixel.a <= 0.001:
				continue
			image.set_pixel(x, y, Color(pixel.r * tint.r, pixel.g * tint.g, pixel.b * tint.b, pixel.a * tint.a))
	return image


static func _ensure_parent_directory(resource_path: String) -> void:
	var absolute_path: String = ProjectSettings.globalize_path(resource_path)
	var parent: String = absolute_path.get_base_dir()
	if not DirAccess.dir_exists_absolute(parent):
		DirAccess.make_dir_recursive_absolute(parent)
