# R17.C2 — Event Studio Qt / Graphe / Pages

Base explicitement empilée sur **R17.C1** (#280), pour utiliser le même
Content, AuthoringSession, événement et journal tactique, plutôt que
de copier un second moteur de décisions.

## Fonctions reconnectées

- `EventGraphView` : cartes déplaçables et ajout réel de dépendances ET/OU ;
  positions uniquement côté UI, liens persistants dans Mission.triggers.
- Catalogue d'actions R9.C / R9.D : typage des champs tactiques, y compris
  activation/désactivation des pages et rejet des commandes hors registre.
- Pistes cinéma (dialogue, audio, FX, caméra, acteurs) vers les événements
  `tactical_event` du **GameProject canonique** (pas de scripts silencieux).
- Marqueurs d'événements en profondeur/hauteur via `IsoProjection` et
  `RendererController` partagés : Player conserve sa vue sans overlays R9.
- Onglet **Pages & états** de R9.D : priorité, conditions, commandes, enabled,
  repeat, cooldown, création/suppression via les méthodes de R17.C1.

## Tests

```bash
python -m unittest tests_standalone.test_drawtemp5_r9c \
  tests_standalone.test_drawtemp5_r9d \
  tests_standalone.test_r17c_event_integration -v

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_drawtemp5_r9c -v
```

Les workflows utilisent Python 3.12 et les tests Qt/Quick sur trois OS.
L'offscreen valide une intégration logicielle, **pas** un GPU physique ni la
certification d'un parcours utilisateur sur machine de release.

## Avant fusion

1. Attendre l'intégration R17.C1 (#280), puis changer la base de cette PR
   de la branche R17.C1 vers master si nécessaire ; vérifier le diff GitHub.
2. Vérifier les logs CI au SHA final ; ne pas considérer vert par héritage.
3. Compléter l'E2E levier/porte/page/choix/cinématique/Player et des captures
   validées avant de clore le gate R17.3.
