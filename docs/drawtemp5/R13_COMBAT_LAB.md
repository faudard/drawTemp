# DrawTemp 5.0 — R13 Combat Design & Balance Lab

## Périmètre livré sur cette branche

Le lot R13 s'appuie exclusivement sur les règles `sporebound.engine.Battle`,
`Content`, `Campaign` et les commandes d'IA existantes. Il n'introduit ni
second moteur, ni nouvel état de sauvegarde, ni sérialisation parallèle.

| Lot roadmap | Preuve / point d'accès | État sur cette branche |
| --- | --- | --- |
| R13.1 Tactical Intent | `inspect_encounter` → `tactical_intents` : charges possibles, sorts engagés, réactions armées, timeline CT conditionnelle | Adaptateur R13 livré, projections existantes réutilisées |
| R13.2 Coordinated AI | `sporebound.coordinated_ai`, diagnostics de décisions réellement exécutées | Comportements existants réutilisés, pas de nouvelle stratégie |
| R13.3 Formations | Projections d'escouade/formation de `tactical_intents` et formations du moteur | Observation livrée, IA existante |
| R13.4 Terrain & Floors | `inspect_encounter` expose hauteur/couvert/obstacles/étages; IA de liaison existante | Inspection livrée, pas de nouvel algorithme |
| R13.5 Boss & Elite | Les ordres et télégraphies de boss existants restent exécutés dans `Battle` | Réutilisation, intégration Qt spécifique à compléter |
| R13.6 Encounter Designer | Fenêtre Qt autonome, grille avec objectifs et unités, édition X/Y par unité et simulation d'une variante isolée par Balance Matrix | Première passe fonctionnelle; édition de tous les équipements/objectifs visuels non terminée |
| R13.7 Battle Simulation | `simulate_encounter`, replay vérifié sur chaque seed, métriques de CT/commandes, export headless | Livré |
| R13.8 Visual Battle Lab | Tableau des seeds + chronologie des commandes et positions depuis `trace_seed` réellement rejoué | Première passe Qt ; graphiques avancés à compléter |
| R13.9 Balance Regression | `compare_encounters`, seeds appariées, seuils configurables, dérive de digest et inputs explicitement signalés | Livré |
| R13.10 Human Playtest | `human_review` réutilise des rapports locaux **opt-in**; aucune activation implicite | Analyse disponible, vrais playtests et taille d'échantillon requis |
| R13.11 Campaign Balance | `campaign_review` réutilise la progression et la courbe XP/économie/équipement du moteur | API livrée, parcours de campagne à certifier |

L'interface Qt 6 est un **outil autonome provisoire** : elle ne prétend pas
être déjà branchée sur le Studio final R2 ni sur un Player Qt R12 terminé.
La carte est **un schéma orthogonal d'analyse**, pas le rendu isométrique commun
prévu au jalon R3. Aucune simulation ne représente la durée humaine réelle.

## Utilisation

Tests unitaires sans Qt :

```sh
python -m unittest tests_standalone.test_drawtemp5_r13 -v
```

Rapport R13 headless, première seed diagnostiquée :

```sh
python -m drawtemp.sdk.r13_cli \
  --content sporebound/content/core.json --mission garden \
  --seed-start 1 --runs 4 --limit 120 --trace --report r13-before.json

# Exécuter à nouveau avec le contenu modifié et les mêmes paramètres
python -m drawtemp.sdk.r13_cli \
  --content sporebound/content/core.json --mission garden \
  --seed-start 1 --runs 4 --limit 120 \
  --baseline r13-before.json --report r13-after.json
```

Une comparaison qui échoue quitte avec code **2**. Les entrées invalides
produisent une erreur et quittent avec code **1**. Les métriques de durée
restent des **ticks CT** et nombres de commandes.

Ouvrir la fenêtre Qt 6 (Python 3.12 et `pip install ".[qt6]"`) :

```sh
python -m drawtemp.studio.r13_workbench \
  --content sporebound/content/jeanne.json
```

Dans l'onglet **Encounter Designer**, les colonnes X/Y proposent une variante
temporaire. Le bouton de simulation valide et teste cette variante via
`balance_matrix.run_matrix()`; ni le fichier de contenu, ni la partie, ni les
sauvegardes ne sont modifiés. Dans **Battle Lab**, choisir le nombre de seeds,
lancer les simulations, consulter la timeline et charger un ancien JSON
Battle Lab pour voir les régressions. Le fichier exporté contient des
preuves `battle_lab` et la trace de la première seed.

API headless :

```python
from drawtemp.sdk.r13_combat_lab import (
    inspect_encounter, evaluate_variant, simulate_encounter,
    trace_timeline, compare_encounters, human_review, campaign_review,
)
```

## Gate R13 : ce qui est vérifié / ce qui reste ouvert

- **Vérifié par les tests nouveaux** : projection non destructive, variante
  validée par le modèle canonique, simulation reproductible, traces de commandes
  et replays, JSON, détection de dérive à inputs identiques, incompatibilité
  de seeds et référence non vérifiée.
- **Couvert par la suite historique** : IA coordonnée, formations, boss,
  hauteurs/étages, Balance Matrix, Battle Lab, playtests humains et campagne.
- **Non certifié à ce stade** : qualité tactique ressentie, courbes de difficulté
  de tous les chapitres Jeanne, minute réelle sur un échantillon humain,
  accessibilité/revue visuelle multi-OS de Qt, intégration finale au Studio
  et au Player, édition graphique complète des objectifs/équipements, et
  qualification des dépendances R1/R12 sur `master`.

La réussite de la CI est nécessaire mais ne valide pas à elle seule les
critères qualitatifs du gate R13. Tout changement d'inputs dont la simulation
reste dans les seuils doit tout de même passer par revue humaine; le champ
`human_signoff_required` le signale explicitement.

### Données de playtest

La télémétrie humaine n'est collectée que si l'utilisateur l'a activée dans
le Player historique. La fenêtre R13 peut importer un rapport JSON local
et produit des agrégats; aucune collecte automatique ni envoi réseau n'est
déclenché par ce lot.
