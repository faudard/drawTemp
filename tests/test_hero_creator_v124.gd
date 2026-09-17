extends SceneTree

const Appearance = preload("res://scripts/data/hero_appearance_definition.gd")
const Compositor = preload("res://scripts/visual/hero_compositor.gd")

func _init() -> void:
	var appearance: Resource = Appearance.new()
	appearance.set("hair_style", "tuft")
	appearance.set("ears_style", "pointed")
	appearance.set("horns_style", "short")
	appearance.set("accessory_style", "scarf")
	appearance.set("accessory_2_style", "badge")
	appearance.set("accessory_3_style", "goggles")
	appearance.set("asymmetry_enabled", true)
	appearance.set("left_horns_style", "none")
	appearance.set("right_horns_style", "short")
	assert(String(appearance.call("directional_part_id", "horns", "left")) == "none")
	assert(String(appearance.call("directional_part_id", "horns", "right")) == "short")
	assert(String(appearance.call("directional_part_id", "horns", "front")) == "short")
	for category: String in ["hair", "ears", "horns", "accessory_2", "accessory_3"]:
		assert(not Compositor.available_part_ids(category).is_empty())
	for direction: String in Compositor.DIRECTIONS:
		var frame: Image = Compositor.compose_frame(appearance, direction)
		assert(frame != null)
		assert(frame.get_size() == Compositor.FRAME_SIZE)
	print("[V1.24] Hero Creator Asymmetry smoke test OK")
	quit()
