# R52.B3 — Parité visuelle Qt 2.5D, DPI et références approuvées

**Portée :** extension de R52.B2 par de vrais screenshots issus du renderer R3 Qt Quick, jamais par un painter indépendant, des pixels synthétiques ou une comparaison de QML statique. Cible Git : intégration #402 vers `master`.

## Matrice : 36 vues

- **Modes** : isometric, top_down, side.
- **DPI physiques** : 1, 1.5, 2. Un processus Qt distinct par configuration définit `QT_SCALE_FACTOR` avant import Qt. Toute capture dont le DPR réellement observé ou les dimensions physiques ne correspondent pas est rejetée.
- **Ambiances** : day (phase 0), night (phase 1). L'interpolation et le tint proviennent du même `RendererController` que le gameplay, mais ne font jamais avancer un tick CT.
- **Clients** : Studio = `QQuickWidget` embarquant le QML partagé, Player = `QQuickView` utilisant `create_view`. Les deux consomment le même `fixture_scene`, le même contrôleur/projection et le même `depth_profile`, avec caméra fixe à 640×480. Pour l'ISO, la légende est masquée pour comparer la **scène commune**, pas le chrome applicatif.
- **Références headless** : coordonnées de trois tuiles fixes dans chaque projection. L'élévation de la tuile 4:3 (niveau 2) est figée; un changement fortuit des positions échoue avant le rendu Qt.

Cette parité compare **les deux hôtes du renderer R3**, pas les captures plein écran de tous les panneaux Studio et Player. Les smokes complets des clients R5/R12 restent nécessaires pour le gate final.

## Exécuter et inspecter les captures

```sh
python -m pip install ".[qt6]"
python -m unittest tests_standalone.test_r52b3_visual_goldens -v
python scripts/r52_visual_goldens.py capture --output r52-visual-report
```

Résultat : `r52-visual-report/actual/*.png` (36 images), `metadata/*.json`, `diff/*.png` (heatmaps Studio↔Player), `r52-visual.json`. Le rapport contient les signatures SHA-256, le profil OS/Qt/backend, les erreurs éventuelles, les mesures de pixels et **`hardware_gpu_certified=false`**.

La comparaison du backend logiciel autorise au maximum `max_channel_delta=12` pour une fraction de pixels différents de `0.02`. Une image nulle, entièrement vide, transparente, générée dans le mauvais DPI ou une matrice incomplète **échoue**. Il n'y a ni promotion silencieuse ni golden fabriqué par le test.

## Approbation humaine séparée

Après revue des captures visuelles (représentativité du relief, profondeur du side, teintes, capture Windows/Linux/macOS) :

```sh
python scripts/r52_visual_goldens.py approve --capture r52-visual-report --reviewer "Nom du validateur"
python scripts/r52_visual_goldens.py capture --output r52-visual-strict --require-approved
```

Le manifeste `tests_standalone/goldens/r52/<os>-qt6.8.3-software/manifest.json` est **versionné uniquement lors d'une PR de revue** comprenant les 36 PNG signés SHA-256 et le validateur désigné. Impossible d'approuver une matrice incomplète, un rapport de parité échoué, ou de remplacer une référence déjà approuvée sans une nouvelle PR explicite. Un baseline absent donne `comparison=blocked`, **jamais `pass`**.

Le profil d'environnement exige PySide6/Qt **6.8.3** et le backend **software**. Un autre Qt ou backend doit bénéficier d'un profil et d'une revue distincts. Les goldens R14.5 restent indépendants : aucune altération de leurs seuils/artefacts.

## Ce que B3 ne certifie pas

- Aucun test positif **GPU réel** : en Qt software/offscreen, un succès de comparaison n'est pas la validation du compositing matériel.
- Pas de facettes R6 latérales, lightmaps physiques ou ombres dynamiques, ni de plateforme 3D.
- Les tolérances sur les images ne prouvent pas la lisibilité de chaque HUD/overlay ; revues sur machines réelles et intégration R50/R51 restent requises.
- **R52.C** gardera la responsabilité du culling et des caches, p95/p99 CPU/GPU, et des budgets de ressources tri-OS.

**Gate release R52 : NO-GO** jusqu'à obtention des vraies captures approuvées, de la parité sur tous les backends ciblés, d'une CI exécutée et des validations matérielles.
