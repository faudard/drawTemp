# 3.7.20 — Intérieurs et étages superposés

## 3.7.20A — Intérieurs visibles (première PR)

**Livré dans la première tranche :**

- Case sélectionnée ou personnage dans une maison/tour/ruine : comportement
  historique de coupe du toit préservé côté Studio et Player.
- Nouveau mode **Intérieurs / coupe des toits** dans le Map Editor isométrique :
  on peut inspecter les bâtiments même sans personnage à l'intérieur.
- Sols praticables et porte repérés sans masquer le terrain, les unités,
  les objets interactifs ou les outils de sélection.
- Nombre de sols, murs, décors et état de l'entrée dans l'inspecteur.
- Sols/murs/objets réels dérivés des tuiles actuelles, pas d'un duplicata figé
  du tampon d'origine. Une peinture ultérieure change immédiatement la lecture.
- Fonctionne pour les identités persistantes et les anciens tampons reconnus ;
  les cartes historiques restent lisibles sans migration.
- Aucun changement de version Content, de sauvegarde, d'IA, de CT, de
  pathfinding, de collision ou d'intégrité des replays.

**Parcours manuel à vérifier** : placer une Maison, activer ISO puis Intérieurs ;
voir les cases praticables sans toit opaque, peindre un mobilier existant
(`feature:crate`, `feature:lantern`) et voir les informations de l'inspecteur
se mettre à jour. Désactiver Intérieurs puis entrer dans la maison avec un
acteur ; la coupe automatique doit toujours fonctionner. Répéter après
Undo/Redo, sauvegarde/réouverture et aux zooms 24, 54, 96, puis dans le Player.

**Limite** : il s'agit d'un intérieur sur le **niveau tactique existant**.
Les étages simultanément jouables au même (x, y) ne sont PAS implémentés.
L'affichage "Niveau" dans l'éditeur est une hauteur unique par case, pas un
indice d'étage. Les PNG d'architecture restent une représentation externe :
le rendu des vrais murs intérieurs et des cloisons artistiques nécessite un
lot d'assets distinct.

## 3.7.20B — RFC préalable aux vrais étages jouables

### Problème

Le moteur utilise `Board.tiles[(x,y)]`, `Unit.pos=(x,y)`, les objets,
déploiements, objectifs, déplacements, portées et triggers exprimés en 2D.
`tile.height` est une élévation, pas un étage empilable. Remplacer
`height` par un prétendu floor ID serait incorrect : le rez-de-chaussée et
le premier étage pourraient être simultanément traversables au même (x,y).

### Contrat proposé (non implémenté)

1. **Deux espaces explicitement séparés** :
   `ground_pos=(x,y)` pour la projection visuelle, `level_id` stable pour
   les niveaux navigables ; une adresse tactique serait `(level_id,x,y)`.
   Une même structure peut posséder plusieurs plateaux superposés.
   Les terrains sont par plateau ; une hauteur de relief existe toujours à
   l'intérieur d'un plateau.
2. **Niveaux nommés**, par exemple `ground` et `upper`, chacun avec
   leurs tuiles, ouverture/visibilité, altitude de référence et emprise.
   Les plafonds/toits portent des surfaces d'occlusion, pas des collisions
   implicites.
3. **Connexions explicitement autorisées** : escaliers, échelles, passerelles,
   sauts et trous, avec source, destination et coût. Aucun téléportage vertical
   depuis deux cellules superposées en l'absence d'une connexion.
4. **Mouvement et portées** : graphes de voisins 3D, coûts et dénivelés,
   occupation et pathfinding par plateau ; LOS et couverture décident si une
   attaque entre deux étages est autorisée. Les règles doivent être validées
   par des cas de jeu avant ajout à `Battle`.
5. **Édition** : étages dans l'arborescence de la structure, plateau actif,
   étages inférieurs en fantômes, sélection et déplacement à (x,y,level),
   visible de coupe, undo/redo atomique, liaison bidirectionnelle des
   escaliers, diagnostics de destinations orphelines.
6. **Player** : les mêmes plateaux et règles, filtre d'étage dynamique pour
   ne pas masquer les unités, transition caméra reproductible, saisie des
   destinations ambiguës explicite.
7. **Persistance et migration** : version de contrat négociée avant évolution ;
   la lecture de tout contenu v1 reste déterministe sur un unique niveau
   `ground`. Toute nouvelle clé est validée ; l'ancien code ne doit pas lire
   silencieusement une campagne multilevel comme si elle était 2D.
   L'ordre canonique des plateaux/connexions doit garantir sauvegardes,
   digests et replays identiques.

### Décisions de gameplay à obtenir avant codage

- Une unité au premier étage peut-elle attaquer directement une unité au
  rez-de-chaussée, et dans quelles conditions d'occlusion ?
- Peut-on détruire le sol d'un étage, déclenchant la chute d'un acteur ?
- Les grandes unités peuvent-elles emprunter escaliers/échelles ?
- Une unité sur la toiture compte-t-elle comme à l'extérieur pour les attaques
  à distance, la caméra et la météo ?
- Quelle profondeur de bâtiments et quelle taille maximale de plateaux
  servent de budgets de performance ?

### Gates indispensables de 3.7.20B

- Tour à deux plateaux partiellement superposés, deux personnages aux mêmes
  coordonnées XY mais niveaux distincts : occupation indépendante.
- Escalier montant/descendant, détour interdit sans connecteur, interaction
  avec porte, déclencheur et objectif sur le bon plateau.
- Sélection, changement d'étage, hit-testing et occlusion aux zooms 24/54/96
  dans l'éditeur **et** dans le Player.
- Sauvegarde, reprise, undo/redo, sérialisation déterministe, replay identique,
  export et compatibilité bit-à-bit des anciennes cartes v1.
- Benchmark sur château multiétage, captures artistiques inspectées et
  validations Windows/macOS/Linux.

La phase B exige une modification coordonnée du modèle, du moteur, des règles,
du runtime et de la persistance. Elle ne doit pas être fusionnée comme une
simple couche graphique ni être annoncée comme terminée avec la phase A.
