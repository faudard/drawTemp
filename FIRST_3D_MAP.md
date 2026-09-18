# Première map tactique 2.5D / 3D

La mission 1 utilise maintenant `maps/mission_1_map.tscn`, une scène `SporeMap3D` éditable directement dans le workspace **3D** de Godot.

## Éditer une case

1. Ouvre `maps/mission_1_map.tscn`.
2. Dans `Tiles`, sélectionne par exemple `Cell_06_02`.
3. Dans l'Inspector :
   - `cell` = coordonnée tactique X/Y ;
   - `elevation` = hauteur logique ;
   - `terrain_type` = ground / obstacle / cover / hazard / extraction / bonus / crown ;
   - `display_label` = texte optionnel visible au-dessus de la case.
4. La position et le bloc 3D se recalculent automatiquement.

Les cases sont volontairement des nœuds explicites plutôt qu'une génération opaque au runtime : elles sont sélectionnables, duplicables et versionnables comme le reste d'une scène Godot.

## Relief façon FFT

Le plateau est en 3D, mais la logique de combat reste discrète sur une grille 2D (`Vector2i`). `elevation` ajoute la troisième dimension sans changer les coordonnées tactiques. C'est le modèle classique 2.5D utile pour un tactical RPG : terrain 3D + logique de cases 2D + personnages pouvant rester en sprites/billboards plus tard.

## Spawns et objets

- `Spawns/HeroSpawn*` : `cell` + `order`.
- `Spawns/EnemySpawn_*` : `cell`, `unit_id`, rôle et overrides.
- `Objects/*` : porte, interrupteur et coffre avec la même donnée métier que la map 2D.

Ils se recalent automatiquement sur le sommet de la case ciblée.

## Compatibilité runtime

`SporeMap3D` expose les mêmes méthodes que `SporeMap2D` :

- `to_environment()` ;
- `hero_start_cells()` ;
- `enemy_spawn_data()` ;
- `interactable_definitions()`.

Le BattleController existant peut donc jouer la mission sans connaître le format d'authoring 2D ou 3D.

## Aperçu

La scène contient une caméra orthographique et une lumière directionnelle. Lance la scène seule avec **F6** pour avoir un aperçu du plateau. Dans l'éditeur, le plugin Sporebound ajoute aussi des informations et les boutons **Vue 3D**, **Recaler**, **Capturer pos.** et **Valider** dans l'Inspector. Après un déplacement manuel au gizmo, **Capturer pos.** convertit la position 3D vers la case tactique la plus proche ; sur une case, la hauteur est également recalculée.

## Ancienne version 2D

L'ancienne scène n'est pas perdue : `maps/mission_1_map_2d_legacy.tscn`.
