# 3.7.19C — Palette d'acteurs et d'objets interactifs (premier lot)

## Objectif

Placer visuellement des personnages/monstres déjà configurés et des objets
interactifs depuis le Map Editor isométrique, sans JSON manuel. Ne pas
introduire de registre parallèle de personnages, de règles de combat ni de
modification des formats Content/Replay.

## Parcours utilisateur

1. Ouvrir **Acteurs et objets** dans la barre supérieure du Map Editor.
2. Rechercher un acteur déjà présent dans la mission (Jeanne, bandit, loup,
   garde, etc.) ou choisir Porte, Levier, Coffre, Bélier, Catapulte, Passage ou
   Défense.
3. Un acteur affiche sa silhouette réelle du renderer partagé. Les quatre
   orientations et les deux poses idle/marche sont prévisualisables.
4. Pour un levier, bélier ou une catapulte, sélectionner **une porte existante**
   comme cible. Pour un passage, saisir sa destination sous forme `x,y`.
5. Cliquer **Placer sur la carte**, puis une case de l'éditeur. Un contour bleu
   et, en mode isométrique, le sprite de l'acteur indiquent la cible. La
   validation réelle a lieu au clic ; une case bleue n'est pas une promesse de
   placement autorisé.
6. Répéter pour d'autres cases, utiliser **Annuler/Rétablir**, sauvegarder et
   relancer le playtest.

## Contrats

- `entity_entries(data, mission_id)` construit la liste depuis les acteurs
  présents dans la mission, même si `Content.archetypes` est vide (cas des
  campagnes existantes). Les archétypes réutilisables restent gérés par le
  Character & Bestiary Studio.
- `place_entity` retourne une copie validée du document, jamais une
  mutation in-place. Les identifiants d'acteurs et d'objets sont générés sans
  collisions à l'intérieur de la mission.
- Le clonage conserve les attributs de combat de l'acteur source et l'équipe,
  change son ID, sa position et son orientation, restaure PV/MP lorsque ces
  maxima figurent dans la définition et remet l'état de tour à zéro.
  Les patrouilles suivent la translation (elles sont rejetées si elles sortent
  de la carte).
- La gestion des liens, des destinations, des collisions et des contraintes
  des objets utilise `authoring.add_object` et le modèle Content existants.
- Les changements sont tous effectués par `Document.replace` et sont donc
  compatibles avec l'historique de l'éditeur.

## Validation

- `python -m unittest tests_standalone.test_entity_palette_3719c -v`
- `SPOREBOUND_GUI_SMOKE=1 python -m unittest tests_standalone.test_entity_palette_3719c -v`
  avec un affichage Tk ou Xvfb
- Matrice CI GitHub, Windows/Linux/macOS et distribution.

### Limitations explicites

Ce lot ne crée pas un éditeur avancé de statistiques depuis la palette ; les
unités sont configurées dans Character/Bestiary Studio. Les objets n'ont pas
encore de sprites PNG spécialisés ; une pastille neutre représente leur
prévisualisation sur la carte. Le déplacement d'objets et d'unités existants
continue d'utiliser les outils de déplacement déjà présents.

L'orientation choisie est un attribut de spawn persistant ; la prévisualisation
de la pose de marche reste purement graphique, sans horloge de simulation.
L'édition des interactions conditionnelles et les inspecteurs communs sont
prévus pour 3.7.21C et 3.7.21A.
