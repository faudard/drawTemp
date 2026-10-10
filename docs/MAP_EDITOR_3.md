# Map Editor 3.0 — phase 2.5.1

Cette étape complète l'éditeur Tk existant plutôt que de créer un second
format de carte. Le moteur `Battle` reste **headless** et continue à lire
les mêmes `Content`/`Mission` validés ; aucun changement de règle, d'ABI ou
de replay n'est introduit.

## Sélection et presse-papiers

Dans `python -m sporebound editor --content chemin/vers/contenu.json` :

1. Choisir **Sélection** dans *Outil*. Cliquer/glisser pour sélectionner un
   rectangle inclusif. Maintenir **Maj** au début du geste pour ajouter le
   rectangle à la sélection précédente, même s'il est disjoint.
2. Appuyer sur **Copier cases** ou **Ctrl+C** lorsque le canevas a le focus.
   Une copie est un instantané indépendant, comprenant uniquement les
   attributs des cases sélectionnées et les objectifs de ces cases.
3. Déplacer le curseur avec l'outil **Collage** : les cases à destination sont
   encadrées en vert, les débordements hors carte en rouge. Cliquer pour coller.
   On peut aussi choisir la case d'ancrage et appuyer sur **Coller terrain**
   ou **Ctrl+V** avec le focus canevas.
4. **Annuler / Rétablir** traite chaque collage comme une opération complète.
   Un collage interdit (hors carte, mur sur un personnage, objectif invalidé,
   zone de déploiement bloquée) est intégralement rejeté par `Content`.

Le presse-papiers préserve les formes irrégulières : les cases **non
sélectionnées** à l'intérieur du rectangle englobant ne sont jamais
modifiées. Les cases sélectionnées sans terrain explicite effacent la
définition du terrain de destination. Les objectifs sont copiés eux aussi ;
les objectifs précédemment présents sur ces cases sont remplacés.

**Les unités, triggers et objets de siège ne sont pas dupliqués** :
leurs identités, dépendances et liens exigent des opérations de création
spécifiques. Le presse-papiers est temporaire (non enregistré dans le jeu).

## Pinceaux, couches et placement

- **Pinceau** et **Rectangle** conservent leurs outils de terrain,
  relief +/−, murs, terrain coûteux, couvert, danger et objectif.
- Dans *Terrain*, **unit** déplace l'unité sélectionnée à la case cliquée ;
  **object** déplace l'objet choisi. Les validations de collisions, de
  footprint et de références du modèle s'appliquent.
- Les pinceaux **zone+** et **zone-** ajoutent ou retirent les cases dans
  la zone identifiée par le champ *Zone*. Le premier ajout crée la zone et
  inclut automatiquement les empreintes initiales des unités alliées afin
  de ne pas invalider leur déploiement. Un dernier retrait peut supprimer
  une zone devenue vide. La validation refuse notamment une case bloquée
  et une position de joueur hors des zones restantes.
- Les interrupteurs, portes et engins référencés gardent leurs identifiants.
  Le déplacement d'une défense translate les cellules de son effet ; le
  débouché d'un passage reste à son emplacement explicitement défini.
- **Couches visibles** : Terrain, Relief, Déploiement, Objectifs, Objets et
  Unités. Leur masquage change uniquement la visualisation d'authoring,
  pas les données ni l'état du moteur.

Une mission créée depuis le Project Workspace 2.5.5 est immédiatement
éditable avec ces nouveaux outils.

## Contrats et limites

- Toutes les modifications sont des copies validées par
  `Content.from_dict`, puis confiées à `Document.replace` pour Undo/Redo.
- Le jeu et les sauvegardes existants conservent leurs formats.
- Le mode **Collage** est un aperçu de destination sur la grille Tk, pas un
  moteur de rendu 2.5D. Les futurs calques graphiques/tilesets et palettes
  de sprites nécessitent la phase suivante de 2.5.1 et le renderer 2.6.
- La duplication automatique de groupes d'unités, objets et événements,
  les transformations rotation/symétrie et l'édition visuelle avancée des
  zones multi-camps sont hors périmètre de cette fondation.

## Validation

```sh
python -m unittest discover -s tests_standalone -p test_map_authoring.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```

Les tests couvrent les zones irrégulières, copier-coller avec objectifs,
les limites de carte, le refus d'un terrain sous une unité, les déplacements
d'acteurs et objets, les zones de déploiement, l'historique et les gestes Tk.
