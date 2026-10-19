# R35.A — Living World Clock et horaires PNJ (préliminaire)

**Statut : code en PR #339 ; non fusionné/certifié.** Basé sur la proposition R35.1/R35.2/R35.3/R35.10/R35.11 de la roadmap R31–R40 (#303). Ce lot n'implémente pas encore R35.B (factions, économie, quêtes), R35.C (debugger GUI, village complet), ni la validation UX/GPU.

## Contrat et sécurité

- Source unique d'auteur : `GameProject.extensions["org.drawtemp.livingworld"]`, enveloppe R24 `{"schema_version":1,"data":{...},"references":[]}`. Document v1 strict : `version=1`, `start_minute` (0–1439), `ticks_per_minute` (1–3600), `clock_policy="exploration_only"`, `npcs` (≤256).
- Chaque PNJ contient `id` et `schedule` (1–32 arrêts par jour, triés, minutes distinctes). Arrêt : `minute`, `scene` (référence à un contenu existant), `activity`, et optionnellement `when: {"flag": "market_open", "eq": true}`. La condition lit les flags canoniques de la campagne, sans script arbitraire.
- Tick **entier** : `day=(start_minute + ticks // ticks_per_minute)//1440`, `minute=(start_minute + ticks // ticks_per_minute)%1440`. Aucun delta de rendu ou horloge système. Un tick progresse avec `GameSession.route_realtime_step`, ou via `living_world_advance(n)` en mode campagne. Le temps **ne progresse pas** pendant les combats CT, événements autonomes ou à la seule ouverture du Player.
- Hors focus : projection déterministe de la dernière activité éligible à une minute donnée, en bouclant au dernier arrêt de la veille avant le premier de la journée. C'est une **approximation de présence/activité**, pas un pathfinding, une simulation continue ou une téléportation visuelle ; aucune promesse de convergence géométrique.
- Snapshot facultatif `living_world: {"version":1,"ticks":N}` intégré au **GameSession existant** et couvert par son digest, y compris sauvegarde/reprise et changement de zone. Sans extension, les anciens manifestes et checkpoints restent identiques. Un snapshot manquant, inconnu, invalide ou associé au mauvais projet est refusé.
- Limites : 256 PNJ, 32 arrêts/PNJ, incréments ≤1 000 000 ticks par appel, compteur ≤2⁵³−1. Lecture de tous les PNJ O(N × arrêts), avance horaire O(1). Ces bornes sont des garanties de complexité, pas des budgets de performances mesurés.

## Extrait d'auteur

```json
{
  "schema_version": 1,
  "data": {
    "version": 1,
    "start_minute": 479,
    "ticks_per_minute": 60,
    "clock_policy": "exploration_only",
    "npcs": [{
      "id": "merchant",
      "schedule": [
        {"minute": 0, "scene": "arrival", "activity": "sleep"},
        {"minute": 480, "scene": "arrival", "activity": "trade",
         "when": {"flag": "market_open", "eq": true}},
        {"minute": 1020, "scene": "arrival", "activity": "home"}
      ]
    }]
  },
  "references": []
}
```

La scène `arrival` doit exister dans `GameProject.exploration` ou dans les missions de `Content`. Les projets sont soumis à la validation canonique et les mutations éditoriales doivent passer par AuthoringSession.

## Vérification et suites

Exécuter : `python -m unittest tests_standalone.test_r35_living_world -v`. Cas : rollover minuit, condition de quête, projet versionné, sélection hors focus, corruption de checkpoint, absence d'extension et pause CT. **Ces tests ne remplacent pas** une certification de replay événementiel complète ou un run UI. Suivants : GUI Studio et édition transactionnelle des schedules, réputation R35.B, événements quotidiens idempotents, visualiseur temporel R35.C et VS-35.
