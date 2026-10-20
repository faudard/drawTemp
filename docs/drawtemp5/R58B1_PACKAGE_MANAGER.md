# R58.B1 — Package Manager Qt : audit et retrait réversible

**Statut : incrément implémenté en PR, non certifié.** Ce lot étend R58.A
et le système d'archives/reçus R24.C. Il ne représente pas le gate R58.B complet.

## Utilisation dans Studio

Dans un projet **déjà enregistré**, ouvrir **Outils → Packages de ressources R58
→ Gérer les packages…**. Le dialogue affiche la liste R24.C canonique des
packages, les versions, ressources, empreintes d'archive, usages et motifs de
blocage. Le Studio conserve le **même AuthoringSession** et les mêmes actions
Undo/Redo que le reste de l'éditeur.

**Installer un pack vérifié…** ouvre une archive locale explicite, puis demande
son SHA-256 connu *indépendamment* des octets de l'archive. R58.A vérifie
le pin, les dépendances épinglées et les recettes existantes. Le Studio
affiche une confirmation par défaut **Non**. L'installation simple utilise
l'implémentation R24.C de référence, qui refuse le remplacement de fichiers
et revalide l'archive, les contraintes du projet et la révision du document.

**Retirer les références…** est activé uniquement si le pack est sans usage.
Une prévisualisation liste les assets et fichiers concernés. Après confirmation
par défaut **Non**, une **seule** transaction AuthoringSession retire ses entrées
AssetRegistry et son reçu R24.C ; l'application est contrôlée contre un
changement de révision, de contenu ou de SHA-256 depuis la prévisualisation.

## Politique de sûreté

- **Aucun octet de ressource n'est supprimé physiquement** : les fichiers déjà
  importés restent disponibles après un retrait, afin de permettre
  Annuler/Rétablir et de ne jamais casser une restauration de sauvegarde.
  Le nettoyage physique et la collecte des orphelins nécessitent un
  futur contrat séparé, explicite et fondé sur des références externes.
- Les *bindings* AssetRegistry, les animations non possédées par le pack,
  les références du Content et les métadonnées/extensions du GameProject
  sont examinés ; tout usage détecté interdit le retrait.
- Les reçus R24.C ne conservent **pas** les arêtes de dépendance d'origine.
  Un projet contenant **plusieurs** packs refuse donc de retirer un seul pack
  (dépendances non prouvables), même si leur usage direct paraît nul.
- L'import de plusieurs archives n'est pas encore une transaction atomique ;
  le dialogue installe **un** pack à la fois. Pas de mises à jour silencieuses,
  migration automatique, résolution réseau ou rollback d'une collection
  de packs. Les migrations de versions doivent rester explicites et revues.
- Le SHA-256 ne prouve ni signature de l'auteur, ni authenticité, ni droit légal
  de redistribution. Les licences des manifestes sont des déclarations
  d'auteur et ne sont **pas** approuvées automatiquement à l'export.
- Les modifications ne sont pas sauvegardées automatiquement sur disque ;
  Studio exige toujours une sauvegarde explicite.

## Tests

~~~bash
python -m unittest \
  tests_standalone.test_drawtemp_r58a_package_ecosystem \
  tests_standalone.test_drawtemp_r58b_package_manager \
  tests_standalone.test_drawtemp5_r24c
~~~

Qt offscreen optionnel (PySide6 6.8.3 / Python 3.12) :

~~~bash
QT_QPA_PLATFORM=offscreen python -m unittest \
  tests_standalone.test_drawtemp_r58b_qt
~~~

Les tests couvrent le parcours du dialogue, un SHA invalide, la liaison au
registre, le retrait, les références externes (bindings, animation et
métadonnées), les dépendances inconnues, la corruption, l'Undo/Redo et les
changements de révision. Ce test **offscreen** n'est pas une certification
onscreen, GPU, accessibilité, DPI ou manette ; il faut de la QA matérielle et
les preuves de CI sur le SHA final.

## Suite : R58.B2 et R58.C

R58.B2 : schéma de reçu contenant une fermeture de dépendances vérifiable,
migrations versionnées, diff d'updates, rollback crash-safe, désinstallation
avec analyse exhaustive des références, contrôle précis de rétention physique.

R58.C : construire et installer un pack original
**personnage + HUD + quête** dans deux jeux indépendants, avec preuves
de licence, provenance et export sur machine propre. Les gates
R58.A (signature si infrastructure disponible), R58.B et R58.C restent ouverts.
