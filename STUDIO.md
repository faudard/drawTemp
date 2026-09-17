# Sporebound Studio V1.9.6 — Level design natif 2D / 2.5D

## Maps

`🗺 ÉDITER LA MAP` ouvre le `.tscn` dans le workspace natif adapté : **2D** pour `SporeMap2D`, **3D** pour `SporeMap3D`. Le dock Studio sert de catalogue/assistant, pas de remplacement au level editor Godot.

### Création

Avant `+ Mission`, choisis un template :

- **Template vide** : 10×8 + 3 spawns héros.
- **Escarmouche 8×8** : couverture/obstacles + 2 ennemis.
- **Objectif 10×8** : extraction + couronne + ennemis.
- **Grande 12×10** : terrain plus large prêt à habiller.

## Map 2.5D / 3D

La mission 1 est une `SporeMap3D`. **Éditer la map** ouvre automatiquement le workspace 3D. Les cases sont sous `Tiles` et exposent `cell`, `elevation`, `terrain_type` et `display_label`. Les spawns et objets exposent leur `cell` et se recalent sur le sommet du terrain. L'Inspector Sporebound fournit **Vue 3D**, **Recaler**, **Capturer pos.** et **Valider**. Tu peux déplacer une case, un spawn ou un objet au gizmo puis utiliser **Capturer pos.** pour convertir la position vers la grille tactique.


## Toolbar Spore Map 2D

- `Sol / Hauteur / Terrain / Objectifs` : sélection des `TileMapLayer` natifs.
- `+ Objet` : ajoute un spawn héros/ennemi, porte, interrupteur, coffre ou zone sur la case survolée (sinon case sélectionnée/centre).
- `Pinceau rapide` : optionnel pour les actions Sporebound spécifiques.
- `Aperçu tactique` : mouvement + enveloppe d’attaque du spawn ennemi sélectionné.
- `Erreurs` : validation directement sur la viewport.
- `Snap sélection`, `Cadrer sélection`.
- `▶ Ici` : sauvegarde toutes les scènes puis lance automatiquement la mission courante en playtest protégé.

## Zones polygonales

Ajoute **+ Objet > Zone polygonale**. Le nœud `SporeMapZone2D` est un vrai `Polygon2D` : utilise les outils de points/polygone de Godot pour changer sa forme.

Propriétés :

- `zone_id` : identifiant stable pour les triggers.
- `display_name`.
- `zone_type` : deployment / objective / trigger / danger / camera.
- `team` : any / player / enemy.
- `enabled`.

Quand une zone est sélectionnée, les cases qu’elle couvre sont surlignées dans la viewport.

Dans **Mission Logic**, les conditions `player_enters_zone` / `enemy_enters_zone` utilisent le champ **Zone ID condition**.

## Inspector enrichi

- Map : cadrer, valider, aperçu tactique, **▶ Tester ici**.
- Spawn : cadrer, snap ; ennemi → ouvrir la `UnitDefinition`.
- Interactable : cadrer, snap, suivre la liaison.
- Zone : cadrer, snap, type/id + nombre de cases couvertes.

## Source de vérité

Le runtime consomme directement la scène native : TileMap, spawns, interactables et zones. Les anciennes listes de cellules restent uniquement comme migration/fallback des anciennes missions.


## Combat tactique 3D

- Ouvre `maps/mission_1_map.tscn` pour éditer le plateau depuis le workspace 3D.
- Avec le nœud `SporeMap3D` sélectionné, utilise **▶ Combat 3D** dans l’Inspector pour sauvegarder et lancer directement le prototype.
- La scène jouable est `scenes/mission_1_battle_3d.tscn`.
- Une activation permet un déplacement et une attaque dans l’ordre souhaité.
- **M** active le mode déplacement, **A** le mode attaque, **Espace** termine l’activation.
- Clic droit ou **Q/E** pivote la caméra, la molette zoome.
- Vert = cases atteignables ; rouge = portée d’attaque.
- Les unités, statistiques et spawns sont lus depuis les Resources et la map natives du projet.


## Combat 3D V1.9.9 — lecture tactique

- Survole une case verte : le chemin utilisé est affiché en jaune avant le clic.
- Le déplacement est exécuté case par case ; `max_jump_up` et `max_jump_down` contrôlent séparément les changements de niveau.
- En mode attaque, seules les cases avec ligne de vue sont rouges ; les cases de couvert sont orange.
- Un obstacle entre tireur et cible bloque la ligne de vue. Un relief intermédiaire plus haut peut aussi la bloquer.
- Une cible à distance placée sur une case `cover` reçoit une réduction de dégâts configurable.


## Combat 3D V1.10.0 — orientation, saut et couvert directionnel

- Chaque unité affiche sa direction au sol. **F** tourne de 90° ; **Shift+F** tourne dans l’autre sens.
- Les attaques de flanc et de dos reçoivent des bonus réglables sur `SporeBattleBoard3D`.
- Survole un ennemi en mode attaque pour voir les dégâts prévus et leurs modificateurs.
- Les changements de hauteur d’un chemin apparaissent en bleu et sont animés comme un saut.
- Sur une case `cover`, règle `cover_facing` dans l’Inspector : le muret se déplace/rotate visuellement et ne protège que contre les attaques venant de cette direction.
- La mission 1 contient plusieurs orientations de couvert différentes pour servir d’exemple éditable.


## Compétences sur le plateau 3D — V1.11

Dans `scenes/mission_1_battle_3d.tscn`, les deux compétences définies sur chaque `UnitDefinition` sont disponibles avec **1** et **2**. Le ciblage et les zones sont lus directement depuis `SkillDefinition` / `SkillEffect`.

Couleurs : violet = case de ciblage, cyan = zone vide, rouge = ennemi affecté, vert = allié affecté. `Esc` annule le ciblage. Les formes disponibles dans l’éditeur Skills sont `single`, `cross`, `diamond`, `line` et `circle`.


## Réactions, IA et zones persistantes — V1.12

Dans **Units**, chaque `UnitDefinition` expose maintenant `Réaction`, `Portée réaction` et `Bonus dégâts réaction`. Les modes disponibles sont `none`, `counter`, `opportunity` et `intercept`.

Dans **Skills**, le type d'effet `zone` crée une zone persistante. Le bloc permet de choisir `damage/heal/status`, la phase `activation_start` ou `activation_end`, la durée en rounds, la forme et le rayon. Les zones sont visibles directement sur le plateau 3D avec leur durée restante.

L'IA 3D compare désormais attaque normale et skills utilisables. Les quatre ennemis de la mission 1 ont reçu des compétences/réactions de démonstration pour tester immédiatement ces systèmes.


## V1.13 — Prévision de combat 3D

Dans `scenes/mission_1_battle_3d.tscn`, une attaque ou compétence n’est plus exécutée au premier clic. Le premier clic prépare l’action et ouvre le panneau de prévision. **Entrée** confirme, **Échap** annule. Le panneau montre les HP projetés, modificateurs de terrain/orientation, réactions et les effets de compétence sur chaque cible.


## Présentation combat 3D — V1.14

- Chaque acteur affiche désormais des barres HP/Focus billboard directement dans le monde 3D.
- La timeline compacte montre l'activation courante et les suivantes selon l'initiative.
- La fiche en bas à droite inspecte automatiquement l'unité survolée, alliée ou ennemie.
- La caméra suit l'acteur actif avec interpolation ; `Q/E` pivotent, la molette zoome et `C` recentre immédiatement.
- Les réglages `camera_follow_active` et `camera_smoothing` sont exposés dans l'Inspector de `SporeBattleBoard3D`.


## Présentation combat 3D — V1.15

- `ActionWheel` affiche les commandes autour de l’unité active pendant le tour joueur.
- La caméra cadre automatiquement attaquant/cible pendant une attaque ou un skill puis revient au suivi de l’unité active.
- Le shake, le zoom d’action et le menu contextuel se règlent depuis `SporeBattleBoard3D` dans l’Inspector.
- Le curseur et les personnages ont maintenant une animation de présentation légère sans modifier les règles tactiques.


## V1.16 — VFX d’action 3D

Le combat 3D consomme désormais directement les `VfxDefinition` éditées dans l’onglet **VFX** de Sporebound Studio. Les champs `kind`, couleurs, durée, nombre de particules, rayon et largeur de traînée pilotent le rendu runtime. Les attaques de base utilisent le `basic_attack_vfx_id` de l’apparence d’unité et les compétences utilisent leur `vfx_id`.


## V1.17 — VFX avancés

- Le type **beam** est disponible dans l’onglet **VFX** pour les lasers/faisceaux continus.
- `Lance prismatique` fournit un exemple prêt à tester avec `prism_beam`.
- Les projectiles 3D suivent une cible mobile lorsque l’action vise une unité.
- Les AOE affichent maintenant un impact sur chaque cellule affectée au lieu d’un seul effet central.
- Les statuts persistants affichent leur `vfx_id` directement autour de l’unité jusqu’à expiration.


## V1.18 — sprites directionnels

Dans **Visuals**, un personnage peut maintenant utiliser un spritesheet `single`, `4_way` ou `8_way`.

- `rows` : une ligne du spritesheet par direction ; les champs Start/Frames décrivent les colonnes du clip.
- `blocks` : chaque direction possède un bloc de frames consécutives ; `Stride frames` définit la taille d’un bloc (`0` = calcul automatique).
- Ordre 4 directions par défaut : `front,right,back,left`.
- Ordre 8 directions par défaut : `front,front_right,right,back_right,back,back_left,left,front_left`.
- Les clips disponibles sont : Idle, Move, Attack, Cast, Hit et KO.
- Le panneau de preview permet de changer séparément l’état et la direction.

Le runtime choisit la direction en fonction du **facing tactique de l’unité et de la caméra isométrique**. Tourner la caméra change donc automatiquement la vue du sprite sans modifier l’orientation tactique de l’unité.
