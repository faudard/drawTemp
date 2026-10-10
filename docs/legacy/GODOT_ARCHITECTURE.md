# Architecture V1.9.6 — Native 2D / 2.5D Level Design

## Contrat de map

```text
MissionDefinition.tres
		|
		+-- map_scene_path --> maps/*.tscn
								|
								+-- SporeMap2D (@tool)
								+-- Ground / Height / Terrain / Objectives (TileMapLayer)
								+-- SporeHeroSpawn2D / SporeEnemySpawn2D
								+-- SporeMapInteractable2D
								+-- SporeMapZone2D (Polygon2D)
```

`MissionCatalog.environment()` instancie la scène et appelle `SporeMap2D.to_environment()`. V1.9.5 ajoute `zones`, chaque entrée contenant `id`, `type`, `team`, `enabled` et les cellules couvertes.

## Zones

`SporeMapZone2D` ne stocke pas une liste de cellules : la forme auteur est le polygone natif Godot. `occupied_cells(map)` calcule les cellules dont le centre tombe dans le polygone. Cela garde une édition libre tout en conservant un runtime tactique discret.

Les triggers `player_enters_zone` / `enemy_enters_zone` comparent la position logique de l’unité aux cellules exportées par la zone.

## Playtest depuis la viewport

`SporeNativeMapEditor.play_current_map()` :

1. sauvegarde les scènes ouvertes ;
2. retrouve la `MissionDefinition` liée au `scene_file_path` courant ;
3. écrit `user://sporebound_editor_test.json` avec `autostart=true` ;
4. lance `main.tscn`.

`BattleController.consume_editor_test_request()` consomme ce fichier. En `editor_test_mode`, `save_campaign()` devient un no-op afin qu’un playtest de level design ne modifie pas la progression persistante.

## Création rapide

Le menu `+ Objet` de la toolbar crée les nœuds avec `EditorUndoRedoManager`, leur attribue l’owner de scène et les sélectionne immédiatement. Le placement vise la case survolée, puis la sélection, puis le centre de map.

## Templates

Les templates de mission ne sont pas des formats parallèles : ils initialisent simplement une `MissionDefinition`, puis `_create_native_map_scene()` produit la même scène Godot native que toute autre mission.

## Contrat 2.5D / 3D

`SporeMap3D` est une seconde implémentation du contrat de map. Les cellules sont des `SporeTacticalTile3D` avec une coordonnée logique `Vector2i`, une `elevation` entière et un `terrain_type`. Les spawns/objets 3D exportent les mêmes données que leurs équivalents 2D. `MissionCatalog` reste donc indépendant de la représentation auteur.

```text
MissionDefinition.tres
		|
		+-- map_scene_path --> SporeMap2D  -> TileMapLayer
						   \-> SporeMap3D  -> Tiles/SporeTacticalTile3D
											  SporeHeroSpawn3D
											  SporeEnemySpawn3D
											  SporeMapInteractable3D
```

La hauteur 3D est convertie vers le dictionnaire runtime `heights[Vector2i] = int`. Les coordonnées X/Z de la scène ne deviennent jamais la source de vérité : `cell` et `elevation` le sont.
