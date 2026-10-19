# R17.E / R17.6 — Contrôle des droits et intégrité des assets

## Portée

Ce lot ajoute une **preuve technique bloquante** pour les exports candidats
à une release, sans inventer de licence ni valider juridiquement les visuels.
Il prolonge R17.8, où plusieurs régions de sprites partagent un PNG d'atlas.
La vérité demeure le registre `GameProject.assets` / `Content`; aucun nouveau
registre de gameplay ou deuxième système d'animation n'est créé.

Par défaut, `preflight` et `export_game` conservent leur sémantique **preview** :
un manque de justificatifs est **signalé**, mais l'archive ne porte pas le
statut de release. Le mode strict `--require-licenses` exige un justificatif
par fichier physique. `--release` ajoute l'obligation d'un rapport R14
conforme ; un rapport absent ou non certifié est refusé.

## Contrat technique

À côté de `game.json` et `game.game.json`, le propriétaire peut fournir
`asset-licenses.json` au format versionné :

```json
{
  "schema": 1,
  "assets": {
    "art/hero/atlas.png": {
      "status": "pending",
      "rights_holder": "",
      "license_id": "",
      "evidence_path": "licenses/hero-grant.txt",
      "sha256": "<SHA-256 réel sur 64 caractères>",
      "allow_modification": false,
      "allow_redistribution": false
    }
  }
}
```

L'exemple ci-dessus est **volontairement refusé en mode strict**. Pour un
usage réel, l'ayant droit doit fournir un document local sous `licenses/`,
identifiable et non vide, une référence de licence/autorisation, son identité,
le SHA-256 exact du fichier et une validation **effective** des droits de
modification et de redistribution ; seulement alors le propriétaire peut
attester `status: "approved"`. Un simple libellé `"CC-BY"` ne suffit pas.

Le contrôle R17.6 vérifie :
- chaque chemin d'asset physique référencé par le registre, une seule fois
  même quand plusieurs sprites partagent le même atlas ;
- présence de tous les champs, états approuvés et permissions explicites ;
- SHA-256 de chaque fichier de source et correspondance à l'attestation ;
- justificatifs réels sous `licenses/` sans évasion de répertoire ni fichier vide ;
- noms de fichiers et clés d'attestation non ambigus entre OS ;
- présence du manifeste des droits et des justificatifs dans le bundle
  autonome, chacun inventorié avec SHA-256 ;
- refus d'un bundle preview si `verify --require-release` est demandé.

L'outil n'a aucun moyen de prouver qu'un document de droits est *authentique* :
la certification légale et la revue artistique demeurent **humaines**. Les
fichiers `assets/watercolor/rights.json` d'INT-03 restent `pending` tant
qu'aucun accord vérifiable n'existe. Ne pas les marquer approuvés afin de
faire passer un gate.

## Utilisation

```bash
# Prévisualisation : droits manquants = avertissement visible.
python -m drawtemp.export.cli check --content path/to/game.json

# Préflight strict sur les justificatifs de chaque asset physique.
python -m drawtemp.export.cli check --content path/to/game.json --require-licenses

# Export de candidature release : licences strictes ET preuve R14.
python -m drawtemp.export.cli export --content path/to/game.json \
  --runtime-dir path/to/native-player --output path/to/bundle \
  --release --r14-report path/to/r14-report.json

# Rejeter explicitement une archive de preview.
python -m drawtemp.export.cli verify --bundle path/to/bundle --require-release

python -m unittest tests_standalone.test_r17_asset_rights -v
```

## Gates encore ouverts

- INT-03 : publication réelle des 11 PNG dérivés, provenance et droits
  `assets/watercolor/rights.json` validés par le détenteur légal.
- R14/R17.9 : goldens revus, tests Qt on-screen et mesure GPU physique.
- R17.8 : installation et exécution vérifiées sur postes utilisateurs vierges,
  codesign/notarisation/compatibilité glibc.
- La vérification SHA du manifeste du bundle **n'est pas** une signature
  cryptographique ; un attaquant pouvant tout remplacer peut régénérer le
  manifeste. La signature/distribution de release reste à traiter dans R23.

**Décision :** la CI sur ces tests prouve le refus des attestations incomplètes,
jamais l'obtention de nouveaux droits de redistribution.
