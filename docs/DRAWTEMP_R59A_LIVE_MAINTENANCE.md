# R59.A — Production & Live Maintenance: fondations (NO-GO)

État : **implémentation partielle** de R59.A sur une branche de travail.
La roadmap canonique est `DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md`.
Aucune certification release 10.0, signature ni test d'installation n'est revendiqué.

## Contrats livrés dans ce lot

- `drawtemp.export.live_maintenance.release_descriptor` : s'appuie sur
  `publication_plan` R39 (intégrité des bundles R15, droits et provenance déclarée)
  pour lier semver X.Y.Z, révision Git, plateforme, famille, empreinte du manifeste
  et empreinte canonique des dépendances déclarées. **Ces métadonnées ne sont pas
  une SBOM de runtime vérifiée, ni une signature cryptographique**.
- `validate_release_descriptor` : refuse schéma inconnu, version ambiguë,
  approbation revendiquée et compatibilité implicite des sauvegardes historiques.
- `plan_update` : compare version, cible, famille, empreinte des bundles et
  schémas de sauvegarde observés. Un passage N-1→N est **bloqué** tant qu'un
  adaptateur réel n'a pas été développé et prouvé avec fixtures. Même un
  plan « candidate » demeure **NO-GO**.
- `snapshot_saves` : copie bornée des fichiers de sauvegarde et backups de
  récupération dans un nouveau répertoire atomiquement publié, inventaire
  avec SHA-256, aucune modification du dossier source.
- `verify_save_snapshot` : rejette les corruptions, fichiers ajoutés,
  chemins relatifs suspects, doublons, liens symboliques et fichiers spéciaux.
- `restore_saves` : copie la génération contrôlée **uniquement dans une
  destination absente**. N'écrase jamais une sauvegarde existante et ne
  modifie pas le Player en cours.

### Exemple Python (sans activation d'une mise à jour)

```python
from drawtemp.export.live_maintenance import (
    snapshot_saves, verify_save_snapshot, restore_saves,
)

snapshot_saves("user-data/saves", "recovery/1.0.0")
verify_save_snapshot("recovery/1.0.0")
restore_saves("recovery/1.0.0", "recovery/1.0.0-restored")
```

Les manifestes de release nécessitent les arguments `bundle`, `provenance`,
`version`, `revision`, `target`, `family` et `save_schema`, et leur
construction échoue si le preflight R39 refuse le bundle.

## Gates et limites explicites

| Domaine | Situation après ce lot |
|---|---|
| Versionnement, empreinte de bundle et dépendances | API de déclaration, contrôles stricts |
| Copies de secours et restauration vers dossier neuf | Implémentées avec empreintes et refus d'écrasement |
| Compatibilité N/N-1 | N accepté seulement si le Player déclare N; **adaptateur N-1 non livré** |
| Release Center Qt (R59.B) | Non implémenté |
| Mise à jour atomique du Player installé (R59.C) | Non implémentée |
| Rollback transactionnel binaire + saves | Non implémenté; seule la récupération de copies de sauvegardes est couverte |
| Attestation indépendante de SBOM/signatures | Non implémentée |
| Vérification machine propre tri-OS / UX GPU | À exécuter et contrôler en CI et physiquement |
| Décision release | **NO-GO** tant que tous les gates R59 ne sont pas prouvés |

## Tests

```bash
python -m unittest tests_standalone.test_r59a_live_maintenance -v
python -m unittest tests_standalone.test_r39_publishing -v
```

La matrice CI R59.A cible Python 3.10 et 3.12 sur Linux, Windows et macOS.
Ces tests sont headless : ils ne certifient pas une installation native réelle.

## Étapes suivantes

1. **R59.A suite :** schémas de sauvegardes existants, adaptateurs N-1→N
   idempotents par type réel de sauvegarde, fixtures Jeanne/CT et deuxième jeu,
   corpus de rejets et tests d'injection de panne.
2. **R59.B :** Release Center Qt lisant les diagnostics R39/R50/R59, avec
   affichage NO-GO obligatoire, matrice de plateformes et aperçu des notes.
3. **R59.C :** installation en emplacement versionné, journal d'activation,
   double slot Player, contrôle de signature, rollback automatique après
   crash et restauration explicite des sauvegardes précédentes.
4. Certification séparée : install/réinstallation/récupération PC propres
   tri-OS, conformité légale/redistribution et décision humaine.
