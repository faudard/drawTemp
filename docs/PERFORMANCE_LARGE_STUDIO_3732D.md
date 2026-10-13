# 3.7.32D — Rafraîchissement du Studio à grande échelle

## Objectif

Réduire les recalculs évitables sur 32×32, 64×64 et 128×128, sans créer un
second modèle de jeu, ni changer le gameplay, la sélection, le format de
sauvegarde ou les assets.

## Fast paths livrés

1. **Projection Content validée et réutilisée.** `EditorContentProjection`
   conserve le modèle issu de `Content.from_dict()` tant que le document
   auteur est identique *en valeur* (empreinte JSON canonique). La génération
   change après un paint, undo, redo, changement de mission/document ou
   mutation profonde ; une validation refusée n'écrase pas la projection valide.
   Ce parcours conserve le coût d'empreinte du document, mais évite une
   nouvelle construction de l'ensemble des modèles sur chaque sélection.
2. **Renderer des grandes cartes isométriques.** Au-delà de 4 096 cases,
   `EditorRenderCache` reçoit l'identifiant de génération validée. Il peut
   ainsi vérifier un rendu sans recopier profondément le plateau, la mission
   et les unités ou reparcourir les hauteurs sur chaque changement de
   sélection. Les appels externes et les combats conservent la vérification
   conservatrice antérieure. Les cartes plus petites conservent leur politique
   précédente d'invalidation géométrique.
3. **Mini-carte.** Le fond statique est réutilisé tant que mission, contenu et
   couches affichées restent identiques ; le rectangle de viewport est
   actualisé séparément. Le mode combat reconstruit toujours le fond et ne
   réutilise jamais une scène statique de l'édition. Un élément Canvas ajouté
   hors du composant invalide le fond.
4. **StudioPanels.** La sélection de cases met uniquement à jour le
   libellé. Les coups de pinceau sur le terrain (hors effacement et objectif)
   actualisent immédiatement la carte, l'inspecteur et la mini-carte mais
   **diffèrent le rafraîchissement des onglets Studio masqués**. L'événement
   `<<NotebookTabChanged>>` force leur synchronisation dès qu'un onglet est
   ouvert. Les modifications d'acteurs, d'objets, d'événements, de déploiement
   ou d'objectifs continuent le parcours de rafraîchissement complet.
5. **Sélection de cases.** La restriction aux limites de carte parcourt les
   cases sélectionnées, et non toutes les cases du plateau.

## Tests

- `tests_standalone/test_large_map_refresh_3732d.py` : 32²/64²/128²,
  mutations imbriquées, retour arrière, validation refusée, mise en cache du
  fond, changement de couches et édition externe du Canvas.
- `tests_standalone/test_large_map_refresh_3732d_gui.py` : véritable
  application Studio sur une carte 128² ; un déplacement de mini-carte
  conserve les identifiants du fond ; un coup de pinceau invalide le fond.
- Le nouveau workflow Ubuntu/Xvfb exécute les deux suites et archive
  `performance-large-studio-3732d.json`.

## Profilage reproductible

    python3 -m unittest tests_standalone.test_large_map_refresh_3732d -v

    SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest -v \
      tests_standalone.test_large_map_refresh_3732d_gui

    # Smoke CI rapide
    xvfb-run -a python3 scripts/benchmark_large_studio_refresh_3732d.py \
      --quick --output large-studio-smoke.json

    # Baseline sur machine de référence
    xvfb-run -a python3 scripts/benchmark_large_studio_refresh_3732d.py \
      --sizes 32,64,128 --cells 24,54,96 --samples 100 \
      --output large-studio-reference.json

Deux modes sont exécutés dans des fenêtres séparées sur la même machine :
`Content.from_dict` + snapshot conservateur du renderer contre projection
validée + révision. La mesure inclut peinture Tk idle, p50/p95/p99, mémoire
RSS et items Canvas. Elle **n'inclut pas l'entrée matérielle ni tous les
onglets de l'application** ; l'intégration Tk Studio est contrôlée
séparément. La durée observée sur CI partagé n'est pas un seuil universel.
Moins de 100 échantillons : queues p99 exploratoires.

## Critères d'acceptation

- CI entière verte, tests GUI Xvfb inclus ;
- invariance fonctionnelle des peintures, undo/redo, couches, sélection,
  combats, panneaux et sauvegardes ;
- mêmes sorties Canvas pour les scènes équivalentes et pas de stale cache ;
- pas de budgets p95/p99 bloquants avant collecte sur les postes de référence.

Les optimisations suivantes visent le diff local de tuiles 128²,
les autres onglets lourds et l'instrumentation granulaire de
`StudioPanels.refresh`. Ne pas confondre l'accélération des parcours ciblés
avec une garantie de fluidité totale sur tous les matériels.
