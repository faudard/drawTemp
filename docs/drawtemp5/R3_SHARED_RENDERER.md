# DrawTemp 5 — R3 Shared Renderer : tranche initiale

Référence : [Roadmap 5.0](../DRAWTEMP_5_0_ROADMAP.md#r3) — branche `master`.

## Livraison incluse

- **R3.1 (première tranche)** : un seul `IsoViewport.qml` alimenté par `drawtemp.render.qt_viewport` ; point d'entrée Qt Quick unique pour Studio et Player. Le renderer n'exécute aucun gameplay. Le Studio pourra embarquer `QQuickView` avec `QWidget.createWindowContainer`.
- **R3.2 (socle)** : projection isométrique inversible, altitude du terrain, conversion visuelle et sélection des losanges surélevés.
- **R3.3 (socle)** : pan, zoom borné 40–300 %, ancrage invariant sous la souris et centrage sur la mission.
- **R3.4 (partiel)** : atlas de terrain PNG existant (16 cases sources de 96×48) et culling CPU par bornes visibles. **Pas de batching/chunking GPU certifié**, ni gestion complète des régions sales.
- **R3.5 et R3.6 (partiels)** : terrain, acteurs et objets, ordre de profondeur dérivé du contact au sol. Relief en volumes, bâtiments multi-étages, toitures/coupes et gestion complète d'occlusion restent ouverts.
- **R3.10 (partiel)** : sélection des cases, acteurs et objets, y compris avec zoom/altitude ; sélection des structures détaillées à développer.
- **R3.12 (socle de validation)** : tests unitaires headless et smoke QML logiciel sur Windows/Linux/macOS. **Ce n'est pas une certification de performances GPU.**

Les acteurs et objets ont des silhouettes temporaires. Les sprites de production, animations, VFX, overlays tactiques, streaming d'atlas, caches et hot-reload (**R3.7–R3.9 et R3.11**) font partie des tranches suivantes. Ne pas cocher le **gate R3 complet** sur cette PR.

## Exécuter

Sous Python 3.12, installer les dépendances Qt :

```sh
python -m pip install ".[qt6]"
python -m drawtemp.render.qt_viewport --mode studio
python -m drawtemp.render.qt_viewport --mode player
python -m unittest tests_standalone.test_drawtemp5_r3 -v
```

Les deux lanceurs utilisent **le même renderer et la même scène de référence Jeanne** ; la distinction `--mode` représente le client hôte en attendant le shell Qt R2. `--smoke` ouvre la vue et la referme automatiquement pour la CI. Aucune commande n'altère les fichiers Content/GameProject ni les lanceurs Tk existants.

## Contrat applicatif

```python
from drawtemp.render import scene_from_mission, fingerprint
from drawtemp.render.qt_viewport import create_view

scene = scene_from_mission(content.missions[mission_id], simulation.snapshot())
view, controller = create_view(scene)
# Après une commande R1 ou une édition R5 :
controller.replace_scene(scene_from_mission(content.missions[mission_id], simulation.snapshot()))
```

La fenêtre Qt et son contrôleur doivent être conservés par l'hôte. L'adaptateur crée une **copie de présentation**, pas un nouveau modèle persistant. Les mutations de gameplay passent exclusivement par R1. Les IDs, tuiles et acteurs proviennent du modèle canonique.

## Critères de certification restant à mesurer

1. Remplacer les silhouettes par les atlas d'acteurs/structures, implémenter animations et découpe de toiture.
2. Introduire le batching et les chunks (pas un `Repeater` par tuile à 128² en production), un cache texture et une invalidation locale.
3. Capturer des goldens de chaque vue avec tests d'occlusion/étages et contrôle DPR, Linux/Windows/macOS.
4. Benchmarker une **vraie** GPU pour 32²/64²/128² aux zooms cibles : p50/p95/p99 frame time, CPU/GPU/VRAM, nombre de nœuds visibles, backend Qt, pilotes et matériel.
5. Tester le branchement aux vrais shells R2/R12 dès leur intégration, avec interaction souris/clavier et même scene/atlas dans les deux.
