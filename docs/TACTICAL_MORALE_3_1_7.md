# 3.1.7 — Morale tactique et commandement

Cette évolution complète le bestiaire vivant de la PR #52. Elle dépend de
`feat/3.1.2-3.1.6-living-bestiary` et se fusionne **après** cette PR.
Elle n'ajoute aucune mutation implicite dans les prévisions de combat.

## Moral observable

`morale_snapshot(battle, unit_id)` calcule un état parmi :
`steady → shaken → wavering → routing`.

La pression provient de données déjà enregistrées dans la bataille :
perte de PV, décès d'un compagnon, mort du capitaine bandit, encerclement
et moral initial hérité de la campagne. Un officier peut prendre une
action `rally` pour relever un allié. Toutes les causes sont renvoyées
dans `reasons` ; aucune RNG n'est consommée.

| Moral | Dégâts physiques/magiques |
|---|---:|
| steady | 100 % |
| shaken | 90 % |
| wavering | 80 % |
| routing | 65 % |

Les bonus/malus ne s'appliquent qu'aux combattants avec
`doctrine:*` ou `morale:*`. Les soldats ordinaires des anciens
scénarios conservent leur logique sans tag. Ce calcul est effectué par
la règle de dégâts du moteur et partagé par `forecast` et `execute`.
La fonction `tactical_intents(battle)["morale"]` expose les états
et leurs causes sans modifier l'état de la bataille.

## Commandement et contre-jeu

- Un capitaine vivant disposant de son action rallie en priorité son
  allié démoralisé le plus menacé à deux cases maximum.
- Le ralliement exige une cible alliée vivante et vulnérable, coûte
  l'action du capitaine, modifie un seul tag et émet `morale_rally`.
- Un brigand wavering/routing préfère fuir ; s'il est encerclé ou
  gravement blessé, il peut capituler, en utilisant l'authentique
  commande `surrender` et ses événements persistants.
- Un arbalétrier sous `reload:empty` subit **20 % de dégâts
  supplémentaires** lors d'une attaque de base en mêlée : la phase
  de recharge devient une véritable fenêtre d'attaque exploitable.

La sélection UI utilise `tactical_action_options` et
`tactical_command("rally:<unit_id>", cell)`, sans code spécial dans
le Player.

## Compatibilité et intégration

Ce bundle reste opt-in : `tactical_rpg_rules()` installe le moral,
ses commandes et sa formule versionnée `3.1.7-morale`.
`default_rules()` ne change pas.

**Important :** un replay produit avant 3.1.7 avec l'ancien manifeste
3.1 est déclaré incompatible via `Replay ruleset mismatch`.
Aucune ancienne commande n'est silencieusement réinterprétée.

La campagne conserve `hero.morale` et le réinjecte dans une nouvelle
bataille, sans dupliquer les tags de la mission. Lors d'une défaite,
le moral observé peut dégrader l'état sauvegardé ; les blessures
restent contrôlées par la politique existante `wound_policy`.

## Gate de vérification

```bash
python -m unittest discover -s tests_standalone -p 'test_morale31.py' -v
python -m unittest discover -s tests_standalone -v
```

Les tests couvrent : prédiction pure, ralliement valide/invalide,
choix de l'IA capitaine, reddition à plein PV sous panique,
effet réel sur les dégâts, exposition des arbalétriers,
intégration Player, replay bit-à-bit et incompatibilité explicite
du manifeste. CI prévue : Linux/Windows/macOS, Python 3.10/3.12/3.14.

## Prochaine étape (3.1.8)

Tester les scénarios dans un parcours de campagne scénarisé :
embuscade des bandits et perte du chef, goulot de lanciers,
meute de loups, escouade protégeant des arbalétriers. Mesurer
la fréquence des redditions et la durée des rencontres, puis
rendre les intentions et le moral visibles sur le plateau.
