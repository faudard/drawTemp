# 3.7.32C — Studio fast paths : Workspace et graphes

La PR #119 vient d'être fusionnée : les fast paths sont présents dans master.
Cette PR de suivi ajoute des mesures **avant/après** de leurs chemins réels,
sur le même processus et avec les mêmes données, et renforce le gate de parité.

## Mesures reproductibles

Sous Linux avec Tk/Xvfb :

    python3 -m unittest tests_standalone.test_workspace_cache_3732c -v
    SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest -v \
      tests_standalone.test_retained_event_graph_3732c_gui \
      tests_standalone.test_event_graph_gui

    # Profilage smoke (5 mesures, p99 non représentatif)
    xvfb-run -a python3 scripts/benchmark_studio_fastpaths_3732c.py \
      --quick --output fastpaths-smoke.json

    # Machines de référence, 100 mesures minimum
    xvfb-run -a python3 scripts/benchmark_studio_fastpaths_3732c.py \
      --resources 200 --events 160 --samples 100 \
      --output fastpaths-reference.json

Le benchmark mesure en millisecondes p50/p95/p99 pour deux comparaisons :

- **Workspace** : validation Content puis construction de StudioIndex et
  recherche, face à WorkspaceModelCache réutilisé avec empreinte des valeurs.
- **Canvas des événements** : dessin complet forcé, face au rendu conservé
  pour une simple sélection. Les deux modes appellent le même renderer
  EventGraphStudio et le même modèle event_graph.

Les valeurs ne couvrent pas toute la durée clic-vers-écran, ni la composition
matérielle du rendu. Les résultats du smoke CI ne sont pas un budget temps.

## Corrections fonctionnelles exigées

- Mutation en place de Content/GameProject : invalidation de l'index.
- Échec de validation : dernière projection valide conservée.
- Recherche et références : sémantique et ordre identiques à l'ancien code.
- Sélection simple : conservation des identifiants Canvas.
- Aperçu : couleurs de condition et d'action correctes.
- Modifications d'action, zoom et item externe : retour au rendu complet.
- Parité : types, coordonnées, tags, ordre de peinture et options Canvas.
- Les sauvegardes, replays, règles tactiques et modèles JSON ne changent pas.

## Prochain chantier

La construction de la projection événementielle continue de parcourir les
triggers et l'empreinte du Workspace continue de sérialiser l'état actuel.
Les travaux suivants doivent mesurer le coût des panneaux Studio, le refresh
de l'inspecteur, la grande carte ISO et la mémoire de longues sessions.
Aucune optimisation n'est acceptée sans mesures comparables ni parité.
