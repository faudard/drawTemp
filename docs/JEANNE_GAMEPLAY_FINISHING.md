# Jeanne — finition gameplay (Combat Design 1.0)

Cette tranche renforce **Time × Position × Objective × Team** dans les
missions existantes, sans second moteur, nouvel objectif ni nouvelle IA.

## Parcours jouable

1. **Domrémy** : les sauvetages influencent les ressources du prologue et de la route.
2. **Route des fugitifs** : extraction sur les cases de sortie, sans extermination.
3. **Pont de la Brume** : tenir les cases centrales pendant 35 ticks sans
   présence ennemie concurrente. Les escouades adverses essaient de
   contester cet objectif avec des déplacements validés par `Battle.reachable`.
4. **Choix du pont** : `tenir_passage` donne une potion au combat via
   `battle_support`; `contourner` donne des renseignements utilisés dans la suite.
5. **Hospice, archives/otages et Vaucouleurs** : les branches exclusives,
   récompenses et vérifications de sauvegarde sont conservées.

## Information visible et invariants

- Le panneau Player présente les rôles ennemis, la formation *réellement*
  active et les cases liées à l'objectif. `possible` signifie **plan
  conditionnel** et non prédiction déterministe de la prochaine commande.
- Une formation non active n'a pas de bonus ; seule la géométrie validée par
  `formations3` décide de l'activation.
- L'IA choisit uniquement des commandes normales, sans altérer le RNG,
  l'horloge CT, les unités hors commande ni le journal de replay.
- Les anciennes missions sans tags conservent leur IA historique ; le
  Player active l'ensemble avancé pour Jeanne via les rôles du pont.
- Le château garde ses réelles formations phalange/escorte, et ses tests de
  rejouabilité indépendants.

## Vérification

```sh
python -m unittest tests_standalone.test_jeanne_gameplay_finish tests_standalone.test_jeanne_acte1 tests_standalone.test_jeanne_prologue tests_standalone.test_jeanne_combat31 -v
```

Gate : prévisualisation pure, victoire par objectif non-élimination,
conséquences réelles des choix, mouvement IA légal et replay identique.

Les anciens emplacements Jeanne ne sont pas migrés silencieusement, car
le contenu et le manifeste de règles ont changé. Démarrer une nouvelle
partie ou garder une version compatible pour reprendre un ancien slot.
