# 3.5 — Direction artistique et présentation

## Décision d'architecture

Le **moteur tactique Python reste headless**. Les changements de règles,
positions, PV, CT, journal, aléatoire, sauvegardes et replays appartiennent au
moteur. La présentation consomme seulement des snapshots `BattleFrame`, les
événements déjà émis et le registre portable d'assets. Aucun renderer ni
tick visuel ne doit faire progresser le gameplay.

## 3.5.1 — Motion & sprites (première PR)

- `visual_motion.MotionDirector` interpole, sur une horloge injectable, les
  déplacements entre deux snapshots et reconnaît `move`, `attack`,
  `hit`, `defeat` et `idle`. Un re-dessin (sélection/zoom) ne
  réinitialise pas le mouvement.
- `animation_sprite_id` sélectionne des séquences du registre `animation`,
  en respectant leurs durées, boucles et références validées par
  `AssetRegistry`. L'absence d'asset conserve les formes vectorielles Tk.
- Le Player Tk consomme ces poses dans une boucle cosmétique à environ 16 Hz
  **uniquement** pendant un mouvement ou une animation idle explicite ;
  aucun tick tactique supplémentaire, aucune nouvelle dépendance.
- La version 3.5.1 **n'inclut pas encore les sprites finaux dessinés** ni une
  animation sur le chemin exact d'une unité : l'interpolation relie les deux
  positions observées. Les interfaces alternatives (dont Castle Player) sont
  à connecter ensuite au même contrôleur.

### Convention de bindings

Dans `assets` du manifeste `*.game.json` :

```json
{
  "version": 1,
  "entries": [
    {"id": "jeanne_front_1", "kind": "sprite", "path": "art/jeanne/front_1.png"},
    {"id": "jeanne_front_2", "kind": "sprite", "path": "art/jeanne/front_2.png"},
    {"id": "jeanne_walk_east", "kind": "animation", "loop": true, "frames": [
      {"sprite": "jeanne_front_1", "duration_ms": 110},
      {"sprite": "jeanne_front_2", "duration_ms": 110}
    ]}
  ],
  "bindings": {
    "animation": {"jeanne_move_east": "jeanne_walk_east"},
    "sprite": {"jeanne": "jeanne_front_1"}
  }
}
```

Résolution par priorité : `<unit-id>_<action>_<direction>`,
`<unit-id>_<action>`, `<team>_<action>_<direction>`,
`<team>_<action>`, puis variantes `idle`. Direction : north/south/east/west.
Actions : idle, move, attack, hit, defeat. Les fichiers PNG sont relatifs au
manifeste et validés par le registre existant. Les animations non bouclées
se figent sur leur dernière image. Les séquences idle peuvent boucler.

## Charte visuelle — Jeanne, univers original

- **Personnages** : tactical RPG 2D/2.5D lisible en vue légèrement plongeante ;
  silhouettes distinctes par classe, arme et posture. Jeanne possède une
  silhouette originale immédiatement reconnaissable : cheveux blonds, yeux
  bleus, armure de campagne et bannière, sans reproduire un design tiers.
- **Portraits** : variations neutre, déterminée, inquiète, colère, blessée et
  apaisée. Les traits et accessoires restent cohérents avec les sprites.
- **Décors** : champs de Domrémy, villages incendiés, forêts, ponts, hospice,
  Vaucouleurs, Orléans, remparts et intérieurs de château ; sols, hauteurs,
  couvertures et zones tactiques conservent un contraste fort.
- **Palette** : bleu acier, lin, pierre, bois et or désaturé ; feu et sang
  réservés aux alertes. Télégraphes de compétences, sélection et dangers
  priment sur le décor pour la lisibilité.
- **FX/audio** : impacts courts lisibles, arcs/trajectoires, magie discrète,
  ciel/particules d'ambiance, couches musique/ambiances/voix ; aucune
  synchronisation audio ne doit prendre le contrôle des commandes du moteur.

## PRs à venir

| PR | Fonctionnalité | Gate |
| --- | --- | --- |
| 3.5.2 | Sprites définitifs, atlas, directions et cycles attaque/marche | Jeanne, bandit, loup, écuyer : 4 directions et états cohérents |
| 3.5.3 | Portraits et expressions en dialogues / cinématiques | Expression déterministe liée à la scène, repli sans art |
| 3.5.4 | Tilesets et décors médiévaux 2.5D, niveaux/occlusion | 3 lieux distincts avec lecture tactique intacte |
| 3.5.5 | FX de compétences, indications de ciblage, transitions | Pas de décalage règles/effets, replay inchangé |
| 3.5.6 | Audio contextuel par timeline/événement et mixage | Stop/pause/skip, volume et absence de périphérique |
| 3.5.7 | Prototype comparatif Tk / pygame-ce / PySide6 | Mesurer p50/p95 frame, charge, mémoire, DPI et packaging ; décider ensuite |

## Gate 3.5

Une séquence Domrémy → route → combat → château présente un style cohérent,
des mouvements et expressions reconnaissables, des effets et du son facultatifs,
sans désynchronisation des états ou dégradation de la lisibilité.

Pour comparer les renderers, utiliser **le même jeu de `BattleFrame` figés**,
la même caméra, la même résolution et les mêmes fichiers ; tester de 20 à 200
acteurs, 3 densités de décor et 1x/2x DPI sur Windows, Linux et macOS.
Publier mesures reproductibles avant une éventuelle migration : ne jamais
réécrire `engine.py`, `Battle`, `GameSession` ni les schémas de sauvegarde.
