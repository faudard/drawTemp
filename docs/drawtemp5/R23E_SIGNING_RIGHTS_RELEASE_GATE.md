# DrawTemp 5.5 — R23.E : signatures, droits, essais hors ligne et dossier de release

> **Travail de certification préparatoire — NO-GO.**
> Cette PR n'apporte aucun certificat, clé privée, droit de redistribution,
> notarisation Apple ni décision juridique/humaine. Les scripts ne peuvent
> pas signer automatiquement un produit sans autorité et matériel de confiance.

**Dépendances :** #297 (R23.A) → #312 (R23.B) → #326 (R23.C)
→ #338 (R23.D) → R23.E. Toujours fusionner/rebaser dans cet ordre.

## 1. Inventaire réellement distribué : R23.10

`drawtemp/quality/r23e.py` consulte la **distribution R15 vérifiée** :
manifest natif, vrai Content/GameProject, ressources déclarées par preflight
et `game/asset-licenses.json` lorsqu'il existe.

Pour chaque asset effectivement exporté, le rapport indique son chemin,
son SHA-256, la déclaration de licence textuelle ou son absence.
Une licence déclarée ne prouve **jamais** la titularité, le droit de
redistribuer, le droit de créer une œuvre dérivée, les obligations
d'attribution ou l'existence d'une permission valable.

```bash
python scripts/r23e_release_dossier.py inventory \
  --bundle export/Jeanne \
  --revision "$(git rev-parse HEAD)" \
  --platform Linux \
  --report r23e-assets.json
```

Les inventaires demeurent `legal_status=blocked-pending-human-rights-review`,
même lorsqu'ils ne contiennent aucun avertissement automatique.
Une revue humaine doit examiner les droits et notices des ressources, les
licences et redistributions des dépendances (PySide6/Qt, PyInstaller,
polices, bibliothèques natives) et leur conformité selon les modes
effectifs de liaison/distribution. Les notes de R15 ne sont pas une
attestation juridique.

## 2. Vérification des signatures existantes (pas de service de signature)

`scripts/r23e_verify_signature.py` n'a **aucun chemin de signature
automatique**. Il exige un SHA-256 fourni par un canal indépendant
et une identité d'éditeur vérifiée hors du dépôt :

- **Windows :** `Get-AuthenticodeSignature` avec `Status=Valid`, plus
  comparaison stricte avec le thumbprint du certificat éditeur.
- **macOS :** `xcrun stapler validate` du DMG, montage en lecture seule
  du DMG attendu, `codesign --verify --deep --strict`,
  contrôle de `TeamIdentifier` et `spctl --assess` sur
  **l'application montée depuis ce DMG**.
- **Linux :** SHA du `.deb` + signature détachée via `gpgv`,
  clé publique dans un trousseau local dont le SHA-256 est épinglé,
  fingerprint PGP fourni indépendamment.

Exemple (Linux) avec références **réellement contrôlées** par le
responsable de publication :

```bash
python scripts/r23e_verify_signature.py \
  --platform Linux \
  --artifact release/DrawTempStudio-5.5-preview-Linux.deb \
  --sha256 "<SHA256_PUBLIE_PAR_CANAL_FIABLE>" \
  --revision "$(git rev-parse HEAD)" \
  --signature release/DrawTempStudio-5.5-preview-Linux.deb.asc \
  --keyring /path/to/trusted-release-keyring.gpg \
  --keyring-sha256 "<SHA256_CLE_PUBLIQUE_FIABLE>" \
  --key-fingerprint "<FINGERPRINT_40_HEX_VERIFIE>" \
  --report r23e-signature-Linux.json
```

Exemple Windows : remplacer par `--platform Windows`,
`--artifact ....exe`, `--publisher-thumbprint
<FINGERPRINT_CERTIFICAT_40_HEX>` et conserver
`--sha256`, `--revision`, `--report`.

Exemple macOS : remplacer par `--platform macOS`,
`--artifact ....dmg`, `--team-id <APPLE_TEAM_ID_10_CHARS>`,
`--sha256`, `--revision`, `--report`. La commande monte
et démonte l'image pour vérifier les binaires qui s'y trouvent.

Les rapports de vérification indiquent une observation du système
`verification=os-trust-check-executed`, mais conservent
`release_authorization=not-asserted` et
`manual_signoff=required`. Un GPG valide n'établit pas à lui seul
l'origine industrielle ou la légalité du binaire. La clé ou le
certificat doit être lié à un éditeur autorisé par un contrôle indépendant.

Les **paquets R23.D non signés doivent échouer** à ces commandes : cette
éventualité est normale et ne doit pas être contournée en CI.
Ne jamais placer de clés privées dans le dépôt, les logs ou les artefacts.

## 3. Procédure QA hors ligne / machines propres : R23.1–R23.9

Créer un dossier de preuve par **révision SHA, OS, architecture et machine
réelle/VM vierge**, puis effectuer :

1. Acquérir le binaire et son SHA officiel par un canal vérifié ;
   vérifier la signature et la chaîne de confiance.
2. **Couper l'accès réseau** avant l'installation du produit et avant
   le premier démarrage. Noter version OS, dépendances système déjà
   présentes, CPU/GPU/VRAM, RAM et DPI. Conserver l'inventaire sans données
   personnelles ou identifiants appareil.
3. Installer Studio et Player avec le gestionnaire natif sur Windows,
   Debian/Ubuntu ou macOS Gatekeeper. Vérifier les lanceurs et les erreurs.
4. **Creator :** créer un mini-projet avec carte, acteur, déclencheur,
   scène/campagne, enregistrer, fermer, rouvrir, exporter et valider R14.
5. **Player :** explorer, lancer un combat, enregistrer, quitter,
   restaurer puis contrôler état/résultat et déterminisme.
6. Refaire les parcours avec **clavier seul**, focus et contraste 150 % ;
   tester lecteurs d'écran adaptés (NVDA / VoiceOver / Orca).
7. Mesurer FPS p50/p95/p99, latence d'entrée, RAM/VRAM et temps de
   chargement avec outils matériels ; réaliser une endurance
   de plusieurs heures et vérifier les sauvegardes/crash-recovery.
8. Déclencher une tentative d'import malveillant selon le corpus R23.4,
   confirmer le refus sans modification des données préexistantes.
9. Désinstaller le produit, constater la suppression du programme et la
   **conservation des sauvegardes utilisateur** ; réinstaller hors ligne.
10. Documenter bugs, sévérité, reproductions, correctifs et retests,
    puis associer une revue humaine datée à chaque preuve.

Les tests GitHub offscreen **ne remplacent pas** ce protocole.
L'accès réseau doit être contrôlé par l'opérateur ou une VM configurée,
pas seulement par une variable d'environnement.

## 4. Dossier unique de release

La CI R15 conserve des `r23e-assets.json` sur les trois OS puis appelle :

```bash
python scripts/r23e_release_dossier.py dossier \
  --asset-directory r23e-rights \
  --r23d r23e-upstream/r23d-release-assessment.json \
  --revision "$(git rev-parse HEAD)" \
  --report r23e-release-dossier.json
```

Le rapport établit le statut des **douze gates R23** et bloque toujours
R23.10 et R23.12 faute de revue légale et d'approbation humaine.
Il interdit de mélanger des rapports d'OS ou de SHA distincts.

Des résultats externes peuvent être référencés dans un tableau JSON
`--external-submissions`, uniquement au format :

```json
[
  {
    "kind": "offline_native_qa",
    "revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "platform": "Linux",
    "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "reference": "Rapport externe QA-001",
    "status": "submitted-unreviewed"
  }
]
```

Les `kind` autorisés sont :
`offline_native_qa`, `license_counsel_review`,
`accessibility_review`, `human_playtest_retests`,
`hardware_performance`, `long_session`.

**Les valeurs de l'exemple ne sont pas des preuves réelles.** Une
soumission même bien formatée reste `submitted-unreviewed` et ne
débloque aucun gate ; chaque signature externe doit être authentifiée
et la revue formelle menée avant toute annonce `GO`.

## 5. Travail restant avant un tag 5.5 stable

- Installer une chaîne de signature **autorisée** avec gestion des clés
  sécurisée (HSM ou store cloud) et signer les artefacts **avant**
  la vérification ; notariser et stapler le DMG macOS.
- Valider les termes réels des dépendances et assets, et embarquer
  les notices de redistribution approuvées.
- Exécuter les parcours hors ligne, endurance, performances, accessibilité
  et retests sur matériel représentatif.
- Rejouer toutes les campagnes et les sauvegardes supportées sous le même
  candidat final (tag/SHA) et vérifier les douze gates.
- Obtenir la **décision de publication signée par des responsables humains**.

Tant que cela n'a pas eu lieu :
`decision=NO-GO`, `certified=false`. Aucun tag 5.5 stable automatique.

## Tests ciblés

```bash
python -m unittest tests_standalone.test_drawtemp5_r23e -v
```
