# R8.17 — Crash & Fault-Injection Lab

**Portée :** prolongement de R8.9–R8.16, basé sur les contrats
`GameSession`, `SessionStore`, `LongSessionStore` et le verrou
`session_writer_lock` existants. Aucun nouveau format de sauvegarde.

## Exécution

```sh
python -m unittest discover -s tests_standalone -p test_persistence_fault_r817.py -v
python -m examples.persistence_fault_lab --seeds 1 7 --output persistence-fault-r817.json
```

Le laboratoire lance de **vrais processus Python enfants** qui terminent
brutalement avec `os._exit(79)` ; aucune finalisation Python ou suppression
de verrou ne peut être exécutée après cette instruction. Chaque cas crée son
propre répertoire temporaire et sauvegarde un état initial vérifié.

### Matrice des points de coupure

| Point d'injection | Moment | Résultat autorisé |
|---|---|---|
| Temporaire journal | Mort du processus au milieu de `write()`, avant flush/fsync | Fichier primaire intact ; temporaire partiel ignoré |
| Journal #1 | Avant `os.replace` | L'action n'est pas publiée ; reprise avant action |
| Journal #1 | Après `os.replace` | L'action est durable et rejouée exactement une fois |
| Backup | Avant / après remplacement | Journal publié ; action restaurée sans perte |
| Checkpoint | Avant / après remplacement | État final identique au replay canonique |
| Nettoyage journal #2 | Avant / après remplacement | Compaction sans double application |

Chaque contrôle vérifie les **digests complets de `GameSession`**,
la progression narrative, les reçus d'identifiants d'opérations, et la
convergence après un retry avec le même identifiant. Les replays
multi-fronts et longs combats restent validés par les tests R8 précédents.

Un contrôle multi-fronts tue également le processus pendant le
checkpoint suivant un premier changement de focus. Il compare l'état
`GameSession` complet, l'historique stratégique, l'état des secteurs hors
focus et le rejeu d'un même ID de requête, y compris les identités des
batailles nouvellement créées.

Un test séparé altère volontairement la chaîne de checksum d'un journal.
Le chargeur doit échouer et **ne peut pas** prendre silencieusement
un ancien checkpoint. Une coupure laisse potentiellement un
fichier `*.tmp`; il est diagnostiqué dans le rapport mais ne devient
jamais un checkpoint valide.

### Protocole concurrent multi-processus

1. Le processus A prend le verrou `<slot>.lock` et signale qu'il le détient.
2. Le processus B tente une commande sur le même slot : il doit échouer avant toute mutation.
3. Le processus A libère normalement le verrou.
4. Le processus B peut ensuite enregistrer son action et la rejouer.
5. Les scénarios de crash confirment qu'une mort brutale laisse un verrou
   non récupéré automatiquement.

Pour la suppression d'un verrou résiduel, il faut vérifier que **le
processus d'origine est terminé**, conserver les fichiers de preuve si
nécessaire, puis enlever manuellement `<slot>.lock`. Le laboratoire
ne crée jamais de code qui vole automatiquement un verrou.

### Rapport JSON

`persistence-fault-r817.json` comprend : version, seed, point de coupure,
présence ou non d'une transaction durable, digest récupéré/final,
séquence du checkpoint, entrées rejouées, retry effectué/non effectué,
nombre de temporaires orphelins et contrôle d'exclusion de writer.

Ces preuves sont reproductibles **au niveau des données de gameplay** ;
le rapport ne prétend pas certifier la tenue d'une alimentation électrique
ou les barrières de cache d'un système de fichiers particulier.

### Gate de livraison

- Tous les points de coupure passent sur Linux, Windows et macOS.
- Aucun événement publié ne disparaît ni n'est appliqué deux fois.
- L'action coupée avant publication peut être refaite avec le même ID.
- Aucune archive endommagée n'est silencieusement écrasée.
- Le verrou multi-processus refuse toute seconde écriture active.
- Tous les tests R8 historiques restent verts.

**Limites :** ce laboratoire injecte des crashs de processus, pas des
coupures réelles de courant. L'impossibilité d'écrire, le quota disque,
les privilèges et la corruption matérielle doivent être testés sur des
machines de qualification dédiées. Les seuils de performances restent
ceux des campagnes de mesures précédentes.
