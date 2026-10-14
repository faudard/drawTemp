# Player — menu principal cinématique

Ce menu remplace l'ancien formulaire « Nouvelle aventure / reprendre » dans
`sporebound.player_app.PlayerApplication.title_screen`. Il n'ajoute aucune
couche de gameplay, aucun nouveau format de sauvegarde et aucune dépendance
obligatoire.

## Organisation

- **Continuer** n'est activé que lorsque le slot sélectionné possède un fichier
  ou une copie de secours ; le chargement est toujours validé par
  `PlayerController` (une sauvegarde incompatible sera refusée).
- **Nouvelle partie** conserve la confirmation d'écrasement du slot v2 et le refus
  d'écraser une session longue.
- **Charger une partie** ouvre un panneau de sélection du nom de campagne, du
  slot et du mode de sauvegarde (mode long toujours **opt-in**).
- **Options** et **Quitter** restent visibles dans le menu principal.
- **Choisir campagne / emplacement** et **Outils avancés** sont des points
  d'entrée secondaires. Le gestionnaire, la migration v1→v2, la copie v1/v2
  vers une session longue et les éventuelles démos restent accessibles.

La scène à droite utilise, si présent, le portrait embarqué
`sporebound/content/art/jeanne/jeanne_portrait.png`. Le décor du château est
également dessiné en primitives Canvas pour que le menu reste autonome,
notamment dans le cas d'un projet personnalisé et d'une installation sans
assets optionnels. Les textes de campagne proviennent de `GameProject`, pas
d'identifiants techniques.

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

**Gate manuel avant fusion :** inspecter en 800×580, 1160×820 et plein écran,
à 100/125/150 % et contraste renforcé ; confirmer la lisibilité du titre,
le focus clavier et la fermeture des panneaux, puis créer/charger une partie,
inspecter un slot avec sauvegarde de secours, tester un slot libre et valider
que les actions avancées ne se déclenchent jamais sans clic explicite.
