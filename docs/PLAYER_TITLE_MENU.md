# Player — menu principal cinématique

Ce menu remplace l'ancien formulaire « Nouvelle aventure / reprendre » dans
`sporebound.player_app.PlayerApplication.title_screen`. Il n'ajoute aucune
couche de gameplay ni nouveau format de sauvegarde. Le rendu illustré
utilise désormais **Pillow comme dépendance runtime**, installée avec le projet.

## Organisation

- **Continuer** n'est activé que lorsque le slot sélectionné possède un fichier
  ou une copie de secours ; le chargement est toujours validé par
  `PlayerController` (une sauvegarde incompatible sera refusée).
- Si « Continuer » découvre une empreinte de contenu/projet/règles incompatible,
  un dialogue explique le blocage sans afficher le journal d'erreurs brut. Le
  joueur peut explicitement commencer une **nouvelle partie dans un autre
  emplacement réellement libre** ; aucune sauvegarde, copie `.bak`, archive
  `.damaged` ou journal de session longue n'est écrasé. S'il n'existe aucun
  emplacement libre, le Player explique la situation sans modifier le disque.
  Ce choix ne permet pas de reprendre l'ancienne progression : elle nécessite
  les données d'origine ou une migration explicite validée.
- **Nouvelle partie** conserve la confirmation d'écrasement du slot v2 et le refus
  d'écraser une session longue.
- **Charger une partie** ouvre un panneau de sélection du nom de campagne, du
  slot et du mode de sauvegarde (mode long toujours **opt-in**).
- **Options** et **Quitter** restent visibles dans le menu principal.
- **Choisir campagne / emplacement** et **Outils avancés** sont des points
  d'entrée secondaires. Le gestionnaire, la migration v1→v2, la copie v1/v2
  vers une session longue et les éventuelles démos restent accessibles.

## Illustration intégrée

La campagne Jeanne livre le fond de château peint
`sporebound/content/art/jeanne/jeanne_menu_backdrop.png` (640 × 900,
PNG à palette optimisé). La composition est une illustration seule, sans
boutons ni texte rasterisés. Elle est dérivée d'une création originale
générée pour le menu de Jeanne ; seules les zones illustrées ont été
retenues pour supprimer les éléments factices de la maquette.

Le rendu emploie un **cover crop** de la zone panoramique à gauche des
boutons, sans déformer le ratio de l'image. Avec Pillow, l'interpolation
LANCZOS et un fondu continu vers le menu sont mis en cache par taille de
fenêtre. Sans Pillow, ou si le fichier est illisible, le menu cinématique
utilise directement **le décor vectoriel** : aucun agrandissement pixelisé
par Tk ni bande tramée. Le contraste renforcé masque l'illustration pour
garder une surface lisible. Aucun asset distant, format de sauvegarde ou
changement de règles n'est ajouté.

En l'absence du nouveau fond, le portrait existant
`sporebound/content/art/jeanne/jeanne_portrait.png` peut toujours
apparaître sur le décor vectoriel. Les intitulés proviennent de
`GameProject`, et le mode spécifique « Chapitre I » conserve son
identité dans l'accroche du titre.

La page de titre utilise la palette sombre/ivoire/or, avec focus visible et
boutons Tk natifs. Les choix restent accessibles au clavier. Le contraste
renforcé et l'échelle de texte sont repris des préférences du Player. En
sortant du titre, la disposition initiale des écrans de jeu est rétablie.

## Vérifications

```sh
python -m unittest tests_standalone.test_title_menu -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_title_menu -v
python -m sporebound player --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json
```

**Gate manuel avant fusion :** inspecter en 800×580, 1160×820 et plein écran, avec Pillow puis en simulant son absence,
à 100/125/150 % et contraste renforcé ; confirmer la lisibilité du titre,
le focus clavier et la fermeture des panneaux, puis créer/charger une partie,
inspecter un slot avec sauvegarde de secours, tester un slot libre et valider
que les actions avancées ne se déclenchent jamais sans clic explicite.


## R7 — mise en page fidèle au visuel de référence

`sporebound/title_menu_cinematic.py` remplace le montage vertical gauche
par une interface **entièrement interactive en Canvas Tk** :

- Titre de Jeanne en haut à droite, suivi d'une pile de **six cartes** :
  Continuer, Nouvelle partie, Charger une partie, Campagnes, Options, Quitter.
- Icônes vectorielles et textes dessinés à l'exécution : ils ne sont **pas**
  imprimés dans l'illustration et les fonctions sont reliées aux actions
  existantes du Player.
- Encart Campagne actuelle à gauche, avec nom et description et commande
  « Changer de campagne ».
- Barre inférieure Outils avancés, Crédits et Aide, chacun ouvrant un vrai
  panneau utilisable, sans commandes factices.
- Le décor original `jeanne_menu_backdrop.png` est prioritaire sur
  `jeanne_menu_stage.jpg` (désormais uniquement utilisé en secours). Le PNG
  est chargé séparément du Canvas : aucun texte ni bouton n'est rasterisé.
- Avec Pillow, l'illustration est redimensionnée en `cover` (recadrage sans
  marges) et estompée progressivement vers la colonne de commandes.
- **Sans Pillow**, le PNG n'est volontairement **pas** agrandi par Tk :
  l'image serait pixellisée et la transition créerait une bande pointillée.
  À la place, le décor vectoriel offre un repli net à toute résolution.
- **Pillow>=10 est une dépendance standard** de `pyproject.toml`, y compris
  dans les installations Windows du Player réalisées avec `pip install .`.
- Dimensions calculées via `title_geometry()` ; contrôle explicite des
  800×580, 1160×820, 1595×933, 1672×914 et 1920×1080. À petite taille,
  les sous-titres et pictogrammes se compactent plutôt que se superposer.
- Focalisation Canvas, navigation ↑/↓, Début/Fin et Entrée/Espace ;
  Échap ferme les panneaux. Une partie absente reste inchargeable.
- Le titre et le contenu de campagne viennent du projet ; seules les
  formulations purement décoratives du menu Jeanne sont adaptées à son
  univers. Toutes les mutations de jeu restent dans `PlayerController`.

Le rendu illustré utilise Pillow pour obtenir un redimensionnement doux
(LANCZOS). Sans Pillow ou lorsque le PNG est invalide, le rendu passe sur
le décor vectoriel, sans stipple ni flou d'agrandissement. Le contraste
renforcé masque toujours les fonds illustrés.

### Vérification

Pour installer ou mettre à jour l'environnement du Player :

```sh
python -m pip install -e .
python -c "from PIL import __version__; print(__version__)"
```

Puis lancer les tests :

```sh
python -m unittest tests_standalone.test_title_menu_cinematic -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_title_menu \
  tests_standalone.test_title_menu_cinematic -v
```

Gate visuel non automatisé : vérifier le menu dans la vraie fenêtre du
Player aux trois tailles de texte, les interactions des dix zones actives,
les états de sauvegarde, la navigation clavier et le fond sans Pillow.
