# R69 — Community Creator Hub (10.9 → 11.0)

**Statut : incrément de développement, pas une certification de release ni de droits.**  
Source : [roadmap R51–R80](../DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md), section R69. Dépendances R24/R47/R48/R58/R59 à revalider sur `master`.

## Contrat et choix d'architecture

R69 réutilise exclusivement les archives **R30 `creator_packs` schéma 1**, leur inspection (`inspect_pack`) et l'import **R30.B `pack_import` vers une NOUVELLE copie** du projet. Aucun moteur, mod exécutable, second schéma de GameProject, serveur obligatoire, télémétrie ni téléchargement automatique.

Le SDK `drawtemp.sdk.community_hub` propose :

- `publish_pack(catalog, archive, publisher=..., declaration=..., confirm=True)` : vérifie chaque octet, les SHA-256 internes, la compatibilité SDK, les types inertiels, la provenance par asset, la déclaration de l'auteur ; ajoute un ZIP local par SHA dans `packs/`. La publication réclame un **consentement explicite**.
- `read_catalog`, `search_catalog` et `available_updates` : recherche locale volontaire et **proposition uniquement** des versions SemVer supérieures. Pas de requête réseau, de connexion implicite, ni de migration de projet.
- `acquire_pack(catalog, id, version, destination, confirm=True, expected_sha256=...)` : recopie un ZIP uniquement vers un **nouveau fichier** choisi par l'utilisateur, après vérification d'identité, version, taille, licence, origine et SHA. Le digest externe éventuellement épinglé est contrôlé ; un digest dans le catalogue **n'est pas une signature**.
- `withdraw_pack(catalog, id, version, reason=..., confirm=True)` : marque une version comme **retirée**, la cache des recherches et interdit les nouvelles acquisitions. Le tombstone persiste, une même version ne peut plus être republiée. Les fichiers déjà acquis par d'autres utilisateurs ne peuvent pas être supprimés rétroactivement.

Les champs JSON du catalogue sont fermés, versionnés (`schema: 1`) et bornés (1 Mio). Les versions et identifiants sont vérifiés, les doublons refusés, les écritures sont atomiques et verrouillées par un dossier temporaire. Un verrou laissé par un crash bloque les écritures : vérifier toute instance concurrente avant de supprimer manuellement `.r69-writer-lock`. Un même ID doit publier des versions strictement croissantes.

### Droits, modération et limites explicites

Chaque ressource déclare sa licence et son origine, et l'auteur déclare sa capacité à la redistribuer. **Cela ne prouve pas la propriété ni l'autorisation légale**. Le champ obligatoire `legal_clearance: false` reflète cette limite ; la revue juridique/artistique reste distincte des contrôles automatiques. Le champ `publisher` est une étiquette, **pas une identité authentifiée**. La modération minimale est un retrait local avec motif ; il n'existe pas de modération centralisée ni de système de signalement en réseau. Un index peut être altéré par son opérateur : vérifier le SHA attendu indépendamment pour un transfert à travers une frontière de confiance.

Seuls des ZIP contenant des ressources inertes déjà acceptées par `creator_packs` sont autorisés. Aucun `importlib`, plugin Python/QML, subprocessus, script, exécution ZIP, extraction de ZIP ou activation automatique n'est ajouté. Les modifications de contenus de projet restent sous le contrôle de `AuthoringSession` et du mécanisme d'import existant. Aucun fichier source de projet, sauvegarde, replay, pack existant ou copie consommateur n'est remplacé par le Hub.

## Usage : deux créateurs sur une machine hors ligne

Créer d'abord les packs via `python -m drawtemp.export.creator_pack_cli build` (manifestes R30 avec provenance par ressource). Exemple d'échange :

```shell
python -m drawtemp.export.community_hub_cli publish \
  --catalog ./creator-hub --pack ./my-terrain-1.0.0.zip \
  --publisher studio-original \
  --declaration "I created these assets and consent to redistribution." --confirm

python -m drawtemp.export.community_hub_cli search --catalog ./creator-hub
python -m drawtemp.export.community_hub_cli acquire \
  --catalog ./creator-hub --id my-terrain --version 1.0.0 \
  --output ./received-terrain.zip --confirm

# Prévisualisation R30.B : lister explicitement les ressources à importer.
python -m drawtemp.export.pack_import_cli \
  --content ./source/game.json --pack ./received-terrain.zip \
  --bindings ./asset-bindings.json

# Après revue du plan, création d'une nouvelle copie de projet (jamais écraser).
python -m drawtemp.export.pack_import_cli \
  --content ./source/game.json --pack ./received-terrain.zip \
  --bindings ./asset-bindings.json --output ./copied-project --confirm

python -m drawtemp.export.community_hub_cli withdraw \
  --catalog ./creator-hub --id my-terrain --version 1.0.0 \
  --reason "Author withdrew distribution permission" --confirm
```

La recherche et les mises à jour sont utilisables **sans service distant**. Une future interface Qt ou un index hébergé restera **facultatif** et fera l'objet d'une revue distincte (autorisations, confidentialité, modération, signatures et disponibilité réseau).

## Gate de validation R69.A–C (headless)

```shell
python -m unittest -v tests_standalone.test_drawtemp_r69_community_hub
python -m unittest -v tests_standalone.test_drawtemp_r30b_pack_import
python -m unittest -v tests_standalone.test_drawtemp_r47a_modding
```

Le test VS-69 crée **trois packs PNG synthétiques originaux** (`terrain`, `enemy`, `hud`) depuis les sources du test, publie les trois dans un catalogue local, les acquiert dans un autre espace puis les injecte dans trois nouvelles copies de projet via R30.B ; il contrôle l'absence de modification du projet source. Il teste le retrait, les tombstones permanents, la non-républication de version, les mises à jour manuelles, les consentements refusés, ZIP altérés, clés JSON dupliquées, chemins symboliques et refus d'un fichier Python. Les PNG sont des données de test originales, **pas** des packs commerciaux dont les droits auraient été audités.

**Non couvert / NO-GO release 11.0 :** index public hébergé, signature vérifiée, modération centralisée/notification de retrait, confidentialité UX Qt, vérification terrain Windows/macOS/Linux, preuve de clearance juridique et accessibilité Qt. Le lot R69.B **offline opt-in** n'implique aucune certification de publication communautaire publique.
