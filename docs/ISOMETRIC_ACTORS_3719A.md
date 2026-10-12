# 3.7.19A — Personnages chibi dans le Studio et le Player isométriques

## Pourquoi

Avant ce jalon, `render_isometric` affichait chaque combattant comme
un **cercle bleu ou rouge**, même lorsque le projet contenait des assets
validés dans le Player 2D. Le village Valcroix de la PR #84 révélait ce
décalage artistique. L'objectif est un premier véritable parcours
d'affichage de personnages **sans toucher aux règles tactiques**.

## Livrables

- `content/art/iso/chibi_actors.png` : **PNG indexé transparent original,
  512 × 192**, 24 frames de 64 × 64. Trois silhouettes chibi :
  héroïne en bleu/or, garde en métal/rouge et archer vert/brun.
  Quatre orientations `south, north, east, west`, deux poses `idle, move`
  par archétype. Pixel-art original volontairement limité en palette,
  **prototype à valider**, pas animation de combat définitive.
- `sporebound/iso_actor_atlas.py` : chargement Tk différé, cache de
  recadrages par style/direction/pose/zoom, aucun Pillow requis à
  l'exécution, repli sûr sur vecteurs en cas de PNG absent/corrompu.
  Héroïne explicitement nommée ou identifiée `jeanne` :
  l'atlas existant et approuvé
  `content/art/jeanne/jeanne_atlas.png` est utilisé **en priorité**.
  Aucun duplicata de cet art dans le nouveau pack.
- `sporebound/iso_map.py` : sprite isométrique au pied de la case
  calculé avec le même `visual_center` qu'avant. Sélection, textes,
  barres PV, picking et groupe Canvas `iso_actor_unit_N` conservés.
  Une image manquante restitue l'ancien cercle, jamais une unité invisible.
- `sporebound/iso_battle_view.py` : les changements cosmétiques de direction
  et de pose remplacent **seulement la référence image Canvas** lors d'une
  frame retenue ; pas de reconstruction du décor ni nouveau tick combat.
- `sporebound/editor.py` : le **même atlas** dans la vue de création.
- Tests Python sans GUI : 24 frames/CRC/alpha/opacité, 4 directions,
  reconnaissance des rôles, maintien du moteur headless, fichier absent.
- Test Tk/Xvfb : 3 personnages, zoom 24/54/96, déplacement/rotation,
  item Canvas réutilisé, direction `idle → move`, repli vectoriel,
  captures archivées dans l'artefact CI `iso-chibi-actors-3719a`.

## Contrat artistique et technique

La scène utilise une classification purement visuelle, sans persistance :

| Comportement | Affichage |
| --- | --- |
| `id` ou nom `Jeanne` | Atlas de Jeanne 256×512 déjà validé |
| `team=player` | Héroïne bleue |
| `team=enemy` | Garde rouge/acier |
| `team=neutral` | Archer vert |
| `weapon=bow/crossbow/longbow` ou archétype archer | Archer vert |
| Atlas inconnu, PNG absent, Tk indisponible | Cercle d'équipe historique |

La direction vient en priorité de `ActorPose.direction` (animation),
sinon de `Unit.facing`. Le `move` choisit la seconde image ;
cette PR ne prétend pas fournir l'ensemble des attaques, touches,
morts et 8 directions d'un atlas final. Le tri devant/derrière les
architectures continue de se baser sur les pieds (`iso_depth`).

Le registre des assets de campagne, `Content`, les formats JSON
de bataille et de replay, les classes, dommages, l'IA, les déplacements
et la sauvegarde ne sont pas modifiés. La présentation n'altère
jamais le `Battle.digest()`.

## Tests

```sh
python -m unittest discover -s tests_standalone \
    -p test_iso_actor_atlas_3719a.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover \
    -s tests_standalone -p test_iso_actor_atlas_3719a_gui.py -v
python -m unittest discover -s tests_standalone -v
```

Le workflow `Standalone gameplay` exécute les tests headless sur
Linux/macOS/Windows × Python 3.10/3.12/3.14, et les tests graphiques
sur Linux/Tk/Xvfb à 24, 54, 96 pixels par case. Les captures produites
doivent être examinées avant de certifier la cohérence visuelle.

## Gate / suites

- [ ] CI complète verte sur le SHA de la PR.
- [ ] Captures inspectées et jugées lisibles aux trois zooms.
- [ ] Studio et Player natifs vérifiés sur Windows/macOS.
- [ ] Absence de modifications des digests d'une bataille et des replays.
- [ ] Palette des trois prototypes, cadrage, yeux, armures et silhouettes
  validée avec les portraits/animations définitifs.
- [ ] PR #84 intégrée/juxtaposée dans une scène Valcroix avec des unités.

**P1** : véritables frames 4/8 directions de marche, attaque,
incantation, hit, defeat, accessoires par classe, animations
plus fluides, éclairement et liaison complète au manifeste portable.
Ne pas revendiquer que ces prototypes remplacent les assets finaux.
