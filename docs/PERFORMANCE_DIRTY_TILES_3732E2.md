# 3.7.32E2 — Dirty Tiles et occlusion statique

## Décision d'architecture

La **source unique de rendu** reste `iso_map.render_isometric`, et la
gestion des priorités visuelles reste `iso_depth.depth_order`. Pas de
second painter, aucune modification du moteur tactique ou du JSON.

Quand une mission validée ne change que sur un petit nombre de cases
de terrain (surface, obstacles, couverture, hazard, décor), le pipeline :

1. Compare l'ancienne et la nouvelle mission avec
   `dataclasses.replace(before, board=after.board) == after`.
   Les positions/états d'acteurs, objets, toitures, structures et étages
   doivent être strictement inchangés.
2. Vérifie, via `architecture_instances`, que la liste, l'identité,
   l'emprise et l'ordre des bâtiments sont inchangés. Les structures
   héritées peuvent en effet apparaître/disparaître après une modification
   de terrain. Une variation entraîne le rendu intégral.
3. Étend le dirty set aux voisins 8-connectés, en respectant les limites
   (16 cellules changées / 144 cellules affectées au maximum).
4. Efface seulement les primitives Canvas marquées
   `iso_tile_x_y`, recalcule ces cases avec le renderer canonique
   et les replace selon leur profondeur.
5. Reconstruit la **surcouche architecturale uniquement** (intérieurs,
   façades, toitures, vitrages) avec le renderer canonique, puis rétablit
   le `depth_order` pour les acteurs, objets, arbres et architectures.
   La totalité des 65² ou 128² cases n'est pas redessinée.
6. Remet les contours de sélection au premier plan et mémorise la
   nouvelle génération validée.

La détection des cases à dessiner n'effectue plus de balayage des
16 384 cellules à chaque mutation : seules les cases affectées sont
triées par leur profondeur. La remise en ordre finale peut néanmoins
inspecter l'ordre global déjà calculé.

## Fallbacks obligatoires

Le rendu complet reste exigé si :

- la géométrie ou la hauteur du terrain change ;
- le zoom, les couches ou les atlas changent ;
- une structure héritée n'a plus la même emprise, un acteur se déplace,
  un objet ou un étage tactique change ;
- une sélection traverse une frontière de toit découpé ;
- le nombre de cellules affectées dépasse le budget ;
- un élément Canvas externe change sans passer par le propriétaire.

Les acteurs multi-cases ne sont pas optimisés localement dans cette
première extension. Pas de promesse de patch local en situation de
changement de scène ou d'animation.

## Tests de parité

```sh
python3 -m unittest -v \
  tests_standalone.test_dirty_tiles_3732e \
  tests_standalone.test_dirty_tiles_3732e2

SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest -v \
  tests_standalone.test_dirty_tiles_3732e2_gui \
  tests_standalone.test_dirty_tiles_3732e_gui \
  tests_standalone.test_editor_render_cache_3718d_gui
```

Les tests Canvas comparent types, coordonnées, ordre global, styles,
options et tags, ainsi que la scrollregion. Cas : acteur adjacent,
arbre/arc, toit ouvert et fermé, sélection qui traverse un bâtiment,
undo/redo, relief, zoom. Tests sur 65²/128² et génération 32²/64²/128².

## Performance mesurée

```sh
xvfb-run -a python3 scripts/benchmark_dirty_occlusion_3732e2.py \
  --sizes 65,128 --zooms 24,54,96 --samples 100 \
  --output dirty-occlusion-reference.json
```

Le benchmark compare le rendu complet et local sur **la même maison
avec un arbre**. Il mesure `Content` projeté + `renderer.draw` +
mise à jour Tk idle, après une mutation identique du terrain.
Le workflow CI exécute `--quick`, archive les JSON des scènes simples
et architecturales et sert seulement de smoke fonctionnel.

Les chiffres p95/p99 sur trois échantillons sont exploratoires, sans
certification des délais de réaction sur le matériel des joueurs.

## Suite

3.7.32E3 : scénarios de mobilité réelle, silhouettes animées,
modifications de la structure, sauvegarde et rafraîchissement
incrémental des emprises d'objets et bâtiments. Ce lot requiert
une matrice de dépendances de profondeur spatiale.
