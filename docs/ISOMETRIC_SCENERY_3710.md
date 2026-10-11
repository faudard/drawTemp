# 3.7.10 — Isometric Scenery & Autotiling

Suite empilée sur [3.7.9](ISOMETRIC_MAP_BUILDER.md), sans modification de
la simulation tactique. Ce jalon ajoute des décors isométriques PNG et des
transitions calculées à partir des voisins, sans nouveaux marqueurs JSON.

## Rivières, berges et ponts

La **même peinture au pinceau** continue à stocker `surface:water`,
`surface:bridge` et `height:N`. Le rendu dérive ensuite :

- les bords eau/terre (mousse claire et liseré de berge), automatiquement
  raccordés, sans fausse couture entre deux cases d'eau ;
- les ponts : les côtés de rambarde se déduisent de la direction dominante
  du canal voisin ; un pont croisant un cours d'eau nord/sud s'aligne est/ouest,
  et inversement ;
- les petites cascades si une case d'eau surélevée jouxte une autre case
  d'eau de niveau inférieur sur une face visible ;
- les limites de grille ne créent pas d'artéfacts de mousse hors carte.

Les calculs purs, testables sans Tk, sont dans
`sporebound/iso_connections.py`. Un `bridge` prolonge le canal lors du
calcul des raccords, même s'il reste **traversable** dans le moteur.
Aucune pente, pont 3D ou nage tactique n'est simulé implicitement.

## Nouvel atlas illustré

`sporebound/content/art/iso/props.png` :
12 cadres de **96 × 128 px**, transparents, disposés en une ligne
(`1152 × 128`). Ordre immuable :

```
tree, bush, boulder, ruin, crate, lantern, stairs, stone_wall,
arch, fence, reeds, pillar
```

Ces assets originaux sont des *sprites stylisés de première passe* :
arbres feuillus, végétation, rocher, ruines, crate, lampadaire,
escaliers, mur de pierre, arche, clôture, roseaux et pilier.
Ils servent à valider la découpe, le placement et les pivots avant
une passe définitive de peinture illustrée.

`IsoPropAtlas` charge le PNG une seule fois, vérifie ses dimensions,
découpe les régions, les met à l'échelle avec Tk et conserve les
`PhotoImage` dans un cache par zoom. Le pivot est au sol :
le bas de l'image est décalé de 18 pixels à l'échelle nominale, pour
placer les éléments correctement sur la case. Si l'atlas manque ou
est invalide, le rendu vectoriel précédent reste utilisable.

La liste `FEATURES` inclut maintenant `arch`, `fence`, `reeds`
et `pillar`. Ils sont purement décoratifs. `stone_wall` continue à
utiliser la règle de blocage existante de 3.7.9. Les autres objets ne
modifient pas le `Battle`, les replays ou le pathfinding.

## Usage

1. Ouvrir l'éditeur et activer **Vue isométrique 2.5D**.
2. Dessiner une rivière en `water` : les berges apparaissent en fonction
   des cases voisines.
3. Sur une ligne de traversée, appliquer `bridge`. Les rambardes
   s'orientent automatiquement.
4. Appliquer différents niveaux à deux tronçons adjacents pour tester
   une chute d'eau visuelle.
5. Choisir les objets dans la palette **Décor**. Les nouveaux sprites
   peuvent être peints et copiés par modèles comme les anciens.

## Validation

```sh
python -m unittest discover -s tests_standalone -p test_iso_connections.py -v
python -m unittest discover -s tests_standalone -p test_iso_props.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```

Les tests incluent les cas limites des cartes, les orientations, la
validation PNG et les sprites Tk réellement utilisés puis enregistrés.
La CI multiplateforme reste le gate de revue.

## Suite proposée

- Détourage haute qualité et variantes d'expressions visuelles pour les
  grands arbres, rochers et architectures ; atlas déclinés par biome.
- Objets multi-cases avec pivot, emprise et ordre de profondeur.
- Exposition de paramètres d'orientation et de variante visuelle dans
  l'inspecteur, sans surcharger le format de sauvegarde du moteur.
- Cache de rendu limité au viewport pour les cartes denses.
