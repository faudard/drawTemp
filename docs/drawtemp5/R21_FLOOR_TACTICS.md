# R21.B — Réactions, formation et protection multiétages

> **Tranche de code R21.2 / R21.4 / R21.7.** Proposition en PR empilée
> sur R21.A (#291). Aucun des gates 5.4 ni GPU/UX n'est automatiquement
> certifié par l'ajout des tests.

## Problème corrigé

Le combat possède déjà un modèle de niveau autoritaire :
`Battle.unit_levels`, des escaliers explicites
(`level_move`) et `floor_line_of_sight`.
Certaines règles de formation et d'interception utilisaient néanmoins
seulement `distance((x,y),(x,y))`, ce qui pouvait traiter deux unités
sur des étages différents comme des voisins tactiques.

Cette tranche **réutilise** le Core, le ruleset `tactical_rpg_rules()`,
les missions et le replay canonique. Elle n'ajoute ni mode combat
concurrent, ni champs persistants, ni altération de l'ancien ruleset.

## Comportements

1. **Phalange/mur de boucliers** : un partenaire vivant, allié et placé
   à une case ne suffit plus s'il est sur un autre niveau. Sur le même
   étage, les bonus existants et la protection mutuelle restent identiques.
2. **Escorte** : l'escorte effective et le choix de son destinataire
   exigent le même étage ; une tentative trans-étage est rejetée
   atomiquement par le moteur, sans dépense d'action ni désynchronisation.
3. **Interception** : la préparation impose le même étage que la cible ;
   la visibilité tient compte des véritables tuiles du niveau. Une
   interception présente dans l'état mais invalide n'autorise pas de
   dégâts hors étage.
4. **Overwatch et phalange préparée** : la ligne de vue suit le niveau
   de l'attaquant. Les requêtes `reaction_threats(..., level=N)`
   permettent de séparer explicitement les zones par niveau ; l'ancien
   appel sans niveau conserve sa sémantique du rez-de-chaussée.
5. **Intents Studio/Player** : les avertissements sur la carte tactique
   2D au sol n'affichent pas une réaction ou un sort situé uniquement à
   l'étage supérieur. Les listes détaillées indiquent le niveau connu ;
   elles ne prédisent pas la prochaine action d'une IA.
6. **Diagnostic de formation** : `formation_preview` indique
   `level`, `partners`, `providing_escort`,
   `formation_active`, `break_reason`. Les bonus de couvert/hauteur
   au sol ne sont pas appliqués artificiellement aux tuiles de l'étage.
7. **Reproductibilité** : les ordres, le CT, les commandes de déplacement
   entre niveaux, les réactions et les replays restent sous
   `Battle.execute()`.

## Tests / gate logiciel

```bash
python -m unittest -v tests_standalone.test_r21b_floor_tactics
python -m unittest -v tests_standalone.test_tactical_levels_3720c
python -m unittest -v tests_standalone.test_tactical_rpg3
python -m unittest -v tests_standalone.test_combat31
python -m unittest -v tests_standalone.test_r21_overlapping_threats
```

Scénarios : maison à deux niveaux réellement authorée, jonction par
escalier ; phalange rompue au sol et active une fois réunie ; mur de
boucliers affectant les **dégâts calculés par Battle** ; escorte /
interception refusées tant que séparées ; overwatch visible seulement
sur le bon étage puis déclenché lors du débarquement, avec replay
byte-identique sur le digest canonique.

**La PR est du code soumis à la CI** : le résultat d'un test n'est vert
qu'après son exécution sur le dernier SHA, indépendamment de sa présence
dans `tests_standalone`.

## Ce qui reste à faire

- Affichage graphique explicite du niveau actuellement sélectionné dans
  les viewports Qt et goldens validés manuellement. Ce lot maintient
  volontairement le rendu de danger 2D limité au rez-de-chaussée, plutôt
  que projeter des menaces de plusieurs niveaux sur une seule case.
- Tests d'arcs de menace par étage, portes, herses et couloirs étroits
  avec changements de terrain en cours de combat.
- Exécution de deux stratégies complètes du château :
  force/bélier contre infiltration/diplomatie ; multi-fronts
  synchronisés, boss, fins et balances multi-seeds (R21.8–R21.14).
- Contrôle des performances/feedback UX sur machine réelle, validation
  des snapshots et conservation des anciennes parties/replays Jeanne.

Lien : [roadmap principale R17–R24](../DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md).
