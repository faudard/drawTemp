# DrawTemp 5.0 — R3.C : composition de scènes, toitures et mouvement réel

Suite de R3.B (PR #241 fusionnée), basée sur `master` au 15 octobre 2026.

## Livré dans cette PR

- **R3.5 / R3.6** : projection des surfaces de maison (façades, toiture, planchers de niveaux présents) par le moteur ISO commun. Tri arrière/avant, sélection d'un polygone visible au lieu d'une boîte englobante, zoom/pan identiques dans Studio et Player.
- **Cutaway automatique** : une toiture disparaît lorsque l'acteur vivant entre dans l'emprise du bâtiment, lorsqu'une case du bâtiment est sélectionnée ou lorsqu'un niveau de construction actif est demandé. Les autres toitures ne sont pas masquées. Les niveaux affichés restent des couches visuelles : aucun calcul de combat/LOS/escalier n'est inventé.
- **R3.7 / R12.7** : le déplacement et l'attaque déclenchés par le journal `AnimationDirector` déplacent **le vrai delegate acteur** dans `IsoViewport.qml`. Le Player n'utilise plus son personnage de substitution (`motionGhost`). S'il existe une texture R4 pour l'acteur, c'est cette texture qui se déplace ; sinon le placeholder demeure. Pieds interpolés sur le relief avec correction de hauteur et cycle temporel indépendant du CT.
- **Contrat indépendant** : `drawtemp.render.visual_compositor` fournit interpolation headless, `automatic_cutaway`, `building_surfaces` et `top_building_hit` ; aucune mutation Content/GameProject/Simulation.
- **Tests** : maisons avec/toiture sans cutaway, niveaux, acteurs morts, picking à plusieurs zooms, continuité d'animation, absence de doublon joueur, smoke QML Qt 6. Python 3.10/3.12 et Qt offscreen Windows/Linux/macOS via `drawtemp5-r3.yml`.

## Exécuter

```sh
python -m pip install ".[qt6]"
python -m unittest tests_standalone.test_drawtemp5_r3c.SharedCompositorTests -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp5_r3c.QtR3CSmoke -v
python -m drawtemp.player.qt_app --reference --smoke --smoke-scene battle
```

## Dépendances et réconciliation

Les PR **#247 (R6.2 surfaces détaillées)** et **#248 (R7 sprites directionnels)** étaient encore ouvertes au départ de cette tranche. Cette PR fournit un **fallback de géométrie simple** et l'animation du vrai delegate, mais **ne remplace pas** les surfaces fines et les atlas de production de ces deux lots. Les changements concomitants dans `iso_scene.py`, `qt_viewport.py` et `IsoViewport.qml` devront être réconciliés lorsqu'ils seront intégrés : conserver un seul pipeline de géométrie (préférer les polygones plus complets de R6), une seule texture/sprite et un seul flux d'animation. **Ne pas merger indépendamment ces PR sans ce contrôle.**

La logique d'animation R12.7 produit uniquement des clips après transactions valides ; le rendu R3 ne tire pas de RNG et n'altère pas les sauvegardes ni la consommation de CT.

## Hors périmètre / gate R3 encore ouvert

- Atlas de personnages publiés et cohérence artistique 4 directions : R4/R7, à auditer en intégration.
- Portes/fenêtres dans toutes les orientations, façades et escaliers multi-niveaux avec collision/LOS : R6.2 / R6.10.
- Occlusion GPU pixel-par-pixel, batching/instancing et caches GPU, VFX avancés, textures rechargées à chaud.
- Goldens sur cartes réelles, tests GPU matériel, frame time p95/p99 ; les smokes logiciel Qt et benchmark CPU de R3.B ne constituent pas la certification GPU.

**Statut :** tranche fonctionnelle en revue. Aucun gate R3 global déclaré validé.
