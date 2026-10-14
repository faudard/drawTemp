# 3.7.32D — Map Builder 4.0 : préfabs réutilisables et pose visuelle

## Objectif

Consolider **la bibliothèque 3.7.25D existante**, pas créer un deuxième
format de données. Un modèle de quartier/plaine fortifiée peut mêler maisons,
tours, terrain routier, décors, groupes hiérarchiques, acteurs, objets
interactifs et connexions entre étages, puis être instancié sur une autre
carte comme des ressources ordinaires du Studio.

## Parcours auteur

1. Encadrer les bâtiments/cases/objets dans le Map Editor ; cliquer
   **Grouper cases**. Un ensemble peut contenir plusieurs sous-groupes.
2. Dans **BIBLIOTHÈQUE DE PRÉFABS**, choisir le groupe et cliquer
   **Enregistrer préfab**. Le modèle JSON versionné est publié dans le
   répertoire `prefabs/` voisin du contenu du jeu. Les deux commandes
   d'import et de rafraîchissement du catalogue sont conservées.
3. Le catalogue affiche une **miniature de plan** représentant les sols,
   façades/structures, unités et objets interactifs. Changer la rotation
   `0° / 90° / 180° / 270°` redessine la miniature, sans modifier le fichier.
4. Cliquer **Aperçu préfab** pour vérifier la case sélectionnée, ou
   **Poser à la souris** pour activer le survol sur la carte.
   Vert : pose validée. Rouge : collision, objectif, hors-carte, ou
   autre contrainte Content. Le survol ne crée aucun historique.
5. Un clic place le modèle à la position annoncée. L'opération s'effectue
   toujours via `GroupPrefabPlaceCommand`, `EditingContext` et
   `Document.replace`. Elle est réversible en un seul Undo/Redo.
6. Les instances conservent leurs **groupes éditables** et leurs nouvelles
   identités de structures/acteurs/objets ; les liens internes levier → porte,
   les escaliers et les plateaux sont conservés.

## Rotation métier, hors Tk

`sporebound/group_prefab_transform.py` introduit
`rotate_group_prefab(prefab, quarter_turns)` (0 à 3, dans le sens horaire).

Pour une empreinte de taille `W×H`, un point devient
`(H-1-y, x)` et la nouvelle taille est `H×W`. La transformation
inclut les cellules terrain/route/décor, les cellules de groupes et
sous-groupes, les ancres des bâtiments et leur `turns`, les plateaux
intérieurs **locaux au bâtiment**, les connexions N0↔N1, les objets,
leurs zones de défense et destinations de passage, les patrouilles,
l'orientation des acteurs ainsi que les footprints multi-cases.

Les bâtiments créés continuent de passer par `place_structure`. Les
enregistrements de personnalisation `appearance` (s'ils existent) sont
transportés par la structure habituelle ; les fenêtres tournent avec le
bâtiment. Les originaux ne sont pas modifiés. Le format de fichier reste
`drawtemp_editor_group_prefab` version 1.

La copie d'un préfab conserve les limitations de la bibliothèque existante :
pas de copie implicite des triggers/campagnes, objectifs, zones de
déploiement ni références à des portes exclues du préfab.

## Vérification

```bash
python -m unittest tests_standalone.test_map_builder4_3732d -v
python -m unittest tests_standalone.test_editor_group_prefabs_3725 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest tests_standalone.test_map_builder4_3732d_gui -v
python -m unittest discover -s tests_standalone -v
```

Gates : enregistrer un quartier (au minimum maison/tour, route, décor et
objet), le tourner de 90°, en visualiser l'emprise à l'endroit ciblé, le
placer deux fois dans une autre mission, valider les liens entre entités,
les étages, la sérialisation et Undo/Redo. Démontrer qu'un emplacement
invalide ne change ni Content ni l'historique, et que le Player charge
la mission obtenue sans modèle de prefab supplémentaire.

## Suite

Le lot 3.7.32E utilisera ces **mêmes commandes** pour proposer des variantes
assistées, chaque génération ayant une prévisualisation explicite et une
modification validée ou annulée. L'éditeur et le moteur tactique ne doivent
jamais dépendre d'un nouveau runtime de préfab.
