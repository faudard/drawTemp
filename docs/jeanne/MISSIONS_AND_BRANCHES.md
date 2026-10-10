# Jeanne — Catalogue de missions, embranchements et structure de campagne
**Version de conception 1.0.** Toute la campagne décrite ci-dessous est **prévue** et non considérée comme codée.

Références : [Bible narrative](NARRATIVE_BIBLE.md), [Relations et décisions](RELATIONSHIPS_AND_IMPLEMENTATION.md).

## 1. Structure générale

Période : 1428–1431 en uchronie ; durée indicative : 25–35 h pour le chemin principal complet à maturité (estimation, pas promesse de performance). Prologue estimé : 30–45 minutes, dont au moins deux combats courts.

**Convention :** les IDs en gras ci-dessous sont des identifiants *proposés* pour les missions tactiques de Content. Les scènes de dialogue, de révélation ou de couronnement restent des nœuds narratifs dans GameProject.story, sauf quand une bataille ou un objectif justifie une mission. Le siège « valcroix » est une session multi-fronts associant des missions de secteur, **pas** une fausse mission gagnée automatiquement.

### Graphe macro (les alternatives rejoignent ensuite un nœud commun)

~~~text
PROLOGUE
p0_01_lame -> p0_02_incendie
    -> [p0_03a_secours | p0_03b_poursuite]
    -> p0_04_fuite
ACTE I
a1_01_route -> a1_02_pont -> a1_03_hospice
    -> [a1_04a_archives | a1_04b_familles]
    -> a1_05_vaucouleurs
ACTE II
a2_01_preuves -> a2_02_convoi -> a2_03_augustins
    -> a2_04_riviere -> a2_05_marche_reims -> scène du sacre
ACTE III
a3_01_prep -> siège valcroix (fronts de secteur a3_s01…a3_s06)
    -> a3_03_crypte -> jugement moral de Bracourt/Guillaume
ACTE IV
a4_01_compiegne -> [a4_02a_captivite | a4_02b_secours]
    -> a4_03_avel -> a4_04_voix
ACTE V
a5_01_sceau_est -> a5_02_sceau_ouest
    -> a5_03_bannieres -> a5_04_chapelle -> a5_05_veilleur
    -> [6 conclusions politiques possibles ; épilogues modulaires]
~~~

L'ordre des deux sceaux au début de l'acte V peut être configurable après livraison de l'authoring de routes ; en v1 de production, l'ordre ci-dessus demeure linéaire pour éviter un embranchement technique prématuré.

## 2. Prologue — Les voix dans les champs

Scène préalable **sc_p0_champs** : déplacement libre dans les champs, découverte d'objets (blé, talisman, trace de cheval), rencontre courte avec Jacques ou souvenir de sa voix. Les voix annoncent « une couronne, une épée et des cendres » ; caméra vers Domrémy, fumée puis flammes. La scène impose l'appel à l'aide, pas une victoire magique.

| ID | Type | Situation / carte | Objectif tactique vérifiable | Décisions et conséquences |
| --- | --- | --- | --- | --- |
| **p0_01_lame** | Tutoriel / flashback | Cour familiale, quelques années auparavant | Déplacer Jeanne, parer, frapper un mannequin et Renaud sans tuer | Établit entraînement et mentor ; ne bloque jamais la suite |
| **p0_02_incendie** | Combat court | Bord de Domrémy en flammes | Écarter deux soldats et rejoindre la place | Indices sur ordre de mission ; sortie par interaction réelle |
| **p0_03a_secours** | Alternative A | Maison effondrée, grange | Sauver au moins 2 civils et tenir la sortie pendant 3 tours | + soutien populaire, Margot introduite plus tôt ; indice secondaire retardé |
| **p0_03b_poursuite** | Alternative B | Sentier hors du village | Intercepter le porteur du sceau avant le bord de carte | + preuve, + renseignements ; certains villageois perdus |
| **p0_04_fuite** | Extraction | Route et pont, maisons qui s'effondrent | Extraire Jeanne + au moins un civil/compagnon | Fin des combats du prologue, camp de réfugiés, deuil et première sauvegarde |

**Garantie :** les deux branches récupèrent plus tard les informations indispensables sur Bracourt. Margot peut être recrutée dans l'acte I même si l'on a poursuivi les ennemis.

**Flag set d'entrée :** jeu « neutre », jamais de bonus occulte, arme de Jacques et souvenir de Renaud. Débuter sans combat contre un démon. **Pas de gameplay trompeur :** le flashback est clairement marqué comme souvenir et la mort de Jacques est un événement du canon.

## 3. Acte I — Les Cendres

| ID | Carte | Objectif / sous-objectifs | Retombée |
| --- | --- | --- | --- |
| **a1_01_route** | Chemin de Neufchâteau | Escorter des familles et empêcher le pillage d'un chariot | Débloquer les mécanismes d'escorte, rencontre Renaud |
| **a1_02_pont** | Pont à péage | Briser un barrage OU négocier après preuve tactique | Première possibilité de résolution non létale |
| **a1_03_hospice** | Hospice abandonné | Protéger Agnès et récupérer un témoin | Lettre scellée menant à Bracourt |
| **a1_04a_archives** | Poste d'archives | Infiltrer, saisir des registres et extraire l'escouade | Preuves plus solides, risque politique plus fort |
| **a1_04b_familles** | Étable fortifiée | Libérer des otages avant l'arrivée de renforts | Popularité civile, documents recouvrables plus tard |
| **a1_05_vaucouleurs** | Porte fortifiée | Gagner l'accès à Baudricourt par défense d'une position ou démonstration militaire | Passage vers Chinon et ellipse temporelle |

**Dialogues forts :** confrontation Jeanne–Renaud sur l'entraînement ; premier message de Guillaume, qui réclame des papiers au nom de Bracourt ; Agnès identifie une formule du Livre ; Jeanne prend la responsabilité d'emmener des civils.

**Décision centrale :** une escorte/hospice en danger oblige à choisir entre documents et survivants. Le choix doit affecter les dossiers de cour à l'acte II et la mobilisation civile de l'acte III.

## 4. Acte II — La Bannière

**Ellipse :** Jeanne a 18 ans au début de cet acte ; la rencontre avec Charles à Chinon relève du récit uchronique. Elle n'est pas déclarée « épouse future » ou enfermée dans une trajectoire sentimentale.

| ID | Carte | Objectif / sous-objectifs | Retombée |
| --- | --- | --- | --- |
| **a2_01_preuves** | Cour d'armes de Chinon | Épreuve tactique : défendre un porte-étendard contre vagues limitées | Le dauphin accepte une mission militaire |
| **a2_02_convoi** | Routes d'Orléans | Faire passer vivres et blessés ; route secondaire possible | Ressources lors de l'assaut d'Orléans |
| **a2_03_augustins** | Approche fortifiée | Neutraliser une position / tenir une passerelle, sans tout éliminer | Retrait anglais et moral de l'armée |
| **a2_04_riviere** | Traversée de Loire | Première confrontation Aveline ; tenir puis extraire ou sécuriser un passage | Rivalité et respect selon pertes, captifs et dialogues |
| **a2_05_marche_reims** | Routes de Champagne | Protéger une délégation et ouvrir la route de Reims | Accès au sacre et réaction de la cour |

**Scènes :** sc_a2_chinon ; sc_a2_cour ; sc_a2_avel_arrive ; sc_a2_sacre. Le sacre n'est pas une récompense automatique dans une boîte de dialogue après un combat : il doit devenir un événement de présentation scénarisé, mais il ne demande pas une bataille factice.

**Guillaume :** altercation documentée, possible libération d'un prisonnier / refus d'un accord. Aucune mécanique de romance tant qu'il s'agit d'un antagoniste ayant le pouvoir de capturer Jeanne. **Aveline :** premier affrontement dont la condition de victoire peut être un objectif défensif, sans « mort impossible » ni HP artificiellement infinis.

## 5. Acte III — Le Fer et le Sang : Valcroix

**Valcroix est fictif.** Les événements 1429–1430 qui y sont associés sont une divergence de l'histoire réelle.

| ID logique | Type | But |
| --- | --- | --- |
| **a3_01_prep** | Mission d'approvisionnement, avant le siège | Établir un dépôt ou intercepter un convoi de ravitaillement de Bracourt |
| **valcroix** | Opération stratégique multi-fronts | Choisir l'approche, répartir escouades, combattre des secteurs, ouvrir la cour et atteindre le trône |
| **a3_03_crypte** | Mission tactique après la salle du trône | Protéger les preuves et sortir des archives qui s'effondrent |

### Fronts du siège à relier au vrai moteur de combat

| Secteur / ID Content | Objectif | Liens causaux |
| --- | --- | --- |
| **a3_s01_porte** | Amener le bélier, frapper plusieurs fois, lever la herse | Ouvre cour ; herse bloquée ralentit les renforts |
| **a3_s02_remparts** | Gagner un passage, neutraliser l'huile et les archers | Réduit les pertes à la porte ; peut ouvrir l'accès latéral |
| **a3_s03_souterrains** | Franchir patrouilles et saboter une serrure | Débloque une arrivée intérieure et peut empêcher une vague |
| **a3_s04_ravitaillement** | Couper ou escorter un convoi | Modifie les provisions, capacités des engins et vagues |
| **a3_s05_cour** | Contrôler deux positions et stopper la contre-attaque | Autorise le final selon conditions vérifiées |
| **a3_s06_trone** | Affronter Bracourt, ses gardes et ses postes défensifs | Vraie victoire tactique requise pour déclarer le château pris |

### Approches (5) — modes d'entrée, non cinq campagnes parallèles
1. **Bélier :** forte pression sur la porte, risque d'huile et de sabotage, coût de provisions.
2. **Infiltration :** petite équipe par les remparts, troupes de soutien retardées, possibilité d'ouvrir la herse.
3. **Souterrains :** patrouilles, pièges, mission tactique courte, avantage sur les réserves.
4. **Négociation :** preuve locale requise, trêve possible, pas de victoire du trône inventée.
5. **Assaut direct :** risque maximal et dépenses immédiates, avancée stratégique plus rapide.

L'expérience doit réutiliser la PR de vertical slice existante **#31** et le Campaign & Siege Studio **#33**, sans considérer leurs branches ouvertes comme déjà fusionnées. Réaligner le personnage du châtelain / boss en **Bracourt**, conserver le combat à phases et les exigences de journal/replay. Guillaume peut apparaître en duel intermédiaire, officier capturable ou défenseur absent selon les décisions antérieures ; **Bracourt reste le boss principal du siège** pour préserver la cohérence de l'enquête.

### Résolutions du siège
- Château pris après défaite réelle de Bracourt : documents récupérés.
- Trêve partielle avec secteur neutralisé puis combat de trône : documents récupérés avec coût politique.
- Retraite/défaite locale : remédiation et nouvelle tentative selon ressources ; une défaite finale définitive doit être explicite.
- Sort de Guillaume **après** l'opération : arrestation / exposition / libération sous conditions / mort possible selon vraie action.
- Sauver les registres est un objectif chronométré indépendant de la mort du boss ; échouer ne softlocke pas le récit, mais produit des preuves fragmentaires révélées autrement.

## 6. Acte IV — Les Deux Élues

| ID | Carte | Objectif | Conséquence |
| --- | --- | --- | --- |
| **a4_01_compiegne** | Portes de Compiègne | Couvrir une retraite après une sortie ou tenir une ligne | Capture possible selon choix, réputation et position |
| **a4_02a_captivite** | Fortin de captivité | Évasion par tactique, coopération de compagnon ou négociation vérifiée | Blessures, perte temporaire de matériel, témoin gagné |
| **a4_02b_secours** | Camp avancé | Secourir un prisonnier/chef de milice sans Jeanne captive | Sauvetages et preuves supplémentaires |
| **a4_03_avel** | Front de trêve | Gagner un duel d'objectifs, évacuer civils ou tenir une position | Alliance limitée / respect / hostilité |
| **a4_04_voix** | Ermitage, archives de la Confrérie | Réunir témoins et comparer les deux ensembles de visions | La manip ulation du Veilleur est soupçonnée |

**Important :** le système décide entre captivité et secours avant de déverrouiller la mission ; les deux chemins rejoignent la mission Aveline. Refuser l'alliance ne bloque ni la révélation ni la possibilité de vaincre le Veilleur.

## 7. Acte V — Le Jugement des Voix

| ID | Carte | Objectif | Effet dramatique |
| --- | --- | --- | --- |
| **a5_01_sceau_est** | Prieuré, cave d'archives | Récupérer ou neutraliser un premier sceau sous pression humaine | Première preuve matérielle de rituel |
| **a5_02_sceau_ouest** | Tour de garde isolée | Sauver les porteurs de documents et arrêter un rituel inachevé | Premier événement impossible à réduire à l'humain |
| **a5_03_bannieres** | Fronts de frontière | Coordonner secours, ravitaillement et attaque d'un centre rituel | Alliés et pertes reflètent les choix accumulés |
| **a5_04_chapelle** | Chapelle ruinée | Battre un démon et extraire un captif | Première bataille explicitement surnaturelle majeure |
| **a5_05_veilleur** | Cœur des reliquaires | Boss à plusieurs phases, détruire ou contenir le noyau, protéger les survivants | Choix final parmi les conclusions accessibles |

Les démons de l'acte V se battent suivant les **mêmes lois de moteur** que les unités humaines (initiative, lignes de vue, réactions, statut, boss), avec compétences et gabarits distincts. Éviter un second moteur « magie ».

## 8. Branches principales — préconditions, effets, convergence

| Nœud décisionnel | Alternatives exclusives | Flags persistants | Convergence |
| --- | --- | --- | --- |
| Après p0_02 | Secourir / poursuivre | prologue_path, civilians_saved, evidence | p0_04 |
| Après a1_03 | Archives / familles | a1_path, evidence, civilians_saved | a1_05 |
| Cour de Chinon | Dire tout / négocier des appuis | royal_favor, truth_public | a2_01 |
| Rencontre Aveline | Épargner prisonniers / utiliser force | aveline_respect, war_cruelty | a2_05 |
| Avant Valcroix | Cinq approches de siège | valcroix_approach, supplies_used | secteurs de Valcroix |
| Après la salle du trône | Déclarer / cacher les crimes de Guillaume, selon preuves | guillaume_truth, guillaume_fate | a3_03 |
| À Compiègne | Captivité / secours (état stratégique) | compiegne_branch, political_debt | a4_03 |
| Après a4_03 | Trêve / rivalité avec Aveline | aveline_alliance | a4_04 |
| Après a5_05 | Action finale choisie avec portes conditionnelles | finale_choice | conclusion + épilogues |

**Convergence ne signifie pas effacement :** les mêmes scènes peuvent être réutilisées avec dialogues et unités conditionnels. Les conséquences doivent être visibles après 1–3 missions, et revisitées en épilogue.

## 9. Missions secondaires facultatives (8 amorces)

| ID proposé | Sujet | Récompense narrative / tactique |
| --- | --- | --- |
| **s_margot_01_hospice** | Défendre les soigneurs | Margot progresse, réductions de pertes civiles |
| **s_renaud_01_serment** | Ancien duel, vérité sur Jacques | Confiance Renaud, compétence de contre |
| **s_agnes_01_archive** | Sauver une bibliothèque | Indice alternatif du Livre, codex |
| **s_thomas_01_echange** | Échange de prisonniers | Respect d'Aveline, informateur |
| **s_guillaume_01_restitution** | Restituer des terres et libérer des détenus | Condition de réparation (si personnage encore vivant et libre) |
| **s_avel_01_frontiere** | Trêve et escorte de familles | Preuve concrète pour l'alliance |
| **s_royal_01_comptes** | Enquête sur les finances d'un seigneur | Indice de Bracourt et influence de cour |
| **s_domremy_01_memorial** | Protéger un lieu de mémoire | Épilogue civil et reconnaissance des victimes |

Ces missions ne doivent jamais devenir des prérequis indispensables pour la compréhension de l'intrigue. Certaines peuvent conditionner une fin idéale ou une synergie secrète.

## 10. Parcours de validation narratif

1. **Protectrice :** secours -> familles -> Aveline respectée -> Guillaume jugé -> fin civile.
2. **Vengeresse :** poursuite -> archives -> Guillaume condamné -> conflit avec Aveline -> fin royale ou indépendante.
3. **Diplomate :** secours -> négociation -> trêve à Valcroix -> Aveline alliée -> paix fragile.
4. **Ambivalente :** poursuite -> compromis avec Guillaume -> restitution réelle -> alliance adulte facultative -> fin avec épilogue de couple.
5. **Sombre :** preuves cachées -> pouvoir occulte retenu -> Couronne de cendres.
6. **Sacrificielle :** renoncer au pouvoir -> protéger les alliés -> Dernier bûcher.

**Invariants testables :**
- chaque choix initial dispose d'au moins un chemin jusqu'à a5_05 ;
- aucune mission principale requise n'est définitivement inaccessible sans alternative ;
- les documents critiques sont accessibles via au moins deux sources ;
- les scènes en convergence reflètent les décisions passées ;
- toute fin est obtenue via un objectif vérifiable et une décision explicite ;
- le siège n'est pas validé par un flag narratif sans victoire au trône ;
- sauvegarde/reprise conserve relations, alliés, approche, états de secteurs et conditions de fin.
