# R18.A — Studio shell et parcours projet (candidat à revue)

> Statut : implémentation incrémentale sur la branche R18.A. **Le gate R18 global n'est pas certifié** et R17 reste une dépendance de release.

## Périmètre livré dans cette tranche

- Navigation unifiée entre les dix destinations de la roadmap 5.1 : Projet, Carte, Construction, Personnages, Base RPG, Événements, Campagne, Cinématiques, Analyse, Publication.
- **Construction** est un mode du **même** MapWindow R5/R6 : la même `AuthoringSession`, le même viewport Qt Quick et le même dock Construction. Le passage Carte ↔ Construction change uniquement le mode et les outils disponibles.
- **Publication** propose un Playtest et l'export R15 : l'export reste soumis au préflight et à l'existence d'un runtime natif. Aucune seconde chaîne de packaging.
- Fichier : Nouveau projet via les modèles R15 (création sans écrasement), Ouvrir, Projets récents (normalisation et déduplication, entrées absentes identifiées), Enregistrer, Enregistrer sous, Playtest (Player Qt séparé), Exporter.
- Préférences : thème, langue du shell FR/EN et échelle ; actions globales et raccourcis clavier reconfigurables. Les dispositions édition/analyse/compacte sont persistantes via `QSettings`.
- Le changement de projet ouvre et valide une **nouvelle session canonique** avant de remplacer celle en cours, après confirmation des modifications non sauvegardées. Les pages et leurs anciennes références sont alors libérées.

## Contrôles

```bash
python -m unittest tests_standalone.test_drawtemp5_r18a -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_drawtemp5_r2 -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.qt_shell --smoke --workspace publication
```

Sur une station Qt/PySide6, essayer manuellement :

1. Ouvrir le Studio, créer un projet `blank`, vérifier les deux fichiers `game.json` et `game.game.json` puis les retrouver dans les projets récents.
2. Modifier une carte, passer à Construction via la barre de navigation, sélectionner une structure, revenir à Carte : le document et l'historique sont conservés, les outils contextuels changent de mode.
3. Vérifier Annuler/Rétablir ; ouvrir un projet invalide depuis Récents : le Studio conserve l'ancienne session et signale l'erreur.
4. Lancer Playtest sur un projet enregistré (Player Qt dans un processus isolé). Tester la sauvegarde préalable quand la session est modifiée.
5. Vérifier l'export : contrôle R15 explicite, refus si les prérequis de licence/runtime ne sont pas satisfaits.
6. Tester dispositions édition/analyse/compacte, disposition utilisateur et raccourcis, fermer puis rouvrir le Studio.
7. Refaire au DPI 100 % et 200 %, navigation clavier et FR/EN.

## Limites explicites — ne pas marquer R18 « done »

- Événements et Cinématiques conservent pour l'instant les pages d'aperçu de R2 : leur véritable édition unifiée R9/R11 doit encore être intégrée et certifiée.
- Les dispositions utilisent les docks existants ; la certification multi-écrans/HiDPI et l'onboarding novice restent R18.D.
- La traduction concerne le shell global seulement, pas encore chaque atelier ni tout le Player.
- Le Player conserve les travaux R12 (titre/HUD/input). La certification UX R18.C, avec tests utilisateurs et captures matérielles, n'est pas incluse.
- R17/CI/UX-GPU restent des gates indépendants. Cette PR n'atteste ni du test GPU réel ni d'une release 5.1.

## Suite

R18.B : Inspector 2.0, édition multiple et outils contextuels validés en GUI. R18.C : titre, HUD, contrôles du Player Qt avec E2E réel. R18.D : onboarding, accessibilité, terminologie FR/EN, walkthrough novice et preuves de certification.
