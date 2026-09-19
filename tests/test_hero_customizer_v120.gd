extends SceneTree

const AppearanceDefinition = preload("res://scripts/data/hero_appearance_definition.gd")
const HeroCompositor = preload("res://scripts/visual/hero_compositor.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	test_advanced_part_library()
	test_two_color_head()
	test_morphology()
	test_legacy_migration()
	if failures.is_empty():
		print("[V1.20] Hero Creator Advanced smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_advanced_part_library() -> void:
	for category: String in ["body", "head_shape", "head_pattern", "eyes", "mouth", "facial_hair", "mark", "top", "bottom", "accessory", "weapon"]:
		var ids: PackedStringArray = HeroCompositor.available_part_ids(category)
		expect(not ids.is_empty(), "advanced hero part category must not be empty: %s" % category)
	expect(HeroCompositor.available_part_ids("head_shape").has("mutant"), "mutant head shape available")
	expect(HeroCompositor.available_part_ids("eyes").has("robotic"), "robotic eyes available")
	expect(HeroCompositor.available_part_ids("facial_hair").has("long_beard"), "long beard available")
	expect(HeroCompositor.available_part_ids("mark").has("scar_left"), "scar available")


func test_two_color_head() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	appearance.head_shape_style = "round"
	appearance.head_pattern_style = "spots"
	appearance.head_primary_color = Color("#ff0000")
	appearance.head_secondary_color = Color("#ffff00")
	var first: Image = HeroCompositor.compose_frame(appearance, "front")
	appearance.head_secondary_color = Color("#00ffff")
	var second: Image = HeroCompositor.compose_frame(appearance, "front")
	expect(first.get_data() != second.get_data(), "second head color changes the composed frame")


func test_morphology() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	appearance.head_shape_style = "wide"
	appearance.head_width_scale = 0.75
	var narrow: Image = HeroCompositor.compose_frame(appearance, "front")
	appearance.head_width_scale = 1.45
	var wide: Image = HeroCompositor.compose_frame(appearance, "front")
	expect(narrow.get_data() != wide.get_data(), "head width morph changes output")
	appearance.size_preset = "small"
	var small_rect: Rect2i = HeroCompositor.compose_frame(appearance, "front").get_used_rect()
	appearance.size_preset = "large"
	var large_rect: Rect2i = HeroCompositor.compose_frame(appearance, "front").get_used_rect()
	expect(large_rect.size.y >= small_rect.size.y, "large preset is not visually smaller than small preset")


func test_legacy_migration() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	appearance.cap_style = "royal"
	appearance.face_style = "cyclops"
	appearance.migrate_legacy_fields()
	expect(appearance.head_shape_style == "noble", "legacy royal cap migrates to noble head")
	expect(appearance.eyes_style == "cyclops", "legacy cyclops face migrates to cyclops eyes")
