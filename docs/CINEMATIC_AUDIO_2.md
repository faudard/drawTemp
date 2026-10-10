# 2.9.1 — Audio Studio 2.0 : mixage et timeline de cinématiques

Ce chantier prolonge **Audio Studio 2.6** et **Cinematic Studio 2.9**.
Il ajoute au type d'événement cinématique `sound` des paramètres
**facultatifs**. Les projets existants et tous les anciens événements
`sound` (`cue` seul) restent valides.

## Studio

1. Créer une cinématique dans **Cinématiques**, ou cliquer
   **Exemple Jeanne** puis **Bande-son Jeanne**.
2. Sélectionner un événement sonore (`sound`) dans la liste ou la timeline.
3. Dans le panneau **Pistes audio**, choisir :
   - `music` : musique de scène, y compris thèmes qui se croisent ;
   - `ambience` : sons d'environnement qui peuvent se superposer à la musique ;
   - `voice` : narration/voix avec atténuation automatique des musiques ;
   - `sfx` : effets synchronisés avec les actions.
4. Ajuster **volume**, **fondu d'entrée / sortie** en millisecondes,
   **répéter**, et **ducking voix** (niveau résiduel de la musique en %).
5. Le champ **Acteur / voix / son** contient le **nom de déclencheur audio**.
   Créer son association à un vrai fichier WAV/OGG dans **Son & musique**,
   puis utiliser **Lecture complète** pour entendre la scène synchronisée.

Les enveloppes sont calculées au temps exact de lecture, indépendamment
de la fréquence du rendu Tk ; des pistes différentes jouent simultanément
sur des canaux pygame. Les pistes sans fichier associé sont silencieuses
et ne bloquent ni l'aperçu ni le Player.

## Exemple Jeanne (10 secondes)

| Intervalle | Bus | Déclencheur | Mise en scène |
| --- | --- | --- | --- |
| 0–10 s | music | `jeanne_theme` | Thème orchestré, fondu 1,4 s et 1,9 s |
| 0–8,2 s | ambience | `jeanne_wind` | Vent des champs en fond sonore |
| 1,5–5,9 s | voice | `jeanne_vision` | Voix de la vision, musique à 30 % |
| 8–10 s | ambience | `jeanne_fire` | Feu du village, fondu d'entrée et sortie |

Les quatre déclencheurs sont des placeholders optionnels : importer et
associer ses propres sons pour les entendre. Aucun média sous licence
n'est intégré au dépôt.

## Contrat JSON

```json
{
  "id": "jeanne_voice",
  "kind": "sound",
  "start_ms": 1500,
  "duration_ms": 4400,
  "cue": "jeanne_vision",
  "bus": "voice",
  "volume": 85,
  "loop": false,
  "fade_in_ms": 250,
  "fade_out_ms": 550,
  "duck_percent": 30
}
```

Les nouveaux champs sont optionnels ; `bus` défaut `sfx`, volume
défaut 100 %, fondus défaut zéro, boucle défaut faux, réduction
musique pendant la voix défaut 40 % (si `bus=voice`).
`duck_percent` n'est autorisé que sur une voix.

Le volume final = niveau de piste × enveloppe × volume maître.
Lorsqu'une voix joue, la musique est atténuée selon le pourcentage
résiduel défini, interpolé avec le fondu de la voix. Les effets
et les ambiances ne sont pas duckés.

## Comportement de lecture

- Le Player arrête la musique d'écran à l'entrée de la cinématique, puis
  rétablit celle du prochain écran à la sortie.
- **Pause / Lire** suspend et reprend les canaux de la cinématique.
- **Recommencer** remet le playhead à zéro et relance les événements.
- **Passer / fermer** arrête les pistes créées par la cinématique.
- Les anciens `sound` sans champs de mixage sont lancés une seule fois
  comme effets historiques, y compris au temps zéro.
- Une avance/saut temporel ne rejoue pas rétroactivement les anciens effets.
  Les boucles reprennent actuellement **au début du fichier audio** après
  un seek, sans repositionnement temporel PCM. Il s'agit d'une limitation
  connue du backend pygame.
- Le mix de cinématiques utilise des `pygame.mixer.Sound` chargés en RAM
  pour permettre des canaux superposés. Pour de longues pistes musicales,
  choisir des fichiers compressés courts/raisonnables ; le lecteur standard
  hors cinématique conserve le streaming `mixer.music`.

Les calculs et l'orchestration sont isolés dans
`sporebound/audio_timeline.py` sans Tk, son, fichier ou simulation.
Aucune modification du gameplay, des formats de sauvegarde de combat ou
de la sérialisation des anciens projets.

## Tests

```sh
python -m unittest discover -s tests_standalone -p test_cinematic_audio.py -v
python -m unittest discover -s tests_standalone -p test_cinematics.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_cinematics_gui.py -v
```
