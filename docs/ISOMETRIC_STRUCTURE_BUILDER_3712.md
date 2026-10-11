# 3.7.12 — Structures multi-cases dans le Map Builder isométrique

Ce jalon ajoute une palette de **plans de structures** construits à partir du
terrain et des props déjà présents. Il ne crée pas encore de sprites géants de
bâtiments ou de nouveaux objets tactiques.

## Utilisation

Dans **Carte et combat**, utiliser la ligne **Structures multi-cases** :

1. Choisir `Maison`, `Tour`, `Rempart`, `Escalier`, `Pont` ou `Ruines`.
2. Appuyer sur **Poser structure** (ou simplement choisir un modèle).
3. Survoler la carte : le périmètre apparaît **vert** si l'emplacement est permis,
   **rouge** si la construction sortirait du plateau, recouvrirait une entité ou
   écraserait un objectif.
4. Orienter avec **↻ Bâtiment** / **↺ Bâtiment** (quarts de tour de 90°).
5. Cliquer pour placer toutes les cases **dans une seule transaction**, puis
   utiliser les boutons d'annulation/rétablissement existants.

Les outils fonctionnent aussi en vue isométrique 2.5D ; l'aperçu suit le
hit-testing des cases surélevées. Les dimensions sont mises à jour après rotation
(ex. rempart de 5×1 à 1×5).

## Modèles intégrés

| Modèle | Dimensions originales | Composition |
| --- | --- | --- |
| Maison | 4×3 | Murs en pierre, sol et ouverture praticable |
| Tour | 3×3 | Murs de pierre et escalier intérieur |
| Rempart | 5×1 | Segment de mur haut et bloquant |
| Escalier | 2×4 | Niveaux successifs 0–3, passages ouverts |
| Pont | 3×2 | Surfaces bridge, passables et raccordées à l'eau |
| Ruines | 4×3 | Fondations, segments de murs et ruines |

Les plans emploient la représentation `TerrainClipboard` et sa rotation
`transform_terrain`. La pose passe par `paste_terrain` et la validation
du `Content` ; elle ne contourne donc pas les règles de carte.

## Intégrité du projet

- Aucun nouveau champ ni migration de fichier `Content`, aucune modification
  de carte existante avant que l'utilisateur place un modèle.
- Les unités, leurs empreintes multi-cases, les objets interactifs, les objectifs
  de mission et les reliques ne sont jamais écrasés par une structure.
- Un mur de structure ne remplace pas une case de zone de déploiement.
- Une pose illégale est rejetée sans changement partiel de la carte ou de
  l'historique undo/redo.
- Le moteur tactique, l'IA, le Player headless, les replays et les coordonnées
  restent inchangés.
- Les surfaces, décors et altitudes de la zone visée sont **volontairement
  remplacés** par le plan choisi, comme lors d'un collage de tampon de terrain.
  Les objets et unités ne sont ni copiés ni déplacés.

## Gates

```sh
python -m unittest discover -s tests_standalone -p test_iso_structures_3712.py -v
python -m unittest discover -s tests_standalone -p test_iso_map_builder.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```

Tester en particulier la rotation Maison 4×3 → 3×4 en 2D, la prévisualisation
avant pose, le passage d'un pont en vue iso, le round-trip JSON, l'annulation,
les zones d'occupation et les matrices Python Linux/Windows/macOS.

### Limite artistique

Il s'agit de **plans de maçonnerie** à base de tuiles et de décors disponibles.
Les façades complètes, toitures, tours massives, occlusion avancée, pivots
d'assemblages et bibliothèques de structures peintes restent des travaux
ultérieurs. Le terme « maison » ne signifie donc pas encore un bâtiment
3D ou un sprite unique.
