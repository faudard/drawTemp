extends SceneTree

const Appearance = preload("res://scripts/data/hero_appearance_definition.gd")
const HeroCompositor = preload("res://scripts/visual/hero_compositor.gd")

func _init() -> void:
	var kits: PackedStringArray = HeroCompositor.available_kit_ids()
	assert(kits.has("forest_scout"))
	var appearance: Resource = Appearance.new()
	appearance.set("authoring_mode", "guided")
	appearance.set("library_kit_id", "forest_scout")
	appearance.set("guided_apply_global_tint", false)
	assert(bool(appearance.call("is_guided_mode")))
	for direction: String in HeroCompositor.DIRECTIONS:
		var frame: Image = HeroCompositor.compose_frame(appearance, direction, "idle")
		assert(frame != null)
		assert(frame.get_size() == HeroCompositor.FRAME_SIZE)
	var atlas: Image = HeroCompositor.compose_atlas(appearance)
	assert(atlas.get_size() == Vector2i(1152, 768))
	appearance.set("authoring_mode", "free")
	assert(not bool(appearance.call("is_guided_mode")))
	print("[V1.27] Library-Grounded Hero Creator smoke test OK")
	quit()
