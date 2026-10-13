# Entity & Event Studio 3.2 — chaînes d'événements contextuels

**Dépendance :** PR #111 (Event Studio 3.0), puis PR #117
(arbre et diagnostic 3.1). Cette PR doit rester empilée sur #117
tant que les deux précédentes ne sont pas fusionnées.

## Auteur — parcours sans JSON

Dans **Graphe des événements**, sélectionner un événement existant,
par exemple `chain_middle`. Dans **Événements précédents (chaîne)**,
choisir un autre événement de la mission et cliquer `+ Lier événement`.
Pour retirer une dépendance, sélectionner le même ID et cliquer
`− Délier événement`. Une liste « Attend : ... » résume les preuves requises.

Le bouton **Simuler chaîne** exécute dans un Battle jetable le déclencheur
sélectionné et tous les événements en aval. Le rapport montre :

- les événements effectivement exécutés et leur ordre réel ;
- les événements en attente, avec références encore manquantes ;
- les changements tactiques observés (objets, acteurs, statuts, dangers) ;
- les cinématiques `tactical_event` et scènes `during_tactical_event`
  qu'un véritable déclenchement doit rendre disponibles.

Le graphe ajoute des flèches `après événement` entre les nœuds du modèle
existant, sans sérialiser de graphe visuel distinct.

## Modèle canonique

`Mission.triggers` accepte le champ optionnel `after` :

```json
{
  "id": "chain_middle",
  "condition": "tick",
  "value": 0,
  "after": ["chain_start"],
  "actions": [{"kind": "hazard", "pos": [4, 5], "amount": 6}]
}
```

C'est une condition **ET obligatoire** : le trigger conserve son
prédicat principal (et son éventuel `when` composite). Les événements
référencés doivent avoir été effectivement émis dans `Battle.fired`;
un affichage d'aperçu ou une action hypothétique ne crée jamais cette preuve.

- Références de mission existantes uniquement, sans doublons ni auto-lien.
- Au maximum 8 prédécesseurs par événement et 200 événements dans une
  mission utilisant les chaînes.
- Cycles directs ou indirects refusés dès `Content.validate`.
- Chaque trigger reste **one-shot**. Si un prérequis est émis plus tard
  dans l'ordre sérialisé, `rules.triggers.dispatch` refait des passes
  bornées jusqu'à stabilisation, au même point de commande. **Aucune
  file d'événements indépendante n'est créée**.
- Les contenus sans `after` conservent exactement le parcours
  historique à une passe et le manifeste de règles v1.
- `GameSession` observe les mêmes `Battle.fired` pour les scènes
  et le Player reste responsable des clips cinématiques.

## Scénario de validation

Un événement A émet un signal, B attend A puis modifie une case tactique,
C attend B puis affecte une autre case et déclenche une cinématique / un
dialogue. Les événements sont volontairement enregistrés dans l'ordre
C, B, A pour vérifier l'absence de retard d'un tour.

```bash
python -m unittest tests_standalone.test_event_chains_32 -v
python -m unittest tests_standalone.test_entity_event_studio_3 tests_standalone.test_event_condition_tree_31 tests_standalone.test_event_graph tests_standalone.test_game_session -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_event_graph_gui -v
```

Le replay est vérifié via une vraie session, **pas** via les instantanés
préparés et non journalisés du simulateur. L'aperçu l'indique explicitement.

### Limite

Une chaîne de triggers ne remplace pas la gestion des choix de dialogue :
le pont `during_tactical_event` et les effets narratifs existants
restent responsables des dialogues interactifs.
