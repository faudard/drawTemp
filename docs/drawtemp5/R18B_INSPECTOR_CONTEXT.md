# R18.B — Inspector 2.0 et commandes contextuelles

> Implémentation incrémentale de R18.4 / R18.5. La certification générale R18, la validation sur GPU réel et R17 ne sont **pas** acquises par cette tranche.

## Vue auteur : édition typée et atomique

- Les champs disponibles viennent de `drawtemp.studio.inspector_model.shared_specs()` ; seules les propriétés communes à toute une sélection peuvent être modifiées ensemble.
- Chaque changement est **mis en attente**, validé individuellement par le même schéma typé que le commit, et présenté avec une erreur inline accessible. Tant qu'un champ édité est invalide (entier hors bornes, nom vide, booléen indécis, etc.), *Appliquer* est désactivé.
- Les valeurs mixtes restent vides/indéterminées à l'ouverture : **elles ne sont jamais interprétées comme une instruction de remplacement** avant modification explicite.
- *Ignorer les modifications* réinitialise uniquement le formulaire ; aucun Undo du projet n'est déclenché.
- *Appliquer* envoie **tous** les champs modifiés dans **un** `edit_properties()` avec `expected_revision`. La validation canonique Content + GameProject reste l'ultime arbitre ; si elle refuse un état combiné, la session n'est pas modifiée.
- Si la session est modifiée pendant la saisie par un autre atelier ou un Undo/Redo, le polling Qt **n'efface plus silencieusement le brouillon**. Le formulaire devient obsolète : sa validation et son application sont bloquées jusqu'à un abandon explicite et une actualisation.
- L'inspecteur conserve la navigation via les références entrantes/sortantes héritée de R2.C/D.

## Carte / Construction — aucun outil hors contexte

- `r18_context.py` fournit un contrôle de politique sans PySide6, shared core ni renderer alternatif.
- L'éditeur Carte désactive ses outils de peinture, de copie, de placement/transformation et d'édition de carte dès l'entrée dans Construction. Ces commandes sont aussi **refusées à l'exécution** par leur handler, même si un signal de fin de stroke ou un raccourci est arrivé après le basculement.
- L'entrée en Construction annule les strokes et prévisualisations non confirmés, sans enregistrer de mutation.
- Le dock Construction ne peut ni valider des changements, ni modifier son historique, ni prendre un hit renderer pendant que le mode Carte est actif.
- Le `ConstructionWorkspace`, `MapStudio`, `AuthoringSession` et le viewport R3 existants restent les seuls propriétaires de l'état métier.

## Tests

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_drawtemp5_r18b tests_standalone.test_drawtemp5_r2_cd tests_standalone.test_drawtemp5_r18a -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.qt_shell --smoke --workspace construction
```

La CI R18.B exécute les premiers tests sur Ubuntu, Windows et macOS (Python 3.12 + PySide6 6.8.3). Sous Linux, elle exécute aussi l'intégration Qt Quick réelle : `DRAWTEMP_R18B_MAP_GUI=1` active un test de navigation Carte ↔ Construction, de commandes bloquées et d'identité de session.

## À vérifier manuellement / limites

1. Sélectionner deux personnages, observer les valeurs mixtes et changer le nom + une propriété ; appliquer, Undo et Redo doivent conserver les IDs et un seul pas d'historique.
2. Saisir un nom vide puis une valeur valide : l'erreur doit disparaître sans interaction avec le projet ; le bouton *Ignorer* ne doit ni modifier les données ni invalider l'historique.
3. Commencer une saisie, provoquer une modification du projet depuis un autre atelier, constater le blocage « obsolète » sans disparition de la saisie.
4. En mode Construction, essayer les raccourcis de copie, placement, rotation, puis les clics du viewport ; aucune mutation Carte ne doit se produire.
5. Revenir au mode Carte, tenter les opérations Construction via l'ancienne référence du dock : elles doivent être refusées.
6. Refaire avec clavier seul, thème sombre/clair, échelles UI, HiDPI et lecteur d'écran pris en charge.

**Restant dans R18 :** enrichissement des schémas métier par atelier et éditeurs référencés dédiés, certification ergonomique réelle multi-écrans, éditions Événements/Cinématiques partagées (R9/R11), Player/HUD/Input (R18.C), onboarding et accessibilité globale (R18.D). Ce lot ne les déclare pas livrés.
