# Map Builder 4.0F — Procedural Terrain & AutoBlend

## Statut et périmètre

Ce lot est la **première tranche fonctionnelle** de génération de terrain :
pas encore de génération complète de biomes, ni de nouveaux packs PNG peints.
Il garde les surfaces tactiques ordinaires `grass`, `dirt`, `sand`,
`stone`, `cobble`, `rock`, `water`, `bridge`.

### AutoBlend et parité Studio/Player

Le rendu isométrique commun `render_isometric` calcule des bandes de
transition irrégulières **à partir des quatre voisins** via
`terrain_autoblend.blend_edges` et `blend_polygon`.

- Une frontière entre terrains terrestres de même hauteur est peinte **du
  côté du terrain de plus faible priorité**. Le bord extérieur est le segment
  exact du losange partagé : deux cases ne créent pas deux raccords concurrents.
- Les chemins de terre, prairies, dalles et rochers reçoivent un contour
  irrégulier déterministe. Le rendu exploite le **même atlas existant** et les
  couleurs de surface communes; il s'agit d'une **transition prototype**,
  pas encore d'un véritable mélange de pigments multi-couches.
- Aucun raccord terrestre sur des hauteurs différentes : les falaises restent
  gérées par le relief normal. **Eau et ponts** utilisent les masques
  `iso_connections.py` déjà existants, sans conflit.
- Choix des deux variantes du même atlas déterministe par coordonnées monde,
  sans dépendre du viewport ni de l'ordre de rendu.
- Le rendu est actif par défaut, désactivable visuellement avec
  `layers['AutoBlend']=False` sans affecter la sauvegarde.
- Les mêmes fonctions sont appelées en Studio, en Player et par le chemin de
  rafraîchissement `EditorRenderCache`.

### Outil de génération guidée dans le Studio

Dans l'éditeur de carte :

1. Sélectionner un **rectangle** (jusqu'à **512 cases** pour l'aperçu).
2. Choisir `prairie`, `aride` ou `rocaille`, et saisir une **seed**.
3. Cliquer **Aperçu**. Une grille verte indique **exactement les cases qui
   changeraient**, sans enregistrer de modifications et sans toucher l'Undo.
4. Cliquer **Appliquer**. Une seule transaction `Document.replace` valide la
   totalité de la génération et crée **un unique Undo**.
5. Repeindre ensuite librement au pinceau intelligent; AutoBlend recalculera
   les transitions de manière contextuelle.

Les régions contiguës ou générées en plusieurs sous-rectangles avec la même
seed/style échantillonnent la **même fonction de bruit en coordonnées monde**.
L'ordre de génération n'entre donc jamais dans le résultat.

La génération **ne remplace pas** les unités, objets, objectifs, obstacles,
décors, cases élevées, ponts ou rivières déjà posés. Une proposition contient
un hash SHA-256 du document source : après la moindre modification, elle est
**périmée** et doit être prévisualisée à nouveau. Aucune nouvelle clé JSON de
mission ou migration n'est nécessaire.

### Mise à jour locale

Les couleurs de raccord des cases changées ne dépendent que de ces cases et
de leurs quatre voisines cardinales. `terrain_dependents` documente cette
portée. Sur les cartes sans dépendances complexes, l'accélérateur existant
`editor_dirty_tiles.affected_terrain_cells` rafraîchit un **3×3 conservateur**
plutôt que de reconstruire tout le Canvas. Si acteurs, bâtiments, relief ou
conditions complexes rendent la mise à jour sélective incertaine, le **rendu
complet sécurisé** reste le fallback.

## Validation

```sh
python -m unittest tests_standalone.test_terrain_autoblend_3732f -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_terrain_autoblend_3732f_gui -v
python -m unittest discover -s tests_standalone -v
```

Critères d'acceptation :

- Des terrains voisins distincts produisent une seule transition cohérente
  sans bande sur une rivière, un pont ou une différence d'élévation.
- Les zooms **24 / 54 / 96 px** conservent les mêmes points d'ancrage.
- Une édition locale modifie au plus les 9 cases de la zone dirty sur une
  carte simple; la sortie du Canvas partiel correspond au rendu complet.
- Génération seedée reproductible; aperçu sans effet de bord; commit validé,
  Undo/Redo, sauvegarde et retour Player inchangés.
- Un aperçu obsolète ou une édition sur des ressources protégées est refusé.

## Limites restant pour les lots ultérieurs

L'art peint précédemment est composé surtout de **dioramas isolés** avec des
flancs épais; ce ne sont **pas** des tuiles assemblables directement. Il faudra
produire des textures de dessus propres (sans bord de falaise interne), des
masques d'alpha et des variantes de transition autour d'un pivot/éclairage
communs pour atteindre le rendu aquarelle final. Les futurs lots pourront
ajouter des *brush stamps* peints, de l'herbe et de l'eau animées, et seulement
ensuite une génération par biomes avec routes/rivières à l'échelle d'une carte.
