# R1.C — SDK workers (R1.9) : simulation et validation hors UI

> Tranche additionnelle de **R1 — Tactical Core & Game SDK 5.0**.
> Ne certifie ni R1 dans son ensemble, ni les migrations R1.6, ni la
> distribution autonome R15. Aucune dépendance PySide6/Tk n'est ajoutée.

## Contrat d'exécution

`drawtemp.sdk.workers.SdkWorkQueue` est une frontière Python headless
au-dessus des interfaces canoniques `Simulation` et `AuthoringSession`.
Le Studio Qt garde la propriété de ses documents et le droit de commit.
Le worker ne voit qu'une **copie** de `Content/GameProject` ou du moteur
`GameSession`; il ne sauvegarde pas de fichier et n'émet aucun signal Qt.

| Opération | Thread propriétaire (normalement GUI) | Worker |
| --- | --- | --- |
| `submit_authoring(session, transform)` | Copie le snapshot, sa révision et les options | Prévisualise et valide la paire Content/GameProject canonique |
| `submit_simulation(simulation, max_steps=...)` | Copie l'état moteur et capture la révision | Simule les activations IA déterministes, borne de 1 à 1000 |
| `progress(ticket)` | Lit un compteur thread-safe `(fait, budget)` | Publication après chaque activation |
| `cancel(ticket)` | Invalide immédiatement le ticket, appelle `Future.cancel` | Arrêt coopératif aux points de contrôle |
| `poll(ticket)` | **Non bloquant** : `None` ou résultat terminal, consommé une fois | Aucun accès au handle live |
| `session.apply(result.payload)` | Commit explicite de l'AuthoringPlan réattaché, recontrôle la révision | Jamais exécuté |

`poll` répond avec `WorkResult(status=...)` :

- `ready` : snapshot de simulation ou `AuthoringPlan` utilisable.
- `stale` / `stale_revision` : le handle a changé depuis l'envoi (y
  compris après edit → undo → même contenu). Aucun plan n'est renvoyé.
- `cancelled` : annulation demandée ou confirmée; aucun plan n'est renvoyé.
- `failed` : erreur structurée `error_code` / `message`, par exemple
  `invalid_edit`, `invalid_budget`, `invalid_callback` ou
  `worker_failed` pour une exception inattendue.

Un ticket consommé n'est plus réutilisable; les tickets d'une autre queue,
les appels depuis un autre thread et l'envoi après `close()` lèvent un
`WorkQueueError(code, message)`. `close()` est idempotent et n'attend pas
sur le thread UI. Il ne peut pas interrompre brutalement une fonction Python
arbitraire : une transformation d'authoring longue doit rester pure et, si
elle boucle longtemps, proposer ses propres points d'annulation.

## Exemple Qt Widgets (adaptateur de présentation seulement)

```python
from drawtemp.sdk.workers import SdkWorkQueue

queue = SdkWorkQueue(max_workers=2)  # construit sur le thread GUI
ticket = queue.submit_authoring(
    studio_session,
    lambda content, project: ({**content, "name": "Nouveau nom"}, project),
    kind="project-edit",
)

# Dans le slot déclenché par QTimer, **sur le thread GUI** :
result = queue.poll(ticket)
if result is None:
    pass  # ne pas bloquer la boucle d'événements
elif result.ready:
    studio_session.apply(result.payload)  # revérifie la révision
elif result.status == "stale":
    pass  # rafraîchir puis recalculer, ne jamais appliquer
else:
    pass  # afficher le code/message, sans mutation du modèle
```

Le `transform` ci-dessus est illustratif; dans la vraie application, il
doit produire une paire réellement valide selon `validate_pair`. Les
transformations doivent être pures (ne jamais capturer un QWidget, un
`AuthoringSession`, un QObject ou un handle moteur vivant dans leur closure).
Les modifications de modèle/sauvegarde sont toujours effectuées par le
propriétaire du document, jamais par le worker.

## Simulation directe et hooks de progression

`Simulation.simulate(max_steps=N, cancelled=fn, on_progress=fn)` conserve
son comportement synchrone par défaut. Les nouveaux hooks sont facultatifs :
`cancelled()` est interrogé au début puis à chaque activation; `on_progress`
reçoit `(steps_completed, max_steps)`. Si annulé, l'erreur structurée
`SimulationError(code="cancelled", operation="simulate")` est levée
sans modification du moteur vivant. Les hooks sont invoqués sur le
**thread d'exécution** : ne jamais y toucher directement aux widgets Qt.
`SdkWorkQueue` utilise ces hooks pour publier une progression interrogée
depuis le GUI.

## Garanties, limites et suivi

- Pas de nouveau schéma, de migration de fichier, de format de sauvegarde ou
  de RNG supplémentaire. Les copies exécutent le code original de
  `GameSession`, `AuthoringSession` et `Simulation`.
- Les événements, progressions et previews de Qt doivent être relayés par
  l'adaptateur UI; aucune `Future.result()` bloquante n'est nécessaire.
- Annuler empêche la **publication** d'un plan, pas l'exécution d'effets de
  bord qu'un transform mal écrit effectuerait lui-même.
- Les `StateSnapshot` restent immuables. Aucun résultat en retard ne
  modifie le document, même si le calcul termine après la fermeture du Studio.
- La charge CPU et le temps de deepcopy dépendent de la taille de la session;
  **aucun budget de latence GUI n'est certifié** par cette tranche.

Tests :

```bash
python -m unittest tests_standalone.test_drawtemp5_r1_workers -v
python -m unittest tests_standalone.test_drawtemp5_r1 tests_standalone.test_drawtemp5_r1_authoring -v
python scripts/audit_drawtemp5.py --check --strict
```

Pour le gate R1 intégral restent à certifier : R1.6 migrations explicites,
R1.7 relecture étendue multi-fronts, R1.8 slots/backups/restauration Player,
et R1.10 stabilité contractuelle, exemples et politiques de compatibilité.
