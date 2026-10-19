# DrawTemp 5.5 — R23.D : installateurs système natifs (préversions non signées)

> **État : engineering preview / NO-GO.**
> Les scripts construisent réellement des installateurs natifs, mais aucun
> secret de signature, certificat Authenticode, Apple Developer ID ou
> dépôt Linux signé n'est ajouté ni simulé.

R23.D suit les PR R23.A (#297) → R23.B (#312) → R23.C (#326).
R23.C livre un arbre `DrawTemp/{Jeanne,Studio,release.json}` cryptographiquement
inventorié. R23.D ne réécrit ni le moteur, ni la sauvegarde, ni la
validation des assets de R15 ; il transforme **le même arbre vérifié**
en conditionnement natif puis l'éprouve sur une autre machine CI.

## Livrables

| Plateforme | Générateur | Artefact | Installation/désinstallation |
| --- | --- | --- | --- |
| Windows x64 | **Inno Setup 6** depuis `packaging/r23d/drawtemp-preview.iss` | `DrawTempStudio-5.5-preview-Windows.exe` | Per-user, silencieuse `/VERYSILENT`, fichiers et raccourcis menu Démarrer ; `unins000.exe` |
| Linux Debian/Ubuntu amd64 | **dpkg-deb** (répertoire FHS) | `DrawTempStudio-5.5-preview-Linux.deb` | `dpkg -i` / `dpkg --purge`, sous `/opt/drawtemp-studio-preview`, launchers dans `/usr/bin`, `.desktop` |
| macOS | **hdiutil** + bundle `.app` avec `Info.plist` | `DrawTempStudio-5.5-preview-macOS.dmg` | Montage image, copie `.app` dans un dossier utilisateur, détachement, suppression de l'application |

Chaque paquet contient les fichiers Player natifs, les fichiers jeu
Jeanne et le Studio natif (PyInstaller **onedir**) ; il n'exige pas
l'installation d'un Python utilisateur. Les utilitaires de *build*
et les rapports de QA, eux, utilisent Python 3.12 dans la CI.

Les lanceurs sont :

- Windows : `Studio/DrawTempStudio.exe` et
  `Jeanne/Player/DrawTempPlayer.exe`
- Debian : `/usr/bin/drawtemp-studio-preview` et
  `/usr/bin/drawtemp-player-preview`
- macOS : `DrawTemp Studio 5.5 Preview.app/Contents/MacOS/DrawTempStudio`
  et Player dans `Contents/Resources/Jeanne/Player/`

Sur macOS, un seul bundle graphique `.app` contient le Studio, ainsi
qu'un Player invoquable séparément par le chemin interne. Une application
Player autonome avec icône et signature distincte reste un travail futur.

## Construire un paquet

Sur chaque OS **depuis le même commit Git** et après le build PyInstaller
et l'archive vérifiée R23.C :

```bash
python scripts/r23d_native_installer.py \
  --source r23d-stage \
  --output release/DrawTempStudio-5.5-preview-Linux.deb \
  --platform Linux \
  --revision "$(git rev-parse HEAD)" \
  --report release/r23d-builder.json
```

L'utilitaire appelle `verify_portable` sur la racine de stage, exige
l'OS et le SHA exact, refuse d'écraser un livrable existant, exécute
l'outil système correspondant et crée un `.sha256` indépendant.
Les résultats du build enregistrent `signed=false`,
`notarized=false`, `certification=preview-NO-GO`.

Pré-requis : **ISCC.exe Inno Setup 6** sur Windows, **dpkg-deb**
sur Linux et **hdiutil** sur macOS. L'intégration GitHub Actions
installe Inno Setup sur le runner Windows ; les autres utilitaires sont
fournis par leurs runners systèmes.

## Test d'installation réellement exécuté en CI

Le workflow `.github/workflows/drawtemp5-r15.yml` :

1. Construit R15 puis R23.C, déballe une distribution R23.C vérifiée,
   et génère le paquet natif R23.D (et sa somme SHA-256).
2. Transfère le paquet sur un **runner séparé**, sans checkout du projet,
   `pip install` ni préparation Python supplémentaire.
3. Vérifie les octets de l'installateur à l'aide du `.sha256`.
4. Installe le paquet avec l'outil propre à l'OS.
5. Démarre le vrai **Player** en titre puis exploration, puis le vrai
   **Studio** avec `--smoke`, en Qt `offscreen`.
6. Falsifie le JSON canonique dans le Player installé. Le prochain
   démarrage **doit échouer avec un diagnostic d'intégrité**.
7. Exécute la désinstallation et vérifie la disparition du produit.
8. Crée un `r23d-clean.json` avec résultats et commit exact.
9. Agrège Windows/Linux/macOS et le registre de la **même révision** R23.C.
   `scripts/r23d_release_gate.py` produit toujours
   `decision=NO-GO` et `release_certified=false`.

Un runner GitHub hébergé dispose de logiciels et services préinstallés,
et l'environnement de test Qt est logiciel/offscreen. Cela ne garantit
ni le comportement d'un véritable PC vierge, ni une installation
hors ligne, ni l'accès GPU, ni la compatibilité d'un parc utilisateur
complet. Windows teste un installateur par utilisateur ; Linux un vrai
paquet système ; macOS une installation par copie, pas un installateur
automatisé de type PKG.

## Critères de sécurité et de publication bloquants

- **Windows** : Authenticode avec certificat approuvé,
  SmartScreen/réputation, vérification `signtool verify` et publication
  d'empreintes signées.
- **macOS** : codesign Hardened Runtime sur les exécutables et
  dépendances, Developer ID, notarisation `notarytool`, staple,
  `spctl --assess`, tests Gatekeeper sur une machine propre.
- **Linux** : signature des paquets/repository (ou provenance attestée),
  tests de dépendances et installation sans accès réseau à partir
  d'images OS qualifiées. Les `.deb` de ce PR ne sont **pas signés**.
- **Fonctionnel** : vrais parcours d'auteur et de joueur, import d'assets,
  fermeture/reprise de parties, crash/recovery, sauvegardes isolées des
  données installées, désinstallation sans altérer les sauvegardes.
- **Légal** : attribution, dépendances et licences des assets revues
  par des personnes habilitées.
- **Qualité** : endurance, accessibilité et playtests R23.B sur matériels
  physiques, suivi et retest de chaque anomalie P0/P1.
- **Release** : revue humaine signée R23.12 après vérification de chacune
  des 12 exigences de la roadmap.

Des certificats ou secrets ne doivent pas être ajoutés au dépôt ni aux
artefacts CI. Les flux de signature peuvent être réalisés séparément,
après autorisation et provisionnement sécurisé.

## Tests

```bash
python -m unittest tests_standalone.test_drawtemp5_r23d -v
python -m unittest tests_standalone.test_drawtemp5_r23c -v
```

Les tests R23.D couvrent en particulier l'inventaire réel d'un paquet
Debian (sur Linux), le refus d'écraser une sortie et l'interdiction de
fabriquer une réussite si un OS manque ou si une installation, un test
de falsification ou une désinstallation a été ignoré.
