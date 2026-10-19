# R28.B — Inspecteur des profils de jeu (développement)

**Statut : PR empilée sur R25.A (#298), non fusionnée et non certifiée.**
Cette tranche couvre l'édition persistante des profils R25 par projet/scène
(R28.2, partiel) et conserve l'héritage historique de Jeanne.

## Parcours auteur

1. Démarrer `drawtemp-studio5` (Qt 6), ouvrir un projet existant et
   sélectionner l'atelier **Profils de jeu** (accueil, barre, menu Ateliers).
2. Choisir **Projet** ou une **mission tactique**, une **scène narrative**
   ou une entrée d'exploration déjà présente dans Content/GameProject.
3. Choisir un modèle SRPG, Action, Classic RPG, Narratif, Hybride, ou un profil
   personnalisé. Pour une scène, « Hériter » supprime seulement sa surcharge.
4. Modifier au besoin les cinq capacités déclaratives `movement`, `combat`,
   `camera`, `interaction`, `ui`. Les combinaisons incompatibles sont
   refusées par `sporebound.game_modes`, pas par un validateur Qt divergent.
5. Lire **Aperçu transactionnel**, avec diff de manifeste, révision source,
   état hérité/surchargé et liste éventuelle des missions tactiques protégées.
   **Appliquer** crée une seule opération Undo/Redo via `AuthoringSession`.
   L'enregistrement reste celui de la paire Content/GameProject v1.

**Règle CT non négociable :** une mission tactique existante ne peut pas
recevoir un combat autre que `TACTICAL_CT`. Changer le profil de projet en
Action/Narratif/RPG provoque normalement une erreur si une mission hérite du
profil global. L'option « Conserver les missions existantes en CT » épingle
explicitement l'ancien profil de ces missions dans la **même transaction**.
Les IDs concernés sont listés dans l'aperçu ; rien n'est écrit avant validation.

## Compatibilité

- Lire un projet sans `game_modes` ne le modifie pas et utilise `srpg`.
- Un retour au défaut SRPG, sans surcharges, retire le champ optionnel
  `game_modes` du manifeste : pas de migration silencieuse des projets v1.
- Les identifiants de scènes et les propriétés de profil sont strictement
  contrôlés. Pas de document parallèle, pas de modification des données de
  combat ou des sauvegardes existantes.
- Les plans de prévisualisation sont liés à leur session et à leur révision ;
  un projet changé entre aperçu et application est rejeté.
- Le viewport, le mapping d'entrées et les caractéristiques caméra restent
  ceux du Player existant. Le **profil déclaratif n'active pas le runtime**
  correspondant. Les champs de réglage de caméra (zoom, limites, suivi), HUD
  et remapping de touches dépendent encore de R25.6–R25.8.
- Un projet avec un nouveau profil modifie intentionnellement son manifeste
  et ses digests de compatibilité ; toute vraie migration de sauvegarde exige
  ses propres gates.

## Tests

```bash
python -m unittest tests_standalone.test_r25_foundation tests_standalone.test_r28_profile_inspector -v
python -m unittest tests_standalone.test_drawtemp5_r1_authoring tests_standalone.test_drawtemp5_r2 -v
```

Workflow `.github/workflows/drawtemp-r28b-profile.yml` :
tests headless et smoke PySide6 offscreen sur Ubuntu, Windows et macOS.
**Aucun résultat CI, test onscreen, GPU réel ou démonstration Player
inter-genres n'est présumé vert au seul ajout de la PR.**

## Articulation des branches

- **#298 R25.A** : schéma canonique `game_modes`, prérequis *direct* ;
  la PR R28.B cible la branche R25.A et doit être rebasée après sa fusion.
- **#292 R28.A** : assistant de création, branche indépendante de master.
  Après les fusions, rapprocher le choix du wizard et l'inspecteur sans
  créer de second schéma ni mode tactique présenté comme action.
- **R28.C** : designers Ability/Enemy/Animation branchés sur les règles des
  modes lorsque R26 Player est réellement intégré.
- **R28.8/R28.10** : playtest roundtrip puis mini-jeux tiers requis avant
  certification du jalon complet 6.4.
