# Game Studio 4.0 — 3.3 (intégration incrémentale)

La PR #53 met en cohérence les éditeurs existants, sans troisième manifeste.
La PR #51 (graphe stratégique et preuves tactiques) est déjà intégrée dans `master`.

## Livré : Workspace unifié (3.3.1)

Dans `python -m sporebound editor --content sporebound/content/core.json`,
l'onglet **Espace projet** propose :

1. Recherche instantanée (identifiants, titres, résumés ; insensible aux accents).
2. Inventaire des **nœuds stratégiques** par siège et des **cinématiques**
   en plus des cartes, campagnes, scènes, personnages et assets.
3. Références **→ utilisées** et **← utilisées par** ; double-clic pour ouvrir
   directement la ressource liée dans son éditeur spécialisé.
4. Diagnostics agrégés (assets introuvables/invalides, scènes sans entrée connue,
   cinématiques vides). Les références structurées sont d'abord validées par
   les validateurs existants de `Content` et `GameProject`.

Il s'agit d'une **projection à lecture seule** : aucune nouvelle donnée de jeu
persistante et aucune suppression ou mutation lors d'une recherche.

## Livré : export de jeu source (socle 3.3.6)

Depuis le Workspace, utiliser **Exporter le jeu en ZIP**. La même opération
existe sans interface graphique :

```sh
python -m sporebound export \
  --content sporebound/content/core.json \
  --project sporebound/content/core.game.json \
  --output /tmp/mon-jeu.zip
```

Le ZIP contient `run_game.py`, `game/content.json`,
`game/project.game.json`, tous les assets **référencés**,
les fichiers sources de `sporebound`, `README.txt` et un
`export_manifest.json` avec empreintes SHA-256. Après extraction :

```sh
python run_game.py
```

L'interpréteur **Python 3.10+** et l'environnement graphique restent requis.
Ce ZIP n'est pas un exécutable natif/une distribution installable. Les fichiers
de sauvegarde ne sont pas inclus et les fichiers du workspace restent intacts.
Un asset manquant, un format incorrect ou un chemin non portable bloque
l'export **avant** le remplacement atomique de la destination.

## À compléter avant de lever le Draft

| Jalon | Gate |
|---|---|
| 3.3.2 | Événement tactique prouvé des remparts → effet porte → scène ; conditions ET/OU/NON, journal et rejeu |
| 3.3.3 | Parcours guidé de 3 missions, déploiement, siège, fronts, ressources et deux routes |
| 3.3.4 | Déclenchement scénique/cinématique/audio vérifiable et synchronisé |
| 3.3.5 | Playtest et Undo/Redo transversaux, diagnostics sans ambiguïté entre plusieurs éditeurs |
| 3.3.6 | Export + lancement réel d'une campagne multi-fin avec sauvegarde et reprise |

**Gate global non encore satisfait** : produire entièrement depuis le Studio,
sans éditer de JSON, une campagne jouable de trois missions, deux embranchements,
plusieurs personnages, un siège, des cinématiques et deux fins.

## Tests

```sh
python -m unittest discover -s tests_standalone -p 'test_game_studio4.py' -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover \
  -s tests_standalone -p test_workspace_gui.py -v
```
