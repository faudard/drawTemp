# Sporebound Studio — Hero Creator Expressions & Profiles (V1.26)

V1.26 conserve toute la personnalisation V1.25 et rend enfin les six colonnes de l’atlas visuellement distinctes. Le runtime de combat reste inchangé : le Hero Creator bake toujours un atlas standard 4 directions × 6 états.

## Nouveautés V1.26

- expressions indépendantes pour **Idle, Move, Attack, Cast, Hit et KO** ;
- neuf profils d’expression : Base, Joyeux, Concentré, Agressif, Mystique, Blessé, KO, Héroïque et Malicieux ;
- aperçu direct de chaque état dans le panneau de droite ;
- portrait avec expression, direction, zoom et décalage choisis indépendamment ;
- presets de silhouette : Équilibré, Chibi, Colosse, Élancé, Gros spore et Tank ;
- verrou de proportions pour lier largeur/hauteur du corps et taille/largeur du spore ;
- profils de palette séparés du look : recolorer sans toucher aux pièces, à la morphologie ou à l’identité ;
- quatre palettes fournies : Écarlate & Or, Arcanique violette, Mousse forestière et Cuivre toxique ;
- randomizer mis à jour avec silhouette et expressions cohérentes.

## Expressions et atlas

Les overrides d’expression ne remplacent que les couches du visage concernées (yeux, iris, pupilles, sourcils, bouche et éventuellement dents). Les cheveux, cornes, cicatrices, équipement et morphologie restent identiques.

Par défaut :

- Idle : Héroïque
- Move : Concentré
- Attack : Agressif
- Cast : Mystique
- Hit : Blessé
- KO : KO
- Portrait : Joyeux

Désactiver **Expressions animées** remet toutes les colonnes sur l’apparence de base.

## Workflow conseillé

1. Construire le héros normalement dans les onglets Tête, Visage et Corps.
2. Choisir une silhouette forte dans **Morphologie**.
3. Ouvrir **Expressions / États** et régler les six états.
4. Dans l’aperçu, sélectionner successivement Idle/Move/Attack/Cast/Hit/KO.
5. Choisir l’expression et la direction du portrait.
6. Optionnel : appliquer un profil couleur sans toucher au reste du look.
7. Sauver puis **Générer / appliquer au héros**.

## Compatibilité

Les apparences V1.19 à V1.25 restent chargeables. Les nouveaux champs disposent de valeurs par défaut et le format du `SporeUnitVisualDefinition` n’est pas modifié.

## V1.26.1 — chargement du plugin

Le bootstrap de Sporebound Studio est désormais tolérant aux erreurs des modules optionnels.

1. Ouvrir le projet avec Godot 4.7.1.
2. Aller dans **Projet > Paramètres du projet > Plugins**.
3. Activer **Sporebound Studio 1.26.1**.
4. Le bouton **Sporebound Studio** apparaît dans le panneau inférieur de l'éditeur.
5. Le Studio complet est chargé si tous ses modules sont valides. Si un module optionnel échoue, le plugin tente automatiquement d'ouvrir **Hero Creator** seul.

Le plugin ne doit plus être entièrement désactivé par une erreur d'un outil de map ou d'inspecteur.
