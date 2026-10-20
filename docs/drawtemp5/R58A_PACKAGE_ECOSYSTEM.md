# R58.A — Creator Package Ecosystem : planification d'installation (P0, incrément initial)

**Statut : implémentation headless proposée, non certifiée.** La roadmap canonique est
`docs/DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md`.
Ce sous-lot ne satisfait **pas** à lui seul les gates R58.A, R58.B ou R58.C.

## Contrat réellement livré

`drawtemp.assets.package_ecosystem.plan_package_install` calcule un ordre d'installation
déterministe à partir des **archives R24.C existantes** (format `pack.json`, AssetRegistry
et reçus GameProject canoniques). Aucun second format de ressource, aucun second registre,
aucun nouveau moteur de scripts, aucun accès réseau.

L'appelant doit fournir explicitement :

- des archives locales régulières et non symboliques (1 à 64) ;
- le répertoire racine existant du projet et le dictionnaire GameProject ;
- une table indépendante `{id: sha256}` pour **chaque** archive sélectionnée.

La planification réutilise l'inspection R24.C : manifeste versionné, semver stricte,
hashs de fichiers, licence et origine déclarées, protections anti-ZIP traversal,
taille bornée et rejet des ressources non déclarées. Elle vérifie également les reçus
et fichiers **déjà installés** à l'aide du vérificateur R24.C.

Les dépendances doivent correspondre **exactement** à leur id, version et hash
d'archive : un pack fourni dans le lot ou un pack déjà installé peut les satisfaire.
Pas de résolution « latest », de téléchargement automatique, de changement de
version implicite ni d'installation d'un second pack sous le même ID. Les dépendances
manquantes, les collisions, les cycles, les données installées corrompues et les
pins divergents sont refusés. L'ordre retourné est stable et une empreinte du plan
facilite les revues diff/rollback R58.B ultérieures.

## Exemple minimal (API Python)

```python
from drawtemp.assets.package_ecosystem import plan_package_install

plan = plan_package_install(
    ["./packs/hero.rpack", "./packs/quest.rpack"],
    project_root="./my-game",
    project=project_dict,  # GameProject canonique issu du Studio
    expected_sha256={
        "hero-pack": "<empreinte SHA-256 vérifiée hors archive>",
        "quest-pack": "<empreinte SHA-256 vérifiée hors archive>",
    },
)
print(plan.to_dict())
```

La méthode ne modifie **jamais** les fichiers du projet ou l'historique d'édition.
L'installation proprement dite relève toujours de
`drawtemp.assets.packs.install_pack` et exige une nouvelle vérification des
archives avant chaque application. Un plan n'est **pas** une transaction
multi-pack atomique ni un mécanisme d'installation automatique.

## Frontières de sécurité et droits

- Le SHA-256 obtenu indépendamment atteste l'identité des octets, **pas**
  l'identité du créateur ; les signatures restent `not-verified` tant qu'une
  infrastructure de confiance et sa validation cryptographique n'existent pas.
- La licence, le titulaire des droits et l'élément de preuve proviennent du
  producteur du pack. Ils sont tracés comme **assertions**, non comme autorisation
  juridique de redistribution. `export_approved = false` par défaut.
- Aucun code de tiers n'est exécuté, aucune permission n'est ajoutée ;
  ni scripts arbitraires, ni accès réseau/OS ou sandbox d'exécution prétendue.
- La planification ne peut pas installer plusieurs versions d'un même pack,
  upgrader, désinstaller ou remplacer des ressources existantes.
- Avant R58.C / export : preuve externe des droits, compatibilité et conformité
  licence vérifiées indépendamment, contrôle d'authenticité et certification
  machine propre des deux projets.

## Vérification et suite

```bash
python -m unittest tests_standalone.test_drawtemp_r58a_package_ecosystem \
    tests_standalone.test_drawtemp5_r24c
```

Les tests couvrent tri topologique, relecture sur deux projets distincts,
dépendances absentes et conflictuelles, cycles, collision d'ID, empreintes
manquantes/divergentes, archive piégée, symlinks et intégrité du pack installé.
Les jobs CI Windows/macOS/Linux doivent être vérifiés sur le SHA final.

**Suivant :** R58.A2 (source de confiance/signatures et validation de provenance
juridique vérifiable), puis R58.B (UI Qt, prévisualisation, transaction atomique
multi-packs, mise à jour, rollback et désinstallation sans perte), et R58.C
(pack personnage/HUD/quête validé dans deux jeux et export clean-machine).
