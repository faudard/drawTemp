# R52.C1 — cache de visibilité CPU borné, parité et mesures p95/p99

**État :** lot P0 de R52.C, indépendant des images B3. Cible : `master` après intégration de R31–R55 via #402. Ne **certifie pas** la gate GPU ou la release R52.

## Ce qui change

Le `TileChunkIndex` R3 existant conserve son calcul des limites visibles par quatre coins, tous les plans de relief extrêmes et la traversée ordonnée des chunks. R52.C1 introduit **seulement un LRU de coordonnées visibles** derrière cette interface, pas un nouvel index spatial ni un deuxième renderer.

- Clé = `(lo_x, hi_x, lo_y, hi_y)` **entiers** de `visible_bounds`. Le zoom, la taille viewport, le relief, la caméra et la projection influencent cette clé via la même fonction de culling R3. Des vues différentes ayant les mêmes bornes reçoivent le même ensemble ordonné de tuiles.
- Valeur = `tuple((x,y))` ; les tuiles elles-mêmes restent dans l'index canonique `tiles`. Le cache ne garde aucune seconde copie de dict de terrain, acteur, QImage, QML, texture ou objet de jeu.
- **Par défaut : 256 KiB estimés** et **16 entrées max**. Chaque coordonnée est facturée 128 octets estimés, avec 128 octets par entrée pour tenir compte des surcoûts Python. Ce n'est **pas une mesure RSS**. Les vues trop grandes ne sont **pas** conservées ; leur rendu réutilise le parcours de chunks antérieur sans perte fonctionnelle.
- Éviction du plus ancien lors de la pression mémoire ou du dépassement du nombre d'entrées ; le retour de `visible_tiles()` est toujours une nouvelle liste dans le même ordre qu'en R3.
- **Invalidation fail-safe sur changement de tile** dans `TileChunkIndex.update()`. Comme les hauteurs modifient l'étendue visible, vider tout le LRU est préférable à une invalidation locale incomplète. Un `update()` sans différence conserve le cache.
- Le renderer partagé expose `visibilityStats` avec hits, misses, evictions, bypasses, entrées, taille estimée et budget. `textureStats` / `TerrainTextureBatches` R3.D demeurent inchangés : ne pas compter la mémoire des QImages CPU comme de la mémoire GPU.

## Mesure comparable CPU

```bash
python -m unittest tests_standalone.test_r52c1_visibility_cache -v
python scripts/benchmark_r52_c1.py --frames 80 --size 128 --output r52c1-cpu.json
```

Le benchmark joue **la même séquence de caméra** dans les modes `isometric`, `top_down` et `side` et compare deux configurations du même code de production :

1. Cache activé (256 KiB / 16 entrées).
2. Cache désactivé avec budget de **1 octet** (aucune coordonnée ne peut être conservée).

Il mesure les distributions CPU p50/p95/p99 sur les opérations `render_items`, les nombres de records visibles, les compteurs du cache et un ratio p95 indicatif. Il vérifie que la **suite ordonnée de records rendus est strictement identique** et interrompt le benchmark en cas de différence. Aucune assertion sur un speedup inventé : un cache petit, un déplacement continuel ou un décor principalement dynamique peuvent réduire voire inverser le gain. Le benchmark de référence R3 `scripts/benchmark_drawtemp5_r3.py` reste utilisable.

## Tests et non-régression

`tests_standalone/test_r52c1_visibility_cache.py` vérifie : réutilisation des mêmes bornes, copie superficielle de la liste, scène intacte, sorties R3 identiques sur trois projections et sur pan/zoom, invalidation après changement de relief, LRU et octets bornés, trop grosses vues, paramètres invalides (dont booléens), quantiles, parité du benchmark et propriété Qt `visibilityStats` en offscreen.

Ce lot ne modifie pas les règles CT ni `GameSession`, le format des projets ni les transitions de campagne, ni les shaders/lightmaps. Pour Qt software/hardware, les timings `render_items` sont **CPU uniquement** : aucune information sur les temps de soumission GPU ou les framebuffers matériels.

## Gates restants pour R52.C2/C3 et release

- Captures R52.B3 : la PR #410 a été **fermée sans fusion** après la fusion de la consolidation #402. Ses captures/goldens devront être récupérés explicitement avant toute certification.
- **R52.C2** : caches textures et atlas, invalidation visuelle matérielle, profiling scènegraph/Qt Quick et stress mémoire/QML.
- **R52.C3** : budgets mesurés avec fenêtres visibles sous GPU réel sur Windows/Linux/macOS, p95/p99 mémoire et temps de présentation, recherche des spikes de resize et changements de zoom, comparaison Studio/Player.
- Gates R50/R51/R52 : suites complètes headless/Qt, référence CT et action/equip/campaign, démonstration scène urbaine 2.5D et parité HUD/picking sur profils de caméra.

**Ne pas basculer en Ready/release uniquement sur un résultat CPU headless ou un workflow sans jobs.**
