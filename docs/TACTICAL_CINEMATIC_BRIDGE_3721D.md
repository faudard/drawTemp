# 3.7.21D — Cinématiques d'événements tactiques

## Contexte

La PR #91 / 3.7.21C existe sur `master`. Elle utilise
`Mission.triggers`, `Battle`, `rules.triggers.dispatch`, un inspecteur
contextuel et un rendu isométrique partagé. Ce jalon ne crée ni une deuxième
machine à événements ni un système parallèle de cinématiques.

## Contrat auteur / Player

- `GameProject.cinematics[].trigger` accepte désormais
  `{"kind":"tactical_event","target":"garden/spore_pulse"}`.
- La cible doit identifier **un déclencheur tactique existant** dans
  `Content.missions`. Les références cassées sont refusées avant
  l'enregistrement d'un projet.
- L'onglet **Cinématiques** propose le nouveau type et une liste
  de cibles construites à partir des missions et de leurs vrais
  déclencheurs. Il n'est pas nécessaire de modifier le JSON à la main.
- L'inspecteur du **Graphe des événements** montre séparément les séquences
  tactiques (déclenchement direct) et les cinématiques attachées aux missions
  ou aux scènes (déclenchement distinct).
- Dans le Player, les cinématiques tactiques se jouent lorsque l'ID apparaît
  pour la première fois dans `Battle.fired`, dans l'ordre du moteur et,
  pour chaque ID, dans l'ordre du catalogue cinématique.
- Le Player réutilise `CinematicPlayback`, notamment sa commande **Passer
  la cinématique** et ses pistes sonores existantes. La présentation ne
  modifie pas `Battle`, `GameSession`, le digest de replay ou les règles.
- L'interface mémorise les identifiants déjà présentés par `battle_id`
  afin de ne pas les rejouer lors de simples `show()`. Lors du chargement
  d'une sauvegarde, les déclencheurs déjà dans `Battle.fired` sont marqués
  vus : reprise du combat sans relancer les cinématiques antérieures.

Ce dernier choix fournit une sémantique de **présentation au plus une fois
par session affichée**, et non un journal cinématique persistant. Si
l'application s'arrête pendant la lecture d'un clip, la reprise du combat
ne relance pas le clip déjà déclenché.

## Parcours de validation

1. Dans **Graphe des événements**, sélectionner `garden/spore_pulse`
   (ou créer un événement `interact` sur le levier `switch`).
2. Dans **Cinématiques**, créer une séquence avec le déclenchement
   `tactical_event` et la cible `garden/spore_pulse`.
3. Ajouter un dialogue, un mouvement de caméra ou un son ; sauvegarder
   le projet et le rouvrir.
4. Lancer la mission dans le Player. Quand le vrai moteur déclenche
   `spore_pulse`, la séquence prend la main et revient au combat après
   lecture ou **Passer**.
5. Vérifier qu'un simple rafraîchissement de la carte ou une nouvelle
   commande ne relance pas la cinématique. Sauvegarder/recharger : même
   comportement pour les déclencheurs déjà actifs.
6. Retirer l'événement tactique de la mission sans retirer la cinématique :
   l'enregistrement du projet doit détecter la référence devenue invalide.

## Régressions

```sh
python -m unittest tests_standalone.test_tactical_cinematic_bridge
python -m unittest tests_standalone.test_cinematics tests_standalone.test_event_context
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_cinematics_gui
```

## Hors périmètre

- Aucun changement à `Battle.state()` ou aux formats de sauvegarde / replay.
- Pas de nouvelle condition `story` pendant le combat et pas de dialogue
  de campagne directement invoqué en plein tour tactique ; celui-ci
  impliquerait une transaction de progression narrative séparée.
- Les cinématiques de missions, de scènes et de campagnes continuent de
  suivre leurs points de déclenchement habituels.
- Dans les sièges multi-fronts, les cinématiques tactiques ne sont présentées
  qu'au moment où le Player traite la bataille actuellement visible ; elles
  ne lancent pas une cinématique globale depuis un front hors écran.
