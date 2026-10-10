# Son & musique — Studio 2.6

drawTemp possède déjà `AssetRegistry` (assets portables) et `AudioStage`
(lecture pygame-ce facultative). L'onglet **Son & musique** les réutilise :
aucune règle de combat ni aucun format de sauvegarde n'est modifié.

## Utilisation

1. Ouvrir `python -m sporebound editor --content mon_jeu.json`.
2. Dans **Son & musique**, saisir un ID stable (par exemple `castle_battle`)
   et cliquer **Importer WAV / OGG…**. Le Studio copie le fichier vers
   `assets/audio/<ID>.wav` ou `.ogg`, à côté du manifeste `*.game.json`.
3. Choisir **Musique** ou **Effet**, sélectionner un déclencheur proposé
   (ou saisir son nom), choisir le son, puis **Associer au déclencheur**.
4. Tester avec **Écouter la sélection** et **Stop** ; utiliser
   **Vérifier les fichiers** avant d'enregistrer le projet.
5. Dans **Jeu, campagnes et sauvegardes**, régler les volumes puis
   **Enregistrer projet de jeu…**.

Le lecteur utilise le premier slot musical disponible dans chaque contexte :

| Contexte | Slot(s) utilisés |
| --- | --- |
| Écran titre | `title` |
| Carte de campagne | `campaign` |
| Combat normal | `mission_<mission_id>`, puis `battle` |
| Dialogue / scène | `music_scene_<scene_id>`, puis `campaign` |
| Entrée d'une scène | effet `scene_enter_<scene_id>` (une fois par entrée visible) |
| Événement de combat | effet nommé par `event["kind"]` |

Par exemple, la musique du siège de la mission `castle_gate` peut être
associée à `mission_castle_gate`, et le son d'arrivée dans la scène
`village_fire` à `scene_enter_village_fire`.

Les **ambiances** sont des sons mis en boucle via un slot musical. On peut
les utiliser pour le titre, une mission ou une scène ; le mixage de
plusieurs couches (musique + ambiance indépendante) n'est pas encore proposé.

## Fiabilité

- Seuls les fichiers `WAV` et `OGG` sont importés ; signature vérifiée.
- IDs uniques, chemins relatifs, pas d'écrasement de fichier existant et
  protection contre les chemins et dossiers symboliques sortant du projet.
- Délier avant de retirer un son utilisé. La suppression d'une entrée
  **ne supprime jamais les données sonores sur disque**.
- Le project JSON stocke seulement chemins et liaisons ; pas de données
  binaires en base64. Pour partager le jeu, inclure `assets/audio/`.
- La lecture dépend de `pygame-ce` (facultatif). Sans pygame, matériel
  audio ou fichiers valides, le gameplay reste jouable sans son.
- La sélection d'un son ne modifie ni les événements de combat ni les replays.

La préécoute est dédiée à un seul son à la fois. Le déclenchement des effets
narratifs est une responsabilité du Player UI et ne modifie jamais les choix,
flags, ou conséquences dans le moteur.

**Attention aux projets déplacés :** les chemins sont relatifs au manifeste
du jeu. En déplaçant le `*.game.json` vers un autre dossier, copier aussi
`assets/audio/` (et les autres fichiers d'assets). Le bouton Enregistrer sous
ne déplace pas automatiquement la bibliothèque.

## Tests

```sh
python -m unittest discover -s tests_standalone -p test_audio_studio.py -v
python -m unittest discover -s tests_standalone -p test_renderer_audio.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_audio_studio_gui.py -v
```
