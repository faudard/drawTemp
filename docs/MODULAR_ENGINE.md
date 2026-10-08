# Moteur modulaire : règles et acteurs

Le point d'entrée reste `Battle.execute(command)` pour joueur, IA, CLI et éditeur.
`Battle` possède l'état mutable, le RNG et la transaction. `RuleSet` compose des
politiques explicites, sans singleton ni découverte/import de modules depuis le JSON.
Un combat reçoit ses règles à sa construction ; composer une variante avant de créer
un nouveau combat, plutôt que changer les règles au milieu d'une sauvegarde.

## Familles indépendantes

| Famille | Contrat | Responsabilité |
| --- | --- | --- |
| `commands` | `execute(battle, actor, command)` | Traduire une intention en opérations moteur |
| `effects` | `apply(battle, caster, target, skill, effect, cell)` et `amount(battle, caster, target, skill, effect)` | Résolution et quantité prévisionnelle |
| `formulas` | `calculate(battle, caster, target, skill, ...)` | Dégâts, mitigation et probabilité de toucher |
| `objectives` | `achieved(battle) -> bool` | Victoire ; défaite et protection restent prioritaires |
| `behaviors` | `choose(battle) -> dict` | Choisir une commande pour l'acteur actif |

Les registres et descripteurs sont immuables. `with_rule`, `without` et `with_family`
retournent des variantes ; ils ne modifient ni les règles par défaut ni un autre combat.
Un remplacement exige `replace_existing=True`. Une référence à une règle absente
échoue explicitement ; aucun effet inconnu n'est silencieusement ignoré.

```python
from sporebound.rules import default_rules, FormulaRule
from sporebound.engine import Battle

rules = default_rules()
rules = rules.with_family('commands', rules.commands.without('charge'))
rules = rules.with_family('formulas', rules.formulas.with_rule(
    'damage', FormulaRule(lambda b, caster, target, skill, effect: 8,
                          version='flat-8-v1'),
    replace_existing=True,
))
battle = Battle(content, 'garden', rules=rules)
```

Les calculs et les choix IA doivent être purs : pas de mutation ni tirage RNG. Les
callbacks de résolution utilisent seulement l'état du combat, `battle.rng` et
`battle.emit`. Ne pas cacher d'état mutable dans les closures, les modules ou les
objets callbacks : cet état externe ne fait pas partie du rollback/replay.
Le runtime n'est pas un bac à sable pour du code non fiable.

`damage`, `hit_chance` et `mitigation` sont des formules obligatoires, remplaçables.
L'IA tactique filtre les commandes optionnelles retirées ; elle nécessite `end`.
Un comportement spécialisé peut être enregistré pour une créature sans modifier
`Battle`, et doit sélectionner uniquement des commandes autorisées.

## Ajouter un effet

Enregistrer un `EffectRule` avec sa résolution et son calcul prévisionnel, puis utiliser
son identifiant dans `Effect.kind`. Passer le même `rules` à `Content.from_dict`,
`Content.load`, `Content.validate` et `Battle`.

- `area=True` : résolution une fois sur la zone, avec `target=None`.
- `targets_downed=True` : sélection des unités à terre (ex. résurrection).
- Les effets ciblés partagent un seul jet de précision par victime et compétence.
- Les effets restent exécutés dans l'ordre défini par la compétence.

Un nouvel effet utilise les champs existants du contrat `Effect`. Un nouveau schéma
de paramètres nécessite encore une évolution du modèle. Pour qu'un effet inédit soit
valorisé correctement par l'IA, fournir aussi un comportement approprié : l'utilité
par défaut comprend les effets historiques, pas une sémantique arbitraire.

## Personnages, monstres et invocations

`ActorFactory` crée des `Unit` indépendantes à partir d'archétypes JSON.
`kind` vaut `character`, `monster` ou `summon` ; ce n'est pas une équipe. Un monstre
peut être allié. `team` détermine l'allégeance, `behavior` l'IA et `tags` la classification.
Aucune hiérarchie `Hero -> Monster` ni duplication des règles de combat.

```json
{
  "archetypes": {
    "wolf": {
      "kind": "monster",
      "max_hp": 60,
      "attack": 9,
      "skills": [],
      "tags": ["beast"],
      "behavior": "tactical"
    }
  }
}
```

Une entrée dans `missions[].units` référence cet archétype :

```json
{"id":"wolf_1","name":"Loup","team":"enemy","pos":[3,1],"archetype":"wolf"}
```

Les valeurs explicites du spawn prennent le pas sur l'archétype. HP/MP démarrent aux
maximums résolus si non précisés. Les collections sont copiées : blesser une unité
ou lui ajouter un statut ne modifie pas ses congénères ni la définition auteur.
Les archétypes ne contiennent pas d'identité, position ou état transitoire de tour.
Même les archétypes inutilisés sont validés (stats, compétences, comportement).

Le format historique sans archétype reste accepté. `Content.to_dict()` conserve le
catalogue et sérialise des unités **résolues** : recharger ces unités ne réapplique pas
les nouveaux défauts du catalogue. Pour régénérer depuis un archétype modifié, repartir
du spawn minimal/`ActorFactory`. Le panneau JSON de l'éditeur suit cette même règle ;
il n'existe pas encore d'éditeur visuel dédié aux archétypes.

Exemple complet : `python -m examples.modular_rules`.

## Transactions et sauvegardes

Toute exception d'une commande restaure état, événements, journal et RNG, y compris
une erreur inattendue d'un module. Les erreurs inattendues sont ensuite propagées
pour permettre leur diagnostic, sans être présentées comme une simple entrée invalide.

Les enregistrements v2 contiennent le manifeste des familles, identifiants et versions.
`Battle.replay(recording, rules=rules)` et `load_battle(path, rules=rules)` vérifient ce
manifeste avant de rejouer. Le code des règles n'est jamais sérialisé ou importé depuis
la sauvegarde. L'appelant doit fournir les extensions. Incrémenter la version d'une
règle à chaque changement de comportement ; le manifeste n'est pas un hash de son code.
Les replays v1 restent lisibles avec les règles historiques par défaut et leur checksum.

## Suite de l'extraction

Les cinq familles ci-dessus sont intégrées au moteur actuel. Le cheminement, les
horloges/statuts, réactions préparées, synergies et triggers restent des services de
`Battle`. Leur extraction en politiques spécialisées est une étape ultérieure ;
un nouveau statut ou type de réaction ne se branche pas encore dans un registre.
Les invocations ont un type d'acteur, mais spawn/despawn en cours de combat et leurs
règles d'initiative ne sont pas encore implémentés.
