# 3.7.25 — Groupes d'édition hiérarchiques (Map Editor)

## Objectif

Créer une organisation persistante de carte **sans changer le gameplay** :
une case / une sélection de cases, ses arbres et décors, un ou plusieurs
acteurs, objets interactifs ou bâtiments persistants peuvent être rattachés à
un groupe nommé. Les groupes peuvent contenir des sous-groupes. Le déplacement
du parent déplace ses descendants en une opération annulable.

Cette tranche complète les déplacements existants de structures et d'entités
et réutilise structure_groups.py, map_transform.py, Document.replace et
EditingContext. Pas de nouveau renderer ni de modèle parallèle à Mission.

## Parcours dans l'éditeur

1. Dans l'outil **Sélection**, cliquer ou encadrer les cases (Maj ajoute).
2. Dans **Groupes et appartenances** (inspecteur), cliquer **Grouper cases**,
   saisir « Campement », « Maison du garde », « Jardin », etc.
   **Créer vide** permet d'organiser l'arbre avant le placement.
3. Sélectionner le groupe dans l'arbre : l'emprise combinée de ses cases et
   de ses objets est surlignée sur la carte. **Sous-groupe** crée un enfant.
4. Avec le parent sélectionné, sélectionner de nouvelles cases sur la carte
   puis **Ajouter** pour leur assigner les cases, acteurs, objets et structures
   persistantes complètes. Une case/entité ne peut appartenir directement
   qu'à un groupe ; dissocier l'ancien avant de réassigner.
5. Régler ΔX/ΔY, cliquer **Aperçu** (vert = valide / rouge = refus), puis
   **Déplacer**. Toute la hiérarchie bouge ensemble. Les commandes
   **Annuler / Rétablir** conservent l'historique transversal.
6. **Renommer** change le titre ; **Dissocier** supprime le groupe mais
   conserve toutes les ressources et rattache ses enfants à son parent.
   **Retirer** dissocie uniquement les membres sélectionnés ; **Transférer**
   déplace l'appartenance de ces membres depuis leur groupe précédent.
   **Parent…** réorganise l'arbre (ID du parent, vide = racine), en refusant
   les cycles. Raccourci Ctrl+G : créer depuis la sélection actuelle.


## Glisser-déposer directement dans l'arbre

- **Groupe → groupe** : change le parent du groupe et conserve tous ses
  descendants. La racine virtuelle sert à retirer un parent.
- **Objet / personnage / bâtiment → groupe** : transfère son appartenance,
  sans déplacement sur la carte ni changement d'ID ou de lien.
- **Case de terrain / décor → groupe** : transfère uniquement cette case.
  Les cases d'un groupe sont développées à la demande (128 à la fois).
  La ligne « Cases / décors » transfère **l'ensemble** des cases libres.
- **Élément → Racine / sans groupe** : détache l'élément du groupe sans
  supprimer son contenu. Un groupe glissé sur Racine devient racine.
- Glisser depuis le texte d'une ligne (pas depuis sa flèche d'expansion).
  Après le seuil de déplacement, la destination devient verte si valide,
  rouge si refusée (cycle, auto-déplacement, source manquante). Échap annule.
- Le survol ne modifie pas le document ; le dépôt validé utilise la commande
  typée EditorGroupTreeDropCommand et une entrée d'historique réversible.
- Le déplacement dans l'arbre est **organisationnel** : pour déplacer
  physiquement un groupe et son terrain, utiliser **Aperçu / Déplacer**
  avec ΔX/ΔY.


## Sélection multiple, déplacements et copies profondes (3.7.25C)

- Ctrl+clic ou Maj+clic sélectionnent plusieurs **lignes de groupe**
  dans le Treeview. Si un parent et un enfant sont sélectionnés, le parent
  englobe l'enfant : aucun élément n'est transformé deux fois.
- Dans la zone des groupes, choisir ΔX/ΔY puis **Aperçu / Déplacer** pour
  translater tout le lot en une seule transaction, ou **Aperçu copie /
  Dupliquer groupes** pour créer des copies indépendantes.
- Une copie comprend : sous-groupes, cases et décors, toutes les données
  des structures persistantes (y compris terrain retouché et étages),
  acteurs, objets interactifs et connecteurs d'étages internes.
- Identifiants de groupes, bâtiments, acteurs, objets et connecteurs :
  nouveaux IDs déterministes et sans collision. Les liens internes
  levier→porte et engins→porte sont redirigés vers les copies ;
  les références extérieures conservent leur cible d'origine.
- Les coordonnées des patrouilles copiées sont translatées, de même
  que les cellules de défense ; les destinations de passage demeurent
  absolues (conformément au contrat existant). Les événements globaux,
  objectifs et zones de déploiement **ne sont pas copiés**.
- Le placement refuse les collisions structurelles, les cases hors carte,
  les conflits avec les objectifs/déploiements et l'écrasement de terrain
  extérieur. Rien n'est écrit au moindre échec ; aperçu = sans mutation.
- Pour les niveaux tactiques, les plateaux et connecteurs internes sont
  reproduits avec de nouveaux IDs. Un acteur de niveau supérieur exige
  que son bâtiment et son connecteur soient inclus.
- Les copies deviennent des groupes persistants modifiables à leur tour.
  Une seconde copie obtient encore de nouveaux IDs ; l'historique et la
  sérialisation sont conservés à chaque étape.

## Contrat des données

Métadonnée **optionnelle** missions[].editor_groups (Content v1 inchangé),
absente des contenus historiques et omise pour les listes vides.

Exemple :

    "editor_groups": [
      {
        "id": "group_1", "name": "Cour du château", "parent": null,
        "cells": [[3, 4], [4, 4]], "unit_ids": ["guard_a"],
        "object_ids": ["gate_lever"], "structure_ids": ["structure_1"]
      },
      {
        "id": "group_2", "name": "Décor floral", "parent": "group_1",
        "cells": [[5, 4]], "unit_ids": [], "object_ids": [],
        "structure_ids": []
      }
    ]

- Les groupes sont **propres à la mission**, jamais interprétés par Battle.
- Les IDs des entités et structures restent ceux du modèle existant.
- Une empreinte complète de structure persistante est ajoutée comme un
  seul membre, pas répliquée case par case : son terrain sous-jacent est
  restauré par le système underlay existant.
- Les cellules libres représentent une sélection du terrain existant,
  incluant les éléments de décor (feature) présents sur ces cases.
- Un parent ne recopie pas les références de ses enfants : sa sélection
  est la fermeture transitive de l'arbre. Cycles, IDs manquants et double
  appartenance sont invalides.
- Déplacer un groupe modifie les cases et les ancrages, mais ne déplace
  pas implicitement les objectifs, triggers, zones de déploiement,
  destinations de passage ni chemins de patrouille absolus.

## Sécurité et limites

- Le déplacement n'écrase **jamais silencieusement** une case extérieure
  contenant du terrain non par défaut, ni une structure extérieure.
- Les transitions dont les états intermédiaires violeraient les règles de
  placement (acteurs, bâtiments, objets) sont refusées sans mutation.
- Les structures héritées sans identité persistante doivent d'abord être
  rééditées comme structures persistantes pour être rattachées à un groupe.
- Les cases situées dans une structure persistante sont exclues des membres
  libres : sélectionner son empreinte complète pour déplacer cette structure.
- La sélection et les prévisualisations UI ne sont jamais sérialisées.
- Chaque opération est validée par Content, historisée en une seule entrée
  et rechargée normalement.

## Tests

- python -m unittest tests_standalone.test_editor_groups_3725 -v
- python -m unittest tests_standalone.test_structure_groups_3719b tests_standalone.test_editor_architecture_3723 -v
- SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_editor_groups_3725_gui -v

Gate : créer un groupe, regrouper des décors et une structure, créer un
sous-groupe d'objets, déplacer le parent, Undo/Redo et sauvegarder/recharger
avec exactement la même hiérarchie.


## Bibliothèque de préfabs (3.7.25D)

Depuis **BIBLIOTHÈQUE DE PRÉFABS** dans le Map Editor :

1. Sélectionner un ou plusieurs groupes et sous-groupes (Ctrl/Maj).
2. **Enregistrer préfab** exporte un JSON sous le dossier prefabs/ voisin de la mission.
3. Dans une autre mission, choisir le préfab, sélectionner la case d'ancrage
   puis utiliser **Aperçu préfab** et **Placer préfab**.
4. **Importer préfab** ajoute un fichier JSON provenant d'un autre projet.
   **Actualiser** relit la bibliothèque locale.

Le format drawtemp_editor_group_prefab version 1 conserve coordonnées locales,
groupes hiérarchiques, tuiles, structures/underlays de destination, étages,
connecteurs, acteurs, objets et liens porte–levier/engin. Les identifiants sont
recréés sans collisions ; toutes les données produites sont modifiables avec
les outils habituels. Un passage possède une destination relative au préfab.

La prévisualisation est non destructive. L'insertion passe par une commande
typée et une seule transaction Undo/Redo. Les collisions (bâtiments, terrain,
limites de la carte, objectifs et déploiements) sont refusées.

**Limitations v1 :** ni événements globaux, ni objectifs, ni groupes externes,
ni zones de déploiement ne sont copiés. Export refusé si un levier ou engin
référence une porte non sélectionnée. Fichiers JSON plafonnés à 2 MiB,
version et schéma contrôlés avant import.


## Palette de préfabs visuelle (3.7.25E)

La bibliothèque existante reste compatible avec les fichiers JSON v1 :
aucune migration de format et aucun atlas supplémentaire ne sont nécessaires.

- La section **PALETTE VISUELLE · GLISSER SUR LA CARTE** contient une grille
  de miniatures produites à partir des terrains, bâtiments et entités présents
  dans chaque fichier. Les couleurs différencient eau, arbres, constructions,
  personnages et objets interactifs.
- **Rechercher** filtre par nom de modèle/fichier ; un menu affiche **Tous**,
  **Quartiers**, **Bâtiments**, **Fortifications**, **Décors**,
  **Interactifs**, **Personnages**. La catégorie est calculée à la lecture,
  sans changer les JSON existants.
- Un clic sélectionne le préfab (compatible avec l'ancien menu déroulant).
  Glisser sa miniature sur une case visible du Map Editor affiche une
  prévisualisation verte si la destination est valide, rouge si elle est
  refusée. Relâcher sur la carte instancie le modèle dans une seule transaction
  Undo/Redo.
- Le drop fonctionne sur les grilles orthogonales et isométriques, et tient
  compte de la position de défilement de la carte. Le geste ne déclenche ni
  le pinceau de terrain ni les commandes de jeu.
- Le bouton **Ouvrir la palette visuelle de préfabs** ouvre une fenêtre non
  modale plus grande, pour garder la bibliothèque accessible quand
  l'inspecteur manque de place. Elle utilise les mêmes données et commandes.
- La grille limite la première page à 80 miniatures et encourage un filtrage
  supplémentaire pour les très grandes bibliothèques. Les JSON corrompus
  restent visibles comme invalides et ne peuvent pas être déposés.

Les opérations échouées ne modifient ni la mission, ni l'historique, ni le
Player. Les prévisualisations utilisent la même commande
GroupPrefabPlaceCommand que le bouton **Placer préfab**.
