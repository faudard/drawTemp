# R45.C — Village marchand : vertical slice de sept jours

**État :** incrément de code livré sur branche empilée dans la consolidation
R31–R55. **Gate release R45 non certifié** tant que CI et QA réelle ne sont
pas validées. Ne pas fusionner directement dans `master`.

## Exécuter la démonstration

Générer une paire **Content / GameProject** indépendante des tests :

```bash
python -m drawtemp.sdk.r45_market_village --output /tmp/drawtemp-r45 --gate
python -m drawtemp.player.qt_app \
  --content /tmp/drawtemp-r45/market-r45.json \
  --project /tmp/drawtemp-r45/market-r45.game.json \
  --campaign main
```

Le Player Qt Quick affiche, dans l'écran d'exploration, le panneau **MARCHÉ DU
VILLAGE · R45** : or, stocks/marchands, inventaire, recettes, activités
PNJ, livraisons quotidiennes et bouton **Prochain matin · 08:00**.

Par journée : acheter **2 herbes** et **1 élixir** au marchand, fabriquer
**1 élixir** chez l'artisan, livrer **1 élixir** à la guilde, revendre
**1 élixir** au marchand, puis passer au lendemain. Le rachat d'un élixir
libère la capacité du marchand avant de revendre une unité : la règle
`daily_stock` de R35 n'est jamais ignorée.

| Mesure | Début | Après 7 journées |
|---|---:|---:|
| Or Campaign | 100 | 184 |
| Réputation guilde | 0 | +7 |
| Livraisons quotidiennes uniques | 0 | 7 |
| Reçus d'achat/vente | 0 | 21 |
| Reçus de fabrication | 0 | 7 |

Les journées 1–7 représentent les jours moteurs `0..6`; le dernier saut
de calendrier atteint `world.day == 7`, à 08:00.

## État canonique et garanties

- `GameProject.extensions[org.drawtemp.livingworld].data.starting_gold`
  est **optionnel**, entier `0..100000`. Sans ce champ, le moteur
  conserve le capital initial historique de 0.
- Les quêtes R35 historiques conservent leur schéma. **Option opt-in R45** :
  la paire stricte `delivery_item` et `delivery_quantity` (`1..99`),
  toujours référencée au catalogue R8 ou au stock R35, active une
  livraison d'objet. Une livraison idempotente vérifie simultanément
  fenêtre horaire, réputation, quantité possédée, limites d'or/réputation
  et état du jour, puis consomme l'objet, paie et marque la quête
  **en un commit atomique** dans Campaign + ledger R35 existants.
- Les achats et fabrications passent par `Simulation._apply` et par
  `GameSession`. Le Player calcule des identifiants de transaction uniques
  depuis les ledgers canoniques, **pas** depuis sa révision UI (qui
  recommence à zéro après un chargement).
- Les stocks et plafonds se régénèrent par jour dans le calcul R35/R45.
  L'horloge est purement logique et ne dépend ni du FPS QML, ni de
  timers d'arrière-plan. Les PNJ hors focus restent projetés depuis
  le même calendrier.
- Les sauvegardes passent exclusivement par les slots R17/R1 existants.
  Le runner enregistre et recharge **à chaque jour**, teste les reçus
  rejoués, traverse la zone `outskirts` au quatrième jour, et
  poursuit la semaine sans duplication.

## Vérification

```bash
python -m unittest \
  tests_standalone.test_r45_market_village \
  tests_standalone.test_r45_crafting \
  tests_standalone.test_r35_commerce \
  tests_standalone.test_r35_factions_quests -v

QT_QPA_PLATFORM=offscreen python -m drawtemp.player.qt_app \
  --smoke --smoke-scene exploration \
  --content /tmp/drawtemp-r45/market-r45.json \
  --project /tmp/drawtemp-r45/market-r45.game.json \
  --campaign main
```

La workflow R35 couvre les tests headless sur
Ubuntu/Windows/macOS et le smoke Qt Quick sur Ubuntu.

## Gate restant à produire (critères de sortie R45)

- Résultat CI réussi sur le SHA final (headless + Qt)
- Démonstration manuelle complète au clavier et à la souris :
  survol, navigation clavier, contraste, textes, DPI, fenêtre réduite
- Démonstration matérielle Player et sauvegardes sur Windows, Linux,
  macOS, avec captures traçables et comparaison après crash/reprise
- Vérification des licences des assets et du paquet export R39
- Validation UX de l'auteur dans Studio Qt et calibration des prix ;
  le Balance Lab R45.9 et la météo/saison R45.8 sont encore **ouverts**

**Ne pas confondre :** preuve headless de la semaine déterministe
≠ certification multi-OS GUI/Player/export ni validation de la release 8.5.
