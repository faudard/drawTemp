@tool
class_name SporeCampaignDefinition
extends Resource

@export var id: String = "main"
@export var display_name: String = "Sporebound Campaign"
@export var start_node_id: String = "start"
@export var nodes: Array[Resource] = []


func node_by_id(node_id: String) -> Resource:
	for node in nodes:
		if node != null and String(node.id) == node_id:
			return node
	return null
