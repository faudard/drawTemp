# R66 — Simulation Designer Pro : contrat d'observation v1

**Statut : premier incrément R66.A et briques headless R66.B/C, en PR. Non certifié comme R66 complet.** La PR #289 fournit la vision multi-genres R25–R30 et **est déjà fusionnée** ; la définition R66 est dans `docs/DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md`.

## Portée livrée

- `drawtemp.sdk.r66_simulation_lab.validate_trace` : entrée JSON strictement versionnée (`schema=1`), horizon en jours/ticks entiers, liste de comptes, ressources et événements causaux déjà produits par un moteur ; dépendances vers événements antérieurs, bornes et identifiants contrôlés, opérations `produce`, `transfer`, `consume`.
- `SimulationTraceLab` : projection **séparée et non destructive**, `step`, `seek`, `rewind`, `snapshot`, `cancel`. Chaque déplacement de curseur est transactionnel ; les snapshots sont détachés et incluent les sommes créées/consommées et les contrôles de conservation. Aucun `GameSession`, `Replay` ou checkpoint du Player n'est remplacé ou édité.
- `analyze_batch` : inspection de traces multi-seeds déjà enregistrées, rapport JSON reproductible, SHA-256 déterministe du contenu, p95/p99 des **événements par jour** (pas des durées CPU !), alertes « jours inactifs consécutifs », surconsommation en échec explicite, annulation coopérative entre les traces.
- `compare_batches` : comparaison de rapports complets issus de mêmes seeds/horizon/ressources et détection des différences de stocks de clôture, du p99 d'activité et des fenêtres d'inactivité. Les empreintes servent à détecter des divergences accidentelles, **pas à authentifier cryptographiquement** la provenance.

## Format d'entrée minimal

```json
{
  "schema": 1,
  "seed": 17,
  "days": 1,
  "ticks_per_day": 24,
  "accounts": {"farm": {"food": 1}, "village": {"food": 0}},
  "events": [
    {
      "id": "delivery-1", "tick": 3, "kind": "transfer",
      "resource": "food", "quantity": 1,
      "source": "farm", "target": "village",
      "depends_on": [], "cause": "market-delivery"
    }
  ]
}
```

**Conservation :** `stock_final = stock_initial + produced - consumed` pour chaque ressource, transfert à somme nulle, aucune quantité négative ni overflow de l'audit. Les dépendances sont un DAG implicite en ordre d'événements, sans exécution ni scripting. Le SHA canonise l'entrée analysée, et non une sauvegarde. Bornes : 64 comptes, 16 ressources, 20 000 événements par trace, 32 seeds, 365 jours.

## Reproduire le slice VS-66 de contrat

```bash
python -m unittest tests_standalone.test_r66_simulation_lab -v
```

Le test fournit des **traces synthétiques de 30 jours**, trois seeds, production/transferts/consommation, une variante de rendement et une plage d'inactivité. Il prouve la projection déterministe, la conservation, les garde-fous et l'A/B local. Il **ne simule pas encore** 30 jours avec l'économie du jeu ; aucun rapport de performance réelle CPU/GPU/Studio ne peut être déduit des tests.

## Reste à réaliser avant gate R66

1. R66.A : raccorder un exporteur **en lecture seule** à la simulation canonique R55/R61–R63, après certification des contrats disponibles sur `master` ; vérifier les événements économiques/PNJ réels et leur causalité.
2. R66.B : brancher le Studio Qt au modèle de trace, contrôles step/rewind, inspecteur d'événements et paramètres ; conserver l'Undo/Redo éditorial sur l'`AuthoringSession`, jamais sur le journal Player.
3. R66.C : campagnes 30 jours **réelles** sur plusieurs seeds, détection de softlocks par invariants métier (au lieu de seuls jours sans événements), mesures p95/p99 de temps d'exécution et budgets mémoire sur CI, sauvegarde/reprise/replay inchangés, go/no-go.

Le terme `idle_windows` est une **heuristique de diagnostic** : absence d'événement n'est pas une preuve de blocage. La correction de paramètres revient à l'auteur dans le Studio et nécessite une nouvelle simulation canonique, non la réécriture d'un replay historique.
