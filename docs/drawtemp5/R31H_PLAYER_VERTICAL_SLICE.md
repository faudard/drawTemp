# R31.H — Parcours Jeanne : Studio → Player → sauvegarde/reprise

**État :** implémentation proposée dans la PR #385 (R31.E–H), en brouillon. La CI multi-OS n'est pas certifiée.

## Utilisation dans le Studio

1. Ouvrir la paire Content/GameProject de référence R0 Jeanne non modifiée.
2. Ouvrir Game Logic Studio et cliquer **Créer la démo R31.H** puis confirmer.
3. Le Studio prépare la mission, le dialogue, le graphe v4 et le mapping campagne dans une copie isolée, valide le tout, puis publie une seule transaction R1. Un Undo annule intégralement la démo.
4. Sauvegarder les deux documents du projet. Lancer le Player avec :

       python -m drawtemp.player.qt_app --content /chemin/jeanne-r31h.json --campaign main

Le compagnon GameProject doit être enregistré avec le même radical et le suffixe .game.json. Utiliser un dossier de sauvegardes propre.

**Fail-closed :** l'assistant refuse la création si la mission R0 ou l'introduction ont été personnalisées, ou si la démo existe déjà. Aucun JSON manuel n'est requis.

## Parcours jouable

1. **PNJ :** scène StoryBook avec le garde du village, choix enter, puis drapeau persistant r31_npc_spoken=True.
2. **Porte :** la porte gate est fermée et verrouillée ; le levier lever la déverrouille via la vraie interaction Battle et modifie la collision.
3. **Combat :** Renaud est un ennemi vivant attaqué par la commande native act. Il n'est pas retiré par un faux événement de victoire.
4. **Coffre :** objet tactique natif r31h_chest, 40 or, utilisé une seule fois. Le trigger R9 de son interaction active l'action R31.F logic_set(r31_chest_opened, True).
5. **Extraction :** objectif R31.H opt-in : aucun ennemi vivant, coffre ouvert et joueur vivant arrivé sur la case (6,4). Aucun raccourci ne permet de gagner sans coffre ni combat.
6. **Campagne :** à la finalisation réelle GameSession, le pont R31.G exporte r31_chest_opened vers Campaign.story_flags avec sauvegarde/reprise vérifiée.
7. **Quête :** scène post-victoire r31h_reward avec choix conditionnel claim. Le choix écrit r31_quest_finished=True et attribue 30 or additionnels.

Le scénario réutilise le même Battle, StoryBook, GameSession, Simulation et Player QML que les projets ordinaires. Il ne contient pas de runtime de quête autonome.

## Tests à exécuter

    python -m unittest tests_standalone.test_drawtemp_r31_logic_vertical_slice -v
    QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r31_logic_qt -v

Les tests couvrent préflight non destructif, un seul Undo, sauvegarde R1, refus d'édition destructive, chargement réel du Player, levier, attaque, coffre, sauvegarde avant la victoire, chargement/replay, export et quête terminée, puis sauvegarde/reprise finale.

Workflow : .github/workflows/r31-visual-graph.yml (Linux, macOS, Windows). Un workflow marqué failure avec zéro job exécuté ne valide pas les tests.

## Limites

L'assistant est volontairement limité à la référence Jeanne R0, pas aux missions personnalisées. Les interfaces Qt/QML n'ont pas encore été certifiées en CI. L'objectif r31h_quest_extract n'est activé que sur les contenus qui le déclarent.

**Gate R31 : NO-GO** avant retour d'une CI exécutable et vérification de la suite complète. Ne pas fusionner le brouillon en l'état.