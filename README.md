# Sporebound Tactics — V1.9.6 First Tactical 2.5D Map

## Première map 2.5D / 3D

La **mission 1** est maintenant une vraie scène `SporeMap3D` ouverte dans le workspace **3D Godot**. Chaque case est un nœud `SporeTacticalTile3D` éditable dans l'Inspector avec `cell`, `elevation` et `terrain_type`. Les spawns et interactables sont également des nœuds 3D éditables et se recalent sur le relief.

Le runtime conserve la logique tactique 2D existante : `SporeMap3D` expose le même contrat de données que `SporeMap2D`. Voir `FIRST_3D_MAP.md` pour le workflow.

L'ancienne mission 1 2D est conservée dans `maps/mission_1_map_2d_legacy.tscn`.


## Level design = scènes Godot natives

Les maps restent de vraies scènes `.tscn`. Le projet accepte maintenant **deux authorings natifs** : `SporeMap2D + TileMapLayer` pour les missions 2D historiques, et `SporeMap3D + SporeTacticalTile3D` pour le relief 2.5D. Le dock Sporebound Studio ouvre automatiquement le workspace 2D ou 3D selon la scène.

Workflow mission 1 :

1. `Sporebound Studio > Maps` : sélectionne **La Couronne Beatbox**.
2. Ouvre la map : Godot bascule dans le workspace **3D**.
3. Dans `Tiles`, sélectionne une `Cell_XX_YY`.
4. Modifie `elevation` ou `terrain_type` dans l’Inspector.
5. Modifie les nœuds `Spawns` et `Objects` via leur propriété `cell`.
6. Utilise **Recaler** / **Valider** dans l’Inspector Sporebound, puis teste la mission depuis Studio.

Les missions 2 et 3 conservent le workflow `TileMapLayer` 2D existant.

## V1.9.5

- **Zones polygonales natives** (`SporeMapZone2D`) éditables comme `Polygon2D` dans la viewport.
- Types de zone : `deployment`, `objective`, `trigger`, `danger`, `camera` + filtre d’équipe.
- Les zones exportent les cases couvertes vers le runtime.
- Nouveaux triggers : `player_enters_zone` et `enemy_enters_zone`.
- Exemple fourni dans **Tenir la Scène** : zone `center_stage` visible dans la map et trigger associé.
- Menu **+ Objet** directement dans la toolbar 2D : spawn héros/ennemi, porte, interrupteur, coffre, zone.
- Le curseur de création suit la case survolée même hors mode pinceau.
- **▶ Ici** : playtest direct de la scène ouverte, sans sauvegarder les résultats dans la campagne.
- **▶ Tester direct** disponible aussi depuis `Studio > Maps`.
- Templates de nouvelle mission : vide, escarmouche 8×8, objectif 10×8, grande 12×10.
- Validation des Zone Id, polygones invalides/vides et comptage des zones dans l’Inspector/Studio.
- Nouveau smoke test `tests/test_native_level_design_v195.gd`.

## Couches de map

- `Ground` : sol.
- `Height` : hauteurs 1/2.
- `Terrain` : obstacles, couverture, spores.
- `Objectives` : extraction, bonus, couronne.
- `SporeMapZone2D` : volumes 2D libres pour triggers/objectifs/aires de gameplay.

## Playtest protégé

Le mode `▶ Ici` écrit une requête temporaire dans `user://`, lance la scène principale et démarre automatiquement la mission correspondante. Pendant ce mode, `save_campaign()` est neutralisé : le level designer peut tester sans polluer sa progression persistante.

## 2.5D / 3D

La mission 1 utilise désormais `SporeMap3D`. Le plateau est réellement en 3D dans l’éditeur, tandis que les règles restent basées sur des coordonnées tactiques `Vector2i` et un niveau de hauteur entier. Ce découplage permet de garder le BattleController actuel tout en faisant évoluer progressivement le rendu vers un tactical RPG 2.5D.
## V1.26 — Hero Creator Expressions & Profiles

Le Hero Creator peut maintenant baker une expression différente pour chacun des six états de combat, choisir une pose de portrait, appliquer des silhouettes fortement différenciées et sauvegarder/appliquer des profils de couleur indépendants du look. Voir `HERO_CREATOR.md`.

## V1.25 — Hero Creator Face Details

Le Hero Creator gère désormais des détails faciaux combinables : iris et pupilles séparés, sourcils, nez, dents, taches de peau, trois marques/cicatrices, boucles d’oreilles et bijoux. Les couches restent compatibles avec les transformations directes, les variantes gauche/droite, les presets et la génération d’atlas. Voir `HERO_CREATOR.md`.

## V1.24 — Hero Creator Asymmetry

Le Hero Creator gagne un workflow de production : Undo/Redo 30 états, favoris persistants, comparaison Avant/Après et export/import de looks `.tres`. L’édition directe, les vignettes, les presets et la génération 4 directions restent compatibles avec V1.22.

## V1.22 — Hero Creator Direct Edit

- L’aperçu du héros est maintenant éditable directement à la souris.
- Déplacement, resize uniforme et rotation des groupes Corps / Tête / Visage / Accessoire / Arme.
- Verrouillage des groupes et reset rapide par clic droit.
- Molette pour le resize, Ctrl+molette pour la rotation.
- Les transforms sont persistées et appliquées au portrait/spritesheet généré.
- Voir `HERO_CREATOR.md` pour le workflow complet.

## V1.21 — Hero Creator Pro

- Galeries de vignettes cliquables dans le Hero Creator.
- Offsets fins X/Y par zone visuelle.
- Presets sauvegardables et trois presets fournis.
- Duplication de look vers un autre héros avec génération immédiate.
- Randomizer intelligent à palettes cohérentes.

## V1.20 — Hero Creator Advanced

Le dock **Sporebound Studio > Hero Creator Advanced** permet de construire le héros principal par couches avec forme du spore, motif bicolore, yeux, bouche, barbe, cicatrices, morphologie Petit/Moyen/Grand, présentation Masculin/Féminin/Neutre/Créature et presets de style. Le résultat est prévisualisé en direct puis généré dans le spritesheet 4 directions utilisé par le combat. Voir `HERO_CREATOR.md`.

