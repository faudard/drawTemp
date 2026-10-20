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

`ModRegistry.audit_project(project, expected_pins=...)` vérifie, **sans mutation**, la présence des mods exigés, leur manifeste versionné, leur namespace **et la valeur exacte de leur enveloppe déclarative**, ainsi que les packs R30 encore présents. Les pins (ID → SHA-256 du manifeste) doivent provenir d'un inventaire séparément approuvé par l'appelant. Ce mécanisme ne fournit **pas** une autorité de signature : si l'inventaire lui-même est compromis, le résultat n'est pas une preuve de confiance.

Après installation, falsifier une archive ZIP entraîne le diagnostic `resource_changed` et un résultat `compatible: false`. Le retrait d'un module non disponible ne supprime jamais ses données du projet : l'audit annonce `missing_mod`. `rights_verified`, `native_export_verified` et `release_certified` restent toujours **false** dans ce rapport technique.

## R47.C — Remplacement explicite des versions de manifests (incrément suivant)

`ModRegistry.replace_version(mod_id, manifest, project=..., resource_paths=...,
allow_downgrade=False)` permet un changement de version **sans mutation de données
projet**. Le contrôle exige le même identifiant et namespace, un SemVer nouveau,
une extension strictement identique et des dépendances entrantes/sortantes
toujours compatibles. Les nouvelles archives R30 sont revérifiées intégralement
avant le remplacement du registre en mémoire.

Un downgrade est **refusé par défaut** ; il nécessite
`allow_downgrade=True` et, dans le Studio, un dialogue de consentement indiquant
clairement l'ancienne et la nouvelle version. Une fois la validation réussie,
**toutes les permissions précédentes sont révoquées**, même si le manifeste
réclame exactement les mêmes capacités. Le mod est donc inactif tant qu'il
n'est pas réautorisé.

L'état ancien est préservé si les packs sont absents/corrompus, si un module
dépendant bloque la version, si une autorisation manque ou si l'enveloppe de
l'extension change. Pour modifier les données, une migration `AuthoringSession`
explicite reste obligatoire ; ce remplacement **n'est pas** une migration
automatique de `GameProject`. L'utilisateur peut annuler le remplacement de
métadonnées en sélectionnant **à nouveau l'ancien manifeste et ses packs**
avec confirmation du downgrade ; aucun historique de manifests n'est persisté
ou certifié en dehors du projet.

Le SHA-256 épinglé dans un inventaire externe doit être mis à jour de façon
délibérée après changement de version. Il n'existe ni signature vérifiée ni
autorité de confiance automatique. Couverture :
`tests_standalone/test_drawtemp_r47d_versions.py`, tests Qt du
gestionnaire et matrice tri-OS R47.C.

## R47.E — Intégrité réévaluée à chaque autorisation et changement de projet

**Contrôle à l'instant d'utilisation** : `ModRegistry.verify_runtime(mod_id)`
et le validateur privé `_verify_live` relisent les fichiers ZIP R30,
contrôlent leur identité/leur version/leur SHA-256 et inspectent récursivement
les dépendances installées. Une autorisation donnée au moment de l'installation
ne suffit jamais à contourner cette vérification : `enable`,
`preview_extension`, `apply_extension`, `audit_project` et les nouvelles
installations dépendantes la déclenchent.

Un fichier retiré, remplacé, non régulier ou altéré mène à un diagnostic
`resource_changed`. Une dépendance manquante, incompatible ou cyclique est
refusée. Les ressources **ne sont ni exécutées, ni automatiquement réparées, ni
réapprouvées juridiquement**. Restaurer exactement les octets du pack d'origine
permet un nouveau contrôle ; cela n'octroie pas de permission.

Le gestionnaire Qt propose « **Vérifier l’intégrité** », une vérification
manuelle sans mutation du GameProject. Il reste utile de conserver les mêmes
archives R30 tant que le mod en dépend ; l'inventaire d'assets externe peut
par ailleurs varier indépendamment de la version du manifeste.

Les tests `tests_standalone/test_drawtemp_r47e_live_integrity.py`
exercent l'altération **entre installation et consentement**, l'altération
**après consentement avant preview/apply**, les dépendances altérées, le refus
de nouvelle installation dépendante et le retour à l'archive originale.
Un test Qt offscreen vérifie l'affichage du succès et du refus.
Tout cela reste à faire exécuter réellement par les runners Actions.

## R47.F — Préflight moddé avant le Player

Le couple `Content/GameProject` existant peut être inspecté en lecture seule
avec `inspect_modded_project`, l'inventaire de SHA-256 d'un hôte de confiance
et la liste explicite des namespaces gérés. Cela détecte les données de mod
orphelines, les contributions non épinglées et les archives R30 altérées,
sans confondre ces données avec les extensions natives du jeu. Le contrôleur
Player dispose d'un gate **optionnel**, strict lorsqu'il est activé ; il ne
change pas les sauvegardes ni le Player standard. Détails :
[`R47F_PLAYER_MOD_PREFLIGHT.md`](R47F_PLAYER_MOD_PREFLIGHT.md).

## Commandes et matrice de couverture

Sur Python 3.12 :

~~~bash
python -m pip install .
python -m unittest tests_standalone.test_drawtemp_r47c_two_games -v
python -m unittest tests_standalone.test_drawtemp_r47a_modding -v
python -m unittest tests_standalone.test_drawtemp_r47d_versions -v
python -m unittest tests_standalone.test_drawtemp_r47e_live_integrity -v
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
