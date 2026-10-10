# 2.5.3 — Character & Rules Studio

Cette première tranche de **Character & Rules Studio** édite les données
réelles de `Content v1` sans JSON manuel. Elle est intégrée à l'éditeur Tk
principal dans l'onglet **Personnages & règles 3.0**.

## Utilisation

L'onglet contient cinq sous-vues :

1. **Héros / monstres** : sélectionner un personnage de la mission active
   pour modifier son nom, type, camp, PV/PM, attaque, magie, vitesse,
   déplacement, défenses, arme, réaction, soutien, passif de mouvement,
   comportement IA, compétences et synergies (IDs séparés par des virgules).
   **Appliquer personnage** modifie uniquement cette instance et conserve
   les autres missions. Les positions, empreintes et routes de patrouille
   demeurent dans l'éditeur de carte pour respecter ses règles de collision.
2. **Archétypes** : créer un modèle réutilisable, le modifier ou le
   supprimer. On peut y régler type, arme, PV, attaque, vitesse,
   déplacement, compétences, réaction et profil IA. La bibliothèque
   préexistante reste accessible via **Bibliothèque d’acteurs** pour
   capturer et placer un modèle. **Changer un modèle ne réécrit pas les
   unités déjà placées** : les instances de mission sont des snapshots.
3. **Compétences** : créer/éditer une compétence, son coût, sa portée,
   sa portée minimale, son rayon, sa précision, son type de cible, sa
   forme de zone et le caractère magique. Une liste séparée permet
   d'ajouter, remplacer, supprimer et réordonner les effets.
4. **Classes** : créer et éditer les prérequis, niveaux requis,
   bonus de statistiques et compétences débloquées par niveau.
   Syntaxes guidées : `attack=3, max_hp=12` et `flare=2, heal=5`.
5. **Équipement** : gérer les objets d'emplacement `weapon`,
   `armor` et `accessory`, leur prix et leurs bonus
   (`weapon_power=2, attack=3`, par exemple).

Toutes les mutations passent par `Content.from_dict` et
`Document.replace`, comme les autres actions du Studio. Les actions
acceptées sont annulables/rétablissables, et les refus laissent le
document inchangé.

## Contrats préservés

- Aucun changement au format de sauvegarde, à la simulation de combat,
  au manifest du projet, ni aux enregistrements de replay.
- Les noms de skills et leurs IDs restent distincts. Un ID déjà utilisé
  ne peut être créé une seconde fois.
- Une compétence possède toujours au moins un effet.
- Les compétences référencées par une unité, une classe ou un archétype
  ne peuvent être supprimées tant qu'elles y sont utilisées.
- Une classe prérequise par une autre ne peut être supprimée.
- Les champs sont validés par les mêmes règles que le runtime :
  plages numériques, effets et statuts connus, portée minimale,
  types de cible et références croisées.
- Les modèles de personnages sont indépendants des unités des missions :
  modifier un modèle ne modifie pas silencieusement un jeu existant.
- La modification d'une instance respecte les contrôles de collision,
  les équipes obligatoires et les conditions de validité des acteurs.

## Organisation du code

- `sporebound/character_authoring.py` : opérations indépendantes de Tk
  sur les unités, templates, skills/effets, jobs et équipements.
- `sporebound/studio_character_rules.py` : interface Qt-independent
  (Tk Widgets) de création et édition guidée, réutilisant la fonction
  globale du Studio pour les erreurs et les transactions.
- `sporebound/studio_panels.py` : intégration et rafraîchissement.
- `tests_standalone/test_character_authoring.py` :
  tests de validation, d'isolation et d'annulation/rétablissement.
- `tests_standalone/test_character_rules_gui.py` :
  parcours Tk/Xvfb sur les cinq sous-vues.
- `.github/workflows/standalone.yml` : exécution du nouveau test GUI
  dans le job editor.

## Tests

```sh
python -m unittest discover -s tests_standalone -p test_character_authoring.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_character_rules_gui.py -v
```

## À compléter dans 2.5.3

- L'édition visuelle avancée des règles de déverrouillage des synergies
  (missions, séquences cachées, statistiques, membres, indices).
- L'éditeur de combos et d'arbres de classes avec graphes de prérequis.
- Des profils IA guidés plus complets, dont routes de patrouille en carte.
- Les propriétés détaillées des monstres multi-cellules, leur
  représentation graphique et les animations en 2.6.
- L'application explicite d'une mise à jour d'archétype aux instances
  sélectionnées, avec diff et garde-fous de compatibilité.
