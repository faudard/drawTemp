# R62.B.1 — Farm Studio natif : authoring typé et transaction canonique

**Statut :** implémenté sur branche empilée au-dessus de
[R62.A (PR #423)](https://github.com/faudard/drawTemp/pull/423) ;
aucune certification CI, UX, GPU ou release déclarée.

Ce sous-lot lance [R62.B — Farm & Relationship Studio](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md)
sans créer de base d'édition parallèle et sans étendre le runtime R62.A.

## Parcours Studio

Dans le Studio Qt : **Outils → Farm Studio R62 : cultures et élevage…**
ou la commande correspondante dans la palette.

- **Paramètres** : seed, jours/saison (2..120), météo déterministe opt-in.
- **Parcelles** : identifiant stable, scène d'exploration canonique et sol.
- **Cultures** : graine/objet consommé, objet produit, quantité, croissance,
  sols et saisons multiples avec cases à cocher.
- **Animaux** : scène, alimentation, objet produit, cadence et quantité.
- **Aperçu** : validation de l'extension et du couple Content/Project via
  `AuthoringSession.preview_project`; états initiaux saison/météo projetés,
  sans mutation de partie ni sauvegarde.
- **Historique local** : annuler/rétablir (50 étapes par défaut), suppression
  et édition via contrôles typés. Pas de renommage silencieux d'identité.
- **Appliquer au projet** : exactement une transaction globale R1,
  révision attendue obligatoire, sauvegarde seulement par mécanisme Studio
  existant. L'Undo/Redo global reste maître.

Le calendrier R35 est obligatoire. Si absent, une case **explicite** permet
d'initialiser un document R35 minimal **dans la même transaction** que
l'extension R62. Une horloge existante, ses PNJ et ses horaires sont conservés
à l'identique ; elle n'est jamais réinitialisée. Le bouton **Modifier les
horaires PNJ R35…** ouvre l'éditeur natif de routines existant, et un
changement de révision invalide le brouillon R62 ouvert.

Les listes d'objets proviennent des équipements Content et des ressources R55
déjà déclarées. Les scènes proviennent de l'exploration du projet. Toute
référence inconnue est refusée et jamais corrigée automatiquement.

## APIs headless

`drawtemp.studio.farming_authoring` :

- `FarmDraft(session)` : CRUD typé (upsert/remove) par famille, paramètres,
  historique local, `preview()`, `apply()`.
- `preview_farm_design(..., initialize_clock=False)` : validation et
  proposition sans effets de bord, avec rapport de compteurs.
- `apply_farm_design(session, preview)` : validation d'appartenance/révision
  via `AuthoringSession.apply`. Un brouillon périmé n'écrase pas une
  modification faite ailleurs.
- `initial_clock()` et `empty_farm()` : fabriques déclaratives sans I/O.

Le runtime persiste toujours `GameSession` et son inventaire Campaign ; les
widgets ne gèrent ni récoltes, ni récompenses, ni horloge séparée.

## Tests

```sh
python -m unittest tests_standalone.test_r62_farming_authoring -v
python -m unittest tests_standalone.test_r62_farming_life -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r62_farming_gui -v
```

La CI `.github/workflows/r62-farming-studio.yml` propose matrices Python
3.10/3.12 et Qt offscreen 3.12. Seuls les tests réellement exécutés et
concluants pourront certifier ce lot.

## Hors périmètre / R62.B.2 et R62.C

- **R62.B.2** : relations sociales à progression persistée, commandes
  conversation/cadeaux, diagnostics de routines et conditions visuelles, tests
  de non-duplication sociale et de checkpoint.
- **R62.C** : vertical slice ferme–village jouable, économie R55, progression
  PNJ, boucle complète dans le Player Qt, plus validation UI humaine.
- CI réelle sur SHA final, tests de performance longue saison et rejouabilité
  multi-seeds restent des gates ouverts.
