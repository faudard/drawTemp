# Jeanne d'Arc — Chapitre I (MVP jouable)

## Lancer le chapitre directement

Depuis la racine du dépôt, Python 3.10+ avec Tk :

```bash
python -m sporebound jeanne-chapter1
```

Dans le Player, sélectionner un emplacement puis **Commencer le chapitre I**.
**Continuer le chapitre I** recharge le dernier checkpoint de cet emplacement.

La campagne principale (prologue compris) reste inchangée :

```bash
python -m sporebound player
```

Le lanceur du chapitre réutilise `sporebound/content/jeanne.json` et
`jeanne.game.json` et adapte **en mémoire** l'entrée de campagne :
il n'y a aucune nouvelle logique de combat ni de format de sauvegarde.
Le profil par défaut `jeanne.chapitre1.game.json` est distinct de celui de
la campagne principale ; les anciens slots ne sont ni écrasés ni migrés
silencieusement. `--profile CHEMIN` permet un profil explicite.

## Contenu jouable

| Étape | Mécanique existante réutilisée |
|---|---|
| Camp des réfugiés | Choix Étienne/Agnès, recrutement et équipement réels |
| Route des fugitifs | Combat tactique avec extraction |
| Pont de la Brume | Contrôle du pont, objectif `hold` |
| Hospice | Défense et choix de ravitaillement |
| Archives **ou** otages | Branche exclusive, preuves ou soutien |
| Vaucouleurs | Combat final et audience |
| Conclusion | Drapeaux `acte1_complete` et `acte2_appui`, sans faux Acte II |

Le prologue n'est **pas marqué accompli** et ne donne aucune récompense
fictive. Le MVP commence au camp sur une nouvelle sauvegarde indépendante.

## Gate

```bash
python -m unittest tests_standalone.test_jeanne_chapter1_mvp -v
python -m unittest tests_standalone.test_jeanne_acte1 -v
python -m unittest tests_standalone.test_jeanne_prologue -v
python -m sporebound validate --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json
```

Valider les deux branches, le rechargement après le dilemme, le combat final,
la persistance des choix, ainsi que le démarrage sans Studio ni édition JSON.

**Hors MVP :** Acte II, monde ouvert, doublage, équilibrage humain certifié,
nouveau moteur cinématique ou nouveaux formats.
