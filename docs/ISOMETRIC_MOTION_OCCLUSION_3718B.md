# 3.7.18B — Mouvement interpolé & occlusion isométrique

## Objectif

Après le raccord 3.7.18A (vue ISO dans le Player et Playtest de l'éditeur),
supprimer deux écarts de présentation : les unités téléportées entre deux
cases et les acteurs systématiquement dessinés **au-dessus** de tous les
bâtiments, même lorsqu'ils passent derrière une façade.

## Livrables

### 1. Interpolation déterministe des animations

- Le **même `MotionDirector`** que celui du renderer 2D existant fournit
  des positions fractionnaires `ActorPose(x, y, action, direction)`.
- `iso_depth.visual_center` projette ces coordonnées dans
  `IsoGeometry` et interpole l'altitude de terrain entre les cases
  voisines. Il s'agit d'un déplacement visuel, jamais d'une nouvelle
  case tactique, d'un mouvement de moteur ou d'une nouvelle physique.
- Le Player ISO programme des frames via `root.after(60, ...)` **uniquement
  pendant une animation active** ; la vue 2D conserve ses réglages et
  la gestion actuelle des sprites. Aucune nouvelle boucle de simulation.
- Les clics restent projetés via la géométrie réelle du plateau, sans
  utiliser les positions flottantes pour valider une commande.

### 2. Ordre de profondeur par bâtiment et unité

- Chaque personnage reçoit son groupe Canvas `iso_actor_unit_N`, chaque
  structure détectée son groupe `architecture_instance_N`.
- L'assemblage est trié **de l'arrière-plan vers l'avant-plan** à partir
  des pieds des personnages et de l'extrémité avant de l'emprise des
  bâtiments (`x+y` dans la projection ISO).
- Les personnages derrière un bâtiment peuvent être cachés par celui-ci.
  Ceux en avant apparaissent devant. Les contours de sélection restent
  toujours au premier plan.
- La **coupe automatique de toiture** prend en compte l'intersection
  fractionnaire des empreintes animées. Un personnage qui traverse le
  seuil ne doit pas disparaître derrière une toiture opaque pendant
  l'interpolation.
- La même composition est utilisée dans l'éditeur et dans le Player.

### Compatibilité

- Aucun changement des `Battle`, `GameSession`, `Content`,
  `ActorView`, coordonnées du moteur, règles CT/IA, sauvegardes,
  replays, RNG ou hit-test tactique.
- Aucun nouveau PNG ou dépendance runtime.
- Le rendu orthogonal du Player demeure disponible.
- Les cartes historiques restent inchangées et s'affichent sans
  nouvelles métadonnées.

## Gates

```sh
python -m unittest discover -s tests_standalone -p test_iso_motion_occlusion_3718b.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_iso_motion_occlusion_3718b_gui.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_iso_battle_view_3718_gui.py -v
python -m unittest discover -s tests_standalone -v
```

La CI relance la matrice Linux, Windows, macOS × Python 3.10 / 3.12 / 3.14
ainsi que les distributions. Le job graphique Linux/Xvfb comporte un smoke
spécifique de la composition devant/derrière une maison et de la coupe
pendant la traversée de son entrée.

## Limites connues

Ce jalon apporte la **profondeur 2.5D par empreinte entière**, pas une
occlusion de pixels ou une profondeur 3D par mur. Dans une très grande
structure, la silhouette est ordonnée d'un seul bloc. Les animations ISO
emploient encore des silhouettes simplifiées ; la connexion aux sprites
de mouvement/attaque directionnels de Jeanne reste à réaliser.

La reconstruction complète de la scène lors des frames animées est une
dette importante : **3.7.18C** devra mettre en cache les fonds, les
structures et les couches tactiques, ne déplacer que les acteurs, et
quantifier le p95 sur 32², 64² et 128².

PR empilée sur la 3.7.18A : intégrer la PR parente avant de la fusionner
dans `master`.
