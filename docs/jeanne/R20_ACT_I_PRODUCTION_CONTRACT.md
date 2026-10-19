# R20.A — Jeanne, Acte I : bible de production et contrat du projet

**Statut :** pack de contenu existant sur `master`, complété par un audit
d'authoring automatique. **Ce n'est ni une certification R20 ni un nouvel Acte I
jouable créé par cette PR.** Les combats de l'Acte I sont déjà implémentés dans
`sporebound/content/jeanne.json` / `jeanne.game.json` et couverts par
`test_jeanne_acte1.py`. La bible longue reste la référence d'intention pour
les actes futurs. Cette tranche rattache R20.1/R20.8/R20.9 à des artefacts réels.

## Canon et cohérence dramatique

L'univers est une **uchronie fantastique**, pas une reconstitution historique.
En 1428, Jeanne fuit Domrémy après l'incendie meurtrier et enquête sur la
responsabilité humaine de Bracourt et de ses agents. Le Livre des Voix est un
fil rouge, pas une excuse pour effacer les conséquences des décisions. Le
surnaturel demeure ambigu dans l'Acte I. L'héroïne garde le choix de la
protection des civils, des preuves et de ses alliances.

| Personnage / groupe | Motivation et conflit | Présence effective dans le pack Acte I |
|---|---|---|
| Jeanne | Deuil de Jacques ; protéger les survivants ou poursuivre les preuves | Héroïne, dialogues et combattante |
| Jacques, Renaud | Héritage familial ; enseignement du combat sans vengeance aveugle | Souvenirs, tutoriel |
| Étienne, Agnès | Protection armée ou soins ; manque de ressources | Choix de recrutement et équipement effectifs |
| Réfugiés, frère Michel | Survie, ravitaillement et témoignage | Interactions du village, hospice, drapeaux |
| Bracourt / Guillaume | Responsabilités dans les violences de Domrémy | **Promesse narrative / enquête**, exposition dramatique encore à compléter |
| Aveline, Charles, Confrérie | Enjeux politiques et surnaturels des actes ultérieurs | **Non livrés comme personnages jouables dans cet acte** |

La relation Jeanne–Guillaume ne doit jamais convertir les actes de torture en
marqueur d'affection. Toute romance éventuelle n'appartient qu'à une suite
adulte, sans contrainte, reconnaissance de ses crimes et réparation réelle.
Voir [Bible narrative](NARRATIVE_BIBLE.md) pour la chronologie étendue et
[Missions et branches](MISSIONS_AND_BRANCHES.md) pour le programme complet.

## Parcours réellement encodé

| Segment | Mission / scène canonique | Choix et conséquence |
|---|---|---|
| Champs / souvenir | `sc_p0_champs` → `p0_01_lame` | Exploration, visions et apprentissage |
| Village en crise | `p0_02_incendie` → `sc_p0_cendres` | `secourir` / `poursuivre` ; `prologue_path` |
| Fuite | `p0_03a_secours` **ou** `p0_03b_poursuite` → `p0_04_fuite` | Extraction et promesse |
| Camp et route | `sc_a1_camp` → `a1_01_route` | Un compagnon équipé ; choix réellement exclusif au recrutement initial |
| Pont | `a1_02_pont` | Protection ou renseignement : `pont_plan` |
| Hospice | `a1_03_hospice` | Blessés ou dossiers : `hospice_aide` |
| Dilemme | `sc_a1_dilemme` → `a1_04a_archives` **ou** `a1_04b_otages` | `acte1_choix` + preuve ou soutien civil |
| Vaucouleurs | `a1_05_vaucouleurs` → `sc_a1_fin` | `acte1_complete`, `acte2_appui`, `acte2_route_ouverte` |

Les deux alternatives du dilemme convergent sur `sc_a1_debrief` mais
conservent leur identité dans `acte1_choix`. La fin propose une justification
**conditionnelle** par archives ou témoignages, et un recours aux convictions
de Jeanne toujours disponible. `a1_04b_otages` est le vrai ID utilisé par le
pack ; les anciennes tables de conception nommant `a1_04b_familles` doivent
être interprétées comme projet de contenu, pas comme identifiant existant.

## Sources de vérité et règles de modification

- `sporebound/content/jeanne.json` : missions, carte tactique, objectifs et récompenses.
- `sporebound/content/jeanne.game.json` : récit, conditions, choix, recrutement,
  scènes, exploration, effets et ressources de présentation.
- `GameSession` / `Campaign` : choix effectivement effectués, équipement,
  progression, reprise et sauvegarde.
- `sporebound/narrative.py` : validation et exécution communes à tous les jeux.
  **Pas de moteur narratif spécial Jeanne**, ni nouveau format pour ce pack.
- Ce document et `scripts/audit_r20_act1.py` : **contrats de revue**
  vérifiant le contenu, jamais autorité pour le Player.

Conserver les IDs et les drapeaux existants : le digest narratif est lié aux
sauvegardes. Toute modification de `jeanne.game.json` peut invalider des
slots déjà créés et exige une stratégie de migration/test R20.C explicite.

## Exécuter les contrôles

```bash
python scripts/audit_r20_act1.py
python -m unittest tests_standalone.test_r20_act1_contract -v
python -m unittest tests_standalone.test_jeanne_acte1 tests_standalone.test_jeanne_prologue -v
```

L'audit vérifie la paire `Content`/`GameProject` canonique, les liens des
11 missions, les chemins village et archives/otages, les changements de
drapeaux, la progression scène→combat, le recrutement et l'accès conditionnel
à la fin. Il **échoue** si une révision reste techniquement valide mais change
silencieusement la signification d'une branche. Les tests du contrat incluent
des mutations négatives et l'examen des choix accessibles via `GameSession`.

**Séparation des preuves :** une inspection statique ou un état narratif
construit pour un test n'est pas une bataille gagnée. Les vrais objectifs
tactiques, le replay, la sauvegarde/reprise et les ressources sont éprouvés
séparément par les tests du Player et `test_jeanne_acte1`. Ce pack ne valide
pas une exportation native sur machine propre, une relecture artistique ou
un playtest humain.

## Reste pour R20.B–D

- R20.B : scènes village/forêt/refuge avec continuité d'exploration et mise
  en scène qualifiée, ainsi que des rencontres tactiques variées.
- R20.C : raccord cinématiques/relations/choix, conservation des branches
  après sauvegarde, migration des slots en cas de changement du récit.
- R20.D : parcours externes des chemins, absence de softlock, preuve de
  Player autonome et retour utilisateur. Tant que non prouvé, **R20 n'est pas
  certifié**.
