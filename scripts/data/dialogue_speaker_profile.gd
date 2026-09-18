@tool
class_name SporeDialogueSpeakerProfile
extends Resource

## Reusable JRPG dialogue presentation defaults for one speaker.
## Dialogue lines remain content-only; this resource owns presentation identity.

@export_group("Identity")
@export var id: String = "speaker"
@export var display_name: String = "Speaker"
@export var unit_id: String = ""

@export_group("Dialogue Look")
@export_enum("left", "right") var portrait_side: String = "left"
@export var accent_color: Color = Color(0.48, 0.82, 1.0, 1.0)
@export var name_color: Color = Color(0.76, 0.92, 1.0, 1.0)
@export_file("*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg") var portrait_path: String = ""

@export_group("JRPG Voice")
@export_range(10.0, 120.0, 1.0) var text_speed: float = 46.0
@export_range(0.55, 1.75, 0.05) var voice_pitch: float = 1.0
@export_range(1, 8, 1) var blip_every: int = 2
@export_range(-40.0, 0.0, 0.5) var blip_volume_db: float = -16.0


func summary() -> String:
	return "%s • %.2fx • %.0f car/s" % [display_name, voice_pitch, text_speed]
