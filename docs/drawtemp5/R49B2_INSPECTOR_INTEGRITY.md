# R49.B2 — Inspecteur Studio : références typées et brouillons protégés

> **Incrément P0, non certifiant.** PR empilée après R49.A (#383) et R49.B1 (#388). La présence du code dans une branche intermédiaire ne prouve pas sa livraison dans `master`.

## Portée réellement livrée

- Réutilise l'inspecteur R18.B : types `PropertySpec`, `validate_draft`, `edit_properties`, `AuthoringSession.preview_pair/apply`, Undo/Redo atomique et `connections` R2.D. **Aucun second propriétaire Content/GameProject.**
- Nouveau scanner **en lecture seule** des références typées déjà reconnues par `resource_links.TARGET_FIELDS` : cartes suivantes, scènes d'entrée, acteurs/objets mission-locaux, scènes, campagnes et clips. Il restitue la ressource source, le champ, le chemin et l'identifiant cible introuvable. Les champs libres de dialogue ne sont pas analysés comme des IDs.
- Budget explicite de scan (`max_nodes=20000`, `max_problems=200`) et profondeur bornée. Un résultat tronqué est **INCOMPLET**, jamais un diagnostic « 0 erreur » probant.
- Cache éphémère indexé par identité de session et révision, invalidé au changement de document. Pas de fichier supplémentaire, de télémétrie ou de mutation de l'historique.
- Dans l'inspecteur : compteur d'anomalies de la sélection, liens cliquables vers les **sources** des références absentes, emplacement technique consultable dans l'infobulle. Depuis **Outils → Vérifier les références du projet**, une liste globale permet de retrouver les propriétaires réels.
- Une saisie de propriétés non appliquée interdit la navigation vers un autre atelier, le changement de document et la fermeture. La sélection dans l'explorateur est indisponible jusqu'à **Appliquer** ou **Ignorer**. Les rafraîchissements programmatiques n'effacent pas la saisie ; une révision externe rend le commit obsolète et le refuse selon R18.B.
- **Appliquer** utilise toujours le preview/apply R1 existant et un seul pas Undo. **Ignorer** supprime uniquement le brouillon de l'interface, sans effectuer de `session.undo()`.

## Régression et sécurité

```sh
python -m unittest -v \
  tests_standalone.test_r49_inspector_integrity \
  tests_standalone.test_drawtemp5_r18b \
  tests_standalone.test_r49_workspace_focus \
  tests_standalone.test_r49_creator_ux \
  tests_standalone.test_r49_experience
```

Le test headless vérifie : liens valides, références de mission mal adressées, scènes/carte absentes, stabilité des résultats, absence de mutation, budget tronqué/refus explicite. Les tests Qt vérifient le signalement inline, la navigation à la source et l'absence de perte d'un brouillon lors de navigation/refresh.

## Limites

- Un audit **advisory** ne remplace jamais la validation canonique Content/GameProject, la migration, le preflight des assets, les licences, la détection des références dynamiques ou les contrats spécifiques de chaque atelier. Ce scanner réutilise les champs R2.D ; il ne prétend pas vérifier tous les schémas de R41–R48.
- Les widgets des éditeurs spécialisés R41–R48 ne sont pas tous convergés vers `PropertySpec` ; l'inspecteur R18.B reste le premier consommateur.
- L'édition en cours exige une action explicite ; un parcours clavier et lecteur d'écran **onscreen réel** doit confirmer l'ergonomie de cette garde.
- Les tests Qt offscreen sont du smoke logiciel et ne prouvent ni accessibilité réelle ni usage productif d'un auteur tiers.

## Gates

**R49.4 partiel / R49.5 partiel :** diagnostics croisés et protection des brouillons, sans certification multi-ateliers ni crash recovery complet.

Suite attendue : R49.B3 — Player en sous-processus Qt géré, événement de fin et retour au contexte Studio sans confondre « lancement réussi » et « playtest terminé ». Puis R49.C — certification auteur, performances sur gros projets et export réel.

**Décision : NO-GO pour le gate R49.**
