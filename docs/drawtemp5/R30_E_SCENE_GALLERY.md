# R30.E — Galerie de modèles narratifs multi-genres

**Statut : première tranche implémentée, proposée en PR draft, empilée sur
R30.D (#343), R30.C (#340), R30.B (#329) et R30.A (#305).**
R30.8 reste **PARTIEL** : cette galerie contient des exemples de scènes
narratives valides, mais pas de jeux complets ni de scènes temps réel
certifiées. La roadmap R25–R29 reste requise pour R30.10.

## Contenu livré

Une bibliothèque embarquée, versionnée, **entièrement hors réseau**, inclut
quatre exemples originaux, en français :

| Famille de découverte | Modèle | Ce qui est réel | Ce qui n'est pas livré |
|---|---|---|---|
| SRPG | Avant-poste tactique | Scène et choix canoniques de briefing | Nouveau combat tactique |
| Action-aventure | Le sentier oublié | Dialogue et exploration racontée | Mouvement top-down temps réel, collisions, puzzles |
| RPG classique | La halte des voyageurs | Scène d'auberge, bifurcation narrative | Combat au menu, boucle ville-donjon |
| Hybride | Du camp au conseil | Transition narrative entre deux lieux | Changement réel de moteur libre/tactique |

Les textes et les scènes sont de nouveaux exemples déclaratifs. Ils ne
contiennent ni fichiers d'art tiers, ni scripts exécutables, ni appels réseau.

Le JSON est installé dans la distribution Python (wheel) via pyproject.toml.
Il est relu par importlib.resources et vérifié par un schéma strict :
version, genres connus, identifiants uniques, bornes de scènes/choix/texte,
graphes sans destination absente ni cycle, absence d'effets exécutables ou
de champs inconnus, statut toujours "narrative-scene-only".

## Réutilisation transactionnelle

1. Ouvrir Studio et choisir **Outils → Packs et revue des conflits**.
2. Onglet **Galerie de modèles** : parcourir les quatre genres, filtrer
   les modèles, lire leur description et les dialogues/choix réels.
3. Choisir un **namespace** (ex. "village") ; le projet générera des
   identifiants sous la forme "r30e_village_forest_path".
4. Facultativement, sélectionner une campagne existante **sans** scène
   d'entrée actuelle. Le lien est opt-in ; une scène existante n'est
   jamais remplacée automatiquement.
5. **Prévisualiser** : construire un GameProject.story candidat et appeler
   AuthoringSession.preview_project/validate_pair. Le contenu tactique
   Content n'est pas modifié ; collisions d'IDs et de liens refusées.
6. **Ajouter dans le Studio** après confirmation : appel explicite à
   AuthoringSession.apply, une seule opération Undo/Redo ; aucune
   sauvegarde implicite sur disque.
7. L'utilisateur peut conserver la nouvelle scène dans le projet en
   cliquant **Enregistrer** dans le Studio.

La galerie peut servir dans plusieurs projets indépendants. Elle peut
également réutiliser un même modèle plusieurs fois dans un projet, avec
un namespace distinct. Les IDs et liens next_scene sont réécrits ensemble ;
aucun ID original existant n'est écrasé.

## API headless

    from drawtemp.studio.r30_scene_gallery import (
        gallery_entries, GalleryController,
    )
    from drawtemp.sdk.authoring import AuthoringSession

    session = AuthoringSession.open("monjeu/game.json")
    print([entry.to_dict() for entry in gallery_entries()])

    gallery = GalleryController(session)
    review = gallery.preview("forest", "village")  # pas de mutation
    transition = gallery.apply(review)             # une transaction Undo
    # session.undo() annule l'ajout si nécessaire
    # session.save() reste un choix utilisateur distinct

Autres identifiants de modèle : "tactical", "inn", "bridge".

Le mode campaign_id permet une liaison facultative :

    gallery.preview("tactical", "poste", campaign_id="main")

Si main possède déjà une entrée narrative, la preview est **refusée**
et ne remplace pas l'introduction existante.

## Vérification

Tests headless (doivent être verts sur HEAD de PR) :

    python -m unittest tests_standalone.test_drawtemp_r30e_gallery -v

Tests Qt offscreen, Python 3.12 et PySide6 :

    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp_r30e_qt -v

Le workflow R30.E exécute les tests sur Windows, Linux et macOS, les suites
R30.A/B/C/D, R1 Authoring, et la baseline tactique Jeanne.

Les tests couvrent explicitement un catalogue de quatre genres, la
validation des graphes et types, des collisions, des previews périmées,
l'Undo/Redo, la compatibilité Content/GameProject, l'absence d'écriture
disque implicite, l'import dans deux projets indépendants et le filtrage
interactif Qt.

## Limites et suite

- Cette étape ne construit pas de jeux temps réel ni un Player hybride.
  Les quatre exemples sont des **scènes narratives** éditables dans
  GameProject.story, sans certification action-aventure/RPG classique.
- La liaison à une campagne est facultative ; sans liaison à une scène
  d'entrée ou autre événement, les scènes existent dans le projet mais
  ne sont pas lancées automatiquement en gameplay.
- Aucun modèle arbitraire, fichier externe de JSON de scène non signé,
  pack de scripts, génération IA, marketplace ni asset sous licence tiers.
- L'intégration d'un catalogue de packs user-authored et un modèle complet
  de donjon/monde/terrain devra attendre les contrats de R25–R29.
- R30.6 (performance), R30.7 (génération optionnelle), R30.9 (SDK exhaustif)
  et R30.10 (deuxième jeu et certification inter-genres) restent ouverts.
