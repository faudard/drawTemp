# R19.B1 — Jeanne : animations directionnelles et export de kit candidat

**Statut : implémentation de travail, pas pack artistique approuvé.**
Dépend de [R19.A](R19_A_ART_DIRECTION_AND_GATE.md), empilé sur sa PR.
Cette tranche prolonge [R7.C](../DRAWTEMP_5_R7C_JEANNE_ART_EQUIPMENT.md)
sans modifier les règles tactiques.

## Ce qui fonctionne

La commande suivante assemble un projet auteur R7 autonome et un pack
AssetRegistry v1 / Player R12. Elle réutilise les **quatre tenues existantes**,
les expressions, les poses historiques et les variantes directionnelles ;
elle n'altère pas le PNG source.

~~~sh
python -m pip install ".[art]"
python -m drawtemp.assets.jeanne_motion_r19 \
  --repository . --output ../jeanne-motion-r19

python -m unittest tests_standalone.test_drawtemp5_r19a \
  tests_standalone.test_drawtemp5_r19b -v
~~~

Les fichiers de sortie sont :

- jeanne.character.json, recette R7 v1 éditable (Character Studio).
- sources/jeanne_r19_{run,magic,block,hit,death,victory}.png,
  planches RGBA en 4 colonnes cardinales et 2–3 phases d'action.
- runtime/atlas.png, runtime/registry.json, runtime/character.json,
  export portable **déjà consommable par CharacterPack/Studio/Player**.
- r19-motion-provenance.json, empreintes exactes et statut
  redistribution_approved: false, art_review: pending.

Un export identique est idempotent. Tout fichier édité manuellement bloque
une nouvelle génération et n'est jamais écrasé. Un dossier temporaire est
utilisé avant publication ; les ressources d'origine et leurs identifiants
restent inchangés.

### Animations R19.B1

| Action | Phases | Composition visuelle |
| --- | --- | --- |
| run | 3 × 4 directions | Oppositions bras/jambes, foulées et poussière |
| magic | 3 × 4 | Bras levés, charge et déploiement de sort |
| block | 3 × 4 | Écu avancé, montée en garde et maintien |
| victory | 3 × 4 | Bannière tenue haute, tissu en mouvement |
| hit | 2 × 4 | Deux reculs et marque d'impact |
| death | 2 × 4 | Chute / silhouette effondrée, atterrissage |

Les clips idle/walk/attack préexistants restent inchangés ; hit et death
reçoivent une seconde phase visuelle. Le runtime R7 connaît déjà ces noms
d'action et consomme leurs durées, boucles et directions sans nouveau schéma.
Chaque tenue bénéficie de l'ensemble des clips via les calques R7.C, même si
le déplacement du tissu **reste statique** en composition et devra être affiné.

## Limites et critères de continuation

**Ce sont des esquisses numériques dérivées à partir de poses existantes,
pas des sprites définitifs peints image par image.** Elles apportent des
silhouettes et gestes distincts, utiles pour prototyper le timing, composer
les tenues et tester le Player, mais une revue humaine doit valider/animer
chaque action et corriger anatomie, pied au sol, compatibilité de la tenue,
occlusions et direction réelle du regard.

Le test R19.A audite **les pixels source** et peut confirmer une séquence non
recyclée ; il ne garantit pas les intentions de l'action. Il faut encore :

1. Revue des captures animées à 24/54/96 px, avant/après sur vrai Player.
2. Enrichissement manuel de l'attaque, du déplacement et des armures ;
   travail spécifique des tissus à chaque phase au lieu du calque statique.
3. Production du loup, bandit, archer, lancier, chevalier, soigneur, officier
   et boss en vues cardinales. Aucun faux miroir non validé.
4. R19.9 : raccord de la séquence visuelle attaques/impact et interruption
   sans faire progresser CT.
5. Validation des droits **par fichier physique**, via INT-03/R15 existants.
6. Goldens Studio/Player, lisibilité en combat, puis profiling GPU réel R19.D.

**Gate R19 toujours ouvert.** Ce commit n'atteste ni droits de publication,
ni direction artistique validée, ni performance 60 FPS, ni animation complète
du bestiaire. Les objets créés peuvent rester localement en mode auteur.
