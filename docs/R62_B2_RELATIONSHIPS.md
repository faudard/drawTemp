# R62.B.2 — Relationship Studio et vie sociale déterministe

**Statut :** code proposé, gate R62 ouvert. Cette tranche dépend du
[R62.A](R62_A_FARMING_LIFE.md) et complète le
[Farm Studio R62.B.1](R62_B1_FARM_STUDIO.md).

## Contrat canonique

`GameProject.extensions["org.drawtemp.relationships"]` est **opt-in**
(enveloppe standard `schema_version=1`, `data`, `references=[]`).
Les projets sans extension ne comportent aucun bloc de sauvegarde social.

Exemple du document `data` (identités à adapter au Content et aux PNJ R35) :

```json
{
  "version": 1,
  "relationships": [{
    "npc": "merchant",
    "initial": 0,
    "talk_gain": 3,
    "talk_activity": "trade",
    "gifts": [{"item": "epee_de_jacques", "gain": 7}]
  }]
}
```

Les PNJ doivent être dans `org.drawtemp.livingworld.npcs` ;
`talk_activity` est `any` ou l'une des activités réellement planifiées
dans les horaires R35 du PNJ. Les cadeaux référencent exclusivement des
équipements Content ou ressources déjà déclarées par R55 : pas de monnaie
sociale ni d'inventaire parallèle. Les affinités sont bornées entre
**-100 et +100**, avec saturation, et les gains journaliers sont déclaratifs.

## Règles de simulation

- `GameSession.relationship_state(npc=None)` : vue détachée des affinités
  et des dernières actions, y compris PNJ hors focus.
- `relationship_talk(npc_id, receipt_id)` : une conversation par
  PNJ et par jour, avec vérification de sa scène R35 et de l'activité
  `talk_activity`.
- `relationship_gift(npc_id, item_id, receipt_id)` : un cadeau par
  PNJ et par jour, vérifié contre les préférences déclarées et débité
  atomiquement de `Campaign.inventory`.
- Le temps est **exclusivement** `LivingWorld.day`. Toute progression
  explicite et les pas fixes R25/R32 synchronisent les relations même
  lorsque le PNJ n'est pas dans la zone active. Aucun timer Qt ne modifie
  la progression.
- Les commandes sont journalisées avec des identifiants idempotents. Le
  rejeu valide les scores, jours et dernières interactions lors du reload.
  Un reçu réutilisé pour une autre commande est refusé ; un retry identique
  ne réattribue pas de points ou de cadeaux, même le lendemain.
- Bornes : **64 PNJ**, **16 cadeaux par PNJ**, **2048 reçus sociaux**,
  intervalles et quantités en entiers validés ; aucune exécution de script.

L'intégration SDK `Simulation` propose les mêmes commandes avec
`expected_revision` et retour de vue immuable.

## Interface auteur Qt

Dans le Studio : **Outils → Relationship Studio R62 : affinités PNJ…**
(également accessible par la palette de commandes).

Les formulaires natifs permettent de définir le PNJ R35, l'affinité
initiale, le gain par conversation, l'activité autorisée et les préférences
de cadeau avec leurs scores. Les objets et activités sont choisis dans
les catalogues typés existants, sans JSON édité à la main.

Un bouton ouvre **Monde vivant R35** pour modifier les horaires ; toute
modification du projet externe invalide la révision en cours et interdit
l'application d'un vieux brouillon. Undo/Redo local borné ; **Appliquer**
est une transaction unique du `AuthoringSession` canonique avec Undo/Redo
global. L'éditeur ne change pas les parties, objets ou stocks du Player.

## Vérifications prévues

```sh
python -m unittest tests_standalone.test_r62_relationship_life -v
python -m unittest tests_standalone.test_r62_relationship_authoring -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r62_relationship_gui -v
python -m unittest tests_standalone.test_r62_farming_life -v
```

Workflow dédié : `.github/workflows/r62-relationships.yml` (headless
Python 3.10/3.12, Qt offscreen Python 3.12). Une exécution de CI doit
réellement lancer les jobs et réussir ; un `failure` avec zéro job
ne certifie aucune assertion.

**Reste hors R62.B.2 :** arcs narratifs, cadeaux avec effets de quête,
événements de relation à seuils, playtest humain, HUD/conversations Player
Qt et vertical slice VS-62 R62.C (culture→récolte→vente→relation). Le gate
R62 n'est pas clos.
