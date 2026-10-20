# R76.B1 — Optimizer Studio (première tranche)

**État : implémenté en draft, non certifié.** Le volet R76.B de la
[roadmap 11.6→12.0](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md)
demande des propositions comparables, une preuve avant/après, une approbation
humaine et une annulation transactionnelle. Cette tranche apporte un premier
cas strictement **lossless** (fichiers byte-identiques) ; elle ne prétend pas
avoir résolu tous les autres cas R76.B ou la certification R76.C.

## Parcours intégré

Dans le Studio Qt, ouvrir **Outils → R76 • Optimizer Studio (assets)** ou
utiliser la palette de commandes. **Enregistrer le projet** au préalable.
Le dialogue construit un instantané du registre canonique du projet ouvert,
sans changer la révision de l'`AuthoringSession`.

1. **Analyser :** calculer le coût physique des fichiers, trouver les paires
   de contenus identiques SHA-256 + taille, partitionnés par extension / type
   d'asset. Les bindings, régions d'atlas et références d'animation gardent
   leurs identifiants logiques.
2. **Comparer :** table avant/après (chemin redondant → chemin canonique),
   octets économisables, digest. Pour les PNG, afficher deux aperçus
   simultanés ; comme les octets sources sont identiques, les pixels décodés
   proviennent du même contenu. Ceci **n'est pas** un golden artistique validé.
3. **Approuver :** cocher explicitement l'accord et choisir un **dossier neuf
   hors du projet original**. Un dossier provisoire privé est construit,
   vérifié puis renommé vers sa destination. Aucun remplacement si destination
   existante, sans écriture dans le répertoire source.
4. **Annuler la copie dérivée :** action dédiée du dialogue (distincte de
   l'Undo de l'`AuthoringSession`), uniquement si le reçu, le registre,
   les hashes de fichiers et les chemins attendus sont toujours inchangés.
   Si l'utilisateur a ajouté ou modifié un fichier, l'annulation est refusée
   au lieu de risquer sa suppression.

L'artefact contient :

```text
<destination-inédite>/
  registry.json     # AssetRegistry v1, copies des chemins dédupliquées
  receipt.json      # SHA de registre, coût constaté, fichiers, politique NO-GO
  assets/            # Une seule copie par chemin physique conservé
```

**Ce n'est pas un bundle de jeu exportable.** Aucun Content, GameProject,
Player exécutable, droits attestés sur la nouvelle distribution ni savegame
n'est présent. Les chemins du registre dérivé sont relatifs à `assets/`.
Les droits et provenance réels des fichiers restent gouvernés par le R15
strict et les règles de licence d'origine ; le reçu indique
`release_certified=false` et `rights=not_attested_for_derived_package`.

## Contrat headless

```python
from pathlib import Path
from sporebound.assets import AssetRegistry
from drawtemp.assets.optimizer import (
    plan_optimization, publish_derived_assets, undo_derived_assets,
)

registry = AssetRegistry(project["assets"])
review = plan_optimization(registry, Path("mon-projet"))
# Aucun changement tant que l'auteur n'a pas approuvé.
artifact = publish_derived_assets(
    registry, Path("mon-projet"), review,
    Path("nouveau-dossier-hors-projet"), approved=True)
# Annulation volontaire et vérifiée, sans toucher aux sources.
undo_derived_assets(
    Path(artifact["directory"]),
    expected_receipt_sha256=artifact["receipt_sha256"])
```

Le plan incorpore tous les hashes de fichiers et le SHA du registre source.
Si un seul input / lien / binding a évolué, l'application refuse le plan
périmé et requiert une nouvelle prévisualisation. Les copies sont recomparées
aux hashes attendus et le registre projeté est revalidé par
`AssetRegistry` puis par `diagnostics()`. Les symlinks, dossiers déjà
existants et destinations dans le projet source sont interdits.

Le coût annoncé se limite aux **octets des fichiers physiques** de l'artefact
dérivé : il exclut manifests, allocations CPU/GPU, encodage/packing natif,
latence I/O, distribution, qualité perçue, gameplay et compression réelle.
Aucune optimisation in-place et aucune modification des sauvegardes.

## Tests / gates

```sh
python -m unittest -v tests_standalone.test_r76_asset_audit \
  tests_standalone.test_r76b_optimizer
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest -v tests_standalone.test_r76b_optimizer_qt
```

- Tests headless : stabilité du plan, économie mesurée, publication
  atomique, refus d'absence d'approbation, stale-plan, symlinks, destination
  existante, copie modifiée et annulation sûre.
- Qt offscreen : écran, détails, activation par approbation, création et
  annulation, préservation de la révision Studio.
- Tri-OS/Python, PySide6 optionnel : la CI doit réellement lancer des jobs.
  Un workflow GitHub en échec avec **0 job** ne vaut pas exécution de tests.

### Suite R76.B2 / R76.C (NO-GO)

- Transformations PNG/audio **réelles** : décodage et comparaison pixels/audio,
  profils couleur/gamma, atlas partagés, cycles animation, goldens approuvés.
- Transaction d'export véritable avec plan de rollback compatible R15 droits,
  manifestes du Player, création de versions, réouverture et parité gameplay.
- Mesurer démarrage, bundle total, mémoire, qualité, CPU/GPU p50/p95/p99
  (avec variance, corpus, OS, matériel, pilote et SHA exact).
- Ne jamais transformer un rapport de validation locale en certification
  artistique, juridique, GPU ou en annonce de release.

**Décision : R76 release NO-GO**, même si R76.B1 a réussi ses tests unitaires.
