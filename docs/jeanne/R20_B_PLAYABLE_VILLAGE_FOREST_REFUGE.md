# R20.B — Village, forêt, refuge : tranche jouable Jeanne

**Livré :** une variante optionnelle du projet Jeanne, utilisant **exactement**
les mêmes missions tactiques et les mêmes systèmes `Content / GameProject /
GameSession / Exploration / Battle` que le jeu de référence. Le prologue,
les sauvegardes historiques, les règles CT et les replays ne sont pas modifiés.

## Lancer dans le Player Qt

Depuis la racine du dépôt avec les dépendances Qt6 installées :

```bash
python -m drawtemp.player.qt_app \
  --content sporebound/content/jeanne.json \
  --project sporebound/content/jeanne.r20b.game.json \
  --campaign jeanne
```

Ou dans le lecteur Python classique :

```bash
python -m sporebound player \
  --content sporebound/content/jeanne.json \
  --project sporebound/content/jeanne.r20b.game.json
```

**Important :** le pack R20.B est volontairement dans
`sporebound/content/`, à côté des illustrations relatives
`art/...` du manifeste existant. Il possède sa propre identité de projet.
Le Player Qt isole les emplacements de sauvegarde des projets externes par
chemin absolu de `content` et de `project`. Ne jamais faire pointer le
`--save-dir` de cette variante vers celui du pack Jeanne historique.

## Quatre environnements effectivement explorables

| Moment | ID de scène | Actions nécessaires | Choix tactique réel |
|---|---|---|---|
| Camp des survivants / forêt | `sc_a1_camp` | Examiner le foyer et les provisions, parler à Margot, secourir éventuellement Éline | Recruter Étienne **ou** Agnès, équiper le compagnon, escorte `a1_01_route` |
| Chemin forestier et pont | `sc_a1_pont` | Lire les traces, observer la passerelle et le passeur, éventuellement sauver Luc | Choisir la couverture ou la surprise, puis `a1_02_pont` |
| Hospice/refuge | `sc_a1_hospice` | Étudier les remèdes et les registres, éventuellement sauver Lucie | Donner les potions aux blessés ou conserver les dossiers, puis `a1_03_hospice` |
| Place du bailli / village | `sc_a1_dilemme` | Examiner le sceau et écouter les familles avant le départ | Archives `a1_04a_archives` **ou** otages `a1_04b_otages` |

L'Acte I se termine toujours par la **vraie** mission
`a1_05_vaucouleurs` et ses choix conditionnels de fin. Le projet R20.B
ne fabrique aucune victoire narrative automatique.

Chaque carte est une scène d'exploration issue du validateur canonique :
coordonnées, obstacles franchissables par itinéraire, points requis,
une sortie, dialogues de témoins et personnages facultatifs.
Les points nécessaires **doivent** être examinés avant le dialogue.
Les civils ont une échéance en pas d'exploration ; rater un secours
n'empêche pas d'avancer ni de terminer l'acte.

## Impact gameplay vérifiable

Les trois civils sauvés alimentent des drapeaux persistants, propres au pack
R20.B, au moyen de `Exploration.actor_action`, avec protection de
l'attribution **exactement une fois** :

| Civil secouru | Drapeau de campagne | Bénéfice de bataille, si sauvé |
|---|---|---|
| Éline (camp) | `camp_rescued` | +1 potion sur `a1_01_route` |
| Luc (forêt) | `forest_rescued` | +1 potion sur `a1_02_pont` |
| Lucie (hospice) | `refuge_rescued` | +1 potion sur `a1_03_hospice` |

Ces bonus sont matérialisés **avant** la bataille dans
`Battle.initial_state`, via `GameSession._battle_support`.
Ils sont donc inclus dans le contrat de replay tactique et ne dépendent
pas d'une UI ou d'un compteur secondaire. Le secours n'est pas nécessaire
pour déclencher la sortie du niveau. Les choix archives/otages, les niveaux,
l'équipement et la suite de l'Acte I conservent leurs règles actuelles.

## Compatibilité des sauvegardes

Le pack original `jeanne.game.json` reste **inchangé**.
`jeanne.r20b.game.json` utilise le schéma `GameProject` version 1,
mais introduit des scènes explorables et du soutien tactique : son digest
`gameplay_project_digest` diffère. Une sauvegarde existante ne peut être
chargée dans un autre pack sans migration explicite ; le système
`IncompatibleSaveError` doit la refuser sans altération. Les changements
de contenu ne sont jamais injectés dans les anciens slots.

## Validation reproductible

```bash
python -m unittest tests_standalone.test_r20b_jeanne_playable -v
python -m unittest tests_standalone.test_r20_act1_contract \
  tests_standalone.test_jeanne_acte1 \
  tests_standalone.test_jeanne_prologue -v
```

Le nouveau test exécute les **vrais combats** des cinq étapes de l'Acte I
depuis le camp pour les deux choix archives/otages, sans forcer les résultats,
et vérifie les secours, l'inventaire initial, la sauvegarde/reprise, les
endings et le refus croisé des sauvegardes originales. Les tests de prologue
complètent le parcours en amont. La CI headless n'est **pas** un test GPU
réel, ni une validation artistique ou de confort joueur.

## Restant pour R20.B et R20.C / R20.D

L'exploration ci-dessus utilise les **thèmes terrain génériques existants** :
la forêt n'est pas encore une scène artistique finalisée avec animations,
cinématiques contextuelles et son spatialisé. Les missions tactiques R20
restent celles du Content préexistant ; le dialogue détaillé des
antagonistes, les scènes de transition, les retours visuels/sonores, le
contrôle clavier/manette Qt sur matériel et le contenu qualitatif de
l'Acte I exigent encore des revues dédiées.

R20.C traite maintenant [les cinématiques authorées, l'après-archives/otages et les épilogues persistants](R20_C_CINEMATICS_AND_PERSISTENCE.md) dans une nouvelle variante isolée. L'auto-déclenchement complet dans le Player Qt et une éventuelle migration volontaire des slots demeurent des gates ouverts. R20.D devra
prouver qu'un joueur externe peut réellement jouer et finir la
campagne complète sans Studio, avec export natif/retours de playtest.
Ce pack ne ferme **pas** le gate global R20.
