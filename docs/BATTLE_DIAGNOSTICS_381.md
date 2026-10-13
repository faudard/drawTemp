# 3.8.1 — Combat Diagnostics et replay par seed

Extension du [Battle Lab 3.8](BATTLE_LAB_38.md). Le Laboratoire permet
désormais d'examiner **les décisions réellement exécutées** au lieu de
déduire la cause d'une défaite d'un seul agrégat.

## Depuis le Studio

1. Ouvrir **Battle Lab**, choisir mission, seeds et plafond de commandes.
2. Lancer **Simuler** puis **sélectionner une seed** dans le tableau.
3. Cliquer sur **Diagnostiquer seed**. Le moteur re-simule sur la *même
   copie du contenu et les mêmes règles* qui ont servi au rapport original.
   Le digest final et l'issue doivent correspondre au rapport initial, sinon
   le diagnostic est refusé.
4. Dans le lecteur, parcourir chaque commande avec ◀/▶ ou sélectionner
   sa ligne. Examiner positions par niveau, PV, CT, déplacements, effets
   et objectifs. Sélectionner un constat pour accéder au pas concerné.
5. Le bouton **Ouvrir la mission dans la carte** revient à la carte d'authoring
   canonique sans y injecter l'état diagnostiqué.

Le lecteur actuel est une **vue schématique 2D**, pas une nouvelle
implémentation du moteur ni une scène Player en temps réel. Il montre les
positions et points de contrôle des unités ainsi que les changements des objets.
Son objectif est le diagnostic reproductible, non la certification graphique.
La conservation intégrale de la commande et des événements moteurs prime sur
l'apparence. Les combats comportant plusieurs niveaux affichent le niveau de
chaque unité dans la liste, même en cas de superposition visuelle.

Le format d'équilibrage `battle_lab` v1, les fixtures CI existantes,
les règles, l'état d'une partie enregistrée et les données d'authoring
restent **inchangés**. Le détail est recalculé **à la demande**, pour
éviter de grossir chaque rapport multi-seeds.

## CLI reproductible

```sh
python -m sporebound battle-diagnostics --mission garden --seed 42 \
  --limit 500 --report diagnostic_seed_42.json
```

Sortie console compacte : issue, digest, nombre de décisions et constats.
Le fichier JSON contient les états initiaux, toutes les commandes exécutées,
les événements associés, l'état après chaque commande, la preuve de replay,
la signature du contenu et le manifeste de règles. Le nombre de commandes
traçables est plafonné à **5 000** pour éviter les rapports/UI incontrôlables.

## Signaux détectés

| Code | Preuve mesurable | Ce que cela ne prouve pas |
|---|---|---|
| `repeat_idle` | Une même unité finit plusieurs activations sans autre commande | Une erreur IA : un défenseur peut volontairement attendre |
| `zero_effect_heal` | Un événement `heal` restaure exactement 0 PV | Que le choix était illégal ou que le soigneur devait agir autrement |
| `failed_cast` | Le moteur émet `cast_failed` | Que l'IA savait anticiper le futur état |
| `command_budget` | Le maximum de commandes est atteint sans résultat | Un deadlock : il peut manquer quelques activations |
| `no_progress_window` | En fin de simulation non résolue, aucun PV, déplacement, objet ou objectif n'a changé pendant la fenêtre | Un soft-lock confirmé |

Ces alertes sont des **hypothèses vérifiables**, avec seed, acteur, pas
et éléments justificatifs. Aucun diagnostic ne pilote les commandes.
Un échec de déterminisme interrompt la capture au lieu de produire une
trace crédible mais différente de la simulation initiale.

## Gates

```sh
python -m unittest tests_standalone.test_battle_diagnostics_381 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_battle_diagnostics_381_gui -v
```

Comparer `run_lab(...)` et `trace_seed(...)` sur même mission, seed,
budget et règles : résultat, nombre de commandes et digest doivent
être identiques. Toute trace doit aussi être vérifiée par
`Battle.replay()`, sans mutation du `Content` fourni.
