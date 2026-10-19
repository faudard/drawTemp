# R20.C — Cinématiques et conséquences persistantes de l'Acte I

## Périmètre livré (incrément d'authoring jouable et prévisualisable)

Ce lot complète le projet R20.B **sans remplacer le projet joueur historique ni
tenter de migrer ses sauvegardes**. La source de vérité reste
`Content` + `GameProject` + `GameSession` : scènes/choix de
`sporebound/narrative.py`, cinématiques de `sporebound/cinematics.py`,
cinématique Qt partagée `drawtemp/player/qt_cinematic.py`.

- **Nouveau projet opt-in** :
  `sporebound/content/jeanne.r20c.game.json`.
- **10 clips authored** sur les scènes canoniques et cinq nouvelles scènes :
  ouverture du prologue, incendie de Domrémy, hospice, dilemme, archives,
  otages, audience de Vaucouleurs et **trois** fins distinctes.
- Clés `trigger.kind = "scene"`, `trigger.target` pointant sur une vraie
  scène `GameProject.story`; projection caméra, personnages, textes, fade
  et FX sont déterministes et ont une durée bornée. **Pas d'audio ou
  de ressources externes non licenciés** ajoutés.
- Les deux résultats tactiques différents (`a1_04a_archives` et
  `a1_04b_otages`) mènent maintenant à des scènes distinctes avant
  `sc_a1_debrief`. Elles enregistrent un choix durable supplémentaire :
  archives scellées ou rendues publiques ; protection des témoins ou
  préparation de leurs dépositions.
- À Vaucouleurs, les choix existants mènent à des épilogues **archives**,
  **témoins** ou **libre arbitre**. Les flags d'origine
  `acte1_complete`, `acte2_appui` et `acte2_route_ouverte` restent
  préservés. Les nouveaux flags `r20c_route_after`,
  `r20c_act1_conclusion` et `r20c_chinon_priorite` donnent
  de la matière à R20.D et à l'Acte II, sans inventer de mission Acte II.

## Prévisualisation cinématique Qt (distincte de l'auto-déclenchement Player)

```bash
python scripts/preview_r20c_jeanne.py --list
python scripts/preview_r20c_jeanne.py --clip r20c_domremy --sample 2500

# Qt 6 installé : ouvrir la scène QML réelle partagée avec le Studio
python scripts/preview_r20c_jeanne.py --clip r20c_vaucouleurs
```

Le prévisualiseur utilise `CinematicStage`, `frame_at` et
`CinematicTransport`. Lire, mettre en pause, chercher, rejouer ou passer
une cinématique **n'applique jamais de choix narratif**, n'accorde pas de
récompense et n'écrit pas de checkpoint de campagne.

**Limite explicite importante :** le Player Qt `drawtemp.player.qt_app`
ne déclenche pas encore automatiquement ces clips lors de l'entrée dans
une scène. Le contenu narratif est bien jouable et sérialisé ; les clips
sont disponibles dans le prévisualiseur Qt et les outils d'authoring.
L'intégration UX de l'auto-déclenchement, de la file d'attente de clips
et de l'acquittement après reprise Player est **un travail restant avant
toute certification R20.10 / R20.D**.

## Jouer la variante R20.C

```bash
python -m drawtemp.player.qt_app \
  --content sporebound/content/jeanne.json \
  --project sporebound/content/jeanne.r20c.game.json \
  --campaign jeanne
```

Parcourir le prologue et les quatre zones R20.B, combattre réellement sur
route/pont/hospice, puis choisir archives ou otages et leurs conséquences.
Après la victoire réelle à Vaucouleurs, choisir un discours de fin,
lire l'épilogue et valider le dernier choix.

## Sauvegardes et sécurité

Une ancienne sauvegarde portant `jeanne.game.json` ou
`jeanne.r20b.game.json` doit continuer à charger **avec son propre projet**.
Le nouveau projet porte une autre empreinte de gameplay et son propre
chemin ; aucun ancien slot n'est remplacé automatiquement. Une tentative
de chargement croisé produit `IncompatibleSaveError("project", ...)` ;
l'échec est non destructif.

Les données historiques `sporebound/content/jeanne.json`,
`jeanne.game.json` et `jeanne.r20b.game.json` restent intactes.
Une vraie migration vers R20.C requerrait une interface explicite avec
préflight des progrès déjà joués, copie isolée, preuve de conservation des
batailles/replays, rollback et acceptation utilisateur : **elle n'est
volontairement pas simulée dans cette PR**.

## Tests et preuves

```bash
python -m unittest tests_standalone.test_r20c_jeanne_cinematics -v
python -m unittest tests_standalone.test_r20b_jeanne_playable \
  tests_standalone.test_jeanne_acte1 tests_standalone.test_jeanne_prologue -v
python scripts/preview_r20c_jeanne.py --list
```

Les tests R20.C réalisent les **vrais combats via le moteur Battle** sur
les routes archives et otages, sauvegardent avant le choix de conséquence,
rechargent, poursuivent vers l'audience, sauvegardent après le choix
d'épilogue et comparent les états/digests. Ils refusent les scènes/choix
cinématiques invalides et le mélange silencieux de versions. Le contrôle
des sauts/recherches cinématiques est **pur et headless**, non une preuve
que les contrôles visuels Qt sont utilisables.

### Critères encore ouverts

- Liaison Player Qt automatique des clips au parcours réel, sans
  rejouement intempestif au reload, avec skip bloquant toute récompense
  implicite ; test GUI onscreen et reprise en plein montage.
- Traitement volontaire des slots entre variantes avec migration
  vérifiée, ou maintien officiel de versions isolées.
- Revue narrative, audio/licences et performance GPU par des humains ;
  distribution autonome (R20.D). Aucun de ces gates n'est déclaré vert
  sur la seule base du contenu et des tests headless.
