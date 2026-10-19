# R17.D — Création Studio, Player Qt, sauvegarde et reprise

PR empilée sur **R17.C2 (#281)**, elle-même dépendante de **R17.C1 (#280)**.
On valide la présence du code dans les **arbres finaux de master** après fusion :
une PR empilée « merged » vers une branche intermédiaire n'est pas une preuve.

## Parcours automatisé

`tests_standalone/test_r17d_studio_player_roundtrip.py` réalise une mission
Jeanne sur les contrats métier existants :

1. **Studio** : `AuthoringSession` + `EventStudio.gate_wizard` pour associer
   le levier à une vraie porte, créer un trigger tactique, un danger au sol
   et une cinématique `tactical_event`.
2. **Pages** : création d'une page à priorité supérieure, condition `interact`,
   actions typées, tout dans le même `Mission.triggers`.
3. **Narration et cinéma** : création et liaison d'une scène/choix,
   ajout d'une piste audio dans `GameProject`, le tout après des pages actives.
   Ce cas révèle un écart concret : les transactions croisées réutilisaient
   `default_rules()` et refusaient un Content pourtant validé avec R9.D.
   Désormais elles utilisent `authored_rules_for_document` partout.
4. **Persistance Studio** : `save_as` de Content et GameProject, `open` et
   vérification des références et du contenu identique.
5. **Player** : `build_controller(content_path=...)` charge les *deux*
   documents ; nouvelle partie, premier choix, mission déverrouillée,
   interaction avec le levier, état réel de la porte, journal et dialogue.
6. **Save / resume** : sauvegarde slot 1, chargement authentifié
   `GameSession.load`, conservation du déclenchement et de la page sélectionnée,
   présence de la piste cinématique, reprise au même dialogue.
   Le choix `continue` se rejoue sans déclencher deux fois la porte, puis
   la nouvelle sauvegarde restaure la bataille.
7. **Player Qt** : vrai `QQmlApplicationEngine`, `create_bridge`,
   `RendererController` R3 et `Main.qml` ; même flux via slots QML,
   et rechargement sans mock de scenegraph.
8. **Atomicité** : une page invalide est rejetée sans changer la révision ni
   le contenu des deux documents sur disque.

## Exécution

```sh
python -m unittest tests_standalone.test_r17d_studio_player_roundtrip -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_r17d_studio_player_roundtrip -v
```

La CI dédiée couvre Ubuntu, Windows, macOS et une batterie R9.C/R9.D.
Les anciens tests restent nécessaires. Les tests QML offscreen **ne sont pas**
une preuve de performances GPU physiques ni de qualité artistique.
La release R17 reste bloquée tant que l'export sur machine vierge, la revue
graphique humaine et les autres gates P0 ne sont pas vérifiés.
