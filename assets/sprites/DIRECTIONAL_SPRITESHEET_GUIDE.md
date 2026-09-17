# Directional spritesheets — Sporebound Tactics V1.18

Les personnages 3D utilisent toujours un `Sprite3D` billboard. La **direction graphique** est choisie à partir du facing tactique de l’unité et de l’angle de caméra.

## Mode `single`

Format historique. Toutes les directions utilisent les mêmes frames. `flip_with_facing` peut retourner horizontalement les vues gauche.

## Mode `4_way`

Noms canoniques :

`front,right,back,left`

### Layout `rows`

Une ligne de texture par direction :

```text
row 0 : front  [Idle...][Move...][Attack...][Cast...][Hit...][KO...]
row 1 : right  [Idle...][Move...][Attack...][Cast...][Hit...][KO...]
row 2 : back   [Idle...][Move...][Attack...][Cast...][Hit...][KO...]
row 3 : left   [Idle...][Move...][Attack...][Cast...][Hit...][KO...]
```

Dans ce layout, `Start` est l'index de **colonne** du début du clip.

### Layout `blocks`

Les frames sont lues de gauche à droite puis à la ligne suivante. Chaque direction occupe un bloc de `Stride frames` frames consécutives :

```text
[bloc front][bloc right][bloc back][bloc left]
```

`Stride frames = 0` demande au runtime de partager automatiquement le nombre total de frames entre les directions.

## Mode `8_way`

Ordre canonique par défaut :

`front,front_right,right,back_right,back,back_left,left,front_left`

Les règles `rows` et `blocks` sont identiques au mode 4 directions.

## Clips

Chaque direction peut utiliser les six états :

- `Idle`
- `Move`
- `Attack`
- `Cast`
- `Hit`
- `KO`

Pour chaque clip : `Start`, `Frames`, `FPS`, `Loop`.

## Conseils

- Garde toutes les frames à la même taille (`frame_width × frame_height`).
- Place les pieds du personnage au même endroit dans chaque frame pour éviter les tremblements.
- Utilise le preview **Visuals** de Sporebound Studio pour tester direction + état avant de lancer le combat.
- `sprite_offset` sert à recaler le pivot visuel sans modifier la logique de grille.
