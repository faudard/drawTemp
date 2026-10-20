# R60.B1 — Les Sentinelles de l'Ambre : vitrine de production hybride

**Statut : code candidat et tests ajoutés. Pas de certification R60, R60.B ou version 10.0.**

Ce premier lot propose un **jeu d'exemple entièrement original dans son habillage**, construit en combinant des contrats existants, sans nouvel état métier ni second moteur :

- R53 : Elya/Oren/Mira, exploration en mouvement libre, combat RPG par commandes, transition vers bataille tactique CT réelle, retour par le routage R25.
- R55 : matière première `resin`, fabrication de `lantern` à partir de deux unités toutes les deux simulations ticks, achat de deux lanternes auprès du marchand du village, livraison de la quête `relight_beacon`; stocks et reçus déterministes, argent et inventaire sous le Campaign canonique.
- R51 : trois écrans HUD déclaratifs (`r60_exploration`, `r60_tactical`, `r60_inventory`), breakpoints 640/1100, projections typées et contrôles explicitement autorisés.
- R1/R15 : création depuis le Studio grâce au modèle Creator `hybrid_r60`, deux fichiers canoniques Content et GameProject v1, prévisualisation et application des modifications R55/R51 dans `AuthoringSession`, historique Undo/Redo.

La présentation est originale, mais réutilise **le contenu et les trois scènes du jeu exemple R53** (village, forêt, crypte). Il ne s'agit **pas encore** d'un jeu vitrine inédit construit de bout en bout, d'un nouveau monde R54 à streaming, ni d'une UX boutique visuelle finalisée.

## Scénario VS-60.B1

1. Créer le projet dans le Creator avec le modèle `hybrid_r60` (pas d'édition manuelle de JSON).
2. En ville, avancer quatre ticks déterministes : deux lanternes disponibles en boutique. Aucun don d'or implicite.
3. Explorer le bois, gagner le combat RPG natif et recevoir la récompense canonique de 12 or ; revenir au village.
4. Acheter deux lanternes (coût 10 or), livrer la quête du phare une seule fois, sauvegarder, redémarrer et vérifier l'impossibilité d'une duplication du reçu ou de la récompense.
5. Traverser la forêt jusqu'à la crypte, gagner le second combat RPG, déclencher une **vraie** mission CT via R25, sauvegarder/charger pendant le CT.
6. Gagner le CT par les commandes natives et l'IA, revenir au village, terminer la quête narrative R41, puis vérifier le solde final (70 or de récompenses R53 moins 10 or d'achat = 60 or nets) et le replay final.

Les tests rejettent les sauvegardes où le stock de lanternes est falsifié, y compris lorsque la somme de contrôle externe est recalculée.

## Exécution

```sh
python -m unittest tests_standalone.test_r60_hybrid_showcase -v
python -m unittest tests_standalone.test_r53_hybrid_slice tests_standalone.test_r55_system_design tests_standalone.test_r51a_ui_layout -v
python -m examples.r60_production_showcase
```

CI : `.github/workflows/r60b1-hybrid-showcase.yml`, Python 3.10 et 3.12 Linux. Le rapport CLI prouve uniquement un parcours headless de cette version de code **si et seulement si la CI publie ses jobs et un artefact**.

## Compatibilité et limites

- Aucun changement des structures de sauvegarde ou des moteurs; les extensions R51/R55 sont opt-in et tous les enregistrements restent vérifiés avec `GameSession`.
- Le projet `hybrid_r53` existant reste inchangé et ne possède ni ces extensions R60 ni ce modèle Creator.
- Le HUD déclaratif ne vaut pas qualification graphique Qt onscreen ni a11y; les combats CT/RPG gardent la limitation de synchronisation des PV/PM inter-modes de R53.C1.
- La formule productive R55 n'est pas un menu visuel de crafting; l'inventaire du Player et l'atelier de fabrication visuel demandent une tranche R60.B2.
- Deux **régions de production** en streaming R54, localisation validée, mises à jour/rollback R59 et UX d'auteur tiers restent à prouver, avec les gates P0 antérieurs.
- Vérifications réelles CI, GPU, natif tri-OS, licences et export sur PC propres nécessaires avant une décision R60.C. La décision de release demeure **NO-GO**.

**Suite cible :** R60.B2 — scène boutique et HUD écran par écran dans le Player, autorité des PV/PM inter-modes, scènes régionales, quête modifiable graphiquement et sauvegarde/reprise aux transitions; R60.C — certification indépendante.
