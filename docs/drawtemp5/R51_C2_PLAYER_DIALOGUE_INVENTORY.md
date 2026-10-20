# R51.C2 — Player : dialogues et inventaire personnalisés réels

**20 octobre 2026 · lot isolé depuis `master` · certification R51 toujours NO-GO.**

### État de base

- `master` contient le contrat de layouts R51.A, le Designer Qt R51.B et
  les menus/focus/jauges R51.B2.
- La PR #411 (premier lot R51.C : a11y/rights/export) a été **fermée sans
  fusion**, et la branche de consolidation temporaire a été supprimée.
  Ce lot R51.C2 repart donc du `master` réel et **ne prétend pas** contenir
  les modifications non fusionnées de #411.
- Ce lot se concentre sur un manque produit vérifiable : remplacer la
  présentation de dialogue et ouvrir un inventaire tactique personnalisé
  sans remplacer le Core, contourner la sauvegarde ou inventer un état.

### Implémentation

1. **Schéma versionné conservé** : nouveaux chemins de binding stricts,
   `dialogue.title`, `dialogue.speaker`, `dialogue.text`,
   `dialogue.progress` (str) et `inventory.item_count` (int).
   Aucun code auteur n'est évalué. Les valeurs viennent de l'unique
   `PlayerController.state()` et de sa `Simulation/GameSession`.
   Le `GameProject` continue d'utiliser `org.drawtemp.ui` v1 ;
   les anciens layouts restent valides.
2. **Nouveaux templates Studio** : un écran `DIALOGUE` modèle avec quatre
   champs de lecture et `dialogue.advance` ; un `INVENTORY` avec total
   d'objets et `inventory.close`. Le Designer conserve ses transactions
   `preview/apply` et Undo/Redo.
3. **Runtime dialogue** : `drawtemp/player/r51_screens.py` vérifie
   `screen=="dialogue"`, lit les textes de la scène réelle, injecte les
   seuls scalaires déclarés, et n'active `dialogue.advance` que sur une
   réplique effectivement disponible sans cinématique bloquante.
   L'action appelle `PlayerController.next_dialogue_line()` : révision,
   autosauvegarde et replay restent R1. **Les choix narratifs continuent
   d'être rendus et arbitrés par les composants historiques** ; aucune
   branche narrative ne peut être inventée par le designer.
4. **Inventaire tactique** : panneau superposé construit avec le même
   `R51Layout.qml` que dans le Studio, et une liste des quantités
   existantes du vrai inventaire `Battle`. L'utilisation recontrôle
   le tour du joueur, la présence de l'objet et délègue à
   `PlayerController.use_item()`, sans second stock. Fermer/Échap
   ne modifie aucune commande ni aucun save. Le HUD CT peut ouvrir
   ce panneau si un `INVENTORY` est présent ; bouton natif de secours.
5. **Repli sûr** : projet legacy, écran absent ou contexte invalide
   conservent l'UI traditionnelle. L'inventaire de campagne/équipement
   et le HUD d'action ne sont pas revendiqués comme substitués.

### Tests proposés (non considérés comme exécutés)

```sh
python -m unittest -v tests_standalone.test_r51a_ui_layout \
  tests_standalone.test_r51b_layout_designer \
  tests_standalone.test_r51b2_ui_navigation \
  tests_standalone.test_r51c2_player_screens \
  tests_standalone.test_r42_narrative_player

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
DRAWTEMP_R51_QT_GATE=1 python -m unittest -v \
  tests_standalone.test_r51b_qt tests_standalone.test_r51c2_qt
```

La CI R51.C2 propose le parcours headless sous Ubuntu/Windows/macOS
et un smoke Qt Quick **software/offscreen** sur Linux. Un test utilise un
récit R42 à plusieurs répliques et vérifie que l'avancement change
exactement une révision R1 et n'offre plus l'action en fin de scène.

### Limites / NO-GO

- L'écran Dialogue personnalise l'affichage narratif mais les décisions
  restent sur les boutons legacy pour conserver l'autorisation canonique.
- L'inventaire est implémenté pour le **combat CT**, non pour tous les
  modes du Player (RPG, action, exploration/campagne).
- `HUD_ACTION` n'est toujours pas branché en production.
- Aucun test humain d'accessibilité, manette physique, GPU onscreen,
  goldens DPI, bundle natif ou clean-machine tri-OS n'est revendiqué.
- Les droits d'assets et la parité d'export complète restent à intégrer
  dans une nouvelle PR : les modifications de #411 sont **non fusionnées**.
- **Gate R51 = NO-GO**, même si cette PR est fusionnable ou fusionnée.
