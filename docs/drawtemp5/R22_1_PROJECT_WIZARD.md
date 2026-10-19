# R22.1 — Project Wizard (tranche fonctionnelle)

## Périmètre livré

- Entrée **Fichier → Nouveau projet…** et bouton sur l'accueil du Studio Qt.
- Dialogue R15 réutilisé, avec modèle `blank`, `tactical`, `narrative` ou
  `jeanne`, identité du jeu (titre et sous-titre), langue FR/EN, écran plein,
  nombre d'emplacements de sauvegarde (1–9) et destination.
- Prévisualisation en lecture seule : paramètres, destination, erreurs explicites.
- Génération atomique du dossier, préflight Content + GameProject + assets,
  aucun écrasement, puis ouverture dans l'unique `AuthoringSession` du Studio.
- Au changement de projet, confirmation des modifications non enregistrées,
  réinitialisation des ateliers hébergés et de la sélection.

## Contrats / limites

- Le schéma de jeu reste **Content / GameProject v1**. Pas de manifeste nouveau,
  pas de second moteur, pas de JSON manuel nécessaire pour initialiser un projet.
- Les modèles R15 restent des **démarrages**, pas des jeux complets. En particulier,
  le modèle « blank » réutilise les unités de base de la carte Jeanne ; il n'est
  pas encore un éditeur de cartes vide de toute entité.
- La prévisualisation vérifie la saisie et les chemins sans toucher au disque ;
  l'intégrité effective est contrôlée pendant la création avant publication.
- Ce lot ne certifie ni l'export natif en machine propre, ni l'acceptation R22.14,
  ni les autres ateliers R22.2–R22.13.

## Reproduction

```sh
python -m unittest tests_standalone.test_drawtemp5_r22_project_wizard
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp5_r22_project_wizard.ProjectWizardQtTests
python -m drawtemp.studio.qt_shell
```

Scénario manuel : Fichier → Nouveau projet → modèle tactique → titre
« Mon jeu » → dossier inédit → Prévisualiser → Créer → modifier la carte →
Enregistrer → réouvrir `game.json` ; vérifier que `game.game.json`
reste cohérent et qu'un dossier existant est refusé.
