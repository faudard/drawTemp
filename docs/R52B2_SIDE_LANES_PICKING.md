# R52.B2 — Projection latérale 2.5D, profondeur et picking

**Portée :** premier profil side utilisable dans le renderer Qt Quick R3 commun. **Cible :** branche de consolidation de la PR #402 ; ne pas adresser directement `master`. **Statut initial :** expérimental / gate R52 NO-GO tant que tests machine, goldens DPI et CI ne sont pas prouvés.

## Modèle mathématique et compromis de visibilité

La carte tactique reste constituée de coordonnées **canoniques** `(x, y, height)`. Le profil latéral affiche des bandes horizontales en conservant un intervalle de profondeur d'une ligne à l'autre :

```text
screen_world_x = 64 * x
screen_world_y = 24 * y - 12 * elevation

x = screen_world_x / 64
y = (screen_world_y + 12 * elevation) / 24
```

Ce **side-on 2.5D à bandes** n'est pas une caméra perspective 3D, ni la projection pure à profondeur nulle où plusieurs lignes de gameplay se superposeraient indiscernablement. Le maintien d'un espacement de 24 unités entre lignes permet un inverse géométrique cohérent sans toucher aux coordonnées des missions. Les surfaces élevées gagnent les superpositions dans le picking des tiles : les mêmes règles valent pour la caméra Studio et le Player, quel que soit le zoom/pan.

`SideProjection` appartient à `drawtemp.render.iso_scene`, aux côtés de `IsoProjection` et `TopDownProjection`. **Aucun second Core, second moteur de rendu ou modèle de sauvegarde** : `Camera`, `TileChunkIndex`, `render_items`, `pick`, `RendererController`, `TerrainTextureBatches` et les contrats Qt restent partagés. Le texture batching isométrique n'est pas réutilisé pour peindre des bandes latérales invalides : ce mode garde ses éléments Qt Quick individuels.

## Surfaces et sélection

- La vue `TopDownViewport.qml` rend aussi le profil `side` à partir des **mêmes lignes R3** ; en mode latéral, les tiles sont en `64×24`, les actors et objets gardent leurs marqueurs de base. Les plateaux surélevés affichent un petit pan de mur **cosmétique**.
- `cellAt` et `pickAt` continuent d'utiliser la projection du contrôleur; l'élévation connue sert à départager les surfaces visuellement superposées. `zOrder` privilégie les bandes de profondeur, sans affecter la simulation.
- Sécurité R6 : tant que les surfaces `building_surfaces` n'ont pas d'équivalent latéral, **les scènes qui contiennent structures / interior_floors sont rejetées**, y compris lors de `replace_scene`, avant modification de l'état du contrôleur. Ne pas silencieusement afficher une maison isométrique en profil latéral.
- `DepthProfile` et presets de zoom acceptent désormais `projection=\"side\"`, avec profils dédiés `side-preview` et `side-close`. Depuis un contrôleur **isométrique**, ces presets restent refusés : le profil n'est pas modifié in-place sans changement du QML correspondant.
- Le bouton **Aperçu latéral 2.5D** du Map Studio ouvre une fenêtre de lecture seule issue de `create_view(scene, projection_mode=\"side\")` : copie détachée de la scène courante et rendu R3 identique au Player, **aucune écriture Content/GameProject**. Les cartes ayant des bâtiments reçoivent un avertissement plutôt qu'un aperçu inexact.

## Validation / non-régression

```sh
python -m unittest discover -s tests_standalone -p 'test_r52b2_side_projection.py' -v
python -m unittest discover -s tests_standalone -p 'test_r52b_ambient_presentation.py' -v
python -m unittest discover -s tests_standalone -p 'test_r52a_depth_pipeline.py' -v
python -m unittest discover -s tests_standalone -p 'test_drawtemp5_r3.py' -v
python -m unittest discover -s tests_standalone -p 'test_drawtemp5_shared_viewport.py' -v
```

Les fixtures R52.B2 couvrent : conversion avant/arrière et élévations négatives/positives, picking au centre (dont plateforme occultant une ligne), trois résolutions/zooms/pans, picking acteurs/objets, culling grand monde, conservation des entrées, fail-closed pour R6, composition QML et smoke PySide6 facultatif. Les tests du nouveau code devront être **exécutés effectivement** en CI ou local avant validation.

## Gates et limites restantes

- **R52.B à poursuivre** : réelle édition des propriétés d'une scène/versionnement Content, animations plus avancées si souhaitées, parité complète des overlays HUD et exports, goldens DPI/profils/backends comparés physiquement.
- **R52.C** : culling et caches mesurés, p95/p99 CPU/GPU, Windows/Linux/macOS, GPU réel Studio + Player, garde mémoire et preuve d'absence de régression CT.
- Les effets de lumière actuels sont uniquement un **filtre d'ambiance 2D**, ni lightmaps ni ombres physiques.
- Les reliefs complexes, façades et toits latéraux R6, visibilité par raycast et physique plateforme complète **ne sont pas certifiés** ici. Ne pas confondre les bandes latérales avec le runtime platformer R32.
- **R50/R51** et l'intégration complète de la PR #402 demeurent des prérequis à la certification release, même si le code R52 se fusionne dans sa branche.
