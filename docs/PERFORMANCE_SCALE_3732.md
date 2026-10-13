# 3.7.32 — Performance & Scale : matrice reproductible

Cette tranche **instrumente** les chemins réels du Studio et du Player. Elle
ne déclare **aucune optimisation acquise** et ne change ni les modèles de jeu,
ni le format des sauvegardes, ni le renderer. Les budgets bloquants seront
décidés après un baseline sur des machines de référence.

## Couverture

| Domaine | Dimensions | Chemin réel | Mesure |
| --- | --- | --- | --- |
| Cartes Studio | 32², 64², 128² | benchmark_editor_render_3718d, EditorRenderCache, renderer ISO | refresh, peinture, sélection, zoom, hauteur, undo/redo, items Canvas |
| Zoom | 24 / 54 / 96 px | Même renderer ISO | p50/p95/p99, items Canvas |
| Acteurs Player | Jeanne authentique + projection visuelle à 80 acteurs | benchmark_player_canvas_376, CanvasRenderer | frame + Tk event pump, items, caches |
| Projets | 200 missions + 50 campagnes validées | Content, GameProject, StudioIndex | index, recherche, validation |
| Graphes | 160 triggers + 160 scènes reliées | build_event_graph, build_story_tree | construction/layout, nœuds, troncature |
| Sauvegardes | 5 puis 60 sauvegardes + historique | StudioHistory, StudioTransactionStore | durée de session, allocations et publication réelle |

Le JSON rassemble l'environnement, le SHA de Git, les paramètres, les
échantillons, p50/p95/p99, RSS du processus et mémoire Python tracée.
Le RSS **englobe** Python et les bibliothèques natives ; ce n'est pas
un compteur exclusif du tas natif. Sur macOS, le repli via resource donne un
**pic**, pas une valeur instantanée. tracemalloc exclut les allocations Tcl/Tk.

Les mesures de mémoire headless sont faites dans une passe séparée.
La première itération headless est un échauffement. Le benchmark Editor
mesure le draw + update_idletasks() : il ne couvre pas le clic→pixel complet.
Le Player inclut un pompage de la boucle Tk. Chaque scénario GUI est exécuté
dans un processus propre, afin de limiter les effets entre caches.

Les 80 acteurs sont une **projection visuelle de stress** ; le benchmark
vérifie que Battle n'est pas muté. Les ressources de Studio sont issues
de Content et GameProject validés. Les graphes utilisent les projections
canoniques : aucun nouveau système événementiel n'est introduit.

## Exécution

Sur Linux avec Tk/Xvfb :

    # Smoke CI : contrôle d'instrumentation, non représentatif
    python3 -m unittest tests_standalone.test_profile_scale_3732 -v
    xvfb-run -a python3 scripts/profile_scale_3732.py \
      --quick --frames 5 --samples 5 --output perf-smoke.json

    # Baseline complet : 3 cartes × 3 zooms + PNG + acteurs 0/80,
    # projets, graphes et sessions ; au moins 100 itérations
    xvfb-run -a python3 scripts/profile_scale_3732.py \
      --frames 100 --samples 100 --assets --output perf-baseline.json

    # Headless sur Windows/macOS
    python scripts/profile_scale_3732.py --phase headless \
      --samples 100 --output perf-headless.json

On peut restreindre sizes/cells/phase et ajuster frames/samples, tout en
conservant les paramètres dans le rapport. La matrice 128² × 96 px et les
sessions longues sont coûteuses : **ne pas** les imposer à chaque push.
Pour comparer deux commits, rejouer les mêmes scénarios/versions Python-Tk
sur le même matériel et avec les mêmes réglages (y compris PNG).

Une estimation p99 avec 5 ou 20 mesures est peu stable :
**100 répétitions minimum**, puis plusieurs runs indépendants pour comparer
les queues de distribution.

## Gate de livraison

1. CI : scripts exécutables, JSON archivé, tests de contrat et de non-mutation.
   **Aucun budget de temps codé dans les assertions.**
2. Visuel : conserver les tests GUI du cache éditeur
   (test_editor_render_cache_3718d_gui), de fidélité Editor/Player
   (test_visual_fidelity_art_372_gui) et les tests du Player.
   Comparer les captures aux trois zooms avec murs/toits/occlusion.
3. Référence : archiver un baseline daté **par OS et machine**, Python/Tk,
   mode PNG et SHA de commit. Comparer avant/après à environnement identique.
4. Après les mesures seulement : fixer les budgets bloquants p95/p99,
   latence utilisateur réelle, RSS, nombre d'items Canvas, validation,
   sauvegardes et comportement en session prolongée.
5. Ne pas annoncer d'optimisation si gain non reproductible, divergence
   visuelle/fonctionnelle, fuite mémoire ou changement de périmètre mesuré.

## Limites

- Les clics UI réels, la construction d'arbres Tk massifs et la latence totale
  d'interaction de tout le Studio demandent une instrumentation complémentaire.
- Le rendu Editor et le rendu Player n'ont pas exactement le même périmètre
  chronométré ; on ne doit pas les comparer directement comme deux modes
  interchangeables d'un même benchmark.
- Le smoke CI ne vaut **pas** un baseline certifié. Aucun gain chiffré global
  ni baseline multi-OS n'est affirmé tant que les runs de référence n'existent.
- Le benchmark nettoie ses fichiers temporaires et ne modifie pas les
  documents de l'auteur.
