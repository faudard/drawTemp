# V1.28 — FFT Turn Loop

Cette passe remplace le cooldown universel des compétences par une boucle de combat inspirée directement de Final Fantasy Tactics.

- Tous les combattants commencent à **0 CT**.
- À chaque clock tick, **CT += VIT**. Une unité devient active à **CT >= 100**.
- Pendant son Active Turn : **1 Move maximum + 1 Act maximum**, dans n’importe quel ordre.
- Fin de tour : le joueur garde la main pour choisir l’**orientation**, puis valide **WAIT / FIN**.
- Coût CT exact : Move+Act = **100**, Move seul = **80**, Act seul = **80**, Wait = **60**.
- Le coût est soustrait au CT réellement atteint (overflow conservé), puis le reliquat est plafonné à **60**.
- Les **cooldowns de compétences sont désactivés**. Une compétence est limitée par l’action du tour, son coût en Focus et son éventuel temps de cast.
- Les champs `cooldown_rounds` / `cooldowns` restent uniquement pour charger sans casse les anciennes ressources/sauvegardes ; le runtime les ignore et les purge.
- Les API `has_tag`, `cast_time_ticks`, `interrupt_on_damage`, `uses_accuracy`, `accuracy` ont été rétablies dans `SporeSkillCatalog`.

## Test

Lancer avec un exécutable Godot 4.7.1 :

`godot --headless --path . --script res://tests/test_fft_turn_loop_v128.gd`

## Compatibilité / corrections de parse

- Les deux appels runtime à `UnitCatalog.make_hero()` ont été réalignés sur la signature actuelle à 7 arguments.
- Les appels déjà présents à `SkillCatalog.has_tag()`, `cast_time_ticks()`, `interrupt_on_damage()`, `uses_accuracy()` et `accuracy()` ont désormais une implémentation.
- `SporeBattleController` reste la classe du contrôleur actif et `main_v19.gd` continue de l'étendre.

## Validation effectuée

- scan statique des appels `SkillCatalog.*` : aucune méthode manquante ;
- vérification des appels `make_hero()` actifs : 7 arguments ;
- vérification du point d'entrée `main.tscn -> main_v19.gd -> battle_controller.gd` ;
- vérification des règles CT et de l'absence de cooldown comme condition d'utilisation.

Le test headless est inclus. L'environnement de génération ne disposait pas d'un binaire Godot local et l'accès réseau du conteneur empêchait de télécharger Godot 4.7.1, donc le test n'a pas pu être exécuté ici.
