# Map Builder 4.0 — 3.7.32E : génération assistée de quartiers

## Principe

La génération assistée **ne crée pas un second format de cartes**. Elle produit
exactement les mêmes objets `drawtemp_editor_group_prefab` v1 que la
bibliothèque de groupes 3.7.25D, réutilise
`GroupPrefabPlaceCommand` / `place_group_prefab`, et n'introduit aucune
donnée spécifique au générateur dans Content, GameProject ou le Player.

Une proposition est un **plan inspectable**, pas un ordre de modification :
l'auteur doit d'abord prévisualiser le résultat exact, puis confirmer.

## Parcours d'auteur dans le Studio

Dans la zone **GÉNÉRATION ASSISTÉE · QUARTIER** :

1. Choisir **Village**, **Marché** ou **Fortifié** ; taille 16×14, 20×16
   ou 24×18 ; seed entière comprise entre 0 et 999998.
2. Cliquer **Générer 3 variantes**. Les trois variantes correspondent
   explicitement aux seeds N, N+1 et N+2. Elles diffèrent par la
   distribution des maisons/tours et des jardins.
3. Choisir la variante. La **miniature de la bibliothèque existante**
   présente ses routes, maisons/tours/remparts, jardins et coffre.
4. Avec l'outil **Sélection**, cliquer la case d'ancrage sur la carte,
   puis **Aperçu des différences**. Un cadre **vert** indique une insertion
   valide ; **rouge** signale collision, bord de carte, verrou de calque
   ou contrainte métier. Le panneau donne les comptes de cellules
   modifiées, bâtiments, objets et groupes ajoutés.
5. Cliquer **Confirmer placement**. L'opération est autorisée uniquement
   si la mission, l'ancre, la variante et la révision du document sont
   identiques au dernier aperçu validé. Une seule transaction est
   créée dans l'historique. Undo/Redo reste opérationnel.
6. Cliquer **Enregistrer comme préfab** pour ranger la variante choisie
   dans `prefabs/`, puis la réutiliser dans une autre mission, la
   faire pivoter et la placer à la souris via le lot D.

## Contenu et contrats

`sporebound/quarter_generator.py` est headless et déterministe.
Aucune graine globale, aucun état caché ni dépendance Tk.

Les plans comportent :
- Quatre maisons/tours dans les quadrants (variante déterministe par seed),
  des chemins reliés et un espace central.
- Pour **Marché** : une rue centrale plus large en pavés.
- Pour **Fortifié** : des segments de remparts supplémentaires.
- Jardins et décors `tree`, `bush`, `boulder`.
- Un coffre interactif standard `kind=chest` associé à son groupe.
- Groupes hiérarchiques : racine du quartier, routes, bâtiments, jardins
  et coffre. Tous restent rééditables via l'arbre et les palettes Studio.

Les bâtiments sont écrits à partir des `structure_template` existants.
La validation de placement utilise `place_group_prefab` et Content ;
elle refuse d'écraser des structures, du terrain extérieur non trivial,
des unités/objets ou des objectifs et des zones de déploiement.

**La prévisualisation ne modifie aucune ressource.** Le rapport de
différences est construit en comparant les tuiles effectives de Content
avant/après placement simulé, et non en comptant seulement les cellules
du modèle. Le verrouillage de calques 3.7.32C reste actif.

La génération n'ajoute pas de nouveaux étages ou d'événements narratifs
automatiques. Ceux-ci sont conçus manuellement dans les outils existants ;
les préfabs contenant déjà des plateaux/escaliers restent pris en charge
par le moteur du lot D.

## Tests

```bash
python -m unittest tests_standalone.test_map_builder4_3732e -v
python -m unittest tests_standalone.test_editor_group_prefabs_3725 -v
python -m unittest tests_standalone.test_map_builder4_3732d -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest tests_standalone.test_map_builder4_3732e_gui -v
python -m unittest discover -s tests_standalone -v
```

Gates :
- Même paramètres ⇒ mêmes trois propositions et même placement ; des
  seeds différentes ⇒ plans distincts.
- Prévisualisation avant/après exacte, sans mutation de Content ni
  d'historique, y compris si emplacement invalide.
- Confirmation nécessaire avant toute écriture ; aucune acceptation
  implicite ni effet de bord sur le Player.
- Sauvegarde d'une variante en préfab portable, deux insertions dans
  une mission, IDs indépendants et un seul Undo par insertion.
- Validation de toutes les tailles/styles ; refus des entrées mal formées.
- Édition manuelle du résultat dans les outils historiques.

## Clôture de Map Builder 4.0

Le parcours intégral A–E (pinceaux → architecture → niveaux/calques →
préfabs → suggestions) devra ensuite être éprouvé sur une place fortifiée
comportant maisons, rivière, pont, tour à deux étages et objets
interactifs dans le Player. La génération assistée n'est pas une excuse
pour contourner ce gate de gameplay.
