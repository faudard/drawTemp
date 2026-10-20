# R52.B1 — Lumière d'ambiance et caméra dans le renderer partagé

**Statut :** PR empilée sur R52.A (#398) ; périmètre R52.B *partiel*, certification encore NO-GO.

## Design retenu

- `drawtemp/render/ambient_presentation.py` définit les presets vérifiés de zoom pour le contrôleur R3 déjà sélectionné (`isometric` / `top_down`), les filtres d'ambiance validés et un interpolateur déterministe indépendant de `GameSession`.
- `RendererController.setLightingProfile()`, `transitionLighting()`, `advanceLighting()` et `setCameraPreset()` exposent le même pipeline à Studio/Player. Un signal `presentationChanged` distinct permet d'actualiser la teinte sans relancer `render_items()` à chaque frame d'ambiance.
- Les deux vues `IsoViewport.qml` / `TopDownViewport.qml` utilisent le même signal et la même logique de couleur. Le filtre `Rectangle` n'a pas de capture d'événement ; aucun changement à `pickAt()`, `cellAt()`, aux textures, à la collision ni au tick CT.
- L'inspecteur `RenderLookInspector` est accessible depuis le bouton **Aspect 2.5D** de l'éditeur de cartes existant. Il gère réglages de couleur/opacité, niveau jour/nuit, presets de zoom, durée et transitions, avec prévisualisation / application **locale** / abandon de l'aperçu. Il **n'écrit pas** de données dans Content, GameProject ou les sauvegardes.

## Contrats et modes

| Caméra | Statut | Remarque |
|---|---|---|
| Isométrique (large/proche) | disponible | Zoom 0.7 / 1.35, centre monde préservé |
| Top-down (large/proche) | disponible | Zoom 0.8 / 1.5, centre monde préservé |
| Side | **interdit / NO-GO** | Le renderer courant n'a pas de projection side et de picking équivalent certifiés ; afficher le preset comme non disponible plutôt que simuler un second moteur |

La lumière est un **filtre d'ambiance 2D par-dessus la scène**, pas une véritable lightmap. Les options `lightmap` et `shadows` de R52.A restent explicitement non implémentées. Aucun shaders, illumination dynamique, occlusion physique de la lumière, rendu 3D ni nouvelle camera latérale n'est déclaré opérationnel.

## Contrôles

```bash
python -m unittest discover -s tests_standalone -p 'test_r52b_ambient_presentation.py' -v
python -m unittest discover -s tests_standalone -p 'test_r52a_depth_pipeline.py' -v
python -m unittest discover -s tests_standalone -p 'test_drawtemp5_r3.py' -v
python -m unittest discover -s tests_standalone -p 'test_drawtemp5_shared_viewport.py' -v
```

Les tests de R52.B1 incluent schémas fail-closed, interpolation par pas, désactivation side, invariants de caméra, contrôleur Qt et chargement des deux QML. Les tests GUI requièrent PySide6 et `QT_QPA_PLATFORM=offscreen` pour les smokes, **pas une certification GPU**. La présente PR n'affirme aucun résultat vert avant exécution effective.

## Gates complémentaires pour R52.B complet / R52.C

1. Projection side, sélection sur relief et prise en compte des plateformes avec preuves de parité Studio/Player et test monde/écran/picking.
2. Goldens par DPI, profil et backend avec validation humaine ; tests de vraie lumière ou maintien de l'étiquette *ambient-only*.
3. Mesures R52.C CPU/GPU p95/p99 sur machines physiques Windows, Linux et macOS ; mémoire/caches/LOD.
4. Confirmation des gates amont R50/R51 et absence de régression CT/save/replay à partir du contenu témoin Jeanne.

**Déploiement :** ne pas fusionner cette PR tant que #398 n'est pas validée et intégrée dans la branche cible, et tant que le blocage des workflows sans jobs n'est pas compris.
