# DrawTemp 5.0 — R15 Export & packaging (tranche d'intégration)

## Objectif

Le Player natif est un binaire autonome Qt 6, sans Studio et sans Python à installer.
La wheel Python historique (workflow `distribution.yml`) **ne satisfait pas**
ce critère. Le flux R15 fabrique un runtime natif par plateforme, ajoute les
deux documents validés (Content/GameProject), les assets référencés, un registre
de SHA-256 et vérifie le tout **avant** d'exécuter le jeu.

## Utilisation

```bash
python -m pip install ".[qt6]" "pyinstaller==6.15.0"
python -m drawtemp.export.cli check --content sporebound/content/jeanne.json
python -m PyInstaller --noconfirm --clean --onedir --name DrawTempPlayer --collect-data drawtemp --collect-data sporebound scripts/r15_player_entry.py
python -m drawtemp.export.cli export --content sporebound/content/jeanne.json --runtime-dir dist/DrawTempPlayer --output export/Jeanne
python -m drawtemp.export.cli verify --bundle export/Jeanne
./export/Jeanne/Player/DrawTempPlayer --smoke
```

Sous Windows, lancer `DrawTempPlayer.exe`. Pour une création Studio native,
construire `scripts/r15_studio_entry.py` sous PyInstaller (mêmes options).
Chaque plateforme construit son propre runtime : un export Linux n'est pas
un exécutable Windows. La CI `drawtemp5-r15.yml` effectue build + smoke
sur Windows, macOS et Linux puis conserve les prévisualisations.

## Expérience Creator

Dans l'éditeur Qt R5, cliquez **Nouveau / Export** pour ouvrir
l'assistant Creator. Trois parcours y sont disponibles : choisir un modèle
(\`blank\`, \`tactical\`, \`narrative\` ou \`jeanne\`), prévisualiser
et importer sans modifier l'original un projet de schéma v1, ou valider
puis exporter un Player natif. L'import crée le sous-dossier
\`originals/\` pour permettre un retour en arrière; aucun convertisseur
pour des schémas inconnus n'est activé.

CLI équivalente :

\`\`\`bash
python -m drawtemp.export.cli template --kind tactical --output /tmp/my-tactics
python -m drawtemp.export.cli import --content ./game.json
python -m drawtemp.export.cli import --content ./game.json --output /tmp/imported
python -m drawtemp.export.cli inspect-extension --manifest ./extension.json
\`\`\`

L'API d'extensions v1 ne lit que des descripteurs JSON avec
\`api_version\`, \`id\`, \`name\` et \`capabilities\`
(\`asset-catalog\`, \`property-panel\`, \`project-template\`).
Aucun plugin Python non fiable n'est exécuté dans la chaîne d'export.

## Contrats et garde-fous

- `Content.json` et `Content.game.json` sont soumis au validateur commun
  `validate_pair`; aucune nouvelle sérialisation gameplay n'est introduite.
- Tous les assets du registre sont contrôlés et copiés depuis des chemins
  bornés au projet; les fichiers copiés sont inventoriés et hachés.
- Le manifeste `manifest.json` est vérifié au lancement du binaire gelé :
  un fichier modifié, ajouté ou manquant bloque le jeu avant initialisation Qt.
  Les SHA-256 établissent l'intégrité, **pas une signature d'éditeur**.
- Un dossier d'export existant n'est jamais écrasé; la publication est
  préparée dans un dossier temporaire avant renommage.
- Le fichier optionnel `asset-licenses.json` associe chaque chemin relatif
  à son texte de licence. `--require-licenses` refuse les licences absentes.
  Sans cette option les avertissements restent visibles : les droits de
  redistribution ne sont pas certifiés implicitement.
- `--r14-report` impose un rapport R14 valide et **complet** avant
  d'indiquer « R14 evidenced ». L'option ne doit pas être passée avec
  une preuve offscreen ou incomplète.

## État des lots R15

| Lot | État de cette tranche |
| --- | --- |
| R15.1 Distribution Studio | Build PyInstaller multi-OS en CI; installateurs/signatures à certifier |
| R15.2 Player Export | Bundle natif avec vérification au lancement; test machine propre à prouver |
| R15.3 Assets & hashes | Copie contrôlée, inventaire, SHA-256, avertissements licences |
| R15.4 Project Templates | 4 projets de départ validés, assistant Qt et CLI |
| R15.5 Content Validation | Préflight dédié, validation canonique et diagnostics de ressources |
| R15.6 Project Migration UI | Assistant Qt, aperçu, import v1 réversible; anciens schémas bloqués |
| R15.7 Creator Documentation | Tutoriel de création/import/export; captures et guides approfondis à poursuivre |
| R15.8 Plugin API | Manifeste v1 déclaratif, sans chargement de code tiers |
| R15.9 Release Pipeline | Artifacts prévisualisés; publication/signatures bloquées |

**Le gate R15 n'est pas réputé validé par un smoke logiciel**. Il nécessite
une installation propre sans Python/Studio, les tests R14 et les preuves de
distribution signée et de licences appropriées.
