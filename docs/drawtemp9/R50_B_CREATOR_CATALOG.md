# R50.B — Catalogue Creator & parcours auteur réels (tranche 1)

La roadmap [R41–R50](../DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md)
exige cinq genres éditables et exportables pour certifier DrawTemp 9.0.
**Cette PR ne satisfait pas ce gate** : elle branche un catalogue honnête et
deux parcours déjà couverts par les APIs canoniques, sans contrefaire les
modes dont l'intégration Studio/Player n'est pas terminée.

## Démarrer

```bash
python -m unittest -v tests_standalone.test_r50b_catalog
python -m drawtemp.studio.qt_shell
```

Dans le Studio : **Créer → Mini-jeux → Catalogue R50 (NO-GO)**.
Le catalogue est utilisable au clavier et expose explicitement les modes
non disponibles (bouton désactivé + raison). L'entrée prototype narratif
ne constitue **pas** un jeu hybride certifié.

| Genre attendu | Entrée | Création | Preuve disponible |
|---|---|---|---|
| SRPG | Le duel du village | Oui | R15 pair validée, R1 transactions, GameSession CT et replay headless |
| Action-aventure | La vallée des lanternes | Bloquée | Manque parcours auteur/Player complet |
| RPG classique | Le relais des trois compagnons | Bloquée | Manque intégration RPG_TURN dans Player |
| Metroidvania | La citadelle suspendue | Bloquée | Manque création/Player certifiable |
| Roguelite | Les salles mouvantes | Bloquée | Manque création/Player certifiable |
| Hybride narratif | Le conseil des gardes | Bloquée | Manque transition récit/action/CT et retour |
| Prototype narratif supplémentaire | Le choix du village | Oui (prototype seulement) | Choix, état de récit et checkpoint GameSession |
| Prototype d'exploration libre | La vallée du guet | Oui (prototype seulement) | Studio R1 → R25 libre à 60 Hz → combat CT → retour, via PlayerController/save/replay |
| Prototype combat action R26 | Le guet de la clairière | Oui (prototype seulement) | Studio R1 → R26 attaques/ennemi → PlayerController et checkpoint GameSession vérifié |

Les noms de projets sont des intitulés de démonstration, **pas**
des jeux complets ou des assets préexistants. Aucun contenu tiers n'est
ajouté par ce lot.

### Parcours couvert automatiquement

1. L'auteur choisit une entrée et un dossier parent existant. Aucun JSON
   manuel ni écrasement n'est demandé.
2. Le créateur canonique R28.E/R15 fabrique sous un dossier temporaire
   Content + GameProject.
3. Une `AuthoringSession` existante édite réellement le sous-titre du projet,
   valide la paire, effectue Undo puis Redo et sauvegarde.
4. La paire est rouverte depuis disque et comparée avec le snapshot validé.
5. Le préflight R15 et `audit_minigame` exercent une `GameSession` CT
   ou un choix narratif, puis contrôlent l'égalité du checkpoint replay.
6. Le projet n'est publié dans son dossier final qu'après ces vérifications,
   sans suppression des dossiers utilisateurs existants.

L'API ne crée **aucun** projet pour un genre sans support enregistré.
La fenêtre ne lance **pas** un faux Player Qt. Les champs
`native_player_tested`, `qt_onscreen_tested`,
`standalone_export_tested` et `release_9_0_ready` restent à `false`.

### Second lot : PlayerController réel (headless)

L'API `check_player_journey` charge la **paire publiée par le Studio**,
passe par `sporebound.player_controller.PlayerController`, sélectionne une
campagne et un slot temporaires, applique une action acceptée
(démarrage de la mission CT ou choix narratif), puis relit le slot avec une
nouvelle instance du contrôleur. La reprise est comparée à l'enregistrement
de référence, et les deux documents auteurs sont vérifiés **inchangés
octet pour octet**. Les sauvegardes sont isolées hors du projet.

Une paire corrompue est rejetée au preflight, sans tentative de réparation
silencieuse. Si le Player échoue dans le dossier temporaire, la création
du starter n'est **pas publiée**. Cette vérification rapproche R50.B du
Player réel mais ne lance ni QML, ni Player natif, ni installateur.

```bash
python -m unittest -v tests_standalone.test_r50b_player_journey
python -m unittest -v tests_standalone.test_r50b_catalog
```

## Tranche R50.B suivante — Exploration libre et transition CT

Le catalogue comprend désormais un **prototype supplémentaire**, distinct
d'une action-aventure certifiée : `exploration_prototype`.

- Création depuis le Studio (aucun JSON édité à la main) ; le générateur
  réutilise `create_template("narrative")` et `AuthoringSession.preview_pair`
  pour ajouter la scène `arrival`, son profil `FREE_REALTIME`, une route vers
  la mission CT existante et une route de retour.
- Vrai `PlayerController.route_realtime_step` : huit ticks déterministes
  puis sauvegarde/reprise avec comparaison du journal et de la position.
  Une commande de déplacement invalide est refusée sans changer le slot.
- `PlayerController.route_transition` démarre le combat CT canonique,
  suivi de sauvegarde/reprise, abandon explicite et retour au village.
- Tous les checkpoints viennent du même `GameSession`, et les documents
  auteurs restent immuables. Le starter n'est publié qu'après le parcours.
- `action_adventure` reste **bloqué** : cette démonstration ne prouve pas
  les attaques temps réel, le Player QML, la manette, les collisions physiques
  natives, ni le routage déclenché par proximité du portail (R25 accepte
  encore une transition par identifiant de lien).

```bash
python -m unittest -v tests_standalone.test_r50b_exploration
```

## Nouvelle tranche R50.B — Combat action R26 dans GameSession

Le nouveau prototype `action_combat_prototype` utilise effectivement les
attaques, le cooldown, les dégâts, l'IA ennemie et la récompense **R26**.
Ce n'est pas le Player action-aventure complet.

- Dans la paire Content/GameProject canonique, `org.drawtemp.actioncombat`
  déclare en extension de schéma 1 un catalogue de scènes R26 **inertes**.
  `GameProject.validate` vérifie l'identité, les dimensions, les obstacles,
  la position initiale et le profil `ACTION_REALTIME` ; les données
  inconnues, les changements de version ou les géométries divergentes
  sont rejetés.
- Dans `GameSession`, `route_action_step` exécute de vrais ticks R26,
  puis enregistre `scene_action` dans **le même** checkpoint que la
  campagne et les routes. Le chargement rejoue les commandes et vérifie
  l'égalité avec la scène autorisée, le checksum et l'état final.
  Aucun format de sauvegarde parallèle, ni progression fictive.
- `PlayerController.route_action_step` sauvegarde chaque commande via
  le mécanisme de transaction existant et restaure le checkpoint précédent
  après toute erreur.
- Le test de jeu réalise un premier coup, recharge la partie en plein combat,
  poursuit jusqu'à la défaite de l'ennemi puis reprend encore la partie.
  Une commande hors ordre et une altération du journal sont refusées.

### Clôture R26, or de campagne et transition CT (tranche suivante)

Le prototype passe maintenant par `route_action_settle("after_action_to_ct")`,
seulement si **tous les ennemis sont vaincus et que le héros est vivant**.
L'inventaire R26 ne peut contenir que des pièces gagnées une fois par ennemi :
les objets arbitraires ou d'autres récompenses ne sont pas convertis.

La transaction unique `PlayerController._apply` effectue dans l'ordre :
validation de la victoire R26 et du lien R25, attribution des pièces dans
`Campaign.gold`, enregistrement d'un marqueur et de son montant dans
`Campaign.story_flags`, archivage du **replay R26 intégral** dans
`scene_action_history`, démarrage de la vraie mission CT, puis sauvegarde.
Une exception restaure l'état antérieur ; aucun paiement partiel ne subsiste.

À chaque lecture de checkpoint, le validateur `action_settlement` rejoue
la victoire avec la scène publiée, vérifie les pièces, les marqueurs, le
caractère unique de la scène et la route/historique utilisés. Revenir
ensuite dans cette scène ne permet pas de redémarrer la récompense.
L'historique R26 est borné à 32 scènes et strictement opt-in ; les
sauvegardes historiques n'acquièrent pas de champ supplémentaire.

**Limite de confiance :** le ledger prouve l'origine et le caractère
unique de *l'attribution R26*, mais ne remplace pas un audit exhaustif
de tous les autres flux économiques qui peuvent modifier l'or de campagne
(achats, missions, etc.). Le moteur ne prétend pas fournir une protection
cryptographique contre un utilisateur capable de réécrire l'ensemble
des sauvegardes et de recalculer tous leurs digests.

L'entrée complète `action_adventure` reste bloquée : pas encore de rendu
Player onscreen, contrôles manette, portail physique, release bundle ni
certification R50.C.

```bash
python -m unittest -v tests_standalone.test_r50b_action tests_standalone.test_action_runtime_r26
```

```bash
python -m unittest -v tests_standalone.test_r50b_action tests_standalone.test_action_runtime_r26
```

## R50.B — Player Qt expérimental branché sur le slot canonique

Un Player graphique **opt-in** complète les parcours headless R50.B.
Il réutilise le `TopDownViewport` R3 et le pont Qt R26 existants, mais
**ne lit ni n'écrit** la sauvegarde autonome `action.json` de l'ancienne
démo : toutes les commandes proviennent de `sporebound.PlayerController`,
dont chaque tick est persisté dans le `GameSession` vérifié.

```bash
# Dans un dossier contenant game.json et game.game.json
python -m drawtemp.player.r50b_action_app --content ./project/game.json --new
# Reprise du même slot : ne pas passer --new
python -m drawtemp.player.r50b_action_app --content ./project/game.json
# Smoke Qt non visible : profil jetable, aucun écrasement
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.player.r50b_action_app --content ./project/game.json --smoke

# Entrée équivalente depuis le Player standard
drawtemp-player5 --r50b-action --content ./project/game.json --new
# Console script opt-in
drawtemp-player-r50b --content ./project/game.json
```

- `R50BActionController` est une façade **sans dépendance Qt**.
  `step(dx,dy,attack,dodge,guard,interact)` utilise exclusivement le
  `PlayerController.route_action_step` de la campagne, pas un nouveau
  `ActionRuntime.save`. Sauvegarde F5 et reprise F9 utilisent le même slot.
- Le QML affiche la carte top-down, les personnages, PV, endurance, tick
  R26, or de campagne, commandes et messages. ZQSD/WASD/flèches déplacent
  le héros ; Espace attaque ; Maj esquive ; Ctrl garde ; P pause.
- **Terminer R26 → CT** devient activable seulement après victoire réelle ;
  la transaction délivre le montant prouvé et démarre la mission CT.
  L'écran CT est pour l'instant un **handoff explicite**, pas une fausse
  représentation jouable du moteur tactique : R l'abandonne sans gain
  tactique puis retourne à la clairière en **un seul commit de slot** via
  `route_abandon_ct`.
- La sauvegarde est isolée par chemin de projet sous le profil utilisateur,
  ou par `--profile`. `--new` refuse d'écraser un slot existant.
  `--smoke` utilise un profil temporaire. Un respawn implicite après mort
  est désactivé pour ne pas effacer une progression sans consentement.
- Les binaires natifs figés refusent ce mode expérimental ; il ne saurait
  justifier une certification hardware ou un bundle R15 propre.

**Tests :** `tests_standalone.test_r50b_action_player` (états purs,
commandes, persistance, rollback, handoff R26→CT et smoke QML offscreen).
Ce test ne prouve **ni** une session Qt onscreen sur un poste utilisateur,
**ni** l'ergonomie, la manette, le framerate réel, la distribution native
ou l'intégration graphique du gameplay tactique CT. R50.C demeure NO-GO.

### Restant pour la vraie R50.B

- R41.B : RPG classique jouable par menus, groupe et sauvegarde.
- R26/R40 et R43–R46 : routes action/metroidvania/roguelite et récit hybride
  dans le **même** GameSession et les rendus Studio/Player.
- Vérifier chaque projet par **vrai** playtest QML onscreen, contrôles
  accessibles et export exécutable, pas seulement par instanciation Python.
- Mesurer édition/playtest/retour sur des machines Windows/Linux/macOS,
  approuver les droits et rejeter les ressources ou plugins inconnus.
- Faire certifier R40 et les gates P0 R41–R49, puis appliquer R50.C.

## Commandes de vérification

```bash
python -m unittest -v tests_standalone.test_r50b_catalog tests_standalone.test_r50b_player_journey tests_standalone.test_r50b_exploration tests_standalone.test_r28e_minigames_certification
```

En CI, l'exécution Qt est **offscreen** et ne représente ni une preuve de
GPU physique, ni un test utilisateur onscreen. Un job qui échoue ou est
refusé avant allocation d'un runner ne constitue pas une validation.
La PR R50.A [#378](https://github.com/faudard/drawTemp/pull/378) demeure
indépendante et non fusionnée au moment de la création de ce lot.
