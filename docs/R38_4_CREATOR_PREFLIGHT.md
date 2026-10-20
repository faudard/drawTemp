# DrawTemp R38.4 — Preflight continu du projet (P0)

**Statut : lot en PR, non certifié.** R38.4 ajoute un audit **en lecture seule** du Content/GameProject courant. Le précontrôle ne publie pas de Player, n'écrit pas les fichiers, ne migre aucun schéma et ne délivre **aucune** certification de release.

## Périmètre R38.4A

- Revalidation canonique via `sporebound.studio_transaction.validate_pair` : événements R9, cycles de dépendances, références physiques de portes/interactions, cinématiques, campagnes, monde, assets déclarés, extensions validées, schémas connus. Les erreurs canoniques bloquent l'audit ; le rapport signale alors qu'il est incomplet.
- Audit de références typées R49 réutilisé : références absentes localisées avec la source. Les budgets de parcours tronqués sont **bloquants** ; aucun résultat partiel n'est déclaré conforme.
- Convergence R31 : chaque graphe visuel compilé doit correspondre **exactement** aux événements R9 générés dans la même mission. Une édition divergente du déclencheur natif bloque la prévisualisation. La vérification ne construit pas de nouvel exécuteur.
- Porte sans case adjacente libre : **avertissement** `door_sealed` et chemin vers l'objet ; une porte à ouverture distante peut être intentionnelle. Les portes avec mauvais liens, triggers et géométrie sont bloquées par les validateurs existants.
- Assets : sans racine disque, aucun succès d'intégrité de fichiers n'est revendiqué si des fichiers physiques existent ; avec racine, réutilisation d'AssetRegistry.diagnostics pour fichiers manquants, signatures incorrectes, atlas et traversées hors projet.
- Droits : réutilisation du validateur R15/R17 `_check_asset_rights`, y compris `asset-licenses.json`, hash SHA-256 lié à chaque fichier, statut, redistribution, modification et preuve sous `licenses/`. Cela vérifie la **cohérence technique des attestations**, jamais leur validité juridique.
- `report["content_sha256"]` et `project_sha256` empreignent les deux dictionnaires inspectés ; `revision` indique la révision R1 éventuelle. Aucune prétention de correspondance avec un commit Git ni à un export déjà écrit.

## API

~~~python
from drawtemp.sdk.r38_preflight import inspect_project

report = inspect_project(session.snapshot())  # sans accès disque
report = inspect_project(
    session.snapshot(),
    asset_root=project_dir, require_licenses=True,
)
for issue in report["issues"]:
    print(issue["severity"], issue["code"], issue["path"], issue["message"])
if not report["ready_for_preview"]:
    raise ValueError("Preflight Creator Tools non validé")
~~~

Champs du rapport : `schema`, `kind`, `revision`, empreintes Content/GameProject, `passed` (contrats inspectés), `ready_for_preview` (validation + fichiers + droits lorsque strict), `complete` (scan non tronqué), `asset_integrity_verified`, `rights_verified`, `release_certified=False`, `errors`, `warnings`, `issues` typées et `counts`.

Par défaut, un projet canonique sans assets passe l'audit sans racine disque. Avec assets mais sans `asset_root`, `passed` peut être vrai tout en ayant `ready_for_preview=False`. L'option `require_licenses=True` bloque également l'audit si les preuves nécessaires ne peuvent pas être vérifiées.

## UI Studio

**Outils → R38 • Preflight du projet…** : lecture de l'état actuel non sauvegardé, sélection facultative de la racine des assets, mode strict des droits, bouton **Réanalyser le projet**, liste erreurs/avertissements avec chemin source. Cette interface ne corrige ni ne supprime aucune donnée automatiquement.

## Contrats et gates

1. Determinism : même snapshot et même racine immobile donnent le même rapport.
2. Atomicité : analyse read-only ; aucune mutation même en échec.
3. Références : passe uniquement en cas de scan complet et de champs typés résolus.
4. Graphes : détecter un événement R9 natif édité indépendamment de son graphe R31.
5. Assets : fichier absent et signature invalide bloquent `ready_for_preview`.
6. Licence : absence, attestation périmée ou evidence manquante bloquent le mode strict.
7. Porte close : avertir sans inférer un softlock lorsque l'ouverture peut être scriptée.
8. Qt : ouverture/fermeture/réanalyse sans changement de révision.
9. Aucun faux statut `release_certified` : R14, exécution sur machines propres et provenance légale restent hors périmètre.
10. Workflow CI Ubuntu/Windows/macOS ; tests R38.1–R38.3 et R17 droits réutilisés.

### Exécution

~~~sh
python -m unittest tests_standalone.test_drawtemp_r38_preflight.PreflightTests -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r38_preflight.PreflightQtTests -v
python -m unittest tests_standalone.test_r17_asset_rights -v
~~~

Les tests doivent effectivement passer avant toute fusion. GitHub Actions peut refuser des workflows avant même de créer des jobs : dans ce cas, **aucun test n'est validé**.

## Limites explicites

R38.4A ne calcule pas encore l'accessibilité géométrique exhaustive d'un donjon ni la faisabilité des énigmes. Ne pas déduire une « absence totale de softlock » d'un simple scan de portes. La validation des scripts/packs liés à l'export et les rapports CI liés au SHA seront approfondis en R38.4B et R38.5.
