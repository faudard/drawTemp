# Studio Cinématiques — première tranche jouable

Le **Studio → Cinématiques** édite les séquences dans le même manifeste
`*.game.json` que la campagne, avec une timeline visuelle et un aperçu
reproductible. Le moteur tactique reste indépendant du rendu Tk.

## Créer une cinématique sans JSON

1. Démarrer `python -m sporebound editor`, ouvrir **Cinématiques**.
2. Choisir un identifiant, un titre, un déclencheur et la campagne/mission cible.
3. Cliquer **Créer**, puis ajouter plusieurs événements, avec les temps en
   millisecondes. Les barres sont ordonnées selon leur début. On peut glisser
   une barre horizontalement pour déplacer son événement (pas de 100 ms).
4. Sélectionner un événement pour éditer sa piste, sa durée et ses paramètres,
   puis **Appliquer**. On peut parcourir la séquence avec le curseur.
5. **Lecture complète** joue l'aperçu avec Pause / Recommencer / Passer.
   **Annuler** et **Rétablir** gèrent l'historique des modifications.
6. **Enregistrer projet** enregistre le manifeste dans le dossier choisi.

Le bouton **Exemple Jeanne** crée une séquence de test (champs, personnage en
mouvement, voix, panoramique, fondu) attachée à la première campagne, sans
fichier ni module supplémentaire. Il est possible de la prévisualiser
immédiatement.

## Événements et déclenchements

| Événement | Champs spécifiques | Rendu |
|---|---|---|
| `background` | `color` | couleur de décor sur l'intervalle |
| `actor` | `actor`, `from`, `to` | déplacement interpolé d'un personnage |
| `camera` | `from`, `to`, `zoom_from`, `zoom_to` | panoramique/zoom |
| `dialogue` | `speaker`, `text` | nom et boîte de dialogue |
| `fade` | `color` | fondu progressif |
| `sound` | `cue` | son facultatif via `AudioStage` / AssetRegistry |

Les points utilisent les coordonnées normalisées à la scène (environ 0..1 pour
rester à l'écran). Si une liaison `sprite` ou `portrait` existe dans l'AssetRegistry
pour l'identifiant de l'acteur, le Player et l'aperçu l'utilisent ; sinon
un repère vectoriel est dessiné. Les images sont affichées sans découpage
d'atlas ni animation articulée. Le format est
déclaratif, sans scripts Python et sans mutation de l'état de combat.

Les déclencheurs sont :

- `campaign_start` : après **Nouvelle partie** (pas lors du chargement) ;
- `before_mission` : avant l'entrée en bataille du Player ;
- `after_mission` : lors du retour d'une bataille terminée à la campagne.

Plusieurs séquences pour le même déclencheur jouent dans l'ordre du manifeste,
avec possibilité de les passer. Les missions multi-fronts passent encore
par leur parcours dédié, sans séquencement cinématique spécifique.

## Exemple de données

```json
{
  "cinematics": [{
    "id": "jeanne_vision",
    "name": "Jeanne entend la voix",
    "trigger": {"kind": "campaign_start", "target": "main"},
    "duration_ms": 6000,
    "events": [
      {"id": "scene", "kind": "background", "start_ms": 0,
       "duration_ms": 6000, "color": "#243c56"},
      {"id": "jeanne", "kind": "actor", "start_ms": 0,
       "duration_ms": 5400, "actor": "jeanne",
       "from": [0.15, 0.65], "to": [0.65, 0.65]},
      {"id": "voice", "kind": "dialogue", "start_ms": 1200,
       "duration_ms": 3800, "speaker": "Une voix",
       "text": "Ton destin est devant toi."}
    ]
  }]
}
```

`GameProject.validate()` rejette les ID dupliqués, les références de mission
ou campagne inconnues, les types non reconnus, les événements hors durée, les
coordonnées non numériques, les couleurs invalides et les durées excessives.
L'interface modifie une copie du manifeste puis valide intégralement avant de
publier la modification. L'échec ne corrompt pas le projet.

La fonction sans interface `frame_at(clip, time_ms)` calcule les positions,
le cadrage et les dialogues de manière déterministe, quel que soit l'ordre de
lecture ou de déplacement du curseur.

## Compatibilité et limites

Les projets anciens sans `cinematics` restent compatibles : le champ vide
n'est pas sérialisé. Les nouveaux projets ajoutant des cinématiques ont
normalement un nouveau digest de projet, ce qui exige de nouvelles sessions
ou un mécanisme explicite de migration pour les anciennes sauvegardes.

Ce jalon **ne** fournit **pas encore** de pistes musicales mixées,
de panoramas importés, d'animations articulées de sprites, d'effets
de particules, de montage vidéo, de lipsync, de branches interactives au sein
d'une cinématique, de keyframes de poses articulées ou de synchronisation avec
l'animation d'une bataille en cours. Les embranchements interactifs doivent
encore passer par le Studio Scénario.

## Vérification

```sh
python -m unittest tests_standalone.test_cinematics -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
    tests_standalone.test_cinematics_gui -v
```

La CI existante exécute le contrat sans écran sur Python 3.10/3.12/3.14,
Windows/Linux/macOS, et l'intégration visuelle sur Linux/Xvfb.
