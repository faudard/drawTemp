# R70.A — Genre Expansion Certification : socle de vérification

**Statut : lot R70.A préparatoire, non certifié.** La PR #289 est une roadmap documentaire déjà fusionnée. Ce lot n'annonce ni jeux R61–R66 terminés ni release 11.0 validée.

## Périmètre et garanties

- `drawtemp.quality.r70_genre_certification.required_evidence()` décrit une matrice vérifiable et exhaustive : dépendances R50/R60–R66, régressions SRPG et action-aventure, quatre graines déterministes pour chacun des **trois** nouveaux genres (gestion, vie quotidienne, survie/action), migrations et formats de sauvegarde, création no-code, export, budgets, droits d'assets, tests sur Windows/Linux/macOS, GPU physique, machines propres, sécurité, QA et approbation humaine.
- `audit_seeded_replay(execute, ...)` exécute deux fois **le vrai runner fourni par le moteur** pour chaque graine, vérifie les empreintes d'état tick par tick, la restauration du dernier état et les budgets bornés d'agents/cellules. Ce helper ne fabrique pas de moteur, de jeu, de migration ni de preuve GPU. Le runner de chaque genre sera relié au runtime canonique à l'arrivée de R61–R66.
- `build_ledger(revision, evidence_dir)` vérifie les preuves déclaratives ancrées sur un SHA de commit exact avec checksum, interdiction des chemins sortants/liens symboliques, JSON à clés uniques, slots connus et refus des doublons. Toute preuve manquante, invalide ou en échec figure dans le rapport.
- **Le rapport reste `NO-GO` même si toutes les preuves déclarées sont présentes.** Une trace produite par un auteur n'est pas une approbation indépendante. R70.C devra vérifier physiquement provenance, licences, CI, machines propres, parcours auteur et SHA final avant toute autorisation de tag.
- R67–R69 (réseau, plateforme alternative, hub) restent conditionnels et ne bloquent pas R70.

## Usage

```bash
python -m unittest discover -s tests_standalone -p "test_r70_genre_certification.py"
python -m drawtemp.quality.r70_genre_certification \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --evidence-dir /path/to/r70-evidence --output /path/to/r70-ledger.json
# Avec --enforce, un résultat non certifié échoue toujours (code 1).
```

Arborescence attendue : `records/*.json` et `artifacts/*` dans `--evidence-dir` (sans liens symboliques). Exemple d'enregistrement R60 ; ajuster l'empreinte sur le contenu réel d'`artifacts/r60.log` :

```json
{
  "kind": "drawtemp-r70-evidence", "schema": 1,
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "requirement": "R60", "scope": "upstream_gate",
  "platform": "agnostic", "genre": "agnostic", "seed": -1,
  "outcome": "passed", "artifact": "artifacts/r60.log",
  "sha256": "<hex sha256 of real artifact>"
}
```

Les enregistrements déclarent une observation, pas une attestation indépendante. Pour chaque slot exact, consulter `required_evidence()` ou le tableau `missing` du rapport. Les benchmarks sont vérifiés contre les budgets explicitement fournis par le projet ; aucune cible p95/p99 universelle n'est inventée.

## Suite

**R70.A2** : brancher les véritables corpus sauvegarde/replay et profils R61–R66, documenter les budgets mesurés et corriger les régressions. **R70.B** : trois projets visuellement éditables via les ateliers existants et parcours export vérifiables. **R70.C** : validation indépendante tri-OS, GPU réel, droits, sécurité, QA tiers et décision explicite sur le commit final.
