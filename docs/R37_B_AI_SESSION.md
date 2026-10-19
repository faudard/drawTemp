# R37.B — IA du Player : faits canoniques et mémoire persistée

**État : développé dans la PR #371 ; certification CI et R37 global à confirmer.**

## Intégration au jeu sans second moteur

- `GameProject.extensions['org.drawtemp.advancedai']` reste l'unique document d'authoring de politiques. L'enveloppe R24 `schema_version=1, data, references` est vérifiée par `GameProject.validate`.
- `sporebound.advanced_ai.AdvancedAI` stocke les blackboards dans `GameSession`, pas dans Qt, le journal de combats ni un fichier latéral.
- Pour le monde R35, un acteur `realtime` doit référencer un PNJ authored, avec une activité et une scène issues de la projection canonique de l'horloge du monde. L'option `distance` est fournie uniquement lorsqu'il existe deux positions sur la même scène.
- En tactique, un acteur `ct` se réfère à une unité effectivement présente dans le combat en cours. Ses faits viennent de Battle (`hp`, présence d'opposants, distance), et son horloge est `Battle.tick` ; les décisions sont seulement prévisualisées.
- `ai_decision_preview(actor_id)` renvoie un rapport déterministe des scores et rejets. **Aucune action n'est exécutée** : ni `Battle.execute`, ni déplacement de PNJ, ni modification d'une quête.
- `ai_remember(actor_id, changes)` est limité aux PNJ temps réel dans une scène active. Les écritures CT restent interdites tant qu'une mémoire propre à chaque rencontre et son replay ne sont pas certifiés.

## Exemple de manifeste

```python
from sporebound.advanced_ai import EXTENSION

project.extensions[EXTENSION] = {
    'schema_version': 1,
    'data': {'version': 1, 'agents': [
        {'id': 'merchant', 'mode': 'realtime', 'policies': [
            {'id': 'open', 'action': 'trade', 'base': 10,
             'when': {'activity': 'trade', 'blackboard.alert': True},
             'terms': {}},
            {'id': 'rest', 'action': 'rest', 'base': 2,
             'when': {'activity': 'sleep'}, 'terms': {}},
        ]},
    ]},
    'references': [],
}
project.validate(content)
session = GameSession.new(content, project, 'main', seed=42)
session.ai_remember('merchant', {'alert': True})
decision = session.ai_decision_preview('merchant')
```

L'acteur `merchant` suppose une extension `org.drawtemp.livingworld` déjà valide contenant ce PNJ. La politique ne remplace jamais les décisions du Player : elle est un contrat testable avant branchement volontaire de l'exécution.

## Checkpoint, replay et compatibilité

Quand R37 est activé, le **checkpoint `GameSession` v1 existant** ajoute `advanced_ai` :

```json
{
  "version": 1,
  "blackboards": {
    "merchant": {
      "schema_version": 1,
      "actor_id": "merchant",
      "updated_tick": 0,
      "values": {"alert": true}
    }
  },
  "history": [{"actor_id": "merchant", "tick": 0,
               "changes": {"alert": true}}]
}
```

- Les écritures sont bornées à 2 048 par checkpoint, atomiques et monotones ; une écriture invalide n'ajoute rien.
- Le chargement reconstruit **tous** les blackboards en rejouant cet historique et compare les snapshots. Les ticks mémoire temps réel sont bornés par l'horloge R35 restaurée. Le digest extérieur de `GameSession` couvre aussi `advanced_ai`.
- Cela détecte les corruptions et divergences internes, **sans prétendre authentifier un fichier entièrement réécrit et recalculé par un tiers** : un hash sans clé n'est pas une signature.
- L'absence de l'extension signifie **aucune clé `advanced_ai`** dans les anciens checkpoints. Un champ injecté dans un projet non opt-in est rejeté. Inversement, un projet opt-in exige le champ dans ses checkpoints.
- Changer le projet de politiques change `project_digest`, et les checkpoints d'un autre manifeste restent incompatibles sans migration explicite.

## Tests

```sh
python -m unittest tests_standalone.test_r37_ai_session -v
python -m unittest tests_standalone.test_r37_ai_decision -v
python -m unittest tests_standalone.test_r35_living_world tests_standalone.test_r25_fixed_realtime tests_standalone.test_game_session -v
```

Les gates R37.B sont les contrats headless, la validité des replays, le maintien du CT par défaut et la compatibilité historique. **Non couvert** : éditeur visuel de Behavior Trees (R37.C), perception réelle / LOS (R37.D), intégration des commandes IA au gameplay et certification visuelle du boss (R37.E).
