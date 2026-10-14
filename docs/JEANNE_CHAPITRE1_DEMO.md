# Jeanne d'Arc — Chapitre I : pass de finition démo

Le MVP demeure une campagne autonome qui réutilise les missions et les
sauvegardes déjà testées. Aucun changement de moteur, de données d'auteur,
de replay ni de format de sauvegarde.

## Lancer

```sh
python -m sporebound jeanne-chapter1
```

1. **Commencer** ou **Continuer le chapitre I** depuis le menu avec le portrait de Jeanne.
2. Lire la scène de recrutement, choisir Étienne ou Agnès, puis ouvrir la prochaine étape.
3. Consulter le briefing : objectif réellement demandé par le moteur,
   conseil de positionnement et bouton **Entrer en mission**.
4. En combat, l'affichage est en **2.5D isométrique** (comportement du
   Player actuel) avec aperçu des actions et aide activés pour le chapitre.
   Les tours ennemis se déclenchent automatiquement avec un petit délai ;
   on peut désactiver cette assistance pendant le combat.
5. Après la victoire, consulter le résultat en français et avancer vers le
   choix des archives **ou** des otages (branches exclusives).
6. Vaincre les assaillants de Vaucouleurs, choisir l'appui narratif et
   terminer sur un bilan de campagne lisible.

Le briefing, les cartes d'objectifs et le bilan final ne modifient jamais
la campagne. L'IA automatique passe par le même `PlayerController.ai_turn`
et les mêmes checkpoints que le bouton manuel. Les callbacks différés sont
annulés lors d'un changement d'écran et refusent de jouer pendant les
dialogues, la phase de déploiement ou une bataille déjà finie.

### Tests ciblés

```sh
python -m unittest tests_standalone.test_jeanne_chapter1_mvp -v
python -m unittest tests_standalone.test_jeanne_acte1 -v
python -m unittest tests_standalone.test_jeanne_prologue -v
```

### Critères de sortie de la démo

- Deux parcours testés jusqu'à leur issue, récupération sauvegarde comprise.
- Validation manuelle Tk sous Windows et Linux : menu, briefing, projection
  isométrique, actions, IA automatique, scènes et conclusion, y compris
  l'affichage en fenêtre 800×580 et en 1160×820.
- Profils du prologue inchangés, aucune récompense fictive.
- Aucun blocage ou exception en quittant une bataille pendant un tour auto.
- Réussite des jobs CI touchés ; les erreurs historiques des autres
  sous-systèmes doivent être distinguées des régressions du chapitre.

**Hors MVP :** monde ouvert, cinéma avancé, Acte II, sprites définitifs,
équilibrage certifié par playtests humains.
