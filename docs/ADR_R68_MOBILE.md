# ADR R68.A-MOBILE — Études Android et iOS distinctes

**Statut : PROPOSED / NO-GO pour une annonce produit.** Date : 2026-10-20.

## Contexte et décision

Les APIs amont `pyside6-android-deploy` et `pyside6-ios-deploy` existent, mais DrawTemp épingle actuellement PySide6 6.8.3 pour Python 3.12 (extra Qt6) et utilise des chemins `Path.home()/.drawtemp` et des contrôles principalement desktop. Aucun portage ni build mobile du Player n'est démontré ici. **Pas de fork gameplay ; PC reste référence ; spikes mobiles isolés et optionnels.**

## ADR Android (scope séparé)

- Toolchain Linux/macOS, cross-wheel Android PySide6/shiboken6 pour l'ABI cible, SDK/NDK et version Python embarquée compatibles : vérifier la matrice **avec les versions réellement choisies**, pas seulement avec la dernière documentation Qt.
- Packaging APK/AAB et signature; inventaire libs/ressources et droits, permissions minimales, scan dépendances et taille.
- Entrées tactiles/gestes, densité d'écran, TalkBack, clavier/manette, safe areas; pause/reprise Android, perte de contexte graphique, tempête d'événements; stockage privé/SAF.
- Au moins deux téléphones physiques représentatifs, démarrage/installabilité, sauvegarde/replay CT/action et mesures CPU/GPU/mémoire/batterie. Un émulateur ne valide jamais ce gate.
- **Décision initiale : NO-GO produit, R68.B Android à envisager seulement après compatibilité de toolchain confirmée.**

## ADR iOS (scope séparé)

- Outil officiel `pyside6-ios-deploy` requiert macOS/Xcode et génère un projet à compiler/signer ; roues iOS correspondant à CPython et à chaque cible device/simulateur.
- Le flux documenté implique du **linkage statique**. Examiner, avec compétence juridique, obligations LGPL/GPL/Qt commercial, redistribuabilité et règles App Store avant un choix de packaging. Aucun avis de conformité n'est prononcé ici.
- Répertoire sandbox, backup, permissions `Info.plist` et descriptions d'usages, signature, provisioning/TestFlight, suppression/reprise app, import/export des sauvegardes.
- Touch et VoiceOver, tailles cibles, changements d'orientation, performance et chauffe réelles, au moins un iPhone et un iPad physiques avant GO.
- **Décision initiale : NO-GO produit ; dépendance supplémentaire à un audit licence/distribution signé.**

## Non-régressions et critères de sortie

Les deux expériences doivent prouver la même logique déterministe `GameSession`, format de save/roundtrip et contenu que sur PC; pas de nouveaux contrats de sauvegarde non versionnés. R39 demeure PC. R68.C rendra deux décisions signées indépendantes (GO/REDUCE/NO-GO) sur le SHA final, pas une certification dérivée d'un test CI.

Sources : https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-android-deploy.html ; https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-ios-deploy.html ; https://www.qt.io/development/open-source-lgpl-obligations
