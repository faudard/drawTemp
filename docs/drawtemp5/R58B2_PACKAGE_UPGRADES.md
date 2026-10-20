# R58.B2 — mise à jour réversible de packages isolés

**État : implémentation de la tranche isolée (code en consolidation R51–R80), pas de certification R58.B ni de release.**

## Portée réellement implémentée

Le dialogue Studio **Outils → Packages de ressources R58** propose désormais
**Mettre à jour / Restaurer…** pour un projet n'ayant **qu'un pack R24.C installé**.

1. Sélectionner une archive R24.C locale, régulière, non-symbolique.
2. Fournir une empreinte SHA-256 obtenue *indépendamment* de l'archive.
3. Prévisualiser version source/cible, empreinte et fichiers nouvellement créés
   ou conservés. Par défaut toute confirmation est **Non**.
4. Confirmer pour créer les nouveaux fichiers dans un **répertoire de version
   distinct**, puis appliquer la migration en **une** transaction
   \`AuthoringSession\` avec Undo/Redo. La sauvegarde disque est manuelle.
5. Pour revenir à une version plus ancienne, fournir **son archive vérifiée**,
   confirmer explicitement la rétrogradation puis confirmer son diff. Si les
   fichiers de cette version sont déjà présents, ils sont revalidés et réutilisés
   sans aucun écrasement.

Le moteur réutilise les fonctions et le schéma **R24.C** (pack manifest, reçus,
AssetRegistry). Les IDs d'assets et leurs kinds doivent être identiques entre les
deux versions. Les liens d'animations et les bindings canoniques conservent
leurs identifiants. Les références externes à l'ancien chemin **physique**
sont bloquantes ; un changement d'ID/kind exige un schéma de migration explicite
hors de ce lot.

## Fiabilité et cas refusés

- Une autre installation de pack dans le même GameProject bloque la migration,
  car les anciens reçus R24.C ne décrivent pas les **dépendances inverses**
  nécessaires pour remplacer sans casser un consommateur. Aucun ajout de
  dépendance dans le nouveau pack n'est permis pour ce sous-lot.
- Vérification du projet et du pack installés, de la révision, du snapshot,
  du SHA d'archive, du manifeste, des fichiers candidats et des signatures
  de ressources au moment de la prévisualisation et avant l'application.
- Aucune réécriture des anciens assets ou fichiers : une version cible
  existante ne peut être utilisée que si son inventaire et ses SHA correspondent
  **exactement** à l'archive fournie.
- En cas d'échec Python pendant la copie/l'application, suppression des
  **seuls fichiers créés** et conservation de l'ancien pack/éditeur.
- Après un arrêt brutal du processus pendant la copie, un répertoire de
  version partiellement écrit peut subsister. Le projet enregistré conserve
  l'ancien reçu ; l'opération suivante refuse ce répertoire incomplet.
  **Il ne s'agit pas encore d'une transaction durable tout-ou-rien sur les
  fichiers et le GameProject.** Toute suppression d'orphelins doit être revue
  manuellement ; ne pas prétendre à un rollback crash-safe complet.
- La présence d'une version antérieure sur disque ne suffit pas à revenir en
  arrière : l'archive d'origine et son pin sont toujours requis.
- Aucune signature de créateur, preuve juridique de redistribution,
  permission d'exécution, migration de scripts, téléchargement distant ou
  certification d'export n'est accordée.

## Vérification

\`\`\`sh
python -m unittest \
  tests_standalone.test_drawtemp_r58b_upgrades \
  tests_standalone.test_drawtemp_r58b_package_manager \
  tests_standalone.test_drawtemp_r58a_package_ecosystem \
  tests_standalone.test_drawtemp5_r24c
\`\`\`

Test Qt additionnel sous Python 3.12 + PySide6 6.8.3 :

\`\`\`sh
QT_QPA_PLATFORM=offscreen python -m unittest \
  tests_standalone.test_drawtemp_r58b_qt
\`\`\`

Le test offscreen, même réussi, ne certifie ni la navigation clavier/manette
en conditions réelles ni le DPI, le GPU, la compatibilité OS ou l'accessibilité.

**Prochain lot R58.B3** : ajouter un reçu canonique avec dépendances directes,
fermeture/résolution de dépendances, transactions multi-packs avec journal de
reprise durable, schéma de migration id/kind/path et nettoyage contrôlé des
ressources orphelines. **R58.C** : démontrer une réutilisation personnage/HUD/quête
dans deux jeux avec export et provenance indépendante.
