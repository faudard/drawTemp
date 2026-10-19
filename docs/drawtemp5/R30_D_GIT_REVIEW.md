# R30.D — Collaboration Git locale et revue sémantique

**Statut : proposition de code, PR empilée sur R30.C (#340), R30.B
(#329) et R30.A (#305).** Ce lot couvre une première lecture contrôlée
de l'historique Git LOCAL, sans prétendre offrir du travail collaboratif
distant, des conflits visuels spécialisés ou un Creator Studio 7.0 certifié.

## Motivation et architecture

Un utilisateur doit pouvoir comparer sa session DrawTemp non sauvegardée
avec deux versions de son jeu suivies dans Git, puis choisir explicitement
les valeurs de ses conflits sans perdre ses modifications locales.

Le nouveau module headless drawtemp/studio/r30_git_review.py implémente
LocalGitProject et GitReviewController. Il utilise les contrats
Content/GameProject réels et R30.A/C semantic_review (merge à trois
voies par identifiants de mission, listes ordonnées traitées comme atomiques).
L'UI Qt existante R30.C réutilise ses widgets de conflits et la session
AuthoringSession partagée du shell R2.

## Flux utilisateur

1. Ouvrir un Content/GameProject déjà enregistré dans un dépôt Git local.
2. Depuis Studio -> Outils -> Packs et revue des conflits, ouvrir
   l'onglet Git local, indiquer une référence de base (branche ou tag)
   et une référence entrante (branche ou commit ; HEAD accepté).
3. Cliquer Comparer en lecture seule. Pour chaque référence, résoudre
   précisément son commit par Git rev-parse puis lire par ls-tree/cat-file
   les blobs des deux fichiers suivis, sans checkout de branche.
4. Refuser les fichiers non suivis à une ref, symlinks, Gitlinks,
   entrées hors projet, noms de ref invalides, blobs JSON de plus
   de 8 MiB, JSON incohérent, clefs JSON dupliquées et contraintes
   Content/GameProject non respectées.
5. Visualiser les différences et choisir garder local / prendre entrant
   pour chaque conflit dans l'onglet Diff & conflits (même grille
   que la revue de paires de fichiers R30.C).
6. Valider que la base est un ancêtre réel Git de l'entrant et du HEAD local.
   Avant validation en session, comparer de nouveau les OID de commits
   de base/entrant et HEAD local, les hashes des deux fichiers locaux, et la
   révision plus le fingerprint de la session.
7. Fusionner UNIQUEMENT via AuthoringSession.preview_pair/apply avec
   validation canonique et Undo/Redo, sans enregistrer automatiquement
   sur le disque. L'utilisateur sauvegarde depuis le shell quand il le
   décide, avec les contrôles de sauvegarde concurrente R1 existants.

## Engagement Git : lecture seule

Les sous-commandes Git exécutées ici sont uniquement :
- rev-parse --show-toplevel / --is-inside-work-tree / --verify,
- merge-base --is-ancestor,
- ls-tree,
- cat-file -s / cat-file blob.

Aucune utilisation de shell=True, pas de hooks activés par le code,
pas de fetch, pull, push, stash, checkout, add, commit, merge, reset,
rebase, écriture de refs ou d'index. Les tests d'intégration, dans
leurs propres dépôts temporaires, utilisent git init/add/commit
uniquement pour fabriquer des fixtures et vérifier la non-mutation.

Les références sont validées et résolues en OID immuables avant accès
au contenu ; un tag/une branche modifié entre preview et apply provoque
un refus. Les fichiers physiques du projet actif sont également
figés par leur SHA-256. Les mutations de session sont refusées si la
révision évolue entre les deux actions.

**Attention :** ce n'est pas une transaction Git ; ce n'est pas non plus
une preuve de validité juridique des assets, un contrôle de contribution
multi-auteurs, un serveur de review ni un merge métier par commande.
Pour l'instant, l'éditeur ne commite jamais le résultat à votre place.
Une configuration Git locale non fiable n'est pas une frontière de
sandbox OS ; la source Git doit rester contrôlée par le développeur.

## API de revue

    from drawtemp.studio.r30_git_review import GitReviewController

    controller = GitReviewController(session, "mon-jeu/game.json")
    preview = controller.compare_refs("v1-base", "feature/game")
    decisions = {conflict.path: "local" for conflict in preview.conflicts}
    transition = controller.apply(decisions)
    # La session a gagné un Undo ; aucun git commit ni écriture disque.

Les noms de ref admis sont simples et qualifiés. Les syntaxes Git
révisionnelles complexes comme HEAD~1, rev:path et @{...}
sont volontairement interdites (créer un tag explicite au besoin).

## Test et critères d'acceptation

    python -m unittest tests_standalone.test_drawtemp_r30d_git -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp_r30d_qt -v

R30.D inclut un workflow Python 3.12 Linux, Windows, macOS,
tests R30.A/B/C, revue Git, Qt offscreen et baseline tactique Jeanne.
Les runners et résultats CI doivent être vérifiés sur le SHA final.

Les tests contrôlent : lecture de vraies révisions Git, merge non
conflictuel, conflit exigeant une décision, Undo, branche déplacée, HEAD local changé, base non ancêtre,
modification externe des fichiers, changement de révision de session,
injection de ref, document historique invalide, dépôt absent, refus de
modification Git/Content automatique.

## Restant à faire pour R30

Git distant, authentification et permissions, PR GitHub bidirectionnelles,
rebase conflictuel avancé, comparaison visuelle des cartes/scènes,
collaboration multiauteur simultanée et gestion des locks, plugins
sandboxés, modèles et galerie, performance 1M ressources, droits
validés et seconde production inter-genres certifiée ne sont pas
couverts. R30.5 est PARTIEL ; R30.10 reste bloqué par R25–R29.
