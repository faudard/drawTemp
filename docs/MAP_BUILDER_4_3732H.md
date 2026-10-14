# Map Builder 4.0H — Painted Transition Masks

## Objectif

Remplacer les bandes unies utilisées par `3.7.32F` aux jonctions de
terrains par de **véritables masques alpha RGBA**, colorés avec les pigments
générés en `3.7.32G`. Le rendu reste commun au Studio et au Player et ne
change **aucun** état de simulation, de sauvegarde ou de mission.

## Modèle de raccords

- La topologie (qui borde qui) reste calculée dans
  `terrain_autoblend.blend_edges`. `iso_connections.py` continue de gérer
  les berges, les ponts et les cataractes.
- Chaque côté receveur est recouvert par un **lavis directionnel transparent** :
  N (ouest→nord), E (est→sud), S (sud→ouest), W (nord→est). Ces directions
  correspondent aux quatre segments du losange isométrique.
- La couche est **opaque et de la même couleur que le pigment voisin**
  au contact exact entre deux tuiles, puis s'estompe avec un contour
  irrégulier à l'intérieur de la case de plus faible priorité.
  L'alpha et les variations sont déterministes.
- Aux coins où se rejoignent trois matériaux, les directions sont peintes
  **dans l'ordre stable de priorité des surfaces**, pour éviter que l'ordre
  d'itération des voisins change l'apparence. Les bandes restent limitées au
  losange de leur propre case.
- Un cache de `IsoTerrainAtlas` conserve les objets `tk.PhotoImage` des
  masques : **6 matériaux × 4 faces × 4 variantes**, et des versions
  redimensionnées par zoom. Une cache LRU qui libérerait les images
  encore référencées par un Canvas serait incorrecte : ces références
  restent vivantes pendant toute la vie de l'atlas.
- Sans atlas aquarelle valide, ou avec un atlas explicitement externe, le
  rendu revient aux polygones AutoBlend du lot F. Aucun décodeur additionnel
  ni librairie Pillow n'est requis.

**Invariance d'assemblage :** chaque arête est traitée indépendamment de
l'ordre des cases et du viewport. L'AutoBlend reste dérivé des
**quatre voisins**; une modification d'une case conserve le parcours
Dirty Tiles 3×3 existant ou le repli complet quand il est nécessaire.

## Qualité et artefacts

Exporter les 24 masques canoniques (6 matériaux × 4 directions) :

```bash
python -m sporebound.terrain_transition_masks --output-dir /tmp/terrain-painted-masks
```

Le workflow Editor conserve également ces fichiers dans l'artefact
`terrain-watercolor-painted-masks-3732h`.

## Tests

```bash
python -m unittest tests_standalone.test_terrain_transition_masks_3732h -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest tests_standalone.test_terrain_transition_masks_3732h_gui -v
python -m unittest tests_standalone.test_terrain_autoblend_3732f -v
python -m unittest tests_standalone.test_terrain_watercolor_3732g -v
```

* Gates : PNG 96×48 RGBA/CRC, transparence hors du losange, alpha feutré à
  l'intérieur, couleur exacte sur chaque bord et résultats reproductibles ;
  jonctions à trois surfaces avec ordre de priorité indépendant de la
  traversée ; rendu Tk aux zooms 24, 54 et 96 ; rendu retenu Studio identique
  au rendu complet et fallback sans images masquées.
* Les tests de `3.7.32F` continuent de prouver la reproductibilité des
  seeds, l'Undo/Redo, la protection des surfaces spéciales et le repaint local.

## Limites

Ces masques sont **procéduraux inspirés de l'aquarelle**, et non des textures
peintes manuellement. Ils améliorent le mélange terre/herbe/pierre, sans
promettre une continuité pixel-par-pixel parfaite aux **sommets partagés par
quatre cases de matériaux distincts**, ni de nouveaux reliefs, végétaux
animés ou biomes. Une passe de revue visuelle sur cartes de référence
permettra de décider si des correctifs d'angle sont encore nécessaires.

Suite logique : **3.7.32I — Ambient Terrain Animation**, où l'herbe et
les eaux reçoivent des animations décoratives optionnelles, sans affecter le
CT, les collisions et les sauvegardes.
