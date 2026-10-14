# DrawTemp 5.0 — R0 : fondation Qt 6 et migration

## Objectif et état réel

Architecture retenue : **Studio Qt Widgets/PySide6, Player Qt Quick/PySide6,
rendu Qt Quick commun, Tactical Core Python indépendant**. Le runtime existant
reste la référence des règles et des formats. Les applications Tk restent
utilisables pendant la migration.

Référence : `8d29cdf8eaa907a9317130ae5a2efc4c6024f9db` (14 octobre 2026).
La PR #218 est **fusionnée**, contrairement au statut de la proposition initiale.
Cette branche part directement de cette consolidation et en conserve les assets,
les missions et les fonctionnalités. Aucun merge supplémentaire n'est requis.

R0 est une fondation exécutable, pas un Studio terminé. **La certification globale
reste bloquée par les échecs hérités de la baseline** ; voir `baseline.json`.
Les workflows existants restent inchangés : aucun test historique n'est désactivé.

| Lot | Livrable | État |
| --- | --- | --- |
| R0.1 Baseline | Commit gelé, suite historique exécutée, échecs identifiés | Établie ; certification verte à obtenir |
| R0.2 Audit | Inventaire AST, imports UI directs, chemins transitifs différés, gate d'import initial | Livré |
| R0.3 ADR | UI, rendu, threading, sérialisation et packaging ci-dessous | Décisions initiales consignées |
| R0.4 Packages | `drawtemp.core/sdk/render/studio/player/assets/platform` | Frontières créées ; extraction complète en R1 |
| R0.5 Compatibilité | Contrat conservateur sur formats, identités, migrations et rollback | Livré |
| R0.6 Harnais | Legacy/adapter, dialogue, interaction, combat, reprise et replay | Exécutable et couvert par tests |
| R0.7 Référence | Petit projet Jeanne déterministe, village/lisière, personnages, porte, levier et dialogue | Validé headless ; revue graphique à venir |

## Utilisation

Le runtime historique conserve sa compatibilité Python >=3.10 et ses commandes.
La cible de qualification initiale du nouveau client Qt est **Python 3.12**.
Le lancement Qt refuse les autres versions avec un message explicite. PySide6
6.8.3 est épinglé pour cette première base reproductible ; ce n'est pas une
prétention à utiliser la dernière version Qt. Une montée de version aura son
propre passage de CI et sa validation visuelle sur les trois OS.

```sh
python -m pip install ".[qt6]"
python -m drawtemp.platform.qt_bootstrap
# ou : drawtemp-qt6
python -m drawtemp.platform.qt_bootstrap --smoke

python scripts/audit_drawtemp5.py --check --report r0-imports.json
python -m drawtemp.sdk.migration --report r0-parity.json
python -m unittest tests_standalone.test_drawtemp5_r0 -v
```

La fenêtre de preuve contient un vrai `QMainWindow` et un `QQuickWidget` qui
charge le composant QML partagé. Elle annonce explicitement que le renderer
isométrique sera livré en R3. Elle ne prétend ni éditer ni jouer une campagne.
Le Player Qt Quick indépendant et les docks du Studio seront construits en R2.

En CI, `QT_QPA_PLATFORM=offscreen` et `QT_QUICK_BACKEND=software` servent uniquement
au test de composition sans écran. Le lancement normal ne force aucun backend.
Ce test ne certifie **ni le GPU, ni les performances, ni le rendu isométrique**.

## ADR-001 — deux applications, un runtime

- `drawtemp.core` expose les modèles canoniques existants. Aucun deuxième
  `Content`, `GameProject`, moteur de combat ou format de sauvegarde.
- `drawtemp.sdk` fournit une façade expérimentale de migration. Les commandes
  sont déléguées à `GameSession`. Les snapshots sont des copies détachées du
  recording canonique, pas encore les snapshots immuables de présentation R1.
- `drawtemp.studio` recevra les fenêtres Widgets, docks, modèles/vues et commandes
  d'édition. Pas de création de widgets Tk depuis le nouveau Studio.
- `drawtemp.player` recevra la présentation QML et les contrôleurs du Player.
- `drawtemp.render` sera commun aux deux clients, avec géométrie, caméra,
  profondeur et asset IDs identiques. Aucun calcul de règles dans QML.
- `drawtemp.assets` réutilisera le registre `sporebound.assets`, avant extraction.
- `drawtemp.platform` possède l'initialisation Qt et les services de plateforme.

Les répertoires sans fonctionnalité sont des frontières documentées, pas des
systèmes annoncés comme terminés. Les imports historiques `sporebound.*` sont
conservés jusqu'à R16, y compris pour les outils et sauvegardes existants.

## ADR-002 — Scene Graph et intégration Widgets/Quick

Le renderer cible est Qt Quick Scene Graph. Le composant QML de R0 est une preuve
de chargement et de packaging. `QQuickWidget` constitue le premier point
d'intégration du viewport dans les docks Widgets ; R3 devra mesurer son coût
contre une fenêtre Quick embarquée avant de figer la solution à grande échelle.
Le Player utilisera Qt Quick directement, sans dépendance aux widgets du Studio.

Les coordonnées tactiques restent celles du modèle. Isométrie, profondeur,
occlusion, éclairage et animations restent de la présentation. Le picking doit
retourner des coordonnées/identifiants canoniques, jamais modifier les règles.
Une extension C++ ne sera envisagée qu'après profilage et budget mesuré.

## ADR-003 — ownership et threading

En R0, les appels de simulation sont synchrones ; aucune concurrence artificielle.
Les QObject et les widgets appartiennent au thread UI ; aucun objet graphique
ne traverse la frontière du SDK. R1.9 pourra confier la simulation à un worker
unique, qui possède alors seul sa session. Les échanges utiliseront des états
copiés/immuables et des commandes identifiées. Toute réponse asynchrone portera
la révision du document ; un calcul périmé sera rejeté. Aucun accès concurrent
à `GameSession`, aucun callback de widget dans le cœur des commandes.

## ADR-004 — compatibilité et migration non destructive

| Ressource | Garantie R0 |
| --- | --- |
| Content / GameProject | Structures et versions existantes conservées ; validation canonique |
| Sauvegardes | Chargement par GameSession ; aucune réécriture lors d'une simple lecture |
| Identités contenu/projet/règles | Contrôles existants conservés, refus d'une incompatibilité |
| Replays | Même seed, commandes, états tactiques et conséquences ; replay validé |
| Assets | IDs, chemins et métadonnées actuels conservés |
| Projet de référence | Dérivé en mémoire ; les fichiers Jeanne originaux restent intacts |
| Configuration UI future | Sidecar distinct ; ne modifie pas les identités de gameplay |
| Anciennes versions | Compatibilité limitée aux formats déjà acceptés par le runtime |

Tout changement ultérieur de format exige une migration nommée/versionnée,
une sauvegarde de l'original, une sortie distincte, un rapport de différences et
un test de reprise. Pas de conversion silencieuse, pas de suppression du legacy
avant le gate R16. R0 n'élargit pas artificiellement les formats déjà supportés.

## ADR-005 — distribution

Qt est une dépendance **optionnelle** (`.[qt6]`) : installation headless sans Qt,
commande historique intacte, nouveau point d'entrée distinct. Le QML est inclus
dans le package et testé après installation hors du checkout. L'export Player
sans les outils d'auteur reste R15 ; le package actuel inclut encore le legacy.
L'audit des licences et la validation des bundles natifs devront précéder R15.

## Audit et dette explicitement conservée

`scripts/audit_drawtemp5.py` parcourt les imports absolus, relatifs et les appels
littéraux à `import_module` / `__import__`. Il produit la liste des modules,
les dépendances, les imports UI et les chemins depuis core/sdk vers l'UI.
Les imports dynamiques non littéraux sont listés pour revue manuelle. Cela ne
constitue pas une preuve de tous les chemins d'exécution Python possibles.

Le gate statique bloque les dépendances UI **à l'import initial** de core/sdk.
Les dépendances différées dans les fonctions sont conservées dans le rapport
`deferred_ui_paths_to_extract_in_r1`, et non masquées. Notamment,
`iso_structures → iso_architecture → atlas Tk` reste à séparer en R1 : données
et géométrie d'un côté, peinture/canvas de l'autre. L'interdiction dynamique des
imports Tk/Qt est en plus testée pendant tout le scénario de référence.

Un premier couplage a été supprimé : `SURFACES` et `FEATURES` appartiennent
maintenant à `terrain_schema`, partagé entre modèle, transformations et rendu.
`iso_map` continue de les réexporter pour préserver ses clients historiques.

## Harnais et projet de référence

`reference_project()` dérive une mission d'entraînement de Jeanne en mémoire,
avec sol pavé de village, lisière d'arbres, Jeanne/Renaud, dialogue d'entrée,
porte fermée et levier adjacent. Il conserve les règles et schémas existants.
Ce petit fixture est un outil de certification, pas une nouvelle campagne produit.

Le gate : dialogue → mission → interaction réelle avec le levier → porte
franchissable → sauvegarde → reprise des deux runtimes → combat commandé par
l'IA jusqu'à victoire → relecture du replay. Aucune assignation artificielle du
résultat, du CT ou de l'acteur actif. Les états sont comparés après chaque action.
Un test injecte un adapter défectueux et exige la détection de la divergence.

Les UUID de bataille sont non déterministes par conception. La comparaison
normalise seulement l'UUID de la bataille courante et sa référence dans
`tracked_battles`, et retire le hash d'enveloppe qui dépend de cet UUID. Les
recordings originaux restent vérifiés par le runtime ; les commandes, événements,
états, seeds et conséquences ne sont pas supprimés de la comparaison.

`reference-baseline.json` est gelé et a été comparé au runtime du commit initial
non modifié. Le test ne le régénère jamais. Toute modification doit faire l'objet
d'une revue des conséquences de gameplay, pas d'un renouvellement automatique.

## Critères de sortie restant à certifier

- Corriger ou qualifier les échecs de la suite globale du commit de départ.
- Obtenir les résultats des jobs GitHub Python et Qt sur les OS ciblés.
- Vérifier manuellement la fenêtre Qt sur Windows, Linux et macOS.
- R3 : GPU réel, profondeur, picking, relief, sprites et parité Studio/Player.

La réussite du harnais R0 n'est pas une certification de toutes les campagnes,
des éditeurs, de toutes les anciennes sauvegardes ni de l'extraction complète R1.

## Validation locale de cette tranche

- 55 tests ciblés réussis : fondation, GameSession, prologue/chapitre Jeanne,
  événements, transformations et structures/cartes isométriques.
- Smoke Qt 6.8.3 Widgets + Quick réussi, y compris depuis le package installé
  hors du dépôt, en backend logiciel/offscreen.
- Référence gelée comparée au runtime du checkout initial non modifié.
- Audit : 263 modules, 26 avec imports UI directs ; zéro chemin UI à l'import
  initial de core/sdk ; 20 chemins différés enregistrés pour extraction R1.
- Suite historique relancée dans un worktree intact du commit de référence :
  voir les nombres et identifiants exacts dans `baseline.json`.

Les validations locales n'attestent pas les jobs GitHub ni le rendu GPU réel.

## Suite R1.A

La [première tranche SDK R1](R1_SDK.md) sépare les données de bâtiments du rendu,
active le gate statique strict et ajoute l’API de simulation à snapshots immuables.
Le rapport `dependency-audit.json` ci-dessus reste le constat historique de R0.
