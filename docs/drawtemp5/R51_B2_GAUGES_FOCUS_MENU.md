# R51.B2 — HUD avancé, focus clavier et menu de titre personnalisable

**Statut : code proposé, branche dépendante de R51.B (#404), non intégré à master.**
Ce lot prolonge la roadmap R51.A → B → C sans changer Content, le Core,
GameSession, le format de save ou l'export. Le lot R51.A (#397) a été fusionné
sur la branche de consolidation, **pas directement sur master**.

## Fonctions livrées dans la branche

- Inspector Qt : deux sélecteurs de **bindings entiers typés** pour les jauges
  (valeur et maximum), modification dans un même brouillon validé.
  Les bindings `str`, les chemins arbitraires et types inconnus échouent.
- Ordre de focus : boutons « Focus précédent/suivant » avec permutations
  transactionnelles, validation de l'ensemble exact des identifiants,
  refus des doublons, composants non interactifs ou limites.
- `R51Node.qml` transmet permissions, évènements de focus et déplacements
  clavier dans les arbres `row/column` imbriqués.
  `R51Layout.qml` parcourt les **QQuickItem réels**, conserve l'identifiant
  focus courant, saute les boutons désactivés et fait revenir au début/fin.
  Touches prévues : Tab/Shift-Tab et flèches selon les contrôles Qt.
- **Écran de titre personnalisé** : le modèle `MENU` créé depuis le Studio
  comporte « Nouvelle partie » et « Continuer », avec focus déclaré.
  Dans `Main.qml`, ce menu opt-in utilise les mêmes `R51Node.qml` et
  `R51Layout.qml` que le Studio ; le bouton **Menu classique**
  permet toujours de revenir à l'écran historique.
- Le titre précède l'existence de `GameSession` : la projection refuse
  donc **tout binding runtime** au lieu d'inventer des valeurs.
  Un menu sans `menu.new_game` est ignoré en faveur du menu classique.
- Les seules commandes de jeu exposées depuis ce titre sont
  `menu.new_game` et `menu.continue`, acheminées via les méthodes réelles
  du `PlayerController` et une seconde vérification de permissions.
  `menu.continue` reste inactif quand aucune sauvegarde valide n'existe.
  `menu.options` et `menu.quit` restent de **strictes interactions Qt**
  vers le popup natif et `Qt.quit()`, sans scripts auteur.
- Les projets sans namespace `org.drawtemp.ui` conservent
  rigoureusement leur interface historique et leur gameplay CT.
- La projection Qt Player reste read-only ; le Studio affiche
  explicitement des valeurs de démonstration.

## Vérification à exécuter (non revendiquée comme passée)

```bash
python -m unittest -v tests_standalone.test_r51a_ui_layout \
  tests_standalone.test_r51b_layout_designer \
  tests_standalone.test_r51b2_ui_navigation \
  tests_standalone.test_player_hud_layout_r710

# Simple validation Qt software/offscreen, pas de GPU physique :
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
DRAWTEMP_R51_QT_GATE=1 python -m unittest -v tests_standalone.test_r51b_qt
```

Les tests couvrent l'édition sans mutation, le focus et les boutons désactivés,
le menu sans session de jeu, les titres invalides, les opérations R12,
le round-trip Studio/AuthoringSession et les propriétés Qt.

## Limites et risques ouverts

- **La manette physique n'est pas certifiée.** Les flèches et Tab passent par
  Qt Quick ; le mapping des D-pads / boutons hardware nécessite un E2E avec
  matériel et dépend des backends. Ne pas présenter ce lot comme un contrôle
  manette complet.
- Menus `DIALOGUE` et `INVENTORY` : toujours prévisualisables, mais non
  substitués aux écrans Player historiques. `HUD_ACTION` également.
- Les contraintes responsive sont déclaratives; le visuel doit encore être
  contrôlé au vrai DPI/GPU, texte long et haute-contraste.
- GitHub Actions des PR R51 précédentes a répondu `failure` avec **zéro
  job démarré**. Cela bloque toute déclaration de CI verte ou de gate fermé.
- R51.C doit auditer visuellement Qt Quick (Studio/Player), l'accessibilité,
  la manette matérielle, les exports PC multi-OS et les droits des ressources.
- **R50 / 9.0 et R51 / 10.0 : NO-GO** jusqu'aux preuves documentées.

## Ordre de merge

1. Vérifier la présence effective de R51.A sur la branche de consolidation ;
   ne jamais confondre PR fusionnée et intégration `master`.
2. Fusionner R51.B (#404) sur la même branche seulement après tests/résolution.
3. Rebaser cette PR R51.B2 sur R51.B fusionnée, vérifier le diff et la CI.
4. Ne viser R51.C que sur une branche issue de cette base consolidée.
