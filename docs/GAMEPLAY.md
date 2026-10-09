# Règles du runtime autonome

## Horloge et activation

- Départ à CT 0 pour le contenu fourni ; CT += Speed par tick, activation à 100.
- Haste : gain ×1,5 arrondi inférieur ; Slow : gain /2, au moins 1. Sleep/Stop figent CT.
- Égalité : ordre du roster, indépendamment du CT excédentaire.
- Un Move et un Act par activation, ordre libre. Attendre conserve une incantation.
- Fin : coût 100 pour Move+Act, 80 pour un seul, 60 pour attente. Overflow conservé,
  reliquat plafonné à 60. Une commande scellée au début de l’activation est consommée.
- Les statuts positifs décrémentent en ticks ; `-1` dans les spawns est permanent.
  Poison/Regeneration agissent en fin d’activation (1/8 PV max, au moins 1).
- Aucun cooldown universel. MP et temps d’incantation limitent les compétences.

## Terrain et placement

Déplacement cardinal, coût de destination, montée/descente limitée par Jump. Les
unités vivantes bloquent les chemins, les corps peuvent être traversés. Une résurrection
échoue si sa case est occupée ou devenue bloquée. Le chemin est déterministe à coût égal.
Les dangers s’appliquent à chaque case parcourue ; une mort interrompt immédiatement
le déplacement et libère l’activation.

Ignore Height ignore la différence de niveau. Teleport ignore le chemin mais conserve
les contraintes de destination ; jusqu’à Move+5, succès 100% dans Move puis -10 points
par case supplémentaire. L’échec consomme Move. Move-MP Up rend 10% MP max (minimum 1).
Les poussées/tractions s’arrêtent aux obstacles/unités ; une chute au-delà de Jump inflige
5 dégâts par niveau excédentaire. Les déplacements forcés peuvent prendre la couronne.

La ligne de vue utilise une grille supercover, bloque les murs/corners et les cases
plus hautes que les deux extrémités +1. C’est une convention tactique simple, sans
raycast 3D. Le couvert est une donnée de terrain et un faible critère de placement IA ;
il n’ajoute pas de réduction de dégâts, conformément à la séparation avec l’évasion.

## Combat

Attaque : PA×WP en mêlée/lance ; moyenne(PA,Speed)×WP à distance ; MA×WP pour Focus ;
PA²×Brave/100 à mains nues. Magie : puissance×MA×Faith lanceur×Faith cible/10000.
Les supports Attack/Magic Attack UP multiplient par 4/3 ; Defense/Magic Defense UP,
Protect/Shell par 2/3. Guard divise par 2. DEF est soustraite puis résistance élémentaire
appliquée (de -100% vulnérabilité à 100% immunité). Les arrondis sont entiers, par étape.

Évasion physique multiplicative : face = classe/bouclier/arme/accessoire ; côté =
bouclier/arme/accessoire ; dos = accessoire. Concentrate ignore ces couches mais pas
Blade Grasp (Brave). Magie utilise une couche d’évasion magique. Charging/Sleep/Stop
neutralisent l’évasion ; Charging augmente les dégâts physiques ×1,5.

Un jet par victime est partagé entre les effets d’une compétence. Les effets sont
appliqués dans leur ordre de définition. Les formes prises en charge sont diamond,
cross et square. `scope=target` affecte les unités de la zone, y compris les alliés ;
`allies` et `enemies` filtrent par rapport au lanceur. Les zones persistantes infligent
des dégâts en fin d’activation, expirent en ticks et peuvent se cumuler.

Counter ne peut pas déclencher une autre réaction en chaîne. Opportunity agit à la
sortie d’une case adjacente, Brave comme chance de déclenchement. Pursuit remplace les
dégâts gratuits par un suivi spatial : une fois par Move ennemi, le poursuivant peut
occuper la case adjacente qui vient d’être libérée, y compris après Disengage, avec un
coût de 20 CT et un jet de Brave. Le preview de déplacement expose ce risque.
Auto-Potion consomme réellement une potion disponible, soigne 25 PV et ne ressuscite pas.
MP Switch redirige tout le coup vers les MP dès qu’au moins 1 MP reste, sans report de
l’excédent sur les PV.

Charge est une commande Move+Act réservée aux unités qui contrôlent l’espace en mêlée.
Elle exige un ennemi aligné et au moins deux cases d’approche rectiligne, coûte 20 CT
supplémentaires, s’arrête à la portée d’engagement, résout l’attaque de base puis tente
un push d’une case sur coup direct. Guard/Overwatch/dangers peuvent interrompre l’approche
et Brace absorbe le push : Charge convertit donc position et temps en pression plutôt
qu’en multiplicateur de dégâts gratuit.

## Incantation

Le CT du lanceur continue pendant le cast. Les MP sont payés à la résolution, pas au
lancement. Move/Wait conservent le cast ; une autre action le remplace. Sleep/Stop,
mort et Silence magique interrompent ; les dégâts ordinaires ne l’interrompent pas.
Short Charge divise le délai par deux, minimum 1 tick.

`lock=cell` conserve la case ; `lock=unit` suit la position actuelle. Portée/ligne de vue
sont vérifiées au lancement, pas à la résolution. Une case vide reçoit tout de même
les effets de zone et consomme les MP. Manque de MP à résolution : échec sans dépense.
Les casts simultanés sont résolus dans l’ordre du roster après mise à jour des horloges.

Les prévisions affichent le coup direct avant réactions et avant futurs changements de
position/statut ; elles ne prétendent pas prédire les décisions adverses pendant un cast.

## Missions et campagne

Objectifs : élimination, survie en ticks, extraction d’un joueur, contrôle **continu**
d’une zone non contestée, récupération puis extraction de la couronne. Mort du porteur :
la couronne tombe sur sa case. Une défaite (aucun joueur vivant ou personnage protégé mort)
prime sur une victoire simultanée. Les ennemis éliminés ne terminent pas automatiquement
une mission d’extraction/contrôle : son objectif doit être atteint.

Les triggers s’exécutent une fois : tick atteint, entrée d’un joueur, unité vaincue.
Actions disponibles : message, ajout/modification d’un danger, application de statut.
Les portes et interrupteurs ouvrent des passages ; les coffres ajoutent de l’or au butin.
Un objet consomme Act. Les interactions sont réservées au joueur.

Chaque première victoire accorde la récompense, le butin, 100 XP et 50 XP de classe,
puis débloque les missions suivantes. Niveau = 1+XP/100, niveau de classe = 1+XP/50,
plafonds 20. +3 PV par niveau et +1 PA tous les trois niveaux gagnés. Les classes ajoutent
leurs bonus et compétences selon maîtrise ; l’équipement ajoute des bonus sans cumul
lors des préparations répétées. Pas de récompense de défaite ni de farming d’une mission
déjà validée. L’or achète les objets tarifés ; équiper transfère une unité de l’inventaire
vers le slot et restitue l’ancien objet. Déséquiper restitue l’objet.

## IA et équilibrage

L’IA évalue déplacement + attaque/compétence, soins, résurrection et interactions proches.
Elle pénalise les dégâts alliés, MP, déplacement et dangers, valorise un KO, priorise
les soins à moins d’un tiers des PV, et progresse vers les objectifs. Elle attend pendant
une incantation. Ce n’est pas une recherche minimax et elle ne planifie pas encore un
puzzle de portes ou une coordination de plusieurs unités. Les slots, stats et compétences
permettent de construire des comportements distincts, sans profils IA configurables séparés.

`balance` exécute des seeds consécutives et rapporte les issues et durées médianes.
`limit` signifie que le budget de commandes a été atteint, pas une victoire. Une absence
d’activation pendant 10 000 ticks devient un match nul explicite.

## Migration de Godot

**Actif et autonome :** `sporebound/`, `tests_standalone/`, `pyproject.toml` et la CI
`standalone.yml`. Godot n’est utilisé par aucune commande du nouveau runtime.

**Conservé pour référence :** `scripts/`, `scenes/`, `maps/`, `addons/`, `data/*.tres`,
`project.godot`, assets, anciens tests `.gd` et documents versionnés. L’ancien README et
l’ancienne architecture sont dans `docs/legacy/` ; leurs anciens liens étaient relatifs
à la racine du dépôt. Les anciens points d’entrée Godot restent exécutables séparément.

Les JSON fournis reprennent les personnages et l’esprit tactique du projet, mais ce sont
quatre scénarios de travail, avec stats/compétences rééquilibrées, pas une conversion
fidèle des trois maps `.tscn`. Il n’existe pas encore d’import automatique `.tres/.tscn`
ou des anciennes sauvegardes. Ne pas supprimer ces sources avant migration vérifiée.

Restent notamment : compatibilité zodiacale/sexe, Intercept, décompte de disparition des
corps, arbres de progression historiques, tous les passifs et effets custom, renforts,
cinématiques/dialogues, créateur de héros et pipeline d’assets. Aucun de ces systèmes
n’est déclaré porté par cette PR. Le nouveau runtime n’est pas un clone FFT exact.

## Validation

```sh
python -m unittest discover -s tests_standalone -v
python -m sporebound validate
python -m sporebound balance --mission garden --runs 20
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest discover -s tests_standalone -p test_editor_gui.py -v
```

La dernière commande concerne Linux. Le test Tk édite réellement une case, annule/rétablit,
enregistre le JSON, lance le playtest, joue une activation IA et revient à l’éditeur.
Les règles et le document de l’éditeur sont testables sans affichage ; le test Tk est
explicitement ignoré lorsqu’aucun affichage de test n’a été demandé.

## Déploiement et assaut du château

Générer les quatre missions de siège puis les ouvrir dans l’éditeur :

```sh
python -m examples.siege_scenarios > siege.json
python -m sporebound editor --content siege.json
python -m sporebound play --content siege.json --mission castle_ram
```

Chaque mission commence à t=0, sans unité active. Les zones bleues de l’éditeur
sont les zones de déploiement : sélectionner l’unité dans la liste, cliquer une
case, choisir une orientation et exécuter `deploy`. Répéter librement, puis
exécuter `start_battle`. Au terminal : `deploy captain 0 2 E`, puis `start`.
La formation proposée est déjà valide : démarrer sans la modifier est possible.
L’IA et les simulations acceptent cette formation explicitement.

Le déploiement ne consomme ni CT, ni action, ni aléatoire et ne déclenche aucun
renfort, statut ou objectif. Toute l’empreinte d’un grand acteur doit tenir dans
une même zone, sans chevauchement. Seuls les personnages joueurs vivants peuvent
être placés. Une fois l’assaut lancé, le placement libre est verrouillé.
Sauvegarde/reprise et replay incluent les commandes de préparation.

Dans les données, `deployment` est une liste de zones
`{"id": "camp", "cells": [[0, 2], [1, 2]]}`. Les positions initiales des joueurs
doivent tenir dans ces zones. Sans zone, le comportement historique reste
inchangé : activation immédiate. Les zones s’éditent dans l’onglet JSON.
Cette étape place le groupe déjà prévu dans la mission ; sélection d’une réserve,
budget d’armée et placement des machines ne sont pas encore implémentés.

Les missions bélier/artillerie/renforts disposent maintenant d’une enceinte fermée
et d’une porte `locked: true` : impossible de contourner le mur ou d’ouvrir la
porte à la main. Un interrupteur lié peut toujours lever une porte verrouillée.
Avancer le bélier jusqu’à la porte puis frapper quatre fois (ou deux tirs de
catapulte) ouvre le passage. L’approche avec le troll est une mission d’élimination.

### Remparts, défenses et salle du trône

Les exemples proposent désormais sept missions. Le scénario complet passe par
l’approche contre le troll, une voie au choix (bélier, artillerie, infiltration),
la cour intérieure, puis `castle_throne`. La victoire finale exige d’éliminer le
châtelain et ses deux gardes royaux ; une défaite ne permet pas de passer à la suite.
PV, MP, statuts et consommables suivent le groupe. `elapsed_ticks` cumule le temps
des phases terminées, auquel s’ajoute le tick du combat en cours.

```sh
python -m examples.siege_campaign --play
python -m examples.siege_scenarios > siege.json
python -m sporebound editor --content siege.json
python -m sporebound play --content siege.json --mission castle_ramparts
```

Le lanceur de campagne terminal joue automatiquement les défenseurs et propose
les choix entre les phases. C’est un parcours en mémoire : les sauvegardes de
combat de la CLI habituelle restent propres à une mission, sans reprise globale
de campagne. L’éditeur permet de tester chaque mission séparément.

**Remparts.** Installer `grapple` avec `interact grapple`, puis se déplacer sur
son point de départ `(7,1)` et vers le rempart `(8,1)`. Atteindre le levier
`portcullis_lever` pour lever la herse et emprunter `stairs` pour descendre dans
la cour. Le bélier reste une autre solution dans cette mission.

Les objets `passage` ont `pos`, `destination`, `cost` (défaut 2), `enabled`
et `bidirectional` (défaut true). Une liaison désactivée doit être installée par
interaction, ce qui consomme l’action. La traversée fait partie du déplacement
normal : budget, collisions sur toute l’empreinte, réactions, dangers à l’arrivée
et triggers restent appliqués. Elle autorise la différence de hauteur prévue par
l’auteur, sans permettre de marcher librement à travers les murs. Les cordes,
échelles, escaliers et passerelles utilisent ce même contrat.

**Défenses.** `boiling_oil` frappe devant la porte ; `stone_drop` couvre le
passage de la cour. Ces objets `defense` définissent l’équipe propriétaire,
les cases visées, la puissance, les charges et le cooldown en ticks. Un opérateur
vivant adjacent doit dépenser son action pour tirer. L’IA évalue les cibles et
évite les tirs dont les dégâts alliés dépassent le bénéfice. Une zone touche
chaque acteur une seule fois, même s’il occupe plusieurs cases. Le tir allié est
possible ; les charges épuisées et les postes sabotés restent inutilisables.
Un adversaire adjacent peut neutraliser définitivement le poste par interaction.

L’éditeur colore les zones menacées en orange, dessine les liaisons et affiche
leurs états ainsi que les charges restantes. Le dessin est utilitaire ; l’huile
inflige des dégâts immédiats et ne crée pas encore de nappe persistante.
