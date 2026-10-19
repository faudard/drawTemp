# R18.C — Player Qt Quick : confirmation des cibles et HUD tactique

> Tranche incrémentale sur la branche R18.C, empilée sur R18.B (#310). **Pas de certification de la version 5.1, de l'UX complète ni des performances GPU réelles**.

## Fonctionnalités

Le Player Qt Quick R12 conserve son écran titre, Nouvelle partie, Continuer, Charger, Options, Quitter, le retour au titre et la sauvegarde. R18.C ajoute un contrôle explicite pour les actions tactiques dirigées vers une case :

1. Cliquer sur une case ou la sélectionner avec les flèches : **sélection seule**, aucune commande moteur.
2. Cliquer sur « Déplacer », « Attaquer » ou choisir une compétence (ou utiliser M/A selon les réglages). Le Player valide la destination et montre un bandeau de confirmation contenant la case, le type d'action et la prévision issue de `Simulation.tactical_presentation`.
3. « Confirmer · Entrée » exécute **une** commande existante, après vérification de la révision, de la case et de l'unité active.
4. « Annuler · Échap » ou changer de case supprime la demande, sans modifier la session.
5. Si un autre chemin a modifié le combat, l'action en attente devient non confirmable puis est rejetée avant tout ordre moteur.

Le HUD existant reste alimenté par le moteur : CT, PV/PM, liste des unités, intentions ennemies, timeline, ligne de vue, couvert, risques de déplacement et estimations d'attaque (pas de promesse de dégâts garantis). Un texte explicite rappelle que sélection et action sont distinctes.

## Contrats de sauvegarde et de simulation

- `PlayerController._pending_target` est une **projection UI éphémère**, non présente dans les documents, checkpoints, replay ou préférences.
- La demande et l'annulation ne consomment aucun RNG ni tour et n'appellent aucune commande de simulation.
- `confirm_target` passe par `command` / `use_skill` existants, qui gardent leurs contrôles canoniques de coût, LOS, CT et validation moteur.
- Les changements de case, de titre, de partie, de sauvegarde chargée et les transitions tactiques effacent la demande en cours.
- Les commandes headless historiques restent compatibles : l'obligation de confirmer ne s'applique **qu'au chemin UX du Player Qt**.

## Tests CI

```bash
python -m unittest tests_standalone.test_drawtemp5_r18c \
  tests_standalone.test_drawtemp5_r12 \
  tests_standalone.test_drawtemp5_r12_tactical -v

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.player.qt_app --reference --smoke --smoke-scene battle
```

Le workflow R18.C exécute les tests Python et le smoke QML sur Ubuntu, Windows et macOS, plus le parcours titre → dialogue → campagne → combat → sauvegarde → titre → reprise sous Linux.

## Points restant à certifier en conditions réelles

- Test souris + clavier AZERTY/QWERTY sur GPU réel, y compris focus, ordre de tabulation et absence de double activation.
- Accessibilité native et lecteurs d'écran, contrastes, échelles UI et petits écrans.
- Ergonomie du HUD : portraits/compétences/coûts, niveaux et interactions à plusieurs étages, historique d'actions.
- Confirmation équivalente des actions verticales, objets et interactions lorsque les critères UX le nécessitent.
- Campagne Jeanne complète avec sauvegardes/replays historiques et certificats R17, puis onboarding et tests novices R18.D.

Ne pas déclarer R18.C globalement « done » tant que ces scénarios de certification ne sont pas démontrés.
