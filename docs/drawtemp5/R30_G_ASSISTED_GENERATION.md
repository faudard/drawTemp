# R30.G — Génération assistée de terrains et d'amorces de puzzles

**Statut : première tranche R30.7 en PR draft.** Dépend de R30.F (#356),
R30.E (#350), R30.D (#343), R30.C (#340), R30.B (#329), R30.A (#305).
Aucune génération « IA » ou export Player certifié n'est annoncée.

## Ce qui est développé

Trois assistants déterministes, locaux et optionnels, branchés **sans
nouveau schéma** sur Content v1 / GameProject v1 :

| Mode | Génération réelle | Précautions |
|---|---|---|
| Clairière | Petites mosaïques de surfaces dirt/sand/stone/cobble | Uniquement cellules vierges, non occupées et non éditées |
| Sentier | Marche quatre-connectée de surfaces, maximum 12 cases | Ne traverse pas les cases occupées, bloquées ou déjà peintes |
| Levier/porte | Deux objets canoniques door/switch, avec switch.link vers door.id | Validation du lien, positions libres adjacentes, levier accessible sans franchir la nouvelle porte |

Le terme « puzzle » désigne ici **une amorce jouable avec levier/porte**.
La recherche vérifie l'accès du joueur au levier sur la grille tactique
existante avec les portes existantes et la future porte considérées comme
bloquantes. Elle **ne prouve pas** que la porte soit indispensable pour
atteindre la fin, qu'aucun contournement n'existe, ni que tous les chemins de
quête/IA soient valides. Le level designer doit la placer sur un passage
approprié et réaliser un playtest. Aucun solvability solver global ou
générateur de puzzle graph R27 certifié n'est livré.

## Flux Studio et Undo

Ouvrir **Outils → Terrains et puzzles assistés…** puis choisir :
1. la mission existante ;
2. le mode (clairière, sentier, levier/porte) ;
3. le rectangle local (x, y, largeur, hauteur, borné à 16×16) ;
4. la graine entière non négative, et un namespace d'objet sûr pour puzzle.

**Prévisualiser sans modifier** calcule un candidat. Les cases conservées,
occupées, changées, et les positions exactes de la porte et du levier
sont affichées par une petite grille Qt Widgets. Le candidat complet
passe par \`AuthoringSession.preview_pair\`, qui vérifie Content/GameProject
avec les validateurs R1/Content existants. On ne crée aucune mission ni
objet hors de Content.

**Appliquer dans le Studio** nécessite un clic de confirmation. Une seule
opération \`AuthoringSession.apply\` ajoute un point Undo/Redo. Il n'y
a pas de \`save\`, de script, d'appel réseau, de lecture de modèle d'IA
ni de mutation globale avant confirmation. L'enregistrement reste séparé.

Tout changement du rectangle, du mode, de la graine ou de la mission
invalide l'aperçu. Un changement concurrent de révision de session, y
compris edit → undo ABA, est refusé par le contrat R1.

## API headless

    from drawtemp.sdk.authoring import AuthoringSession
    from drawtemp.studio.r30_assist_generation import AssistController

    session = AuthoringSession.open("jeu/game.json")
    helper = AssistController(session)

    proposal = helper.preview(
        "mission_1", rectangle=(1, 1, 4, 3),
        mode="clearing", seed=17, namespace="zone1")
    assert not proposal.to_dict()["applied"]
    transition = helper.apply(proposal)  # un seul Undo
    # session.undo() / session.save() restent explicites

Modes disponibles : \`clearing\`, \`trail\`, \`lever-door\`. Toutes les
propositions sont détachées des documents d'origine, et un résultat appliqué
ne peut pas être réappliqué sans une nouvelle preview. Les surfaces
autorisées sont les identifiants canoniques de \`sporebound.terrain_schema\`.

Sécurité de données :
- aucune case auteur existante n'est repeinte ;
- les unités (y compris footprints), objectifs, reliques, zones de
  déploiement, événements spatialisés, structures et objets sont évités ;
- les objets puzzle reçoivent des IDs namespacés, sans écraser ceux du
  niveau actif ;
- les placements de levier/porte sont différents, adjacents et validés
  par le modèle, sans ajuster secrètement le terrain bloquant ;
- aucune modification de GameProject, d'asset, de règle CT ni de replay.

## Tests et CI

    python -m unittest tests_standalone.test_drawtemp_r30g_assist -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp_r30g_qt -v

CI R30.G prévue sur Linux, macOS, Windows avec Python 3.12,
regressions Authoring R1, performance R30.F, baseline Jeanne et Qt
offscreen. Les résultats doivent être inspectés sur le SHA final.
Aucun « green » n'est déduit de l'existence de la PR ou du workflow.

## R30.7 : limites et suite

R30.7 **partiel** : pas de génération guidée par un modèle IA, pas de
solveur de donjon/gate/quest global, pas de génération de cartes multi-zones,
pas de grand stress-test de scènes réelles, pas de certification R27/R28
ou action-aventure R29. Des charges spéciales comme combats multi-fronts,
portes destructibles et sièges exigent toujours un playtest complet.

R30.10 est bloqué par R25–R29 ; les quatre modèles R30.E restent des
exemples narratifs et non des jeux complets inter-genres certifiés.
