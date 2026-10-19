# R17.13 — Release Evidence : dossier de candidature DrawTemp 5.0

## Objectif

Réunir, sur un commit précis, les pièces justificatives nécessaires à une
revue externe : SHA-256 des artefacts, logs, captures éventuelles, états CI,
risques ouverts, contrôles R17.1 à R17.13, notes de version **provisoires**.

Ce dossier n'est **pas une autorité de certification**. Une réussite CI ou
un JSON déclarant « approuvé » ne peut ni certifier les licences des
sprites, ni garantir un GPU physique, ni authentifier un testeur externe.

## Code et formats

Module : drawtemp.quality.r17_release_evidence

- build_dossier() : construit un index (schema 1, genre
  drawtemp5-r17-release-evidence), avec revision, components, gates,
  artifacts, blocking_reasons et release_ready=false.
- release_notes() : produit une version Markdown explicitement DRAFT/BLOCKED.
- index_artifacts() : calcule réellement la taille et SHA-256 des fichiers.
  Refuse nom invalide, lien symbolique et fichier absent.
- inspect_checks() : refuse les runs appartenant à un autre commit, les
  pages GitHub manquantes, ainsi que les jobs échoués/en attente.
  Un retry plus récent et non terminé ne peut être caché.
- inspect_cross() : vérifie un rapport de la tranche R17.12, sans lui
  attribuer une certification de release.
- inspect_r14() : vérifie le contrat R14, sans transformer la
  déclaration d'un développeur en attestation de GPU physique.
- scripts/r17_collect_checks.py : télécharge les pages GitHub
  check-runs pour un SHA donné avec GITHUB_TOKEN.

Les statuts sont blocked ou partial tant qu'une preuve indépendante
fait défaut. Les artefacts sont mesurés localement, jamais uniquement
sur la base d'une empreinte déclarée.

## Commandes reproductibles

~~~sh
python -m unittest \
  tests_standalone.test_r17_13_release_evidence \
  tests_standalone.test_r17_13_check_capture -v

python -m drawtemp.quality.r17_release_evidence \
  --revision "$(git rev-parse HEAD)" \
  --artifact "roadmap=docs/DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md" \
  --artifact "review=docs/drawtemp5/R17_CONSOLIDATED_REVIEW.md" \
  --report artifacts/r17-13/release-evidence.json \
  --notes artifacts/r17-13/RELEASE_NOTES_DRAFT.md
~~~

Preuves optionnelles :

~~~sh
python -m drawtemp.quality.r17_release_evidence \
  --revision "$(git rev-parse HEAD)" \
  --checks-json artifacts/r17-13/github-checks.json \
  --cross-json artifacts/r1712/r1712-evidence.json \
  --r14-json artifacts/r14-report.json \
  --content path/to/authored-content.json \
  --bundle path/to/native-bundle \
  --review-json artifacts/external-review.json \
  --artifact "capture=artifacts/hardware-capture.png" \
  --report artifacts/r17-13/release-evidence.json \
  --notes artifacts/r17-13/RELEASE_NOTES_DRAFT.md
~~~

Attention : un fichier review JSON peut être archivé et haché, mais ne
permet pas à lui seul d'authentifier une signature humaine. Un PNG haché
n'est pas une capture approuvée. Le préflight des assets est exécuté avec
require_licenses=True ; un simple fichier de licences superficiel ne suffit
pas à déclarer R17.6 conforme. La validation juridique reste distincte.

L'option --require-ready rend un code de sortie non nul tant que la
publication est bloquée. Elle n'est pas utilisée dans la CI de
prévisualisation : ce workflow doit tester la production du dossier sans
prétendre publier le jeu.

## Critères bloquants

| Domaine | Preuves indépendantes à obtenir |
|---|---|
| R17.1–R17.4 | Intégration des commits au master final, édition unique et replay |
| R17.5 | Captures de parité validées visuellement et procédure documentée |
| R17.6 | Contrats de redistribution/modification des assets, propriétaire identifié |
| R17.7 | Sauvegarde/replay CT, RNG, recovery et injection de fautes |
| R17.8 | Test d'installation et lancement sur postes utilisateurs vierges |
| R17.9 | Frame-times p50/p95/p99 sur GPU matériel identifié, revue goldens |
| R17.10 | Compatibilité et réversibilité de la migration legacy |
| R17.11 | Parcours Qt Player et Studio, conflit externe, restauration/annulation |
| R17.12 | Parcours Studio→Player→save→export dans le binaire relocalisé |
| R17.13 | Manifestes, SHA, logs, captures, risques, revue externe de publication |

## Checklist de publication

- [ ] Code des PR nécessaires présent dans le **tree final de master**.
- [ ] Résultats CI au vert sur le SHA exact (jobs absents ou queued bloquants).
- [ ] Vérification juridique humaine des licences, auteurs et droits.
- [ ] R14 visuel/GPU matériel réellement vérifié et approuvé.
- [ ] Installation complète, exécution, sauvegarde, reprise et rollback
      sur Windows, Linux et macOS sans dossier de développement.
- [ ] Contrôles d'accessibilité, densité, clavier et traductions.
- [ ] Signature/notarisation et procédure de publication/retour arrière.
- [ ] Notes de version revues par un responsable externe à la production
      technique de ce rapport.

## Pipeline de preuves

Workflow : .github/workflows/drawtemp-r17-13-release-evidence.yml.

Sur Python 3.10/3.12 : exécute tests, récupère les résultats GitHub du SHA
exact, construit le dossier et le brouillon RELEASE_NOTES_DRAFT.md, puis
conserve les fichiers en artefact GitHub pendant une durée limitée.

**Aucune GitHub Release n'est créée**, et aucune mention READY ni
CERTIFIED n'est générée à partir de preuves insuffisantes.

La sortie R17.12 préexistante, même « verte » sur un runner isolé,
prouve au mieux l'exécution et la relocalisation du binaire ; pas
la totalité du parcours utilisateur ni la provenance juridique des assets.
