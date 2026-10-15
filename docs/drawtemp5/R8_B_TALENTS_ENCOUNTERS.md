# DrawTemp 5.0 — R8.B : arbres de talents et rencontres

**Base :** `master` après consolidation #237.
**État :** tranche implémentée et en revue ; ce document ne certifie pas le gate R8 complet.

## Livrables de cette tranche

- **R8.3 (complément)** : visualisation native Qt des DAG classes/talents via
  `QGraphicsScene`, choix d'une classe, prérequis, niveau, XP/JP sous contrat
  existant, coût JP, spécialisations exclusives, bonus et compétences.
  Actions création/modification/suppression validées par
  `sporebound.class_ai_authoring`. Suppression interdite si d'autres talents
  utilisent la référence ; cycles refusés.
- **R8.8 (première version jouable)** : composition de rencontre depuis la
  même base RPG, choix mission, visualisation 2D des cases et unités, placement
  d'archétypes existants, déplacement et retrait, rôles/formation/escorte,
  objectif et récompense. Les missions restent dans `Content.missions`.
- **R8.1 / R8.10** : deux actions supplémentaires accessibles dans la fenêtre
  R8 native ; chaque commande passe par `AuthoringSession.preview_pair`,
  validation croisée Content/GameProject, et une entrée Undo/Redo, sans JSON
  édité directement.
- **R8.11 (complément)** : aperçu interactif des placements et des branches de
  talents. Le graphe et la carte représentent l'état actuellement édité ;
  **ils ne simulent pas une issue de combat**.

## Démarrage / scénario utilisateur

```bash
python -m pip install -e ".[qt6]"
drawtemp-qt6-database
```

1. Créer une classe et des compétences dans la Base RPG, puis ouvrir
   **Classes et talents…** dans la barre d'outils ou sur la classe sélectionnée.
2. Créer un talent de défense, un talent fils (pré-requis), vérifier les liens
   et coûts JP dans le graphe. Tenter un cycle : le changement est rejeté,
   et le document reste inchangé.
3. Créer un archétype de Lancier avec le type d'arme `spear`, puis ouvrir
   **Composer une rencontre…**.
4. Choisir une mission, cliquer sur une case libre, placer le Lancier dans une
   équipe, lui attribuer une phalange. Déplacer le pion, définir l'objectif
   et la récompense, puis enregistrer.
5. Annuler/rétablir une modification, recharger les deux fichiers, vérifier
   les IDs, les coordonnées, la classe et les effets inchangés.

La référence automatisée `lancer_example` de R8.A reste disponible.
`tests_standalone/test_drawtemp5_r8b.py` valide les DAGs, les refus
atomiques, les créations/déplacements de vrais acteurs, la phalange, le
round-trip de sauvegarde et l'historique. `test_drawtemp5_r8b_qt.py` vérifie
l'interface avec PySide6 sous `QT_QPA_PLATFORM=offscreen`.

## Contraintes et limites explicites

- **Un modèle n'est pas une instance** : les archétypes sont copiés dans
  les missions et leur modification ne réécrit pas silencieusement les unités
  déjà placées.
- **Modèle canonique unique** : `Content v1`/`GameProject`. Le Studio Tk
  historique n'est pas supprimé.
- **Refus des incohérences** : spawn bloqué/occupé, dernier acteur indispensable
  à une équipe, mauvaise formation ou escorte, cycle de talents, compétence
  inconnue, référence requise, coût JP invalide.
- **Sans promesse d'équipement runtime automatique** : l'équipement reste
  défini par `Content.equipment`. Affectation au héros via la campagne/les
  règles existantes, pas une nouvelle colonne dans `Unit`.
- **Aperçu de rencontre 2D seulement** : aucune substitution au renderer
  isométrique partagé R3, au Player R12 ou au Battle Lab R13.
- **R8 non clos** : sélection/édition groupée directement dans l'interface,
  renommages/migrations, gestion complète des variables globales et des états,
  profils IA approfondis, aperçus sprites/portraits et QA GUI humaine restent
  à traiter. La validation graphique offscreen ne certifie pas un rendu GPU.

## Commandes de validation

```bash
python -m unittest discover -s tests_standalone -p "test_drawtemp5_r8_database.py" -v
python -m unittest discover -s tests_standalone -p "test_drawtemp5_r8b.py" -v
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests_standalone -p "test_drawtemp5_r8b_qt.py" -v
QT_QPA_PLATFORM=offscreen python -m drawtemp.studio.rpg_database_qt --smoke
```

Le workflow `drawtemp5-r8.yml` doit donner le statut des validations Linux,
Windows et macOS ; en cas d'échec, le gate reste bloqué.
