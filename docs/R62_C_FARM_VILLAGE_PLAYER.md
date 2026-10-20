# R62.C — Ferme & Village : boucle jouable dans le Player Qt

**Statut :** implémentation de la passerelle Player et des tests proposée en
PR, **gates non certifiés** ; dépend de R62.A/B.1 et de la branche sociale
R62.B.2. La fusion de R62.B.2 est une condition préalable.

## Fonctionnement

Sur une scène d'exploration qui déclare `org.drawtemp.farming` et/ou
`org.drawtemp.relationships`, le Player affiche un panneau **FERME & VILLAGE**
avec des actions typées :

1. Une parcelle libre affiche les cultures possibles, la graine consommée,
   le stock dans l'inventaire Campaign, le sol et la croissance attendue.
   **Semer** débite une graine réelle et journalise un reçu.
2. **Attendre jusqu'au prochain jour** avance exclusivement
   `LivingWorld` (R35) jusqu'à minuit selon le `ticks_per_minute` déclaré.
   Aucun timer QML, autre calendrier, timer système ou progression fantôme.
   Les fermes et affinités hors focus se synchronisent au jour R35.
3. La parcelle affiche **prêt** lorsque le moteur le calcule. **Récolter**
   crédite l'objet produit dans l'inventaire Campaign.
4. Le marchand R55 de la même scène permet de **vendre 1** objet à son prix
   déclaré, si le joueur en possède et si son stock dispose de capacité.
   L'or est exclusivement celui de `Campaign.progress.gold`.
5. Les PNJ R35 présents affichent leurs horaires et affinités R62.B.2.
   **Parler** respecte l'activité et la limite quotidienne ; **offrir**
   consomme un objet canonique déclaré et applique son gain, positif ou
   négatif, sans seconde base d'inventaire. Les PNJ positionnés nécessitent
   une interaction adjacente.
6. Les actions valides provoquent une révision SDK et passent par
   l'autosauvegarde existante. Les slots et backups reprennent le même
   `GameSession.recording()`, y compris les journaux de ferme,
   d'économie et de relations.

Le panneau affiche les seules entités de la zone active ; il reste
strictement absent des anciens projets sans R62. Les boutons désactivés
n'accordent aucune ressource et une commande invalide est refusée par le
moteur sans écriture partielle de Campaign.

## Architecture

- `drawtemp/player/r62_village.py` : projection uniquement ; ne lit que
  les vues figées `Simulation.farming_state`,
  `relationship_state`, `system_state`, `living_world_state` et les
  définitions GameProject. Aucun journal complet livré au renderer.
- `drawtemp/player/controller.py` : fonctions `farm_plant`,
  `farm_harvest`, `farm_feed`, `farm_collect`,
  `farm_wait_day`, `relationship_talk` et `relationship_gift`.
  Reçus automatiques issus de la longueur du journal **persisté**, pas du
  temps de l'interface. Un reçu explicite peut rejouer un retry.
- `drawtemp/player/qt_app.py` : slots Qt PlayerBridge.
- `drawtemp/player/Main.qml` : panneau de commandes QML, sans écriture
  directe d'objets de session.

**Précondition de contenu :** une parcelle cultivable, une culture dans
la saison, une graine réellement acquise (récompense de narration, stock
initial canonique, commerce, etc.), un marchand R55 autorisé pour l'objet
de récolte et un PNJ R35/R62 social. Le Player **ne crée pas**
automatiquement d'objets gratuits. Pour un slice immédiatement jouable,
l'éditeur doit préparer ces sources de départ dans le projet.

## Régression

```sh
python -m unittest tests_standalone.test_r62_village_player -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_r62_village_player_gui -v
python -m unittest tests_standalone.test_r62_farming_life \
  tests_standalone.test_r62_relationship_life -v
```

Le test headless monte une scène R25, la ferme R62.A, les habitants
R62.B.2 et une boutique R55. Il attribue **uniquement dans le setup**
une graine au Campaign canonique, puis exécute :
**semer → refus de récolte précoce → jour suivant → récolter →
vendre → offrir → parler → sauvegarder → restaurer → rejouer les reçus**.
Le test vérifie les soldes, scores, calendriers et journaux sans
double consommation ni double gain.

Un smoke PySide6 ouvre la **vraie** application QML du Player,
vérifie les objets de commande, utilise le bridge réel et sauvegarde /
recharge. Il ne remplace pas un test visuel, un parcours souris réel ni
une certification GPU/export.

## Gate toujours ouvert

Pour fermer complètement R62, il reste à exécuter la CI et le parcours
visuel sur plateformes cibles, vérifier la lisibilité et l'accessibilité
de l'UI, fournir un projet de référence entièrement autonome sans seed
de test, valider plusieurs saisons et de longues sessions, puis clôturer
les éventuels conflits d'intégration des PR parentes.
