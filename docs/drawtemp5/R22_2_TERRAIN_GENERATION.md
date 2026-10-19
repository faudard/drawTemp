# R22.2A — Génération de terrain par biome dans la carte avancée

## Livré

La roadmap **R22.2** complète le R5 existant, qui fournit déjà : pinceaux,
rectangle, lasso, transformations, calques verrouillables et structures/prefabs.
Cette tranche ajoute au Studio Qt une **génération déterministe** :

- Biomes Prairie / Forêt / Roche / Marais (surfaces canoniques uniquement).
- Graine stable et couverture réglable de 1 % à 100 %.
- Cible : carte entière jusqu'à 4096 cellules ou sélection rectangle/lasso.
- Aperçu *sans mutation* avec fantômes colorés via le viewport R3 commun.
- Application en **une transaction R1** ; Undo/Redo et sauvegarde standard.
- Préservation stricte des tuiles déjà éditées, acteurs, objets, structures,
  zones de déploiement, déclencheurs spatiaux, objectifs, reliques, escaliers.
- Protection contre les previews obsolètes (révision et changement de carte),
  les verrous de calques activés après l'aperçu et les résultats vides.

## Invariants

Le résultat d'une case dépend seulement du **seed, biome et coordonnées
globales** ; ni ordre de sélection ni RNG global n'affectent les résultats.
L'algorithme utilise SHA-256 pour une distribution reproductible. La zone
de génération est bornée à 4096 cases par transaction pour éviter une
prévisualisation disproportionnée.

Aucun JSON manuel, nouveau schema, génération d'assets, IA, modification de
règles tactiques ou certification GPU n'est introduit. Le terrain non édité
reste implicite selon les règles R5 et les tuiles « eau » reçoivent le flag
canonique `blocked`.

## Vérification

```sh
python -m unittest -v \
  tests_standalone.test_drawtemp5_r22_terrain \
  tests_standalone.test_drawtemp5_r22_terrain_qt \
  tests_standalone.test_drawtemp5_r5_map \
  tests_standalone.test_drawtemp5_r5_selection \
  tests_standalone.test_drawtemp5_r5_layers
```

Dans le Studio : **Carte → Génération biome…** → choisir graine et biome →
**Prévisualiser** → comparer le fantôme puis **Appliquer** → Ctrl+Z.
Pour une région, sélectionner d'abord au lasso et cocher
« Limiter à la sélection ».

## Hors périmètre de R22.2A

Édition de catalogues de prefabs hors structures R6, routes/liens de monde,
bruit multi-octaves et masque de génération plus avancé, benchmarks GPU
et acceptation « premier jeu complet » R22.14.
