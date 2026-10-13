# 3.7.18D — Profiling et invalidation du rendu Studio

Le Studio utilise maintenant `EditorRenderCache`, un adaptateur de commandes
Canvas autour du **renderer isométrique existant**. Le moteur tactique, le
format de sauvegarde, les atlas et le cache du Player ne changent pas.

## Invalidation

- La géométrie et les buckets de picking sont conservés tant que dimensions,
  zoom et hauteurs restent identiques. Une nouvelle instance `Content` ne suffit
  pas à invalider : le Studio reconstruit ses modèles à chaque refresh.
- Les commandes de dessin sont comparées par cellule, type, tags et ordinal.
  Seuls les items ajoutés/supprimés ou leurs coordonnées/options modifiées
  traversent Tcl. Un rafraîchissement identique crée **zéro** item Canvas.
- Les règles de raccord des rivières, de coupe des toitures, de profondeur et
  d'apparence des acteurs restent exécutées par `render_isometric`. Cela prend
  aussi en compte les modifications en place, undo/redo, imports et changements
  de mission, sans dépendre d'un compteur de révision incomplet.
- L'ordre de peinture est rétabli quand la topologie de la liste de commandes
  change. Un changement de profondeur réapplique l'ordre des groupes.
- Le passage par la vue plate abandonne le cache. Le retour ISO reprend la
  propriété du Canvas et efface les items de la vue plate. Les aperçus de
  placement sont explicitement nettoyés lors du refresh.
- Au-delà de **4 096 cases**, le Studio conserve seulement la géométrie et
  utilise le rendu Canvas complet. Le profiling 128² a montré une régression du
  diff de commandes et environ 24 Mo de mémoire Python conservée : ce chemin
  n’est donc pas activé sur les grandes cartes. Le retour à une petite carte
  reconstruit proprement la liste retenue.
- Le cache contient une seule scène et une seule géométrie ; pas d'historique de
  frames. Les références PNG des commandes restent celles des atlas existants.

## Mesure reproductible

```bash
xvfb-run -a python scripts/benchmark_editor_render_3718d.py \
  --frames 20 --output studio-render-3718d.json
xvfb-run -a python scripts/benchmark_editor_render_3718d.py \
  --sizes village --assets --frames 20 --output studio-render-assets-3718d.json
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest discover \
  -s tests_standalone -p test_editor_render_cache_3718d_gui.py -v
```

Le benchmark compare l'ancien dessin complet et le cache sur le même processus,
la même scène et les mêmes opérations : ouverture, refresh sans modification,
sélection, peinture, hauteur, zoom, undo/redo et sélection de 400 cases. Les
cartes 32²/64²/128² ont des bandes d'eau et de relief ; Valcroix couvre les
structures, objets et acteurs. Le mode `--assets` active les vrais atlas PNG.
Les opérations d'édition passent par `Document`.

Le JSON donne médiane/p95 par opération, temps d'ouverture, parsing du modèle
séparé, nombre d'items Canvas et allocations Python courantes/pic via tracemalloc.
La mémoire est mesurée dans une passe distincte pour ne pas fausser les latences.
Elle **n'inclut pas** la mémoire native Tcl/PNG et n'est pas le RSS du processus.
Le temps de dessin inclut `update_idletasks`, mais ni les panneaux Studio, ni la
mini-carte, ni les commandes `Document`. Ce n'est donc pas la latence complète
clic→écran du Studio, et ce n'est pas une mesure du Player.

La CI conserve les deux rapports JSON comme artifacts. Les tests Tk comparent
les types, coordonnées, options et ordre de **tous** les items au rendu complet,
y compris avec les PNG, et vérifient la stabilité des IDs sans modification.
Pas de seuil temporel universel sur les runners partagés. Le mode réellement
utilisé (`retained` ou `geometry`) figure dans les rapports.

## Limites assumées

La génération des commandes et la recherche des structures parcourent encore
la scène : ce cache réduit les échanges Python/Tcl et les reconstructions de
picking, pas toute la complexité Python. Un zoom ou une modification de hauteur
invalide la géométrie ; un changement de topologie peut réordonner tous les items. Le chemin grande
carte reconstruit toujours les items Canvas, mais réutilise le picking.
La première ouverture et certaines opérations globales peuvent être plus lentes
avec le cache et celui-ci augmente la mémoire Python. Le pooling de commandes,
le culling et les dirty regions restent des pistes à mesurer ultérieurement.
La mini-carte et `Content.from_dict` restent recalculés dans le refresh Studio.

## Résultats locaux du 13 octobre 2026

Python 3.12 / Linux / Tk 9 / Xvfb, 20 échantillons par opération.
Rapport complet : [studio_render_3718d.json](performance/studio_render_3718d.json).
Valeurs indicatives sur cet environnement, pas un budget certifié multi-OS.

Refresh sans modification, en millisecondes :

| Scène | Médiane avant → après | p95 avant → après | Cache |
| --- | --- | --- | --- |
| 32² (vecteurs) | 21.7 → 13.9 | 23.7 → 19.2 | retained |
| 64² (vecteurs) | 77.8 → 49.2 | 93.2 → 72.9 | retained |
| Valcroix + PNG | 45.2 → 15.8 | 47.4 → 21.4 | retained |
| 128² (vecteurs) | 281.1 → 256.1 | 327.6 → 311.9 | geometry |

La sélection 128² passe de 295,1 à 258,7 ms en médiane. Elle reste trop
lente pour parler d'une édition fluide de grandes cartes. Le cache adaptatif
conserve environ 2,9 Mo Python sur ce cas, contre environ 24,1 Mo pour le diff
complet rejeté lors du profiling. Sur 64², la liste retenue conserve environ
6,0 Mo ; certaines opérations globales (zoom, undo/redo, sélection massive)
restent moins bonnes dans les mesures, visibles dans le JSON.

Validation : suite complète de 763 tests passée avec Tk activé avant l'ajout du
repli grande carte ; après cet ajout et la correction de l'ordre des couches,
15 tests GUI ciblés éditeur passent, dont 5 nouveaux tests de parité/cache.
