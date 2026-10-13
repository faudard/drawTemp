# Entity & Event Studio 3.1 — arbre des conditions et diagnostic moteur

## Dépendance

**PR empilée sur Entity & Event Studio 3.0 (#111)** : ne pas fusionner
la branche 3.1 sur `master` avant #111. À la fusion de #111, rebaser et
recibler 3.1 sur `master`.

## Édition visuelle des conditions composites

Dans **Graphe des événements → Condition** :

1. Sélectionner l’événement tactique; la condition principale
   (interact/tick/etc.) demeure obligatoire.
2. Créer une condition secondaire avec `+ ET`, `+ OU`, `+ NON`.
3. Dans l’arbre nouvellement visible, sélectionner une feuille ou un groupe.
4. `Remplacer nœud` change une feuille via le formulaire déjà existant.
   `+ ET` et `+ OU` enveloppent la sélection et créent un sous-groupe.
   `Inverser NON` nie le sous-arbre ou supprime la négation existante.
5. `Retirer nœud` supprime la sélection; si un AND/OR ne possède plus
   qu’un opérande, cet opérande remplace automatiquement le groupe.
   `↑ Nœud` et `↓ Nœud` réordonnent les conditions sœurs.
6. Le bouton `Effacer les ajouts` rétablit la condition principale.

L’arbre utilise des **chemins de sélection non persistants**,
pas de nouveaux IDs ni un modèle parallèle. Chaque opération reste
une mutation atomique via `event_graph.py` et `Content.from_dict`,
avec historique existant et validation des opérateurs/feuilles.

## Prévisualisation lisible

`Tester avec le moteur` affiche `✓` ou `✗` pour **chaque feuille et
chaque opérateur**, puis les actions et conséquences réellement constatées.

- Les feuilles utilisent `battle.rules.trigger_conditions`, y compris
  les règles explicitement composées du projet.
- Pour un levier, une **copie jetable** exécute le véritable ordre
  `Battle.execute(interact)` avant le dispatch, sans injecter de faux événement.
- La trace est prise **avant les actions du trigger**, évitant qu’une
  conséquence (statut, apparition, etc.) fausse le diagnostic de sa condition.
- L'exécution réelle et la file de cinématiques/scènes continuent ensuite
  dans le `Battle` isolé puis dans le `GameSession` du Player.
- Un scénario de préparation impossible ne devient jamais artificiellement vrai.

## Tests

```bash
python -m unittest tests_standalone.test_event_condition_tree_31 -v
python -m unittest tests_standalone.test_entity_event_studio_3 tests_standalone.test_event_context tests_standalone.test_event_graph -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_event_graph_gui -v
```

Aucune modification des formats historiques de sauvegarde ni du
manifeste des règles; les nouvelles formes n’existent que dans `when`,
déjà introduit par #111.
