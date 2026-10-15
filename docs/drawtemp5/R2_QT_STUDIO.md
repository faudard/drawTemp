# DrawTemp 5.0 — R2 : Qt Application Foundation & Design System

## Lancement

Prérequis : Python 3.12, dépendance optionnelle PySide6. Le SDK tactique reste importable sans Qt.

```bash
python -m pip install -e ".[qt6]"
drawtemp-studio5
drawtemp-studio5 --content chemin/vers/jeanne.json
drawtemp-studio5 --smoke --workspace project
drawtemp-studio5 --reset-layout
```

Le fichier Content doit être accompagné de son manifeste GameProject canonique
(`.game.json`). Un projet sans ces deux fichiers est refusé par `AuthoringSession.open`,
sans génération implicite d'un nouveau manifeste. Sans `--content`, le Studio
charge la fixture Jeanne R0 en mémoire; enregistrer sous crée **deux** documents
via `StudioTransactionStore`.

## Livraison de cette tranche R2

| Lot | État | Preuve / limite |
| --- | --- | --- |
| R2.1 | Implémentation initiale | CLI, journalisation, boîte Save/Discard/Cancel, Save As sûr ; pas d'auto-sauvegarde silencieuse |
| R2.2 | Implémentation initiale | QMainWindow, menus natifs, toolbar, docks et ateliers Widgets |
| R2.3 | Partiel | Huit destinations; R5, R8 et R10 partagent une session; R9, R11 et Analyse sont pour l'instant consultables depuis le shell, non éditables |
| R2.4 | Partiel | Fusion Light/Dark, typographie et échelle 90–130 %, préférences persistantes; iconographie dédiée à produire |
| R2.5 | Initial | QStandardItemModel (QAbstractItemModel), recherche récursive, favoris persistants en métadonnées locales QSettings, ID stables, références indicatives |
| R2.6 | Initial | Nom validé sur sélection typée et multi-sélection, une transaction et un Undo, détection de sélections périmées; autres champs à connecter |
| R2.7 | Initial | Docks réarrangeables, visibilité, presets et saveState/restoreState versionnés |
| R2.8 | Initial | Actions réutilisées menus/barre/palette; Ctrl+O/S/Z/Shift+Z/Shift+P, recherche, personnalisation de raccourcis |
| R2.9 | Partiel | Noms accessibles, recherche, tab focus Qt native, contraste et échelle; tests NVDA/VoiceOver/Orca manuels requis |
| R2.10 | Partiel | Préférence FR/EN des libellés d'ateliers dans le shell; externalisation et traduction de tous les ateliers restant à livrer |

### Intégration documentaire

- **Une seule session** `AuthoringSession` est passée aux interfaces R5, R8, R10,
  avec des opérations d'édition validées via `preview_pair` / `apply`.
- **Pas de nouvel historique** ni de nouveau format Content/GameProject.
- Le shell garde la propriété des opérations ouvrir/enregistrer ; les contrôles
  d'ouverture/enregistrement des fenêtres accueillies sont désactivés dans
  le shell pour éviter que l'un des sous-ateliers change de session en cachette.
  Les lanceurs standalone R5, R8, R10 ne sont pas modifiés.
- Les références de l'inspecteur sont **indicatives uniquement** : ce n'est pas
  un graphe certifié pour supprimer/renommer des identifiants.
- Le widget R3 dans R5 reste le viewport Qt Quick commun existant.
- Les préférences locales utilisent `QSettings(DrawTemp, Studio5)`, jamais un
  champ supplémentaire sur les documents de jeu.

### Tests

```bash
python -m unittest tests_standalone.test_drawtemp5_r1_authoring tests_standalone.test_drawtemp5_r2 -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.studio.qt_shell --smoke --workspace project
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.studio.qt_shell --smoke --workspace maps
```

La CI exécute des tests Python 3.12 / Qt 6 sur Ubuntu, Windows et macOS.
La réussite offscreen **ne certifie pas** la composition GPU, l'identité visuelle,
les performances ni l'accessibilité aux lecteurs d'écran.

### Gates ouverts avant de clôturer R2 au sens de la roadmap

1. Vérifier visuellement un parcours Jeanne complet via le Studio Qt sur
   chacun des OS, avec viewport matériel R3 et fonctionnement des raccourcis.
2. Intégrer R9 / R11 dans le propriétaire de session commun, sans créer de
   copies concurrentes de GameProject (cf. INT-02).
3. Élargir l'inspecteur à des propriétés typées pour tous les ateliers, y
   compris valeurs mixtes par champ et messages d'erreur sous les champs.
4. Externaliser toutes les chaînes et tester FR/EN, textes longs, claviers
   internationaux et lecteurs d'écran; homogénéiser les icônes et états vides.
5. Vérifier le round-trip layout/favoris/zoom/thème en GUI et les limites de
   chargement sur de gros projets, avant de déclarer le gate R2 acquis.

Cette PR est une **tranche d'intégration R2**, pas une certification R2 complète.
