# R17.11 — Player Qt : erreurs et récupération explicite

**Portée :** actions de récupération dans le vrai Player Qt Quick, sans
second registre de vérité, sans migration de sauvegardes et sans masquer les
différences entre une prévisualisation offscreen et un test GPU réel.
Dépend du renforcement de `PlayerSlotStore` proposé dans R17.7 / #287.

## Parcours utilisateur

1. Le menu titre conserve les statuts réels `SaveManager.catalog()` :
   principale valide/invalide/absente et secours vérifié.
2. « Restaurer auto (.bak) » et « Restaurer secours » ne proposent une
   action que lorsque le **primaire est invalide ou absent** et que le
   **secours est vérifié** ; la présence d'un simple fichier `.bak`
   n'autorise rien.
3. Un dialogue modal **annulable** présente la source exacte, le risque de
   revenir à un état antérieur et la conservation d'une copie endommagée.
   La validation exige un clic explicite sur « Restaurer le secours vérifié ».
4. Lors de la demande, le Player calcule une empreinte SHA-256 de chacun
   des deux fichiers (ou `None` si absent), sans écrire sur disque.
   À la confirmation, le stockage R1 **revérifie ces empreintes sous le
   verrou d'écriture**. Modification externe → code `stale_recovery`,
   refus sans remplacement ni progression perdue.
5. Une sauvegarde encore valide est toujours protégée
   (`primary_valid`). Le Player ne choisit **jamais implicitement**
   la version `.bak` lors de « Continuer ».
6. Les erreurs affichent un intitulé, une explication et une action concrète :
   incompatibilité de campagne, secours invalide, fichier dangereux,
   modification externe, copie endommagée déjà archivée ou erreur disque.
   L'état de la partie reste inchangé après échec.

L'interface existante de chargement et les méthodes Qt appelées dans les
smokes R12 restent disponibles. Les boutons de restauration visibles
utilisent maintenant les méthodes `requestRecovery`,
`confirmRecovery`, `cancelRecovery`, et le dialogue d'erreur
`dismissRecoveryNotice`.

## Commandes de test

```bash
python -m unittest \
  tests_standalone.test_r17_recovery_ux \
  tests_standalone.test_drawtemp5_r12_save_manager \
  tests_standalone.test_r17_persistence_recovery -v

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest \
  tests_standalone.test_r17_recovery_ux_qt \
  tests_standalone.test_drawtemp5_r12_save_manager_qt -v
```

## Scope non fermé

- Le Player n'offre pas encore un navigateur graphique de versions
  historiques : seul le secours R1 est restaurable.
- Les erreurs de publication de packs/licences R17.6 relèvent également
  de l'interface d'export Studio ; ce flux n'est **pas** déclaré
  certifié par cette PR.
- Le Studio doit encore disposer d'un dialogue de résolution des
  changements externes `AuthoringSession.external_change`, sans
  écrasement automatique ; l'intégration de ce parcours relève d'une
  tranche R17.11 distincte.
- Cette PR ne certifie ni le matériel GPU, ni les licences des assets,
  ni l'installation clean-machine, ni une release 5.0.

**Fusion :** #285 → #287 → cette PR. Les autres tranches R17 restent
indépendantes et leurs preuves ne peuvent être présumées vertes.
