# Entity & Event Studio 3.3 — débogueur de chaînes tactiques

**PR dépendante :** #111 (3.0) → #117 (3.1) → #122 (3.2).
Ne pas fusionner directement sur `master` avant les PR précédentes ;
après leur fusion, rebaser et recibler la branche 3.3.

## Parcours dans le Studio

Dans **Graphe des événements** :

1. Choisir un événement d'origine et le scénario *État initial*,
   *Condition vraie* ou *Condition fausse*, ainsi que le tick.
2. **Démarrer debug** construit un `Battle` jetable et charge la chaîne
   d'événements par les véritables `Mission.triggers`.
3. Sélectionner un événement de cette chaîne et activer
   **Point d’arrêt** ; il est exclusivement propre à la session de debug.
4. **Continuer debug** exécute le vrai dispatcher jusqu'au prochain
   point d'arrêt, *avant* les actions du trigger concerné.
5. **Pas suivant** exécute un seul trigger prêt, sans réévaluer son prédicat
   dans une couche parallèle. **Inspecter condition** révèle l'état actuel
   des feuilles et combinateurs ET/OU/NON + références `after`.
6. La chronologie indique les déclenchements, l'ordre, les actions typées,
   les différences avant/après (unités, statuts, danger, objets),
   les conditions empêchant la suite ainsi que les scènes/cinématiques liées.
7. **Arrêter debug** détruit l'état jetable. Une modification de Content,
   un changement de mission ou un Undo/Redo invalide le diagnostic actif.

## Architecture

`rules.triggers.dispatch(battle, *, observer=None, before_fire=None,
fire_limit=None)` est **l'unique moteur tactique**. Ses options, absentes
dans les appels du Player, sont strictement destinées au diagnostic :

- `observer` lit les statuts `waiting`, `condition_false`,
  `composite_false`, `breakpoint` et `fired`.
- `before_fire` permet d'arrêter **avant** la première action.
- `fire_limit=1` permet d'exécuter **un événement** à la fois, dans
  le bon ordre même si la chaîne est stockée C, B, A.
- L'algorithme de cascades garde son budget de passes et les triggers
  `one-shot` du runtime. Aucun second registre ou moteur d'exécution.

Le débogueur `sporebound/event_debugger.py` retient un Battle indépendant
et le journal UI (200 événements maximum). Dans le cas d'une interaction
porte/levier, le vrai `Battle.execute(interact)` est d'abord appelé avec
les triggers temporairement absents de la simulation; les triggers sont
ensuite réinstallés pour l'exécution pas à pas.

**Attention aux replays :** un scénario diagnostique peut positionner
artificiellement le tick ou les unités. Il n'est PAS authentifié comme un
replay du Player. Le rapport indique `replay_verified=None` et
« NON ATTESTÉ ». La fidélité du Player continue d'être prouvée uniquement
par les enregistrements de `GameSession` / `Battle.replay` réguliers.

Les points d'arrêt et les traces **ne sont jamais sérialisés** dans les
JSON de contenu, de projet ou de sauvegarde.

## Tests

```bash
python -m unittest tests_standalone.test_event_debugger_33 -v
python -m unittest tests_standalone.test_event_chains_32 tests_standalone.test_event_condition_tree_31 tests_standalone.test_entity_event_studio_3 tests_standalone.test_event_graph tests_standalone.test_game_session -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_event_graph_gui -v
```

Gate : condition bloquante clairement identifiée, pause exacte avant effet,
pas à pas A→B→C, résultat final identique au dispatcher normal,
undo/redo sans état de debug persistant et rejouabilité du Player inchangée.
