# R47.C — Deux modules déclaratifs, deux jeux, intégrité et replay

**Statut : incrément d'intégration en PR #384, sans certification 8.7.** La roadmap R47 exige deux extensions dans deux jeux, des tests multiplateformes et un gate de diffusion réel. Ce document distingue **couverture reproductible automatisée** et **preuves encore manquantes**.

## Deux exemples installables et reproductibles

- [combat-tactics-r47.json](../../examples/mods/combat-tactics-r47.json) : module `combat-tactics-r47`, namespace `org.example.r47.combat`, données de conception tactique (rôles, annotations), **sans modification des calculs du combat**. Cette extension ne charge pas de Python, QML ou moteur de règles tiers ; elle ajoute des données au GameProject canonique.
- [tool-inspector-r47.json](../../examples/mods/tool-inspector-r47.json) : module `tool-inspector-r47`, namespace `org.example.r47.inspector`, checklist auteur lue/inspectable par le gestionnaire de mods Qt R47.B. Aucune fonction widget ou API privée externe n'est injectée.

Les deux modules ne sont **pas des preuves** d'une nouvelle mécanique de combat ou d'un système public d'extensions exécutables. Ils valident le contrat sûr d'extensions déclaratives R47.A/B. Les descriptions de licences CC0 des fixtures originales **ne suffisent pas à certifier tous les droits des projets ou packs tiers**.

## Deux projets témoins (sans fork du Core)

Le test `tests_standalone/test_drawtemp_r47c_two_games.py` crée deux projets canoniques via `drawtemp.export.templates.create_template` :

1. `tactical` : base tactique issue du Creator existant, compatible avec le moteur CT et le replay de campagne.
2. `asterion` : second jeu de référence du SDK, avec sa propre campagne et ses extensions historiques conservées.

Pour chacun : installation explicite de **deux manifestes**, approbation des permissions **en mémoire seulement**, preview et apply `AuthoringSession`, sauvegarde sur disque, réouverture du même GameProject, lecture des deux namespaces, préflight R15, initialisation de la campagne par `GameSession` canonique et vérification `verify_recording` du replay. Le Content reste sémantiquement identique avant et après insertion des extensions.

Le test refuse également : exécution arbitraire (`entrypoint`), écrasement implicite du manifeste ou downgrade en place, suppression de mod encore référencé dans le GameProject, nouveau mod inconnu après réouverture, digest de manifeste falsifié.

## Packs R30 vérifiés à l'installation ET au contrôle ultérieur

Le test génère des archives R30 de données JSON originales, sans fichiers Python/QML, avec manifestes et SHA-256 calculés. Chaque module épingle un pack par ID, version et SHA-256 d'archive. Les chemins sont choisis par le host et non déduits du JSON du manifeste.

`ModRegistry.audit_project(project, expected_pins=...)` vérifie, **sans mutation**, la présence des mods exigés, leur manifeste versionné, leur namespace et les packs R30 encore présents. Les pins (ID → SHA-256 du manifeste) doivent provenir d'un inventaire séparément approuvé par l'appelant. Ce mécanisme ne fournit **pas** une autorité de signature : si l'inventaire lui-même est compromis, le résultat n'est pas une preuve de confiance.

Après installation, falsifier une archive ZIP entraîne le diagnostic `resource_changed` et un résultat `compatible: false`. Le retrait d'un module non disponible ne supprime jamais ses données du projet : l'audit annonce `missing_mod`. `rights_verified`, `native_export_verified` et `release_certified` restent toujours **false** dans ce rapport technique.

## Commandes et matrice de couverture

Sur Python 3.12 :

~~~bash
python -m pip install .
python -m unittest tests_standalone.test_drawtemp_r47c_two_games -v
python -m unittest tests_standalone.test_drawtemp_r47a_modding -v
~~~

La CI `.github/workflows/drawtemp-r47c-two-games.yml` prévoit Windows, macOS et Ubuntu, et relance également les contrats R30 et R15, ainsi que la baseline tactique R1. Une validation Python/JSON headless ne vaut **pas** exécution sur machine utilisateur finale, sur GPU physique ou en Qt onscreen.

## Gate R47.C : preuves exigées pour GO

| Domaine | État de cet incrément | Pour certification complète |
|---|---|---|
| 2 manifestes et 2 projets | Exemples/tests présents ; CI à confirmer | Tests verts sur SHA final |
| Content/GameProject/replay | Tests headless ajoutés | Reprises Player et sauvegardes de longue durée réelles |
| Packs et hashes | Contrôles install/audit et tamper tests | Preuves de licences et provenance approuvées |
| Compat versions / refus | Tests SemVer, collisions et désinstallation non destructive | Migration documentée et rollback de versions |
| Studio Qt | Gestionnaire R47.B disponible | Tests QTest onscreen, focus/DPI, tests utilisateur |
| Windows/Linux/macOS | Workflows déclarés | Runners exécutés et logs archivés |
| Native Player | Preflight R15 sans runtime natif | Export de vrai Player + installation, lancement, sauvegarde et désinstallation |
| Sécurité | Aucun code tiers exécuté | Revue de sécurité indépendante ; signatures si activées |

Le pipeline d'export R15 **ne peut pas être simulé avec un script Python ou un faux exécutable**. Il exige un répertoire runtime natif et vérifie un bundle réellement assemblé. Le test R47.C s'arrête donc volontairement au préflight tant que le runtime et les tests d'export clean-machine ne sont pas disponibles.

**Décision : NO-GO R47 (non certifié)** jusqu'à la levée documentée de ces exigences ; ne pas fusionner sur la seule base de la présence de fichiers de tests.
