# 3.7.32E — Dirty Tiles P0 · rendu incrémental isométrique

## Contrat

Le renderer canonique reste `render_isometric` : il n'existe ni duplicata
de la simulation, ni second dessin isométrique. Les primitives d'une cellule
portent le tag stable `iso_tile_x_y`. Sur une mission validée dont seul le
terrain simple a changé, le renderer efface/rejoue ces primitives pour les
cellules invalidées, puis les replace **dans leur ordre de profondeur**.

## Portée du premier fast path

- Une édition de surface/collision/couverture/hazard ou coût sur au plus
  16 cellules devient une invalidation locale de rayon Chebyshev 1
  (au plus 144 cellules), couvrant le bord des rivières, les ponts,
  les transitions et les faces de blocs.
- Le contexte de rendu est issu d'une génération Content validée. Le diff
  compare les anciennes et nouvelles valeurs ; aucune identité de
  dictionnaire mutable n'est traitée comme une version.
- L'état du renderer, les couches et atlases, le zoom et les dimensions
  doivent être identiques ; toute intervention externe sur les items Canvas
  force le rendu complet. Les positions de sélection peuvent changer,
  avec recalcul des contours.
- Les unités ordinaires peuvent rester dans la scène si leurs sprites sont
  éloignés de la zone impactée. Toute proximité avec un acteur, ainsi que
  les objets, structures, toitures, intérieurs, personnages multi-cases,
  accessoires de décor et changement de hauteur déclenchent le **fallback
  intégral**. Le traitement des silhouettes/occlusions vient dans la
  tranche suivante, après tests spécifiques.
- Un coup de pinceau massif, un zoom, une manipulation d'étage et une
  invalidation du cache conservent le rendu complet.

Le chemin est conditionné par `scene_revision` et la matrice de validation
du document ; les appelants externes, scripts et combats restent en mode
conservateur.

## Tests

Sous Linux, Python avec tkinter et Xvfb :

    python3 -m unittest tests_standalone.test_dirty_tiles_3732e -v

    SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest -v \
      tests_standalone.test_dirty_tiles_3732e_gui \
      tests_standalone.test_editor_render_cache_3718d_gui

Le gate compare les éléments Canvas à un rendu complet du même
`render_isometric` : types, coordonnées, options, tags, ordre global
et scrollregion ; tests avec eau, ponts, undo/redo, relief et trois zooms.
Les tests couvrent les cartes de 32²/64²/128² (planificateur) et 65²/128²
(rendu Tk, 65² dépassant la limite du chemin geometry).

## Mesures

    # Smoke CI : trois mesures, résultat exploratoire
    xvfb-run -a python3 scripts/benchmark_dirty_tiles_3732e.py \
      --quick --output dirty-smoke.json

    # Référence : mêmes paramètres sur un poste stable, 100 mesures minimum
    xvfb-run -a python3 scripts/benchmark_dirty_tiles_3732e.py \
      --sizes 65,128 --zooms 24,54,96 --samples 100 \
      --output dirty-reference.json

Ce benchmark compare le dessin complet et le rendu local, avec
`Content.from_dict` amorti via le même `EditorContentProjection`,
et la peinture Tk `update_idletasks()`. Les mutations tactiques sont
appliquées avant chronométrage, afin d'isoler le coût du refresh.

Les p50/p95/p99 ne donnent ni la latence de saisie physique ni une mesure
de fluidité de toute l'application. Le mode CI n'établit **aucun budget**
et n'autorise pas de revendication de vitesse certifiée.

## Suite

3.7.32E2 : graphe de dépendances d'occlusion pour les façades, toitures,
décors élevés et acteurs proches, en conservant un gate de rendu intégral.
3.7.32F : scheduler d'invalidation/déduplication des callbacks Tk.
