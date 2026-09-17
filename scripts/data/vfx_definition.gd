@tool
class_name SporeVfxDefinition
extends Resource

## Reusable visual effect referenced by skills, statuses and basic attacks.

@export_group("Identity")
@export var id: String = "vfx"
@export var display_name: String = "VFX"
@export_multiline var description: String = ""
@export_enum("burst", "projectile", "beam", "aura", "ring", "cross", "slash") var kind: String = "burst"

@export_group("Look")
@export var primary_color: Color = Color("#ff7b72")
@export var secondary_color: Color = Color.WHITE
@export_file("*.png", "*.jpg", "*.jpeg", "*.webp") var texture_path: String = ""
@export_range(0.1, 8.0, 0.05) var texture_scale: float = 1.0
@export_range(0.05, 4.0, 0.05) var duration: float = 0.45
@export_range(0, 64, 1) var particle_count: int = 8
@export_range(1.0, 180.0, 1.0) var radius: float = 26.0
@export_range(1.0, 24.0, 0.5) var trail_width: float = 5.0
@export_range(0.0, 20.0, 0.5) var shake_strength: float = 2.0
@export_range(0.0, 1.0, 0.05) var flash_strength: float = 0.55

@export_group("Texture Animation")
@export_range(0, 1024, 1) var frame_width: int = 0
@export_range(0, 1024, 1) var frame_height: int = 0
@export_range(0, 999, 1) var start_frame: int = 0
@export_range(1, 999, 1) var frame_count: int = 1
@export_range(0.1, 60.0, 0.1) var fps: float = 12.0
@export var loop: bool = false


func frame_index(elapsed: float) -> int:
	var count: int = maxi(1, frame_count)
	var safe_elapsed: float = maxf(0.0, elapsed)
	var safe_fps: float = maxf(0.1, fps)
	var frame: int = int(floor(safe_elapsed * safe_fps))
	if loop:
		frame %= count
	else:
		frame = mini(frame, count - 1)
	return start_frame + frame
