# R45.A — Living Simulation & Economy : crafting canonique

**Statut : code proposé, R45 non certifié.** Ce lot complète les
fondations R35 (horloge, agendas, réputation, quêtes et commerce), sans
remplacer le futur R55 System Designer. R45.B Qt et R45.C restent à faire.

## ADR — source de vérité unique

- Le schéma déclaratif est la clé optionnelle `recipes` de
  `GameProject.extensions["org.drawtemp.livingworld"]["data"]`. Il conserve
  `version: 1` du document R35 : aucune migration silencieuse.
- Le joueur possède ses objets et sa monnaie uniquement dans
  `Campaign.inventory` et `Campaign.gold`, existants depuis R8.
- Le propriétaire de l'horloge, des agendas, des factions et de la traçabilité
  reste `LivingWorld`, détenu par `GameSession`.
- Aucun nouveau registre de stock/inventaire, aucune exécution de scripts,
  aucun RNG, aucune horloge murale ni modification des règles CT.
- La simulation hors-focus projette l'agenda R35 ; elle ne fabrique rien
  sans commande. L'économie simulée en continu appartient à un autre lot.

## Schéma facultatif `recipes`

Chaque recette contient exactement `id`, `npc`, `scene`, `activity`,
`faction`, `min_reputation`, `inputs`, `outputs`, `gold_cost` et
`daily_limit`.

- Identité unique ASCII, 1–64 caractères. PNJ, scène, faction et activité
  existants, avec arrêt d'agenda compatible.
- Les entrées et sorties contiennent chacune 1 à 8 éléments
  `{"item": "...", "quantity": 1}`. Les items existent dans les magasins
  R35 ou le catalogue `Content.equipment` R8.
- Chaque quantité est entre 1 et 99, sans doublon d'item par côté ni
  auto-consommation d'un même item dans une recette.
- Coût en or entier entre 0 et 1 000 000, limite quotidienne 1 à 1 000.
  Au maximum 128 recettes par document.

Exemple à ajouter au document LivingWorld de R35 :

```json
"recipes": [{
  "id": "brew_elixir",
  "npc": "merchant", "scene": "arrival", "activity": "trade",
  "faction": "guild", "min_reputation": 0,
  "inputs": [{"item": "herb", "quantity": 2}],
  "outputs": [{"item": "elixir", "quantity": 1}],
  "gold_cost": 4, "daily_limit": 2
}]
```

## Exécution, intégrité, replay

`GameSession.living_world_craft(recipe_id, quantity, transaction_id)`
exige une exploration active, aucun dialogue en attente, PNJ ouvert et
réputation suffisante. Elle valide les ressources, le budget quotidien et
la plage portable JSON (2^53-1) **avant** toute mutation. Elle modifie
atomiquement l'inventaire et la monnaie canoniques.

Le checkpoint R35 ajoute `crafts` seulement si `recipes` est présent :
`{transaction_id: {recipe, quantity, day, sequence}}`. Un même identifiant
réessayé avec des arguments identiques est un no-op, un réemploi avec des
arguments différents échoue. Les reçus sont bornés à 2048, triés sur
`sequence` et validés sur les jours, références et plafonds. Le digest
GameSession les protège. Une modification de recette exige une migration
explicite de projet et sauvegarde.

**Compatibilité :** un projet sans `recipes` ne reçoit aucune nouvelle
clé dans ses projections ou checkpoints ; il reste utilisable tel quel.

## Gates restant ouverts

- R45.B : auteur Qt Living Economy, calendrier/stock/recettes,
  previews, apply/Undo/Redo et tests onscreen.
- R45.C : village 7 jours achat→fabrication→vente, PNJ et conséquences,
  sauvegarde/replay, vrais parcours Player, clean-machine tri-OS,
  licence d'assets, mesures/acceptation utilisateur.
- Ce changement inclut des tests headless sur idempotence, bornes, rollback,
  passages de jour, falsification de reçus et sauvegardes héritées R35.
