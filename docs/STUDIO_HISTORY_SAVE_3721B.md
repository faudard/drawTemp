# 3.7.21B — Historique transversal et sauvegarde récupérable

## Objectif

Enregistrer les deux documents historiques **Content** et **GameProject**
dans un seul geste de l'éditeur, sans modifier leurs contrats de sérialisation,
leurs versions ni les sauvegardes/replays du Player. Offrir une timeline
d'édition commune au Map Editor et au Game Studio.

## Interface

- **Enregistrer tout** : applique les champs de configuration, valide le
  contenu tactique et le manifeste de projet ensemble, puis publie les
  deux JSON. Le projet est enregistré à côté du contenu sous le nom
  « nom.game.json » (même convention que reload_project).
- **Annuler / Rétablir** : restaure les deux états en mémoire; snapshots
  plafonnés à 50 modifications, redo invalidé par une nouvelle opération.
  Un glisser de pinceau forme un seul point d'historique.
- Le Studio capture les actions UI passant par _run, les actions carte
  via design_change et les modifications de cinématique via _apply.
  Les champs en saisie non appliqués ne sont pas des changements du modèle.

Les boutons d'annulation internes des panneaux existants sont conservés.
Lors d'une annulation globale, leurs piles locales sont invalidées pour
éviter de réappliquer un snapshot d'une autre branche d'historique.

## Protocole de sauvegarde et récupération

Les deux fichiers ne peuvent pas être remplacés simultanément par le
système de fichiers. Un journal d'intention et deux générations sont utilisés.

1. Validation croisée par Content.from_dict et GameProject.from_dict.
2. Préparation des deux fichiers .studio-next et sauvegarde des octets
   précédents dans .studio-prev (sans reformater les anciens fichiers).
3. Publication atomique du journal <content>.studio-recovery.json, incluant
   chemins absolus et empreintes SHA-256 précédentes/suivantes.
4. Remplacement atomique **par fichier** : Content, puis GameProject.
5. Suppression du journal après les deux publications; conservation des
   .studio-prev comme génération de secours.

Si une panne intervient après publication du journal, le prochain lancement
du Map Editor demande explicitement de **terminer** la nouvelle sauvegarde,
de **revenir** aux fichiers précédents ou de **quitter sans rien modifier**.

Le protocole vérifie les deux destinations et toutes les sources nécessaires
AVANT de restaurer quoi que ce soit. Une modification externe, un fichier de
récupération altéré ou une version inconnue bloque la récupération, sans
écraser les preuves. Le dialogue de récupération est également proposé lors
de l'ouverture d'un autre document contenant un journal.

Pour prévenir la **perte de mises à jour**, l'éditeur conserve les empreintes
SHA-256 des deux fichiers au dernier chargement/enregistrement réussi.
« Enregistrer tout » refuse de réécrire une paire modifiée entre-temps par
un autre processus. Le store vérifie encore la paire après préparation et
chaque destination juste avant publication. Une collision tardive conserve
le journal et nécessite une récupération contrôlée.

Après un Undo global, les caches du storyboard et du renderer cinématique
sont réinitialisés, les sons actifs sont arrêtés et la mission courante est
recalée si la mission restaurée n'existe plus.

Tant qu'un journal est présent, « Enregistrer tout » et les sauvegardes
anciennes du Studio refusent d'écraser l'état interrompu.

Les commandes isolées « Enregistrer sous » et « Enregistrer projet de jeu… »
restent pour compatibilité; seule « Enregistrer tout » fournit la coordination.

## Tests et gate

Commande : python -m unittest tests_standalone.test_studio_transaction_3721b

Scénarios couverts : round-trip, préflight invalide, undo/redo combiné,
invalidation redo, panne pendant la deuxième publication, rollback,
rollforward, premier enregistrement interrompu, fichier externe modifié
et backup corrompu.

La matrice Python teste les transactions et les conflits de fichiers.
Le job Linux Tk/Xvfb exécute explicitement
tests_standalone/test_studio_history_gui_3721b.py : créer une mission,
modifier la configuration, annuler/rétablir et enregistrer les deux fichiers.
La revue manuelle doit encore couvrir une panne réelle, le choix de
récupération et la réouverture sous Windows/macOS.

## Limites

- Cette transaction couvre Content et GameProject, pas les imports PNG/WAV
  ni l'export ZIP.
- Il ne s'agit **pas** d'une transaction ACID multi-fichiers : un lecteur
  externe peut observer une paire incomplète avant récupération.
- L'historique global est en mémoire, non un journal de commandes persistant;
  les snapshots complets pourront être remplacés par des commandes typées.
- Les raccourcis globaux Ctrl+Z/Y ne sont pas interceptés pour conserver
  l'Undo natif des champs texte.
