# Sporebound — Direction visuelle Comic sélectif

Cette branche fixe la direction visuelle du niveau 1 autour d'un langage **BD / manga noir et blanc avec couleur sélective**.

## Règles visuelles

- Décor et volumes : encre, niveaux de gris, contraste marqué, texture/grain léger.
- Rouge : Momo, ennemis et danger.
- Vert : déplacement, alliés, cases atteignables.
- Violet : magie, hazards et cases spéciales.
- Bleu/cyan : sélection, MP, information tactique.
- Or : couronne, objectif et information prioritaire.
- HUD : panneaux noirs, bordures ivoire épaisses, coins presque carrés.
- Initiative : portraits lisibles, couleur par camp, surbrillance or pour l'unité active.
- Dialogue : grands portraits/cut-ins, cadre BD, nom du locuteur coloré, texte très lisible.
- Le terrain doit rester lisible avant d'être décoratif : silhouettes nettes, cases compréhensibles, objectifs visibles.

## Niveau 1

La Couronne Beatbox reste le point focal de la carte. La post-production comic est appliquée au monde 3D avant le HUD, de sorte que l'interface conserve ses couleurs tactiques nettes.

Le niveau 1 sert de référence pour les futurs niveaux : même grammaire de couleur, même HUD, mêmes dialogues et mêmes priorités de lisibilité.


## Architecture visuelle Godot

La composition visuelle doit être **éditable dans l'éditeur Godot** :

- géométrie, placement, lumières, panneaux, cut-ins et matériaux dans des `.tscn` ;
- couleurs et rendu dans des `StandardMaterial3D`, `ShaderMaterial`, `Environment` et ressources de thème ;
- scènes réutilisables pour les éléments répétés (arbres, panneaux, cut-ins) ;
- scripts limités au comportement : animation, binding des données, réactions aux états de jeu ;
- éviter de générer en GDScript des arbres complets de `Control`, `MeshInstance3D` ou de décor statique quand Godot peut les sérialiser dans une scène ;
- aucun `Label3D.fixed_size` décoratif dans la carte : les indications du monde doivent conserver une taille physique cohérente avec la caméra ;
- les décors de fond ne doivent pas être des plans fixes dans le monde si la caméra peut tourner. Utiliser `WorldEnvironment` ou des éléments périphériques réellement 3D.


### Prévisualisation complète

`scenes/mission_1_battle_3d.tscn` doit montrer le niveau utile directement dans l'éditeur :

- la map est instanciée sous `MapRoot` au lieu d'être uniquement chargée par code au lancement ;
- le HUD est une instance de `battle_hud_3d.tscn` visible/modifiable en 2D ;
- caméra et curseur sont des scènes réutilisables ;
- le code runtime réutilise les instances présentes et ne crée des fallbacks que si elles manquent.

Le but est qu'un level designer puisse déplacer le décor dans la vue 3D et ajuster l'UI dans la vue 2D sans modifier `spore_battle_board_3d.gd`.


### Feedback de combat

Les éléments temporaires de combat doivent aussi utiliser des scènes réutilisables quand leur structure visuelle est stable :

- `combat_floating_text_3d.tscn` porte la taille, le billboard, le pixel size et le contour des textes ;
- `combat_feedback_burst_3d.tscn` utilise `GPUParticles3D` plutôt qu'une boucle qui crée des meshes à la volée ;
- `unit_actor_3d.tscn` porte les nodes visuels communs à tous les combattants (sprite, ombre, sélection, direction, vitaux, labels) ;
- les scripts ne changent que le contenu, la couleur, l'état et l'animation.

Les textes flottants restent petits et ancrés dans le monde : pas de `fixed_size` et pas de gros texte écran pour les dégâts, objets ou compétences.


### Marqueurs tactiques

Les marqueurs temporaires du plateau suivent désormais la même règle scene-first :

- `tactical_marker_3d.tscn` sert pour objectifs, cases de déplacement, danger, preview d'IA, zones persistantes et hover tactique ;
- `mission_hazard_3d.tscn` porte le rendu des spores/hazards via `GPUParticles3D` ;
- aucune logique de gameplay ne doit recréer un `Label3D`, un anneau, ses matériaux et ses meshes à chaque usage ;
- les labels du monde utilisent `fixed_size = false` et un `pixel_size` contrôlé pour rester proportionnés à la caméra.

Les scripts ne fournissent plus que : texte, couleur, rayon, position et durée.


### Transitions et résultats

Les écrans/effets transitoires suivent aussi l'architecture scene-first :

- `skill_burst_3d.tscn` pour l'impulsion visuelle d'une compétence ;
- `victory_celebration_3d.tscn` pour les confettis/spores de victoire ;
- `battle_result_overlay.tscn` pour VICTOIRE / DÉFAITE ;
- `turn_transition_banner.tscn` pour le changement de tour ;
- `mission_event_banner.tscn` pour les événements de mission.

Le battle controller ne construit plus ces panneaux, labels, matériaux ou particules à la main. Il instancie les scènes et fournit les données dynamiques.


### Palette environnementale

Le niveau 1 applique désormais une palette partagée par des ressources `.tres` :

- `comic_ink.tres` : encre / silhouettes / speakers / câbles ;
- `comic_stone.tres` et `comic_stone_light.tres` : pierre, champignons et ruines ;
- `comic_wood.tres` : bois volontairement désaturé ;
- `comic_accent_gold.tres` : Couronne et objectif principal ;
- `comic_accent_green.tres` : sortie / validation ;
- `comic_accent_cyan.tres` : information tactique / vinyle ;
- `comic_accent_purple.tres` : magie / spores / DJ.

Règle : les éléments naturels et architecturaux restent en valeurs gris/brun désaturées. Les couleurs saturées sont réservées aux informations de gameplay et aux points narratifs.

### Composition niveau 1

- la Couronne doit être lisible par sa **silhouette réelle**, pas par un gros texte ;
- la sortie doit être reconnaissable par sa forme et son accent vert ;
- les panneaux du monde restent petits et secondaires ;
- les ruines et champignons périphériques servent de cadre sans masquer les cellules ;
- les props DJ conservent uniquement les accents cyan/violet ;
- éviter les anneaux statiques qui doublonnent les marqueurs tactiques runtime.
