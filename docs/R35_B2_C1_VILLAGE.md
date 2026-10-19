# R35.B2 / R35.C1 — Boutique canonique, village vivant et timeline de diagnostic

**Statut : code proposé dans la PR d'intégration #339, non certifié sur master.** R35.B2 complète R35.A/B1 ; R35.C1 fournit l'API de création R1 et une prévisualisation temporelle *headless*. **R35.C2 ajoute un premier éditeur Qt interactif des horaires PNJ** depuis Outils → Monde vivant, avec ajout/suppression de PNJ, arrêt, activité, condition, preview, apply/Undo/Redo. Les déplacements PNJ géométriques, l'économie avancée, la météo, le crafting et la revue utilisateur restent à faire.

## Format de boutique (GameProject.extensions)

Ajouter `shops` dans `data` de l'extension `org.drawtemp.livingworld` :

```json
"shops": [{
  "id": "village_shop",
  "npc": "merchant",
  "scene": "arrival",
  "activity": "trade",
  "faction": "guild",
  "min_reputation": 0,
  "items": [
    {"id": "herb", "buy_price": 7, "sell_price": 3, "daily_stock": 5}
  ]
}]
```

- Maximum 32 boutiques, 32 articles par boutique ; id NPC/lieu de scène/activité/faction doivent se résoudre depuis les données canoniques. Le marchand doit avoir au moins un arrêt horaire `trade` dans la scène de la boutique.
- La disponibilité exige à la fois : scène du joueur active, PNJ présent à la bonne activité, réputation suffisante, aucune cinématique/rencontre/dialogue tactique en cours.
- `GameSession.living_world_trade("village_shop", "herb", "buy", 2, "purchase_01")` utilise le portefeuille `Campaign.gold` et `Campaign.inventory`. `"sell"` rachète des objets au tarif `sell_price`, sous la limite de stock `daily_stock`. La transaction ne modifie rien si fonds, stock, inventaire ou réputation sont insuffisants.
- Le stock est réinitialisé **par jour du WorldClock**, pas par sortie/retour de scène. Stock courant = quota journalier - quantités achetées + quantités revendues le même jour ; il reste compris entre 0 et `daily_stock`.
- L'identité `transaction_id` est persistante et idempotente : même commande → `False`, aucune nouvelle récompense ; réemploi avec des arguments différents → refus. Nombre de reçus borné à 2 048 ; leur chronologie, prix et stock sont validés à la reprise. `GameSession.recording()` garde les reçus uniquement si le projet déclare des boutiques. Chaque reçu contient un numéro de séquence explicite, indépendant de l'ordre des clés JSON. La signature SHA256 des sauvegardes détecte les altérations accidentelles, **elle n'est pas une authentification cryptographique**.
- `daily_stock` est un quota déterministe de réapprovisionnement chaque jour, sans RNG ni temps système. Les objets utilisent les IDs d'inventaire déjà présents ; les prix sont des entiers en or et ne constituent pas une économie dynamique complète.

## Diagnostic et authoring

- `GameSession.living_world_timeline(scene="arrival", limit=512)` retourne les changements de routines PNJ et ouvertures/fermetures de quêtes du jour courant, triés et limités (1 à 2 048 entrées par page, indicateur `truncated`). Le rapport marque `preview_only=true` : il projette les flags *actuels*, ce n'est pas une preuve historique d'exécution ou un journal de simulation.
- `drawtemp.studio.living_world_authoring.preview_living_world(authoring_session, document, expected_revision=...)` crée un plan de modification du vrai `GameProject.extensions` : validation canonique des références, refus des modifications invalides et révisions périmées. `apply_living_world(authoring_session, preview)` intègre la modification à l'historique R1 Undo/Redo, sans créer un deuxième registre de PNJ ou une base parallèle.
- L'éditeur Qt `drawtemp.studio.living_world_qt.LivingWorldDialog` édite les heures, lieux, activités et conditions, en réutilisant l'unique `AuthoringSession` du Studio. Le panneau de timeline projette les horaires avec les flags de quête absents : ce n'est pas un débogueur du replay historique du Player. Tests Qt hors écran : `tests_standalone/test_r35_village_qt.py`.
- Le scénario de régression `tests_standalone/test_r35_village.py` contient quatre PNJ, une boutique, deux changements horaires pour le marchand, une quête liée à la réputation, une transition campagne→CT→campagne et le contrôle des reçus après restauration.

## Validation attendue

```bash
python -m unittest tests_standalone.test_r35_living_world tests_standalone.test_r35_factions_quests tests_standalone.test_r35_commerce tests_standalone.test_r35_village -v
python -m unittest tests_standalone.test_r25_scene_router tests_standalone.test_r25_fixed_realtime tests_standalone.test_game_session -v
```

Le workflow `.github/workflows/r35-living-world.yml` exécute la matrice Linux/Windows/macOS. **Ne pas passer le gate R35 au vert** avant réussite des tests du SHA intégré et contrôle UX/Player réel : les raffinements de l'éditeur Qt (drag-and-drop temporel, animation de scrubbing, flags runtime), les PNJ navigant réellement, stocks multi-boutiques avancés, crafting, profiling et le vertical slice produit final ne sont pas certifiés ici.
