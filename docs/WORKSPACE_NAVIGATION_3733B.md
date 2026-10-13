# 3.7.33B — Navigation synchronisée Map ↔ Workspace

## Objectif

Rendre la **sélection**, la navigation et l'inspection cohérentes entre la
carte tactique, l'explorateur du projet, le navigateur de groupes et le panneau
Inspecteur existants. Aucune nouvelle fenêtre, table de ressources persistée
ou modification de `Content` / `GameProject`.

## Parcours

1. **Depuis la carte** : en mode Sélection, cliquer un acteur, un objet ou
   une case vide. Le Workspace sélectionne la ressource dont l'identifiant
   est stable ; le panneau Inspecteur affiche sa projection courante.
   L'arbre des groupes sélectionné fait de même pour les groupes persistants.
2. **Depuis l'arbre** : sélectionner un acteur, objet ou groupe : sa position
   réelle est révélée sur la carte, sans imposer un changement d'onglet.
   « Ouvrir dans le Studio » conserve le comportement de navigation explicite.
3. **Fil d'Ariane** : « Projet / Mission / Case / Ressource », mis à jour
   avec les données live et sans enregistrer de coordonnées figées.
4. **Précédent / Suivant** : historique distinct d'Undo/Redo, 64 ressources
   au maximum, déduplication et abandon de l'historique futur après nouvelle
   navigation. Un acteur déplacé reste identifié par son ID et ouvre sa
   nouvelle case. Une ressource supprimée est ignorée pendant la traversée.
5. **Nouveau projet** : l'historique local est réinitialisé, pour ne pas
   suivre par erreur les identifiants réutilisés dans un autre document.

## Architecture

- `workspace_navigation.py` : fonctions de résolution headless, un
  `NavigationHistory` borné, aucun import Tk ni mutation de données.
- `studio_workspace.py` : un seul arbre `ProjectWorkspaceIndex`, un seul
  inspecteur, synchronisation explicite des sélections, actions d'historique.
- `editor.py` : réutilise `focus_workspace_map` pour localiser les
  références, avec mode prévisualisation `show_map=False` pour préserver
  l'onglet actif. Les callbacks de sélection utilisent les outils existants.
- Les entrées `map_tile:<mission>/<x>,<y>` sont **éphémères** dans le
  navigateur et ne créent aucun nouveau nœud de gameplay.

## Gate de validation

- Sélectionner un acteur sur la carte : arbre et inspecteur affichent le bon ID.
- Sélectionner un objet dans l'arbre : bonne case mise en évidence, onglet
  Workspace conservé tant que l'auteur n'a pas demandé « Ouvrir ».
- Naviguer acteur → groupe → objet → précédent → suivant, avec ressources
  déplacées et suppressions intermédiaires.
- Une carte vide et les groupes sans cases restent navigables.
- Recharger un projet, puis tester de nouveau l'historique : aucune identité
  du projet précédent n'est réutilisée.
- Le comportement des commandes d'édition, d'Undo/Redo et du gameplay reste
  inchangé.

## Tests

```sh
python -m unittest tests_standalone.test_workspace_navigation_3733b -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_workspace_navigation_3733b_gui -v
```

Cette PR est indépendante de **3.7.33A** (édition directe des propriétés) et
n'essaie pas de corriger les erreurs de préfabriqués de groupes que sa CI
remontait lors de l'examen de #136.
