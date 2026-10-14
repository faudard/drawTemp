# Entity & Event Studio 3.6.2 — Navigation et diagnostic des parcours

**Périmètre :** intégration dans `StoryGraphEditor` existant,
sans nouvel onglet, nouveau graphe, format de sauvegarde ni règle gameplay.
Cette tranche complète 3.6 (ports et liens Canvas) et 3.6.1 (regroupements et
comparaison A/B).

## Recherche et recentrage

La barre **Rechercher** du haut de l'**Arbre narratif** propose :

- recherche textuelle insensible à la casse et aux accents sur
  les **IDs, titres, interlocuteurs et textes** de scènes ;
  **IDs, labels, conditions et destinations** des choix ;
  **IDs, conditions, actions et gardes** des événements tactiques
  de la mission active ;
- filtres **Tout / Scènes / Choix / Conditions / Événements / Problèmes** ;
- liste de résultats déterministe, avec nombre total de résultats et
  limitation explicite à 180 entrées visibles ;
- sélection d'un résultat puis **Centrer** ou sélection directe dans la liste :
  ouvre l'occurrence concernée, déplie ses ancêtres et replace la caméra
  au milieu de cette carte. Si le parcours n'existe pas depuis la racine
  actuellement affichée, utilise **Scène · id** comme racine d'**affichage
  uniquement**. Aucune racine d'entrée du jeu n'est modifiée ;
- recherche d'un événement placé au-delà de la palette par défaut de
  60 cartes : l'événement sélectionné est provisoirement épinglé à la
  dernière position visible, sans faire exploser le nombre d'items Canvas.

Le recentrage se fonde sur des chemins d'occurrences canoniques du
`StoryGraph` et non sur des identifiants de widgets. Les coordonnées de
Canvas sont recalculées à partir de la disposition courante.

## Diagnostic de portée narrative

`navigation_diagnostics` parcourt en largeur les scènes accessibles depuis
les **quatre familles de racines réellement déclarées** :

- `entry_scenes` : entrée de campagne ;
- `after_mission` : victoire ;
- `after_strategic_event` : événement stratégique ;
- `during_tactical_event` : événement tactique.

Les scènes reçoivent un statut :

| Statut | Sens exact |
|---|---|
| `reachable` | Chemin structurel depuis une entrée sans traverser de choix conditionnel |
| `conditional_only` | Chemin structurel uniquement via un ou plusieurs choix porteurs de `when` |
| `unreferenced` | Ni racine ni aucun lien entrant ; scène isolée |
| `disconnected` | A un lien entrant, mais son sous-graphe n'est relié à aucune entrée |

**Ce n'est pas un solveur de conditions.** Un chemin marqué
`conditional_only` n'est pas déclaré impossible : sa disponibilité dépend
des drapeaux, du journal et de l'état réel de `StoryBook` en cours de jeu.
Une scène `unreferenced` peut être un brouillon intentionnel ou un module
réutilisable non encore placé. Les rapports sont des aides d'authoring.

Le bouton **Diagnostiquer** filtre les problèmes structurels et les chemins
conditionnels à vérifier, puis permet de les ouvrir directement depuis les
résultats. Les liens `after` / `after_any` tactiques restent régis par
le graphe de triggers et ne sont pas supposés exécutés simplement parce que
le dialogue est structurellement accessible.

## Performance et validation

- Indexeur pur, recherche par texte et filtres sans mutation du modèle ;
- BFS itérative, cycle-safe, budgets explicites jusqu'à 20 000 scènes ;
- index d'affichage borné à 180 résultats, avec total séparé ;
- Canvas conservant ses plafonds de 350 occurrences, 25 scènes détachées
  et 60 événements ;
- aucun changement au Player, sauvegardes, replays et historique
  Content+GameProject.

Tests :

```bash
python -m unittest tests_standalone.test_story_graph_navigation_362 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest discover \
  -s tests_standalone -p test_story_graph_navigation_362_gui.py -v
python -m unittest tests_standalone.test_story_graph_scale_361 \
  tests_standalone.test_visual_branch_graph_36 -v
```

La CI exécute le smoke Tk/Xvfb comme étape bloquante. Le test couvre les
chaînes de **1 200 scènes**, les scènes réutilisées, recherche accentuée,
scènes isolées, sous-graphes déconnectés, choix conditionnels et un
événement hors de la palette originale. Des corrections de stabilité des
tests 3.5 sont incluses (coordonnée hors carte, normalisation JSON).
