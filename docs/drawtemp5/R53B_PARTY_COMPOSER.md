# R53.B1 — Party Composer (Studio Qt + authoring R1)

**Statut : implémentation candidate en PR #400, gates NON CERTIFIÉS.**

## Accès et parcours auteur

Depuis le Studio, menu **Outils → R53 • Party Composer et combos…**. R41 Party Studio reste indépendant et intact.

1. Configurer le groupe R41 et ses membres actifs initiaux. Le R53 Composer refuse une campagne sans groupe R41.
2. Choisir la campagne, le **leader initial** parmi les membres actifs, et une **position distincte** pour chaque héros.
3. Ajouter ou éditer des combos. Dans la table, les ID des membres sont séparés par virgules et leur ordre définit l'initiateur (premier héros). Choisir un ou plusieurs modes déclaratifs.
4. Sélectionner chaque combo : la table des compétences offre uniquement les **compétences natives de dégâts ciblant un ennemi**, réellement possédées par le héros dans le premier template canonique Content. Laisser toutes les compétences vides conserve un combo purement déclaratif. Remplir tous les participants pour l'exécution `RPG_TURN` opt-in; la validation interdit les choix incomplets.
5. **Prévisualiser** : le plan montre avant/après, coût MP, attaque de base, arme et effets natifs. Il ne chiffre pas de dégâts contre une cible fictive et ne simule aucun rendu CT/action.
6. **Appliquer** : un seul `AuthoringSession.preview_project → apply`, compatible avec l'**Undo/Redo du Studio**, puis enregistrer le projet avec le flux R1 ordinaire. Les modifications de formulaire invalident automatiquement une ancienne preview.

Le module headless `drawtemp.studio.party_orchestration_authoring` expose `inspect_orchestration`, `native_damage_choices`, `combo_impact_preview`, `preview_orchestration_edit` et `apply_orchestration_edit`. La fenêtre Qt est `drawtemp.studio.party_orchestration_qt.R53PartyComposerDialog`.

## Autorité, schéma et compatibilité

`GameProject.extensions["drawtemp.partyrpg"]["data"]["orchestration"]` conserve le schéma R53 v1. Une clé optionnelle `defaults` regroupe `campaign_id → {"leader": hero_id, "formation": [slot...]}`. Chaque `leader` doit appartenir au `active` initial R41; les slots sont uniques, leur nombre égale les membres actifs; les campagnes inconnues sont rejetées.

`GameSession` initialise ses valeurs depuis ces defaults, mais conserve exclusivement les changements en jeu dans son journal R53 replayé. Cela ne crée **aucune** deuxième source pour les HP, XP, inventaire, équipements, récompenses, CT, skill damage ou histoire. Les projets sans R53 et les anciens slots ne changent pas.

**Limite volontaire** : après édition R53, une modification R41 supprimant un héros actif nécessaire à un default R53 échoue à la validation. L'auteur doit ajuster R53 avant de retirer ce héros. Les combos sont un catalogue **global à toutes les campagnes** dans ce schéma, et les defaults sont isolés par campagne.

## Tests

```sh
python -m unittest -v tests_standalone.test_r53_party_composer tests_standalone.test_r53_party_composer_qt
python -m unittest -v tests_standalone.test_r41_party_studio tests_standalone.test_r41_party_qt
```

La CI dédiée demande Python 3.12 et PySide6 Qt offscreen sur Linux, macOS et Windows; ni capture visible ni accessibilité NVDA/VoiceOver ni GPU ne sont implicitement validés. **Aucun statut vert n'est revendiqué sans logs GitHub**.

## NO-GO / R53.B2 et R53.C

- Composer sous forme visuelle drag/drop des cases, explication d'éligibilité de chaque duo, rôles/liens d'équipe et animation/feedback détaillé dans le Player. **B2 partiel :** le Player QML montre l'action combo `C`, un sélecteur filtré des capacités RPG utilisables et les partenaires en récupération, sans moteur supplémentaire. Test headless `tests_standalone.test_r53_player_combo` (commande Simulation, sauvegarde/reprise, compat R41); un rendu QML onscreen et les annonces de feedback accessibles restent à certifier.
- QTest de navigation clavier exhaustive, écrans HC/RTL et automation multi-plateformes.
- R53.C: scène exploration → leader switch → combat CT/RPG → retour PV/inventaire/loot, sauvegarde au milieu des transitions, deux seeds.
- Fusion effective des dépendances R41/R43/R51 sur le même graph Git de consolidation, résolution des conflits de PR #400, et jobs CI exécutés.
