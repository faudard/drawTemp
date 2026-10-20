# R50.A — Release ledger DrawTemp 9.0 (NO-GO by design)

> Scope : **contrat de preuve et inventaire headless**, pas un certificat
> 9.0 ni un gel d'API effectif. Base : roadmap
> [R41–R50](../DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md).
> R40 et les gates R41–R49 ne sont pas réputés acquis par la présence de
> commits, de PR ou de rapports auto-déclarés.

## Utilisation

```bash
python -m unittest -v tests_standalone.test_r50_certification
python -m drawtemp.quality.r50_certification \
  --revision "$(git rev-parse HEAD)" \
  --evidence-dir artifacts/r50a/input \
  --output artifacts/r50a/release-ledger.json
```

La CLI produit un **ledger explicite** même si le répertoire des preuves
est vide : `NO-GO`, `tag_allowed=false`, manquants et rejets détaillés.
`--enforce` renvoie code 1 quand la release n'est pas autorisée ; sans
cette option, code 0 signifie uniquement **rapport produit avec succès**.

CI : `.github/workflows/drawtemp-r50a-release-ledger.yml` sur Python
3.10/3.12, sortie attachée au SHA du workflow. Le job ne transforme pas
les tests headless en test Qt onscreen, GPU, machine propre ou essai humain.

## Contrat d'un enregistrement de preuve

Créer `<evidence-dir>/records/<id>.json` et le fichier physique
`<evidence-dir>/artifacts/<nom>`. Exemple pour une régression CT :

```json
{
  "kind": "drawtemp-r50-evidence",
  "schema": 1,
  "revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "requirement": "R50.3",
  "scope": "replay",
  "platform": "agnostic",
  "family": "srpg",
  "outcome": "passed",
  "artifact": "artifacts/jeanne-replay.log",
  "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

Les valeurs illustratives de révision et de checksum **ne sont pas des
preuves réelles**. Pour une entrée effective, utiliser le SHA exact du
checkout et le SHA-256 calculé sur les octets de l'artefact réel.

Le lecteur impose les clés exactes, les scopes/plateformes/familles
prévus par la matrice, le SHA Git exact, le checksum de chaque fichier,
la taille max de 8 MiB, un chemin relatif sous `artifacts/`, zéro
doublon de slot et zéro clé JSON répétée. Les dossiers non présents
n'autorisent aucun passe-droit. Tous les problèmes deviennent des
`invalid` ou `missing` visibles. Les preuves `failed` sont conservées
comme échecs déclarés, jamais traitées comme passes.

**Provenance :** un artefact avec checksum valide peut avoir été produit
par un auteur non fiable. Le ledger marque donc `reported-unverified`,
jamais `certified`. Un rapport de tests ne remplace pas une signature
d'artefact, une identité de runner, une approbation juridique ni une
preuve matérielle indépendante.

## Couverture et suites

| Exigence | Matrice minimale (état déclaré seulement) |
|---|---|
| R40, R41–R49 | Une preuve de gate amont par jalon, vérifiée ensuite contre master |
| R50.1 | Ledger présent, explicitement non approuvé |
| R50.2 | Migration/rollback des sauvegardes historiques |
| R50.3 | Replay de six familles (5 genres + démonstrateur hybride) |
| R50.4 | Cinq templates originaux traçables |
| R50.5 | Création et édition/playtest/export sans JSON, par famille |
| R50.6 | Studio/Player Qt onscreen réel Windows/Linux/macOS |
| R50.7 | Player et installateurs sur machine propre tri-OS |
| R50.8 | Benchmarks sur GPU physique tri-OS |
| R50.9 | Audits indépendants de sécurité et de droits |
| R50.10 | Décision humaine traçable et indépendante |

Cette matrice est un **minimum d'indexation** : elle ne prouve pas
les données de R50.2, la qualité des scènes, la parité Studio/Player,
l'absence de P0, la fiabilité des parcours, l'accessibilité, les licences,
ni les métriques p95/p99. Ce sont des gates à mesurer et approuver
avec des preuves complémentaires. La politique de certification
R50.C doit authentifier la provenance, contrôler les artefacts et
confronter les résultats au SHA `master` final, avant toute éventuelle
autorisation de release.

Prochaines PR, une fois R40 et les P0 R41–R49 vérifiés :
**R50.B** (templates et parcours Creator/Player réels), puis
**R50.C** (certification indépendante, tri-OS/hardware/utilisateurs et
décision GO/NO-GO). Aucun badge 9.0 ni tag de release ne doit être publié
sur la seule base de R50.A.
