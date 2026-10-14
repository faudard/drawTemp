# 3.7.32K — Biome Composition / Naturel aquarelle

## Pourquoi cette tranche

La PR #160 a introduit les régions seedées et AutoBlend. Depuis, les
PR #173/#178 et #197 ont ajouté le lavis aquarelle, les raccords peints
et des animations d'environnement. La prochaine étape ne consiste plus
à ajouter des bandes colorées, mais à **composer de vrais paysages**
avec les matériaux et les décors existants.

## Studio

Dans l'éditeur de cartes, sélectionner une zone rectangulaire (jusqu'à
512 cases dans le Studio), puis choisir une seed, un profil de paysage et
une densité de décors **0 / 1 / 2 / 3**.

Profils supplémentaires :

| Profil | Signature visuelle |
| --- | --- |
| `bocage` | Prairies, petits chemins de terre sinueux, arbres et buissons |
| `lande` | Poches herbeuses, terre sèche, affleurements rocheux |
| `vallon` | Prairie humide, plages de terre, bancs sableux et rochers |

Les profils `prairie`, `aride`, `rocaille` restent compatibles avec
leurs résultats antérieurs à seed identique. Les noms de surface
sauvegardés restent `grass/dirt/sand/stone/rock/cobble` et les détails
restent des `feature` existantes : `tree/bush/boulder/reeds`.

L'aperçu utilise **vert** pour les surfaces modifiées et **ocre** pour
les décors proposés. Il est calculé sans modifier le document, ni
l'historique. Confirmer applique les deux types d'édition **dans un
seul Undo/Redo** ; annuler récupère la scène précédente.

La densité zéro désactive complètement les nouveaux décors (comportement
hérité). Les décors sont optionnels et purement présentation :
aucune nouvelle collision, couverture, hauteur, valeur de déplacement
ou règle de combat.

## Géographie et rendu

- Bruits lents de relief/humidité, déformés par un champ de déplacement
  spatial (domain warping) ; les nappes se raccordent au-delà du rectangle
  sélectionné, sans reset local de seed.
- Plantation déterministe par **coordonnées mondiales** et seed, avec
  modulation en taches à une autre échelle. Les roseaux peuvent apparaître
  à proximité d'une rivière **préexistante** ; le générateur ne crée
  pas d'eau ni de rivière au milieu d'un scénario construit.
- Les décors passent par les sprites aquarelle `IsoPropAtlas`,
  les matériaux passent par `terrain_watercolor`, les frontières par
  `terrain_transition_masks` et l'ambiance par `IsoEnvironmentAtlas`
  (si activée). Aucun moteur alternatif n'est introduit.
- Les unités, objets, objectifs, rivières, ponts, hauteurs, props,
  surfaces bloquées et tuiles déjà dotées de propriétés tactiques
  restent protégés. La validation du plan se fait une deuxième fois
  lors de l'application, avec empreinte SHA du document d'origine.
- La dirty-tile invalidation reste locale, grâce aux entrées standard
  du modèle `Tile`. L'aperçu ne touche pas aux données et un plan
  obsolète est refusé.

## Limites et prochaine passe artistique

Ce lot produit une **composition de biomes** réellement jouable,
avec l'atlas aquarelle déjà livré, mais ne remplace pas les props existants
par de nouvelles illustrations peintes. La densité végétale est
intentionnellement limitée pour préserver la lisibilité tactique.

Pour une version de finition, créer des variantes dessinées à la main
des arbustes/champs, améliorer les micro-détails des sols et ajouter
un outil « routes et cours d'eau » indépendant, avec validation de
continuité/pathfinding et préservation des structures. Ne pas générer
automatiquement des obstacles ni modifier le contenu tactique sans
une option explicite.

## Gate

```sh
python -m unittest tests_standalone.test_terrain_autoblend_3732f -v
python -m unittest tests_standalone.test_terrain_biomes_3732k -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_terrain_autoblend_3732f_gui -v
```

Gates de qualité : mêmes seeds et résultats quel que soit le sous-rectangle,
replay sauvegarde et Undo/Redo stables, absence d'édition de la rivière/des
unités, masques et atlas identiques Studio/Player à 24/54/96 px.

**Statut** : en revue, ne pas considérer la matrice CI validée avant
son résultat sur GitHub.
