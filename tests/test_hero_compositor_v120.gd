extends SceneTree

const AppearanceDefinition = preload("res://scripts/data/hero_appearance_definition.gd")
const HeroCompositor = preload("res://scripts/visual/hero_compositor.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	appearance.head_shape_style = "mutant"
	appearance.head_pattern_style = "dense_spots"
	appearance.eyes_style = "cyclops"
	appearance.mouth_style = "fang"
	appearance.facial_hair_style = "moss_beard"
	appearance.mark_style = "crack"
	appearance.head_scale = 1.15
	appearance.head_width_scale = 1.20
	for direction: String in HeroCompositor.DIRECTIONS:
		var frame: Image = HeroCompositor.compose_frame(appearance, direction)
		expect(frame.get_size() == HeroCompositor.FRAME_SIZE, "frame size stays 192x192 for %s" % direction)
		expect(frame.detect_alpha() != Image.ALPHA_NONE, "frame keeps alpha for %s" % direction)
	var atlas: Image = HeroCompositor.compose_atlas(appearance)
	expect(atlas.get_size() == Vector2i(1152, 768), "atlas remains 6 states x 4 directions")
	if failures.is_empty():
		print("[V1.20] Hero compositor morphology test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
