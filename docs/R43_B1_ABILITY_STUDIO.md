# R43.B1 — Combat & Ability Designer Qt (première intégration)

**Statut : code en PR empilée sur R43.A. Non fusionné, non certifié.**

## Périmètre livré par cette branche

- Atelier Qt Widgets `AbilityDesignerDialog` accessible depuis **Outils →
  Combat & Ability Designer R43** et depuis l'atelier **Gameplay (R28)**.
  Ce dernier conserve son éditeur R8 ; aucune base de compétences bis.
- Création d'une compétence, sélection/édition des compétences R43, profils
  explicites TACTICAL_CT / ACTION_REALTIME / RPG_TURN, cible/portée/forme,
  coût et timing par profil.
- Effets 1..8 : ajouter, modifier, supprimer, monter/descendre ; formulaires
  typés pour élément/statut/portée/durée et formules **constante** ou
  **statistique × pourcentage**.
- Aperçu **schématique** sur 9 × 9 cases (forme + zone d'impact + portée
  Manhattan, clic de destination) ; aucune tentative de simuler LOS, picking
  natif, équipe réelle ou collisions. Ce n'est pas un Player.
- Aperçu de compilation et de valeurs brutes à partir des formules R43.A,
  avec messages de rejet explicites. **Ne pas présenter cela comme des
  dégâts réels** : mitigation, esquive et règles Battle restent dans Battle.
- `AbilityDraft` (sans Qt) conserve uniquement un brouillon en mémoire ;
  `preview_ability(AuthoringSession, ...)` produit une paire transactionnelle
  Content+GameProject, `apply` commet **un seul Undo/Redo**. Aucune mutation
  persistante depuis les widgets tant que l'auteur n'a pas appliqué.
- Contrôle des révisions pour refuser un aperçu déjà périmé.
- Les formules arborescentes R43.A non représentables par ce formulaire
  **ne sont jamais converties silencieusement** en constante. L'édition et
  l'application sont bloquées jusqu'au futur graphe de formule.

## Compatibilité : limitations documentées

R43.A compile vers `Content.skills` exclusivement les capacités CT utilisant
les formules constantes autorisées. Pour les profils ACTION_REALTIME et
RPG_TURN, le formulaire enregistre des **plans déclaratifs valides**, mais
aucun Player R26/RPG n'exécute ces nouvelles abilities dans ce lot. Les
cooldowns CT non nuls restent refusés. L'ancien éditeur R8 garde ses capacités
existantes et ne doit pas modifier les compétences R43 générées sans que
la validation détecte un conflit.

Le rayon et la portée de l'aperçu sont strictement bornés, mais
la parité avec l'iso/top-down et les hitboxes native est non prouvée.

## Commandes de vérification attendues

```sh
python -m unittest tests_standalone.test_drawtemp_r43_ability_contracts -v
python -m unittest tests_standalone.test_drawtemp_r43b_ability_draft -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r43b_ability_qt -v
```

Workflow `r43-ability-studio.yml` : contrats/drafts sur Windows, Linux,
macOS (Python 3.12), et UI Qt offscreen sur Linux. Le résultat de CI
est à vérifier sur le SHA de cette PR ; ne pas extrapoler à un test GUI
onscreen, GPU réel ou une release.

## Suite R43.B2 → R43.C, non terminée

1. Compiler l'arbre de formules en graphe UI typé sans conversion de données,
   formules de dégâts/coût et effets avec sandbox d'exécution bornée.
2. Réutiliser les widgets de viewport R3 pour cibler cases/zones/cônes,
   naviguer clavier/manette et prouver le picking/LOS/cibles.
3. Raccorder les adaptateurs des profils à GameSession, Battle/R26 et RPG_TURN
   en préservant RNG, CT Jeanne, save/load, interruption/cooldown et replay.
4. Balance Lab sur plusieurs seeds, synchronisation R36 des FX au tick et
   réduction de flashs (opt-in).
5. Slice VS-43 : **quatre compétences**, zone d'effet et synergie incluses,
   sauvegarde/replay CT + action; tests 30/60/120 FPS, UI onscreen,
   GPU matériel, export Player clean-machine tri-OS.

**Gate R43 : NO-GO** jusqu'à ces preuves. La fusion de cette branche dans
R43.A ne certifie ni R43.B complet ni DrawTemp 8.3.
