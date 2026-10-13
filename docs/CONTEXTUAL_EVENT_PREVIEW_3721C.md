# 3.7.21C — Événements et prévisualisation contextuelle

## Livraison (incrément compatible avec master)

Dans **Graphe des événements**, la sélection d'une condition ou d'une action
ouvre un panneau **Contexte et prévisualisation** sans quitter le graphe.

- Le panneau lit le déclencheur réel de `Mission.triggers`, en conservant
  l'ordre et la priorité des actions tels qu'utilisés par le Player.
- Les boutons **Scène liée** et **Cinématique liée** ouvrent les éditeurs
  canoniques lorsqu'une ressource de la **mission** est présente.
- Le lien narratif concerne `story.after_mission[mission_id]`, donc **après la
  victoire**. Les cinématiques visibles ont `before_mission` ou
  `after_mission` pour déclencheur. Elles ne sont **pas** activées par le
  déclencheur tactique sélectionné.
- Le bouton **Tester avec le moteur** instancie une bataille jetable à partir
  d'une copie du contenu, désactive les autres déclencheurs, puis réinjecte le
  déclencheur choisi dans `rules.triggers.dispatch`. Le prédicat et les
  actions sont donc exécutés par le **moteur existant**, jamais réinterprétés
  par l'interface.
- Un choix de scénario permet de sonder l'état **initial**, un état
  **condition vraie** ou **condition fausse**. Les conditions `tick`, `enter`,
  `hp_below`, `defeated` et `wave_capacity` s'appuient toutes sur les
  prédicats du moteur. Les états testés sont synthétiques et annoncés.
  Lorsque le contre-exemple est impossible (par exemple `tick >= 0`),
  le Studio affiche une erreur explicite au lieu de fabriquer un résultat.
- Le rapport indique condition, tick effectivement utilisé, événements moteur,
  créations/suppressions d'unités et **diff d'état** : PV, PM, position, statuts
  et dangers de terrain modifiés par les actions. Le rapport distingue les
  règles non activées, exécutées et les échecs partiels du moteur.
- Les cinématiques de type `scene` associées à la scène narrative
  après-victoire sont aussi proposées. Le créateur choisit **quelle**
  cinématique ouvrir si plusieurs ressources sont liées.
- Le tout est sans écriture ni modification du projet, de la mission ou
  de l'historique undo/redo.

## Parcours de validation

1. Ouvrir le Map Editor → onglet **Graphe des événements**.
2. Créer un déclencheur `tick >= 5` avec action `message`.
3. Sélectionner son nœud, scénario « État initial », tester au tick `4` :
   aucune activation.
4. Tester au tick `5` : événement `trigger` puis `message`.
   Répéter avec « Condition vraie » et « Condition fausse » : l'éditeur
   prépare les ticks `5` et `4` sans simulation des tours intermédiaires.
5. Ajouter une action `hazard` : vérifier la ligne « Case … · danger :
   ancienne → nouvelle valeur » dans les conséquences.
6. Revenir aux blocs, déplacer une action, revenir au graphe : l'ordre est
   identique. Enregistrer et rouvrir : aucune donnée d'aperçu n'est sérialisée.
7. Configurer une scène après victoire, une cinématique de mission et une
   cinématique liée à cette scène. Vérifier leur présence et la sélection
   explicite de la cinématique depuis le graphe. L'absence de lien
   désactive le bouton correspondant.
8. Choisir un boss `hp_below` et un point `enter` : comparer les scénarios
   vrai/faux, sans modifier les PV ou coordonnées du fichier projet.

Commandes de régression :

```bash
python -m unittest tests_standalone.test_event_context tests_standalone.test_event_graph
# Linux avec Xvfb, même protocole que la CI :
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_event_graph_gui
```

## Limites connues (à ne pas confondre avec une cinématique jouée)

- Le tick fourni est une **sonde ponctuelle** du prédicat : les ticks
  intermédiaires ne sont pas simulés, aucune IA ni campagne n'est déroulée.
  Les scénarios « vraie/fausse » utilisent des **états de test synthétiques** ;
  les positions simulées ne garantissent pas un chemin praticable, et
  `wave_capacity` n'invente pas des unités qui n'existent pas.
  Pour tester un enchaînement complet, utiliser le véritable playtest.
- Les objets de carte (leviers, portes), conséquences stratégiques et scènes
  cinématiques n'ont pas encore de lien direct `trigger → scène` dans le
  modèle de runtime. Le panneau ne crée pas de faux liens. Leur unification
  complète exige une évolution explicite et testée des contrats de jeu.
- L'aperçu est textuel et contextuel, pas un rendu visuel du Player. Une
  prévisualisation viewport synchrone reste un chantier distinct.
- Les opérations de sauvegarde globale, d'historique transversal et de
  récupération ne sont pas modifiées ici (3.7.21B).

Ce jalon ferme **l'incrément de navigation et de diagnostic tactique** de
3.7.21C, sans prétendre fermer l'intégration runtime narrative/cinématique
ou l'ensemble du Studio End-to-End.


## Aperçu isométrique des interactions (3.7.21C, deuxième incrément)

Le panneau **Graphe des événements** peut maintenant enregistrer une condition
`interact` avec l'ID d'un objet de la mission (par exemple `switch`).
C'est une règle de déclenchement **réelle**, validée par `Content` et exécutée
par la même famille `rules.triggers` que le Player. Le moteur émet
`interact` lors de la commande `Battle.execute({"kind": "interact", ...})`,
puis applique les triggers lorsque son dispatcher est appelé. Il n'existe
pas d'interpréteur de condition supplémentaire dans le Studio.

Dans l'aperçu **Condition vraie**, le Studio prépare un acteur vivant à
proximité de l'objet et lui attribue une activation de test. **La préparation
est synthétique et non sauvegardée** ; l'action sur le levier est en revanche
une vraie commande moteur avec ses règles de légalité. L'aperçu montre :

- **Avant** : état préparé, levier disponible et porte fermée.
- **Après** : interaction exécutée, porte ouverte, case débloquée, objet utilisé.
- Une action `wave` ou `spawn` dans le trigger est exécutée réellement par
  `rules.triggers.dispatch` ; les renforts figurent alors sur la carte.
- Les différences d'objets (`open`, `used`, `hp`, `pos`) et le journal
  sont visibles en complément des différences d'unités et du terrain.

**Vue isométrique avant/après** ouvre deux Canvas indépendants avec le
renderer partagé `render_isometric`, les atlas existants et les structures
persistantes. Le prévisualiseur n'importe pas de Tk dans le moteur headless
et ne modifie ni le document ni la mission courante du Player.

### Gate « levier → porte → renfort »

Sur la mission `garden` livrée avec drawTemp :

1. Sélectionner/créer un trigger `interact`, choisir l'objet `switch`.
2. Ajouter une action `message`, puis `wave` avec un archétype disponible
   et une case de renfort libre.
3. Dans le panneau de contexte, sélectionner **Condition vraie** puis
   **Vue isométrique avant/après**.
4. Vérifier dans l'aperçu la porte `gate` fermée avant, ouverte après,
   l'interaction du levier `switch`, le renfort et la chronologie moteur.
5. Vérifier que la carte enregistrée reste inchangée après fermeture.

### Limites de la navigation narrative

La scène `after_mission` est une transition **après une victoire de
campagne**, pas une action immédiate `trigger → dialogue`. Le panneau propose
un accès à l'éditeur canonique de cette scène, mais ne force pas une victoire
ni ne modifie `Campaign` dans l'aperçu isolé. La prévisualisation des
cinématiques de scène reste disponible dans `Cinematic Studio`.

### Tests ajoutés

`test_event_context.py` : valide la référence de l'objet, l'émission réelle
de `interact`, la porte qui se débloque, les renforts, la non-mutation des
données et le scénario négatif.

`test_event_graph_gui.py` : ouvre deux Canvas rendus à partir de vrais
états `Battle`, sans remplacer le Studio principal.
