# R55 — System Designer: premier lot exécutable

Cette livraison commence **R55.A** et fournit une première interface native **R55.B** de la
[roadmap R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).
Elle **ne valide pas encore** le gate R55 ni la release 10.0 : l'éditeur
Qt nécessite une qualification QTest/UX approfondie, l'intégration au tick
canonique et la certification de bout en bout restent à livrer.

## Propriété et schéma

- Source éditoriale unique : `GameProject.extensions["org.drawtemp.systems"]`,
  enveloppe standard `{"schema_version": 1, "data": ..., "references": []}`.
- Schéma `data` v1 : `version`, `resources` (`id`, `initial`,
  `capacity`), `producers` (`id`, `inputs`, `outputs`, `interval`),
  `merchants` (`id`, `resource`, `scene`, `buy_price`, `sell_price`),
  `quests` (`id`, `resource`, `quantity`, `flag`).
- Aucun script, callback, expression utilisateur ni seconde base de données :
  l'économie est un composant du `GameSession`; l'inventaire, la monnaie et
  les flags de quête sont ceux de `Campaign`.
- `validate_systems(spec, scenes)` rejette références inconnues, booléens
  à la place d'entiers, doublons, versions futures, recettes sans entrées,
  dépendances cycliques et capacités hors budget.
- Ordre de résolution déterministe : ticks entiers; producteurs triés par
  identifiant; au plus 32 producteurs, 64 ressources, 256 ticks/commande,
  65 536 ticks/session et 512 commandes de journal. Le `max` de chaque stock
  borne aussi les productions et achats/ventes.

## Runtime (opt-in)

`GameSession.system_state()` et `system_preview(ticks)` fournissent des
copies détachées. `system_advance(ticks)` déclenche les cycles sans horloge
murale. `system_trade(merchant_id, action, quantity, transaction_id)` réalise
une transaction atomique dans une scène d'exploration active, avec identifiant
idempotent; `system_fulfill(quest_id)` livre des objets de l'inventaire de
campagne et positionne un flag narratif une seule fois.

`GameSession.recording()` inclut `systems` **uniquement** pour les projets
qui activent cette extension. `from_recording` rejoue le journal de commandes
pour reconstruire les stocks; un stock falsifié, une opération inconnue, une
réception répétée, une sauvegarde R55 manquante ou un flag de quête manquant
fait échouer le chargement. Les anciens projets/saves n'ont aucun changement
de format. L'historique R55 ne remplace pas la validation canonique de
`Campaign`.

## Studio headless

`preview_system_design(AuthoringSession, document, expected_revision=...)`
vérifie le graphe et produit un `AuthoringPlan` validé; seul
`apply_system_design` le commite. Le projet bénéficie du même Undo/Redo et
du contrôle de révision que les autres ateliers. `forecast_system_design`
calcule les stocks/deltas et affiche les liaisons du graphe sans modifier le
projet.

## Tests

```sh
python -m unittest tests_standalone.test_r55_system_design -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r55_system_design_gui -v
```

Couvre cycles/typing, ordre stable, projection sans mutation, capacité,
achats/ventes sans duplication, quête unique, sauvegarde/rechargement, rejet
de stock forgé même avec checksum recalculé, Undo/Redo et compatibilité
des sauvegardes sans R55.

## Interface R55.B initiale

Dans le Studio Qt, ouvrir **Outils → System Designer R55**. Un graphe
représente les liens ressources → producteurs → ressources et
ressources → marchands/contrats; les onglets permettent d'ajouter ou retirer
des éléments via des formulaires typés. La projection affiche les deltas et
les stocks insuffisants. **Appliquer au projet** crée une seule transaction
`AuthoringSession`, compatible avec les commandes générales Undo/Redo.
Les producteurs à plusieurs ressources restent visibles ; leur édition avancée
nécessitera un éditeur multi-ports dédié.

## Reste pour le gate R55

- **R55.B** : édition avancée multi-ports, déplacement/nœuds, raccourcis,
  accessibilité Qt, QTest d'interactions complets et gestion explicite
  des conflits entre deux fenêtres.
- **R55.C** : démonstrateur complet réellement assemblé via le Studio,
  raccord marchand/quête au Player, transition entre régions, simulations
  longues multi-seeds, balance et rapport GO/NO-GO sur master final.
- **Runtime** : pilotage explicite des cycles depuis le tick canonique du
  Player; pas de « cadence automatiquement activée » avec cette PR.
