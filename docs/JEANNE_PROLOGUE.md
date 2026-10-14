# 3.0.2 + 3.0.3 — Jeanne : contenu autonome et prologue jouable

**État : tranche verticale du prologue en données tactiques/narratives ; pas la campagne complète.**

L'objectif est de commencer une histoire de Jeanne d'Arc **uchronique** dans le Player existant, sans casser les tests et les scénarios historiques de Sporebound. Le moteur de combat et les sauvegardes restent identiques.

## Présentation du prologue — vue 2.5D par défaut

Le Player lance maintenant **les champs de Domrémy** et **les ruines** en vue
isométrique, comme les missions tactiques. Le contrôle « Vue isométrique 2.5D »
dans la colonne de droite permet de repasser en vue orthogonale sans toucher à
la progression. Le même choix s'applique ensuite à la présentation des combats.

Les cases d'exploration sont toujours une grille logique à quatre voisins :
flèches / ZQSD / WASD et clic sur le losange adjacent. Le moteur de
`GameSession.exploration_state()`, les points d'intérêt, délais de secours,
conditions de sortie et sauvegardes ne changent pas. Un adaptateur convertit
uniquement les cases narratives en terrains **temporaires** et les affiche par
`iso_map.render_isometric`, avec l'atlas de Jeanne ; il ne crée pas un modèle
de carte ni un format de sauvegarde parallèle.

Validation ciblée :

```bash
python -m unittest tests_standalone.test_exploration_iso_view -v
python -m unittest tests_standalone.test_exploration_stage -v
python -m unittest tests_standalone.test_jeanne_prologue -v
```

Gate manuel : lancer une nouvelle campagne Jeanne, vérifier Jeanne et les
points d'intérêt en 2.5D, cliquer une case adjacente et examiner un souvenir,
basculer en 2D, sauvegarder/recharger, puis entrer dans la première mission
tactique en 2.5D. La représentation de l'exploration conserve des marqueurs
vectoriels pour les habitants et interactions : une finition artistique dédiée
de leurs sprites et de leurs animations reste à réaliser.

## 3.0.3.2 — Le village vivant

Cette étape enrichit l'exploration de Domrémy avec **quatre habitants** :
trois personnes à secourir (Colin, Isabeau, Loïse) et un témoin
(Frère Michel). Chacun suit une petite route déterministe, cohérente avec
les obstacles de la carte. Les villageois n'utilisent pas l'IA tactique de
combat : leur déplacement appartient au moteur narratif headless.

- **Parler** : accéder au dialogue si Jeanne se trouve sur une case proche.
- **Secourir** : faire sortir un civil de la zone dangereuse. Chaque secours
  est attribué **une seule fois** dans `village_rescued`.
- **Pression** : chaque déplacement et chaque commande « Attendre » avance
  une horloge d'exploration. À l'échéance d'un habitant, celui-ci n'est plus
  secourable. Les échéances sont des tours logiques, jamais du temps réel :
  mettre en pause ne pénalise pas le joueur.
- **Échec partiel sans softlock** : même si l'on n'a sauvé personne, Jeanne
  peut trouver les deux souvenirs obligatoires, atteindre le carrefour,
  puis choisir secours ou poursuite. Les conséquences persistent.
- **Impact en combat** : `GameProject.battle_support` définit des bonus
  d'inventaire tactique conditionnés par un flag numérique. Sauver au moins
  un habitant ajoute une potion à la défense de la grange ; sauver au moins
  deux habitants en ajoute une seconde et apporte une potion à la fuite.
  Cette préparation utilise **Battle.initial_state**, sérialisé et rejoué par
  les mécanismes normaux de sauvegarde. Elle ne modifie aucune unité après
  la création de la bataille.
- **Rétrocompatibilité** : les projets sans `actors` ni `battle_support`
  restent valides ; les formats antérieurs ne sont pas remplacés.

### Validation

```sh
python -m unittest tests_standalone.test_living_village -v
python -m unittest tests_standalone.test_exploration_stage -v
python -m unittest tests_standalone.test_jeanne_prologue -v
```

Les tests vérifient : déplacements prévisibles, dialogue, double
récompense interdite, échéance de sauvetage, sauvegarde/reprise au milieu de
l'exploration, reprise d'un combat avec inventaire conditionnel, et rejet
des projets mal configurés.

**Limites :** les civils sont visibles et sauvables **pendant l'exploration**
et influencent les réserves de la bataille suivante. Ils ne sont pas encore
des unités d'escorte autonomes dans le combat tactique, ni des habitants
persistants sur une carte monde.

## 3.0.3.1 — Exploration narrative et séquences visuelles

Cette évolution ajoute le contrat optionnel `GameProject.exploration` sans
changer les schémas existants de Content, Battle, Campaign et GameSession.

- **Champs** : déplacement 2D sur une carte narrative (flèches, ZQSD, WASD
  ou clic sur une case adjacente), examen des blés, du médaillon, des fleurs
  et du vieux chêne. Deux souvenirs sont requis avant le déclenchement de
  la vision.
- **Domrémy en flammes** : après le combat, exploration des ruines :
  la maison de Jacques, les appels de la grange et les traces des soldats.
  Le choix de secours ou de poursuite ne devient accessible qu'après les
  deux découvertes essentielles.
- **Mise en scène** : illustrations vectorielles procédurales Tk, motifs de
  blé et d'incendie, séquences de vision et de fumée avec animation légère.
  Aucune image externe n'est obligatoire.
- **Sauvegarde** : positions et visites sont conservées dans
  `Campaign.story_flags`, checkpointées par le `GameSession` normal.
  Déplacement interdit hors carte, sur un obstacle ou par saut diagonal.
  Les hotspots inaccessibles sont refusés à la validation de projet.
- **Accessibilité** : boutons d'interaction affichés quand Jeanne est à
  une case, commandes clavier et clic pour les déplacements voisins.
- **Compatibilité** : sans section `exploration`, un projet ancien conserve
  strictement ses scènes et sa sérialisation actuelles.

L'exploration est **headless** : les contrôles passent de
`PlayerController` à `GameSession` puis à `Exploration`, tandis que
`exploration_view` ne modifie aucune donnée métier.

La transition du village vers l'une des deux missions utilise toujours les
choix et effets de `StoryBook` déjà validés. Les flammes sont visuelles :
elles n'appliquent pas de dégâts d'exploration et ne doivent pas être présentées
comme un nouveau moteur tactique.

### Tests dédiés

```sh
python -m unittest tests_standalone.test_exploration_stage -v
python -m unittest tests_standalone.test_jeanne_prologue -v
```

### Limites restantes

- Pas encore de déplacement libre continu hors grille.
- Les habitants suivent maintenant de courtes routes dans les cartes
  d'exploration, mais pas encore une IA d'évacuation multi-unités dans les
  batailles tactiques.
- Les cinématiques sont des vignettes vectorielles, non des animations
  dessinées image par image ou des vidéos.
- Pas de gestion étendue des choix dialogués sur la carte d'exploration
  ni de doublage.
- Aucun changement de règles du combat ou de contenu de l'acte I.

## Lancer le jeu

Depuis la racine du dépôt, sous Python 3.10+ :

~~~sh
python -m sporebound validate --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json
python -m sporebound player --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json
~~~

Dans la fenêtre, sélectionner « Les Cendres de Domrémy », emplacement 1 puis « Nouvelle partie ». Les sauvegardes sont enregistrées par le **PlayerController** dans le profil du projet ; « Continuer » les recharge par un checkpoint vérifié. Les JSON sont inclus dans le package au même titre que les exemples initiaux.

Pour lancer le Studio sur le contenu Jeanne :

~~~sh
python -m sporebound editor --content sporebound/content/jeanne.json
~~~

L'éditeur permet d'inspecter les cartes et les unités. Les scènes de dialogue résident dans le projet **jeanne.game.json** ; utiliser les fonctions de Studio compatibles avec le manifeste sans confondre la carte tactique et l'arbre de scènes.

## Scènes et parcours jouables

1. **Les champs** : découverte des souvenirs sur une petite carte explorable, puis écoute ou rejet des voix.
2. **La vision** : bannière, couronne, bûcher ; Jeanne découvre la fumée.
3. **Souvenir de Renaud** : mission tactique « leçon d'armes », combat de formation non létal dans l'histoire ; objectif du moteur = vaincre le partenaire d'entraînement.
4. **Domrémy en flammes** : vrai combat contre deux pillards, exploration des ruines puis choix exclusif.
5. **Secours** : tenir la défense jusqu'à l'évacuation ; protéger Margot.
6. **Poursuite** : vaincre le garde et le porteur de sceau pour récupérer un indice.
7. **Fuite** : atteindre les cases d'extraction à l'est en gardant en vie un rescapé.
8. **Promesse** : épilogue dialogué ; aucun contenu des actes I–V ne se débloque à ce stade.

### Choix et états
- Choix « secourir » : \`prologue_path="secours"\`, \`civilians_saved+=10\`, déverrouille seulement \`p0_03a_secours\`.
- Choix « poursuivre » : \`prologue_path="poursuite"\`, \`evidence+=10\`, déverrouille seulement \`p0_03b_poursuite\`.
- Après la mission choisie, une scène unique et partagée déverrouille \`p0_04_fuite\`.
- L'épilogue sauvegarde \`prologue_complete=true\` et laisse la campagne sans mission disponible, sans recommencer un ancien scénario champignon.

Le graphe conserve un chemin neutre après les deux options ; **aucun** \`Mission.next_missions\` n'ouvre les deux branches à la fois. \`GameSession\` suit les victoires réelles et applique les récompenses une seule fois.

## Gameplay et limites

- Les personnages sont des combattants humains. Les compétences « Estoc », « Frappe de garde » et « Premiers soins » utilisent les règles physiques/soins existantes, sans magie de combat, invocation ou démons.
- Le Player Tk affiche maintenant deux scènes explorables et des vignettes vectorielles animées pour le feu et les visions. Les sprites de personnages, illustrations finales, animations avancées et cinématiques complètes restent à créer.
- Le flashback est matérialisé par une mission d'entraînement qui se termine lorsque Renaud perd tous ses PV : il ne meurt **pas** dans l'histoire ; les objectifs avancés de duel sans élimination feront partie de l'itération suivante.
- La mission « Secours » vérifie que Margot survit et que suffisamment de temps s'écoule ; elle ne simule pas individuellement chaque habitant. La fin « Fuite » exige une unité jouable dans une case d'extraction **et** la survie du rescapé protégé, mais pas son déplacement physique dans la zone. Un véritable objectif multi-unité d'extraction est futur.
- Les conséquences exactes des choix sont persistées pour l'acte I. Les drapeaux sont du contenu data-driven dans \`GameProject.story\` et ne requièrent aucune modification des règles ni de version de sauvegarde.
- Ce prototype n'intègre pas encore le siège de Valcroix : celui-ci appartient aux travaux de l'acte III, qui réutiliseront les PR du château.

## Tests

~~~sh
python -m unittest tests_standalone.test_jeanne_prologue -v
python -m unittest discover -s tests_standalone -v
~~~

La suite dédiée charge réellement Content et GameProject, conduit chaque chemin jusqu'à sa fin avec le moteur/IA, vérifie l'exclusivité des missions, l'absence de succès factice, la sauvegarde en plein combat et la cohérence d'une reprise. Les scripts de CI existants exécutant \`unittest discover\` incluent ce module.

## Roadmap

- **3.0.2 — terminé dans cette tranche** : nouveau contenu autonome, unités, jobs, équipements, titre et scènes.
- **3.0.3 — tranche jouable** : sept scènes et cinq rencontres ; les deux variantes de mission sont exclusives ; sauvegarde/reprise et tests.
- **3.0.3.1 — livré** : exploration sur grille des champs et des ruines, interactions persistantes et vignettes animées.
- **3.0.3.2 — livré** : habitants mobiles, dialogues, sauvetages chronométrés et fournitures conditionnelles en combat.
- **3.0.3 suite** : escortes multi-unités dans les missions tactiques, caméra narrative avancée, portraits spécifiques, animation d'incendie plus riche.
- **3.1** : actes I et relations, premières preuves et retour de Guillaume.
- **3.3** : château de Valcroix (réemploi des moteurs de siège validés).
- **3.4** : démons tardifs et embranchements majeurs.

**Référence narrative :** PR #35 (\`docs/jeanne/\`). Les IDs de missions \`p0_01_lame\` à \`p0_04_fuite\`, les flags \`prologue_path\`, \`civilians_saved\` et \`evidence\` reprennent le catalogue de cette bible.
