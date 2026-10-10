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
| `statuses` | Blocages, vitesse, mitigation, interruption, réveil, fin de tour | Cycle de vie des statuts |
| `movements` | Bonus, relief, téléportation, callback de fin de mouvement | Traversée et budget partagés par moteur et IA |
| `reactions` | Avant/après dégâts, sortie de zone, prévision, évasion | Réactions passives |
| `preparations` | Validation, couverture, entrée de zone, interception, déplacement forcé | Réactions préparées |
| `tactics` | Options, nombre de partenaires, diviseur, repositionnement | Synergies offensives et Relay |
| `trigger_conditions` | `matches(battle, trigger)` et `validate(context, trigger)` | Conditions de scénario |
| `trigger_actions` | `apply(battle, action)` et `validate(context, action)` | Actions de scénario |

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

Les enregistrements v3 contiennent le manifeste des familles, identifiants et versions.
`Battle.replay(recording, rules=rules)` et `load_battle(path, rules=rules)` vérifient ce
manifeste avant de rejouer. Le code des règles n'est jamais sérialisé ou importé depuis
la sauvegarde. L'appelant doit fournir les extensions. Incrémenter la version d'une
règle à chaque changement de comportement ; le manifeste n'est pas un hash de son code.
Les replays v1 restent lisibles avec les règles historiques par défaut et leur checksum.
Les anciens replays v2 vérifient leur manifeste à cinq familles ; les sept familles
ajoutées doivent correspondre aux valeurs par défaut historiques. Une extension de
ces familles nécessite un enregistrement v3. Les nouvelles versions ne sont pas
lisibles par les anciens exécutables.

## Statuts, déplacements et réactions personnalisés

```python
from sporebound.rules import MovementRule, StatusRule

rules = rules.with_family('statuses', rules.statuses.with_rule(
    'meditating', StatusRule(
        blocks=frozenset({'act', 'reaction'}), beneficial=True,
        end_turn=lambda battle, unit: battle._heal(unit, 3),
        version='meditation-v1',
    ),
))
rules = rules.with_family('movements', rules.movements.with_rule(
    'climber', MovementRule(bonus=2, ignore_height=True),
))
```

Référencer ces identifiants dans `Unit.statuses` / `Unit.movement`, dans un archétype
ou un effet `status`. Les statuts sont appliqués dans l'ordre `(priority, id)` pour
les modificateurs et fins de tour. Une priorité basse s'applique en premier.
Les durées restent en ticks, `-1` signifie permanent. L'expiration suit l'ordre
d'insertion historique des statuts pour conserver l'ordre des événements.

Les capacités bloquées sont `activation`, `act`, `move`, `magic`, `reaction`,
`continue_move`, `charge` et `evasion`. `interrupt` accepte `all` ou `magic` ;
`cancel_prepared` annule une posture et `wake_on_damage` retire le statut après des
dégâts effectifs. `beneficial` informe l'évaluation IA. Le moteur consulte
`Battle.movement_budget(unit)` ; l'ancienne propriété `Unit.movement_budget` reste
une commodité pour les valeurs historiques, sans accès aux règles du combat.

Une `ReactionRule` peut absorber un dommage via `before_damage` (retour vrai),
réagir à un dommage non nul via `after_damage`, ou agir à la sortie d'une zone via
`on_leave`. Ce dernier retourne vrai pour demander le déplacement de poursuite.
`forecast_leave` produit une ligne de menace sans mutation du combat ; son ensemble
`seen` est local à la prévision et permet de limiter une poursuite à une fois.
Une réaction qui modifie l'absorption des dégâts doit aussi adapter la prévision
via les formules/effets si cette absorption doit apparaître dans l'interface.

Une `PreparationRule` partage `enters` entre prévision du trajet et résolution.
`covers` sert à la carte de menaces ; `intercepts` choisit une protection et
`displace` réduit éventuellement un déplacement forcé. Les attaques préparées
réutilisent la portée/LOS de l'arme, consomment leur charge et leur coût CT.
L'IA tactique n'émet plus une posture retirée du registre.

## Synergies et campagne

Les synergies offensives exposent des options et un `divisor` commun à la prévision
et à la résolution. Une option indique `id`, `target`, `partner` ou `partners`,
et `ct_cost`. L'ordre des résultats est déterministe, indépendamment de l'ordre
d'enregistrement. Les combos offensifs utilisent les attaques des partenaires ;
Relay dispose des callbacks `reposition` et `execute`.

Les méthodes de campagne `unlock_tactic[_members]`, `prepare_tactic[_members]`,
`evaluate_tactic_unlocks`, `prepare` et `load` acceptent `ruleset=rules`. Cela permet
à une nouvelle synergie de traverser déblocage, préparation, sauvegarde et combat.
`finish` utilise les règles du combat. Les groupes restent limités à deux ou trois
membres ; les données de campagne n'embarquent jamais les callbacks Python.

## Conditions et actions de scénario

Les deux registres de triggers sont séparés. Leurs validateurs reçoivent un
`ValidationContext` avec `board`, `unit_ids`, `rules`, et les helpers `cell`, `unit`,
`integer`. Les conditions sont pures ; les actions mutent le combat dans la
transaction de la commande. L'ordre des triggers et de leurs actions reste celui
du JSON. Un trigger est marqué avant ses actions et ne s'exécute qu'une fois.
Une exception restaure aussi son marqueur, le déplacement en cours et le RNG.

## Limites et suite

Les douze registres couvrent maintenant les familles extraites. `Battle` reste
responsable de l'état, de l'ordonnancement CT, des transactions et du replay ; les
services de règles appellent ses opérations. Le pathfinding et l'ordonnancement
ne sont pas des plugins arbitraires : les modes de mouvement configurent le
parcours commun. Le terminal et l'éditeur embarqués utilisent les règles par
défaut ; les extensions Python sont assemblées par leur application hôte.

Les invocations ont un type d'acteur, mais spawn/despawn en cours de combat,
renforts et durée de vie restent à implémenter. Les prochains chantiers sont les
profils IA spécialisés et l'édition visuelle des archétypes/règles.
