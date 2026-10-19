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
python -m unittest -v tests_standalone.test_r50b_catalog
python -m unittest -v tests_standalone.test_r28e_minigames_certification
```

En CI, l'exécution Qt est **offscreen** et ne représente ni une preuve de
GPU physique, ni un test utilisateur onscreen. Un job qui échoue ou est
refusé avant allocation d'un runner ne constitue pas une validation.
La PR R50.A [#378](https://github.com/faudard/drawTemp/pull/378) demeure
indépendante et non fusionnée au moment de la création de ce lot.
