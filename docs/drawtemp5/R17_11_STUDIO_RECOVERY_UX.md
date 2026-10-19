# R17.11 — Studio Qt : recovery UX, conflits Content / GameProject

Cette tranche expose le mécanisme transactionnel R1/3.7.21B déjà présent
(`StudioTransactionStore`) dans le vrai éditeur de cartes Qt. Elle
n'introduit **aucun format de sauvegarde supplémentaire**, aucun état de
combat ni mutation automatique d'un document utilisateur.

## Journal d'un Save All interrompu

Le menu de l'éditeur ajoute « Récupérer projet ». Ouvrir un projet possédant
`<content>.studio-recovery.json` propose aussi cette récupération.

Le Studio inspecte **sans écriture** les deux issues possibles :

- **Terminer l'enregistrement** : publier les deux générations `studio-next`
  validées (Content et GameProject).
- **Revenir en arrière** : rétablir les octets précédents `studio-prev`.
  Si l'enregistrement initial était interrompu, les deux documents sont
  retirés pour revenir à l'absence d'origine.

Chaque issue est désactivée lorsqu'un fichier manque, qu'une empreinte est
erronée, qu'un tiers a modifié un document, ou que le couple résultant est
invalide. Le journal reste alors intact pour un diagnostic manuel.

L'aperçu contient un **jeton SHA-256** des deux documents, du journal et
des fichiers de récupération. La confirmation le vérifie à nouveau avant
toute écriture : toute modification entre l'inspection et le choix provoque
un refus, et aucune « préférence » du dialogue ne remplace le garde-fou
du stockage canonique. Les sources symboliques sont refusées.

Quand la récupération aboutit à deux documents, ils sont intégralement
validés avant que la session Qt active soit remplacée. Si des changements
locaux non enregistrés existent, une confirmation distincte est demandée
avant de les abandonner. Aucun rollback ou reload n'est automatique.

## Conflits d'enregistrement

`AuthoringSession.storage_status()` expose seulement un diagnostic
lecture seule : journal présent, destination connue et divergence entre
les empreintes chargées et celles sur disque. `save()` conserve sa propre
vérification stricte de concurrence.

Lors d'un conflit externe, un dialogue propose :

- **Enregistrer une copie** : créer un *nouveau* couple Content/GameProject,
  sans toucher à la destination modifiée par un tiers.
- **Recharger du disque** : relire le couple validé après un second accord
  si le Studio comporte des modifications non enregistrées.
- **Annuler** : ne rien changer.

Un journal en attente est orienté vers l'écran de récupération ; un échec
d'accès disque demeure visible, sans tentative de réparation automatique.

## Tests

```bash
python -m unittest \
  tests_standalone.test_r17_studio_recovery \
  tests_standalone.test_studio_transaction_3721b \
  tests_standalone.test_drawtemp5_r1_authoring -v

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest \
  tests_standalone.test_r17_studio_recovery_qt \
  tests_standalone.test_drawtemp5_r5_selection_qt -v
```

Les nouvelles injections couvrent crash entre les deux publications,
retour arrière exact, achèvement, modification externe du journal/des
sources/des documents, corruption, annulation du dialogue et copie locale.
La matrice CI exécute le parcours Qt sur Linux, Windows et macOS.

## Limites explicites

- `StudioTransactionStore` n'est pas transformé en verrou
  inter-processus complet : la confirmation protège contre les fichiers
  changés depuis l'aperçu, mais **un écrivain hostile qui modifie les
  fichiers pendant la phase d'écriture** reste une limitation du protocole
  multi-fichiers actuel (voir R17.12).
- Une panne après la première publication nécessite une nouvelle inspection
  et action de l'utilisateur. Ne pas effacer le journal à la main.
- Il reste à couvrir les boîtes de dialogue de préflight/export R15/R17.6
  et l'E2E Studio/Player/export multi-machine.
- Les tests Qt `offscreen` sont des contrats fonctionnels, pas une
  validation artistique, ergonomique ou GPU certifiée.
