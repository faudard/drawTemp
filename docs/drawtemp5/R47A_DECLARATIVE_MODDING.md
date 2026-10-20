# R47.A — SDK & Modding 2.0 : contrats déclaratifs (8.7, incrément)

**État : code proposé en PR, non certifié.** Ce lot correspond à la fondation **R47.A** de la [roadmap R41–R50](../DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md). Il ne constitue **ni** R47.B (inspecteur Qt), **ni** R47.C (deux plugins / deux jeux et gate multiplateforme), et ne certifie pas la release 8.7.

## Décision d'architecture / contrat d'API

- Conserver le **Core headless** et les schémas canoniques Content et GameProject ; aucune migration implicite de sauvegarde, de gameplay CT ou de replay.
- Le SDK reste **provisional**, SDK_API_VERSION reste (1, 0). La nouvelle feature négociable est modding-declarative.v1, réexportée dans drawtemp.sdk. Aucune promesse de stabilité ABI binaire ou d'API Python tierce arbitraire.
- Le module public drawtemp.sdk.modding expose validate_mod_manifest, read_mod_manifest, ModRegistry, ModError. Il s'appuie sur **R24 AuthoringSession / GameProject.extensions**, **R30 require_sdk** et **R30 inspect_pack** ; pas de second registre métier ni de système de fichiers propriétaire.
- Un « mod » R47.A est une **déclaration JSON non exécutable**, pas un module Python. Les champs sont strictement fermés : schema, id, version, namespace, requires, permissions, dependencies, resources, extension, rights. Les champs python, entrypoint, script, import, command, ou d'autres clés non prévues sont rejetés.
- **Versionnement** : SemVer exact MAJOR.MINOR.PATCH, intervalles [min_api, max_api) pour SDK et [min_version, max_version) pour les dépendances. Les versions supérieures et features inconnues sont refusées ; les évolutions incompatibles exigeront un nouveau schéma ou major.
- **Dépréciation** : aucune feature R24/R30 n'est retirée et les manifestes R15 v1 / Studio R24 v2 restent indépendants. Une future suppression exige ADR, notice de dépréciation, fixtures cross-version et refus/migration explicite — jamais une transformation silencieuse.

## Permissions, isolation et limites

project.read et project.extensions.write sont les seules permissions R47.A. Elles doivent être octroyées **exactement et explicitement** avant activation ; la désactivation révoque toutes les permissions. Le manifeste doit déclarer project.extensions.write pour avoir un bloc extension. L'application appelle AuthoringSession.preview_project, puis AuthoringSession.apply avec expected_revision : aucune écriture hors namespace, aucun remplacement d'une extension existante, Undo/Redo natif. project.read **ne fournit aucune extraction arbitraire** de données dans cet incrément.

Le registre est **éphémère** et ne scanne ni n'auto-charge de modules. Il ne lance aucun script ni subprocess : pas de Python/QML, eval, exec, fichiers ou réseau par mod. L'exécution de code tiers, même « sandboxée », est **hors contrat** tant qu'une isolation mesurée (CPU/mémoire/timeout, permissions) n'est pas prouvée. R47.4/R47.5 sont donc respectés par la limitation aux données déclaratives, **pas** par l'affirmation d'une sandbox OS.

## Ressources, licences, intégrité et suppression

Chaque pack référencé dans resources doit être fourni explicitement par l'hôte sous son ID et validé par l'inspection R30 de l'archive entière et de ses éléments. Les **ID, version et SHA-256 de l'archive** doivent être identiques à ceux du manifeste. Les packs manquants, falsifiés ou d'une version différente bloquent l'installation. Les chemins ne sont **pas** pris dans le JSON pour ouvrir des fichiers arbitraires.

rights comprend license, origin, evidence et redistributable explicites. Leur présence **n'est ni une signature cryptographique ni une autorisation juridique vérifiée** ; rights_verified reste donc **false**, et les exports/distributions restent NO-GO jusqu'à approbation externe. Les signatures éditeur et la chaîne de confiance sont à traiter dans R47.C/R50 : ne pas considérer un hachage comme une signature.

La suppression retire seulement la déclaration **en mémoire**. Elle refuse un mod encore requis par un autre mod, et refuse si des données existent dans le namespace du GameProject fourni. Elle ne supprime **jamais** données de jeu, packs ou fichiers utilisateurs ; l'hôte doit conserver des diagnostics pour les références orphelines. L'upgrade/downgrade silencieux d'un manifeste déjà installé est interdit (collision) ; des migrations dirigées et rollback seront à livrer en R47.B/C.

## Exemple d'intégration

~~~python
from drawtemp.sdk import ModRegistry, read_mod_manifest

registry = ModRegistry()
manifest = read_mod_manifest("examples/mods/quest-r47.json")
registry.install(manifest)
registry.enable(manifest["id"], grants=["project.extensions.write"])

# editor : AuthoringSession canonique déjà ouverte par le Studio
plan = registry.preview_extension(manifest["id"], editor)
# L'hôte présente le diff du plan et recueille une confirmation explicite.
registry.apply_extension(manifest["id"], editor,
                         expected_revision=editor.revision)
# editor.undo() / editor.redo() restent les seules sources de vérité
~~~

## Vérification / portes encore ouvertes

Commande ciblée : python -m unittest tests_standalone.test_drawtemp_r47a_modding.

Couverture R47.A : validation de JSON et de schémas fermés, version API/feature, dépendances, collisions, permission refusée par défaut et révoquée, preview/apply/Undo/Redo, protection de la révision et du namespace, archivage invalide, hash absent, refus de suppression destructive. Les tests ne prouveront pas à eux seuls le bon fonctionnement du Studio.

**Poursuite :** R47.B — Plugin/SDK Inspector Qt, UX de consentement, activation et désinstallation réversibles, matrice Qt onscreen ; R47.C — deux packs complets sur deux jeux, vrais exports Windows/Linux/macOS, integrity/license approvals, CI sur SHA master, mesure de mémoire/timeout si une exécution isolée est ajoutée. Le gate **R47 reste NO-GO** tant que ces preuves manquent.
