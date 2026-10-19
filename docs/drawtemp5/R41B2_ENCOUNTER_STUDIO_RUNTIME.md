# R41.B2 — Rencontres RPG_TURN, Encounter Studio et écran Player

**Statut : code en PR #381, non certifié.** Le moteur CT reste séparé, et le Player RPG est un premier incrément utilisable mais pas un vertical slice de release.

## Contrat canonique

- Dans `GameProject.extensions["drawtemp.party_rpg"].data`, le champ **optionnel** `encounters` est un dictionnaire de 64 rencontres maximum. Son absence préserve les manifests R41.A, les projets précédents et les digests existants.
- Chaque rencontre est versionnée par l'enveloppe R24 et référence un ID stable, une scène **existante en profil RPG_TURN**, jusqu'à 12 IDs **ennemis de Content**, et un entier `reward_gold` borné. Aucune duplication de définition de héros/ennemi/compétence.
- Le Studio écrit les rencontres par `AuthoringSession.preview_project/apply` ; une modification = une transaction Undo/Redo. `EncounterStudioDialog` fournit un formulaire Qt accessible et refuse les prévisualisations obsolètes.
- `ClassicEncounter` a un ordre de jeu déterministe (vitesse puis ID), journal borné à **256 actions de joueur**, IA ennemie déterministe limitée à **32 tours automatiques** par décision, et vérification intégrale du replay à la reprise.
- **Actions :** attaque, garde, utilisation des compétences déjà présentes dans Content (effets simples damage/heal), potion (inventaire Campaign), fuite, KO et résultat victoire/défaite. Les capacités avancées, états, éléments, portée/AOE et formules globales relèvent de R43 : **elles sont refusées, jamais simulées partiellement**.
- `GameSession` possède le mode et l'état `rpg`. La sauvegarde contient un bloc opt-in `rpg_encounter` qui est **rejoué** sur les entrées du journal. Les potions sont rapprochées de `Campaign.inventory` à chaque commande et au chargement. Sur victoire, **une seule** transaction attribue l'or de la rencontre et 50 XP aux héros engagés, puis pose le flag `r41:<id>`. Une récompense déjà attribuée ne peut pas être rejouée.
- `Simulation` porte les mutations sous contrôle de révision avec rollback. Le Player Qt Quick utilise le même GameSession, sans moteur de sauvegarde, renderer ni base d'inventaire parallèles.

## Format auteur (dans data du namespace drawtemp.party_rpg)

```json
{
  "version": 1,
  "campaigns": {
    "main": {
      "recruitable": ["jeanne", "margot"],
      "initial": ["jeanne"],
      "active": ["jeanne"],
      "max_active": 2
    }
  },
  "encounters": {
    "sparring": {
      "scene": "inn",
      "enemies": ["renaud_mentor"],
      "reward_gold": 17
    }
  }
}
```

La scène `inn` doit être effectivement décrite dans `GameProject.exploration` et disposer d'un profil `RPG_TURN`. Les références d'acteur doivent exister dans `Content.missions` et correspondre à l'équipe `enemy`.

## Limites explicites : gates non acquis

1. **R41.6**, transitions `SceneRouter` exploration→combat→exploration, **non intégré** : le démarrage des rencontres est réservé pour l'instant aux projets RPG non routés, depuis le menu campagne. Si le routing R25 est activé, l'API bloque ce début de combat plutôt que contourner les portails et préconditions. L'intégration de scènes et des flags est le prochain lot.
2. La formule de combat simplifiée et déterministe est un **adaptateur RPG_TURN**, non une transposition du moteur CT (R43 devra harmoniser compétences et équipement).
3. Pas encore d'interface gamepad certifiée, d'équilibrage réel, d'effets avancés, de boss, de lab multi-seeds ni de template installable R41.C.
4. La CI et le Qt offscreen ne valent pas **Qt onscreen, GPU matériel ni recette d'un Player exporté**.

## Commandes de validation à exécuter

```sh
python -m unittest tests_standalone.test_r41_classic_party -v
python -m unittest tests_standalone.test_r41_party_studio -v
python -m unittest tests_standalone.test_r41_party_qt -v
python -m unittest tests_standalone.test_r41_encounter -v
python -m unittest tests_standalone.test_r41_encounter_qt -v
python -m unittest tests_standalone.test_r25_foundation tests_standalone.test_game_session -v
```

**Ne pas considérer ces commandes comme passées tant qu'il n'existe pas des jobs réellement exécutés et des logs sur le SHA final.** Le prochain lot doit valider des parcours Player utilisables au clavier/manette, réintroduire le SceneRouter dans le flux RPG et certifier le vertical slice R41.C.
