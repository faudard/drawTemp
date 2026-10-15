# DrawTemp 5.0 — R8.D : états, réactions et doctrines IA

> Suite de R8.A/B/C déjà fusionnés. **Tranche d'authoring**, pas nouvelle
> simulation ni clôture générale de R8.

## Implémentation

- **R8.6 — States & Reactions** : dans la Base RPG, sélectionner une unité
  placée puis ouvrir **États et IA tactique…**. Onglet *États, résistances
  et réactions* : ajouter/retirer les états initiaux (durée en ticks ; -1
  permanent), résistance élémentaire -100..100 %, réaction, soutien et
  mouvement passifs. Validation via le vrai `Content`, dans une transaction R1.
- **R8.6 — Skill effects** : troisième onglet permettant de remplacer un
  effet de compétence existant par `status` ou `cleanse` (état, durée,
  portée). La compétence reste dans `Content.skills` ; aucune table
  supplémentaire de statuts.
- **R8.7 — Enemy & AI Profiles** : modes `tactical`, `coordinated`,
  `phase_boss` et `adaptive_boss` lorsqu'ils sont supportés par
  `authored_rules_for_document`. Rôles médic, protecteur, chef, éclaireur,
  flanqueur et soutien ; doctrines existantes `pack_hunt`,
  `bandit_ambush`, `spear_hold`, `crossbow_reload`, escouade,
  formations `shield_wall`, `phalanx`, `escort`, et route de patrouille.
- **R8.11 (contrat fonctionnel)** : l'aperçu instancie une vraie
  `sporebound.engine.Battle` avec la version des règles réellement
  déduite du document. Il expose les états, la vitesse effective, les
  interdictions de mouvement/action, la résistance, l'état formation
  calculé et un digest. Le plan IA n'apparaît **que si cet ennemi
  est actuellement actif** ; les activations futures ne sont pas prédites.

Les états initiaux, éléments, passifs, routes et tags sont persistés **sans
modification de schéma** dans `Mission.units`. Les modèles de bestiaire
ne sont pas réécrits en modifiant une instance. Les doctrines existantes
dépendent des tags `doctrine:` et n'entrent pas en conflit avec les
patrouilles. Les autres tags (morale, boss, progression, etc.) restent
intacts.

## Cas de sécurité métier

- Un `spear_hold` ou une `phalanx` exige une arme `spear` ;
  `crossbow_reload` exige une arme `ranged`.
- Boss adaptatif et doctrines d'ennemis sont refusés sur les alliés.
- Une escorte cible un allié vivant à portée ; une patrouille exige au
  moins deux cellules distinctes et non bloquées, et ne peut pas coexister
  avec une doctrine.
- Réaction/support/mouvement inconnus, statut inconnu, durée zéro,
  résistance hors -100..100 et rôle dupliqué sont refusés sans mutation.
- **Une résistance élémentaire de 100 % supprime les dégâts de cet élément,
  pas un état `poison`/ `silence`** : le runtime ne modélise pas une
  immunité aux statuts dans ce contrat. La UI n'utilise pas ce terme.
- Les doctrines réutilisent `sporebound.doctrines31` et le graphe
  `tactical_rpg3`/R6 existant, sans second calcul IA ni scripts `eval`.

## Vérification

```bash
python -m pip install -e ".[qt6]"
python -m unittest discover -s tests_standalone -p 'test_drawtemp5_r8d.py' -v
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests_standalone -p 'test_drawtemp5_r8d_qt.py' -v
drawtemp-qt6-database
```

Tests attendus : résistance utilisée par `Battle._mitigate`, vitesse
calculée par les politiques de statuts, véritable `Battle` avec profils
tactiques, validité des tags et formation, annulation après échec,
Undo/Redo, roundtrip de Content+GameProject, fenêtre Qt offscreen.

**À certifier ensuite** : tests GitHub Actions verts sur les trois OS,
revue visuelle humaine sur Qt 6, parité Player et replay de chaque profil,
tests d'équilibrage pour plusieurs formations et automatisation de ces
preuves. Ce lot ne prétend pas livrer l'immunité aux statuts ou un
éditeur arbitraire de règles runtime.
