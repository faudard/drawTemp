# R28.C — Ability & Enemy Designers (6.4, tranche tactique)

**Statut : PR de développement, non certifiée.**
**Base empilée : R28.B (#306) → R25.A (#298)**. La PR R26.A (#300)
est indépendante et son runtime action headless n'est pas encore raccordé à
GameSession/Player ni aux ressources R8. Aucun faux mode jouable n'est proposé.

## Fonctionnalités réellement éditables

Dans `drawtemp-studio5`, ouvrir **Gameplay** (menu Ateliers / accueil).

### Ability Designer

- Choisir une mission réelle (portée de validation) puis une compétence
  existante de `Content.skills`.
- Modifier cible, zone, coût PM, portée minimum/maximum, précision.
- Sélectionner l'**indice d'un effet existant**, puis ajuster son type
  compatible R8, élément, état, destinataires, puissance et durée.
- **Prévisualiser** calcule le diff des données **validées** via
  `DatabaseEditor.preview_many` sur une session R1, sans écriture.
  Modifier la compétence + un effet constitue un unique Undo.
- **Appliquer** échoue si la révision a changé. Tous les acteurs, classes
  et effets continuent à référencer les mêmes IDs; le validateur
  `sporebound.model.Content` refuse combinaisons incohérentes.
- Pas de création de nouvelles mécaniques action/RPG, pas de formule
  de dégâts inventée : seul le modèle `Skill/Effect` tactique existant
  est effectivement pris en charge.

### Enemy Designer

- Choisir une mission et un **acteur ennemi placé** dans Content.
- Éditer comportement IA, doctrine, formation, rôles, escouade, cible
  d'escorte et itinéraire de patrouille via les règles **R8.D** existantes.
- **Prévisualiser** utilise la fonction canonique R8 de validation/édition,
  puis instancie un **vrai Battle** sur les données détachées pour
  constater son état initial et son SHA/digest. Il ne prétend ni
  simuler de futurs tours ni prévoir la politique IA à 100 %.
- Un ennemi incompatible (doctrine sans arme requise, patrouille
  impossible, escorte sans allié, IDs inexistants) bloque avant commit.
- Application et Undo/Redo via la même `AuthoringSession`; aucune
  collection secondaire d'ennemis ni copie de GameProject.

## Capacités par mode

| Profil R25 | Compétences R8 / IA tactique | Contrat runtime |
|---|---|---|
| SRPG tactique | Édition, aperçu, validation/Undo | Battle existant |
| Action Adventure | **Non activé** dans ce workbench | R26 ActionRuntime actuellement autonome, sans mapping Skill/Effect |
| Classic RPG | **Non activé** | Combat par menu R28.9 absent |
| Narrative / NONE | **Non activé** | Pas de moteur de combat |
| Hybrid | Scènes CT **uniquement** | Action/CT transition et save communs encore manquants |

Une capacité de projet ne modifie pas automatiquement une mission tactique :
les règles R25 imposent encore CT à toutes les missions Content v1.
Le panneau indique explicitement le mode pris en charge, sans inventer
un HUD, une hitbox, un capteur de vision, une formule, une IA action
ou une table d'aptitudes spécifique.

## Dépendances et limites

- #298 R25.A : profils de jeu et capacités déclaratives versionnées.
- #306 R28.B : inspecteur de profils / scène Qt (parent de cette PR).
- #292 R28.A : wizard indépendant ; intégrer ultérieurement le menu et
  les nouvelles pages Studio avec un rebase explicite, sans écraser
  une autre branche.
- #300 R26.A : moteur action headless, non intégré au contenu R8
  ou au Player. Future R28.C2 pour **capteurs, états et capacités
  action** après les contrats d'intégration GameSession/SceneRouter.
- R28.3 et R28.4 restent **partiels** : pas de formule d'action ou de
  ciblage temps réel, pas d'édition de capteurs action, pas de preview
  Player/GPU, pas de certification novice R28.10.

## Vérifications

```bash
python -m unittest tests_standalone.test_r28c_gameplay_designers -v
python -m unittest tests_standalone.test_drawtemp5_r8_database tests_standalone.test_drawtemp5_r8d -v
python -m unittest tests_standalone.test_r25_foundation tests_standalone.test_r28_profile_inspector -v
```

CI : `.github/workflows/drawtemp-r28c-designers.yml`, tests headless
Python 3.10/3.12/3.14 et Qt 6 offscreen sur Linux/Windows/macOS.
Tests onscreen, tests d'usage et mesures GPU réels restent à exécuter.
