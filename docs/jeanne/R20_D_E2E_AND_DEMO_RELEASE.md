# R20.D — Jeanne Acte I : acceptation de bout en bout et démo locale

> Statut : **intégration de tests E2E et préparation de paquet**, pas
> certification de release. Le jeu autonome distribué au public exige encore
> une preuve réelle d'exécution, les droits des ressources, des retours
> utilisateurs et une approbation explicite.

## 1. Parcours authentiques, du début à la fin

```bash
# Tous les quatre parcours, avec journal JSON local
python scripts/certify_r20d_jeanne.py --report r20d-acceptance.json

# Réduire à un parcours pendant le développement
python scripts/certify_r20d_jeanne.py --case otages_poursuite
```

Le script crée une **vraie nouvelle GameSession** sur
`jeanne.json` + `jeanne.r20c.game.json`. Il n'injecte jamais
`progress.completed`, `progress.story_pending` ou `battle.result`.
Chaque parcours traverse les champs, les visions, le village en feu,
les deux routes alternatives du prologue, **la jonction réelle vers
`sc_a1_camp`**, la forêt, le pont, l'hospice, le dilemme et la
mission finale Vaucouleurs.

Les personnages se déplacent par commandes cardinales validées
(`Exploration.move`), examinent les hotspots obligatoires, sauvent
éventuellement les civils et choisissent les options permises par
`StoryBook`. Les batailles sont jouées par commandes réelles
`GameSession.execute(choose_command(...))` jusqu'à une vraie
victoire moteur, sans raccourci de script. Le combat est sauvé/rechargé
alors qu'il est actif ; la bataille, les récompenses et les scènes
sont vérifiées de nouveau sur les checkpoints du moteur.

L'acquittement des cinématiques de scène est également effectué via
`GameSession.acknowledge_scene_cinematic`, sans pouvoir changer
les résultats tactiques. Le script vérifie les suites archives/otages,
les scènes d'épilogue, trois conclusions distinctes et l'absence de
mission laissée ouverte par accident.

| Parcours | Prologue | Compagnon | Choix d'acte | Conclusion |
|---|---|---|---|---|
| `archives_secours` | Secours | Étienne | Archives, copie scellée | Preuves |
| `otages_poursuite` | Poursuite | Agnès | Otages, protection | Témoins |
| `foi_secours` | Secours | Agnès | Otages, dépositions | Libre arbitre |
| `archives_poursuite` | Poursuite | Étienne | Archives, publication | Preuves |

**Résultat :** rapport `r20d-jeanne-headless-acceptance`, statut par
parcours, combats et nombre de commandes, scènes, cinématiques
acquittées, preuve de round-trip des sauvegardes. En cas de chemin
bloqué ou de défaite, le script retourne un code non nul et conserve
l'erreur. Un succès marque **le test headless** comme passé, jamais
`release_certified`.

## 2. Démo locale indépendante de Studio

Le Creator R15 accepte une paire
`jeanne-act1.json` + `jeanne-act1.game.json`, **pas**
`jeanne.json` + `jeanne.r20c.game.json` directement comme
paire d'export. Le script d'assemblage gère cette adaptation
sans modifier les fichiers de travail :

```bash
python scripts/prepare_r20d_jeanne_demo.py dist/jeanne-act1-dev
python -m drawtemp.player.qt_app \
  --content dist/jeanne-act1-dev/jeanne-act1.json \
  --project dist/jeanne-act1-dev/jeanne-act1.game.json \
  --campaign jeanne
```

Les sprites/portraits référencés sont copiés **sans path traversal**,
avec validation du manifeste via `AssetRegistry` et `preflight`.
La démo produite en mode développement inclut un rapport
`r20d-preflight.json` avec `release_certified: false`.
Il est interdit d'écraser une cible déjà présente.

## 3. Export natif : droits et preuves obligatoires

```bash
python scripts/prepare_r20d_jeanne_demo.py dist/jeanne-act1-native \
  --native-runtime build/native-player \
  --r14-report reports/r14-complete.json \
  --license-manifest reviewed/asset-licenses.json
```

- Le runtime doit être **un véritable binaire natif déjà construit**.
  Le script appelle `drawtemp.export.r15.export_game` puis
  `verify_bundle` et n'émule aucun exécutable.
- Le rapport R14 doit être **complet et vérifié** ; fournir un fichier
  de remplissage ne permet pas de franchir le gate.
- Tous les fichiers d'assets doivent être couverts par
  `asset-licenses.json`. Le dossier Jeanne ne contient pas de
  manifeste de licences redistribuables aujourd'hui : **export natif
  intentionnellement bloqué** jusqu'à revue juridique/artistique.
  Un manifeste renseigné ne remplace pas l'avis humain sur les droits.
- La création d'un bundle natif avec manifest SHA-256 constitue une
  preuve de **préparation/intégrité** ; seule une revue machine propre,
  offline, GPU, audio, options/sauvegarde et retours joueur pourra
  lever le gate de distribution R20.14.

## 4. CI et statut honnête

- Linux/macOS/Windows × Python 3.10/3.12 :
  validation de l'assemblage portable et refus de publication sans
  runtime/R14/licences.
- Quatre jobs Linux dédiés, **neuf combats réels par chemin**,
  journaux JSON conservés comme artefacts même en échec.
- Smoke Qt Linux en mode **offscreen** sur les vrais fichiers
  cinématiques de scène, pas un test GUI on-screen ni GPU certifié.
- Les tests précédents R20.A/B/C/C.1 restent requis, de même que
  les workflows de distribution et les contrôles système R14–R16.

Ce travail ne clôt **ni R20.11** (audio/licences), **ni R20.13**
(zéro softlock utilisateur au-delà des chemins testés), **ni R20.14**
(démo distribuée et approuvée). Ces cases doivent rester en
**`blocked`** dans tout rapport Go/No-go en l'absence de leurs preuves.
