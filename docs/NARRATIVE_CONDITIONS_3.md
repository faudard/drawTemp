# 2.5.2 — Éditeur visuel des conditions narratives

Le Studio dispose déjà d'un éditeur de scènes, d'un graphe narratif avec
**occurrences multiples de scènes partagées**, et de règles de choix stockées
dans `GameProject.story`. Cette PR rend les conditions **ET / OU / NON**
éditables graphiquement, sans écrire de JSON, tout en réutilisant les règles
`StoryBook` exécutées par le jeu.

## Éditer une condition dans le Studio

1. Ouvrir l'onglet **Conditions & variables**.
2. Choisir une **Scène** et le **Choix** à restreindre.
3. Dans la palette, sélectionner un prédicat :
   - `flag =` : égalité typée (texte, entier ou booléen).
   - `flag ≥` / `flag ≤` : comparaison numérique stricte.
   - `mission terminée` : mission déjà gagnée.
   - `or ≥` : montant d'or minimal.
4. Sélectionner un nœud dans l'arbre, puis utiliser :
   - **Remplacer / init.** : remplacer le nœud par le prédicat choisi,
     ou initialiser une condition si le choix n'en a pas.
   - **ET / OU** : envelopper le nœud dans un nouveau groupe booléen.
   - **NON** : inverser un prédicat ou un groupe entier.
   - **+ enfant** : ajouter un prédicat au groupe ET ou OU sélectionné.
   - **Supprimer** : supprimer un enfant d'un groupe non vide, ou
     rendre un choix inconditionnel en supprimant la racine.
5. Pour ajouter un nouveau branchement, renseigner **Identifiant** et
   **Libellé**, puis **Créer un choix + condition**.
6. **Voir dans le graphe** ouvre la scène canonique dans l'arbre narratif ;
   inversement, **Conditions** sur un choix du graphe mène à son éditeur.

Les modifications sont validées et enregistrées **atomiquement** via
`GameProject.from_dict`. Undo/Redo du scénario fonctionne aussi sur la
structure ET/OU/NON. Aucune occurrence secondaire d'une scène partagée
n'est dupliquée dans le projet.

**Règle de secours :** chaque scène doit toujours posséder au moins un
choix inconditionnel. La validation empêche de conditionner le dernier
choix libre, et refuse les cycles narratifs, les références inconnues,
les comparaisons invalides et les arbres trop profonds.

## Prévisualisation des variables sans modifier la sauvegarde

Dans l'onglet Conditions & variables, définir temporairement :

- **Variables** : `trust=2; guard_oath=true; region=south`.
- **Or** : nombre entier compris entre 0 et 1 000 000.
- **Missions terminées** : `garden; hold`.

Cliquer **Tester la condition** indique *VISIBLE* ou *MASQUÉ* à partir
du même évaluateur `sporebound.narrative.matches` que le runtime.
La simulation ne touche ni les slots, ni la progression, ni les flags
actifs, et ne change pas le `StoryBook.digest`.

## Architecture

- `sporebound/story_conditions.py` : opérations pures de lecture et
  réécriture d'expressions, prédicats typés et simulation isolée.
- `sporebound/studio_story_conditions.py` : Treeview Tk + formulaires
  + commandes interactives. Les chemins de nœuds ne sont que des
  positions temporaires dans une condition, jamais des IDs de scènes.
- `sporebound/studio_story.py` et `studio_story_graph.py` :
  navigation entre les onglets existants.
- Aucun changement au moteur de combat, à la sauvegarde, à l'API
  de `StoryBook` ni au schéma JSON.

## Validation

```sh
python -m unittest discover -s tests_standalone -p 'test_story_conditions.py' -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_story_conditions_gui.py -v
```

La matrice CI existante teste Windows/macOS/Linux et Python 3.10/3.12/3.14 ;
le job Xvfb vérifie la manipulation directe dans le Studio.

## Limites et prochaine évolution

Cette étape traite le **graphe narratif et les conditions de choix**. Le
système existant de déclencheurs tactiques (`Mission.triggers`) n'est
pas modifié : leur future visualisation sous forme de graphe
« condition → actions → conséquence » appartient au complément 2.5.2.
Une interface de variables projet typées avec valeur initiale et
catalogue global devra aussi être étudiée avant d'étendre le schéma
de sauvegarde.
