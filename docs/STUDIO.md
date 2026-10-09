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

## Studio avancé — graphe, archétypes et blocs

### Graphe des missions

L'onglet **Graphe des missions** lit et modifie exclusivement les champs
`Mission.next_missions` du contenu tactique. Les nœuds sont organisés
automatiquement en couches à partir de la mission d'entrée de la campagne
sélectionnée. Un nœud vert correspond à un départ, un nœud grisé à une
mission non accessible depuis celui-ci, un nœud jaune à la sélection.

Pour établir un lien, choisir la mission source, la destination puis
**Relier →** ; **Retirer lien** effectue l'inverse. **Afficher mission**
ouvre la mission source dans la vue de carte. L'inspection détecte les
cycles et les missions isolées sans altérer le contenu. Les modifications
sont validées et passent par Undo/Redo.

**Important :** les liaisons sont des déblocages après une victoire, pas
encore des choix exclusifs ou des transitions conditionnelles.
Une mission peut débloquer plusieurs successeurs. Un graphe cyclique
reste techniquement permis mais il est explicitement signalé.

### Bibliothèque de personnages et de monstres

L'onglet **Bibliothèque d'acteurs** utilise le registre
`Content.archetypes` et l'usine `ActorFactory` existants.

- **Créer archétype** définit une créature réutilisable avec type
  (character/monster/summon), PV, attaque, vitesse et mobilité.
- **Capturer unité** extrait les caractéristiques d'une unité existante
  et crée un archétype unique, sans ses valeurs transitoires de combat.
- **Placer sur carte** instancie un acteur sur la case sélectionnée.
- **Supprimer archétype** est interdit tant qu'une unité ou un événement
  y fait référence.

Une instance déjà placée est une copie validée des propriétés du modèle ;
les changements ultérieurs d'un archétype ne modifient pas implicitement
les personnages existants. Cette politique préserve les replays et
l'équilibrage historique.

### Événements par blocs

L'onglet **Événements par blocs** permet de composer un déclencheur
`tick`, `enter`, `defeated` ou `hp_below`, puis plusieurs actions
dans un ordre explicite. Les actions guidées proposées sont message,
danger, statut, spawn depuis un archétype et despawn. Les boutons
**Ajouter bloc**, **Supprimer bloc**, **↑** et **↓** manipulent une liste
locale jusqu'à **Valider événement**. La validation par `Content`
garantit que l'ensemble est accepté ou entièrement rejeté.

L'identifiant permet aussi d'éditer un événement déjà créé :
le sélectionner dans la liste, puis remplacer ses blocs. Les règles
plus avancées (vagues, conditions personnalisées, extensions modulaires)
restent accessibles par l'onglet JSON.

## Client joueur indépendant

```sh
python -m sporebound player
python -m sporebound player --content ./jeu.json --project ./jeu.game.json
python -m sporebound player --profile ./profils/ma_partie.game.json
```

Le player Tk fournit un écran titre autonome, le choix de campagne,
un sélecteur d'emplacements, un menu de missions débloquées et une
grille de combat. Les commandes de déplacement, attaque, compétences,
objets, orientation et déploiement passent par le même `Battle.execute`
que la CLI. Le bouton de tour IA emploie `play_activation`.

La progression est commise avec `Campaign.finish` une seule fois à la
fin d'un combat ; elle est alors sauvegardée atomiquement. Les slots
sont placés par défaut dans le répertoire de l'utilisateur plutôt que
dans les fichiers du package. **Nouvelle partie** demande une
confirmation avant d'écraser un slot déjà présent ; **Charger**
refuse un slot absent/corrompu sans remplacer la session précédente.

Un combat quitté avant son résultat est abandonné, pas enregistré
comme victoire. Les sauvegardes en plein combat nécessitent encore
l'API de replay distincte. Le player est fonctionnel, mais sa
présentation Tk reste volontairement sobre et sans assets audio/vidéo.

### Vérifications

```sh
python -m unittest discover -s tests_standalone -p test_studio_advanced.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_studio_advanced_gui.py -v
```
