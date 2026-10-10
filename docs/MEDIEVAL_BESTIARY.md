# 3.1 — Personnages, bestiaire médiéval et progression

Une première bibliothèque médiévale optionnelle pour la campagne alternative de
Jeanne d'Arc. Elle **ne remplace pas** le contenu historique de démonstration
Sporebound et conserve le format `Content v1` / les sauvegardes `Campaign v1`.

## Contenu livré

- **17 archétypes** : loup, loup alpha, chien de guerre, sanglier, bandit,
  archer bandit, pillard, chef bandit, milicien, écuyer, épéiste, lancier,
  arbalétrier, soigneur, chevalier, capitaine d'armes, troll de siège (2×2).
- **10 compétences** dont morsure, cri de meute, charge, garde, estoc,
  tir visé, bandage, ralliement, brise-garde et entaille entravante.
- **11 classes** avec prérequis de niveaux, compétences, bonus et talents.
- **8 objets** d'équipement (armes, armures et accessoires).
- **3 grades** : normal, vétéran (+20 % PV, +2 attaque, +1 défense)
  et élite (+45 % PV, +4 attaque, +3 défense, +1 vitesse).

L'identité du monstre et son tier sont des métadonnées de catalogue, pas de
nouveaux champs du moteur. Le rang choisi est matérialisé à la pose de l'unité
par des statistiques et un tag `rank:veteran` ou `rank:elite`.

## Utilisation Studio

`Personnages & règles 3.0 → Bestiaire médiéval` :

1. **Installer le catalogue** (une seule transaction Undo/Redo).
2. Sélectionner une fiche et lire son rôle.
3. Entrer un ID unique, son nom, son camp (`player` / `enemy`), son
   grade et la position `x,y` ou `auto`.
4. **Placer le personnage** dans la mission active.

`auto` choisit la première zone libre et praticable de la bonne taille,
sans traverser les unités, cases bloquées ou objets existants. Le validateur
du moteur contrôle encore l'ensemble du scénario avant l'enregistrement.

### API de création

```python
from sporebound.medieval_catalog import install_pack, place_entry, find_free_cell
from sporebound.model import Content

data = Content.load("my_campaign.json").to_dict()
data = install_pack(data)  # ajouter sans écraser
spot = find_free_cell(data, "mission_1", "siege_troll")
data = place_entry(data, "mission_1", "siege_troll", "troll_01",
                   "enemy", spot, rank="elite")
Content.from_dict(data)  # validation réelle
```

Toutes les opérations sont *pures* : un refus laisse le document initial
inchangé. Réinstaller le pack identique est sans effet ; un ID `med_*`
déjà utilisé pour une définition différente fait échouer toute l'opération.

## Évolution des personnages

Le système existant de campagne reste **la source de vérité** :

- niveau du personnage : `1 + XP // 100` (limité à 20) ;
- niveau de classe : `1 + XP_classe // 50` (limité à 20) ;
- points JP disponibles : `XP_classe // 50 - JP_dépensés` ;
- 100 XP et 50 XP de classe par victoire de mission validée, une fois ;
- un changement de classe est autorisé si le prérequis est atteint ;
- les talents s'achètent séparément et restent persistés ;
- les bonus de classe, compétences et talents sont appliqués à la préparation
  de combat, sans modifier les templates ni les unités des autres missions.

Chemins initiaux :

```text
Recrue
├── Écuyer
│   ├── Épéiste → Duelliste
│   └── Garde   → Chevalier
├── Archer      → Tireur d'élite
├── Éclaireur   → Rôdeur
└── Soigneur
```

Dans le client Tk classique, l'écran **Talents / classes** permet maintenant
de choisir aussi une classe sans talents et de changer de classe en campagne.
Le changement est persisté avant la modification de l'état en mémoire ;
la sélection et l'achat des talents restent interdits pendant les combats.

**Important :** les `med_*` jobs doivent être volontairement sélectionnés
sur une recrue. Installer le pack ne change pas rétroactivement les héros
existants ni leur classe `brave`.

## Tests

```bash
python -m unittest discover -s tests_standalone -p 'test_medieval_catalog.py' -v
python -m unittest discover -s tests_standalone -v
```

Les nouveaux tests couvrent la compatibilité Content v1, l'isolation des
imports, les collisions, les unités 2×2, les grades, les prérequis de classe,
l'attribution des JP et la sauvegarde/relecture d'un personnage évolué.

## Étapes suivantes

1. **3.1.2 — Traits et IA de bestiaire** : chasse en meute réelle, tactique
   des brigands, moral/fuite, comportement de boss/troll et contrôles de
   simulation. Les tags ajoutés ici ne prétendent pas fournir ces
   comportements tant qu'ils ne sont pas implémentés.
2. **3.1.3 — Récompenses et recrutement** : XP par participation, blessure,
   mort permanente configurable, recrutement et promotion narrative.
3. **3.1.4 — Dossiers de personnages** : relations avec Jeanne, biographies,
   équipement visuel, animations, portraits et journal des événements.
4. **3.1.5 — Équilibrage et éditeur de progression** : courbes de difficulté,
   stats/compétences par niveau, comparaison de builds et tests combat p95.
