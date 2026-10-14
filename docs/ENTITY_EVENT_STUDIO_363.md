# Event Studio 3.6.3 — Branch QA & Coverage

## Objectif

Mesurer **ce qui est relié**, **ce que StoryBook est réellement capable de
parcourir dans des états synthétiques bornés**, et **ce que Battle déclenche
dans un aperçu isolé**, sans confondre ces preuves.

Le panneau **QA & couverture** s'ouvre depuis l'**Arbre narratif** déjà
existant ; il ne crée pas d'éditeur ni de schéma parallèle. Les diagnostics
sont consultables, double-cliquables (recentrage dans le graphe) et exportables
en JSON déterministe.

## Trois niveaux de preuve

### 1. Audit structurel — `audit_branch_coverage`

- Décompte de scènes, choix, scènes et choix atteignables depuis les
  entrées réelles (`entry_scenes`, `after_mission`,
  `after_strategic_event`, `during_tactical_event`).
- Distinction **scène non référencée**, **sous-graphe déconnecté** et
  **chemin conditionnel** (3.6.2).
- Signalement des **choix terminaux** uniquement à titre informatif :
  une fin de dialogue sans `next_scene` est souvent voulue.
- Validation locale conservatrice des conditions contradictoires :
  `all(flag=x et flag=y)`, `gte > lte`, égalité incompatible avec une
  borne, et `condition et not(condition)`. Les `any` ne sont déclarées
  contradictoires que si toutes leurs branches le sont.
- Références tactiques `after_choice` par mission.
- Les drapeaux dynamiques, décisions IA et conditions non prouvées
  contradictoires restent **indéterminés**, jamais marqués impossibles.

### 2. Sondes StoryBook — `probe_story_choices`

- Chaque racine déclarée est traitée séparément, avec un état
  `Campaign` synthétique jetable (or = 0, aucune mission terminée,
  drapeaux initiaux vides).
- Les transitions utilisent **réellement**
  `StoryBook.choices(progress)` puis `StoryBook.choose(progress, id)`.
  Les effets narratifs et les gardes du moteur s'appliquent : un choix
  conditionnel qui dépend d'un drapeau positionné par un choix précédent
  peut être exercé.
- Limites par défaut : **220 états**, **24 étapes**, **30 chemins finis**.
  Rapports explicites sur les choix exercés/non exercés et le budget.
- Les racines d'après-mission ou événements sont *forcées en entrée de
  sonde* ; cela ne prouve pas que leur événement source survient
  réellement en jeu.
- Un choix **non exercé** n'est pas déclaré impossible : budget,
  préconditions de campagne ou suite de missions pourraient le permettre.

### 3. Aperçus Battle — `probe_tactical_branches`

- S'appuie sur `event_branches.preview_choice_routes` déjà existant :
  contexte tactique isolé, `Battle.execute(story_effects)`,
  choix exclusifs et réunification `after_any`.
- Au plus **8 événements sources** par appel depuis le panneau
  (maximum technique : 20). Affiche blocages, erreurs et IDs
  d'événements déclenchés par choix.
- **Pas de replay certifié** : seul un enregistrement réel de
  `GameSession` et son rejeu peuvent attester un replay complet.

## UI

Bouton **QA & couverture** dans le bandeau de l'**Arbre narratif** :

- **Auditer la structure** : tableau de constats (niveau/scène/choix/raison)
  et résumé chiffré ; double-clic pour la navigation canonique.
- **Simuler les dialogues** : exécuter les choix StoryBook sur copies
  de Campaign et produire la liste d'options non exercées.
- **Prévisualiser événements** : sonder la conséquence tactique réelle
  des événements liés à des scènes.
- **Exporter JSON** : enregistrer le rapport complet, avec provenance
  et indicateurs `replay_verified=false`.

Les outils n'altèrent ni `Content`, ni `GameProject`, ni les sauvegardes
et ne modifient pas l'historique Undo/Redo.

## Commandes de validation

```bash
python -m unittest tests_standalone.test_branch_qa_363 -v

SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover \
  -s tests_standalone -p test_branch_qa_363_gui.py -v

python -m unittest tests_standalone.test_story_graph_navigation_362 \
  tests_standalone.test_visual_branch_graph_36 \
  tests_standalone.test_event_choice_branches_34 -v
```

Le test Tk/Xvfb est bloquant dans `.github/workflows/standalone.yml`.

## Critères de clôture

1. Rapports stables, bornés et exportables, sans altération de données.
2. Choix réellement parcourus par StoryBook distingués des choix simplement
   atteignables structurellement.
3. Contradictions démontrables signalées ; conditions dynamiques restant
   « à vérifier ».
4. Chemins sans `next_scene` visibles comme **fins**, pas comme erreurs
   inconditionnelles.
5. CI multi-OS et test Tk verts avant intégration de la PR.
