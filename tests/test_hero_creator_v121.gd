extends SceneTree

const AppearanceDefinition = preload("res://scripts/data/hero_appearance_definition.gd")
const Compositor = preload("res://scripts/visual/hero_compositor.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	test_part_thumbnails()
	test_fine_offsets()
	test_starter_presets()
	if failures.is_empty():
		print("[V1.21] Hero Creator Pro smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_part_thumbnails() -> void:
	var image: Image = Compositor.compose_part_thumbnail("head_shape", "noble", "front", Color.WHITE)
	expect(image.get_size() == Vector2i(96, 96), "part thumbnails stay 96x96")
	expect(image.detect_alpha() != Image.ALPHA_NONE, "thumbnail keeps transparency")


func test_fine_offsets() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	appearance.head_shape_style = "pointed"
	appearance.eyes_style = "big"
	appearance.face_offset = Vector2.ZERO
	var centered: Image = Compositor.compose_frame(appearance, "front")
	appearance.face_offset = Vector2(7, -5)
	var shifted: Image = Compositor.compose_frame(appearance, "front")
	expect(centered.get_data() != shifted.get_data(), "face offset changes composed output")
	appearance.face_offset = Vector2.ZERO
	appearance.weapon_offset = Vector2(8, 3)
	var weapon_shifted: Image = Compositor.compose_frame(appearance, "front")
	expect(centered.get_data() != weapon_shifted.get_data(), "weapon offset changes composed output")


func test_starter_presets() -> void:
	var paths: PackedStringArray = PackedStringArray([
		"res://data/hero_presets/royal_scarlet.tres",
		"res://data/hero_presets/mystic_violet.tres",
		"res://data/hero_presets/forest_scout.tres",
	])
	for path: String in paths:
		expect(ResourceLoader.exists(path), "starter preset exists: %s" % path)
		var preset: Resource = load(path)
		expect(preset != null, "starter preset loads: %s" % path)
		if preset != null:
			expect(not String(preset.get("head_shape_style")).is_empty(), "preset has a head shape: %s" % path)
