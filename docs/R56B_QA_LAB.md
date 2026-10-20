# R56.B — QA Lab visuel et batch headless

Statut : proposition de développement P0, non certifiée. R56.A est déjà
fusionné ; R56.B ne remplace pas les tests humains, la validation Qt/GPU
ou la détection avancée R56.C.

## Utilisation dans le Studio

Menu Outils > R56 • QA Lab du gameplay.

Le dialogue prend une copie détachée de la session AuthoringSession R1.
Renseigner le SHA Git complet de 40 caractères (révision déclarative), la
campagne, la seed et un identifiant de scénario. Choisir une opération
GameSession autorisée, entrer ses arguments au format JSON, puis une assertion
facultative sur une propriété de GameSession.recording.

La capture est MANUELLE : elle ne surveille pas les saisies d'un Player
réel ni n'enregistre une vidéo. Ajouter chaque commande avec Capturer cette
commande, puis cliquer Créer scénario pour épingler les digests Content
et GameProject. Aucune action n'est exécutée au moment de la capture.

Un lien facultatif vers une ressource du Studio peut être attaché à chaque
commande. C'est un lien typé (family, mission_id, resource_id), stocké dans
la suite JSON annexe, et non dans le projet ou le save. Seules les ressources
réellement présentes dans l'index de l'éditeur peuvent être localisées.

Exécuter le lot lance 1 à 12 scénarios via un worker Qt et l'exécuteur R56.A
canonique, sans modifier la session de l'éditeur. Sélectionner un scénario et
une étape pour voir commande, digest, checkpoint, mode, erreur et source.
Les numéros sont des indices de commande et non des ticks moteur universels.

Importer/exporter une suite, exporter un rapport, puis comparer avec un rapport
précédent du même lot par statut et hash de chaque étape. Les suites
incompatibles ou dépassant 2 MiB sont rejetées.

## API Python

Module : drawtemp.quality.r56_lab.

- capture_case : production d'un cas depuis des actions explicites ;
- build_suite / validate_suite : format versionné, 12 cas maximum ;
- run_batch : vrai GameSession, replay/checkpoints R56.A, compteurs ;
- inspect_case : trace + premier échec + lien de ressource facultatif ;
- diff_batches : comparaison de rapports avec même empreinte de suite ;
- read_suite / read_report / save_json : I/O JSON bornées.

CLI headless (suite R40 mono-starter, rapport identique à l'API Qt) :

    python -m drawtemp.quality.r56_lab --suite scenario-suite.json \
        --revision "$(git rev-parse HEAD)" --report r56-batch.json

Le CLI retourne 0 seulement lorsque tous les scénarios du lot passent ; il
retourne 2 pour no-go, source périmée, schéma invalide ou sortie dangereuse.

Exemple API :

    from drawtemp.sdk.r40_starters import create_starter_pair
    from drawtemp.quality.r56_lab import capture_case, build_suite, run_batch

    content, project = create_starter_pair("r40-adventure")
    sha = "a" * 40  # Exemple seulement : utiliser git rev-parse HEAD
    case = capture_case(
        content, project, identifier="movement",
        starter="r40-adventure", revision=sha,
        steps=[{"operation": "route_realtime_step", "args": [0, 0],
                "expect": [{"path": ["mode"], "equals": "campaign"}]}])
    batch = run_batch(build_suite([case]), content, project, revision=sha)
    assert batch["status"] == "headless-passed"

Ce succès ne prouve que le replay headless du lot. Les rapports portent
TOUJOURS release_certified=false et revision_independently_attested=false.
Un scénario bloqué/échoué produit un état no-go, jamais un faux vert.

## Vérifications attendues

    python -m unittest tests_standalone.test_r56a_scenarios -v
    python -m unittest tests_standalone.test_r56b_qa_lab -v
    QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r56b_qa_lab_qt -v

Le test Qt est facultatif sans PySide6. Les suites de régression R40, R49,
R55 et les matrices Windows/Linux/macOS restent nécessaires.

R56.C : softlocks automatiques, récompenses doublées, collisions et
transitions, minimisation de contre-exemple par sous-séquence, CI
indépendamment attestée et décision GO/NO-GO sur SHA final.
