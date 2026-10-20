# ADR R52.A — Contrat de profondeur 2.5D sur le renderer Qt Quick partagé

**Statut :** implémentation de fondation P0, sans gate GPU ni release certifiée. **Date :** 2026-10-20.

## Décision

Conserver exactement le pipeline R3 : `iso_scene.Camera`, `IsoProjection` / `TopDownProjection`, `render_items`, `pick`, `TileChunkIndex`, `qt_viewport.RendererController` et les deux vues Qt Quick existantes. Ne créer **aucun second renderer**. Les couches visuelles optionnelles sont placées derrière les terrains et ne capturent pas la souris ; les éléments gameplay et les HUD continuent d'utiliser les transformations canoniques et le picking R3 sans facteur de parallaxe.

## Contrat R52.A

- Schéma purement présentation, `version=1`, `projection` identique à celle du controller, `layers` plafonnées à 8 ; pas de référence de shader ni de chemin/URL d'image arbitraire. Une couche est une surface couleur avec identifiant, centre en coordonnées de scène `(x,y)`, dimensions en pixels de projection, `parallax` dans `[0,1]` et `opacity` dans `[0,1]`.
- Définition du déplacement décoratif : `screen_x = W/2 + (pan_x + projected_x * zoom) * parallax` ; identique en y. `parallax=1` correspond exactement à la projection R3, `parallax=0` ancre le décor au centre du viewport. Le tri entre décors respecte l'ordre déclaré ; ils restent derrière la grille et les objets.
- Monde/écran interactifs : `camera.screen(projection.project(x,y,z))` et `projection.unproject(*camera.world(sx,sy),z)`. Aucun calcul décoratif n'entre dans `cellAt`, `pickAt`, les structures, le calcul du relief, CT ou le replay.
- Validation avant mutation via `RendererController.setDepthProfile`. Erreur de schéma, clé inconnue, version non reconnue, NaN/Inf, doublon, taille excessive ou projection divergente => exception et état inchangé. Profil absent => rendu original.
- Effets : demandes booléennes `lightmap` / `shadows` acceptées comme intention mais **désactivées explicitement** (`not-implemented-r52b`) jusqu'à un vrai pass partagé approuvé. Le logiciel n'est donc pas présenté comme ayant des lightmaps ou des ombres GPU en R52.A.

## Backend, performances et fallback

`backend_plan` est un plan **indicatif** : le choix réel RHI/Qt Quick doit être fait avant la création du moteur par le bootstrap Qt existant. Si le matériel n'est pas accessible, préférence au renderer logiciel explicitement déclaré et preuve de dégradation ; si aucun backend admissible, échec bloquant. Aucun test GPU physique n'est affirmé ici.

Budget de départ : 8 couches visuelles, taille par couche 2048 × 2048 pixels de projection maximum, aucune allocation texture de décor ni téléchargement d'assets par ce contrat. Les budgets CPU/GPU p95/p99, atlas, lightmaps, ombres réelles et culling avancé sont reportés à **R52.B/C** et devront être mesurés sur les trois OS et hardware réels.

## Tests et critères de fusion

- Headless : profils invalides, copie défensive, conversion bidirectionnelle, trois fixtures de caméra (iso normal, iso zoom/pan et top-down), picking au centre des tiles, ordre R3 inchangé et dégradation explicite.
- Qt : charger chaque vue avec couches activées, vérifier avec QTest onscreen que le terrain et le HUD restent au premier plan et que la sélection fonctionne, puis générer goldens par DPI / backend (non couvert par le test headless).
- Avant **GO R52** : deux autres sous-lots R52.B/C, trois profils demandés (y compris side camera après contrat de picking), preuves hardware Windows/Linux/macOS, CPU/GPU p95/p99, comparaison Studio/Player, non-régression CT et baseline assets.

### Dépendances et non-objectifs

R52 dépend de R3/R19/R36/R39/R51 ; les PR ouvertes et gates de release doivent être validées séparément. Le présent changement n'implique pas que R51 ou R50 soit livré. Aucun mécanisme de lumière, collision, gameplay, sauvegarde, éditeur avancé ni rendu GPU nouveau n'est revendiqué.
