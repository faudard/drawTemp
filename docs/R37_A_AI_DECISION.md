# R37.A — Advanced AI : contexte, blackboard et décisions explicables

**Statut : implémentation proposée en PR, non certifiée R37 / 7.7.**
Référence : [Roadmap R37](DRAWTEMP_7_1_TO_8_0_DETAILED_ROADMAP.md#9-r37--advanced-ai-studio-77).

## Périmètre du lot

- **R37.1 (socle P0)** : AI Decision Context v1 (acteur, mode CT/temps réel, seed, tick fixe, faits scalaires) et blackboard v1 par acteur, sérialisable en JSON. Mise à jour immuable par copie et tick monotone ; schémas inconnus refusés.
- **R37.3 (premier moteur headless)** : politiques déclaratives `when` / `terms` avec scores entiers pondérés ; rapport de tous les candidats admis ou exclus, et digest SHA-256 canonique.
- **R37.8/R37.9 (fondations)** : limites de charge, validation stricte, fallback explicite, diagnostic des raisons, interdiction d'exécuter scripts ou callbacks depuis une policy.
- API SDK publique `ai-decision.v1` sans dépendance Qt/Tk.

Ce lot est **opt-in**. `sporebound.ai`, `sporebound.coordinated_ai`, le combat CT et les anciens checkpoints ne sont pas modifiés. L'évaluateur produit une **proposition**, jamais une commande effectivement exécutée : les règles canoniques du moteur restent souveraines.

## Exemple : un garde suit son ennemi

```python
from drawtemp.sdk import new_blackboard, update_blackboard, evaluate_decision

context = {'schema_version': 1, 'actor_id': 'guard_1', 'mode': 'realtime',
           'tick': 120, 'seed': 42,
           'facts': {'enemy_visible': True, 'distance': 2, 'hp': 20}}
board = update_blackboard(new_blackboard('guard_1'), {'alert': 1}, tick=100)
policies = [
    {'id': 'patrol', 'action': 'patrol', 'base': 5,
     'when': {'enemy_visible': False}, 'terms': {}},
    {'id': 'retreat', 'action': 'flee', 'base': 6,
     'when': {'enemy_visible': True}, 'terms': {'hp': -1}},
    {'id': 'chase', 'action': 'chase', 'base': 3,
     'when': {'enemy_visible': True},
     'terms': {'distance': -1, 'blackboard.alert': 6}},
]
report = evaluate_decision(context, board, policies)
assert report['action'] == 'chase'
assert report['score'] == 7  # 3 - 2 + 6
print(report['candidates'])  # pondérations et exclusions explicables
```

Le score n'est pas une probabilité. La seed est conservée pour la traçabilité ; cet évaluateur n'utilise aucun hasard. Les faits et la mémoire ne sont pas une deuxième simulation et doivent être lus du moteur au tick indiqué.

## Sécurité, replay et limites

- Les snapshots JSON sont strictement versionnés, sans champs inconnus, sans flottants ni valeurs exécutables ; booléens distincts des entiers, IDs ASCII minuscules.
- 64 faits, 64 valeurs mémoire, 64 candidats, 16 tests/16 termes au maximum par policy. Pondérations entières ±1024, valeurs bornées à ±1 000 000, score limité à ±2³¹−1.
- Égalité des conditions typée ; terme manquant ou non numérique => exclusion et raison explicite, jamais zéro inventé. Classement déterministe par identifiant à score égal.
- Blackboard isolé par acteur, horodatage monotone, snapshot futur interdit. La persistence dans `GameSession` n'est pas encore raccordée : le prochain lot intégrera son checkpoint canonique plutôt que créer un format de sauvegarde parallèle.
- Aucun arbre de comportement visuel, système de perception, pathfinding multi-genre, coordination, boss ni intégration Studio/Player dans cette PR. **Gate global R37 non satisfait.**

## Validation

```sh
python -m unittest tests_standalone.test_r37_ai_decision -v
python -m unittest tests_standalone.test_drawtemp_r31_logic_graph -v
```

La CI dédiée exécute les tests headless sur Linux, Windows et macOS (Python 3.12), sans revendiquer une certification Qt/GPU.

## Ordre de développement

1. **R37.B** : adaptateurs de faits Player + snapshot blackboard dans `GameSession`, replay et opt-in sans régression Jeanne/CT.
2. **R37.C** : behavior trees bornés et éditeur visuel avec undo/redo, débogage des nœuds.
3. **R37.D** : perception, LOS/bruit, navigation via adaptateurs existants, coordination et patterns de boss.
4. **R37.E** : AI Debugger, dataset multi-genres, certification de replay et vertical slice boss.
