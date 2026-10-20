# R43.B3 — Ciblage natif CT et viewport R3

**État : implémentation PR empilée sur #394 → #391 → #373.**
**Validation CI et intégration Player : non démontrées (NO-GO).**

## Objectif et sources de vérité

R43.B1 utilise encore une grille 9×9 schématique, sans visibilité des
obstacles, hauteurs et unités. Cette branche ajoute un aperçu **réellement
adossé au code natif CT**, sans inventer un deuxième algorithme de combat.

- `drawtemp/sdk/ability_targeting_r43.py` reçoit `AuthoringSession`,
  Ability R43.A, mission, lanceur et cellule. Il valide le contrat, compile
  temporairement la compétence CT et construit un `Battle` **détaché** à
  partir de `Content` copié.
- `Battle._target` décide de la légalité (équipe, portée, cases occupées,
  LOS, étages), `Battle._area` donne la zone, `Battle._affected` les
  bénéficiaires par effet. `Battle.line_of_sight` apporte le même test
  supercover que le jeu tactique.
- Pour éviter des modifications irréversibles : aucune commande `execute`,
  aucun état de `GameSession` modifié, aucun tirage publié, aucune
  mutation de `AuthoringSession`. Le skill de démonstration et la présence
  dans le loadout du lanceur n'existent **que dans le clone** de la mission.
- Le catalogue original R43.A et les skills natifs du projet restent intacts.
  `schema_version`, formules et capacités non prises en charge restent
  refusées par `compile_ct_skill`.
- Le calcul retourne `legal`, raison d'échec, `available`, `area`,
  `recipients`, `line_of_sight`, origine et destination. Pour éviter
  de surcharger l'UI, les intentions retournées ont un budget de **1 024
  cases candidates**. Au-delà, refus explicite plutôt qu'un résultat partiel.

## UI Studio : viewport partagé

Le bouton **Ciblage natif CT — ouvrir la carte R3** est accessible dans
**Combat & Ability Designer R43**. Il ouvre `NativeTargetingDialog` :

- contrôle explicite de la mission et du lanceur ;
- widget Qt Quick **`IsoViewport.qml` original** et
  `make_controller(scene_from_mission(...))`, comme dans Map Studio ;
- `interactionMode = "select"`, événements `cellSelected` de R3, sans
  recréer une grille ni un picker divergent ;
- overlays `reach` pour cases légales, `intent` pour AoE et `danger`
  pour cible refusée. Les overlays sont purement visuels et utilisent
  les interfaces de `RendererController.setOverlays` ;
- panneau de diagnostics et contrôle de révision pour ne jamais montrer
  une prévisualisation comme actuelle après une édition concurrente.

Aucune commande tactique n'est déclenchée en cliquant une case : c'est un
**inspecteur de l'auteur**, pas une exécution Player.

## Limites / décisions de gate

1. **TACTICAL_CT uniquement**, formules constantes compilables. Les
   formules dépendantes de statistiques R43.B2 et les profils ACTION_REALTIME
   / RPG_TURN restent déclaratifs, pas exécutés par ce lot.
2. `Battle` ici est une nouvelle simulation **détachée de la mission
   initiale**. L'aperçu indique des cibles et effets **structurels**, pas
   la disponibilité de l'action au tick d'une partie en cours, ni les MP,
   le cooldown, les interruptions, crits/atténuations ou combos réellement
   exécutés. Cela nécessite une passerelle `GameSession.active_battle`
   séparée avec tests de save/replay.
3. Le ciblage sur les étages supérieurs est bloqué explicitement jusqu'à
   une capacité dédiée de la simulation.
4. L'éditeur ne supporte pas encore les cônes. La schématisation R43.A
   n'autorise que `single`, `diamond`, `cross`, `square`. Ajouter
   `cone` nécessite d'abord un contrat versionné R43.A et une règle Battle
   correspondante (jamais un masque cosmétique seul).
5. Tests Qt **offscreen** et géométrie R3 disponibles dans cette PR; une
   interaction onscreen à la souris, clavier/manette, le vrai GPU, les
   exports clean-machine et la certification 30/60/120 FPS sont à prouver.

## Tests attendus

```sh
python -m unittest tests_standalone.test_drawtemp_r43b3_native_target -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp_r43b3_target_qt -v
python -m unittest tests_standalone.test_combat31 tests_standalone.test_jeanne_combat31 -v
```

CI dédiée : `.github/workflows/r43b3-native-targeting.yml`.

## Suite R43.B4 / R43.C

Adaptateurs sur la `GameSession` vivante sans faux état, sauvegarde/replay
de casts, cooldowns et coûts versionnés, interactions d'états et de combos,
visualisation/FX au tick R36, Balance Lab avec seeds réels. Puis vertical
slice quatre compétences jouables et matrice de certification PC.

**Gate R43 = NO-GO** tant que ces preuves ne sont pas réunies.
