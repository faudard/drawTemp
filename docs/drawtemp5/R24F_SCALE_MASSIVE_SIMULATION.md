# R24.F — Renderer CPU Scale & Massive Simulation Lab (R24.6/R24.7)

> **Proposition en PR empilée après R24.E (#344)**. Ce lot ajoute un outil de mesure reproductible et des améliorations prudentes. Il ne clôt PAS R24.6/7 dans leur définition GPU/performance de production, et ne certifie aucune release 6.0.

## 1. Simulations multi-seeds : un seul Battle canonique

`drawtemp.sdk.r24f_mass_lab.MassiveSimulationJob` réutilise **sporebound.battle_lab.run_lab**, l'IA existante et `Battle.replay`. Aucune copie de logique de combat, aucun moteur parallèle, aucune donnée narrative modifiée.

Le créateur spécifie une mission du Content v1, 1..128 seeds unsigned distinctes, 1..1500 commandes max par seed, et un budget total de 1..50000 commandes. Le job est **synchrone et piloté par appels `step()`**, avec une seed complète par étape. `cancel()` demande une interruption **entre** deux seeds, jamais au milieu d'une activation du Core ; la simulation déjà vérifiée reste consultable dans un rapport marqué `cancelled`, sans `passed` frauduleux.

Chaque étape reconstruit le Battle via R13, exécute l'IA du produit, rejoue le journal, vérifie son digest et conserve les distributions issues du moteur : victoires/défaites/draw/limites, ticks/commandes, résultats, actions, journaux et événements. Un `Content` source est copié et fingerprinté ; les règles restent identiques d'une seed à l'autre.

**Deux types de métriques sont distincts :** le résultat *déterministe* (digest des samples natifs, règles et Content) et le temps *observé sur l'hôte* (wall p50/p95/p99, process CPU p50/p95/p99, par seed). La comparaison `compare_massive_runs()` compare les digests/résultats à charge identique ; elle n'utilise jamais les temps CPU pour prouver une divergence de gameplay.

### API

```python
from drawtemp.core import Content
from drawtemp.sdk import MassiveSimulationJob, compare_massive_runs

content = Content.load('drawtemp/creator_examples/asterion.json')
job = MassiveSimulationJob(content, 'signal_depot',
                           seeds=(1, 17, 221), max_commands=50)
while not job.finished:
    step = job.step()  # un Battle + replay authentique par appel
    # Entre deux steps : éventuellement job.cancel()
result = job.report()
```

## 2. Renderer scale : même R3, pas de GPU inventé

`drawtemp.quality.r24f_scale.profile_cpu_renderer()` construit des scènes synthétiques à 32×32, 64×64 et 128×128, zooms 24/54/96 px et 0..80 acteurs. Il utilise exactement `TileChunkIndex`, `Camera`, `IsoProjection` et `render_items` existants, comme les clients Qt Studio/Player.

Mesures : construction index, rendu CPU des éléments visibles (p50/p95/p99, temps mesurés), nombre de chunks/index, limite de 20 000 enregistrements visibles par défaut, invalidation incrémentale d'une case, update sans changement, restauration et hash des éléments affichés. Aucun renderer alternatif, changement de gameplay ou promesse sur la durée d'un `frameSwapped`.

Une petite optimisation dans `TileChunkIndex.update` retourne immédiatement lorsque les données d'une scène n'ont pas changé, sans recréer l'index d'élévations : amélioration mécanique ciblée pour les rafraîchissements de caméra.

`compare_cpu_scale()` refuse les scénarios, les données visibles ou les environnements différents sauf override explicite. Il peut appliquer une tolérance de dégradation p95 CPU, mais **n'est pas un gate GPU**, pas un certificat de 60 FPS et ne mesure ni upload de textures, VRAM, Qt RHI, ni compositing hardware.

## 3. CLI headless

```bash
# Exemple complet : Asterion + 9 profils CPU
python -m drawtemp.quality.r24f_cli --mode both --seeds 3 --command-limit 16 --report r24f.json

# Campagne de 32 seeds ; sortie unique sans écrasement
python -m drawtemp.quality.r24f_cli --mode battle --seeds 32 --command-limit 100 --report battle-32.json

# Renderer seulement, 128x128, 80 acteurs
python -m drawtemp.quality.r24f_cli --mode renderer --sizes 128 --zooms 24 54 96 --actors 80 --samples 10 --report r3-cpu.json

# Annulation simulée après 2 seeds : retour 3 et rapport cancelled
python -m drawtemp.quality.r24f_cli --mode battle --seeds 10 --cancel-after 2 --report cancelled.json

# Deux captures dans une classe machine stable : tolérance p95 CPU 50 % par défaut
python -m drawtemp.quality.r24f_cli --mode both --baseline r24f.json --report r24f-next.json
```

**Codes retour :** 0 = mesures sans régression détectée ; 1 = échec ou données invalides ; 2 = régression mesurée ; 3 = volontairement annulé. Les chemins d'entrée/baseline ne peuvent être utilisés comme sortie. Les rapports existants ne sont pas écrasés.

## 4. CI et statut de preuve

```bash
python -m unittest tests_standalone.test_drawtemp5_r24f tests_standalone.test_drawtemp5_r13 tests_standalone.test_drawtemp5_r3b
```

Linux Python 3.10/3.12 ; Windows/macOS Python 3.12 ; tests de profils sur les trois tailles et trois zooms et sim R13 sur plusieurs seeds. Les budgets d'exécution ne sont pas imposés comme des SLA absolus cross-OS : les chiffres dépendent de la charge CPU. Les comparateurs valident strictement la forme, la parité déterministe et refusent les régressions artificiellement injectées.

Pour clore R24.6 et R24.12, il faut encore **des captures hardware réelles** selon `drawtemp.quality.r14.validate_gpu_profile` : minimum 120 frames par taille/zoom, nom du GPU/driver/backend Qt, résolution, p95/p99, VRAM mesurée, tests DPR/occlusion et qualité d'image approuvés. Le profil CPU R24.F n'est qu'une baseline logicielle de la même architecture.

## 5. Limitations

- Annulation coopérative entre seeds seulement. Une seed individuelle peut encore durer le temps autorisé par son cap en commandes, sans watchdog de thread/processus en R24.F.
- Pas de parallélisme automatique : la reproductibilité repose sur `run_lab` séquentiel et canonique.
- Un rapport `cancelled` ou `partial` est un diagnostic, jamais une preuve de gate complet.
- Les métriques et fichiers R24.F n'altèrent ni GameProject ni GameSession, et aucune donnée de test ne devient une nouvelle source de gameplay.
- Les résultats hardware et la performance à 60 FPS seront validés séparément sur un SHA consolidé dans R14/R24.12.
