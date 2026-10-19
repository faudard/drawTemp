# DrawTemp R24.C — Packs de ressources versionnés, publication et intégrité

> **Statut : code en PR empilée après R24.B (#316) et R24.A (#296).** Ce lot constitue une première implémentation R24.4 et une tranche R24.11. Ne pas en déduire une certification 6.0, une validation juridique des droits, un système de signatures cryptographiques ou le gate R24.12.

## Architecture

Le pack est une archive ZIP inspectable et non exécutable. Elle contient exactement `pack.json` à la racine, plus un fichier par entrée déclarée sous `files/...`. Les ressources autorisées sont les kinds existants de `AssetRegistry` (`sprite`, `portrait`, `sound`, `animation`). Les animations référencent seulement les sprites déclarés par leur propre pack. Aucun script, binaire exécutable, callback plugin, nouveau renderer ni registre d'assets parallèle n'est autorisé.

Le manifeste a `schema_version: 1`, `id` (slug portable), `version` SemVer stricte `major.minor.patch`, `name`, `files`, `entries`, `dependencies`. Chaque fichier fournit un chemin relatif portable, la taille exacte, un SHA-256 hexadécimal et une déclaration de droits : `id`, `rights_holder`, `evidence`, `redistributable`, `modifiable`. Une autorisation de redistribution explicite est obligatoire ; elle n'est jamais inférée à partir d'un hash ou d'une extension de fichier.

Les dépendances sont `{"id": "base-pack", "version": "1.0.0", "sha256": "<64 caractères hexadécimaux>"}` : le pack dépendant ne s'importe que si le même ID/version/digest d'archive a déjà été installé dans ce projet. Pas de résolution implicite en ligne, ni mise à niveau automatique.

Les IDs sont préfixés par le slug de pack (`forest-pack.tree`). Les chemins sont préfixés par `assets/packs/<id>/<version>/...`. Les bindings de présentation existants restent inchangés, afin d'éviter de remplacer le personnage ou le terrain d'un projet silencieusement. Les collisions d'ID (insensibles à la casse), de chemins et de namespaces sont refusées.

## Publication déterministe

```python
from pathlib import Path
from drawtemp.assets.packs import publish_pack

# source/pack.json contient tous les hashes, licences et entrées ;
# les fichiers déclarés sont dans source/files/<chemin>.
preview = publish_pack(Path('source'), Path('forest-pack.rpack'))
print(preview.sha256)
```

La construction utilise une liste triée, des timestamps ZIP figés et l'écriture sans écraser une destination existante. Les octets source sont lus, contrôlés puis empaquetés ; toute modification de taille/SHA, référence inconnue, chemin dangereux, version future, licence absente ou archive trop volumineuse provoque un refus. Une publication déjà présente n'est pas remplacée.

## Inspection et installation réversible

```python
from drawtemp.sdk import AuthoringSession
from drawtemp.assets.packs import inspect_pack, install_pack

preview = inspect_pack('forest-pack.rpack')  # ne modifie rien
editor = AuthoringSession.open('game.json')
transition = install_pack(preview, editor, '.', expected_revision=editor.revision)
editor.save()  # sauvegarde explicite des Content/GameProject canoniques
```

`inspect_pack` lit et vérifie les membres déclarés et les SHA-256, avec limites : archive 64 Mio, 128 fichiers, fichier individuel 16 Mio, données décompressées 64 Mio, manifeste 256 Kio, maximum 512 entrées du registre et 32 dépendances. Les chemins de traversée, symlinks ZIP, fichiers inattendus, collisions insensibles à la casse et données non déclarées sont refusés.

`install_pack` revérifie l'archive sur disque, contrôle la révision de la session, prépare un `AuthoringSession.preview_project`, refuse les dépendances manquantes/collisions, publie uniquement des fichiers nouveaux, vérifie leur intégrité/signature technique, puis applique **une seule transaction** dans la session d'édition. Un échec ordinaire nettoie les nouveaux fichiers sans toucher aux anciens. Un crash brutal en milieu de copie peut laisser des orphelins mais ne peut pas réécrire Content/GameProject avant `apply` ; le nettoyage forensic de ces orphelins reste à améliorer.

Le reçu technique est **dans** `GameProject.extensions.org.drawtemp.resourcepacks`, via le contrat R24.A : chaque pack installé y conserve version, hash d'archive, chemins/hashes physiques, références d'assets et assertions de licence. Il n'y a pas de registre JSON annexe faisant foi. L'import ne modifie pas de sauvegarde GameSession, ne remplace pas les bindings de présentation et n'effectue aucune migration implicite de données v1→v2.

## Vérification avant export

`drawtemp.export.r15.preflight` lit les reçus R24.C et vérifie la présence, les chemins sûrs et SHA-256 de chaque fichier physique. Toute modification d'un PNG, WAV ou OGG après installation bloque l'export ; le contrôle `AssetRegistry.diagnostics` vérifie également la signature technique. Les projets anciens sans reçu R24.C continuent à emprunter le chemin de préflight existant, sans création automatique d'extension.

**Important :** les données de licence incluses dans le pack sont des affirmations du créateur du pack, pas une authentification du détenteur des droits. Le gate `asset-licenses.json` / `require_licenses=True` de R15 reste en vigueur pour la redistribution ; les déclarations R24.C ne génèrent ni une approbation légale ni une dispense de revue humaine. SHA-256 n'est pas une signature d'éditeur : R24.10 devra ajouter une chaîne de confiance/signature vérifiable et une politique de révocation.

## Politique de migration / compatibilité

- `schema_version: 1` seulement. Un schéma inconnu échoue explicitement sans altérer les fichiers.
- Les versions SemVer sont exactes ; remplacer un pack par une version différente sous le même ID n'est pas autorisé en R24.C sans une future migration explicite des assets et références.
- L'import est non destructif. Un développeur doit d'abord inspecter/mettre à jour les références métiers dans AuthoringSession lors d'une migration de pack.
- R24.C ne rajoute pas de backend serveur, marketplace, dépendances distantes ni protocole de diffusion de packs.

## Gates QA

```bash
python -m unittest tests_standalone.test_drawtemp5_r24c tests_standalone.test_drawtemp5_r24b tests_standalone.test_drawtemp5_r24a tests_standalone.test_drawtemp5_r15 tests_standalone.test_drawtemp5_r15_creator
```

Les tests fabriquent de vrais ZIP et PNG synthétiques pour vérifier stabilité binaire, hashes, publication sans écrasement, refus de ZIP malformé, import dans GameProject, dépendances, undo/redo, rollback, altération après import et préflight export. Le workflow CI R24.C est exécuté sur Linux, Windows et macOS (plus Python 3.10 sous Linux). Les résultats CI du SHA exact sont à confirmer avant toute fusion.

**Suite :** signatures et révocations (R24.10), migration de packs explicite et outillage UI (R24.4), scénarios de certification de deuxième univers (R24.9/12), puis R25 Game Modes Foundation.
