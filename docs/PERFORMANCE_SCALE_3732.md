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

## 3.7.32B — Latence réelle de callbacks Tk et comparaison avant/après

La suite active un traceur **opt-in**, sans enregistrer le contenu des jeux.

Sous Linux/macOS :

    SPOREBOUND_UI_TRACE=/tmp/drawtemp-ui-trace.jsonl \
      python3 -m sporebound editor

Sous Windows PowerShell :

    $env:SPOREBOUND_UI_TRACE = "C:\temp\drawtemp-ui-trace.jsonl"
    python -m sporebound editor

La variable doit pointer vers un chemin **absolu**. Chaque ligne JSON contient
le nom du parcours, les durées de callback et callback→prochain idle Tk,
et des **compteurs numériques seulement** (cases, ressources, nœuds et items).
Quatre chemins sont instrumentés : \`map.refresh\`, \`workspace.refresh\`,
\`event_graph.draw\`, \`story_graph.draw\`. Le traceur est inactif si la
variable est absente. Il n'écrit jamais les noms des missions, textes
narratifs, IDs d'acteurs ou contenus JSON du projet.

La mesure callback→idle est une approximation de l'attente dans la boucle
événementielle Tk. Elle **n'est pas** une mesure matérielle clic→pixel,
et peut être contaminée par des callbacks concurrents. Toute comparaison
doit isoler le même parcours, le même contenu et des actions répétées ;
il ne faut pas confondre temps du callback et temps de composition écran.
Le coût de traçage lui-même est un biais, à estimer avec l'instrumentation
désactivée.

Comparer deux rapports structurés des mêmes scènes :

    python scripts/compare_profile_scale_3732.py \
      baseline.json candidate.json \
      --output comparison.json --markdown comparison.md

Ce comparateur exige le même Python/OS/Tk/CPU logique, les mêmes paramètres
et le même jeu de scénarios. En cas de différence d'environnement, l'option
\`--allow-host-mismatch\` sert uniquement à examiner les résultats : pas
à certifier une régression. L'affichage comprend les deltas absolus/relatifs
p50/p95/p99 et les compteurs mémoire/Canvas quand disponibles.

Un seuil bloquant est **strictement optionnel**, après calibration locale :

    python scripts/compare_profile_scale_3732.py \
      baseline.json candidate.json \
      --block-p95-pct 15 --block-min-ms 2

Ceci n'est qu'un **exemple de syntaxe** et non un budget recommandé. En l'absence
d'options \`--block-*\`, la comparaison n'échoue pas en raison des seules
différences de vitesse. Des incompatibilités de schéma, scénarios et paramètres
font échouer la comparaison afin d'empêcher des gains artificiels.

À poursuivre après capture des données : diagnostic de la consommation
native par plateforme (RSS seul insuffisant), instrumentation de l'entrée
utilisateur, segmentation modèle→rendu→Tk idle, validation des graphes par les
éditeurs réels et tests de vieillissement sur plusieurs heures.


Agréger les traces réelles par opération et niveau de complexité :

    python scripts/summarize_ui_trace_3732.py \
      /tmp/drawtemp-ui-trace.jsonl --output perf-ui-summary.json

Le script sépare notamment les tailles de carte (\`map_cells\`), le nombre
de ressources (\`resource_nodes\`) et les nœuds des graphes. Pour chacun,
il calcule le p50/p95/p99 de callback, callback→idle et temps d'attente
idle ; les groupes de moins de 100 échantillons restent exploratoires.
Ne pas fusionner des scènes de tailles différentes dans un même percentile.
