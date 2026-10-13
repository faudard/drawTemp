# 3.7.20B — Plateaux intérieurs superposés éditables (authoring visuel)

Cette étape fait passer les intérieurs d'une **simple coupe de toiture**
à une **construction de plateaux superposés personnalisables**, sans JSON
manuel et sans compromettre les combats actuels.

**Important : les nouveaux plateaux sont pour le moment VISUELS.**
Ils ne portent pas de personnages tactiques et ne participent PAS au
pathfinding, à l'occupation, à la ligne de vue ou aux actions de `Battle`.
Ne pas présenter cette tranche comme des étages *jouables*. Le runtime
multi-niveaux reste spécifié dans
[INTERIORS_MULTILEVEL_3720.md](INTERIORS_MULTILEVEL_3720.md).

## Utilisation dans le Map Editor

1. Placer une maison, une tour ou une ruine via l'outil Structure ;
   sélectionner ensuite une de ses cases au rez-de-chaussée.
2. Choisir **Étage supérieur (visuel)**, niveau `1`, et cliquer **Créer**.
   Répéter pour les niveaux 2 et 3. La vue ISO/Intérieurs est activée.
3. Choisir un niveau et l'opération **Sol**, **Mobilier**, **Trou**
   ou **Restaurer**.
4. Cliquer **Peindre étage**, puis cliquer sur le losange **surélevé**
   de la case : le sol, le mobilier ou la présence du plancher est édité.
5. **Ctrl+Z/Ctrl+Y**, enregistrer, rouvrir, contrôler la mini-carte et
   l'onglet JSON. La visualisation des niveaux ne change pas les
   unités, cases bloquées ni règles de combat.

La palette visuelle de ce lot est volontairement limitée aux matériaux
`stone/cobble/dirt/grass` et meubles `crate/lantern/pillar/stairs`.
Les vrais sprites et un vrai rendu intérieur mural/portes devront enrichir
cette palette dans une livraison artistique suivante.

## Schéma des données

Champ facultatif de la mission, absent des cartes existantes :
```json
"interior_floors": [
  {
    "structure_id": "structure_1",
    "level": 1,
    "tiles": [
      {"pos": [1, 1], "surface": "stone", "feature": "crate"},
      {"pos": [2, 1], "surface": "cobble", "feature": ""}
    ]
  }
]
```

- `structure_id` désigne **une structure persistante** Maison/Tour/Ruines.
  Les anciens tampons sans identité sont toujours chargés et affichés,
  mais doivent être recréés/convertis en structure persistante avant
  d'accueillir des plateaux.
- `pos` est une coordonnée **locale au bâtiment orienté** ; elle ne
  référence pas directement une case de combat. Un déplacement conserve
  donc l'agencement interne sous la même identité.
- `level` vaut 1 à 3. Le niveau 0 est toujours la grille tactique
  historique ; les valeurs 1–3 sont uniquement visuelles à cette étape.
- L'absence d'une case dans `tiles` représente une ouverture de plancher
  (pas de sol dessiné). Cela ne provoque jamais une chute de personnage.
- Les identifiants de structure sont uniques ; un même bâtiment n'a
  qu'un enregistrement par niveau. Les positions, surfaces, meubles et
  duplications sont validés.
- Une suppression explicite du bâtiment supprime les plateaux associés
  dans la même commande undoable. Les cartes `Content` v1 qui ne
  possèdent aucun étage gardent le même schéma sérialisé qu'avant.
- Une rotation future ou un changement d'emprise doivent rebaser les
  coordonnées locales ou refuser l'opération tant que le résultat n'est
  pas valide ; les tests n'annoncent pas encore ce parcours comme terminé.

## Contrôles de non-régression

- Terrain et unités inchangés par toutes les opérations de plateau.
- Transactions invalides rejetées avant remplacement du Document.
- Undo/Redo sur création, peinture et suppression ; sauvegarde/rechargement
  conservant le contenu du plateau.
- Sélection géométrique de la case surélevée (24/54/96), y compris sur
  les ouvertures pour pouvoir reboucher les trous.
- Identité stable des structures et références cassées interdites.
- Même rendu commun sans second moteur ISO ; aucune modification de la
  simulation headless.
- Tests du modèle dans
  `tests_standalone/test_interior_levels_3720b.py`, preuve Tk dans
  `tests_standalone/test_interior_levels_3720b_gui.py`.

## Pour rendre les étages jouables (3.7.20C)

Avant de permettre le placement de deux acteurs à la même position XY
sur des niveaux différents, il faut livrer un **système de position
tactique à étage** et ses liens de navigation (escaliers, échelles,
passages), puis aligner collision, mouvement, trajectoires d'attaques,
objectifs, conditions de triggers, caméra, Player, sauvegarde et replay.

Le format `Content v1` courant suppose exactement une case par XY.
Il faut décider et tester la compatibilité/détection de version avant
d'introduire ces règles. La tranche B ne crée pas un faux acteur
multi-niveaux à partir de `tile.height`.
