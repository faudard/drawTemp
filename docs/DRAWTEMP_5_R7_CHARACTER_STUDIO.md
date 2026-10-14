# DrawTemp 5.0 — R7 Character Creator & Animation Studio

## État de la PR

Tranche fonctionnelle indépendante du Player 5.0. Les animations et
calques sont enregistrés comme recettes d'édition et publiés dans le
format canonique AssetRegistry v1. Aucun changement Content/GameProject,
simulation, CT, sauvegardes ou RNG.

**Ce n'est pas encore la certification R7 complète.** La validation réelle
de Jeanne paysanne/armure en combat dans le Player Qt 6 dépend encore des
jalons R3/R4/R12 et de créations artistiques distinctes. Une tenue
dupliquée n'est pas présentée comme de l'art original.

## Exécution

Python 3.12 et Qt :

~~~sh
python -m pip install ".[qt6,art]"
python -m drawtemp.studio.character_studio --root .
~~~

Headless (Python 3.10+ ; sans Qt) :

~~~sh
python -m pip install ".[art]"
python -m drawtemp.assets.characters --template jeanne --save-template jeanne.character.json
python -m drawtemp.assets.characters --recipe jeanne.character.json --root . --export /tmp/jeanne-export
python -m unittest tests_standalone.test_drawtemp5_r7 -v
~~~

Le pack exporté contient atlas.png, registry.json, character.json et les
portraits. Régions de l'atlas, durées et IDs des animations sont validés
par sporebound.assets.AssetRegistry. Le Player Qt R12 pourra choisir les
IDs selon le contrat anim_<character>_<outfit>_<action>_<direction>.

## Parcours de création

1. Choisir Jeanne ou un prototype chibi. Les quatre colonnes de l'atlas
   historique Jeanne identifient réellement S/N/E/O et les huit lignes
   historiques couvrent idle, walk, attack, hit et death.
2. Choisir une variante, ou dupliquer la tenue pour créer peasant / armor.
   Remplacer les sprites ou calques : un renommage seul ne valide pas la
   distinction des deux tenues.
3. Choisir orientation et animation. Modifier les images clés dans la
   timeline : source PNG, région, durée et offset. Lecture temps réel avec
   boucle ou arrêt selon les métadonnées du clip.
4. Configurer les calques modulaires directionnels (cheveux, cape, vêtements,
   arme...), couleur et alpha ; l'aperçu et l'export emploient le même
   compositeur RGBA.
5. Enregistrer la recette, inspecter la QA, exporter le pack. Undo/Redo
   disponibles (Ctrl+Z / Ctrl+Shift+Z).

## Modèle, compatibilité et sécurité

Document auteur version 1 : id, name, size, pivot, variants.
Chaque variante contient clips, layers et expressions. Un clip comporte
des orientations et des images-clés (source, région, durée, offset).
Les pieds gardent un pivot commun quelle que soit l'animation.

Les références PNG sont portables, relatives à la racine du dépôt et
résolues sans sortie par traversée ou symlink. L'export ne modifie jamais
les images source et publie ses ressources par remplacement atomique.
Les opérations d'édition sont transactionnelles, versionnées et annulables ;
un aperçu calculé sur une ancienne révision ne peut pas être commité.
Aucune dépendance Qt/Tk dans le module modèle.

## Périmètre détaillé

| Lot | Couverture de la tranche |
| --- | --- |
| R7.1 Character Workspace | Qt Widgets, modèles, variantes, aperçu |
| R7.2 Modular Appearance | Calques par slot, orientation et offset |
| R7.3 Color Customization | RGB et opacité ; palettes avancées encore à faire |
| R7.4 Directional Compositor | S/N/E/O avec alignement sur pivot commun |
| R7.5 Outfit Variants | Variantes d'une identité ; art final encore à créer |
| R7.6 Animation Editor | Timeline, durée, duplication, playback ; onion skin restant |
| R7.7 Combat Animation Set | Contrat de 9 actions, manquants diagnostiqués |
| R7.8 Sprite Sheet Export | Atlas RGBA, frames, timings et AssetRegistry v1 |
| R7.9 Portrait & Expressions | Expressions existantes prévisualisées et exportées |
| R7.10 Equipment Visualization | Slots weapon/clothing/cape ; liaison R8 restante |
| R7.11 Animation Consistency QA | Chemins, dimensions, couverture, tenue distincte |
| R7.12 Character Library | Jeanne, villageois, chevalier et archer ; bestiaire restant |

## Gates de sortie

- [x] Cœur auteur testable sans Qt et sans Pillow.
- [x] Pack exportable en AssetRegistry v1 sans changer Content.
- [x] Variantes réellement composées et QA refusant deux tenues identiques.
- [x] Undo/Redo révisionné et protection des sources.
- [ ] CI multi-OS validée sur le SHA final.
- [ ] Revue GUI humaine sur les trois OS.
- [ ] Assets peasant et armor réellement distincts, animations marche et
      attaque de qualité pour quatre directions (pas de frames recopiées).
- [ ] Branchement visuel effectif dans renderer Qt R3 et Player Qt R12.
- [ ] Certification en jeu : changement de tenue, animation, sauvegarde,
      export Player autonome.

Le gate R7 global reste ouvert tant que ces points ne sont pas fermés.

QA stricte Jeanne :

~~~sh
python -m drawtemp.assets.characters --recipe jeanne.character.json --root . --strict
~~~
