# R49.C1 — Creator Vertical Slice & Gate Ledger (8.9)

**État : CODE EN PR, sans validation CI avérée. R49 = NO_GO.**
Dépendances empilées : R49.A (#383), R49.B1 (#388), R49.B2 (#390),
R49.B3 (#392). Ce lot **ne certifie ni VS-49 complet ni la version 8.9**.

## Exécution réelle, reproductible, sans retoucher les JSON à la main

```sh
python -m drawtemp.quality.r49_creator_gate \
  --output ./r49-evidence \
  --revision <SHA-40-du-commit-testé> \
  --genre srpg \
  --profile-samples 3
```

La commande refuse une destination existante ou un symlink, une révision
invalidée, un genre indisponible ou un échantillonnage hors contrat.
Le dossier n'est publié qu'après toutes les vérifications d'un **vrai**
parcours headless canonique :

1. R28 `create_genre_project("srpg")` (R15 crée les deux fichiers canoniques).
2. `AuthoringSession.open` ; inventaire R2 des cartes et personnages.
3. Édition d'un nom de carte et d'un nom de personnage avec
   `inspector_model.edit_properties`, deux transactions typées R1.
4. Undo, Redo, vérification de la paire complète ; sauvegarde atomique
   existante, fermeture virtuelle puis réouverture d'une nouvelle session.
5. `R15.preflight` sur les deux fichiers et sur les assets réellement présents.
6. Hash SHA-256 des deux fichiers. Si le profil CPU est demandé, mesure
   **R30.F** `collect_profile` des opérations canoniques/synthétiques,
   p50/p95/p99 et pic mémoire tracée ; vérification de non-mutation des sources.
7. Si `--runtime-dir` désigne un runtime natif **préexistant**, packaging
   R15 **preview** et vérification du manifest du bundle. **Jamais**
   de création d'un faux exécutable dans l'outil. Sans runtime :
   `native_bundle.status = blocked`.

L'exercice n'appelle pas le vrai Player, n'affirme aucune action de combat
effectivement jouée et ne prétend pas qu'un scénario UI a été créé par un
auteur non technique. Le mode `narrative` est disponible selon les capacités
R28 ; les modes action/RPG/hybride **restent refusés** faute de contrat runtime
complet. Le test d'intégrité du bundle dans `tests_standalone` utilise un
binaire placebo pour valider le manifest uniquement, clairement non
exécutable et non certifiant.

## Livrables du dossier

- `project/game.json` et `project/game.game.json` : projet authored.
- `report.json` : tests réellement réalisés, SHA-256 des documents,
  préflight et **gate NO_GO** + matrice d'évidence manquante.
- `profile.json` : optionnel ; profil local R30.F, informations machine,
  distinct d'un benchmark GPU certifié.
- `bundle-preview/` : optionnel, si et seulement si un runtime natif existe
  et que la vérification d'intégrité R15 réussit.

`report.json` n'enregistre aucun chemin absolu source ni log Player ; le
rapport de profil R30.F contient néanmoins des métadonnées de la machine
et ne doit pas être partagé publiquement sans revue.

## Matrice de preuves bloquantes (R49.C)

| Dimension | Niveau automatisé R49.C1 | Gate réel |
| --- | --- | --- |
| R28/R1/R2/R15 (sans édition JSON manuelle) | Check headless réel | Ne certifie pas l'ergonomie Qt |
| Undo/Redo, sauvegarde/reopen | Vérifié sur vraie paire | Crash injection et régression multi-ateliers restent |
| Export | Préflight ; manifest preview **si runtime fourni** | Runtime natif exécuté sur poste propre, licences strictes |
| Player | Contrat B3 supervisé (tests indépendants) | Actions de jeu et retour onscreen sur 3 OS |
| Profil p95/p99 | CPU R30.F avec charge et environnement | Baseline matérielle, GPU, seuils, endurance et reviewers |
| Auteurs tiers | Aucun test humain simulé | 2 auteurs, guidé puis libre, vidéo/captures et observations |
| CI | Workflows décrits dans le dépôt | 3 OS, jobs verts sur SHA final présent dans `master` |
| A11y | Contrats Qt en B1/B2 | NVDA/Orca/VoiceOver, clavier, contraste et DPI |

Le ledger accepte seulement des fichiers locaux existants et ordinaires
(max 8 MiB, sans symlink), les indexe par hash SHA-256 et les classe
**not_independently_verified**. **Même un fichier JSON qui proclame
`"GO"` ne peut pas promouvoir le statut automatique en GO.**

Clés admises de `--evidence KIND=FILE` :
`ci_linux`, `ci_windows`, `ci_macos`, `author_guided`,
`author_unguided`, `onscreen_linux`, `onscreen_windows`,
`onscreen_macos`, `native_player_linux`, `native_player_windows`,
`native_player_macos`, `accessibility_review`,
`hardware_profile`, `licenses_review`, `replay_save_review`,
`native_export_clean_machine`.

L'exécution de la commande retourne 0 si le **harness** a fonctionné,
mais le champ `gate.status` reste **NO_GO** en attendant une revue
indépendante. Ce n'est pas une erreur du test, c'est une séparation
intentionnelle entre une preuve technique partielle et la décision release.

## CI et tests

```sh
python -m unittest -v \
  tests_standalone.test_r49_creator_gate \
  tests_standalone.test_r28_creator_workflow \
  tests_standalone.test_drawtemp5_r15_creator \
  tests_standalone.test_drawtemp5_r15
```

CI Python 3.12 sur Windows/Linux/macOS et génération d'un dossier de
preuve headless par OS. Les rapports conservés en artifact GitHub sont
**non certifiants**. Absence de jobs CI exécutés = preuve manquante.

## Passage R49.C2 recommandé

1. Exécuter **vrai Studio Qt visible + vrai Player** avec SRPG/narratif,
   enregistrer session et problèmes observés.
2. Couvrir la création d'une **scène et d'une action jouable depuis l'UI** ;
   actuellement le parcours headless ne crée ni trigger ni action de combat
   et ne satisfait pas seul VS-49.
3. Faire tester l'onboarding à deux auteurs tiers indépendants ; documenter
   chaque blocage P0 et correction.
4. Mesurer sur postes cibles CPU/GPU/frame time p95/p99/mémoire après
   établissement des baselines ; vrai export clean-machine et licences.
5. Faire valider R49.6 + R49.10 par un responsable release sur les SHAs
   effectivement fusionnés dans `master` ; conserver NO_GO sinon.

**Décision R49.C1 : NO_GO, preuves en cours de constitution.**
