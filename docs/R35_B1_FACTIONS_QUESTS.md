# R35.B1 — Factions et quêtes quotidiennes persistantes

**Implémentation incrémentale sur la PR d'intégration #339, pas de gate R35 certifié.** Complète R35.A sans changer la base de données tactique, le renderer ni le format historique.

Le document `org.drawtemp.livingworld.data` admet désormais, en plus des champs R35.A, les listes optionnelles `factions` (0–64) et `daily_quests` (0–128). Exemple :

```json
{
  "factions": [{"id": "guild", "initial": 0}],
  "daily_quests": [{
    "id": "delivery", "faction": "guild", "min_reputation": -10,
    "start_minute": 480, "end_minute": 1000,
    "completion_flag": "delivery_day",
    "reward_gold": 10, "reputation_delta": 3
  }]
}
```

Les tableaux ci-dessus sont **ajoutés au document `data` de R35.A**, pas des documents séparés. Toutes les heures sont des minutes 0..1440, la plage de quête est [début, fin) et ne traverse pas minuit dans cette version.

- `GameSession.living_world_reputation_event("guild", 5, "helped")` applique une fois une modification de réputation bornée à [-100,100]. Même ID/même effet : non-opération ; même ID/effet différent : erreur explicite. Les reçus (maximum 2048) sont sauvegardés dans le checkpoint du monde.
- `GameSession.living_world_finish_daily_quest("delivery")` vérifie la plage horaire, le seuil de réputation, l'absence de récompense déjà délivrée au jour courant et **la preuve dans les flags de campagne** : `progress.story_flags["delivery_day"]` doit être un entier égal au jour courant. Ce flag doit être posé par un événement de quête canonique, non par la simulation. La récompense s'ajoute à `Campaign.gold`; la réputation et le dernier jour récompensé sont sauvegardés dans le même `GameSession`.
- Les mutations sont vérifiées avant écriture afin d'éviter les récompenses partielles. La lecture `living_world_state` expose la réputation et l'état `ready/claimed_today` par quête. L'état reste déterministe pour un checkpoint identique, sans timer système.
- Les NPC et sauvegardes d'un projet ne déclarant pas ces nouveaux tableaux continuent d'utiliser la forme R35.A ; les anciens projets sans extension restent inchangés.

**Tests ajoutés :** `python -m unittest tests_standalone.test_r35_factions_quests -v`. Vérifier aussi `tests_standalone.test_r35_living_world` et la régression GameSession/CT. **Limites :** pas encore de GUI auteur de réputation/quêtes, pas de magasin/stocks/achats, pas de validation sur machine propre, pas de replay intégral des événements de faction ou des transitions quotidiennes. Ces points restent nécessaires à R35.B/C et au gate VS-35.
