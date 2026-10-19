# R21.C — Préparation de siège, bélier, herse et visibilité multi-fronts

> **Tranche incrémentale R21.8–R21.10** proposée au-dessus de R21.B,
> elle-même au-dessus de R21.A. Ce document ne certifie ni les deux
> approches complètes du château, ni les parcours Player Qt/GPU.

## Frontière d'architecture

Réutiliser strictement `Battle.execute` et
`MultiFrontSession.execute` pour toute action d'auteur ou de joueur.
Le moteur possède déjà les commandes `interact` pour pousser le bélier,
frapper la porte, tirer au catapulte et actionner le levier de herse,
ainsi que les conséquences entre fronts pilotées par `front_links`.
Aucune formule parallèle de siège et aucune nouvelle donnée persistée.

## Implémentation

### 1. Prévisualisation d'opération tactique

`siege_operation_preview(battle, object_id)` retourne un objet JSON
pour les équipements `ram`, `catapult`, `switch`, `door` :

- unité effectivement active, disponibilité et motif de refus issu
  du **véritable handler** de l'interaction ;
- `phase` : `advance`, `strike`, `breach`, `open` ou `unavailable` ;
- position actuelle et destination immédiate réelle du bélier ;
- état de la porte liée et ses PV immédiatement après l'action si
  elle est exécutée maintenant.
- données `current_state_only` : le résultat n'anticipe ni
  l'activation suivante, ni la survie future de l'équipage, ni les
  choix IA ni les fronts hors focus.

La prévisualisation appelle `Battle._interact()` **sur une copie
profonde isolée**, capture ses événements véridiques et ne touche pas
au RNG ni au journal de la bataille réelle. Seule
`Battle.execute({"kind": "interact", "object": "..."})` peut modifier
l'état canonique et donc la sauvegarde ou le replay.

### 2. Visibilité stratégique des fronts

`siege_front_readiness(MultiFrontSession)` montre, dans une projection
détachée, les fronts et leurs états stratégiques, ainsi que leurs
portes et engins.

Pour les fronts **jamais visités**, il combine
`session.content.missions` avec `session.front_overrides` et les
distingue explicitement d'une bataille réellement créée :
`source=authored_plus_committed_overrides`. Une porte ouverte à
distance par un levier reste affichée comme ouverte avant le premier
switch de focus.

Les liens one-shot indiquent `applied`, leur événement source et les
fronts cibles ; aucune conséquence n'est appliquée par cette projection.
Les renforts interdits restent lus depuis le même
`session.blocked_reinforcements` canonique.

### 3. Accès pour le joueur/testeur

Le centre de commandement existant accepte :

```text
siege
```

Il restitue l'état de préparation en JSON formaté, exploitable par un
futur panneau de préparation Qt et les outils de certification.
Le précédent `status` n'est pas modifié.

## Validation automatisée prévue

```bash
python -m unittest -v tests_standalone.test_r21c_siege_readiness
python -m unittest -v tests_standalone.test_siege
python -m unittest -v tests_standalone.test_fronts
python -m unittest -v tests_standalone.test_siege_routes
python -m unittest -v tests_standalone.test_r21b_floor_tactics
```

Les nouveaux tests vérifient les vrais événements `ram_advanced`,
`siege_hit` et `front_link_applied` via les commandes canoniques ;
ils couvrent également chemin bloqué et rollback, PV de porte sans
formule dupliquée, levier ouvrant une porte sur front **non
matérialisé**, diminution de l'opposition de cour, projection pure et
replay exact `MultiFrontSession.replay`. Des fixtures spécifiques
raccourcissent le trajet du levier pour tester la causalité réelle
sans falsifier la commande.

**Statut des preuves :** il faut lancer les suites et obtenir la CI
verte sur le dernier SHA avant de considérer le gate logiciel atteint.
Les tests de source ne sont pas un résultat de validation en soi.

## Manques avant le gate complet R21

- Placement/déploiement d'équipe depuis les contrôles Qt du Player,
  inspection sans JSON et roundtrip d'équipements.
- Traction du bélier avec équipage visible, collisions d'acteurs et
  obstacles dynamiques, herse animée, portails dans les étages et
  rendu Studio/Player certifié par capture et GPU réel.
- Avancement multi-fronts joué sur plusieurs tours avec
  ravitaillement, renforts et checkpoint externe rechargé.
- Deux approches terminables jusqu'à la salle du trône, au moins
  deux fins sauvegardées et statistiques de Balance Lab multi-seeds.
- Rebase/CI dans l'ordre R21.A puis R21.B puis R21.C avant toute fusion
  finale dans master.

Voir [roadmap R17–R24](../DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md).
