# 2.5.3.2 — Synergy & Unlock Studio

L'onglet **Personnages & règles 3.0 → Synergies & secrets** permet
d'éditer les règles de découverte des combos tactiques directement dans
le Studio, sans rédiger de JSON et sans changer le moteur ni la sauvegarde.

## Contrat du jeu

Une synergie est identifiée par **tactique + membres**. Les identifiants
des membres doivent désigner des combattants joueurs existants dans
les missions. Le nombre de membres dépend de l'arity du moteur :

- Duos : `pincer`, `crossfire`, `relay`.
- Trio : `encirclement`.

Les tactiques supplémentaires du mode **Tactical RPG 3.0** (`chain_strike`
et `trio_burst`) dépendent d'un Ruleset opt-in ; elles ne sont pas
présentées comme des tactiques du moteur standard pour ne pas générer
des contenus invalides en mode classique.

Chaque combo possède une seule règle de déverrouillage, composée de
prédicats **ET / OU**. Les conditions proposées utilisent précisément le
format natif de `Content.tactic_unlocks` :

| Condition | Exemple | Signification |
|---|---|---|
| Statistique | `shared_kills ≥ 2` | Les partenaires ont participé à deux éliminations |
| Mission actuelle | `mission = garden` | La règle est évaluée lors de cette mission |
| Mission terminée | `completed_mission = escape` | Cette mission a été gagnée |
| Séquence | `status → forced_move → damage` | Trois événements ordonnés dans le journal |

Les statistiques fréquentes comprennent `missions_together`,
`shared_kills`, `rescues` et `intercepts`, ainsi que les compteurs
spécifiques aux tactiques prévus par le moteur.

## Créer un secret

1. Dans **Synergies & secrets**, sélectionner **Nouveau combo**.
2. Choisir la tactique et saisir les **IDs des membres** séparés par des
   virgules, par exemple `ziggy,momo`.
3. Compléter éventuellement les indices :
   `hidden` (inconnu), `clue` (indice), `near` (proche du déblocage),
   et `unlocked` (description de la capacité révélée).
4. Dans l'arbre, sélectionner une condition et employer **ET**, **OU**
   pour l'englober dans un groupe, **+ Enfant** pour ajouter une règle,
   **Remplacer** pour changer la condition, ou **Supprimer nœud** pour
   supprimer un enfant d'un groupe non vide.
5. Terminer avec **Créer / enregistrer**. Tous les membres, missions,
   seuils, groupes et tactiques sont alors validés avec le même modèle
   `Content` que celui du jeu.

Un groupe ET / OU ne peut pas devenir vide. La racine d'un secret ne
peut pas être supprimée. Les arbres possèdent une profondeur d'édition
et un budget de rendu bornés pour garder la navigation prévisible.

## Composer un enchaînement caché

Pour un prédicat **séquence** :

- Choisir chaque événement dans la liste : `status`, `forced_move`,
  `damage`, `downed`, `tactic`, `revive`, etc.
- Une étape peut préciser un champ d'égalité, comme
  `status=slow`, `mode=push` ou `tactic=pincer`.
- Les boutons d'étapes réordonnent les événements **sans modifier
  leur signification**.
- **Même cible** exige que les étapes concernent la même unité.
- **Action de tous les membres** exige que tous les membres du combo
  soient sources d'au moins un événement de la séquence.
- **Fenêtre en ticks** limite le temps entre première et dernière étape.
- **Objectif / répétitions** permet de demander plusieurs réalisations
  non chevauchantes de la séquence.

Ces champs suivent `sporebound.bonds.event_sequence_count` et
`unlock_rule_met` : le Studio ne réinterprète pas arbitrairement
les événements.

## Simuler la découverte

L'aperçu utilise les fonctions du moteur
`bonds.unlock_rule_met` et `bonds.unlock_progress`.

Il accepte des statistiques de test séparées par virgules, une
mission actuelle et des missions terminées. Des événements de combat
hypothétiques peuvent être saisis avec la notation :

`status@2@ziggy@boss; forced_move@4@momo@boss; damage@6@ziggy@boss`

Chaque entrée décrit `type@tick@source@cible`. Les éventuels
filtres de statut et de mode sont présents dans la définition des
étapes. L'affichage indique si le combo est débloqué et un
pourcentage de progression estimé, **sans modifier le joueur, les
flags, les replays ni aucun fichier de sauvegarde**.

## Architecture et tests

- `sporebound/synergy_authoring.py` : API pure, accès par chemins
  stables, composition ET/OU, create/update/delete, validation,
  aperçu du runtime.
- `sporebound/studio_synergy_unlocks.py` : onglet Tk, Treeview des
  conditions, éditeur des étapes, textes d'indices et simulateur.
- `sporebound/studio_character_rules.py` : intégration à 2.5.3.
- `tests_standalone/test_synergy_authoring.py` : tests d'immutabilité,
  règles, séquences, rollback, arity et Undo/Redo.
- `tests_standalone/test_synergy_unlock_gui.py` : test réel Tk/Xvfb.
- `.github/workflows/standalone.yml` : CI dédiée.

Tests locaux :

```sh
python -m unittest discover -s tests_standalone -p test_synergy_authoring.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_synergy_unlock_gui.py -v
```

## Hors périmètre

Cette étape n'invente pas de nouvelles capacités tactiques. Les synergies
standard sont prédéfinies par le moteur. Un catalogue de tactiques
personnalisées, des effets de combo modifiables et les règles opt-in
de 2.7 devront être abordés séparément, avec versions de rulesets et
garanties de replay.
