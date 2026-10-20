# R31.I — Stabilisation, attestation locale et gate multi-OS

**État : implémentation en brouillon PR #385, PAS certifiée.** Ne pas fusionner R31.E–I sur master avant validation réelle.

## Correctifs de fiabilité

- R31.F : l'écriture d'une variable refuse le changement de type bool↔int en cours de Battle. Le budget de 4 096 événements est vérifié **avant** l'émission pour qu'aucun événement incompatible n'entre dans le journal.
- R31.H : le test de sauvegarde avant victoire vérifie le slot Player primaire avec PlayerSlotStore.inspect()/load(), puis rejoue le GameSession canonique. Les preuves de butin et d'interaction coffre viennent de Battle.events / Battle.loot, pas d'un champ HUD absent.
- R31.H : des tests de validation Content refusent une quête avec coffre absent ou coffre prétendument déjà ouvert au chargement.
- Aucun nouvel état de campagne, deuxième registre de variables ou format de sauvegarde n'a été introduit.

## Attestation R31.I

Le script scripts/r31i_certify.py exécute les vrais tests unittest et produit une attestation JSON : suite, commit SHA, OS, version Python, nombre exécuté, erreurs, échecs, tests ignorés, extraits de diagnostics. Le statut est FAIL si une suite n'a aucun test exécuté, n'atteint pas le minimum fixé, possède au moins une erreur/échec ou un seul test ignoré.

Depuis la racine du dépôt :

    python -m pip install .
    python scripts/r31i_certify.py --suite headless --min-tests 25 --output r31i-headless.json

Pour les tests GUI Qt (avec un display compatible ou la plateforme offscreen Qt) :

    python -m pip install '.[qt6]'
    QT_QPA_PLATFORM=offscreen python scripts/r31i_certify.py --suite qt --min-tests 5 --output r31i-qt.json

Sur Windows PowerShell, définir auparavant $env:QT_QPA_PLATFORM = 'offscreen' et $env:QT_QUICK_BACKEND = 'software'.

Les preuves de la CI doivent être téléchargées depuis GitHub Actions comme artefacts r31i-headless-<OS> et r31i-qt-<OS>. Leur présence et leur statut PASS ne doivent être interprétés que pour le SHA exact de la PR.

## Cause CI : faits vérifiés

Le workflow DrawTemp R31.ABCDEFGH sur la PR #385 a conclu failure le 20 octobre 2026 avec **zéro job**, aucun step/log de test. Au même moment plusieurs workflows indépendants du dépôt affichaient failure, ce qui rend improbable une simple assertion Python défaillante dans R31. En revanche il n'existe pas assez de données pour attribuer avec certitude ces échecs au quota, à la facturation, aux runners ou aux permissions.

À vérifier dans GitHub : Actions > workflow run > annotation d'exécution / notification ; Settings > Actions (permissions, règles, runners) ; politique de consommation/runners du compte ou de l'organisation. **Les droits d'administration nécessaires ne sont pas accessibles au connecteur** ; aucune de ces causes n'est déclarée comme confirmée.

## Gates précis

1. Trois attestations headless PASS (Ubuntu, Windows, macOS), avec le SHA courant et au moins 25 tests exécutés chacune.
2. Trois attestations Qt offscreen PASS, avec au moins cinq tests réellement exécutés chacune et aucun skip.
3. Vérification du parcours Jeanne complet dans le Player réel, y compris avant/après checkpoint, coffre une fois, récompense une fois, compatibilité des journaux.
4. Absence de changement de manifests de règles pour les anciens projets qui n'activent aucun système R31.
5. Revue et résolution des échecs existants de la PR, puis retrait du brouillon seulement après les preuves.

**Statut présent : NO-GO.** Si GitHub Actions continue à conclure failure sans job, aucune attestation CI n'est produite ; le code de test et l'outil local ne valent pas certification exécutée.