# R77.A–B — Exploratory QA et Exploration Lab (développement, NO-GO)

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

R77.C : campagne quatre genres, fuzz sauvegardes/transitions, preuves SHA/CI,
correction d'un softlock injecté et certification après validations réelles.

## R77.B — Exploration Lab Qt et inspection headless

Le menu **Studio → Outils → R77 • Exploration Lab (R26)** et l'atelier
**Analyse** donnent accès à un dialogue de lecture seule. Charger **un
fichier JSON de scène ActionRuntime R26 existant** (≤256 Kio) ne convertit pas
automatiquement les scènes d'exploration R25 ni les missions CT en scènes R26.

Parcours : choisir une scène R26 → fixer les cellules objectif (`x,y;x,y`)
et les seeds → choisir les budgets → **Exécuter l'exploration**. L'interface
présente :

- Heatmap d'occupation par tick, fenêtre de 24×24 cellules navigable pour
  les scènes jusqu'à 128×128 ; chaque cellule indique visites et seeds.
- Parcours par seed et timeline des commandes/ticks exécutés, plus des chemins
  critiques issus du BFS statique R29. Ces chemins abstraits **ne sont pas
  nécessairement exécutables dans le Player**.
- Liste des constats et annotations humaines explicites (`suspected_false_positive`,
  `needs_investigation`, `reproduced_manually`, `accepted_risk`).
  Ces qualifications sont conservées uniquement en mémoire, ne modifient
  pas le projet et ne produisent aucun badge de certification.
- **Geler comme référence**, puis charger une seconde version de la scène
  et relancer : comparaison de couverture et de visits par cellule. Seules
  scènes de même ID et mêmes dimensions sont comparées. La différence de
  SHA indique si les sources ont changé ; il faut conserver les seeds/budgets
  équivalents avant d'interpréter une différence comme une régression.
- Liens vers les ateliers Cartes / Graphes **uniquement si un identifiant
  de ressource Studio correspond exactement à l'ID de la scène importée** ;
  identité du nom ne vaut pas preuve de parité du contenu.

Le modèle headless `drawtemp.quality.r77_lab.build_lab_view` **recalcule**
les preuves R77.A depuis la source détachée et rejette toute incohérence avant
de produire une heatmap. `minimize_runtime_failure` réduit par suppression de
commands une exception R26 **reproductible**, sous budget (≤64 tentatives),
sans prétendre produire une séquence globalement minimale. Les risques R29
fournissent leurs témoins BFS séparés. Le rapport R77.A enregistre désormais
l'ordre exact des objectifs dans `config.goals` pour une vérification fidèle
même avec plusieurs sorties.

### Vérifications ciblées

```bash
python -m unittest discover -s tests_standalone -p 'test_drawtemp_r77a_exploratory.py'
python -m unittest discover -s tests_standalone -p 'test_drawtemp_r77b_lab.py'
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests_standalone -p 'test_drawtemp_r77b_qt.py'
```

QTest offscreen valide les commandes et interactions de ce dialogue seulement.
Une revue **onscreen** (clavier, accessibilité, DPI) reste nécessaire. Un bouton
« ouvrir carte » absent/disabled signifie qu'aucune ressource Studio reliée par
ID n'a pu être établie. Les rapports ne sont pas écrits sur disque par le
dialogue, ne sont pas exportés et n'attribuent jamais `release_certified=True`.

**Gate toujours NO-GO :** campagne quatre genres (R77.C), fuzz
save/transition, inspection manuelle de faux positifs, sessions longues,
CI sur les plateformes et preuve d'un bug corrigé sur SHA final manquent.
