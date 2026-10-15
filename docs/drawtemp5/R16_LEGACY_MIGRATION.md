# DrawTemp 5.0 — R16 Migration finale & Legacy Cleanup

> **Statut : en cours / non certifié.** Cette PR amorce R16 sans prétendre
> que R15 (distributions autonomes), R14 (preuves hardware et E2E), ni les
> remplaçants Qt sont déjà validés. La suppression des clients Tk serait
> actuellement dangereuse pour les projets utilisateurs existants.

## Tableau de suivi

| Lot | Statut | Preuve / condition de clôture |
| --- | --- | --- |
| R16.1 — Legacy Inventory | Implémenté (statique) | `scripts/inventory_drawtemp5_legacy.py` : imports Tk, appels Canvas, imports transitoires `sporebound`, entrypoints |
| R16.2 — Project Migration | Première tranche | Bundle versionné avec paire canonique v1 validée, empreintes SHA-256 et originaux bit-à-bit ; pas de conversion imaginaire vers un schéma v2 |
| R16.3 — Save Compatibility | Première tranche | Import explicite **uniquement** des `game_session` v1 et `session_checkpoint` v2 vérifiés par le runtime/replay, sans réécriture ; autres formats refusés avec motif |
| R16.4 — Renderer Retirement | Bloqué | Équivalence GPU/caméra/picking/goldens R3, R12 et R14 démontrée sur machines réelles |
| R16.5 — Studio Retirement | Bloqué | Atelier Qt de remplacement vérifié, parcours sans JSON, Undo/Redo + import/export; R15 packaging validé |
| R16.6 — Namespace Cleanup | Conservation transitoire | `sporebound` demeure le namespace moteur compatible ; pas de suppression ni de changement de format de sérialisation |
| R16.7 — Documentation Cleanup | Première tranche | Ce guide et README 5.0 ; le corpus Tk historique est conservé comme référence legacy |
| R16.8 — Final Regression | Première tranche | Tests `test_drawtemp5_r16.py` et CI Linux/Windows/macOS ; certification R14/R15 et épreuves de distribution encore à produire |

**Gate officiel R16 non atteint :** le Player/Studio livré ne doit plus dépendre
de Tk, tous les formats explicitement supportés doivent pouvoir être migrés sans
perte et la restauration doit être éprouvée. Un contrôle statique « 0 import Tk
dans `drawtemp/` » ne prouve ni les imports transitifs, ni les plugins chargés
dynamiquement, ni les dépendances contenues dans le packaging.

## 1. Inventaire du legacy (R16.1)

```bash
python scripts/inventory_drawtemp5_legacy.py --report r16-inventory.json --fail-on-qt-tk
```

Le rapport donne les modules sources concernés, lignes, imports de compatibilité
et lanceurs déclarés. Les modules `sporebound/` sont inventoriés et **ne sont
pas supprimés** : `drawtemp.core` et le gameplay en utilisent toujours les
contrats. Aucun renommage arbitraire de classe Python sérialisée n'est réalisé.

## 2. Migration de projet avec originaux et rollback (R16.2)

```bash
# Aperçu 100 % lecture seule
python -m drawtemp.sdk.legacy_migration project \
  --content /jeux/jeanne.json --dry-run

# Produit un dossier qui n'existait PAS auparavant
python -m drawtemp.sdk.legacy_migration project \
  --content /jeux/jeanne.json --destination /migrations/jeanne-r16

# Restaure les octets initiaux à un NOUVEL emplacement, sans écraser les projets
python -m drawtemp.sdk.legacy_migration rollback \
  --bundle /migrations/jeanne-r16 --destination /migrations/jeanne-original
```

Structure du bundle :

```text
jeanne-r16/
  receipt.json                   # version migration, chemins, SHA-256, provenance
  originals/jeanne.json          # copie exacte, non reformattée
  originals/jeanne.game.json
  project/jeanne.json            # documents validés / normalisés au schéma v1
  project/jeanne.game.json
```

La paire est validée contre les **vrais contrats** `Content` et `GameProject`
du moteur avant publication. Écriture par staging puis publication du dossier.
Une destination existante ou un original modifié pendant la conversion bloque
l'opération. Le rollback vérifie **les quatre** empreintes (originaux et fichiers
publiés) et restaure les originaux dans un nouveau répertoire. Les sauvegardes
et profils existants ne sont jamais déplacés automatiquement.

**Limite actuelle :** seul le couple canonique Content v1 / GameProject v1 est
admis. Les structures propriétaires plus anciennes, les éventuels formats
pré-v1 et les données inconnues exigent un convertisseur nommé, testé sur
fixtures réelles; aucun schéma de contenu 5.0 divergent n'est introduit.

## 3. Import de sauvegardes explicite (R16.3)

```bash
python -m drawtemp.sdk.legacy_migration inspect-save \
  --save /saves/session.json --content /jeux/jeanne.json

python -m drawtemp.sdk.legacy_migration import-save \
  --save /saves/session.json --content /jeux/jeanne.json \
  --destination /saves/importees/session-1.json
```

L'import ne commence qu'après validation du checksum, du contenu, du manifeste,
des règles et du replay par le même runtime. Le fichier copié garde **exactement
les mêmes octets**, le source est préservé, la destination doit être libre et
aucun repli silencieux vers `.bak` n'est autorisé.

Formats actuels :

- **Pris en charge :** `game_session` version 1 (session brute),
  `session_checkpoint` version 2 (enveloppe SessionStore).
- **Non pris en charge :** slots historiques `PlayerSession`, archives
  `LongSessionStore`, replays Battle/Scenario isolés, sauvegardes utilisant
  des règles/contenus différents. **Aucune conversion trompeuse** : conserver
  le runtime et les données d'origine, puis développer un adaptateur dédié.

L'import n'est **pas** une reprise automatique dans le Player 5.0 : il place
une copie vérifiée à l'emplacement choisi, à intégrer explicitement au système
de slots concerné.

## 4. Certification finale (R16.4 à R16.8)

```bash
python -m unittest tests_standalone.test_drawtemp5_r16 -v
python scripts/inventory_drawtemp5_legacy.py --fail-on-qt-tk
```

CI : `.github/workflows/drawtemp5-r16.yml` sur les trois OS, Python 3.12.
Cette matrice prouve les cas unitaires en environnement propre **mais pas**
les seuils GPU ni une distribution installable.

Avant de supprimer des fichiers `sporebound.editor`, `sporebound.player_app`,
`sporebound.tk_renderer`, `sporebound.exploration_iso_view` et les panneaux
Tk, fournir au minimum :

1. Une **release R15** installée et testée sans environnement Python/Studio,
   avec assets et licences, et un parcours Jeanne complet.
2. L'audit des imports **transitifs et runtime** du binaire Studio et Player
   (0 Tk), les contrôles QA R14 complets et les goldens GPU multi-OS.
3. Des fixtures migrées d'anciens projets, profils, slots et replays réels,
   avec tests de parité avant/après et rollback d'une migration interrompue.
4. Les chemins de compatibilité nécessaires, avertissements de dépréciation
   puis calendrier de retrait du namespace `sporebound` documentés.
5. Mise à jour des entrypoints et du packaging, sans briser les intégrations
   Python existantes, et une campagne de régression finale sur le dernier SHA.

**Décision de migration :** sécuriser les données et mesurer la dette maintenant;
ne retirer le legacy qu'après preuve d'équivalence et passage du gate R15.
