# 3.7.14 — Atlas architectural isométrique (assets PNG)

La vue isométrique utilise maintenant des **sprites originaux, livrés en PNG
palettisé transparent** au lieu de dessiner exclusivement les façades et les
toitures via des polygones Tk.

## Fichiers

- `sporebound/content/art/iso/buildings.png` : atlas PNG RGBA logique
  (palette + canal alpha), **6 frames**, 350 × 220 px chacune, atlas
  2100 × 220 px. Art pixel à composition isométrique, pierre, tuiles,
  bois, fenêtres, ombres portées et végétation. Aucun modèle externe.
- `sporebound/iso_building_atlas.py` : chargeur Tk `PhotoImage` avec
  vérification des dimensions, crop par frame, zoom et cache par variante.
- `sporebound/iso_architecture.py` : réutilise la détection des plans
  existants et préfère le sprite si le bâtiment est entièrement visible.
- `sporebound/iso_map.py` et `sporebound/editor.py` : transmettent
  le chargeur sans modifier le format des documents.

## Ordre des frames

| Index | Structure | Orientation des dimensions |
| --- | --- | --- |
| 0 | Maison | 4×3 |
| 1 | Maison | 3×4 |
| 2 | Tour | 3×3 (rotation 0/180) |
| 3 | Tour | 3×3 (rotation 90/270) |
| 4 | Ruines | 4×3 |
| 5 | Ruines | 3×4 |

Toutes les rotations continuent d'être celles des tampons de terrain ;
la parité sélectionne le cadrage du sprite adapté.

## Règles d'affichage

- Le sprite est visible quand **Bâtiments** est activé et, pour Maison/Tour,
  quand **Toitures** est également activé.
- La détection des structures reste basée sur leurs **tuiles et hauteurs** :
  pas de nouvelle colonne JSON, pas de migration, pas d'objet technique créé
  en plus des objets tactiques.
- Si une unité vivante se trouve dans l'empreinte ou qu'une case intérieure
  est sélectionnée, **la coupe de toit existante est prioritaire**. Le
  dessin vectoriel sans toit préserve le suivi des acteurs et l'édition.
- Si le PNG ne se charge pas ou que la version Tk ne prend pas en charge
  son format, **retour automatique au rendu vectoriel 3.7.13**.
- Le cache d'images est conservé par zoom, structure et orientation ; aucun
  décodage PNG par case ni recalcul des pixels à chaque survol.

## Limites

Il s'agit d'une **première passe d'assets pixel-art**, conçue pour
l'intégration et les tests d'occlusion. Elle n'est pas une version artistique
finale peinte à la main et ne couvre pas encore remparts, escaliers et ponts.
Les sprites représentent le volume visible des structures ; ils ne changent
ni le `blocked`, ni les unités, ni les règles d'altitude, ni le CT. Les
intérieurs interactifs et les véritables étages jouables restent un jalon
distinct et doivent être spécifiés côté moteur avant de les représenter comme
des lieux réellement accessibles.

## Gates

```sh
python -m unittest discover -s tests_standalone -p test_iso_building_atlas_3714.py -v
python -m unittest discover -s tests_standalone -p test_iso_architecture_3713.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```

La CI doit rester verte sur Linux/Windows/macOS, inclure distribution Python
avec les PNG packagés, et rejeter les frames invalides avant toute promotion
de PR. Vérifier ensuite visuellement le rendu à 24/54/96 pixels et le point de
coupe lors de la sélection d'une unité en intérieur.
