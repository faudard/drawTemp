# Première mission tactique 3D jouable

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

## Runtime 3D de la mission 1

**F5 lance maintenant directement `scenes/mission_1_battle_3d.tscn`.** La branche 2D reste dans le projet mais n'est plus le flux de jeu par défaut.

Le runtime 3D utilise les données de `mission_1.tres` et de `mission_1_map.tscn` :

- récupérer la **Couronne Beatbox** en `(9,0)` ;
- la ramener sur une case d'**extraction** verte ;
- récupérer les **2 vinyles** en objectif secondaire ;
- activer le **champignon-interrupteur** pour ouvrir la porte ;
- ouvrir le **coffre à spores** pour gagner du Focus ;
- subir les flaques de spores en fin d'activation ;
- déclencher l'événement de manche 2 qui ajoute un nouveau danger.

Éliminer tous les ennemis ne suffit donc plus à gagner la mission 1 : la Couronne doit réellement être extraite. Si son porteur tombe K.O., elle tombe sur sa case et peut être récupérée à nouveau.

`SporeMap3D` reste la source d'authoring du plateau et expose `to_environment()`, `hero_start_cells()`, `enemy_spawn_data()` et `interactable_definitions()`.

## Lancer et jouer

- **F5** : lance directement la mission 1 3D jouable.
- **F6** sur `maps/mission_1_map.tscn` : aperçu/édition du plateau seul.
- **M** : déplacement.
- **A** : attaque.
- **1 / 2** : compétences.
- **F** : orientation de fin de tour.
- **Espace** : terminer l'activation.
- **Q / E** : rotation de caméra.
- **Molette** : zoom.
- **R** : recommencer la mission, y compris après victoire/défaite.

La scène contient une caméra orthographique et une lumière directionnelle. Dans l'éditeur, le plugin Sporebound ajoute aussi des informations et les boutons **Vue 3D**, **Recaler**, **Capturer pos.** et **Valider** dans l'Inspector. Après un déplacement manuel au gizmo, **Capturer pos.** convertit la position 3D vers la case tactique la plus proche ; sur une case, la hauteur est également recalculée.

## Ancienne version 2D

L'ancienne scène n'est pas perdue : `maps/mission_1_map_2d_legacy.tscn`.
