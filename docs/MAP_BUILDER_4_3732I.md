# Map Builder 4.0I — Ambient Terrain Animation

## Objet

Première tranche des animations décoratives du terrain : brins d'herbe
oscillants, roseaux, petites feuilles et rides à la surface de l'eau.
Ce lot **n'ajoute aucune animation de combat**, aucun nouveau champ à
`Content`, `GameProject` ou `Battle`, aucune graine RNG persistée et
aucune migration de sauvegarde. Le temps utilisé est exclusivement celui
de la présentation graphique.

## Architecture

- `sporebound/terrain_ambient.py` est indépendant de Tk et du moteur.
  `strokes_for_cell` échantillonne les coordonnées d'une case existante
  et retourne de petits traits / ellipses transparents déterministes,
  appartenant au **même groupe de profondeur `iso_tile_x_y`** que le terrain.
- Les accents d'herbe utilisent la surface `grass`; les roseaux et les
  feuilles réutilisent les décors existants (`reeds`, `tree`, `bush`) ;
  l'eau reste `water` et conserve ses masques de berges, cascades et ponts.
- `TerrainAmbientAnimator` conserve les positions initiales de chaque
  primitive `iso_ambient`. Toutes les poses sont une fonction pure de
  **(case, élément, horloge de présentation)**. Un rafraîchissement applique
  uniquement `Canvas.coords`, sans reconstruire textures ou widgets,
  sans reclassification tactique et sans dérive cumulative.
- En grand format, l'échantillonnage est réduit de manière déterministe selon
  le nombre de cases. La densité cible de végétation et de rides reste
  **inférieure à quelques centaines de groupes** plutôt que 16 384
  animations séparées; le nombre exact dépend de la seed et du décor.
- `render_isometric` est utilisé à la fois par le Studio et par le Player,
  avec **les mêmes pivots de scène**. Les primitives sont placées après les
  textures et raccords F–H, avant les unités; l'occlusion courante et les
  groupes de dirty tiles restent en vigueur.
- Le Player réutilise sa minuterie de présentation existante pour animer les
  cases même pendant une scène inactive : **125 ms par image au repos** et
  la cadence déjà existante pendant les mouvements. Les updates n'affectent
  pas les activations CT et ne modifient jamais les événements tactiques.
- Le Studio offre la case à cocher **« Ambiance animée »** dans
  « Terrain & couches ». Son minuteur Tk est annulé à la fermeture. Avant
  un redraw retenu, les primitives sont remises à leurs coordonnées de
  référence; les caches `EditorRenderCache` restent donc autoritaires.
- Pour désactiver les animations sans aucune donnée de jeu, utiliser
  `layers['Ambiance']=False` lors de `render_isometric`.

## Ce qui n'est pas encore livré

Les animations sont de **petits accents graphiques vectoriels aquarellés**,
pas des sprite sheets haute fidélité. Elles ne déplacent pas les PNG de
personnages, n'animent pas la géométrie des bâtiments, ne simulent pas
physiquement les vents, et ne sont pas synchronisées à un flux audio.
La simulation de rivières, les courants, la pluie, les saisons et la
génération complète de biomes restent des travaux distincts.

## Gates

```bash
python -m unittest tests_standalone.test_terrain_ambient_3732i -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_terrain_ambient_3732i_gui -v
python -m unittest tests_standalone.test_terrain_autoblend_3732f -v
python -m unittest tests_standalone.test_terrain_transition_masks_3732h -v
```

Validation attendue :
1. La même coordonnée, les mêmes surfaces, le même clock et le même zoom
   produisent des positions identiques, quel que soit le viewport.
2. Au repos du Player, les mêmes items de Canvas sont réutilisés pendant
   huit ticks. **Aucune modification des tours, PV, CT ou état de mission**.
3. Dans le Studio, l'annulation d'une animation avant le redraw retenu
   évite la dérive cumulative. Les dirty tiles héritent du même comportement.
4. Sur une carte 128², le nombre d'éléments animés reste sous un budget
   dépendant de la densité, et aucun timer ne tourne dans un moteur headless.
5. Mode désactivé : aucune primitive `iso_ambient` et aucun champ JSON
   supplémentaire.
