# Sporebound — Direction visuelle Comic sélectif

Cette branche fixe la direction visuelle du niveau 1 autour d'un langage **BD / manga noir et blanc avec couleur sélective**.

## Règles visuelles

- Décor et volumes : encre, niveaux de gris, contraste marqué, texture/grain léger.
- Rouge : Momo, ennemis et danger.
- Vert : déplacement, alliés, cases atteignables.
- Violet : magie, hazards et cases spéciales.
- Bleu/cyan : sélection, MP, information tactique.
- Or : couronne, objectif et information prioritaire.
- HUD : panneaux noirs, bordures ivoire épaisses, coins presque carrés.
- Initiative : portraits lisibles, couleur par camp, surbrillance or pour l'unité active.
- Dialogue : grands portraits/cut-ins, cadre BD, nom du locuteur coloré, texte très lisible.
- Le terrain doit rester lisible avant d'être décoratif : silhouettes nettes, cases compréhensibles, objectifs visibles.

## Niveau 1

La Couronne Beatbox reste le point focal de la carte. La post-production comic est appliquée au monde 3D avant le HUD, de sorte que l'interface conserve ses couleurs tactiques nettes.

Le niveau 1 sert de référence pour les futurs niveaux : même grammaire de couleur, même HUD, mêmes dialogues et mêmes priorités de lisibilité.


## Architecture visuelle Godot

La composition visuelle doit être **éditable dans l'éditeur Godot** :

- géométrie, placement, lumières, panneaux, cut-ins et matériaux dans des `.tscn` ;
- couleurs et rendu dans des `StandardMaterial3D`, `ShaderMaterial`, `Environment` et ressources de thème ;
- scènes réutilisables pour les éléments répétés (arbres, panneaux, cut-ins) ;
- scripts limités au comportement : animation, binding des données, réactions aux états de jeu ;
- éviter de générer en GDScript des arbres complets de `Control`, `MeshInstance3D` ou de décor statique quand Godot peut les sérialiser dans une scène ;
- aucun `Label3D.fixed_size` décoratif dans la carte : les indications du monde doivent conserver une taille physique cohérente avec la caméra ;
- les décors de fond ne doivent pas être des plans fixes dans le monde si la caméra peut tourner. Utiliser `WorldEnvironment` ou des éléments périphériques réellement 3D.
