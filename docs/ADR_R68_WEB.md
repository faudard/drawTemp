# ADR R68.A-WEB — Étude de faisabilité du Player navigateur

**Statut : PROPOSED / NO-GO pour une annonce produit.** Date : 2026-10-20.

## Contexte

DrawTemp repose sur un cœur Python, `GameSession`, la simulation/replay et un Player Qt Quick via PySide6. Qt for WebAssembly permet des applications Qt compilées en WASM à partir de C++ ; cela ne rend pas automatiquement ce Player Python exécutable dans un navigateur. R39 interdit explicitement le Web comme cible de publication.

## Décision d'architecture provisoire

Ne pas créer de second moteur gameplay ni prétendre que PySide6 est disponible sur WASM. Avant toute UI Web : prouver sur un spike isolé comment exécuter exactement les contrats de tick/replay, comment transporter contenu et saves, et comment dessiner via la même projection sans réimplémentation divergente. Faute de runtime reproductible, **NO-GO**, possibilité de réduire le scope à viewer statique non jouable, identifié comme tel.

## Gate de preuve spécifique Web

- Versions précises Qt, Emscripten, Python/WASM (si utilisé), navigateur/OS/GPU, provenance et revue de licence.
- Démarrage froid, taille téléchargement, démarrage hors connexion, compatibilité navigateur, politique CSP/COOP/COEP si threading.
- Mapping clavier, manette et tactile, focus/safe area, visibilité suspendue, reprise sans pas de simulation perdu ni doublé.
- Stockage persistant non-Posix : quotas, effacement, export/import, checksum sauvegarde et continuité du replay.
- Mesures FPS p50/p95/p99, stabilité WebGL, mémoire, latence d'input; accessibilité, tests sur machine physique et documentation des échecs.

## Alternatives écartées à ce stade

- Transposer les fichiers Python en JS sans preuve de parité : risques de divergence replay et duplication cœur.
- Considérer un smoke test Qt/WASM C++ ou navigateur headless comme une certification DrawTemp.
- Lier le Studio aux services distants ou modifier R39 pour accepter `web` sans Player validé.

## Revue et coût

Recherche conditionnée par R39/R57/R59/R60. Estimation chiffrée uniquement après spike ; maintenance navigateurs, dépendances et hébergement sont des coûts ouverts. Pas de décision GO automatique issue du vérificateur de preuves.

Sources : https://doc.qt.io/qt-6/wasm.html ; https://doc.qt.io/qtforpython-6/deployment/index.html
