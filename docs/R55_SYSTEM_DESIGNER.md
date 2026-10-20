# R55 — System Designer : économie, Studio et Player (développement)

Ce lot suit [R55 dans la roadmap R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).
Le **gate R55 reste ouvert** : le présent document distingue les API et tests
committés des preuves CI, UX, équilibre et certification encore manquantes.

## Source unique et contraintes

- Schéma versionné, opt-in : `GameProject.extensions["org.drawtemp.systems"]`
  avec enveloppe standard (`schema_version=1`, `data`, `references=[]`).
- `resources` (stock initial / capacité), `producers` (maps de ressources
  consommées/produites et intervalle), `merchants` (ressource, scène
  **d'exploration**, prix achat/vente), `quests` (livraison, flag).
- Aucun hook Python, exécution dynamique ni nouvelle monnaie/inventaire.
  `GameSession` possède l'économie ; `Campaign` possède toujours l'or,
  les objets et les flags de progression.
- Validation fail-closed : IDs distincts, références connues, montants
  entiers bornés, graphes de production acycliques, version stricte, budgets
  explicites. Les producteurs s'exécutent dans l'ordre des identifiants.
- Limites actuelles : au plus 64 ressources, 32 producteurs, 16 marchands,
  32 quêtes, 256 ticks par commande, 65 536 ticks par session et 512 entrées
  de journal. **Ces limites ne sont pas encore certifiées pour une longue
  campagne** ; l'extension reste expérimentale.

## Simulation et persistance

`GameSession.system_state()/system_preview()/system_advance()` exposent une
projection détachée et un pilotage explicite. Les déplacements fixes
`route_realtime_step()` (R25) et `route_platform_step()` (R32) avancent
désormais l'économie d'un tick par pas validé ; un mouvement refusé ne doit
pas modifier l'économie, le journal de déplacement ni la campagne.

Les ticks successifs sont fusionnés dans une entrée `advance` du journal :
600 frames de mouvement n'épuisent plus à eux seuls 512 reçus. Le chargement
rejoue les recettes à partir du stock initial et refuse un checkpoint altéré
(stock, tick, opération ou reçu invalide), y compris après recomputation du
checksum JSON. Les anciennes sauvegardes n'ont **aucune clé R55** et gardent
leurs contrats d'origine.

`GameSession.system_trade()` vérifie scène, stock, capacité, monnaie,
quantité et identifiant idempotent avant un changement atomique de
`Campaign.inventory` et `Campaign.gold`. `system_fulfill()` retire les
ressources réellement possédées et n'active le flag de quête qu'une fois.

Le journal R55 démontre la conservation **des stocks gérés par l'économie**.
Il ne constitue ni une signature cryptographique ni une preuve de tous les
mouvements d'or et d'inventaire provenant d'autres systèmes de jeu.

## Studio Qt (R55.B)

**Outils → System Designer R55** propose une vue de dépendances et quatre
onglets : ressources, ateliers, marchands et quêtes. Ajout, modification et
suppression se font avec des formulaires typés ; les producteurs acceptent
désormais plusieurs ports `ressource:quantité` séparés par des virgules,
**sans écrire de JSON**. Le graphe est validé dès la modification et une
projection affiche les deltas de stocks et manques.

Un clic **Appliquer au projet** passe par
`preview_system_design(AuthoringSession, ...)` puis
`apply_system_design(...)` : l'édition est atomique, contrôlée par révision,
compatible Undo/Redo et ne crée pas de base de projet parallèle.

## Player SDK et interface Qt Quick (R55.C en cours)

`drawtemp.sdk.simulation.Simulation` expose `system_state`,
`system_preview`, `system_advance`, `system_trade`, `system_fulfill`
avec projections immuables, contrôle de révision et rollback SDK.

Le contrôleur Player dispose des actions `system_wait`, `system_trade`
et `system_fulfill`. Pour les projets R55, le HUD Qt Quick affiche un
panneau de stocks, un bouton d'avance, les offres des marchands de la scène
et les livraisons de quêtes. Les reçus d'achat/vente créés depuis cette
interface utilisent un identifiant dérivé de la longueur persistée du
journal, jamais l'heure locale.

Les modes narratifs, combats CT et autres runtimes n'avancent **pas**
automatiquement les cycles. L'intégration dans toutes les boucles Player,
l'UX finale, la gestion des inventaires externes et les performances restent
à qualifier.

## Canvas Qt interactif — lot R55.B.2

Le Studio R55 dispose de nœuds sélectionnables et déplaçables : un clic sur
un nœud ouvre ses propriétés dans l'inspecteur synchronisé, tandis que
**Modifier la sélection** ouvre les champs typés existants. Déplacer un nœud
avec la souris ou les flèches déplace les liaisons à l'écran.

La création de liens se fait par **sortie verte → entrée bleue**, ou avec
**Relier des nœuds…** au clavier. Chaque liaison est normalisée par le
module headless `system_design_graph.edit_link` : ressource → atelier
(entrée), atelier → ressource (sortie), ressource → marchand/quête.
Une quantité bornée est demandée pour les liaisons d'atelier. Une référence
introuvable, un type de port incompatible, une quantité invalide ou un cycle
bloque le changement sans modifier le brouillon existant. Supprimer une
liaison ne peut pas détruire le dernier port obligatoire d'une recette.

**Annuler/Rétablir (brouillon)** et Ctrl+Z/Ctrl+Shift+Z restaurent les
modifications de ressources, de connexions et de disposition graphique, avec
un historique borné à 50 étapes. **Appliquer au projet** constitue ensuite
une transaction unique dans `AuthoringSession`; son Undo/Redo global
continue de fonctionner normalement.

**Portée** : les positions des nœuds sont une aide visuelle locale à
l'éditeur, et ne font pas partie du schéma économique versionné. Elles ne
sont donc pas persistées après fermeture ; aucun déplacement graphique ne
modifie le gameplay ni la sauvegarde de partie. Les connecteurs sont
créés par deux clics, pas encore par glisser-déposer continu.

## Vertical slice VS-55 proposé et testable

```sh
python -m examples.r55_micro_economy
```

L'exemple construit un projet canonique à deux régions via
`AuthoringSession`, avance les cycles avec des pas fixes, traverse la
frontière, achète deux lingots, livre une quête, sauvegarde et recharge.
Il vérifie que la même transaction et la même quête ne créent aucune
ressource/récompense supplémentaire après rechargement.

## Tests ajoutés

```sh
python -m unittest tests_standalone.test_r55_system_design -v
python -m unittest tests_standalone.test_r55_graph_links -v
python -m unittest tests_standalone.test_r55_player_sdk -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r55_system_design_gui -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.player.qt_app --smoke --reference
```

Workflow indépendant : `.github/workflows/r55-system-designer.yml`.
Les workflows GitHub ont été observés en état **failure avec zéro job** ;
aucune exécution des assertions n'a pu être confirmée. Aucun résultat
d'intégration, de performance p95/p99 ni de test GPU humain n'est revendiqué.

## Restant pour autoriser le gate R55

- Étendre le canvas nodal : déplacement, ports interactifs, clavier, lecteurs
  d'écran, interactions QTest et preuves UX de création sans JSON.
- Faire jouer le VS-55 dans le **Player réel** en GUI, y compris marchand,
  quête et deux zones, sous captures/goldens ; tester les exports propres.
- Mesurer l'endurance, les limites de ticks/reçus, la consommation CPU/RAM,
  le p95/p99 multi-seeds et les écarts d'équilibrage ; garantir les migrations
  et les saves anciennes.
- Exiger CI fonctionnelle sur le SHA final, validation de master, et décision
  explicite GO/REDUCE/NO-GO. R50, R55 et la release 10.0 ne sont pas certifiés.
