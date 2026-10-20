# R41.C — VS-41 : Le relais du village

**Code en PR #381, non certifié et non fusionné dans master.**

## Modèle original créé depuis le Studio

Dans DrawTemp Studio, choisir **Fichier → Projet depuis un modèle rapide… → classic_rpg**. Le Creator existant génère un dossier nouveau contenant le Content canonique (game.json) et le GameProject (game.game.json), vérifiés par validate_pair et preflight avant publication atomique. L'auteur peut ensuite ouvrir, modifier, enregistrer et lancer le Playtest sans éditer le JSON à la main.

### Scènes, héros et objectifs

- **Village du relais :** recruter les trois héros originaux Elya (garde), Oren (éclaireur) et Mira (soigneuse). Le joueur commence avec Elya ; les deux autres sont recrutables puis activables (capacité trois).
- **Équipement :** le modèle apporte une lame (+3 attaque), une cape (+6 PV max, +1 défense) et une potion. Les objets sont stockés une seule fois dans Campaign.inventory ; HeroProgress détient l'équipement individuel. Le moteur RPG reconstruit les bonus depuis Campaign au début et à la reprise de la rencontre.
- **Bois des Brumes :** combat au tour par tour contre un loup. La victoire rapporte 12 pièces d'or et pose le flag R9 narratif r41_woods.
- **Crypte des Veilleurs :** le portail depuis le bois n'est autorisé qu'après sa victoire. Combat contre un gardien, 24 pièces d'or et flag r41_crypt.
- **Retour au village :** après deux victoires, quête « Rallumer la lanterne du relais » clôturable une seule fois. Prime de 25 pièces d'or et deux potions. Chaque héros actif reçoit 50 XP à chaque victoire.

Le template conserve une **mission Content v1 explicitement TACTICAL_CT**, sans la détourner pour les combats RPG_TURN. Les personnages, compétences, la campagne, le SceneRouter, les flags et la sauvegarde restent des sources canoniques partagées.

## Gates techniques dans les tests ajoutés

Le test headless tests_standalone/test_r41_vertical_slice.py exerce le modèle et le Creator, le recrutement, l'équipement, la traversée des portails, les deux combats, la quête, les XP et butins, l'idempotence, les checkpoints de combat, la détection d'une corruption d'équipement et le retour après sauvegarde/rechargement.

Le test tests_standalone/test_r41_slice_qt.py instancie le **vrai Player Main.qml avec bridge et renderer R3**, puis parcourt le scénario en Qt Quick offscreen.

Commandes à lancer et vérifier sur le SHA final :

    python -m unittest tests_standalone.test_r41_vertical_slice -v
    python -m unittest tests_standalone.test_r41_routed_encounter -v
    python -m unittest tests_standalone.test_r41_classic_party -v
    python -m unittest tests_standalone.test_r41_encounter -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_r41_slice_qt -v

Ces commandes sont incluses dans la CI dédiée, mais **aucune exécution réussie n'a été observée** : GitHub Actions produit jusqu'ici des runs en échec et zéro job. La simple présence de tests n'est pas un gate validé.

## R41.C : validations encore ouvertes

1. Réparer l'exécution des jobs CI, collecter les logs sur un SHA stable et vérifier les régressions tactiques Jeanne.
2. Recette Player réel **onscreen / clavier / manette / accessibilité**, y compris les séquences de focus et les raccourcis.
3. Produire un export **Player PC natif autonome** et installer sur une machine propre ; auditer les licences et la provenance des assets ; matrice Windows/Linux/macOS et GPU physique.
4. Équilibrer les combats et compléter les capacités/états avancés avec R43. Les PV/PM sont actuellement reconstruits au début de chaque nouvelle rencontre ; les niveaux/équipements/objets et récompenses persistent dans Campaign.

**Ne pas conclure que VS-41 est certifié ni fusionner la PR dans master en l'absence de preuves.**
