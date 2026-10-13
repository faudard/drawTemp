# 3.7.19C — Palette d'acteurs et d'objets interactifs (premier lot)

## Objectif

Placer visuellement des personnages/monstres déjà configurés et des objets
interactifs depuis le Map Editor isométrique, sans JSON manuel. Ne pas
introduire de registre parallèle de personnages, de règles de combat ni de
modification des formats Content/Replay.

## Parcours utilisateur

1. Ouvrir **Acteurs et objets** dans la barre supérieure du Map Editor.
2. Rechercher un acteur déjà présent dans la mission, un **archétype installé**
   dans Character/Bestiary Studio (loup, bandit, chevalier, etc.) ou choisir
   Porte, Levier, Coffre, Bélier, Catapulte, Passage ou Défense.
3. La liste affiche des **miniatures PNG**, avec le même atlas que le renderer
   pour les acteurs, et des icônes du décor existant pour les objets. Un acteur
   permet de prévisualiser ses quatre orientations et ses deux poses idle/marche.
4. Pour un archétype, choisir le camp **player/enemy** avant la pose.
   Pour un levier, bélier ou une catapulte, sélectionner **une porte existante**
   comme cible. Pour un passage, cliquer successivement l'entrée et la sortie
   **sur la carte**, sans saisir de coordonnées.
5. Cliquer **Placer sur la carte**, puis survoler une case de l'éditeur.
   L'empreinte complète s'affiche en **vert si la pose réelle est valide** ou
   en **rouge si elle est refusée** ; la barre d'état détaille alors la raison.
   Le sprite ou l'icône est visible à l'échelle de la carte. Cliquer pour poser.
6. Pour les passages, une flèche relie l'entrée choisie au pointeur ; la sortie
   doit être une case distincte, non bloquée, contrôlée par les règles du jeu.
   Échap annule le mode sans modifier Content. L'opération valide est
   enregistrée en une seule transaction Undo/Redo.
7. Répéter pour d'autres cases, enregistrer et relancer le playtest.

## Contrats

- `entity_entries(data, mission_id)` construit la liste depuis les acteurs
  présents dans la mission **et** les archétypes installés dans
  `Content.archetypes`. Les campagnes anciennes sans archétypes continuent
  de fonctionner. Les modèles restent gérés par Character/Bestiary Studio,
  sans création d'un catalogue parallèle.
- `place_entity` retourne une copie validée du document, jamais une
  mutation in-place. Les identifiants d'acteurs et d'objets sont générés sans
  collisions à l'intérieur de la mission.
- Le clonage conserve les attributs de combat de l'acteur source et l'équipe,
  change son ID, sa position et son orientation, restaure PV/MP lorsque ces
  maxima figurent dans la définition et remet l'état de tour à zéro.
  Les patrouilles suivent la translation (elles sont rejetées si elles sortent
  de la carte). Une insertion directe d'archétype conserve sa référence
  `archetype` et laisse `ActorFactory` résoudre ses propriétés au chargement.
  Le camp choisi n'affecte que cette nouvelle instance.
- La gestion des liens, des destinations, des collisions et des contraintes
  des objets utilise `authoring.add_object` et le modèle Content existants.
- Les changements sont tous effectués par `Document.replace` et sont donc
  compatibles avec l'historique de l'éditeur.
- Le retour de survol `preview_entity_placement` exécute la **même validation
  que la pose** sur une copie non persistée. L'éditeur évite de recalculer
  celle-ci à chaque pixel du pointeur grâce à une clé de cache par cellule,
  choix, document, orientation, zoom et mode de rendu.

## Validation

- `python -m unittest tests_standalone.test_entity_palette_3719c -v`
- `SPOREBOUND_GUI_SMOKE=1 python -m unittest tests_standalone.test_entity_palette_3719c -v`
  avec un affichage Tk ou Xvfb
- Matrice CI GitHub, Windows/Linux/macOS et distribution.

### Limitations explicites

Ce lot ne crée pas un éditeur avancé de statistiques depuis la palette ; les
unités sont configurées dans Character/Bestiary Studio. Les objets n'ont pas
encore de sprites PNG spécialisés : des illustrations provisoires réemploient
l'atlas de décors existant, avec un marquage explicite de leur statut de
placeholders. Leur vraie apparence finale reste à créer. Le déplacement d'objets et d'unités existants
continue d'utiliser les outils de déplacement déjà présents.

L'orientation choisie est un attribut de spawn persistant ; la prévisualisation
de la pose de marche reste purement graphique, sans horloge de simulation.
L'édition des interactions conditionnelles et les inspecteurs communs sont
prévus pour 3.7.21C et 3.7.21A.


## Gate de la deuxième passe : sprites et passage graphique

- Le rendu partagé `render_isometric` prend un `object_atlas` optionnel ;
  le Player et le Studio y passent la **même classe** `IsoObjectAtlas`.
- En sélectionnant un passage sans destination, le premier clic mémorise
  seulement une entrée en mémoire d'UI : **aucune modification du Document**.
- Le second clic est validé par `place_entity` ; sorties identiques à l'entrée,
  hors carte ou bloquées sont rejetées sans édition partielle. Le mode reste
  actif après un refus, sauf annulation explicite par Échap.
- Passage dessiné au survol : origine bleue, flèche verte/rouge vers la sortie.
- Tests de PNG, de rendu Tk, de transitions, de sauvegarde/rechargement et
  de retour arrière à intégrer aux gates CI et revue visuelle multi-zoom.
