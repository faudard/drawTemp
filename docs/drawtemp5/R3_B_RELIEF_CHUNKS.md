# DrawTemp 5.0 — R3.B : relief, chunks et overlays

**Base :** `master` après fusion de la PR #237. **Cible :** lots R3.4, R3.5, R3.9 et R3.12 de la [roadmap 5.0](../DRAWTEMP_5_0_ROADMAP.md#r3). Le gate complet R3 reste **ouvert**.

## Implémentation réelle

- **R3.4 — Index spatial :** `TileChunkIndex` regroupe les cellules par chunks de 16×16 et conserve les données visuelles en mémoire. Le rendu pan/zoom interroge les chunks traversant le champ de caméra, sans refaire une passe exhaustive sur les 128² cases. `update(scene)` renvoie les coordonnées modifiées et actualise uniquement les cellules concernées dans chaque chunk. Ce n'est **pas** un batching GPU.
- **R3.5 — Relief :** les tuiles élevées dessinent deux faces verticales là où les voisines est/sud sont plus basses. Les profondeurs et les couleurs sont déterminées par l'unique projection isométrique ; les deux hôtes Qt partagent le même composant QML. Relief sans nouveaux assets obligatoires.
- **R3.9 — Overlays temporaires :** `reachable`, `path`, `los`, `range`, `cover`, `danger`, `intent`, `objective`. Ils sont des `[x,y]` visuels, détachés de Content et de la simulation. Les aperçus sont effacés par défaut à chaque nouvelle scène pour éviter une intention ennemie périmée.
- **R3.12 — Diagnostics CPU :** `scripts/benchmark_drawtemp5_r3.py` mesure les temps p50/p95/p99 de la projection des scènes 32², 64², 128², enregistrés par la CI. Ce n'est pas une mesure de frame time GPU, ni un gate 60 FPS.

## Contrat des intégrateurs Qt

```python
from drawtemp.render.iso_scene import scene_from_mission
from drawtemp.render.qt_viewport import make_controller

scene = scene_from_mission(mission, simulation.snapshot())
renderer = make_controller(scene)
renderer.setOverlays({
    "reachable": [[2, 3], [3, 3]],  # calculé par les règles existantes
    "danger": [[4, 3]],
})
renderer.clearOverlays()
# Lorsque la session évolue, ne conserver aucun overlay de l'ancien tour :
renderer.replace_scene(scene_from_mission(mission, simulation.snapshot()))
```

Les overlays sont validés avant mutation; un type inconnu, une case hors carte ou une coordonnée non entière produit `ValueError` sans effacer l'ancien aperçu. La sélection R5/R12 conserve son contrat `cellAt`, `selectCell`, `pickAt`; aucun changement de schéma/sauvegarde.

## Validation automatisée

```bash
python -m unittest tests_standalone.test_drawtemp5_r3b.ChunkAndLayerTests -v
python -m unittest tests_standalone.test_drawtemp5_r3b.QtRendererR3BSmoke -v
python scripts/benchmark_drawtemp5_r3.py --frames 80 --output r3-cpu.json
```

La CI exécute la géométrie, les snapshots, les chunks, la parité Studio/Player, les overlays, et les smokes Qt réels sur trois OS (rendu logiciel hors écran).

## Limites et prochaines tranches

1. **R3.4 :** vrai atlas texture batching/instancing GPU et dirty-region Qt Quick (le Repeater recrée encore la liste des nodes visibles quand la caméra change).
2. **R3.6 :** couverture bâtiment, toiture/cutaway, occlusion acteur derrière murs, étages multiples, picking des différentes parties.
3. **R3.7–R3.8 :** sprites animés directionnels, eau/feu/météo/particules/ombres.
4. **R3.9 :** branchement effectif des calculs tactiques R1/R12 sur les overlays ; les exemples de cette PR sont purement présentation.
5. **R3.11–R3.12 :** gestion mémoire GPU, refresh atlas, goldens visuels, mesures sur vraies cartes graphiques, captures et rapport de profilage multiplateforme.

**Ne pas déclarer la certification R3 terminée** tant que ces gates ne sont pas satisfaits.
