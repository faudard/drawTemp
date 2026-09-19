class_name SporeTimelineActorCard
extends Panel

@onready var portrait: TextureRect = $Portrait
@onready var name_label: Label = $Name


func bind_actor(actor: SporeUnitActor3D, is_active: bool) -> void:
	if actor == null:
		return
	portrait.texture = actor.portrait_texture()
	name_label.text = actor.display_name.substr(0, mini(3, actor.display_name.length())).to_upper()
	tooltip_text = "%s • CT %d • VIT %d%s" % [
		actor.display_name,
		actor.ct,
		actor.effective_speed(),
		" • CAST" if actor.is_casting() else ""
	]

	var style := get_theme_stylebox("panel").duplicate() as StyleBoxFlat
	if style == null:
		return
	style.border_color = (
		Color(1.0, 0.80, 0.16, 1.0)
		if is_active
		else (
			Color(0.12, 0.58, 0.92, 1.0)
			if actor.team == "player"
			else Color(0.88, 0.18, 0.15, 1.0)
		)
	)
	var width: int = 3 if is_active else 2
	style.border_width_left = width
	style.border_width_top = width
	style.border_width_right = width
	style.border_width_bottom = width
	add_theme_stylebox_override("panel", style)
