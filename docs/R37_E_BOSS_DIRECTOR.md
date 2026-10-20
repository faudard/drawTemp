# R37.E1–E2 — Boss & AI Director : phases canoniques, signaux et Studio

**Statut : code et tests ajoutés à la PR #371. Exécution CI non certifiée.**

## Principe

Le moteur de combat R6/R8 possède déjà les vraies transitions `hp_below → boss_phase`, les `queue_wave` de `EncounterDirector`, des compétences à incantation `cast_ticks`, les aperçus `boss_r6_telegraph` et le journal `Battle.recording`. R37.E **n'ajoute pas** de seconde machine à états de boss, de spawn caché, de règle de dégâts, ni de commande d'attaque parallèle.

## Contrat de projet

Document optionnel `boss_directors` à côté de `agents` dans `GameProject.extensions['org.drawtemp.advancedai']['data']`, sans modification de la sauvegarde historique :

```json
{
  "version": 1,
  "agents": [{
    "id": "warden", "mode": "ct",
    "policies": [{
      "id": "wait", "action": "wait", "base": 0,
      "when": {}, "terms": {}
    }]
  }],
  "boss_directors": [{
    "id": "throne_warden",
    "mission": "throne",
    "boss": "warden",
    "phases": [
      {
        "phase": 2, "label": "Gardien",
        "cue": "Attention à la charge",
        "trigger": null
      },
      {
        "phase": 3, "label": "Rage",
        "cue": "Des renforts arrivent",
        "trigger": "final_fury"
      }
    ]
  }]
}
```

Le boss est un ennemi avec comportement réel `phase_boss` ou `adaptive_boss` dans une mission Content. Le début de la progression est dérivé du tag initial `boss_phase:` (par défaut phase 1). Pour chaque phase ultérieure, le seuil de vie est obtenu **uniquement** du trigger `hp_below` de la mission qui contient son action réelle `boss_phase`. Toutes les transitions existantes doivent être couvertes exactement, sans phase additionnelle inventée, sans doublon ni trou. Plafonds : 16 directeurs, 8 phases, libellés 80 caractères et indications 160 caractères.

## Aperçus du jeu

```python
game = GameSession.new(content, project, "main", rules=tactical_r6_rules())
game.start_mission("throne")
director = game.ai_boss_preview("throne_warden")
```

`GameSession.ai_boss_preview` refuse toute mission non active. Le résultat JSON réutilise `boss_r6_telegraph` et expose :
- phase actuelle et HP%, métadonnées de présentation ;
- seuils déclencheurs réels et historique des transitions observées ;
- menaces visibles / incantations effectivement programmées (`scheduled`) ;
- renforts **possible** (scripts non déclenchés), **queued** (dans EncounterDirector) ou **observed** (acteurs déjà apparus).

Une prévision de commande `conditional` lorsque le boss est **réellement actif** ne constitue pas une attaque déjà exécutée. Lorsqu'il ne joue pas, l'intention est **unknown** plutôt que devinée. Le rapport porte un SHA‑256 déterministe ; l'évaluation n'avance pas CT ni RNG et n'écrit aucune commande.

## Studio

`Outils → Boss & AI Director R37.E…` :
- liste les boss réels des missions Content ;
- crée une fiche de directeur en dérivant **exactement** les phases de triggers existantes ;
- édite les textes des phases et avertissements ;
- inspecte les références authored lorsqu'aucun Battle réel n'est fourni ; la fenêtre **n'invente pas** de combat de démonstration ;
- applique une mutation canonique via `AuthoringSession.preview_project/apply` avec Undo/Redo et garde de révision.

Pour créer une **nouvelle phase jouable**, il faut d'abord l'ajouter à la mission Content via les triggers R8 ; R37.E ne la simule pas.

## Tests

```bash
python -m unittest tests_standalone.test_r37_boss_director -v
python -m unittest tests_standalone.test_elite_boss_r6 tests_standalone.test_boss_encounter_r6b -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r37_boss_director_qt -v
```

Gates visés : identités/contrats/phasage validés, aucune transition fictive, preview idempotente et sans mutation, menaces honnêtes, sessions GameSession et replays Battle, sauvegarde/restauration, legacy sans extension, transactions R1 stales et Undo/Redo, Qt offscreen.

### Limites du lot

Le **Director est actuellement une façade de diagnostic et d'édition de métadonnées**, pas un contrôleur d'actions. L'exécution des intentions R37 par la pipeline officielle, l'éditeur de nouveaux patterns/attaques, les campagnes batch de simulation et la QA visuelle d'un boss entièrement joué sont des travaux ultérieurs R37.E3 / R37.F. Éviter toute annonce de conformité finale ou de tests verts tant que GitHub Actions échoue avant l'exécution des jobs.
