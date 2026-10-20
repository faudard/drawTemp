# R77.A — Exploratory QA headless (développement, NO-GO)

La [roadmap R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md) demande
des agents bornés, couverture, traces, diagnostic de softlocks et aucune
modification des données auteur. Ce premier lot travaille **uniquement** sur
les scènes R26 `ActionRuntime` déjà implémentées.

## Exemple reproductible

```python
from drawtemp.quality.r77_exploratory import explore_action_scene

scene = {
    "id": "tiny_quest", "width": 5, "height": 5, "walls": [],
    "hero": {"pos": [1, 2], "hp": 10},
    "enemies": [], "objects": [],
}
report = explore_action_scene(
    scene, goals=[[3, 2]], seeds=(1, 2, 3),
    ticks_per_seed=128, state_budget=20000,
)
assert report["runtime_replay_verified"]
assert not report["release_certified"]
```

Les seeds sont des entiers non négatifs distincts (maximum 8 et 32 bits).
Le budget est limité à **512 ticks par seed**, **4096 ticks au total**, et
**200 000 états** pour l'analyse R29.B ; toute demande hors limites échoue.
Le rapport inclut le hash de la scène, la configuration, les zones et
conditions traversées, les actions, les events du runtime, la trace complète
par seed, le hash de chaque trace, le hash d'état final, les exceptions et
le replay vérifié par le runtime canonique.

## Interprétation stricte

- `partial` : exploration bornée et rejeu réussis, sans preuve d'exhaustivité.
- `abstract_softlock_risk` : l'exploration statique R29.B trouve une impasse
  dans **son abstraction** de déplacement et d'inventaire. La trace
  `static_preflight.counterexamples` aide à reproduire, mais ne prouve pas
  un softlock dans le Player réel.
- `inconclusive` : budget du solveur statique épuisé. **Ne signifie pas** absence
  de softlock.
- `runtime_exception` : une exception ou une divergence de replay a été
  observée ; lire `failures`, `runs[].trace` et la dernière commande.

Aucun fichier auteur n'est écrit. Les scènes sont copiées et hachées avant
et après les rollouts. Les commands sont exécutées par le vrai
`ActionRuntime.step`, sans double moteur. La preuve de stabilité est produite
par `ActionRuntime.from_recording`.

## Tests

```bash
python -m unittest discover -s tests_standalone -p 'test_drawtemp_r77a_exploratory.py'
```

Les tests ciblent le trajet libre, la clé puis porte, la porte sans clé,
le rejeu depuis les commandes, l'entrée auteur inchangée et les entrées
malformées. **Une syntaxe valide ou une CI sans jobs n'est pas une validation
d'exécution** ; la PR reste en brouillon si la CI est bloquée.

## Limites / suite

La couverture de zones/conditions/actions est expérimentale et dépend des
seeds et des budgets ; elle ne mesure ni chemins de quêtes ni conditions de
StoryGraph. Les ennemis sont simulés par le vrai R26, mais les preuves R29.B
sur les puzzles ne couvrent pas leurs tactiques. Les collisions dynamiques,
saves GameSession, transitions, tous les genres, faux positifs, QTest Qt,
comparaison Studio, GPU réel et tests humains **ne sont pas certifiés**.

R77.B : interface Exploration Lab (heatmaps, navigation et comparaison de
versions, validation humaine). R77.C : campagne quatre genres, fuzz
save/transition, minimisation de contre-exemples, preuves SHA/CI et
correctif d'un softlock injecté avant certification.
