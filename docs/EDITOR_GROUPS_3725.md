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
