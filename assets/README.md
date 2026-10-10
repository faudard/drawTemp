# Bibliothèque graphique Sporebound

Ce dossier conserve les visuels **réutilisables sans Godot** pour le futur
client graphique : portraits, illustrations, sprites, icônes et kits PNG/JPG.

- `portraits/` : portraits de personnages et visuels de dialogue
- `sprites/` : planches et conventions de sprites directionnels
- `hero_parts/` : éléments modulaires de personnage par direction
- `hero_kits/` : kits graphiques et manifestes `kit.json`
- `status_icons/` et `vfx/` : icônes, références et effets graphiques
- `catalog.json` : ancien inventaire d'illustrations, converti en chemins
  relatifs ; ce catalogue sert de **référence**, non de source runtime active

Les anciens fichiers `.import`, ressources `.tres`, matériaux et shaders Godot
ont été retirés. Le moteur et l'éditeur Python actuels ne chargent pas
automatiquement ces images. Leur intégration exige un contrat graphique
et des tests dédiés ; ne pas confondre catalogue d'art et contenu jouable.
