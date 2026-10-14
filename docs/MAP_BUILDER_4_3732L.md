# Map Builder 4.0L — Natural Map Generator (tranche jouable)

## Objectif

Passer des peintures locales de 3.7.32F/K à une **composition cohérente de
carte entière** : relief doux, rivière 4-connectée, route, pont de franchissement,
berges naturelles, petites clairières et végétation. Le Studio et le Player
emploient exactement les atlas aquarelle G/H/J déjà fusionnés.

## Fonctionnement du Studio

1. Sélectionner un rectangle **d'au moins 12 × 12 et d'au plus 4096 cases**.
2. Choisir le biome `bocage`, `lande`, `vallon` (ou l'un des trois
   profils précédents), la `seed` et la densité de végétation `0–3`.
3. Cliquer **Aperçu carte**, sans modifier Content ni l'historique Undo.
   Violet = relief, bleu = eau, ocre = route/pont, jaune = décor.
4. Cliquer **Créer carte**. La proposition entière est validée contre
   la révision SHA du projet et appliquée en **une seule transaction Undo/Redo**.
5. En cas de conflit avec des cases authored, repositionner la sélection,
   ou dessiner d'abord ces éléments dans une zone vierge.

Le générateur est disponible dans l'éditeur de carte à côté du bouton
de génération de sol F/K. Il ne crée pas de second format de mission.

## Topologie garantie

- Tracé de rivière sinueux d'une frontière à l'autre. Chaque segment
  est relié à son suivant par un voisin **cardinal** : aucune diagonale
  seulement visuelle. Les berges reprennent les matériaux watercolor
  `dirt`/`sand`/`grass` selon biome et seed.
- Route continue dans la direction transversale de la rivière.
  Les tuiles de rencontre deviennent `bridge` et **non bloquantes** ;
  ailleurs les chemins sont des sols `dirt` de hauteur zéro.
- Deux clairières autour de points de passage sur la route, supprimant
  les irrégularités de hauteur et les props générés à cet endroit.
- Relief modéré à hauteur 0 ou 1, absent des passages principaux et de
  leur marge immédiate. Aucun changement de hauteur des cases authored.
- Végétation facultative, uniquement parmi les `feature` déjà supportées :
  `tree`, `bush`, `boulder`, `reeds`. Elle ne modifie pas la couverture,
  les collisions, le coût ni les intentions tactiques.

## Préservation et sécurité

Les routes/rivières ne sont jamais créées sur une unité ou son empreinte,
un objet, une relique, une zone de déploiement, un objectif, un événement
positionné, une structure, une route pavée, un pont/point d'eau existant,
un décor authored, une hauteur ou une case à propriétés tactiques spéciales.

Si un axe indispensable croise ces zones protégées, la génération est
**refusée explicitement**. Il n'y a ni suppression silencieuse, ni rivière
interrompue par un passage inaccessible.

Après l'aperçu, toute modification du document invalide le plan.
La validation recalcule intégralement le résultat attendu à seed/rectangles
identiques : un faux plan ou un aperçu partiellement modifié est rejeté.
La seule écriture est une mise à jour de `board.tiles`, via
`Content.from_dict(...).to_dict()`, puis `Document.replace`.
Le Player relit exactement les mêmes tuiles.

## Limites assumées du lot L

- Une route principale et un cours d'eau principal, avec les éventuels
  ponts à leur intersection ; pas encore de graphe routier reliant des
  objectifs arbitraires choisis par l'utilisateur.
- Une région préalablement construite qui bloque l'axe doit être
  repositionnée ou éditée manuellement. La recherche A* de corridors
  alternatifs avec certificats de connectivité objective sera un lot dédié.
- Les hauteurs modifient effectivement la tactique hors du corridor :
  le Studio doit laisser une revue humaine vérifier la jouabilité avant
  d'intégrer ces cartes dans une mission de campagne.
- Les sprites et les matériaux sont ceux déjà disponibles. Le lot L apporte
  une **meilleure composition**, pas de nouveaux dessins originaux.
- Les rendus 24/54/96 px doivent être inspectés humainement après la CI.
  Les tests n'attestent pas à eux seuls de la qualité artistique.

## Gates automatisés

```bash
python -m unittest tests_standalone.test_terrain_landscape_3732l -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_terrain_landscape_3732l_gui -v
python -m unittest tests_standalone.test_terrain_biomes_3732k -v
```

Couverture : seeds identiques, validation de continuité orthogonale,
ponts, caractères bloquants de l'eau et praticabilité des routes,
parité du rendu isométrique aux trois zooms, conservation de l'authoring,
aperçu obsolète/falsifié, sérialisation, Undo/Redo unique.

**Gate d'acceptation final :** CI verte + validation visuelle Studio/Player
sur une carte de 24² ou 32² + playtest de passage du pont.

## Suite : 3.7.32M

Étendre les corridors de L à un **graphe de points d'intérêt explicites** :
choix de bâtiments, campements, ponts, sortie et missions, liaison par
A* sur coûts de terrain, détours autour de ressources authored et score de
jouabilité. Ajouter des images étalons sauvegardées et une comparaison
quantitative du budget graphique avant/après génération.
