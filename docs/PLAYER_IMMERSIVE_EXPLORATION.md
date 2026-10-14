# Player — exploration immersive et raccourcis

Le Player de Jeanne affiche les scènes d'exploration directement dans un
Canvas occupant la surface disponible. Le titre, les gros compteurs
campagne et l'ancien inspecteur latéral ne prennent plus de place sur la carte.
Les points d'intérêt restent affichés dans la vue isométrique et les
interactions sont disponibles sans panneau permanent.

## Commandes

| Touche | Effet |
| --- | --- |
| Flèches / ZQSD / WASD | Déplacer Jeanne d'une case |
| Clic sur une case voisine | Marcher jusqu'à cette case |
| E | Parler à l'habitant voisin ou examiner le lieu voisin |
| R | Secourir un civil voisin quand l'action est possible |
| Espace | Attendre un déplacement dans une scène à habitants |
| Échap | Ouvrir/fermer le menu de pause |
| F5 | Sauvegarder la session active |
| F9 | Recharger le slot actif après confirmation |
| F3 | Inspecteur technique en lecture seule (campagne) |

Le menu Échap fournit **Reprendre**, **Sauvegarder**, **Charger**,
**Gestion des sauvegardes**, **Vue isométrique**, **Options** et
**Menu principal**. Les écrans narratifs et le combat conservent leurs
contrôles contextuels. En combat, Échap reste prioritaire pour annuler la
sélection lorsque la carte tactique a le focus.

Les touches F3/F5/F9 sont réservées et ne sont plus proposées par le
remappage des actions tactiques. Les anciennes préférences qui leur
assignaient une action ne sont pas supprimées ; le validateur de préférences
les signalera, puis utilisera les raccourcis sûrs par défaut.

## Contraintes de fiabilité

- F5 utilise `PlayerController.save()` : aucun format de sauvegarde parallèle.
- F9 recharge exclusivement la campagne et le slot actifs, en respectant
  le mode long, la validation du journal et la récupération existante.
- Aucun jeu de règles, variable narrative ni progression n'est modifié par
  la refonte de présentation.
- La taille des cases isométriques s'adapte au viewport sans modifier leurs
  coordonnées logiques, le hit-testing ou la carte narrative.
- Le changement de vue et la sortie du menu de pause ne doivent jamais
  consommer un tour ni déclencher une interaction.

## Vérification

```sh
python -m unittest tests_standalone.test_player_immersive_map tests_standalone.test_exploration_iso_view -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_player_immersive_map tests_standalone.test_exploration_iso_view_gui -v
```

Vérifier manuellement une partie neuve de Jeanne en 800×580 et 1160×820,
déplacement et clic sur les cases voisines, interaction avec les blés,
assistance aux villageois, F5/F9, Échap, retour du menu et passage en vue
orthogonale. Confirmer aussi qu'aucune pression sur F5/F9 depuis le menu
principal ne modifie une sauvegarde.
