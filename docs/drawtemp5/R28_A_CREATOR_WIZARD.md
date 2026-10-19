# R28.A — Assistant de creation multi-genres (premier lot)

**Portee reelle :** implementation progressive du R28.1 (interface Qt et
validation des prerequis), pas une certification du R28 / version 6.4.

## Utilisation

Dans `drawtemp-studio5`, choisir **Fichier → Nouveau projet multi-genres**
(ou la page Projet). Choisir le genre et un **dossier inexistant** ; le rapport
montre les capacites visees, l'etat du moteur et les blocages. Cliquer
**Creer et ouvrir** uniquement lorsque le rapport est valide.

| Genre | Etat de la creation | Modele reel |
|---|---|---|
| SRPG tactique | Cree et ouvre un projet canonique v1 | R15 `tactical` |
| Aventure narrative | Cree un projet narratif v1, avec regles tactiques existantes | R15 `narrative` |
| Action-aventure | Bloque (mouvement/combat temps reel non integres) | Aucun |
| RPG classique | Bloque (combat de menus absent) | Aucun |
| Hybride | Bloque (transitions mixtes et profil de scene absents) | Aucun |

**Important :** les valeurs mouvement/combat/camera affichees sont des
**capacites cibles**, non un nouveau schema persisté. Ni Content,
ni GameProject, ni le Player ne sont modifies par cet assistant. Un genre
non supporte ne se transforme jamais silencieusement en SRPG.

Le createur reutilise le generateur **atomique** R15 et l'ouverture
`AuthoringSession` R1 : refus des ecrasements, validation de la paire,
un seul proprietaire du document et protection des changements non sauves.

## Verification

```bash
python -m unittest tests_standalone.test_r28_creator_workflow -v
python -m unittest tests_standalone.test_drawtemp5_r15_creator tests_standalone.test_drawtemp5_r2 -v
```

QTest/Qt offscreen ne constitue pas une certification visuelle GPU ou
un test d'installation sur machine propre.

## Suite necessaire pour fermer R28

1. **R25/R26** : profils versionnes en GameProject, modes action et transitions
   reels, persistance/replay compatibles avec Jeanne.
2. **R28.1/R28.2** : rendre les cinq choix creables puis editer les profils
   par projet/scene dans l'inspecteur transactionnel avec undo/redo.
3. **R28.3-R28.6** : connecter les designers Ability, Enemy, Animation/Hitbox,
   Event/Quest aux regles et aux deux Player.
4. **R28.7-R28.9** : Labs, playtest roundtrip sans mutation du document,
   combat RPG classique.
5. **R28.10/R28.11** : trois mini-jeux crees visuellement par des testeurs
   externes, guides FR/EN et certification UX sur postes reels.

**Gate non atteint :** l'action-aventure et le RPG classique ne sont pas
encore creables/jouables. Ne pas annoncer R28.1 complet avant ces dependances.
