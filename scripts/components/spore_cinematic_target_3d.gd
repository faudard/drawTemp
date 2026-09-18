@tool
class_name SporeCinematicTarget3D
extends Node3D

## Reusable focus anchors attached to a battle actor.
## The .tscn owns the Marker3D positions so framing can evolve visually in Godot.


func anchor_global(anchor_name: String) -> Vector3:
	var wanted: String = anchor_name.to_lower()
	var marker_name: String = "Center"
	match wanted:
		"head":
			marker_name = "Head"
		"feet":
			marker_name = "Feet"
		_:
			marker_name = "Center"
	var marker: Marker3D = get_node_or_null(marker_name) as Marker3D
	return marker.global_position if marker != null else global_position
