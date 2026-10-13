# Entity & Event Studio 3.6 — Visual Branch Graph

## Objectif

Relier visuellement des scènes, réponses et événements tactiques dans le
**Story Graph existant** (« Arbre narratif »), par glisser-déposer de ports
de connexion. Le Graphe des événements, le StoryBook, `Mission.triggers`,
`during_tactical_event`, `StudioHistory` et `GameSession` restent les
seules sources de vérité.

3.6 s'appuie sur 3.4/3.5 ; fusionner leurs commits avant cette PR.

## Utilisation dans « Arbre narratif »

- Sélectionner une racine, notamment **Tactique · mission/événement** pour
  les scènes liées à des triggers tactiques.
- À droite, choisir la **mission**. Les autres scènes et ses événements
  apparaissent comme cartes dans les deux colonnes du **même Canvas**.
- Cliquer une scène, puis choisir sa **réponse** dans l'inspecteur.
  Glisser le **port turquoise** du bord droit vers une autre carte :
  - **Scène/choix → scène** : écrit `choice.next_scene`.
  - **Scène/choix → événement** : écrit `trigger.after_choice`.
  - **Événement → scène** : écrit `during_tactical_event`.
  - **Événement → événement** : écrit une dépendance `after` (**ET**),
    ou `after_any` (**OU**) suivant le sélecteur de l'inspecteur.
- **Maj + glisser puis déposer sur le vide** : crée une nouvelle scène
  liée au choix de départ, ou un nouvel événement `tick=0`/message
  relié à l'événement source. Les identifiants sont générés et validés ;
  la mise en page reste calculée depuis les données d'authoring.
- Relâcher hors cible sans Maj annule la liaison sans modifier les fichiers.
- Double-cliquer une carte d'événement pour ouvrir le Graphe des événements
  et son inspecteur spécialisé. Double-cliquer une scène conserve le
  parcours existant vers l'éditeur narratif.
- Les autres scènes sont affichées une fois ; les scènes déjà visibles
  gardent leurs **occurrences multiples** habituelles, mais leurs liens
  modifient une unique définition canonique.
- Palettes bornées à **25 scènes détachées** et **60 événements** par
  mission ; indication explicite de la troncature.

## Architecture

`visual_branch_graph.connect_visual_branch` est le point d'entrée
**sans Tk** pour les quatre combinaisons de liaisons. Il prépare une
copie et renvoie un couple complètement validé
`(Content.to_dict(), GameProject)`. Toutes les transitions passent par :

- `story_authoring.link_choice` et
  `story_authoring.set_tactical_scene`
- `event_graph.bind_choice`, `event_graph.link_event` et
  `event_graph.link_alternative`
- `Content.from_dict(..., rules=authored_rules_for_document(...))`
- `GameProject.from_dict(..., content)`

Une référence inconnue, un choix hors scène, un événement d'une autre
mission, un cycle narratif ou un cycle de dépendances ne modifie **rien**.
Les liaisons directes vers un même nœud sont rejetées.

`studio_visual_branch_links.VisualBranchInteractions` ajoute les ports
au `StoryGraphEditor` sans remplacer les inspecteurs et sans stocker
une deuxième structure de graphe. Le trait de prévisualisation n'est
que temporaire dans le Canvas ; le glisser-déposer utilise
`Canvas.canvasx/canvasy` pour rester compatible zoom/défilement.

L'action UI est publiée sous un seul `StudioPanels._run`, après
validation des **deux documents**. Elle intègre le même
`StudioHistory` transversal et sa sauvegarde transactionnelle
`Enregistrer tout`.

## Scénario d'acceptation

Créer une scène « À la porte » avec **trois choix** (assaut, négociation,
attente) ; lier chacun à une scène, et les deux premiers à des événements
tactiques exclusifs via leurs gardes. Créer une réunion OR depuis les
branches et lier l'événement commun à un dernier dialogue. Jouer les deux
parcours dans le Player, puis sauvegarder/recharger : le journal doit
rejouer les actions exactes sans fusionner les choix incompatibles.

Tests :

```bash
python -m unittest tests_standalone.test_visual_branch_graph_36 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest discover \
  -s tests_standalone -p test_visual_branch_graph_36_gui.py -v
python -m unittest tests_standalone.test_event_choice_branches_34 \
  tests_standalone.test_event_branch_builder_35 -v
```

**Gate :** le test Tk est requis dans la CI de l'éditeur.
Les aperçus de Studio restent isolés et non authentifiés ; la garantie
de replay provient des vrais `GameSession.recording()` et
`GameSession.from_recording()`.
