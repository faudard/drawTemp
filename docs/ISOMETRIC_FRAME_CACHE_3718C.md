# 3.7.18C — Cache des frames isométriques en combat

## Problème

La vue Player 3.7.18A/B partage les atlas avec l'éditeur et affiche les
personnages animés, mais le canvas était **effacé intégralement** toutes les
60 ms pendant une interpolation : sols, rivières, reliefs, décors, bâtiments,
menaces et acteurs étaient recréés même lorsque seule la position visuelle
d'un personnage changeait.

## Mise en œuvre

`IsoBattleCanvas` conserve le snapshot graphique courant et réutilise la
scène pendant les seuls ticks de `MotionDirector` :

1. Le premier rendu ou changement pertinent appelle toujours
   `render_isometric`, construit la scène complète et mémorise sa géométrie.
2. Une nouvelle frame d'animation utilisant **le même BattleFrame**
   déplace uniquement les groupes de personnages `iso_actor_unit_N`
   avec `canvas.move` en coordonnées fractionnaires, interpolées sur le
   relief. Aucun terrain ni overlay n'est recréé.
3. Le classement de profondeur des acteurs et des structures reste recalculé
   pour permettre le passage devant/derrière les façades.
4. Si une empreinte animée traverse un seuil de toiture, la signature de
   coupe change : une reconstruction volontaire retire/rétablit le toit.
   Le reste du déplacement reprend ensuite le chemin léger.
5. Tout nouveau snapshot (même avec contenu identique), changement de plateau,
   caméra/zoom, dimensions du viewport, ordre des acteurs ou changement de
   coupe invalide le cache. Les sélections, menaces et résultats sont portés
   par le BattleFrame : ils ne peuvent donc pas rester figés après changement.
6. `dispose()` libère les références à l'ancien snapshot et les caches
   d'atlas. L'historique du jeu n'est jamais modifié.

Les compteurs d'observabilité `_scene_rebuilds` et
`_actor_only_frames` permettent de vérifier les économies de redraws.

## Tests et mesure

```sh
python -m unittest discover -s tests_standalone -p test_iso_frame_cache_3718c.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_iso_frame_cache_3718c_gui.py -v

# Mesures Tk réelles, deux modes avec mêmes cartes et poses
xvfb-run -a python3 scripts/benchmark_iso_frame_cache_3718c.py \
  --sizes 32,64,128 --frames 5
```

Le benchmark affiche `full_p50_ms/full_p95_ms` pour une reconstruction
complète et `cached_p50_ms/cached_p95_ms` pour le même snapshot animé avec
cache. Il neutralise les PNG afin d'isoler le coût du Canvas, rapporte des
mesures **indicatives propres à la machine** et ne prétend pas démontrer un
budget cible universel. Le job CI exécute 32² et 64² ; 128² reste une
mesure reproductible manuelle afin de ne pas pénaliser chaque PR.

## Contraintes préservées

- Pas de changement de `Battle`, `Content`, cartes, IA, CT, mouvement
  autorisé, dégâts, sauvegarde ou replay.
- Le Player orthogonal et l'éditeur isométrique conservent leurs APIs.
- Aucun nouveau PNG ni dépendance lourde.
- Les menaces, la sélection et l'occlusion sont priorisées par la justesse
  plutôt que par une réutilisation invalide d'items.
- La scène reste entièrement reconstruite lorsque des entités changent de
  manière significative (nouveau `BattleFrame`) : l'optimisation est
  **ciblée sur les frames intermédiaires d'animation**, pas une promesse de
  cache permanent pour toutes les éditions.

## Suites

3.7.18D pourra séparer également les couches terrain et overlay lors des
changements de sélection tactique ; la présente PR ne change volontairement
pas leur cycle d'invalidation. Examiner ensuite le budget mémoire sur des
cartes très denses et les effets multi-étages.
