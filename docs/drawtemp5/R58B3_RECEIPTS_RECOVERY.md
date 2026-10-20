# R58.B3 — Provenance des dépendances et journal de reprise

**Statut : tranche B3.1 implémentée, à valider sur CI et en conditions réelles.**
R58.B complet et R58.C restent **NO-GO**.

## 1. Reçus R24.C sans rupture de schéma

Nouveaux reçus de `org.drawtemp.resourcepacks` : champ additionnel
`dependencies` avec les dépendances directes déclarées par l'archive :
`[{ "id": "...", "version": "1.0.0", "sha256": "..." }]`.

- L'enveloppe GameProject `schema_version:1` ne change pas et le
  `AssetRegistry` demeure l'unique registre des ressources.
- **Reçus historiques sans cette clé = dépendances inconnues**.
  Ne pas interpréter une absence comme une liste vide ; les opérations
  dépendantes d'un graphe complet restent interdites.
- Les nouveaux reçus déclarent explicitement `dependencies: []`
  lorsqu'ils sont autonomes.
- `verify_installed_packs` vérifie les références existantes,
  les identités version/SHA exactes, les dépendances dupliquées, les
  auto-dépendances et les cycles, en plus des fichiers et licences R24.C.
  Les incohérences invalident également le préflight d'export existant.
- Les reçus ne sont **pas des signatures**. Une personne malveillante
  modifiant le GameProject peut supprimer des métadonnées : le Studio
  traite alors le graphe comme inconnu. L'authenticité cryptographique
  de l'éditeur et les droits de redistribution restent non certifiés.

## 2. Retrait et mise à jour d'un pack feuille

Le Studio analyse les **dépendances inverses** :
- Si toutes les arêtes sont déclarées et valides, un pack sans
  consommateur peut être retiré, même en présence d'autres packs.
- S'il a un consommateur, l'état montre `required-by:<id>` et
  le retrait ou la mise à jour est bloqué.
- Si plusieurs packs contiennent au moins un reçu historique sans
  `dependencies`, l'opération est bloquée (précaution sur les
  dépendances inconnues).
- L'upgrade vers une nouvelle version ne doit pas changer les
  dépendances directes du pack remplacé : mêmes IDs, versions et
  SHA-256. Un changement nécessite un protocole de migration
  multi-packs distinct.
- Toute mise à jour conserve les IDs et kinds d'assets et passe
  par `AuthoringSession` (une transaction Undo), sans sauvegarde
  disque automatique ni suppression d'ancien fichier.

## 3. Marqueur persistant avant copie

Avant la création des fichiers d'une nouvelle version, le moteur écrit
`.drawtemp-r58-package-upgrade.pending.json` avec création exclusive,
permissions restrictives, `fsync`, projet/version/empreintes,
liste bornée des fichiers attendus et SHA du snapshot source.

- Si le processus s'arrête pendant la copie, le marqueur persiste :
  les prochaines opérations du Package Manager et les imports R24.C
  refusent de continuer avant revue (`recovery_required`).
- **Reprise après interruption…** dans le dialogue Qt montre pour
  chaque fichier `verified`, `missing`, `mismatch` ou
  `unsafe-link`/`unsafe-type`.
- L'acquittement est explicite, avec un SHA du journal et une
  identité de pack encore cohérente dans la session. Il **ne supprime
  aucun asset** et ne restaure pas automatiquement de version.
- Une version déjà entièrement copiée peut ensuite être réutilisée
  si un nouvel aperçu revalide chaque fichier/empreinte de l'archive.
- Une version **partiellement** copiée continue de bloquer son propre
  chemin : revue et nettoyage manuel avant nouvel essai.
- Lors d'une exception Python ordinaire pendant l'application,
  les fichiers créés sont nettoyés selon la politique B2 et le
  journal est clôturé. En cas de fin brutale, le journal reste.

### Limites de durabilité

Il s'agit d'un **journal de détection et de reprise explicite**, pas
d'une transaction distribuée atomique entre système de fichiers,
GameProject sauvegardé et Undo/Redo du Studio. Le marqueur peut
subsister alors que la modification mémoire a réussi mais que la
sauvegarde disque n'a pas eu lieu ; la validation de la session
active et l'acquittement restent nécessaires. N'effacez pas des
répertoires sans vérifier les références des sauvegardes externes.

Les anciens reçus ne sont pas rétroactivement attestés. Il n'existe
pas encore d'upgrade coordonné multi-packs qui remappe les assets
ou renouvelle un pin exact chez tous ses consommateurs.

## Tests de régression

```sh
python -m unittest \
  tests_standalone.test_drawtemp5_r24c \
  tests_standalone.test_drawtemp_r58a_package_ecosystem \
  tests_standalone.test_drawtemp_r58b_package_manager \
  tests_standalone.test_drawtemp_r58b_upgrades \
  tests_standalone.test_drawtemp_r58b3_dependencies \
  tests_standalone.test_drawtemp_r58b3_recovery
```

Test Qt offscreen optionnel :

```sh
QT_QPA_PLATFORM=offscreen python -m unittest \
  tests_standalone.test_drawtemp_r58b_qt
```

La validation CI multi-OS et GUI humaine doit être effectuée **sur le
SHA final** ; ne pas conclure au succès lorsqu'un workflow échoue
sans exécuter de jobs.

## Prochain incrément

**R58.B4** : véritable transaction multi-pack en deux phases avec journal
de reprise et autorité de sauvegarde durable, migrations explicites
ID/kind/path, remappage des dépendances et collecte d'orphelins fondée
sur les références. **R58.C** : personnage/HUD/quête réutilisés dans
deux jeux avec une provenance et un export contrôlés.
