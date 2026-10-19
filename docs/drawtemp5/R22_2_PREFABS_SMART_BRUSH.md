# R22.2B — Terrain Prefab Shelf & Smart Brushes

Ce lot est **empilé sur R22.2A (#315)**. Il utilise le même Studio Qt
et le même renderer Qt Quick R3, sans dupliquer les ateliers d'objets R6.

## Fonctionnel

- **Bibliothèque terrain** : quatre motifs intégrés (carrefour, étang,
  bosquet, campement), catégories, recherche, aperçu fantôme existant R5.
- **Personnalisation** : sélectionner une région rectangle/lasso, mémoriser
  un motif nommé sans acteur/objet/structure, exporter/importer explicitement
  une bibliothèque JSON versionnée de modèles personnels.
- **Transformations** : rotation et miroir des motifs, via le
  TerrainClipboard et le MapSelection déjà présents dans R5.
- **Placement** : choisir un motif, survoler le terrain, vérifier
  collisions, appliquer. Un placement = une seule transaction
  AuthoringSession, avec Undo/Redo.
- **Pinceau intelligent** : rayon 0–3, forme carré/losange, interpolation
  Bresenham d'un trait rapide, masque optionnel sur sélection/lasso.

## Garde-fous

- Le catalogue est **terrain-only**. Le système existant
  sporebound/group_prefabs.py reste responsable des groupes complexes,
  structures, acteurs, zones d'étages et IDs métier.
- **Jamais de duplication silencieuse** des identités, interactions,
  scripts, déploiements ou événements. Le R5 MapSelection interdit les
  collisions sur zones protégées et les prévisualisations obsolètes.
- R1 Preview/Apply gère toujours le document canonique, aucun format de
  mission nouveau. Les verrous de calques sont **revérifiés au commit**.
- L'import/export concerne uniquement un **fichier auteur explicite**,
  non un export de runtime. Version, structure, surfaces, coordonnées et
  bornes validées ; maximum 64 modèles et 2 MiB par bibliothèque.
  Export create-only atomique ; un nom/fichier préexistant n'est pas écrasé.
- Les modèles personnels sont en mémoire pendant la session ; pour les
  conserver et les rouvrir après redémarrage, utiliser Exporter/Importer.
  **Ce lot ne prétend pas** fournir une bibliothèque d'assets projet
  synchronisée ou un gestionnaire multi-utilisateur (R22.12).

## Tests

En environnement Python 3.12 + PySide6 6.8.3 :

~~~sh
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
python -m unittest -v \
    tests_standalone.test_drawtemp5_r22_prefabs \
    tests_standalone.test_drawtemp5_r22_prefabs_qt \
    tests_standalone.test_drawtemp5_r22_terrain \
    tests_standalone.test_drawtemp5_r22_terrain_qt \
    tests_standalone.test_drawtemp5_r5_map \
    tests_standalone.test_drawtemp5_r5_selection \
    tests_standalone.test_drawtemp5_r5_selection_qt
~~~

Validation humaine : créer une carte, peindre des chemins et un étang,
copier au lasso un motif personnel, exporter sa bibliothèque, la réimporter,
déplacer/retourner une copie par preview, annuler puis relancer. Vérifier
qu'une tuile peinte et qu'une unité occupée refusent la pose.

### Non certifié par ce lot

GPU physique, étages et groupes complets, benchmark large carte, export
autonome Player, l'acceptation finale R22.14 « premier jeu complet ».
