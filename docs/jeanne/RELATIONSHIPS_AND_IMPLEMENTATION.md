# Jeanne — Relations, décisions et plan d'intégration drawTemp
**Version 1.0 · Proposition d'authoring, pas implémentation du jeu.**

Documents : [Bible narrative](NARRATIVE_BIBLE.md) · [Missions et embranchements](MISSIONS_AND_BRANCHES.md).

## 1. Principe de production

Ne pas confondre quatre sources de vérité :

1. **Contenu tactique** : unités, cartes, compétences, objectifs et missions validés dans Content.
2. **Projet narratif** : GameProject.story, scènes et choix, expressions conditionnelles, effets de choix.
3. **Progression persistante** : Campaign, missions réussies, flags et historique de décisions.
4. **Siège multi-fronts** : état stratégique, secteurs, vivres, fronts, horloge globale, journal et replay.

Ne pas dupliquer règles tactiques ou IA dans le récit. Une scène décrit une décision ; un combat prouve la réussite d'un objectif ; la progression sert de contrat entre les deux.

### État constaté dans le dépôt à la rédaction
- Le dépôt conserve le nom de package technique **sporebound**, le moteur Python headless et le Studio Tk.
- **sporebound/narrative.py** accepte actuellement, dans GameProject.story, les sections **scenes**, **entry_scenes**, **after_mission**.
- Un choix supporte **when**, **effects**, **next_scene** ; effets reconnus : **set_flag**, **add_flag**, **unlock_mission**, **gold**.
- Les prédicats disponibles sont **all**, **any**, **not**, **flag:eq/gte/lte**, **completed_mission**, **gold_gte**.
- Le graphe des scènes est **acyclique**, chaque scène doit posséder un choix sans condition ; 20 choix maximum par scène ; profondeur de conditions bornée.
- Le graphe Mission.next_missions est un enchaînement distinct ; **tous les successeurs déclarés y sont normalement déverrouillés en cas de victoire**. Ne pas l'utiliser pour simuler une branche exclusive.
- Les travaux de vertical slice du château et de Studio siège existent sous des PR distinctes **#31 et #33 ouvertes au moment de la rédaction**, pas nécessairement dans master.
- Les versions de formats et identités de contenu sont vérifiées lors des replays/sauvegardes : ne jamais réécrire des définitions en conservant une fausse compatibilité.

**Conséquence :** l'intégration Jeanne doit utiliser les flags et les **unlock_mission** de scènes de choix pour les embranchements réellement exclusifs. Il reste à raccorder de façon explicite les issues des opérations multi-fronts au flux d'événements narratifs et aux checkpoints du client graphique.

## 2. Identifiants et conventions de flags

IDs en ASCII snake_case, maximum 64 caractères conformément aux contraintes du validateur. Ne pas dépendre d'intitulés français pour les références internes. Les valeurs ci-dessous sont des **propositions de catalogue global de flags**, pas des variables déjà créées.

### Flags booléens / catégories
| Flag | Valeurs admissibles | Origine |
| --- | --- | --- |
| **prologue_path** | secours / poursuite | Sortie de p0_02 |
| **a1_path** | archives / familles | Hospice |
| **mother_witness** | true / false | Prologue ; information alternative toujours possible |
| **guillaume_truth** | true / false | Preuves et confession |
| **guillaume_restitution** | true / false | Mission ou conséquence documentée |
| **guillaume_fate** | accuse / prison / exile / allied / dead | Jugement après Valcroix |
| **romance_guillaume** | none / closed / growing / committed | Choix explicites à partir de l'acte IV |
| **avel_alliance** | hostile / truce / allied | Acte IV |
| **compiegne_branch** | captive / rescue | Compiègne |
| **valcroix_approach** | ram / infiltration / tunnels / negotiation / direct | Conseil de siège |
| **proofs_public** | true / false | Choix à la cour / après siège |
| **finale_choice** | dawn / crown / truce / embers / sacrifice / exile | Choix final |
| **mentor_truth** | true / false | Quête Renaud |
| **three_seals_resolved** | true / false | Opérations acte V |

### Scores entiers proposés
| Flag | Intervalle d'authoring conseillé | Effet |
| --- | --- | --- |
| **civilians_saved** | 0–100 | Soutien populaire, renforts civils et épilogue de Domrémy |
| **evidence** | 0–100 | Preuves judiciaires / dénonciation Bracourt |
| **royal_favor** | -100–100 | Soutien du roi, logistique et politique |
| **avel_respect** | -100–100 | Trêve, coopération et certains dialogues |
| **guillaume_trust** | -100–100 | Travail commun ; insuffisant à lui seul pour romance |
| **margot_trust** | -100–100 | Départs/retrouvailles et aide médicale |
| **renaud_trust** | -100–100 | Synergie protectrice et confession |
| **war_cruelty** | 0–100 | Réactions populaires, hostilité, fins sombres |
| **veil_knowledge** | 0–100 | Détection de faux rituels et options du final |

Les intervalles ci-dessus doivent être garantis par les scénarios et tests d'authoring ; **add_flag**, dans son implémentation actuelle, vérifie des limites générales mais n'applique pas automatiquement ces intervalles métier. Mettre une politique de clamp dans un adaptateur uniquement après définition explicite de sa sérialisation, sinon vérifier toutes les transitions en tests.

**Initialisation :** un flag absent n'est pas équivalent à un score entier zéro pour les conditions gte/lte. Les scènes d'introduction doivent initialiser les scores et catégorisations nécessaires avec **set_flag** et prévoir un chemin de secours. **add_flag** part en revanche de zéro lorsque la clé est absente ; ne pas s'appuyer sur cette différence implicitement.

## 3. Relations : états et conséquences

Les chiffres sont des paliers proposés, pas une mécanique de « séduction par points ». Les décisions narratives qualitatives doivent primer.

### Jeanne ↔ Guillaume
| Étape | Situation | État / condition | Contenu |
| --- | --- | --- | --- |
| I | Le crime et la poursuite | hostile, romance non disponible | Identification des responsabilités |
| II | Adversaires militaires | aucune scène d'intimité | Conflits de loyauté ; interrogatoires condamnés, pas érotisés |
| III | Valcroix | jugement de ses actes | Exiger vérité et réparation OU condamner / refuser |
| IV | Alliance éventuelle et adulte | guillaume_fate=allied, truth=true, restitution=true, trust>=60, romance non close | Conversations consenties ; confiance testée sur missions de secours |
| V | Engagement possible | Jeanne confirme librement, aucun rapport de captivité, crimes reconnus | Relation explicite ou amitié sans romance |
| Épilogue | Mariage **facultatif** | romance_guillaume=committed, Jeanne et Guillaume vivants et consentants, issue politique compatible | Mariage ou union libre suivant choix final ; jamais promesse déterministe du prologue |

**Règles impératives :**
- Jeanne reste jouable et complète si Guillaume meurt, est jugé ou si la romance est fermée ;
- « charisme », torture ou captivité ne constituent jamais des points de romance ;
- la confession doit nommer les victimes et la part de responsabilité ;
- Guillaume ne peut pas acheter le pardon par un acte héroïque isolé ; la réparation et les choix de Jeanne demeurent nécessaires ;
- ses compétences tactiques peuvent être utiles même lorsque Jeanne refuse toute relation ; **alliance militaire ≠ couple** ;
- si l'une des conditions manque, une issue amicale/neutralité ou rupture est disponible ; aucun softlock.

### Jeanne ↔ Aveline
| Niveau | Déclencheur | Retombée |
| --- | --- | --- |
| -100 à -20 | Exécutions et trahisons | Renforts hostiles et duel sans trêve |
| -19 à 29 | Guerre conventionnelle | Rivalité et respect professionnel conditionnel |
| 30 à 59 | Épargner, délivrer des captifs, échange vérifié | Trêve locale possible |
| 60 à 100 | Preuve du Voile + acte de coopération | Alliance contre le Veilleur, finale de paix possible |

Aveline conserve une motivation anglaise, même en cas d'alliance ; il est injustifié de la transformer en française sur un simple score.

### Jeanne ↔ Charles VII
- **Soutien :** Jeanne agit militairement avec mandat, apporte des preuves et préserve l'ordre.
- **Tension :** Jeanne publie les crimes d'un grand seigneur, agit sans permission ou refuse un compromis.
- **Rupture :** le roi peut refuser des ressources ou retirer la reconnaissance, sans supprimer le chemin principal de Jeanne.
- **Fin :** les épilogues royaux varient selon royal_favor et proofs_public ; le roi ne devient pas un méchant surnaturel.

### Jeanne ↔ Margot / Renaud / Agnès
- **Margot :** confiance reliée à la protection des civils, avec possibilité de départ temporaire et mission de réparation.
- **Renaud :** fidélité fragilisée par le mensonge au sujet de Jacques ; talent de garde rapprochée et synergies après confrontation.
- **Agnès :** preuve et interprétation plutôt que simple affection ; elle peut contredire Jeanne tout en restant utile.

## 4. Actes, variables et portes de finales

### Trois axes de conséquences (ne pas surmultiplier les flags)
- **Humanité :** civilians_saved, war_cruelty, état de Margot.
- **Pouvoir politique :** evidence, proofs_public, royal_favor.
- **Liberté / foi :** veil_knowledge, three_seals_resolved, avel_alliance et décision finale.

### Conditions de fins proposées (règles de design)
- **dawn :** Veilleur neutralisé + preuves publiques + soutien civil suffisant.
- **crown :** Veilleur neutralisé + accord de la couronne, indépendamment de la romance.
- **truce :** Veilleur neutralisé + avel_alliance=allied + trêve formalisée dans un objectif tactique.
- **embers :** acceptation délibérée d'un pouvoir risqué, disponible seulement après découverte des conséquences.
- **sacrifice :** Jeanne accepte un coût mortel après avoir vu une alternative et protège effectivement les autres.
- **exile :** victoire partielle et rejet de toute intégration au pouvoir.
- **defeat :** perdue par l'état de la mission finale, jamais automatiquement choisie par une scène de dialogue.

**Système à implémenter :** construire une liste d'options possibles à partir des résultats et du choix final explicite. Les priorités sont déterministes ; si plusieurs conditions sont satisfaites, **afficher plusieurs choix**, ne pas sélectionner automatiquement la « meilleure » fin. Le chemin « crown » / « exile » ne doit pas disparaître à cause d'un compagnon mort.

## 5. Graphe des scènes proposé

Tous les identifiants ci-dessous sont distincts et leurs arcs avancent dans le temps. Plusieurs branches aboutissent à la **même scène canonique**, sans duplication de définition.

~~~text
sc_p0_champs -> sc_p0_visions -> sc_p0_incendie
sc_p0_apres_incendie
    -> sc_p0_choix_a -> p0_03a_secours
    -> sc_p0_choix_b -> p0_03b_poursuite
sc_p0_reunion (après p0_04_fuite)
    -> sc_a1_marche -> sc_a1_hospice
        -> sc_a1_archives -> a1_04a_archives
        -> sc_a1_familles -> a1_04b_familles
sc_a1_reunion -> sc_a2_chinon -> sc_a2_cour
sc_a2_avel_arrive -> sc_a2_sacre
sc_a3_conseil -> sc_a3_jugement -> sc_a3_livre
sc_a4_compiegne -> [sc_a4_capture | sc_a4_secours]
    -> sc_a4_avel -> sc_a4_deux_voix
sc_a5_rituel -> sc_a5_final_choice
    -> [sc_end_dawn | sc_end_crown | sc_end_truce |
        sc_end_embers | sc_end_sacrifice | sc_end_exile]
~~~

**Attention :** ce diagramme montre un ordre d'auteur, **pas** une instruction d'utiliser next_scene pour sauter directement dans un combat. Le GameProject.story actuel ne dispose pas de commande « start_mission » dans les effets. L'auteur débloque donc la mission, termine la scène, puis le joueur la sélectionne dans la progression. Après victoire, StoryBook.after_victory donne le prochain nœud de récit.

## 6. Exemple de scène conforme au contrat actuel

Exemple **illustratif**, à associer à un Content contenant réellement les IDs de mission correspondants :

~~~json
{
  "id": "sc_p0_apres_incendie",
  "title": "Une décision dans les flammes",
  "speaker": "Jeanne",
  "text": "La grange s'effondre. Des survivants appellent. Un officier s'enfuit avec les papiers de mon père.",
  "choices": [
    {
      "id": "rescue",
      "label": "Sauver les villageois.",
      "effects": [
        {"kind": "set_flag", "flag": "prologue_path", "value": "secours"},
        {"kind": "add_flag", "flag": "civilians_saved", "amount": 10},
        {"kind": "unlock_mission", "mission": "p0_03a_secours"}
      ]
    },
    {
      "id": "pursue",
      "label": "Poursuivre les soldats.",
      "effects": [
        {"kind": "set_flag", "flag": "prologue_path", "value": "poursuite"},
        {"kind": "add_flag", "flag": "evidence", "amount": 10},
        {"kind": "unlock_mission", "mission": "p0_03b_poursuite"}
      ]
    }
  ]
}
~~~

**Pourquoi cet exemple est valide sur le plan des formes :** ID sûr, deux choix inconditionnels, effets connus, pas de cycle. **Condition de validation restante :** les missions de sortie existent dans Content et la scène est insérée dans un GameProject.story complet ; les exemples ne sont pas chargés en production tels quels. Déclarer un seul successeur dans next_missions ou débloquer toutes les branches ruinerait l'exclusivité.

Pour ajouter une scène alternative, définir des prédicats **when** sur les choix et garder systématiquement une issue inconditionnelle ; veiller à l'ordre d'affichage. Aucun effet de « rejoindre automatiquement une armée », « romance », « spawn boss » ou « duel » n'existe nativement dans StoryBook : ce sont des conséquences modélisées par flags, contenu, triggers et orchestration dans le joueur.

## 7. Délivrables d'intégration par PR

### PR 3.0.1 — Bible narrative (ce document)
- Bible, dossiers personnages, macro-actes, motifs et révélations.
- Catalogue de missions, branches, flags, relations et fins.
- Aucun changement de moteur ; aucun changement de sauvegarde.
- Gate : IDs cohérents entre documents, branches rejoignables, changement d'univers explicitement fictionnel.

### PR 3.0.2 — Contenu autonome Jeanne
- Créer une campagne de **démonstration** à côté de core.json existant, pas un remplacement destructeur.
- Ajouter Jeanne, Renaud, soldats humains et équipements médiévaux via les modèles validés.
- Registre d'assets nouveau et facultatif ; pas de dépendance forcée à des images/sons.
- Valider l'import Content/GameProject et trois rencontres de base.
- Ne pas renommer le package Python lors de l'authoring narratif.

### PR 3.0.3 — Prologue réellement jouable
- Scène des champs, vision en dialogue, flashback tutoriel, incendie, choix secours/poursuite, extraction.
- Chaque branche propose un objectif tactique réalisable et rejouable.
- Sauvegarde/reprise après choix et pendant une bataille ; visuels/audio facultatifs.
- Tests des deux branches, du chargement et de la non duplication de récompense.

### PR 3.0.4 — Relations et variables contrôlées
- Catalogue de flags typés/initialisation ; validateurs de cohérence et bornes.
- Portraits/dialogues conditionnels, conséquences visibles dans les objectifs tactiques.
- Tests de combinaison Guillaume : vérité et réparation requises, refus sans softlock, réversibilité de romance.
- Réutiliser les Tactical Bonds déjà disponibles sans confondre affinité de combat et sentiment.

### PR 3.1 — Acte I complet
- Cinq missions principales sur deux branches, deux secondaires ciblées.
- Preuves redondantes, première confrontation Guillaume, nouveau compagnon quoi qu'il arrive.
- CI et capture de toutes les routes.

### PR 3.2 — Chinon, Orléans, Reims
- Charles, Aveline, réputation et preuves ; cinq missions et scènes.
- Première rencontre Aveline avec objectif non létal et victoire vérifiable.

### PR 3.3 — Réécriture narrative du château
- Réutiliser / intégrer après fusion des PR **#31** et **#33** plutôt que réimplémenter le siège.
- Adapter personnages, objectifs, conditions et conséquences de Valcroix.
- Vérifier replay, arrivées multi-fronts, diplomatie, état de ravitaillement, vrai boss et sauvegarde.
- **Ne pas supprimer** l'exemple de château générique si d'autres tests le couvrent.

### PR 3.4 — Actes IV et V
- Compiègne, captivité/secours, alliance/rivalité Aveline, derniers reliquaires et final.
- Pouvoirs occultes implémentés par les registries/modèles existants de compétences et boss.
- Une matrice de simulation des fins et états politiques, plus tests d'accessibilité des routes.

## 8. Tests nécessaires dès la première implémentation

1. Toutes les scènes et conditions sont validées sans cycles, doublons, références perdues, ni impasse sans choix visible.
2. Les deux options de Domrémy ne débloquent **pas** simultanément leurs missions alternatives.
3. Le retour des branches ne réinitialise aucun score ou flag.
4. Chaque route rejoint une fin jouable ; le sacrifice est toujours une décision, pas une punition.
5. Tous les indices majeurs possèdent une source de secours si un compagnon ou une mission facultative manque.
6. Le mariage est impossible si Jeanne est mineure, captive, sans vérité complète, sans réparation, ou si le joueur a fermé la romance.
7. La présence/absence de Guillaume et d'Aveline ne bloque ni le trône de Valcroix ni la mission finale.
8. Les points de non-retour et sauvegardes sont explicites ; recharger après décision conserve ses effets exactement une fois.
9. Aucune scène ne valide automatiquement un siège, un boss, une trêve ou une sortie : le moteur fournit un résultat vérifié.
10. Tests de scénario matrice : protectrice, vengeresse, diplomate, sombre, sacrifice, rupture, Aveline hostile et chemins partiels.

## 9. Points ouverts — à arbitrer avant écrire la campagne complète

- **Nom public définitif** : « Jeanne d'Arc — Les Cendres du Royaume » est un titre de travail.
- **Densité des cinématiques** : principalement portraits/dialogues avec un rendu illustré, ou cinématiques 2D spécifiques.
- **Âge/ellipse** : proposition 17 ans au prologue puis majorité à Chinon ; adapter seulement en vérifiant toutes les scènes de relation.
- **Permadeath** : ne pas le généraliser en v1 ; écriture et QA exploseraient. Préférer blessures et départs scriptés dont les conditions sont visibles.
- **Négociation à Valcroix** : l'alternative « accord sans boss » nécessiterait une vraie évolution du moteur ; la vertical slice #31 actuelle exige une victoire au trône.
- **Découpage du siège dans Studio** : vérifier le contrat définitif de la PR #33 et ne pas conserver les schémas concurrents (PR #32 superseded).
- **Localisation** : contenu source FR, IDs stables en ASCII, textes traduisibles par clef dans une PR ultérieure.

## 10. Critère d'acceptation du contenu complet

Le joueur peut : créer une partie Jeanne -> vivre le prologue -> choisir deux chemins réellement exclusifs -> développer des relations non obligatoires -> convaincre Charles -> gagner une mission d'Orléans -> prendre Valcroix par une approche tactique authentique -> choisir le destin de Guillaume -> découvrir la vérité avec ou sans Aveline -> vaincre l'entité -> choisir une fin correspondant aux conditions et retrouver toutes les décisions dans un épilogue et une sauvegarde cohérents.

**Une bible de design ne valide pas ce gate :** seules des missions et scènes chargées, jouées et testées à partir de données réelles pourront le certifier.
