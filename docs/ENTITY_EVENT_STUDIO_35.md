# Entity & Event Studio 3.5 — éditeur visuel d’embranchements depuis la carte

**Dépendance :** Event Studio 3.4 (#129), qui fournit les gardes
`after_choice`, la convergence `after_any`, la prévisualisation des réponses
et leur replay `GameSession`. Cette tranche ne crée aucun second graphe
d'événements ni une autre interface de StoryBook.

## Dans le Studio, sans changer d’éditeur

Depuis **Carte → Entités → Événements / triggers**, cliquer
**Créer un embranchement narratif sur la case**. Le même assistant est
disponible sous **Graphe des événements → + Choix depuis carte**.

1. Sélectionner d'abord la case sur la carte. La case et la mission
   s'affichent dans l'assistant. Choisir un événement source déjà présent,
   ou laisser le nouvel ID proposé : dans ce cas, une condition **enter**
   sur la case sélectionnée et un message sont créés.
2. Remplir le titre, la question de dialogue, l'interlocuteur et l'ID de
   la scène initiale.
3. Définir les deux réponses avec leur ID, libellé, ID d'événement,
   conséquence **message** ou **hazard** (quantité), et texte de la scène
   propre à cette réponse.
4. Facultativement saisir un ID **Événement commun** et le texte de
   retrouvailles : cela crée une convergence `after_any` ET une scène
   narrative de réunion, sans boucle.
5. **Prévisualiser les deux chemins** : construit les ressources dans des
   copies jetables, puis utilise `preview_choice_routes` pour afficher
   les vrais effets de chaque choix dans un `Battle` isolé.
6. **Créer sur la carte** : valide toutes les données avec
   `Content.from_dict` et `GameProject.from_dict`, puis publie
   les deux résultats via le **même historique global** du Studio.
7. Les éditions avancées restent accessibles dans les éditeurs
   **Graphe des événements** (conditions, actions, liaisons) et
   **Narration** (réponses conditionnelles, drapeaux et scènes).

## Ressources réellement créées

À partir d’un nouveau point d'origine et de deux réponses, l'assistant
produit :

- `Mission.triggers` : un événement source `enter`, deux événements
  secondaires `after=[source]` + `after_choice={scene,choice}`,
  et éventuellement un événement de convergence `after_any=[a,b]`.
- `GameProject.story.scenes` : la question initiale, deux scènes
  de suite spécifiques et éventuellement une scène de retrouvailles.
  Les `next_scene` référencent des scènes ordinaires du StoryBook.
- `during_tactical_event[mission/source]` : lien du point de départ
  vers le dialogue initial, consommé tel quel par `GameSession`.
- Aucun breakpoint, condition artificielle ou configuration d'interface
  n'est enregistré dans le contenu final.

## Atomicité et compatibilité

L'API headless `author_choice_fork` ne modifie pas ses entrées. Elle
retourne **un contenu et un projet tous deux validés**, ou soulève
`RuleError`. L’UI n'installe le projet qu'après le remplacement du
Content ; tout échec est refusé sans nouvelle référence dangling.

Le `StudioHistory` capture cette action imbriquée comme **une seule
entrée Content+GameProject**, annulable/rétablissable, compatible avec
**Enregistrer tout** et la sauvegarde transactionnelle existante.

Le Builder est volontairement limité aux 2 premières actions les plus
fréquentes (`message`, `hazard`) ; il ne prétend pas remplacer le
catalogue complet des actions tactiques qui est toujours éditable dans
le Graphe. Le moteur et le manifeste de règles ne changent pas.

## Validation

```bash
python -m unittest tests_standalone.test_event_branch_builder_35 -v
python -m unittest tests_standalone.test_event_choice_branches_34 tests_standalone.test_event_chains_32 tests_standalone.test_event_debugger_33 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_event_branch_builder_35_gui -v
```

Le dernier test Xvfb a son propre **step bloquant** dans
`.github/workflows/standalone.yml`.

**Gate :** créer sur une case une fourche Attaquer/Négocier, constater
deux conséquences incompatibles et une convergence commune,
sauvegarder/recharger, annuler/rétablir en une action et rejouer les
choix authentiques en `GameSession`. Les aperçus arrangés ne se
prétendent jamais des replays certifiés du Player.
