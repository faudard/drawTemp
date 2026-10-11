# Game Studio 4.0 — 3.3.4 : Cinématiques et audio des scènes

Ce jalon raccorde les cinématiques **existantes** de Game Studio au
`StoryBook` du Player de siège. Il ne remplace ni `MultiFrontSession`, ni le
moteur `CinematicFrame` / `CinematicAudioDirector`, ni les règles tactiques.

## Édition sans JSON

1. Créer un événement stratégique authentifié (ex. le levier de herse sur
   `walls` applique `open_door` à `gate`), puis lier ce nœud à une
   scène via `Scénario & dialogues` (3.3.2).
2. Sélectionner la scène narrative et cliquer sur
   **Cinématique de cette scène…**, qui ouvre la timeline et préconfigure
   un nouveau clip si la scène n'en possède pas encore.
3. Définir **Déclenchement = scene** et **Campagne / mission = ID de scène**,
   puis dessiner les pistes visuelles (fond, personnage, caméra, dialogue,
   fondu) et les pistes sonores existantes (music, ambience, voice, sfx).
4. Réutiliser le catalogue des assets et le preview du Studio. Les cues
   sonores sont des IDs du système AudioStage ; leur liaison aux fichiers
   se fait dans Audio Studio.
5. Sauvegarder le `*.game.json`. Les changements sont validés par
   `GameProject` ; une scène cible supprimée rend le projet invalide.

## Exécution déterministe

- Après le véritable événement de combat, les effets inter-fronts sont
  appliqués, le StoryBook choisit la scène, puis le Player affiche la
  cinématique liée **avant** les options de dialogue.
- Chaque scène peut posséder plusieurs clips ; ils sont lus dans leur
  ordre d'auteur, un à la fois. Le bouton « Passer la cinématique » est
  équivalent à la fin de lecture ; il n'effectue **aucun choix narratif**.
- Une cinématique n'est jouée qu'une fois par partie. Si elle est
  interrompue par une fermeture avant sa fin ou son saut explicite, elle
  recommence au début lors de la reprise. Une fin ou un saut est
  enregistré **immédiatement dans le slot de siège**.
- La nouvelle version **3** du journal narratif ne s'applique **que**
  si le projet a un trigger `scene`. Elle journalise explicitement les
  acknowledgements `{kind: cinematic, scene, clip, at}` et l'ensemble
  des clips lus. Le replay rejette les confirmations forgées, répétées,
  anticipées, hors scène ou inversant l'ordre des pistes.
- Les anciens projets sans clip de scène gardent leurs journaux
  narratifs v1 ou v2 ; le digest `project_digest` empêche de relancer
  silencieusement d'anciennes sauvegardes contre de nouvelles règles.
- La piste audiovisuelle est purement présentation ; l'absence de carte
  son ou d'un fichier audio optionnel ne doit pas altérer l'issue tactique.

## Gates

```sh
python -m unittest discover -s tests_standalone -p test_scene_cinematics.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover \
  -s tests_standalone -p test_scene_cinematics_gui.py -v
python -m unittest discover -s tests_standalone -v
```

Le parcours de régression fait jouer une **interaction authentique** avec le
levier des remparts, ouvre la porte du front non chargé, lance deux clips
successifs (panoramique, texte, musique et trompette), saute le premier,
recharge la partie au milieu du second, reprend le dialogue, puis vérifie
les flags de Jeanne et le replay complet. Une sauvegarde falsifiée doit être
refusée.

**Reste à développer :** le grand gate 3 missions / 2 embranchements /
2 fins alternatives, la gestion de longues timelines en jeu et les
améliorations de synchronisation lip-sync. Ce jalon ne prétend pas
avoir terminé Game Studio 4.0.
