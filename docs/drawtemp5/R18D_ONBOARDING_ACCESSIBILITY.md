# R18.D — Onboarding Studio, accessibilité et parcours Studio → Player

> Incrément de R18.12/R18.13 ; **ne constitue pas la certification R18 ni la levée du gate R17**. Les ateliers Événements/Cinématiques restent à intégrer entièrement au shell.

## Parcours novice implémenté

Depuis **Projet**, un guide non modal propose cinq étapes graduelles :

1. **Ouvrir/créer un projet** : utilise les vraies commandes Studio R18.A/R15. Aucun fichier n'est écrit avant la confirmation.
2. **Découvrir Carte** : ouvre le vrai atelier R5. Un projet et au moins une carte canonique sont nécessaires pour créditer la visite.
3. **Découvrir Personnages** : ouvre l'atelier/Base RPG existant. Au moins un personnage canonique est exigé pour créditer l'étape.
4. **Enregistrer** : ne valide l'étape qu'après réussite du `AuthoringSession.save()` ou `save_as()` (Content + GameProject atomiques).
5. **Lancer le Playtest** : démarre le Player Qt avec le Content enregistré ; l'étape n'est validée qu'après confirmation du démarrage du processus. La présence d'une paire ouverte propre sur disque atteste l'enregistrement lors d'un Playtest réussi.

**C'est un guide de découverte et de vérification de parcours**, pas une preuve qu'une mission a réellement été créée, que Jeanne a été placée, qu'un événement a été relié ou que le joueur a terminé le combat. Ces preuves relèvent des gates de validation manuelle R18/R17.

Le progrès utilise des preuves de navigation, de sauvegarde et de lancement réellement réussis et ne modifie **ni Content, ni GameProject, ni les sauvegardes Player, ni le replay**. Les données du guide sont conservées par projet dans QSettings ; la clé est dérivée du SHA-256 du chemin absolu, pas du chemin brut. Changer de projet ne réutilise pas abusivement la progression du projet précédent. Pour une session provisoire non enregistrée, aucune réussite « Ouvrir projet » n'est supposée.

## Accessibilité et ergonomie

- Commande **Outils → Visite guidée** et raccourci **Ctrl+Shift+G**, avec focus explicite sur le bouton de la prochaine action.
- Masquer le guide est réversible ; pas de pop-up automatique qui interrompt un travail en cours.
- Noms/descriptions accessibles pour le panneau, le progrès, les instructions et les commandes ; chaque étape annonce son statut textuellement (✓ / ○), sans dépendre d'une couleur.
- Page Projet défilante et ateliers disposés en deux colonnes pour limiter le débordement en petites fenêtres et fort scaling.
- Instructions, état de progression, boutons et description de l'incomplétude des ateliers en **FR/EN**. L'internationalisation du *shell entier*, des éditeurs R5–R11 et des outils spécialisés reste à compléter.
- États vides explicites dans les aperçus d'ateliers ; absence de carte/personnage signalée dans le guide, sans afficher de succès fictif.

## Contrôles automatiques (nouveaux et hérités)

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_drawtemp5_r18d \
    tests_standalone.test_drawtemp5_r18a \
    tests_standalone.test_drawtemp5_r18b \
    tests_standalone.test_drawtemp5_r18c -v
```

Le workflow R18.D ajoute des jobs Ubuntu 24.04 / Windows 2022 / macOS 15 avec Python 3.12 et PySide6, plus smoke Studio Projet et Player titre. Les tests vérifient notamment :

- session de référence en mémoire : **aucune étape créditée automatiquement** ;
- clic du guide vers Carte/Personnages puis sauvegarde et lancement simulé du processus Player (sans vraie fenêtre native dans cette assertion) ;
- échec d'ouverture et échec de lancement : pas de progrès fictif ;
- persistance des progrès QSettings après fermeture/réouverture, indépendance par chemin de projet et bascule FR/EN ;
- activation de la commande au clavier et présence des attributs accessibles ;
- **vrai couple Content/GameProject écrit par AuthoringSession**, chargé par `build_controller(content_path=...)` dans le Player indépendant, partie démarrée, sauvegardée, puis reprise avec données inchangées.

## Acceptance manuelle requise pour fermer R18

| Scénario | Preuve / blocage |
|---|---|
| Projet vierge créé par l'interface, carte éditée et personnage placé | Vidéo/captures + Content/GameProject sauvegardés ; aucune édition JSON |
| Événement relié à la carte et test Player | Éditeur R9 à brancher dans le shell ; actuellement pas certifié |
| Première rencontre terminée puis reprise de sauvegarde | Démonstration sur Player natif, idéalement nouveau testeur |
| Clavier seul sur tous les ateliers et boîtes | Ordre de tabulation, focus, absence de collisions Qt |
| Contraste et échelles 90/100/115/130 % | Tests visuels HiDPI / fenêtres 850×580 et multi-moniteurs |
| Lecteurs d'écran Windows/macOS/Linux | NVDA/VoiceOver/Orca, retour de focus et libellés accessibles |
| Conversion FR/EN cohérente | Traduire les libellés encore codés en dur dans R5–R11 |
| Performance/caméra et viewport R3 | Validation GPU native et contrôle des erreurs de lancement |

**Statut honnête :** ce lot livre l'infrastructure d'onboarding, les premiers comportements accessibles et les tests automatiques cités ; il ne prétend ni prouver une expérience novice complète, ni certifier la totalité de R18.12–R18.13.
