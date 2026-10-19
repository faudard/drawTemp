# DrawTemp 5.5 — R23.C : archives natives portables et bilan Go/No-go

> **Version : prévisualisation (NO-GO).** Les livrables de cette PR ne sont
> **ni des MSI**, **ni des DMG notarizés**, **ni des paquets DEB/AppImage signés**.
> L'exécution du Player et du Studio est native/PyInstaller et ne nécessite pas
> Python chez le joueur, mais les utilitaires de conditionnement utilisent
> la bibliothèque standard Python sur les machines de construction/QA.

## Contexte et choix

La chaîne R15 fige déjà le Player et le Studio sur Windows, macOS et Linux ;
R17.8 démontre un Player délocalisé lancé sur un second runner. R23.A ajoute
le verrouillage des manifests et R23.B les mesures d'endurance/accessibilité.
R23.C réunit ces éléments en une **archive portable de deux applications**
avec inventaire complet et test de l'archive reçue hors du checkout.

Aucun second moteur, sérialiseur de combat, changement de sauvegarde, faux
avis légal ou migration opportuniste n'est introduit.

## Produits techniques

| OS du build | Livrable non signé | Entrées |
| --- | --- | --- |
| Windows | `r23c-Windows.zip` | `DrawTemp/Jeanne/Player/DrawTempPlayer.exe`, `DrawTemp/Studio/DrawTempStudio.exe` |
| Linux | `r23c-Linux.tar.gz` | `DrawTemp/Jeanne/Player/DrawTempPlayer`, `DrawTemp/Studio/DrawTempStudio` |
| macOS | `r23c-macOS.tar.gz` | `DrawTemp/Jeanne/Player/DrawTempPlayer`, `DrawTemp/Studio/DrawTempStudio` |

Chaque archive comprend `DrawTemp/release.json` :

- SHA complet du commit, OS ciblé et désignation explicite
  `certification=preview-NO-GO` ;
- inventaire canonique de tous les fichiers, taille, mode et SHA-256 ;
- SHA-256 de l'ancien `Jeanne/manifest.json`, sans réécrire R15 ;
- état `signature=not-asserted` et avertissements de licences conservés.

Un fichier externe `<archive>.sha256` assure le contrôle des octets transférés.
**SHA-256 n'atteste jamais l'identité de l'éditeur.** Il faut obtenir
l'empreinte par un canal de confiance.

La création/installation refuse les chemins absolus, traversals, doublons
et collisions insensibles à la casse, liens symboliques et fichiers spéciaux.
L'extraction est bornée (20 000 membres, 512 Mio/membre, 4 Gio décompressés).
L'installation utilise un dossier temporaire puis un renommage vers une
cible neuve. Ni sauvegardes ni répertoires utilisateur ne sont modifiés.
Une installation existante n'est pas remplacée. La suppression explicite
n'efface que la distribution préalablement vérifiée.

## Commandes de prévisualisation

```bash
# Sur la machine de build, après compilation native R15 :
python scripts/r23c_distribution.py package \
  --game export/Jeanne --studio dist/DrawTempStudio \
  --output release/r23c-Linux.tar.gz \
  --platform Linux --revision "$(git rev-parse HEAD)"

# Exemple : contrôle du SHA de l'archive par un canal de confiance
sha256sum -c release/r23c-Linux.tar.gz.sha256

# Installer sans écraser un répertoire préexistant :
python scripts/r23c_distribution.py install \
  --archive release/r23c-Linux.tar.gz \
  --sha256 "$(cut -d ' ' -f1 release/r23c-Linux.tar.gz.sha256)" \
  --revision "$(git rev-parse HEAD)" --platform Linux \
  --destination /tmp/drawtemp-portable

python scripts/r23c_distribution.py verify --destination /tmp/drawtemp-portable
python scripts/r23c_distribution.py remove --destination /tmp/drawtemp-portable
```

Ces commandes sont **des utilitaires QA**, pas des installateurs système.
L'utilisateur peut également extraire l'archive avec les outils habituels
de son OS, puis exécuter les deux applications natives. Un paquet signé
avec raccourcis, intégration OS, installation/désinstallation système et
mise à jour reste à créer/certifier ultérieurement.

## Preuves CI et limites explicites

`.github/workflows/drawtemp5-r15.yml` ajoute après le build R15 :

1. packaging et test local du nouveau protocole sur chaque OS ;
2. transfert de l'archive à un **runner GitHub hébergé distinct**, sans
   checkout du dépôt ni installation du Studio ou d'une wheel ;
3. vérification du fichier `.sha256`, extraction, lancement du Player en
   modes titre/exploration, lancement du Studio avec `--smoke` ;
4. modification du contenu exporté puis **refus obligatoire** par le Player ;
5. suppression de l'arborescence portable et vérification de sa disparition ;
6. rapport JSON par plateforme avec SHA Git, hash archive et résultats ;
7. agrégation des trois OS et du registre R23.A sur le **même SHA**.

Sur runner Windows, l'outil d'extraction CLI préinstallé peut utiliser Python ;
les **binaires d'application eux-mêmes** sont lancés sans Python installé
par ce workflow. Les runners hébergés ont une couche logicielle préinstallée
et accès au réseau ; ce n'est donc pas une preuve d'installation sur OS nu,
environnement volontairement hors ligne, GPU matériel vérifié ou installateur
notarizé. Linux installe uniquement les bibliothèques système Qt documentées.
Les rendus CI utilisent `QT_QPA_PLATFORM=offscreen` et le backend logiciel.

## Bilan final (toujours NO-GO)

`scripts/r23c_release_gate.py` vérifie trois rapports
`r23c-clean.json`, sans doublon, sur un SHA exact. Il refuse les déclarations
inventées de signature ou d'installation native. Le registre R23.A est
accepté uniquement s'il correspond à la même révision ; le registre
R23.B peut être ajouté explicitement lorsqu'il existe pour **le même SHA**.
Une exécution de deux workflows sur des SHAs différents ne saurait être
combinée pour « certifier » une release.

| Gate | Apport de R23.C | Manques |
| --- | --- | --- |
| R23.1 | Extraction/suppression portable sur 3 OS | Signatures, installateurs système, raccourcis, désinstallation OS |
| R23.2 | Deux exécutables lancés hors checkout, tamper fail-closed | Parcours complet sur PC propre sans réseau, assets/licences validés |
| R23.4 | Validation de distribution + contrôle archives bornées | Fuzz plus large et corpus d'imports du Creator |
| R23.6–8 | Peut intégrer un rapport R23.B sur SHA égal | Sessions de plusieurs heures, audits a11y et retests humains |
| R23.10 | Avertissements de licence conservés | Titularité et permissions de redistribution approuvées |
| R23.11 | Checksums et provenance par SHA | Signatures/notarisation, reproductibilité attestée, changelog final |
| R23.12 | Registre formel des 12 exigences | Validation humaine signée, aucun P0 bloquant |

Tant que ces manques restent ouverts, `decision=NO-GO`,
`certified=false` et le projet **ne doit pas publier DrawTemp 5.5 stable
sur la seule base de cette CI**.

## Tests

```bash
python -m unittest \
  tests_standalone.test_drawtemp5_r15 \
  tests_standalone.test_drawtemp5_r23a \
  tests_standalone.test_drawtemp5_r23c \
  tests_standalone.test_drawtemp5_r23c_release -v
```

Les scénarios incluent extraction hostile (traversal, liens, doublons),
absence du Studio, falsification du contenu, archive corrompue,
mauvaise version, refus d'écraser et suppression contrôlée.

**Travail post-R23.C :** produire des installateurs signables Windows
(MSI/EXE), Linux (DEB/AppImage) et macOS (.app/.dmg), puis les faire tester
sur VM/PC vierges, auditer les dépendances et la légalité des assets, exécuter
les parcours entiers et obtenir une décision Go/No-go humaine.
