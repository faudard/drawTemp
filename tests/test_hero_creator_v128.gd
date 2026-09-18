extends SceneTree

const Appearance = preload("res://scripts/data/hero_appearance_definition.gd")
const HeroCompositor = preload("res://scripts/visual/hero_compositor.gd")

func _init() -> void:
	var kits: PackedStringArray = HeroCompositor.available_kit_ids()
	for expected: String in ["forest_scout", "forest_guardian", "nature_mage"]:
		assert(kits.has(expected))
		assert(HeroCompositor.kit_has_all_directions(expected))
		var metadata: Dictionary = HeroCompositor.kit_metadata(expected)
		assert(String(metadata.get("display_name", "")) != "")
		assert(int(metadata.get("dedicated_state_count", 0)) >= 1)
		for direction: String in HeroCompositor.DIRECTIONS:
			assert(not HeroCompositor.guided_kit_path(expected, direction, "idle").is_empty())
	var appearance: Resource = Appearance.new()
	appearance.set("authoring_mode", "guided")
	for kit_id: String in kits:
		appearance.set("library_kit_id", kit_id)
		for direction: String in HeroCompositor.DIRECTIONS:
			var frame: Image = HeroCompositor.compose_frame(appearance, direction, "attack")
			assert(frame.get_size() == HeroCompositor.FRAME_SIZE)
	var atlas: Image = HeroCompositor.compose_atlas(appearance)
	assert(atlas.get_size() == Vector2i(1152, 768))
	print("[V1.28] Guided Kit Library smoke test OK")
	quit()
