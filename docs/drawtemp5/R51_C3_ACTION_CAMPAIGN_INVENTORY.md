# R51.C3 — HUD d'action R32 et inventaire de campagne

**Branche :** `feat/r51c3-action-hud-campaign-inventory`, dérivée de
`integration/consolidation-r51-r80-20261020` après intégration de R51.C2 (#445).
Cette tranche n'est pas un verdict de publication.

## HUD_ACTION (jeu de plateformes réel)

- L'auteur crée un layout `HUD_ACTION` dans le Studio; template avec
  `action.scene_title` et quatre intentions fixes :
  `action.step_left`, `action.step_right`, `action.jump`,
  `action.attack`. Les bindings sont déclaratifs et typés dans
  `org.drawtemp.ui` version 1.
- Le Player projette seulement l'état du **runtime R32 existant** sur
  l'écran `platform` avec le même `R51Layout.qml` que le Studio.
- Chaque clic fait **exactement un appel**
  `PlayerController.platform_step(move, jump, attack)` ; aucun scheduler,
  physique parallèle, replay ou autosave alternatif. Les entrées maintenues
  et le rythme normal 60 Hz demeurent dans `PlatformViewport`.
- L'attaque est désactivée tant que le runtime R32 n'a pas de boss.
  Les actions sont revalidées lors de l'exécution. Un écran authored
  absent, doublonné, incompatible ou avec intention non autorisée
  laisse le Player natif fonctionner.
- Le HUD est masquable, sans désactiver les commandes d'origine. Il
  nécessite des validations à l'écran réel et manette physique.

## INVENTORY sur l'écran campagne

- Réutilisation du même layout `INVENTORY` et de la valeur typée
  `inventory.item_count` pour l'inventaire tactique et l'équipement
  de campagne. Le contexte est choisi par **l'écran canonique réel** :
  `battle` (R51.C2) ou `campaign` (R51.C3).
- En campagne, objets, quantités et emplacements viennent uniquement de
  `PlayerController.state()["gear"]`. Équiper/déséquiper suit
  `PlayerController.equip_hero("jeanne", item_id)` et
  `unequip_hero("jeanne", slot)`, après nouvelle vérification du stock,
  de l'identité de l'objet et des slots `weapon/armor/accessory`.
  Aucun pouvoir de choisir un autre héros ou d'ajouter un item.
- Fermer l'overlay/Échap ne modifie ni GameSession, ni slot de sauvegarde.
  L'interface de campagne historique et le HUD tactique restent présents
  en l'absence d'un layout compatible.

## Accessibilité partagée

`R51Layout.qml` et `R51Node.qml` déclarent désormais explicitement
`highContrast` et `textScale`, et propagent ces valeurs aux éléments
imbriqués. Contraste élevé, indicateur de focus, descriptions des actions
et hauteur minimale des boutons améliorent l'usage clavier. Cela ne
constitue **pas** une qualification lecteur d'écran.

## Vérifications à exécuter sur les SHAs réels

```bash
python -m unittest -v tests_standalone.test_r51a_ui_layout \
  tests_standalone.test_r51c2_player_screens \
  tests_standalone.test_r51c3_action_inventory \
  tests_standalone.test_r40_player_platform

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
DRAWTEMP_R51_QT_GATE=1 python -m unittest -v \
  tests_standalone.test_r51b_qt tests_standalone.test_r51c2_qt \
  tests_standalone.test_r51c3_qt
```

Workflow : `.github/workflows/r51c3-action-inventory.yml`,
Python 3.12 sous Ubuntu/Windows/macOS et Qt Quick software offscreen Linux.
La présence d'une définition CI n'est pas la preuve que les tests ont
réellement démarré ou passé.

## Limitations — Gate R51 = NO-GO

- Les quatre boutons R32 sont des **impulsions d'une frame**,
  pas une manette directionnelle continue : aucun test de manette physique.
- L'inventaire de campagne concerne ici le menu `campaign` et
  l'équipement de Jeanne, pas tous les inventaires RPG/exploration.
- Le remplacement visuel et fonctionnel **intégral** de l'UI de chaque genre,
  les goldens DPI/HC approuvés et l'accessibilité humaine restent ouverts.
- La PR #411 (audit de licences, export et preuve d'identité UI) a été
  fermée **sans fusion** ; ne pas supposer ces contrôles livrés par C3.
- Droits de redistribution, vrai Player natif tri-OS, GPU physique,
  clean-machine et master SHA final non certifiés.

**Décision R51 : NO-GO** jusqu'à qualification documentée.
