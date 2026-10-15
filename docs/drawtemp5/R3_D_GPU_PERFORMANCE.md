# DrawTemp 5.0 — R3.D / GPU & Rendering Performance

**Base :** `master` (R3.B fusionné). **Dépendance d'intégration :** R3.C / PR #265 encore en cours ; R6.2 #247 et R7.B #248 modifient également le viewport commun.

## Implémenté

- **Moins de nœuds QSG :** les cellules de terrain **plates et statiques** sont composées par paquets de **8 × 8** dans un `QImage` puis affichées comme une **texture Qt Quick** par chunk (`image://drawtemp-tiles/...`). Un Repeater de petits groupes remplace les nombreuses formes/images individuelles.
- **Pipeline unique :** `IsoViewport.qml` est conservé par Studio R5, Player R12 et le visualiseur R3. Tous appellent `RendererController.attach_engine()` pour enregistrer la même interface `QQuickImageProvider`. La source tactique reste `scene_from_mission` / `TileChunkIndex`.
- **Exactitude :** relief, murs, arbres, objectifs, dangers, couvert, acteurs et constructions restent des delegates Qt d'origine. La sélection et les overlays réaffichent une tuile détaillée au-dessus de sa texture de fond ; le survol garde son contour. Désactiver la grille dans Studio réactive le rendu unitaire (pour ne pas montrer des contours précalculés incorrects).
- **R3.11 / cycle de vie :** cache CPU LRU de 64 Mio, comptabilité des pixels RGBA réels, limite des images visibles « épinglées », identifiants versionnés, invalidation de chunks voisins en cas de modification des tuiles, purge sur changement de mission/dimensions/atlas. Textures Qt libérées par la destruction des composants ; les politiques GPU propres au pilote restent hors du budget CPU.
- **Contrat inchangé :** `renderer.items` demeure exhaustif, `renderer.displayItems` décrit uniquement les noeuds à afficher ; `renderer.tileBatches` décrit les textures. Aucune mutation gameplay, sauvegarde ou schema de contenu.
- **Fallback sécurisé :** si un chunk est trop lourd pour le budget, il reste entièrement au rendu unitaire : pas de carte trouée ni de croissance CPU non bornée.

Ce système est du **regroupement de textures précomposées en CPU puis affichées par Qt Quick**, pas de l'instancing GPU natif ou un nouveau moteur C++ RHI.

## Validation

```sh
python -m unittest tests_standalone.test_drawtemp5_r3d.R3DContracts -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp5_r3d.R3DQtSmoke -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python scripts/benchmark_drawtemp5_r3d.py --smoke --map-size 64
```

La CI Python 3.10/3.12 vérifie l'index, la politique d'éligibilité, l'invalidation et le budget. Les jobs Qt Linux/Windows/macOS chargent les vrais QML du Studio et du Player et publient `r3d-qt-profile.json`. Les mesures CPU sont distinguées des événements `frameSwapped`.

### Tests sur machine avec GPU réel

Sans définir `QT_QPA_PLATFORM=offscreen` ni `QT_QUICK_BACKEND=software`, lancer sur poste GPU :

```sh
python scripts/benchmark_drawtemp5_r3d.py --map-size 32 --frames 120 --output perf/r3d-32.json
python scripts/benchmark_drawtemp5_r3d.py --map-size 64 --frames 120 --output perf/r3d-64.json
python scripts/benchmark_drawtemp5_r3d.py --map-size 128 --frames 120 --output perf/r3d-128.json
```

Le rapport renseigne backend graphique, nombre de textures/nœuds supprimés, cache CPU, p50/p95/p99 du temps Python de préparation et **intervalle entre présentations** Qt. Les présentations incluent le scheduling/vsync ; ce ne sont **pas** des temps d'exécution GPU obtenus par timestamp. Une vraie certification GPU nécessite captures RHI/profiler matériel, logs pilotes, captures comparées Studio/Player avec goldens DPR et budgets de frames établis. `hardware_gpu_certified` reste donc `false` même sur GPU.

## Intégration R3.C / R6 / R7

Les composants visuels ont été ajoutés autour du Repeater, sans remplacer les delegates existants, afin de limiter les conflits. Les géométries R6 et les sprites R7 restent en pipeline détail (non batchables). Il faut rebaser sur le `master` courant puis rejouer les tests R3/R4/R5/R6/R7/R12 avant fusion. Ne pas fusionner en supprimant les propriétés de cutaway ou de mouvement de R3.C.

## Gates encore ouverts

- Batching GPU natif d'instances/quad avec réduction du CPU raster par rapport aux atlas Qt Quick.
- Stratégie GPU de résidence et mesure précise VRAM/transferts.
- Benchmarks matériels p50/p95/p99 et captures de référence sur PC Windows/Linux/macOS.
- Comparaison à l'œil des couches et des plans d'architecture avec R3.C/R6/R7.

**Conclusion :** optimisation exploitable et instrumentée, **R3 global non certifié**.
