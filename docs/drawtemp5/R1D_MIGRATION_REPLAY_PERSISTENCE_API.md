# DrawTemp 5.0 — R1.D : migrations, replay étendu, Player et API

> Tranche fonctionnelle R1.6 + R1.7 + R1.8 + R1.10, construite directement sur
> `master`. Les lots ont des contrats explicites et des tests, mais la
> certification globale R1 exige la réussite de la CI et une revue fonctionnelle.

## R1.6 — Import versionné et non destructif

`drawtemp.sdk.content_migration` fournit
`preview_documents(content, project)`, `preview_pair(path)` et
`commit_pair(plan, destination)`.

**Compatibilité réellement prise en charge :** enveloppes `Content` et
`GameProject` **sans champ `version` ou avec `version: 0`**, dont le
reste des données est déjà conforme à la structure et aux invariants
canoniques v1. Seule la version passe à 1; aucune transformation arbitraire
des missions, règles, assets ou dialogues. Les versions inconnues,
changements métier ambigus et données non valides sont **refusés**.

```python
from drawtemp.sdk import preview_pair, commit_pair

plan = preview_pair("vieux_projet.json")
print(plan.changes)  # aperçu pur, sources inchangées
commit_pair(plan, "projet_importe.json")  # nouveau couple seulement
```

Une prévisualisation mémorise les SHA-256 des deux fichiers source, bloque le
commit s'ils changent et repasse par les validateurs `Content`,
`GameProject` et `AuthoringSession`. Le stockage transactionnel canonique
`StudioTransactionStore` est utilisé pour publier les deux documents avec
son journal de récupération. Ni la source ni ses sauvegardes historiques ne
sont écrasées. Pour des formats réellement différents de v1, une migration
spécifique doit être conçue et testée; aucune conversion fictive n'est admise.

## R1.7 — Replay étendu

`drawtemp.sdk.replay` fournit :
- `verify_recording(recording, content, project)` : vérifie les checksums et
  replays imbriqués grâce à `GameSession.from_recording`, puis exige deux
  relectures identiques, sans toucher au fichier original.
- `verify_sequence(content, project, campaign_id, commands, seed=17)` :
  rejoue un ensemble borné de `ReplayCommand`, effectue une vraie restauration
  **après chaque opération**, et produit des `ReplayCheckpoint` avec hash
  de session, identité Content/Project et hash tactique.
- `verify_sequence(..., initial=recording)` : reprend un checkpoint vérifié
  (campagne, bataille ou fronts), sans modifier sa source.

L'allowlist d'opérations est statique. Les tests de régression comprennent
dialogue, porte/levier, combat, doctrines, progression globale de fronts,
changement de front et commande tactique. Le RNG, les CT et événements sont
**ceux des modèles canoniques** : aucun second moteur et aucun second format
de replay ne sont créés. Les UUID des batailles ne sont pas forcés à être
identiques entre deux sessions indépendamment créées; les replays d'un même
checkpoint doivent, eux, être rigoureusement égaux.

## R1.8 — Persistance Player 5.0

`drawtemp.sdk.slots.PlayerSlotStore` est désormais utilisé par
`drawtemp.player.controller.PlayerController` pour `load`, `save`,
`restore_backup` et `inspect_slot`.

- Compatibilité intégrale du chemin `slot_N.json`, du secours
  `slot_N.json.bak` et du `GameSession` v1 existant.
- Validation de la session, du checksum, du replay et de la campagne avant
  toute promotion de l'ancienne sauvegarde en backup.
- Rotation atomique de la copie précédente, sauvegarde primaire atomique,
  relecture et comparaison du résultat après publication.
- Aucun fallback automatique silencieux : `load` exige un primaire valide;
  `restore_backup` est une **action utilisateur explicite**.
- Restauration depuis un backup vérifié, stockage des octets d'un primaire
  corrompu en `.json.damaged`, protection contre le remplacement d'une
  preuve `.damaged` préexistante, refus des liens symboliques.
- Sérialisation des écritures entre writers coopératifs via
  `session_writer_lock`; pas de migration implicite au format
  `SessionStore` v2 ou `LongSessionStore`.

Les formats de checkpoints longs v2 et les archives demeurent accessibles
via leurs services canoniques, mais ne sont **pas** installés silencieusement
sur les slots v1 du Player. La restauration ne remplace pas un mécanisme
de backup externe pour la panne totale du disque.

## R1.10 — Surface publique du Game SDK

```python
from drawtemp.sdk import (
    SDK_API_VERSION, capabilities, Simulation, SimulationError,
    AuthoringSession, preview_pair, commit_pair,
    ReplayCommand, verify_recording, verify_sequence, PlayerSlotStore,
)

assert SDK_API_VERSION == (1, 0)
assert capabilities()["game_session_schema"] == 1
```

Les exports sont différés : aucun import Qt/Tk à l'import du SDK. Les erreurs
des nouveaux sous-modules ont chacune un `code` structuré :
`MigrationError`, `ReplayError`, `SlotError`.

**État exact : `SDK_API_STATUS = "provisional"`.** Le numéro de contrat 1.0
désigne l'interface candidate, pas la certification produit finale ni un
engagement déjà publié de compatibilité éternelle.

Politique proposée : la structure des erreurs, les types retournés et les
noms exportés sont testés; toute rupture de cette surface requiert une
augmentation de la version majeure de l'API, accompagnée d'un adaptateur.
Les additions compatibles augmentent la version mineure. Les formats de
contenu, sauvegardes et replays ont leur propre numéro de schéma : ne jamais
confondre `SDK_API_VERSION` et `GameSession.VERSION`.

## Reproduire les tests

```bash
python -m pip install .
python -m unittest tests_standalone.test_drawtemp5_r1d -v
python -m unittest tests_standalone.test_drawtemp5_r1 \
    tests_standalone.test_drawtemp5_r1_authoring \
    tests_standalone.test_drawtemp5_r12 \
    tests_standalone.test_game_session -v
python scripts/audit_drawtemp5.py --check --strict
```

Le nouveau test est ajouté au workflow R0/R1 headless sur Python
3.10 / 3.12 / 3.14. Aucune réussite CI n'est revendiquée avant retour
des checks associés à la PR. Les capacités GPU, GUI/Qt, longs sièges et
robustesse face aux coupures physiques nécessitent encore des preuves dédiées.
