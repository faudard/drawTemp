@tool
class_name SporeAmbientAudioProfile
extends Resource

## Reusable Godot-native spatial ambience profile.
## Assign a real .ogg/.wav stream later; the emitter uses a quiet procedural
## fallback while the project has no final audio asset.

@export_group("Identity")
@export var id: String = "ambient"
@export var display_name: String = "Ambient"

@export_group("Audio")
@export var stream: AudioStream
@export_enum("forest", "spores", "crown", "exit") var fallback_kind: String = "forest"
@export_range(-50.0, 0.0, 0.5) var volume_db: float = -28.0
@export_range(1.0, 30.0, 0.5) var max_distance: float = 12.0
@export_range(0.1, 8.0, 0.1) var unit_size: float = 2.0
@export_range(30.0, 900.0, 1.0) var fallback_base_frequency: float = 110.0
@export_range(0.0, 1.0, 0.01) var fallback_motion: float = 0.25
@export_range(0.0, 0.5, 0.01) var fallback_noise: float = 0.10
