# 2.5.4.1 — Campaign & Siege Studio (fondation)

L'onglet **Campagne & sièges** travaille sur la même configuration `.game.json`
que les autres outils du Studio : il ne crée aucun registre secondaire.

## Création sans JSON

1. Créer au moins deux missions et sélectionner une campagne dans
   **Jeu, campagnes et sauvegardes**.
2. Cliquer **Créer siège** : deux fronts uniques liés à deux missions sont
   initialisés, avec un focus tactique et les doctrines existantes.
3. Modifier la mission, la force, l'opposition et la doctrine de chaque front.
   Ajouter / retirer les fronts (minimum deux) ou définir le front focalisé.
4. Configurer les réserves et la capacité de convois.
   Ajouter des routes dirigées `reserve → front` ou `front → front`,
   avec leur temps de trajet en tours.
5. **Simuler 5 tours** affiche la projection **hors combat** du
   `FrontDirector`. Elle ne déclenche aucune bataille ni écriture de slot.
6. **Enregistrer projet de jeu…** écrit l'option `sieges` dans le manifeste
   de campagne. Les boutons **Annuler siège / Rétablir siège** sont locaux
   à ce panneau et gèrent au plus 50 modifications par session du Studio.

## Contrat du projet

La clé optionnelle `sieges` est un dictionnaire indexé par identifiant de
campagne; chaque plan référence 2 à 20 fronts, une mission unique par front,
un focus, leurs trois paramètres stratégiques et la logistique.

Les projets v1 historiques n'émettent toujours aucune clé `sieges`
lorsque celle-ci est vide, garantissant la stabilité des digests et des
slots déjà existants.

Le Player affiche **Déployer le siège scénarisé** quand toutes les missions
du plan sont débloquées. Il appelle `PlayerController.start_configured_siege()`,
ce qui génère une vraie `GameSession.start_fronts(...)` avec ses doctrines,
ses réserves et routes, puis produit immédiatement un checkpoint vérifié.
Les missions non débloquées ne sont jamais contournées par l'éditeur.

## Limites (travaux suivants 2.5.4.2+)

Cette tranche édite **les fronts et la logistique de base**. L'édition visuelle
des liens d'événements entre fronts, des vagues de renforts, des convois
attaquables, des chemins alternatifs, des fins diplomatiques et des
transitions de campagne exige une interface dédiée et des tests E2E
supplémentaires. La prévisualisation stratégique ne simule pas les
combats tactiques ni les événements déclenchés par leurs résultats.
