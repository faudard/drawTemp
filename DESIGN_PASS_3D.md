# Mission 1 — 3D Design Pass

Cette passe transforme la mission 1 jouable en petit diorama tactique lisible, sans modifier ses règles de combat.

## Direction visuelle

- Sol forestier sombre, mousse et volumes low-poly pour garder une silhouette claire en vue tactique.
- Diorama périphérique généré au runtime : terre, rebord moussu, champignons, rochers et cristaux hors de la grille jouable.
- Éclairage chaud principal + fill light froid, ambiance brumeuse discrète.
- Cases spéciales immédiatement identifiables : spores violettes, extraction verte, vinyles cyan/noir et Couronne dorée.
- Interactables redessinés : porte en bois/rune, interrupteur-champignon lumineux, coffre stylisé.
- HUD et boutons recolorés dans une palette forêt / charbon / or.

## Personnages

Le runtime 3D accepte maintenant un `portrait_path` transparent comme visuel billboard quand aucune spritesheet n'est définie. Cela permet d'utiliser immédiatement les illustrations de la bibliothèque Sporebound en attendant les sprites directionnels définitifs.

Associations provisoires :

- Pipo : `starter_scout.png`
- Luma : `blue_oracle.png`
- Grincheux : `morel_guard.png`
- Baveux : `aqua_spirit.png`
- Comptable : `rifle_ranger.png`
- DJ Morille : `spore_gunslinger.png`
- Momo conserve son asset Hero Creator existant.

Ces associations sont uniquement des références de présentation. Pour changer un personnage, modifier `portrait_path` dans `data/visuals/units/<id>.tres`.

## Lisibilité tactique

Les éléments décoratifs du diorama restent hors de la grille. Les volumes posés sur les cases restent volontairement bas afin de ne pas masquer les unités, le curseur, les couvertures ou les objectifs. Les objets de gameplay continuent d'utiliser les mêmes cellules et les mêmes données de mission.

## Fichiers principaux

- `scripts/presentation/spore_mission_dressing_3d.gd`
- `scripts/maps/spore_tactical_tile_3d.gd`
- `scripts/maps/spore_map_interactable_3d.gd`
- `scripts/maps/spore_unit_actor_3d.gd`
- `scripts/prototypes/spore_battle_board_3d.gd`
- `assets/portraits/library/`
- `data/visuals/units/*.tres`

## Passe suivante — UI tactique

Une seconde passe visuelle a été ajoutée sur l’interface de combat pour rendre la mission plus lisible sans toucher aux règles :

- timeline compacte avec portraits des prochaines unités ;
- panneau objectif séparé du texte d’aide ;
- inspecteur de case au survol (hauteur, terrain, rôle, occupant) ;
- résumé rapide des interactables de mission (porte, switch, coffre).

## Passe suivante — balises & silhouettes

Nouvelle amélioration de lisibilité en scène :

- balises 3D flottantes sur les cases d’extraction et les vinyles ;
- couronne runtime animée pour ressortir davantage ;
- aura d’équipe sous les unités pour distinguer immédiatement alliés et ennemis ;
- renforcement visuel de l’unité active / sélectionnée sans toucher au gameplay.
