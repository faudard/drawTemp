# R49.C2 — Premier scénario créé depuis le Studio Qt

**Statut : incrément en PR empilée sur R49.C1 (#393).**
R49.C2 couvre l'édition d'un vrai déclencheur CT et d'une scène narrative
depuis les widgets Qt. Il ne certifie toujours ni le Player natif, ni
l'export final, ni le parcours auteur tiers VS-49.

## Parcours accessible depuis Studio

1. Dans **Ateliers → Événements / Animation**, ouvrir l'onglet
   **Premier scénario R49** de l'atelier R28.D.
2. Choisir une mission existante. Indiquer deux **IDs nouveaux** pour le
   trigger tactique et la scène narrative, un tick (1..100000), un titre,
   un intervenant, une réplique et une action **message**.
3. Choisir **Prévisualiser sans modifier** : le modèle R49 vérifie
   la révision, la mission, les types et les IDs, puis l'API R1 effectue
   un preview complet Content + GameProject. Aucun fichier ni état live
   n'est modifié à ce stade.
4. Choisir **Créer scène et action (un Undo)** : une seule transaction
   crée le trigger Content, son action `message`, la scène GameProject
   et le lien `during_tactical_event[mission/event]`.
   Un seul Undo annule ces quatre écritures ; Redo les restaure.
5. Le bouton **Enregistrer puis lancer le vrai Player…** délègue à
   `StudioWindow.playtest()` (R49.B3). Il demande la sauvegarde
   canonique puis lance le Player surveillé, si disponible. Un lancement
   ne prouve PAS que l'événement ait réellement été exécuté en jeu.
6. **Ouvrir l'export Player natif…** délègue à
   `StudioWindow.export_player()` (R15), qui ouvre son assistant avec
   préflight, runtime natif et exigences de droits. Le clic sur le
   bouton ne signifie PAS que le bundle existe ni qu'il est certifié.

L'assistant n'invente **aucun schéma JSON** et ne transforme pas un
jeu SRPG en runtime action/RPG/hybride. Il réutilise `R9.event_composer`,
`sporebound.story_authoring`, la validation `GameProject/Content`
et `AuthoringSession.preview_pair/apply`. Il écrit uniquement sur la
session canonique du Studio.

## R49.C1 renforcé

Le harness `drawtemp.quality.r49_creator_gate` ajoute désormais une
création **effective**, headless et atomique de scène/trigger/message
sur le même projet, avant Undo/Redo/save/reopen et `R15.preflight`.
Il vérifie dans les documents persistés :

- `Content.missions[].triggers[]` contient l'action `message` attendue ;
- `GameProject.story.scenes[]` contient la scène ;
- `GameProject.story.during_tactical_event` lie la bonne mission
  et le bon trigger à la scène.

Le rapport signale `r9_scene_trigger_action = true` et conserve
`qt_gui_author_journey = false`, `real_gameplay_action = false`
et **gate.status = NO_GO**. Ces valeurs ne sont pas des données fictives
de runtime ; elles indiquent exactement la portée du test.

## Régressions prévues

```sh
python -m unittest -v \
  tests_standalone.test_r49_first_scene \
  tests_standalone.test_r49_creator_gate \
  tests_standalone.test_r49_playtest_lifecycle \
  tests_standalone.test_r49_inspector_integrity \
  tests_standalone.test_r28d_animation_events_roundtrip \
  tests_standalone.test_r28_creator_workflow \
  tests_standalone.test_drawtemp5_r15_creator

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.qt_shell --workspace events --smoke
```

Python 3.12 et PySide6 sur Linux, Windows et macOS. L'exécution effective
et les rapports verts doivent être vérifiés sur le SHA courant avant de
qualifier ces tests de réussis.

## Gate onscreen obligatoire

- Créer un projet via le wizard sans JSON, puis naviguer dans R28.D.
- Sur une session Qt **réelle**, prévisualiser puis appliquer la scène,
  voir le trigger et la scène dans l'atelier et leur lien canonique.
- Tester les doublons, une révision stale, une annulation et Redo.
- Sauver/rouvrir depuis le Studio, inspecter le lien, lancer le vrai
  Player Qt, atteindre en combat le tick demandé, constater
  **effectivement** la sortie message et le dialogue.
- Fermer le Player et choisir « Revenir à l'édition testée » ;
  vérifier les ressources, diagnostics et absence de divergence.
- Effectuer préflight strict et export avec runtime natif réel
  et licences approuvées ; vérifier le bundle sur trois postes propres.
- Faire exécuter le parcours libre et guidé par des auteurs tiers,
  avec captures, observations d'accessibilité, timings et P0.

Ce lot n'implémente pas de nouvelle interface pour le combat temps réel,
le choix narratif avancé, l'édition de scènes complexes, les assets
propriétaires ou les mesures GPU. **R49.C2 = code livré en PR ;
gate R49 / VS-49 toujours NO-GO.**
