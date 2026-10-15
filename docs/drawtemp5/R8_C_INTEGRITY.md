# DrawTemp 5.0 — R8.C : variables, références et édition groupée

**Continuation de R8.B dans la même PR #239**, après la consolidation de R8.A dans `master`.

## R8.9 — Global Variables, sans schéma parallèle

Le registre des drapeaux est **déduit** des usages de `Content.missions`,
`GameProject.story`, `GameProject.campaign_flow` et
`GameProject.battle_support`, avec source, chemin, rôle (lecture/écriture)
et type de valeur utilisé par les règles. L'interface **Variables /
références…** est une table consultable. La famille **Variables utilisées**
est également visible dans l'explorateur principal, même lorsque la variable
n'apparaît que dans une mission.

Aucune déclaration fictive n'est ajoutée à Content v1. Les valeurs runtime
sont persistées par `Campaign.story_flags` et ne sont pas écrites dans
`GameProject`. Une nouvelle variable est introduite par une condition ou
un effet narratif dans l'éditeur d'événements R9.

## R8.10 — Renommage contrôlé

La commande `IntegrityEditor.plan_rename(family, old, new, ...)` prévisualise
**une transformation des deux documents** à la révision courante ;
`AuthoringSession.apply(plan)` réutilise validations et Undo/Redo de R1.

Familles autorisées :

- `skills` : ID dans Content.skills, compétences des unités,
  archétypes, classes/talents et références typées `skill` ;
- `jobs` : clé d'emploi, prérequis de classes, liens `job`/`job_id` ;
- `archetypes` : ID de modèle et références `archetype` des unités,
  spawns événementiels et définitions ;
- `equipment` : ID d'équipement et effets `item` des scènes et campagnes ;
- `flags` : références `flag` de conditions, événements et campagnes.

Les renommages de **personnages de mission** restent bloqués : leurs IDs
sont associés aux objectifs, événements, sauvegardes et replays et exigent
une migration séparée.

**Important :** les sauvegardes de campagne et replays déjà créés ne sont
pas migrés par cette opération. L'API exige
`acknowledge_external_saves=True` et l'interface demande confirmation.
Cette confirmation ne garantit pas la compatibilité des anciennes sauvegardes ;
la génération/reprise d'un nouveau parcours et une migration explicite restent
nécessaires si les IDs externes sont utilisés.

Les substitutions portent exclusivement sur les propriétés de référence
connues : **aucun remplacement textuel arbitraire** dans les dialogues ou
étiquettes. Les identifiants invalides/collisions et les éditions qui cassent
`Content`/`GameProject` sont refusés sans effet sur l'historique.

## R8.12 — Édition groupée transactionnelle

Dans **Base RPG**, plusieurs ressources d'une même famille peuvent être
sélectionnées (Ctrl/clic ou Maj/clic), puis **Édition groupée…** ouvre le
champ typé à appliquer. La sélection est prévisualisée sur une copie, puis
validée **une seule fois** ; un Undo annule tout le lot, même si les unités
proviennent de missions différentes. Si une seule ressource est invalide,
aucune modification n'est commise.

L'API headless `IntegrityEditor.plan_bulk(selections, fields)` retourne
le plan détaché : `selections` contient des tuples
`(family, identifier, mission_id)`. Le commit vérifie la révision et
rejette les plans obsolètes après Undo/Redo.

## Validation et limites

```bash
python -m unittest discover -s tests_standalone -p "test_drawtemp5_r8c.py" -v
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests_standalone -p "test_drawtemp5_r8c_qt.py" -v
```

Tests : références lues/écrites entre documents, collision, acknowledgement,
renommage skill/job/equipment/archetype/flag, save-open, Undo/Redo et
lot atomique y compris si un acteur manque ou si un plan devient obsolète.

**Restant pour fermer R8 :** migrations réelles des anciennes campagnes,
édition des profils IA/doctrines détaillées, animation/sprite prévisualisés,
QA manuelle du Studio/Player isométrique partagé et validation CI complète.
Les graphes et placements R8.B sont une vue d'authoring, pas un substitut
au moteur Battle ni à ses budgets de rendu.
