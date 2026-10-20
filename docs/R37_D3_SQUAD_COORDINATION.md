# R37.D3 — Coordination d'escouades : radio, rôles et intentions

**Statut : développement ajouté à la PR #371, CI et certification de gameplay non acquises.**

## Contrat auteur et limites

- Le manifeste unique est `GameProject.extensions['org.drawtemp.advancedai']` ; chaque agent peut recevoir une clé optionnelle `squad: {'id': 'castle_guard', 'role': 'vanguard', 'radio_range': 4}`. Cela ne crée ni base de données d'escouade ni moteur séparé.
- Seuls les PNJ **temps réel** avec capteur et **positions R35 authored** peuvent appartenir à une escouade. Au plus **8 agents par escouade**, avec portée radio entière 0–16 cases par acteur.
- Rôles : `officer`, `vanguard`, `protector`, `flanker`, `archer`, `medic`, `scout`.
- Tous les contrôles passent par `GameProject.validate`. Les projets/slots sans R37 ou sans `squad` conservent leur format.

## Alerte partagée, sans omniscience

- `GameSession.ai_squad_preview('castle_guard')` lit les projections réelles `LivingWorld.npc_pose`, la grille et le blackboard individuels, puis les perceptions R37.D. C'est une **prévisualisation lecture seule**.
- Un membre ayant actuellement `seen` ou `heard` diffuse uniquement à ses voisins **dans la même scène** et **directement accessibles** par chemin R35. Le trajet radio doit respecter la **plus petite portée** émetteur/récepteur ; aucune transmission multi-sauts n'est simulée.
- Les signaux frais sont départagés par la règle `seen` avant `heard`, puis identifiant acteur ASCII trié. Les anciennes mémoires individuelles n'émettent aucun nouveau message radio.
- La cible connue est la position **perçue** ou la dernière position mémorisée **sur cette scène** ; le rapport ne donne pas la position actuelle si elle n'a pas été observée.
- L'ordre partagé n'est pas une commande du Player. La simulation fournit seulement `intent`, `reason`, `route`, `next_step`, `known_pos` et `shared_from`.
- `GameSession.ai_squad_share` est une action explicite : écrit `squad_source`, `squad_signal`, position/scene connue, `suspicion` et `alert` chez les destinataires. Les écritures de plusieurs agents passent par **une opération atomique staged** ; un échec laisse les blackboards et le journal intacts.
- Chaque destinataire refuse une seconde réception au même tick R35. Les journaux sont rejoués à l'ouverture de GameSession. Les champs de provenance ne sont pas accessibles par les écritures libres de `GameSession.ai_remember`.

## Intentions selon le rôle

| Rôle | Proposition calculée |
|---|---|
| Officer | `coordinate`, position conservée tant que l'ordre n'est pas exécuté |
| Vanguard / protector | `protect` : cellule accessible voisine d'un soigneur/archer allié, sinon poursuite |
| Flanker | `flank` : cellule voisine de la dernière cible connue, sans entrer dans un obstacle ni occuper la cellule d'un allié |
| Archer | `cover` à distance, sinon poursuite |
| Medic | `retreat` sur une case améliorant la séparation lorsque menacé, sinon `hold` |
| Scout | `investigate` le dernier signal/position connue |
| Sans cible connue | `patrol`, aucune position cible synthétisée |

Les déplacements et les compétences ne sont **pas exécutés** dans cette phase. Ces propositions doivent ultérieurement passer par les règles canoniques du Player ou de Battle ; elles ne confèrent jamais de bonus tactique caché.

## API

```python
spec = project.extensions['org.drawtemp.advancedai']['data']
spec['agents'][0]['squad'] = {
    'id': 'castle_guard', 'role': 'flanker', 'radio_range': 4,
}
project.validate(content)
game = GameSession.new(content, project, 'main', seed=29)
preview = game.ai_squad_preview('castle_guard') # aucune mutation
delivered = game.ai_squad_share('castle_guard') # mémoires atomiques
```

## Studio

- **Outils → Escouades IA R37.D3** ouvre `AISquadDialog`.
- Sélectionner un PNJ à capteur, affecter un identifiant de groupe, son rôle et la portée de sa radio.
- Valider/Appliquer, suppression du groupe d'un acteur, Undo et Redo passent tous par la transaction canonique `AuthoringSession`.

## Tests et gate

```sh
python -m unittest tests_standalone.test_r37_squad -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r37_squad_qt -v
python -m unittest tests_standalone.test_r37_perception tests_standalone.test_r37_ai_session tests_standalone.test_r37_behavior_tree -v
```

Régressions visées : ordre indépendant du tableau d'acteurs, portée radio et obstacles, absence de partage multi-hop, sauvegarde/replay, forge de mémoire, rollback atomique, typage des rôles, budget 8 acteurs, mouvements proposés non exécutés, Undo/Redo R1 et non-régression CT.

**Non couverts** : émission automatique des alertes à chaque tick, transmission vocale de bout en bout, animations/placements réellement effectués, ordres tactiques CT appliqués, changements de phases boss et validation visuelle du vertical slice. La CI du dépôt n'a jusqu'ici pas produit de jobs pour R37 ; les tests restent donc **non certifiés** jusqu'à exécution effective.
