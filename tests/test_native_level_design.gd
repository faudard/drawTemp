extends SceneTree

const MAPS: PackedStringArray = PackedStringArray([
	"res://maps/mission_1_map.tscn",
	"res://maps/mission_2_map.tscn",
	"res://maps/mission_3_map.tscn",
])


func _init() -> void:
	var failed: bool = false
	for path: String in MAPS:
		var packed: PackedScene = load(path) as PackedScene
		if packed == null:
			push_error("Impossible de charger %s" % path)
			failed = true
			continue
		var instance: Node = packed.instantiate()
		if not instance is SporeMap2D and not instance is SporeMap3D:
			push_error("%s n'a pas SporeMap2D/SporeMap3D comme racine" % path)
			failed = true
			instance.free()
			continue
		root.add_child(instance)
		if not instance.has_method("editor_stats") or not instance.has_method("validation_issues"):
			push_error("%s n'expose pas le contrat d'édition natif" % path)
			failed = true
			instance.queue_free()
			continue
		var stats: Dictionary = instance.call("editor_stats")
		if int(stats.get("heroes", 0)) <= 0:
			push_error("%s n'a aucun spawn héros" % path)
			failed = true
		if instance is SporeMap2D:
			var map_2d: SporeMap2D = instance as SporeMap2D
			if map_2d.native_layer(SporeMap2D.LAYER_GROUND) == null:
				push_error("%s n'a pas de couche Ground" % path)
				failed = true
		elif instance is SporeMap3D:
			var map_3d: SporeMap3D = instance as SporeMap3D
			if int(stats.get("tiles", 0)) != map_3d.grid_width * map_3d.grid_height:
				push_error("%s ne contient pas une case 3D par cellule" % path)
				failed = true
		var issues: Array = instance.call("validation_issues")
		for raw_issue: Variant in issues:
			if not raw_issue is Dictionary:
				continue
			var issue: Dictionary = raw_issue
			if String(issue.get("severity", "")) == "error":
				push_error("%s : %s" % [path, String(issue.get("message", "erreur"))])
				failed = true
		instance.queue_free()
	if failed:
		quit(1)
	else:
		print("[Sporebound] Native 2D/3D level design smoke test OK")
		quit(0)
