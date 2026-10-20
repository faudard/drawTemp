# R41.B3 — RPG_TURN sur SceneRouter, Player Qt et commandes clavier

**Statut au 19 octobre 2026 : CODE EN PR #381, NON CERTIFIÉ.** Prolonge R41.A, R41.B1 et R41.B2 dans la même PR de consolidation vers master.

## 1. Nouveau chemin joueur effectivement raccordé

1. L'auteur configure un profil `classic_rpg` et un groupe R41 avec **Party Studio** dans la source `GameProject`.
2. Dans **Encounter Studio**, il affecte une rencontre à une scène `exploration` déjà définie. L'ennemi référence le `Content` canonique, pas un registre parallèle.
3. Si la partie possède un `SceneRouter` R25, le Player ne propose que les rencontres **rattachées à la scène parcourue** : toute demande de démarrage depuis une autre scène échoue côté `GameSession`, même hors UI.
4. Le Player affiche le groupe et les rencontres de la zone dans le panneau d'exploration. Le combat `RPG_TURN` interrompt la promenade **sans changer le curseur de route** ; le renderer continue à projeter la scène R3 existante.
5. Pendant le combat, `GameSession` et `Simulation` conservent l'historique des routes, les flags, la position d'exploration, les consommations et les journaux de commandes.
6. Quand l'utilisateur quitte le combat résolu (victoire, défaite ou fuite), la campagne reprend **dans cette même scène à la même case**. Les récompenses de victoire restent idempotentes, selon R41.B2.

Les anciennes missions CT demeurent pilotées par `Battle`, `scene_router.route_transition` et leur propre protocole de replay. Aucun changement du format de route historique ni des sauvegardes sans RPG.

## 2. Invariants et contrôle au chargement

`SceneRouter.validate_checkpoint(..., mode="rpg", rpg_scene=...)` ajoute un contrôle strict, uniquement utilisé par le nouveau mode :

- `scene_route.version`, `current` et `history` restent les clés R25 originelles.
- Le parcours complet des liens R25 est rejoué (source→destination) et doit mener au `current` déclaré.
- Le curseur doit désigner une **scène d'exploration**, égale à `ClassicEncounter.scene`.
- Le `rpg_encounter` est reconstruit depuis ses actions, acteurs et inventaire ; `Campaign.inventory` doit correspondre exactement au résultat du replay.
- Des entrées non autorisées, inconnues, incohérentes ou des checksums invalides refusent le chargement, sans auto-réparation silencieuse.

La lecture SDK `Simulation.rpg_route_state()` retourne une projection immuable ; le Player Qt utilise `scene_from_exploration`, exactement comme le rendu R3 de l'exploration normale.

## 3. Contrôles clavier disponibles dans le Player RPG

- `A` : sélectionner Attaque ; `G` : Garde ; `S` : Compétence ; `I` : Potion ; `F` : Fuite.
- `Ctrl+←` / `Ctrl+→` : passer d'une cible admissible à l'autre.
- `Entrée` : valider l'action sélectionnée ou quitter un combat résolu.

Le sélecteur de cible filtre les adversaires/alliés vivants, les sorts personnels et les alliés blessés pour potion. L'API sous-jacente reste autoritaire : toute action ou cible illégale est rejetée atomiquement. Les raccourcis sont actifs **uniquement** dans l'écran `rpg_battle`, et ne reprennent pas ceux du combat tactique CT.

Ces raccourcis sont des ajouts de code non vérifiés physiquement. **La navigation manette et la QA accessibilité/onscreen sont encore à faire** ; aucun support console ou publication PC n'est certifié par les présents changements.

## 4. Tests supplémentaires à exécuter

```sh
python -m unittest tests_standalone.test_r41_routed_encounter -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_r41_routed_qt -v
python -m unittest tests_standalone.test_r25_scene_router \
  tests_standalone.test_r41_classic_party \
  tests_standalone.test_r41_encounter -v
```

La suite `test_r41_routed_encounter` couvre : scene non autorisée, route aller-retour, conservation de la position et de l'historique, save/load au milieu du combat, replay fidèle, route falsifiée mais intérieurement cohérente et retour dans le vrai `PlayerController`. Le test Qt charge le **vrai `Main.qml` et son bridge** en mode offscreen et exécute une transition exploration→combat→exploration ; son passage n'est pas un test de GPU ni de manette.

## 5. Gates de release encore ouverts

- **R41.B3** : instrumentation / mesure clavier onscreen et manette sur matériel PC, transitions complexes avec dialogue et effets de compétences R43 ; aucune certification de gamepad n'est revendiquée.
- **R41.C** : template PC original, groupe 3 héros, village→donjon→2 rencontres→récompenses→retour, tests de conservation de flags et inventaire, compat multi-OS, droits d'assets, profilage, export/installation sur machine propre.
- **CI** : tant que GitHub Actions ne fournit pas des **jobs exécutés et logs sur le SHA final**, la PR reste en **NO-GO**, même si l'API la déclare fusionnable.
