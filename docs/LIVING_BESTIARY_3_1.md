# 3.1.2–3.1.6 — Living Bestiary (opt-in)

Le bestiaire médiéval n'est plus seulement un jeu de statistiques : quatre
**doctrines** différentes prennent des décisions au travers des mêmes commandes
que le joueur et les replays de combat. Les données et les sauvegardes
historiques du projet restent compatibles.

## Intégration

1. Dans **Personnages & règles → Bestiaire 4.0**, installez le catalogue
   médiéval, puis placez un personnage. Chaque pose porte un tag
   `doctrine:<id>` si le preset propose une doctrine.
2. Pour une variante, choisissez une fiche, un nouvel ID, son type et une
   doctrine. **Créer variante**, puis **Placer variante**. Le modèle original
   et les combattants déjà placés ne sont pas réécrits.
3. Dans le Studio, les onglets **Archétypes**, **Compétences** et **Classes /
   IA** restent les sources des statistiques, attaques et arbres de
   progression. Modifier ou supprimer une fiche en cours d'utilisation suit
   le validateur transactionnel et les contrôles de référence existants.
4. En jeu, utilisez le ruleset opt-in :
   ```python
   from sporebound.tactical_rpg3 import tactical_rpg_rules
   from sporebound.engine import Battle

   rules = tactical_rpg_rules()
   battle = Battle(content, "m1", rules=rules)
   ```

Les règles par défaut `default_rules()` ne proposent ni `reload` ni
`surrender` ; leur manifeste ne change pas.

## Quatre doctrines, quatre contre-mesures

| Doctrine | Choix réels | Contre-jeu |
|---|---|---|
| `pack_hunt` | Préférence pour la cible isolée ; contournement arrière et soutien entre loups | Regrouper les alliés, protéger les flancs |
| `bandit_ambush` | Utilise le couvert ; après perte du chef ou blessure sévère, fuit ou se rend | Cibler le chef, couper la retraite |
| `spear_hold` | Estoc à distance de lance ; garde / phalange validée sur sa ligne | Détourner ou traverser la zone par une autre approche |
| `crossbow_reload` | Tire, entre dans l'état `reload:empty`, doit dépenser une action pour recharger ; peut reculer s'il est engagé | Profiter de la fenêtre de rechargement |

`tactical_intents(battle)["doctrines"]` indique les rôles et l'état
prêt/en rechargement **sans faire avancer le combat**. Les décisions
doivent rester déterministes pour la même situation, les mêmes règles et la
même graine. `Battle.execute` valide les commandes, gère le rollback et
enregistre les événements.

La reddition émet `surrender`. Un adversaire rendu n'est pas considéré
comme mort par le journal narratif : le suivi des prisonniers récupère la
fiche et propose son recrutement par la campagne.

## Progression et blessures

```python
campaign = Campaign(unlocked=["m1"], reward_policy="contribution",
                    wound_policy="light")
campaign.hero("squire_a").job_xp["med_guard"] = 50
campaign.customize_hero(content, "squire_a",
    origin="soldier", traits=["steadfast"],
    secondary_job="med_guard", weapon_mastery={"spear": 3})
```

Deux héros d'un même niveau ont alors des PV, défenses, déplacements,
attaques, compétences et maîtrise d'armes potentiellement différents :
leurs avantages et compromis sont appliqués lors de `Campaign.prepare`,
sans modifier leurs templates.

- Origines : commoner, peasant, noble, soldier, artisan.
- Traits (maximum 2) : steadfast, nimble, reckless, careful, resilient.
- Classe secondaire : une classe déjà entraînée (50 XP de classe), deux
  compétences de la classe secondaire maximum.
- Maîtrise : 0 à 5 par famille d'arme, bonus plafonné à +3 en puissance.
- Moral : steady, shaken, wavering, routing ; blessures : arm_injury,
  leg_injury, lasting_scar. Application à la préparation des combats.
- `reward_policy="contribution"` : 75 à 125 XP, 35 à 65 XP de
  classe, contribution bornée à cinq actions utiles. Attribué **une
  seule fois par mission victorieuse** ; ledger de récompenses sauvegardé.
- `wound_policy="off"` par défaut ; modes light / serious pour les
  conséquences des blessures. Un échec affecte le moral, et une blessure
  sévère peut laisser une séquelle.

La campagne conserve séparément `prisoners` et `recruits`.
`campaign.recruit_prisoner(unit_id)` marque un choix persistant et fait
participer le personnage aux missions suivantes dans une case libre.
Cette fonctionnalité ne remplace pas encore les conditions narratives
propres à chaque personnage nommé de Jeanne : elles doivent être
définies au niveau des scènes/choix de campagne.

## Équilibrage et reprise

```python
from sporebound.encounter_balance31 import analyze_three, replay_three

ids = ["m1", "m2", "m3"]
diagnostic = analyze_three(content, ids)
report = replay_three(content, campaign, ids, seeds=(1, 2, 3))
assert all(e["resume_checked"] for e in report["encounters"])
```

Le diagnostic compare des **budgets indicatifs** et la diversité de rôles
(une heuristique, pas une preuve d'équilibrage). Le gate `replay_three`
exécute les vrais combats avec les règles 3.1, vérifie le digest des
replays et effectue le round-trip JSON du profil campagne à chaque mission.
La campagne d'entrée n'est jamais mutée.

## Gates de validation

```bash
python -m unittest discover -s tests_standalone -p 'test_doctrines31.py' -v
python -m unittest discover -s tests_standalone -p 'test_living_bestiary31.py' -v
python -m unittest discover -s tests_standalone -v
```

La CI multiplateforme valide aussi le reste du moteur historique.

## Limites explicites

- `analyze_three` est un indicateur de puissance/composition, non une
  simulation probabiliste complète de difficulté ; la réussite réelle des
  missions se vérifie avec `replay_three`.
- Le moral est d'abord un état de campagne avec un effet au combat et une
  décision de reddition bandit fondée sur la perte du chef/PV ; ce n'est pas
  encore un moteur de panique multi-faction.
- La création de variantes, la doctrine et la pose sont guidées, mais les
  graphes de progression restent dans le Studio classes/IA existant.
- Le recrutement est limité aux prisonniers identifiés et aux cases libres
  d'une mission ; une politique narrative d'exclusion/consentement et une
  autorisation explicite restent nécessaires pour une campagne publiée.
