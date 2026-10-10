# 3.0.2 + 3.0.3 — Jeanne : contenu autonome et prologue jouable

**État : tranche verticale du prologue en données tactiques/narratives ; pas la campagne complète.**

L'objectif est de commencer une histoire de Jeanne d'Arc **uchronique** dans le Player existant, sans casser les tests et les scénarios historiques de Sporebound. Le moteur de combat et les sauvegardes restent identiques.

## Lancer le jeu

Depuis la racine du dépôt, sous Python 3.10+ :

~~~sh
python -m sporebound validate --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json
python -m sporebound player --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json
~~~

Dans la fenêtre, sélectionner « Les Cendres de Domrémy », emplacement 1 puis « Nouvelle partie ». Les sauvegardes sont enregistrées par le **PlayerController** dans le profil du projet ; « Continuer » les recharge par un checkpoint vérifié. Les JSON sont inclus dans le package au même titre que les exemples initiaux.

Pour lancer le Studio sur le contenu Jeanne :

~~~sh
python -m sporebound editor --content sporebound/content/jeanne.json
~~~

L'éditeur permet d'inspecter les cartes et les unités. Les scènes de dialogue résident dans le projet **jeanne.game.json** ; utiliser les fonctions de Studio compatibles avec le manifeste sans confondre la carte tactique et l'arbre de scènes.

## Scènes et parcours jouables

1. **Les champs** : introduction dialoguée ; écouter les voix ou les repousser. Le déplacement libre dans les champs n'est **pas encore** disponible et nécessite une extension de Player/carte d'exploration.
2. **La vision** : bannière, couronne, bûcher ; Jeanne découvre la fumée.
3. **Souvenir de Renaud** : mission tactique « leçon d'armes », combat de formation non létal dans l'histoire ; objectif du moteur = vaincre le partenaire d'entraînement.
4. **Domrémy en flammes** : vrai combat contre deux pillards, puis choix exclusif.
5. **Secours** : tenir la défense jusqu'à l'évacuation ; protéger Margot.
6. **Poursuite** : vaincre le garde et le porteur de sceau pour récupérer un indice.
7. **Fuite** : atteindre les cases d'extraction à l'est en gardant en vie un rescapé.
8. **Promesse** : épilogue dialogué ; aucun contenu des actes I–V ne se débloque à ce stade.

### Choix et états
- Choix « secourir » : \`prologue_path="secours"\`, \`civilians_saved+=10\`, déverrouille seulement \`p0_03a_secours\`.
- Choix « poursuivre » : \`prologue_path="poursuite"\`, \`evidence+=10\`, déverrouille seulement \`p0_03b_poursuite\`.
- Après la mission choisie, une scène unique et partagée déverrouille \`p0_04_fuite\`.
- L'épilogue sauvegarde \`prologue_complete=true\` et laisse la campagne sans mission disponible, sans recommencer un ancien scénario champignon.

Le graphe conserve un chemin neutre après les deux options ; **aucun** \`Mission.next_missions\` n'ouvre les deux branches à la fois. \`GameSession\` suit les victoires réelles et applique les récompenses une seule fois.

## Gameplay et limites

- Les personnages sont des combattants humains. Les compétences « Estoc », « Frappe de garde » et « Premiers soins » utilisent les règles physiques/soins existantes, sans magie de combat, invocation ou démons.
- L'apparence utilise le renderer Tk actuel, sans sprites ou cinématiques spécifiques : portraits, feu animé, fumée, champ traversable et coupe narrative sont des travaux de **présentation ultérieurs**.
- Le flashback est matérialisé par une mission d'entraînement qui se termine lorsque Renaud perd tous ses PV : il ne meurt **pas** dans l'histoire ; les objectifs avancés de duel sans élimination feront partie de l'itération suivante.
- La mission « Secours » vérifie que Margot survit et que suffisamment de temps s'écoule ; elle ne simule pas individuellement chaque habitant. La fin « Fuite » exige une unité jouable dans une case d'extraction **et** la survie du rescapé protégé, mais pas son déplacement physique dans la zone. Un véritable objectif multi-unité d'extraction est futur.
- Les conséquences exactes des choix sont persistées pour l'acte I. Les drapeaux sont du contenu data-driven dans \`GameProject.story\` et ne requièrent aucune modification des règles ni de version de sauvegarde.
- Ce prototype n'intègre pas encore le siège de Valcroix : celui-ci appartient aux travaux de l'acte III, qui réutiliseront les PR du château.

## Tests

~~~sh
python -m unittest tests_standalone.test_jeanne_prologue -v
python -m unittest discover -s tests_standalone -v
~~~

La suite dédiée charge réellement Content et GameProject, conduit chaque chemin jusqu'à sa fin avec le moteur/IA, vérifie l'exclusivité des missions, l'absence de succès factice, la sauvegarde en plein combat et la cohérence d'une reprise. Les scripts de CI existants exécutant \`unittest discover\` incluent ce module.

## Roadmap

- **3.0.2 — terminé dans cette tranche** : nouveau contenu autonome, unités, jobs, équipements, titre et scènes.
- **3.0.3 — tranche jouable** : sept scènes et cinq rencontres ; les deux variantes de mission sont exclusives ; sauvegarde/reprise et tests.
- **3.0.3 suite** : déplacement libre dans les champs, cases de civils à sauver, animation d'incendie, caméra narrative, interactions et portraits propres à Jeanne.
- **3.1** : actes I et relations, premières preuves et retour de Guillaume.
- **3.3** : château de Valcroix (réemploi des moteurs de siège validés).
- **3.4** : démons tardifs et embranchements majeurs.

**Référence narrative :** PR #35 (\`docs/jeanne/\`). Les IDs de missions \`p0_01_lame\` à \`p0_04_fuite\`, les flags \`prologue_path\`, \`civilians_saved\` et \`evidence\` reprennent le catalogue de cette bible.
