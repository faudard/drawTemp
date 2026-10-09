# Studio de jeu — PR #14

## Deux niveaux d'édition

Exécuter `python -m sporebound editor --content chemin/vers/contenu.json`.
Aucune dépendance graphique n'est importée par le runtime headless : Tk n'est
requis qu'au lancement du studio.

### Carte et mission

- **Carte vierge** : définir l'identifiant, le titre et les dimensions
  (4 à 128 cases). Une mission validée est créée avec un terrain vide,
  deux acteurs de référence (joueur et adversaire), sans objets ni triggers.
- **Nouvelle mission** : duplique la première mission existante pour fabriquer
  rapidement une variante complète.
- **Carte et combat** : peindre hauteur, murs, boue, couvert, danger,
  objectif et déplacer une unité sélectionnée. Undo / redo et playtest isolé.
- **Personnages et événements** : ajouter une unité par copie d'un acteur
  fonctionnel du même camp, placer des portes, coffres, interrupteurs,
  béliers, catapultes, passages, défenses et triggers simples.
- **Mission** : titre, type d'objectif, récompense et liste de missions
  suivantes. Les changements de progression sont validés avec les
  références de missions existantes.

Pour placer un acteur ou un objet, sélectionner d'abord une case de la carte,
puis remplir son formulaire. Les objets dépendants d'une porte demandent
l'identifiant d'une porte déjà placée. Pour un passage, saisir `x,y` comme
destination. Pour les événements, les conditions guidées actuelles sont
`enter`, `tick`, `defeated` et `hp_below` ; les actions guidées sont
`message` et `hazard`.

Toutes ces opérations transitent par `Content.from_dict` **avant** d'être
ajoutées à l'historique de l'éditeur. Une modification invalide ne remplace
pas le document actif. L'édition JSON reste disponible pour les règles
avancées, vagues de renforts, archétypes, actions combinées et détails
spécifiques aux objets.

### Jeu, campagnes et sauvegardes

Le nouvel onglet **Jeu, campagnes et sauvegardes** offre :

1. Titre, sous-titre, langue (`fr` ou `en`), volumes, plein écran et 1 à 9 slots.
2. Création de plusieurs campagnes, chacune avec nom, description et
   mission de départ ; la liaison entre missions se fait dans l'onglet mission.
3. **Aperçu écran titre** : un écran de garde Tk interactif avec Nouvelle partie,
   Continuer / jouer, Charger, Options et Quitter l'aperçu.
4. Nouvelle partie, chargement, jeu d'une mission via le moteur `Campaign.prepare`
   et `Battle`, et sauvegarde de progression dans un slot.
   À la victoire, `Campaign.finish` attribue XP, or et nouveaux déblocages,
   sans enregistrer le playtest isolé.

Le manifeste du jeu est sauvegardé dans un fichier `*.game.json` distinct
du contenu combat (`*.json`). **Enregistrer projet de jeu…** ouvre
un sélecteur de destination ; le document de combat dispose toujours de
**Enregistrer sous**. Les sauvegardes de progression sont stockées dans
`<projet-sans-extension>_saves/<campagne>/slot_N.json`, via l'écriture
atomique `Campaign.save` déjà existante.

Exemple minimal de manifeste :

```json
{
  "version": 1,
  "title": "L'assaut du château",
  "subtitle": "Une aventure tactique",
  "campaigns": [
    {
      "id": "main",
      "name": "La campagne principale",
      "description": "",
      "start_mission": "garden"
    }
  ],
  "options": {
    "language": "fr",
    "music_volume": 70,
    "effects_volume": 70,
    "fullscreen": false
  },
  "save_slots": 3
}
```

Le champ `start_mission` doit désigner une mission présente dans le contenu
chargé. `GameProject.validate` vérifie les types, identifiants, unicité,
références et bornes. Les noms de campagne sont limités à des identifiants
sûrs pour la création des chemins de sauvegarde.

## Garanties et limites actuelles

- Compatibilité : le schéma de `Content` v1, les sauvegardes de bataille
  et les replays ne sont pas modifiés.
- **Aperçu de menu**, et non moteur de menus commercial indépendant ;
  « Jouer campagne » utilise actuellement la vue tactique Tk de l'atelier.
- Les options de langue, audio et plein écran sont des **données de
  configuration éditables**, mais ne pilotent pas encore un renderer/audio
  runtime autonome.
- Les slots stockent la progression `Campaign` (personnages, XP, objets,
  déblocages), pas un instantané du milieu d'un combat. Pour sauvegarder
  un combat en cours, utiliser la fonction existante Sauver combat.
- Les missions de siège multi-fronts et leurs journaux v5 constituent
  encore un workflow séparé ; le manifeste ne les convertit pas.
- Le studio ne gère pas encore les assets graphiques, dialogues riches,
  cinématiques, graphe de campagne visuel ni bibliothèques d'archétypes
  avec édition complète de statistiques.
- Ne pas effacer ou renommer une mission déjà utilisée par une sauvegarde ;
  la lecture d'un slot refuse toute mission déverrouillée devenue absente.

## Tests et étapes suivantes

```sh
python -m unittest discover -s tests_standalone -p test_studio.py -v
python -m unittest discover -s tests_standalone -v
# Linux avec un écran Xvfb
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_editor_gui.py -v
```

Évolutions prévues, à faire séparément :

1. Vrai shell joueur autonome (écran titre → chargement → campagne → bataille
   → résultats → retour carte de campagne), sans widgets d'authoring.
2. Éditeurs de dialogue/cinématique, triggers complexes et vagues par blocs
   typés et graphe événementiel, avec prévisualisation déterministe.
3. Bibliothèque de personnages/monstres, archétypes, classes et inventaire ;
   palette d'assets, pinceaux paramétrables, sélection multiple et copier-coller.
4. Graphe de missions et campagnes avec conditions, embranchements, checkpoints
   et validation des impasses ; aperçu de progression.
5. Versionnement des sauvegardes de campagne avec identité de contenu,
   migrations, vérification des collisions de slots et autosave robuste.
