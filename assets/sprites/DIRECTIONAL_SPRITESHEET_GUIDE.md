# Convention d'illustrations directionnelles

Ce document décrit un **format cible d'assets**, pas un renderer disponible
dans le client Tk actuel. La bibliothèque graphique est indépendante du moteur.

## Directions

- `single` : une vue unique
- `4_way` : `front,right,back,left`
- `8_way` : `front,front_right,right,back_right,back,back_left,left,front_left`

## Disposition

En mode `rows`, une ligne d'images par direction. En mode `blocks`,
chaque direction occupe un bloc de frames consécutives. Garder la même
taille de frame pour tous les sprites d'un atlas.

États graphiques prévus : `idle`, `move`, `attack`, `cast`, `hit`, `ko`.
Chaque clip pourrait définir une frame de départ, le nombre de frames,
un FPS et une boucle. Ce contrat reste à implémenter dans un futur renderer.

Aligner le point de contact des pieds entre toutes les frames pour éviter
les déplacements visuels involontaires ; le pivot graphique doit pouvoir
être corrigé sans affecter les règles tactiques.
